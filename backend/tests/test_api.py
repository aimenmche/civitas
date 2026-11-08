from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_full_api_flow() -> None:
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        assert health.json()["version"] == "0.3.0"

        created = client.post("/api/runs", json={
            "world": {"seed": 4242, "world_name": "PyTest World", "initial_population": 12},
            "note": "api test",
        })
        assert created.status_code == 201
        run_id = created.json()["id"]
        assert created.json()["population"] == 12

        listed = client.get("/api/runs")
        assert listed.status_code == 200
        assert any(run["id"] == run_id for run in listed.json())

        paused = client.post(f"/api/runs/{run_id}/control", json={"action": "pause"})
        assert paused.status_code == 200
        assert paused.json()["status"] == "paused"

        stepped = client.post(f"/api/runs/{run_id}/control", json={"action": "step"})
        assert stepped.status_code == 200
        assert stepped.json()["stepped"] is True
        stepped = client.post(f"/api/runs/{run_id}/control", json={"action": "step"})
        assert stepped.json()["day"] == 2

        state = client.get(f"/api/runs/{run_id}/state")
        assert state.status_code == 200
        assert state.json()["run"]["day"] == 2
        assert len(state.json()["agents"]) == 12

        world = client.get(f"/api/runs/{run_id}/world")
        assert world.status_code == 200
        payload = world.json()
        assert payload["width"] * payload["height"] == len(payload["tiles"]["terrain"])

        technology = client.get(f"/api/runs/{run_id}/technology")
        assert technology.status_code == 200
        assert len(technology.json()["tree"]) > 10

        events = client.get(f"/api/runs/{run_id}/events")
        assert events.status_code == 200

        metrics = client.get(f"/api/runs/{run_id}/metrics")
        assert metrics.status_code == 200
        assert len(metrics.json()) >= 1

        snapshot = client.post(f"/api/runs/{run_id}/snapshots", json={"label": "api test snapshot"})
        assert snapshot.status_code == 201
        snapshot_id = snapshot.json()["id"]

        branch = client.post(f"/api/runs/{run_id}/branch", json={"snapshot_id": snapshot_id, "note": "branch"})
        assert branch.status_code == 201
        branch_id = branch.json()["id"]
        assert branch.json()["parent_run_id"] == run_id

        comparison = client.post("/api/experiments/compare", json={"run_ids": [run_id, branch_id]})
        assert comparison.status_code == 200
        assert len(comparison.json()["series"]) == 2

        deleted = client.delete(f"/api/runs/{branch_id}")
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True
