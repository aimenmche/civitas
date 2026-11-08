from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from .constants import LANGUAGE_CONCEPTS
from .names import coin_word, culture_name, language_name


@dataclass
class Language:
    id: str
    name: str
    settlement_id: str
    lexicon: dict[str, str] = field(default_factory=dict)
    origins: list[str] = field(default_factory=list)
    loans: list[dict[str, Any]] = field(default_factory=list)
    speakers: int = 0
    created_day: int = 1

    def speak(self, concepts: list[str]) -> str:
        words = [self.lexicon.get(c) for c in concepts if self.lexicon.get(c)]
        return " ".join(words) if words else ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "settlement_id": self.settlement_id,
            "lexicon": self.lexicon, "origins": self.origins, "loans": self.loans[-12:],
            "speakers": self.speakers, "created_day": self.created_day,
            "word_count": len(self.lexicon),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Language":
        language = cls(
            id=data["id"], name=data["name"], settlement_id=data.get("settlement_id", ""),
            lexicon=data.get("lexicon", {}), origins=data.get("origins", []),
            loans=data.get("loans", []), speakers=data.get("speakers", 0),
            created_day=data.get("created_day", 1),
        )
        return language


@dataclass
class Culture:
    id: str
    name: str
    settlement_id: str
    values: dict[str, float] = field(default_factory=dict)
    customs: list[dict[str, Any]] = field(default_factory=list)
    traditions: list[dict[str, Any]] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)
    art_forms: list[str] = field(default_factory=list)
    taboos: list[str] = field(default_factory=list)
    founded_day: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "settlement_id": self.settlement_id,
            "values": {k: round(v, 2) for k, v in self.values.items()},
            "customs": self.customs[-16:], "traditions": self.traditions[-16:],
            "symbols": self.symbols, "art_forms": self.art_forms,
            "taboos": self.taboos, "founded_day": self.founded_day,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Culture":
        return cls(
            id=data["id"], name=data["name"], settlement_id=data.get("settlement_id", ""),
            values=data.get("values", {}), customs=data.get("customs", []),
            traditions=data.get("traditions", []), symbols=data.get("symbols", []),
            art_forms=data.get("art_forms", []), taboos=data.get("taboos", []),
            founded_day=data.get("founded_day", 1),
        )


def create_language(seed_int: int, settlement_id: str, day: int, origin: str = "", used_words: set[str] | None = None) -> Language:
    rng = random.Random(seed_int)
    used_words = used_words or set()
    lexicon: dict[str, str] = {}
    for concept in LANGUAGE_CONCEPTS:
        if rng.random() < 0.12 and origin:
            continue
        lexicon[concept] = coin_word(rng, used_words)
    language_id = f"lang_{seed_int % 1000000:06d}"
    return Language(
        id=language_id,
        name=language_name(rng, set()),
        settlement_id=settlement_id,
        lexicon=lexicon,
        origins=[origin] if origin else [],
        speakers=1,
        created_day=day,
    )


def create_culture(seed_int: int, settlement_id: str, founder_values: dict[str, float], day: int) -> Culture:
    rng = random.Random(seed_int)
    values = {
        "cooperation": founder_values.get("cooperation", 0.5),
        "tradition": 0.55 + rng.uniform(-0.1, 0.12),
        "hierarchy": founder_values.get("ambition", 0.5) * 0.6,
        "innovation": founder_values.get("curiosity", 0.5),
        "hospitality": founder_values.get("empathy", 0.5),
        "martial": founder_values.get("aggressiveness", 0.5) * 0.7,
    }
    symbols = rng.sample(
        ["the first hearth", "the river stone", "the tall pine", "the morning star", "the red earth", "the white bird", "the old well", "the mountain shadow"],
        k=2,
    )
    return Culture(
        id=f"cult_{seed_int % 1000000:06d}",
        name=culture_name(rng, set()),
        settlement_id=settlement_id,
        values={k: round(v, 2) for k, v in values.items()},
        symbols=symbols,
        founded_day=day,
    )


def add_tradition(
    culture: Culture,
    day: int,
    name: str,
    description: str,
    category: str,
    origin: str,
) -> dict[str, Any] | None:
    if any(t["name"] == name for t in culture.traditions):
        return None
    tradition = {
        "name": name, "description": description, "category": category,
        "origin": origin, "since_day": day,
    }
    culture.traditions.append(tradition)
    if len(culture.traditions) > 20:
        culture.traditions.pop(0)
    return tradition


def borrow_words(
    source: Language,
    target: Language,
    rng: random.Random,
    day: int,
    amount: int = 1,
) -> list[dict[str, Any]]:
    """Language contact: words move between speech communities through use."""
    candidates = [c for c, w in source.lexicon.items() if target.lexicon.get(c) != w]
    if not candidates:
        return []
    rng.shuffle(candidates)
    borrowed = []
    for concept in candidates[:amount]:
        word = source.lexicon[concept]
        old = target.lexicon.get(concept)
        target.lexicon[concept] = word
        record = {
            "concept": concept, "word": word, "from": source.name,
            "from_language": source.id, "day": day, "replaced": old,
        }
        target.loans.append(record)
        if len(target.loans) > 40:
            target.loans.pop(0)
        borrowed.append(record)
    return borrowed


def drift_language(language: Language, rng: random.Random, day: int, rate: float = 0.06) -> list[dict[str, Any]]:
    """Sound change over generations. Not every word shifts every generation."""
    changes = []
    used = set(language.lexicon.values())
    for concept, word in list(language.lexicon.items()):
        if rng.random() < rate:
            old = word
            if len(word) > 2 and rng.random() < 0.5:
                idx = rng.randrange(1, len(word) - 1)
                consonant = rng.choice("strnlk")
                new_word = word[:idx] + consonant + word[idx + 1:]
            else:
                new_word = coin_word(rng, used)
            if new_word and new_word != old:
                language.lexicon[concept] = new_word
                used.add(new_word)
                changes.append({"concept": concept, "old": old, "new": new_word, "day": day})
    return changes
