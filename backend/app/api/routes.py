from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from .. import llm
from ..config import settings
from ..db import SessionLocal
from ..models import RunEvent, RunMetric, Snapshot
from ..schemas import (
    BranchRequest, ChronicleRequest, CompareRequest, ControlRequest,
    RunCreateRequest, SnapshotRequest,
)
from ..services.runtime import manager
from ..services.emergence import detect_emergence
from ..version import __version__

router = APIRouter(prefix="/api")


def _runtime(run_id: str):
    runtime = manager.runtime(run_id)
    if not runtime:
        raise HTTPException(status_code=404, detail="Run not found")
    return runtime


def _event_row(row: RunEvent) -> dict:
    return {
        "id": row.event_id,
        "run_id": row.run_id,
        "day": row.day,
        "year": row.year,
        "season": row.season,
        "category": row.category,
        "importance": row.importance,
        "title": row.title,
        "description": row.description,
        "location": json.loads(row.location_json or "null"),
        "location_name": row.location_name,
        "participants": json.loads(row.participants_json or "[]"),
        "consequences": json.loads(row.consequences_json or "[]"),
        "related": json.loads(row.related_json or "{}"),
        "narrative": row.narrative,
    }


# --------------------------------------------------------------------- system
@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": __version__,
        "runs": len(manager.runtimes),
        "database": "sqlite" if settings.database_url.startswith("sqlite") else "postgresql",
        "llm": settings.llm_active,
    }


@router.get("/llm/status")
def llm_status() -> dict:
    return llm.status()


# ----------------------------------------------------------------------- runs
@router.get("/runs")
def list_runs() -> list[dict]:
    return manager.summaries()


@router.post("/runs", status_code=201)
async def create_run(payload: RunCreateRequest) -> dict:
    runtime = await manager.create_run(payload.world, note=payload.note)
    summary = manager.summary(runtime)
    summary["note"] = payload.note
    return summary


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    runtime = _runtime(run_id)
    return {"summary": manager.summary(runtime), "state": runtime.engine.to_state()}


@router.delete("/runs/{run_id}")
async def delete_run(run_id: str) -> dict:
    deleted = await manager.delete_run(run_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"deleted": True}


@router.post("/runs/{run_id}/control")
async def control_run(run_id: str, payload: ControlRequest) -> dict:
    _runtime(run_id)
    try:
        return await manager.control(run_id, payload.action, payload.speed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs/{run_id}/state")
def get_state(run_id: str) -> dict:
    return _runtime(run_id).engine.to_state()


@router.get("/runs/{run_id}/world")
def get_world(run_id: str) -> dict:
    engine = _runtime(run_id).engine
    world = engine.world
    terrain, elevation, water, fertility, buildable, passable, freshwater, owner, resources = ([] for _ in range(9))
    for tile in world.tiles:
        terrain.append(tile.terrain)
        elevation.append(round(float(tile.elevation), 3))
        water.append(round(float(tile.water), 2))
        fertility.append(round(float(tile.fertility), 2))
        buildable.append(bool(tile.buildable))
        passable.append(bool(tile.passable))
        freshwater.append(bool(tile.freshwater))
        owner.append(tile.owner)
        resources.append({k: round(float(v), 1) for k, v in tile.resources.items()} if tile.resources else {})
    return {
        "width": world.width,
        "height": world.height,
        "seed": world.seed,
        "land_ratio": round(world.land_ratio, 3),
        "rivers": world.rivers,
        "lakes": world.lakes,
        "biomes": world.biome_counts(),
        "start_sites": world.start_sites,
        "weather": world.weather,
        "disaster": world.active_disaster.to_dict() if world.active_disaster else None,
        "tiles": {
            "terrain": terrain, "elevation": elevation, "water": water,
            "fertility": fertility, "buildable": buildable, "passable": passable,
            "freshwater": freshwater, "owner": owner, "resources": resources,
        },
    }


@router.get("/runs/{run_id}/agents")
def get_agents(run_id: str) -> list[dict]:
    return [agent.to_summary() for agent in _runtime(run_id).engine.agents.values()]


@router.get("/runs/{run_id}/agents/{agent_id}")
def get_agent(run_id: str, agent_id: str) -> dict:
    data = _runtime(run_id).engine.agent_detail(agent_id)
    if not data:
        raise HTTPException(status_code=404, detail="Agent not found")
    return data


@router.get("/runs/{run_id}/settlements")
def get_settlements(run_id: str) -> list[dict]:
    engine = _runtime(run_id).engine
    return [settlement.to_summary(engine.agents) for settlement in engine.settlements.values()]


@router.get("/runs/{run_id}/settlements/{settlement_id}")
def get_settlement(run_id: str, settlement_id: str) -> dict:
    data = _runtime(run_id).engine.settlement_detail(settlement_id)
    if not data:
        raise HTTPException(status_code=404, detail="Settlement not found")
    return data


@router.get("/runs/{run_id}/technology")
def get_technology(run_id: str) -> dict:
    return _runtime(run_id).engine.technology_view()


@router.get("/runs/{run_id}/events")
def get_events(
    run_id: str,
    category: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    before_day: int | None = None,
    min_importance: int = Query(default=1, ge=1, le=5),
) -> list[dict]:
    _runtime(run_id)
    with SessionLocal() as session:
        query = session.query(RunEvent).filter(
            RunEvent.run_id == run_id,
            RunEvent.importance >= min_importance,
        )
        if category and category != "all":
            query = query.filter(RunEvent.category == category)
        if before_day is not None:
            query = query.filter(RunEvent.day < before_day)
        rows = query.order_by(RunEvent.day.desc(), RunEvent.id.desc()).limit(limit).all()
    return [_event_row(row) for row in reversed(rows)]


@router.get("/runs/{run_id}/metrics")
def get_metrics(run_id: str, limit: int = Query(default=1000, ge=1, le=3000)) -> list[dict]:
    _runtime(run_id)
    with SessionLocal() as session:
        rows = (
            session.query(RunMetric)
            .filter(RunMetric.run_id == run_id)
            .order_by(RunMetric.day.desc())
            .limit(limit)
            .all()
        )
    return [json.loads(row.metrics_json) for row in reversed(rows)]


@router.get("/runs/{run_id}/history")
def get_history(
    run_id: str,
    category: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    before_day: int | None = None,
) -> list[dict]:
    return _runtime(run_id).engine.history_view(category=category, limit=limit, before_day=before_day)


@router.get("/runs/{run_id}/emergence")
def get_emergence(run_id: str) -> dict:
    runtime = _runtime(run_id)
    with SessionLocal() as session:
        return detect_emergence(run_id, runtime.engine, session)


# ------------------------------------------------------------------ snapshots
@router.get("/runs/{run_id}/snapshots")
def list_snapshots(run_id: str) -> list[dict]:
    _runtime(run_id)
    with SessionLocal() as session:
        rows = (
            session.query(Snapshot.id, Snapshot.run_id, Snapshot.day, Snapshot.label, Snapshot.created_at)
            .filter(Snapshot.run_id == run_id)
            .order_by(Snapshot.day.desc())
            .all()
        )
    return [
        {
            "id": row.id, "run_id": row.run_id, "day": row.day, "label": row.label,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.post("/runs/{run_id}/snapshots", status_code=201)
def create_snapshot(run_id: str, payload: SnapshotRequest) -> dict:
    runtime = _runtime(run_id)
    snapshot = manager.create_snapshot(runtime.engine, label=payload.label)
    return {
        "id": snapshot.id, "run_id": snapshot.run_id, "day": snapshot.day,
        "label": snapshot.label, "created_at": snapshot.created_at.isoformat(),
    }


@router.post("/runs/{run_id}/branch", status_code=201)
async def branch_run(run_id: str, payload: BranchRequest) -> dict:
    runtime = _runtime(run_id)
    state = runtime.engine.snapshot()
    branch_day = runtime.engine.day
    if payload.snapshot_id:
        with SessionLocal() as session:
            snapshot = session.get(Snapshot, payload.snapshot_id)
            if not snapshot or snapshot.run_id != run_id:
                raise HTTPException(status_code=404, detail="Snapshot not found for this run")
            state = json.loads(snapshot.state_json)
            branch_day = snapshot.day
    branch = await manager.create_branch(runtime.engine, state, payload.note, payload.world_name)
    branch.engine.status = "paused"
    summary = manager.summary(branch)
    summary.update({"note": payload.note, "parent_run_id": run_id, "branch_day": branch_day})
    return summary


# ---------------------------------------------------------------- experiments
@router.post("/experiments/compare")
def compare_runs(payload: CompareRequest) -> dict:
    runs = []
    series = []
    for run_id in payload.run_ids:
        runtime = manager.runtime(run_id)
        if not runtime:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        summary = manager.summary(runtime)
        runs.append(summary)
        with SessionLocal() as session:
            rows = (
                session.query(RunMetric)
                .filter(RunMetric.run_id == run_id)
                .order_by(RunMetric.day.asc())
                .all()
            )
        points = []
        for row in rows:
            data = json.loads(row.metrics_json)
            points.append({
                "day": row.day,
                "population": data.get("population"),
                "food": data.get("food"),
                "settlements": data.get("settlements"),
                "tech_count": data.get("tech_count"),
                "avg_happiness": data.get("avg_happiness"),
                "inequality": data.get("inequality"),
                "stability": data.get("stability"),
            })
        series.append({"run_id": run_id, "name": summary["world_name"], "points": points})
    return {"runs": runs, "series": series}


# ---------------------------------------------------------------------- LLM
@router.post("/runs/{run_id}/chronicle")
async def chronicle(run_id: str, payload: ChronicleRequest) -> dict:
    runtime = _runtime(run_id)
    engine = runtime.engine
    events = engine.history_view(limit=max(10, payload.days), before_day=None)
    context = {
        "world": engine.config.world_name,
        "day": engine.day,
        "year": engine.year,
        "population": len(engine.alive_agents()),
        "settlements": [
            {"name": s.name, "population": s.population, "buildings": len(s.buildings), "techs": s.known_techs}
            for s in engine.settlements.values() if not s.ruins
        ],
        "metrics": engine.latest_metrics,
        "events": [
            {"day": e["day"], "category": e["category"], "title": e["title"], "description": e["description"]}
            for e in events
        ],
    }
    try:
        text = await llm.generate_chronicle(context, kind=payload.kind)
    except llm.LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"text": text, "model": settings.llm_model, "day": engine.day}


# ----------------------------------------------------------------- WebSocket
@router.websocket("/ws/runs/{run_id}")
async def websocket_run(websocket: WebSocket, run_id: str) -> None:
    if settings.api_key:
        supplied = websocket.query_params.get("api_key", "")
        if supplied != settings.api_key:
            await websocket.close(code=4401)
            return
    connected = await manager.connect(run_id, websocket)
    if not connected:
        await websocket.close(code=4404)
        return
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(run_id, websocket)
    except Exception:
        manager.disconnect(run_id, websocket)
