from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .sim.world import WorldConfig


class RunCreateRequest(BaseModel):
    world: WorldConfig = Field(default_factory=WorldConfig)
    note: str = Field(default="", max_length=500)


class ControlRequest(BaseModel):
    action: Literal["pause", "resume", "step", "speed"]
    speed: float | None = Field(default=None, ge=0.1, le=32.0)


class SnapshotRequest(BaseModel):
    label: str = Field(default="", max_length=160)


class BranchRequest(BaseModel):
    snapshot_id: str | None = None
    note: str = Field(default="", max_length=500)
    world_name: str | None = Field(default=None, max_length=64)


class CompareRequest(BaseModel):
    run_ids: list[str] = Field(min_length=2, max_length=6)


class ChronicleRequest(BaseModel):
    kind: Literal["summary", "dramatic", "neutral"] = "summary"
    days: int = Field(default=50, ge=5, le=500)


class RunSummary(BaseModel):
    id: str
    world_name: str
    preset: str
    seed: int
    status: str
    speed: float
    day: int
    population: int
    settlements: int
    note: str
    parent_run_id: str | None = None
    branch_day: int | None = None
    created_at: str | None = None
    updated_at: str | None = None
