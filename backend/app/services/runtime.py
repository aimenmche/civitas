from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket
from sqlalchemy import select

from ..config import settings
from ..db import SessionLocal
from ..models import Run, RunEvent, RunMetric, Snapshot
from ..sim.engine import SimulationEngine
from ..sim.world import WorldConfig

log = logging.getLogger("civitas.runtime")


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(5)}"


@dataclass
class RunRuntime:
    engine: SimulationEngine
    speed: float = 1.0
    task: asyncio.Task | None = None
    subscribers: set[WebSocket] = field(default_factory=set)
    persisted_event_ids: set[str] = field(default_factory=set)
    persisted_metric_days: set[int] = field(default_factory=set)
    last_step_at: float = 0.0
    last_saved_day: int = 0
    stopping: bool = False

    @property
    def interval(self) -> float:
        return 1.0 / max(0.1, min(32.0, self.speed))


class SimulationManager:
    def __init__(self) -> None:
        self.runtimes: dict[str, RunRuntime] = {}
        self._lock = asyncio.Lock()

    # -------------------------------------------------------------- lifecycle
    async def startup(self) -> None:
        with SessionLocal() as session:
            rows = session.scalars(select(Run)).all()
            for row in rows:
                try:
                    runtime = self._runtime_from_row(row)
                except Exception:
                    log.exception("Could not restore run %s", row.id)
                    continue
                self.runtimes[row.id] = runtime
                runtime.task = asyncio.create_task(self._loop(runtime))
                log.info("Restored run %s at day %s", row.id, row.day)

    async def shutdown(self) -> None:
        for runtime in self.runtimes.values():
            runtime.stopping = True
            if runtime.task:
                runtime.task.cancel()
        for runtime in self.runtimes.values():
            try:
                self._persist_run(runtime, save_state=True)
            except Exception:
                log.exception("Could not save run %s during shutdown", runtime.engine.run_id)
        await asyncio.sleep(0)

    def _runtime_from_row(self, row: Run) -> RunRuntime:
        state = json.loads(row.state_json) if row.state_json and row.state_json != "{}" else None
        if state:
            engine = SimulationEngine.from_snapshot(row.id, state)
        else:
            engine = SimulationEngine(row.id, WorldConfig(**json.loads(row.config_json or "{}")))
        engine.status = "paused" if row.status == "ended" and engine.status != "ended" else row.status
        runtime = RunRuntime(engine=engine, speed=float(row.speed or 1.0), last_saved_day=row.day)
        self._load_persisted_markers(runtime)
        return runtime

    def _load_persisted_markers(self, runtime: RunRuntime) -> None:
        with SessionLocal() as session:
            runtime.persisted_event_ids = set(
                session.scalars(select(RunEvent.event_id).where(RunEvent.run_id == runtime.engine.run_id)).all()
            )
            runtime.persisted_metric_days = set(
                session.scalars(select(RunMetric.day).where(RunMetric.run_id == runtime.engine.run_id)).all()
            )

    async def create_run(self, config: WorldConfig, note: str = "", parent_run_id: str | None = None, branch_day: int | None = None) -> RunRuntime:
        run_id = _new_id("run")
        engine = SimulationEngine(run_id, config)
        if parent_run_id:
            engine.status = "paused"
        runtime = RunRuntime(engine=engine, speed=1.0)
        self.runtimes[run_id] = runtime
        with SessionLocal() as session:
            row = Run(
                id=run_id,
                world_name=config.world_name,
                preset=config.preset,
                seed=engine.seed,
                status=engine.status,
                speed=runtime.speed,
                day=engine.day,
                note=note,
                parent_run_id=parent_run_id,
                branch_day=branch_day,
                config_json=_json(engine.config.model_dump(mode="json")),
            )
            session.add(row)
            session.commit()
        self.persist_events(runtime)
        self.persist_metric(runtime)
        self.save_state(runtime)
        runtime.task = asyncio.create_task(self._loop(runtime))
        return runtime

    async def create_branch(self, source: SimulationEngine, snapshot_state: dict[str, Any], note: str, world_name: str | None) -> RunRuntime:
        run_id = _new_id("run")
        state = json.loads(json.dumps(snapshot_state))
        state["status"] = "paused"
        for event in state.get("events", []):
            event["run_id"] = run_id
        engine = SimulationEngine.from_snapshot(run_id, state)
        engine.status = "paused"
        if world_name:
            engine.config.world_name = world_name
        runtime = RunRuntime(engine=engine, speed=1.0)
        self.runtimes[run_id] = runtime
        with SessionLocal() as session:
            row = Run(
                id=run_id,
                world_name=engine.config.world_name,
                preset=engine.config.preset,
                seed=engine.seed,
                status="paused",
                speed=runtime.speed,
                day=engine.day,
                note=note,
                parent_run_id=source.run_id,
                branch_day=engine.day,
                config_json=_json(engine.config.model_dump(mode="json")),
            )
            session.add(row)
            session.commit()
        self.persist_events(runtime)
        self.persist_metric(runtime)
        self.save_state(runtime)
        runtime.task = asyncio.create_task(self._loop(runtime))
        return runtime

    async def delete_run(self, run_id: str) -> bool:
        runtime = self.runtimes.pop(run_id, None)
        if runtime:
            runtime.stopping = True
            if runtime.task:
                runtime.task.cancel()
            for websocket in list(runtime.subscribers):
                try:
                    await websocket.close(code=4001)
                except Exception:
                    pass
        with SessionLocal() as session:
            row = session.get(Run, run_id)
            if not row:
                return False
            session.delete(row)
            session.commit()
        return True

    # ------------------------------------------------------------------- loop
    async def _loop(self, runtime: RunRuntime) -> None:
        try:
            while not runtime.stopping:
                await asyncio.sleep(0.12)
                if runtime.engine.status != "running":
                    continue
                now = time.monotonic()
                if now - runtime.last_step_at < runtime.interval:
                    continue
                runtime.last_step_at = now
                try:
                    runtime.engine.step()
                except Exception as exc:  # noqa: BLE001
                    log.exception("Simulation step failed for %s", runtime.engine.run_id)
                    runtime.engine.last_error = f"{type(exc).__name__}: {exc}"
                    runtime.engine.status = "error"
                    await self.broadcast(runtime, {
                        "type": "error",
                        "run_id": runtime.engine.run_id,
                        "error": runtime.engine.last_error,
                    })
                    self._persist_run(runtime, save_state=True)
                    continue
                await self.after_step(runtime)
        except asyncio.CancelledError:
            return

    async def after_step(self, runtime: RunRuntime) -> None:
        self.persist_events(runtime)
        self.persist_metric(runtime)
        self._persist_run(runtime, save_state=False)
        if runtime.engine.day - runtime.last_saved_day >= max(1, settings.autosave_interval_days):
            self.save_state(runtime)
        if runtime.engine.day % max(1, settings.snapshot_interval_days) == 0 and runtime.engine.status != "ended":
            self.create_snapshot(runtime.engine, label=f"Autosave day {runtime.engine.day}")
        payload = runtime.engine.tick_payload(include_events=True)
        payload["speed"] = runtime.speed
        await self.broadcast(runtime, payload)
        if runtime.engine.status == "ended":
            self.save_state(runtime)
            await self.broadcast(runtime, {
                "type": "status", "run_id": runtime.engine.run_id,
                "status": "ended", "day": runtime.engine.day,
            })

    # ------------------------------------------------------------- persistence
    def persist_events(self, runtime: RunRuntime) -> None:
        engine = runtime.engine
        new_events = [event for event in engine.events if event["id"] not in runtime.persisted_event_ids]
        if not new_events:
            return
        try:
            with SessionLocal() as session:
                for event in new_events[-400:]:
                    session.add(RunEvent(
                        run_id=engine.run_id,
                        event_id=event["id"],
                        day=int(event.get("day", engine.day)),
                        year=int(event.get("year", engine.year)),
                        season=str(event.get("season", engine.season)),
                        category=str(event.get("category", "world")),
                        importance=int(event.get("importance", 2)),
                        title=str(event.get("title", ""))[:300],
                        description=str(event.get("description", "")),
                        location_json=_json(event.get("location")),
                        location_name=event.get("location_name"),
                        participants_json=_json(event.get("participants", [])),
                        consequences_json=_json(event.get("consequences", [])),
                        related_json=_json(event.get("related", {})),
                        narrative=event.get("narrative"),
                    ))
                    runtime.persisted_event_ids.add(event["id"])
                session.commit()
        except Exception:
            log.exception("Could not persist events for %s", engine.run_id)

    def persist_metric(self, runtime: RunRuntime) -> None:
        engine = runtime.engine
        if not engine.latest_metrics or engine.day in runtime.persisted_metric_days:
            return
        try:
            with SessionLocal() as session:
                session.add(RunMetric(run_id=engine.run_id, day=engine.day, metrics_json=_json(engine.latest_metrics)))
                session.commit()
            runtime.persisted_metric_days.add(engine.day)
        except Exception:
            log.exception("Could not persist metric for %s", engine.run_id)

    def _persist_run(self, runtime: RunRuntime, save_state: bool = False) -> None:
        engine = runtime.engine
        try:
            with SessionLocal() as session:
                row = session.get(Run, engine.run_id)
                if not row:
                    return
                row.day = engine.day
                row.status = engine.status
                row.speed = runtime.speed
                row.seed = engine.seed
                row.updated_at = datetime.now(timezone.utc)
                if save_state:
                    row.state_json = _json(engine.snapshot())
                    runtime.last_saved_day = engine.day
                session.commit()
        except Exception:
            log.exception("Could not persist run %s", engine.run_id)

    def save_state(self, runtime: RunRuntime) -> None:
        self._persist_run(runtime, save_state=True)

    def create_snapshot(self, engine: SimulationEngine, label: str = "") -> Snapshot:
        snapshot_id = _new_id("snap")
        with SessionLocal() as session:
            snapshot = Snapshot(
                id=snapshot_id,
                run_id=engine.run_id,
                day=engine.day,
                label=label or f"Day {engine.day}",
                state_json=_json(engine.snapshot()),
            )
            session.add(snapshot)
            session.commit()
            session.refresh(snapshot)
            session.expunge(snapshot)
        if label.startswith("Autosave"):
            # Automatic snapshots are checkpoints, not an archive. Keep the
            # newest twenty and drop older ones so a long-running world does
            # not grow the database by megabytes every few minutes.
            with SessionLocal() as session:
                old_ids = [
                    row[0] for row in session.execute(
                        select(Snapshot.id)
                        .where(Snapshot.run_id == engine.run_id, Snapshot.label.like("Autosave%"))
                        .order_by(Snapshot.day.desc())
                        .offset(20)
                    ).all()
                ]
                if old_ids:
                    session.query(Snapshot).filter(Snapshot.id.in_(old_ids)).delete(synchronize_session=False)
                    session.commit()
        return snapshot

    # ----------------------------------------------------------------- control
    async def control(self, run_id: str, action: str, speed: float | None) -> dict[str, Any]:
        runtime = self.runtimes.get(run_id)
        if not runtime:
            raise KeyError(run_id)
        engine = runtime.engine
        if action == "pause":
            if engine.status == "running":
                engine.status = "paused"
        elif action == "resume":
            if engine.status == "ended":
                return {
                    "status": "ended", "day": engine.day, "resumed": False,
                    "reason": "no living agents remain",
                    "message": "This world has ended. Create a new world, or branch from a snapshot on the Time Machine page.",
                }
            if engine.status in ("paused", "error"):
                engine.status = "running"
                runtime.last_step_at = 0.0
        elif action == "step":
            if engine.status == "ended":
                return {
                    "status": engine.status, "day": engine.day, "stepped": False,
                    "reason": "no living agents remain",
                    "message": "This world has ended. Step is disabled because no living agents remain.",
                }
            was_running = engine.status == "running"
            engine.status = "paused"
            engine.step()
            await self.after_step(runtime)
            if was_running:
                engine.status = "running"
            return {"status": engine.status, "day": engine.day, "stepped": True}
        elif action == "speed":
            if speed is None:
                raise ValueError("speed is required")
            runtime.speed = max(0.1, min(32.0, speed))
            runtime.last_step_at = 0.0
        self._persist_run(runtime, save_state=False)
        await self.broadcast(runtime, {
            "type": "status", "run_id": run_id, "status": engine.status,
            "day": engine.day, "speed": runtime.speed,
        })
        return {"status": engine.status, "day": engine.day, "speed": runtime.speed}

    # --------------------------------------------------------------- broadcast
    async def broadcast(self, runtime: RunRuntime, payload: dict[str, Any]) -> None:
        if not runtime.subscribers:
            return
        dead: list[WebSocket] = []
        for websocket in list(runtime.subscribers):
            try:
                await websocket.send_json(payload)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            runtime.subscribers.discard(websocket)

    async def connect(self, run_id: str, websocket: WebSocket) -> bool:
        runtime = self.runtimes.get(run_id)
        if not runtime:
            return False
        await websocket.accept()
        runtime.subscribers.add(websocket)
        await websocket.send_json({"type": "state", "state": runtime.engine.to_state()})
        return True

    def disconnect(self, run_id: str, websocket: WebSocket) -> None:
        runtime = self.runtimes.get(run_id)
        if runtime:
            runtime.subscribers.discard(websocket)

    # ------------------------------------------------------------------ queries
    def runtime(self, run_id: str) -> RunRuntime | None:
        return self.runtimes.get(run_id)

    def summary(self, runtime: RunRuntime) -> dict[str, Any]:
        engine = runtime.engine
        return {
            "id": engine.run_id,
            "world_name": engine.config.world_name,
            "preset": engine.config.preset,
            "seed": engine.seed,
            "status": engine.status,
            "speed": runtime.speed,
            "day": engine.day,
            "population": len(engine.alive_agents()),
            "settlements": len([s for s in engine.settlements.values() if not s.ruins]),
            "note": "",
            "parent_run_id": None,
            "branch_day": None,
            "last_error": engine.last_error,
        }

    def summaries(self) -> list[dict[str, Any]]:
        runs = [self.summary(runtime) for runtime in self.runtimes.values()]
        with SessionLocal() as session:
            rows = {
                row.id: row for row in session.execute(
                    select(Run.id, Run.note, Run.parent_run_id, Run.branch_day, Run.created_at, Run.updated_at)
                ).all()
            }
        output = []
        for run in runs:
            row = rows.get(run["id"])
            if row:
                run.update({
                    "note": row.note, "parent_run_id": row.parent_run_id,
                    "branch_day": row.branch_day,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                })
            output.append(run)
        output.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        return output


manager = SimulationManager()
