"""Persistent, score-based agent memory.

Three stores:
  short_term  - recent observations and conversations, bounded
  long_term   - significant experiences, ranked by importance + recency
  social      - per-person history: help, betrayal, trade, conflict

Nothing every tick is stored. Importance gates retention, and summarization
compresses old low-value material. Retrieval is lexical + tag based today; the
interface is intentionally compatible with a later pgvector semantic store.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MAX_SHORT_TERM = 14
MAX_LONG_TERM = 90
MAX_SOCIAL_HISTORY = 6
MAX_TOTAL_MEMORIES = 180


@dataclass
class Memory:
    id: str
    tick: int
    day: int
    kind: str
    summary: str
    importance: float = 0.4
    sentiment: float = 0.0
    participants: list[str] = field(default_factory=list)
    location: list[int] | None = None
    tags: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, full: bool = True) -> dict[str, Any]:
        out = {
            "id": self.id,
            "day": self.day,
            "kind": self.kind,
            "summary": self.summary,
            "importance": round(self.importance, 2),
            "sentiment": round(self.sentiment, 2),
        }
        if full:
            out.update({
                "tick": self.tick,
                "participants": self.participants,
                "location": self.location,
                "tags": self.tags,
                "detail": self.detail,
            })
        return out


class MemoryStore:
    def __init__(self) -> None:
        self.short_term: list[Memory] = []
        self.long_term: list[Memory] = []
        self.social: dict[str, list[dict[str, Any]]] = {}

    def remember(self, memory: Memory) -> None:
        self.short_term.append(memory)
        if len(self.short_term) > MAX_SHORT_TERM:
            overflow = self.short_term.pop(0)
            if overflow.importance >= 0.55:
                self.long_term.append(overflow)
        if memory.importance >= 0.6:
            self.long_term.append(memory)
        # Social memories are keyed by the other person for fast retrieval.
        if memory.kind in ("social", "help", "betrayal", "trade", "conflict", "family"):
            for other in memory.participants:
                bucket = self.social.setdefault(other, [])
                bucket.append({
                    "day": memory.day,
                    "kind": memory.kind,
                    "summary": memory.summary,
                    "sentiment": round(memory.sentiment, 2),
                })
                if len(bucket) > MAX_SOCIAL_HISTORY:
                    bucket.pop(0)
        self._prune()

    def _prune(self) -> None:
        self.long_term.sort(key=lambda m: (m.importance, m.day), reverse=True)
        if len(self.long_term) > MAX_LONG_TERM:
            self.long_term = self.long_term[:MAX_LONG_TERM]
        if len(self.social) > 60:
            keys = list(self.social.keys())
            self.social = {k: self.social[k] for k in keys[-60:]}

    def recall(
        self,
        tags: list[str] | None = None,
        participants: list[str] | None = None,
        limit: int = 5,
        kinds: list[str] | None = None,
    ) -> list[Memory]:
        tags = tags or []
        participants = participants or []
        pool = self.short_term + self.long_term
        scored: list[tuple[float, Memory]] = []
        seen: set[str] = set()
        for memory in pool:
            if memory.id in seen:
                continue
            seen.add(memory.id)
            if kinds and memory.kind not in kinds:
                continue
            score = memory.importance + memory.day * 0.001
            score += 0.35 * len(set(tags) & set(memory.tags))
            score += 0.5 * len(set(participants) & set(memory.participants))
            if memory.kind in ("betrayal", "conflict", "help"):
                score += 0.2
            scored.append((score, memory))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [m for _, m in scored[:limit]]

    def social_history(self, other_id: str) -> list[dict[str, Any]]:
        return self.social.get(other_id, [])

    def to_dict(self) -> dict[str, Any]:
        return {
            "short_term": [m.to_dict() for m in self.short_term],
            "long_term": [m.to_dict() for m in self.long_term],
            "social": self.social,
        }

    def facts(self) -> dict[str, Any]:
        return {
            "short_count": len(self.short_term),
            "long_count": len(self.long_term),
            "social_count": sum(len(v) for v in self.social.values()),
            "total": len(self.short_term) + len(self.long_term),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryStore":
        store = cls()
        for group in ("short_term", "long_term"):
            for raw in data.get(group, []):
                store.short_term.append(Memory(
                    id=raw["id"], tick=raw.get("tick", 0), day=raw.get("day", 0),
                    kind=raw.get("kind", "observation"), summary=raw.get("summary", ""),
                    importance=raw.get("importance", 0.4), sentiment=raw.get("sentiment", 0.0),
                    participants=raw.get("participants", []), location=raw.get("location"),
                    tags=raw.get("tags", []), detail=raw.get("detail", {}),
                )) if group == "short_term" else store.long_term.append(Memory(
                    id=raw["id"], tick=raw.get("tick", 0), day=raw.get("day", 0),
                    kind=raw.get("kind", "observation"), summary=raw.get("summary", ""),
                    importance=raw.get("importance", 0.4), sentiment=raw.get("sentiment", 0.0),
                    participants=raw.get("participants", []), location=raw.get("location"),
                    tags=raw.get("tags", []), detail=raw.get("detail", {}),
                ))
        store.social = data.get("social", {})
        store._prune()
        return store
