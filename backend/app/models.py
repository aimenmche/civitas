from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    world_name: Mapped[str] = mapped_column(String(64), default="Aureth")
    preset: Mapped[str] = mapped_column(String(40), default="fertile_valley")
    seed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="running", index=True)
    speed: Mapped[float] = mapped_column(Float, default=1.0)
    day: Mapped[int] = mapped_column(Integer, default=1)
    note: Mapped[str] = mapped_column(Text, default="")
    parent_run_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    branch_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    state_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    events: Mapped[list["RunEvent"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    metrics: Mapped[list["RunMetric"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    snapshots: Mapped[list["Snapshot"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class RunEvent(Base):
    __tablename__ = "run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "event_id", name="uq_run_event"),
        Index("ix_run_events_run_day", "run_id", "day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[str] = mapped_column(String(30))
    day: Mapped[int] = mapped_column(Integer)
    year: Mapped[int] = mapped_column(Integer, default=1)
    season: Mapped[str] = mapped_column(String(20), default="Spring")
    category: Mapped[str] = mapped_column(String(40), index=True)
    importance: Mapped[int] = mapped_column(Integer, default=2)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    location_json: Mapped[str] = mapped_column(Text, default="null")
    location_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    participants_json: Mapped[str] = mapped_column(Text, default="[]")
    consequences_json: Mapped[str] = mapped_column(Text, default="[]")
    related_json: Mapped[str] = mapped_column(Text, default="{}")
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[Run] = relationship(back_populates="events")


class RunMetric(Base):
    __tablename__ = "run_metrics"
    __table_args__ = (UniqueConstraint("run_id", "day", name="uq_run_metric"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    day: Mapped[int] = mapped_column(Integer)
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")

    run: Mapped[Run] = relationship(back_populates="metrics")


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    day: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(160), default="")
    state_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[Run] = relationship(back_populates="snapshots")
