from __future__ import annotations

from app.sim.engine import SimulationEngine
from app.sim.world import WorldConfig


def test_world_generation_is_deterministic() -> None:
    a = SimulationEngine("world_a", WorldConfig(seed=321))
    b = SimulationEngine("world_b", WorldConfig(seed=321))
    assert [t.terrain for t in a.world.tiles] == [t.terrain for t in b.world.tiles]
    assert a.world.land_ratio == b.world.land_ratio
    assert len(a.world.start_sites) >= 1


def test_deterministic_replay() -> None:
    a = SimulationEngine("replay_a", WorldConfig(seed=123))
    b = SimulationEngine("replay_b", WorldConfig(seed=123))
    for _ in range(40):
        a.step()
        b.step()
    assert a.day == b.day
    assert a.births == b.births
    assert a.deaths == b.deaths
    assert sorted(a.run_techs) == sorted(b.run_techs)
    assert len(a.settlements) == len(b.settlements)
    for agent in a.alive_agents():
        other = b.agents[agent.id]
        assert agent.position == other.position
        assert agent.inventory == other.inventory
        assert agent.needs == other.needs


def test_snapshot_restore_and_continue() -> None:
    original = SimulationEngine("snap_a", WorldConfig(seed=55))
    for _ in range(12):
        original.step()
    state = original.snapshot()
    restored = SimulationEngine.from_snapshot("snap_b", state)
    assert restored.day == original.day
    for agent in original.alive_agents():
        copy = restored.agents[agent.id]
        assert copy.position == agent.position
        assert copy.inventory == agent.inventory
    for _ in range(6):
        original.step()
        restored.step()
    assert original.day == restored.day
    assert len(original.alive_agents()) == len(restored.alive_agents())
    for agent in original.alive_agents():
        assert agent.position == restored.agents[agent.id].position
        assert agent.needs == restored.agents[agent.id].needs


def test_survival_long_run_has_events_and_no_error() -> None:
    engine = SimulationEngine("longrun", WorldConfig(seed=8))
    for _ in range(90):
        engine.step()
    assert engine.last_error is None
    assert engine.day == 90
    assert len(engine.events) > 10
    assert len(engine.alive_agents()) > 0
    assert engine.latest_metrics["population"] == len(engine.alive_agents())
    assert engine.metrics_history[-1]["day"] == engine.day


def test_agents_use_real_state() -> None:
    engine = SimulationEngine("realstate", WorldConfig(seed=17))
    for _ in range(15):
        engine.step()
    for agent in engine.alive_agents():
        assert agent.action.get("kind")
        assert 0 <= agent.needs["hunger"] <= 100
        assert 0 <= agent.needs["thirst"] <= 100
        assert 0 <= agent.needs["health"] <= 100
        assert agent.position[0] >= 0 and agent.position[1] >= 0
