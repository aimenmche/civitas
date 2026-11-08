from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from .constants import AMBITIONS, INVENTORY_CAPS, INVENTORY_ITEMS, NEEDS, PERSONALITY_PRESETS, PERSONALITY_TRAITS, SKILLS
from .memory import Memory, MemoryStore
from .names import pick_name


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def need_level(value: float) -> str:
    if value < 20:
        return "critical"
    if value < 40:
        return "low"
    if value < 65:
        return "settled"
    return "good"


@dataclass
class Relationship:
    other_id: str
    type: str = "stranger"
    trust: float = 0.0
    affinity: float = 0.0
    interactions: int = 0
    trades: int = 0
    conflicts: int = 0
    gifts: int = 0
    first_met_day: int = 0
    last_interaction_day: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)

    def update_type(self, partnered: bool = False, is_family: bool = False) -> str:
        if is_family:
            self.type = "family"
        elif partnered:
            self.type = "partner"
        elif self.affinity <= -55 or self.trust <= -60:
            self.type = "enemy"
        elif self.affinity <= -28 or self.trust <= -35:
            self.type = "rival"
        elif self.affinity >= 72 and self.trust >= 50:
            self.type = "close_friend"
        elif self.affinity >= 42 and self.trust >= 15:
            self.type = "friend"
        elif self.interactions >= 2:
            self.type = "acquaintance"
        elif self.trades >= 3 and self.trust >= 0:
            self.type = "business_partner"
        return self.type

    def add_history(self, day: int, summary: str, sentiment: float) -> None:
        self.history.append({"day": day, "summary": summary, "sentiment": round(sentiment, 2)})
        if len(self.history) > 8:
            self.history.pop(0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "other_id": self.other_id,
            "type": self.type,
            "trust": round(self.trust, 1),
            "affinity": round(self.affinity, 1),
            "interactions": self.interactions,
            "trades": self.trades,
            "conflicts": self.conflicts,
            "gifts": self.gifts,
            "first_met_day": self.first_met_day,
            "last_interaction_day": self.last_interaction_day,
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Relationship":
        return cls(
            other_id=data["other_id"], type=data.get("type", "stranger"),
            trust=float(data.get("trust", 0)), affinity=float(data.get("affinity", 0)),
            interactions=int(data.get("interactions", 0)), trades=int(data.get("trades", 0)),
            conflicts=int(data.get("conflicts", 0)), gifts=int(data.get("gifts", 0)),
            first_met_day=int(data.get("first_met_day", 0)),
            last_interaction_day=int(data.get("last_interaction_day", 0)),
            history=data.get("history", []),
        )


@dataclass
class Agent:
    id: str
    name: str
    gender: str
    birth_day: int
    birth_location: list[int]
    generation: int
    origin_group: int
    personality: dict[str, float]
    skills: dict[str, float]
    needs: dict[str, float]
    inventory: dict[str, float]
    position: list[int]
    home_tile: list[int]
    lifespan: int
    ambition: str
    reproductive_role: str
    age_years: float = 18.0
    alive: bool = True
    death_day: int | None = None
    death_cause: str | None = None
    settlement_id: str | None = None
    family_id: str | None = None
    partner_id: str | None = None
    parent_ids: list[str] = field(default_factory=list)
    child_ids: list[str] = field(default_factory=list)
    occupation: str = "Wanderer"
    state: str = "idle"
    current_goal: dict[str, Any] = field(default_factory=dict)
    action: dict[str, Any] = field(default_factory=dict)
    decision: dict[str, Any] = field(default_factory=dict)
    plan: list[dict[str, Any]] = field(default_factory=list)
    relationships: dict[str, Relationship] = field(default_factory=dict)
    memory: MemoryStore = field(default_factory=MemoryStore)
    known_techs: list[str] = field(default_factory=list)
    known_languages: list[str] = field(default_factory=list)
    personal_vocabulary: dict[str, str] = field(default_factory=dict)
    research_progress: dict[str, float] = field(default_factory=dict)
    research_target: str | None = None
    influence: float = 5.0
    reputation: float = 50.0
    pregnant: dict[str, Any] | None = None
    last_birth_day: int | None = None
    founder_of: str | None = None
    path: list[list[int]] = field(default_factory=list)
    last_spoke_day: int = 0
    last_social_action_day: int = 0
    housing_id: str | None = None
    shelter_until: int = 0
    traits_visible: bool = True
    stats: dict[str, Any] = field(default_factory=dict)

    # ----------------------------------------------------------- maintenance
    @property
    def age(self) -> int:
        return int(self.age_years)

    @property
    def is_adult(self) -> bool:
        return self.age_years >= 16

    @property
    def can_bear(self) -> bool:
        return self.alive and self.reproductive_role == "bearer" and 18 <= self.age_years <= 45 and self.pregnant is None

    @property
    def can_sire(self) -> bool:
        return self.alive and self.reproductive_role == "sire" and 18 <= self.age_years <= 65

    def happiness(self) -> float:
        parts = [
            self.needs["hunger"], self.needs["thirst"], self.needs["energy"],
            self.needs["health"], self.needs["safety"], self.needs["social"],
            self.needs["shelter"],
        ]
        return round(sum(parts) / len(parts), 1)

    def wealth(self) -> float:
        return round(
            self.inventory.get("food", 0) * 1.5
            + self.inventory.get("water", 0) * 1.0
            + self.inventory.get("wood", 0) * 1.2
            + self.inventory.get("stone", 0) * 1.3
            + self.inventory.get("tools", 0) * 5.0
            + self.inventory.get("currency", 0),
            1,
        )

    def add_item(self, item: str, amount: float) -> float:
        if item not in self.inventory:
            self.inventory[item] = 0.0
        cap = INVENTORY_CAPS.get(item, 99)
        before = self.inventory[item]
        self.inventory[item] = min(cap, before + amount)
        return self.inventory[item] - before

    def has_items(self, items: dict[str, float]) -> bool:
        return all(self.inventory.get(k, 0) >= v for k, v in items.items())

    def remove_items(self, items: dict[str, float]) -> bool:
        if not self.has_items(items):
            return False
        for k, v in items.items():
            self.inventory[k] = self.inventory.get(k, 0) - v
        return True

    def gain_skill(self, skill: str, amount: float, cap: float = 1.0) -> None:
        if skill not in self.skills:
            return
        current = self.skills[skill]
        # Diminishing returns produce specialists instead of universal experts.
        self.skills[skill] = round(min(cap, current + amount * (1.0 - current) * 0.65), 3)

    def memory_add(self, memory: Memory) -> None:
        self.memory.remember(memory)

    def relation(self, other_id: str, day: int = 0, other_name: str = "") -> Relationship:
        rel = self.relationships.get(other_id)
        if rel is None:
            rel = Relationship(other_id=other_id, first_met_day=day, last_interaction_day=day)
            self.relationships[other_id] = rel
        return rel

    # ------------------------------------------------------- serialization
    def to_summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "x": self.position[0],
            "y": self.position[1],
            "gender": self.gender,
            "age": self.age,
            "generation": self.generation,
            "alive": self.alive,
            "settlement_id": self.settlement_id,
            "occupation": self.occupation,
            "state": self.state,
            "action": {
                "kind": self.action.get("kind"),
                "label": self.action.get("label"),
                "target": self.action.get("target"),
            } if self.action else None,
            "health": round(self.needs.get("health", 0)),
            "happiness": self.happiness(),
            "hunger": round(self.needs.get("hunger", 0)),
            "thirst": round(self.needs.get("thirst", 0)),
            "goal": self.current_goal.get("label") or self.ambition,
            "thought": self.decision.get("thought", ""),
            "family_id": self.family_id,
            "partner_id": self.partner_id,
        }

    def to_detail(self) -> dict[str, Any]:
        data = self.to_summary()
        data.update({
            "birth_day": self.birth_day,
            "birth_location": self.birth_location,
            "death_day": self.death_day,
            "death_cause": self.death_cause,
            "personality": {k: round(v, 2) for k, v in self.personality.items()},
            "skills": {k: round(v, 2) for k, v in self.skills.items()},
            "needs": {k: round(v, 1) for k, v in self.needs.items()},
            "inventory": {k: round(v, 1) for k, v in self.inventory.items() if v > 0},
            "home_tile": self.home_tile,
            "ambition": self.ambition,
            "relationships": [r.to_dict() for r in sorted(self.relationships.values(), key=lambda r: r.affinity, reverse=True)],
            "family_id": self.family_id,
            "parent_ids": self.parent_ids,
            "child_ids": self.child_ids,
            "partner_id": self.partner_id,
            "memories": self.memory.to_dict(),
            "memory_facts": self.memory.facts(),
            "known_techs": self.known_techs,
            "known_languages": self.known_languages,
            "personal_vocabulary": self.personal_vocabulary,
            "research_target": self.research_target,
            "research_progress": {k: round(v, 1) for k, v in self.research_progress.items()},
            "influence": round(self.influence, 1),
            "reputation": round(self.reputation, 1),
            "pregnant": self.pregnant,
            "founder_of": self.founder_of,
            "current_goal": self.current_goal,
            "decision": self.decision,
            "action": self.action,
            "plan": self.plan,
            "lifespan": self.lifespan,
            "reproductive_role": self.reproductive_role,
            "origin_group": self.origin_group,
            "wealth": self.wealth(),
            "stats": self.stats,
        })
        return data

    def to_snapshot(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "gender": self.gender,
            "birth_day": self.birth_day, "birth_location": self.birth_location,
            "generation": self.generation, "origin_group": self.origin_group,
            "personality": self.personality, "skills": self.skills,
            "needs": self.needs, "inventory": self.inventory,
            "position": self.position, "home_tile": self.home_tile,
            "lifespan": self.lifespan, "ambition": self.ambition,
            "reproductive_role": self.reproductive_role, "age_years": self.age_years,
            "alive": self.alive, "death_day": self.death_day, "death_cause": self.death_cause,
            "settlement_id": self.settlement_id, "family_id": self.family_id,
            "partner_id": self.partner_id, "parent_ids": self.parent_ids,
            "child_ids": self.child_ids, "occupation": self.occupation,
            "state": self.state, "current_goal": self.current_goal,
            "action": self.action, "decision": self.decision, "plan": self.plan,
            "relationships": {k: r.to_dict() for k, r in self.relationships.items()},
            "memory": self.memory.to_dict(), "known_techs": self.known_techs,
            "known_languages": self.known_languages,
            "personal_vocabulary": self.personal_vocabulary,
            "research_progress": self.research_progress,
            "research_target": self.research_target, "influence": self.influence,
            "reputation": self.reputation, "pregnant": self.pregnant,
            "last_birth_day": self.last_birth_day, "founder_of": self.founder_of,
            "path": self.path, "last_spoke_day": self.last_spoke_day,
            "last_social_action_day": self.last_social_action_day,
            "housing_id": self.housing_id, "stats": self.stats,
            "shelter_until": self.shelter_until,
        }

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> "Agent":
        agent = cls(
            id=data["id"], name=data["name"], gender=data["gender"],
            birth_day=data["birth_day"], birth_location=data["birth_location"],
            generation=data["generation"], origin_group=data.get("origin_group", 0),
            personality=data["personality"], skills=data["skills"], needs=data["needs"],
            inventory=data["inventory"], position=data["position"], home_tile=data["home_tile"],
            lifespan=data["lifespan"], ambition=data["ambition"],
            reproductive_role=data.get("reproductive_role", "none"),
            age_years=data.get("age_years", 18.0), alive=data.get("alive", True),
            death_day=data.get("death_day"), death_cause=data.get("death_cause"),
            settlement_id=data.get("settlement_id"), family_id=data.get("family_id"),
            partner_id=data.get("partner_id"), parent_ids=data.get("parent_ids", []),
            child_ids=data.get("child_ids", []), occupation=data.get("occupation", "Wanderer"),
            state=data.get("state", "idle"), current_goal=data.get("current_goal", {}),
            action=data.get("action", {}), decision=data.get("decision", {}),
            plan=data.get("plan", []), known_techs=data.get("known_techs", []),
            known_languages=data.get("known_languages", []),
            personal_vocabulary=data.get("personal_vocabulary", {}),
            research_progress=data.get("research_progress", {}),
            research_target=data.get("research_target"),
            influence=data.get("influence", 5.0), reputation=data.get("reputation", 50.0),
            pregnant=data.get("pregnant"), last_birth_day=data.get("last_birth_day"),
            founder_of=data.get("founder_of"), path=data.get("path", []),
            last_spoke_day=data.get("last_spoke_day", 0),
            last_social_action_day=data.get("last_social_action_day", 0),
            housing_id=data.get("housing_id"), stats=data.get("stats", {}),
            shelter_until=data.get("shelter_until", 0),
        )
        agent.relationships = {k: Relationship.from_dict(v) for k, v in data.get("relationships", {}).items()}
        agent.memory = MemoryStore.from_dict(data.get("memory", {}))
        return agent


def make_agent(
    rng: random.Random,
    agent_id: str,
    name: str,
    position: tuple[int, int],
    origin_group: int,
    distribution: str,
    cooperation_bias: float,
    abundance: float,
    generation: int = 0,
    age_years: float | None = None,
    parents: tuple[Agent, Agent] | None = None,
    starting_techs: list[str] | None = None,
    birth_day: int = 1,
    family_id: str | None = None,
) -> Agent:
    if parents:
        base = {
            trait: clamp((parents[0].personality[trait] + parents[1].personality[trait]) / 2 + rng.gauss(0, 0.12), 0.02, 0.98)
            for trait in PERSONALITY_TRAITS
        }
        age_years = 0.0 if age_years is None else age_years
        # Match the founder distribution. This used to be an equal three-way
        # draw, so children were 33% nonbinary while founders were 4% — an
        # inconsistent sex ratio that quietly shrank the pool of bearers.
        gender = rng.choices(["woman", "man", "nonbinary"], weights=[48, 48, 4])[0]
        role = _reproductive_role(gender, rng)
        skills = {skill: clamp((parents[0].skills[skill] + parents[1].skills[skill]) / 4 + rng.random() * 0.08, 0.01, 0.8) for skill in SKILLS}
        lifespan = int(clamp(sum(parent.lifespan for parent in parents) / 2 + rng.randint(-6, 6), 45, 95))
        ambition = rng.choice(AMBITIONS)
        inventory = {item: 0.0 for item in INVENTORY_ITEMS}
        needs = {need: 72.0 + rng.uniform(-5, 5) for need in NEEDS}
        needs["health"] = 92.0
        known_techs = list(dict.fromkeys(parents[0].known_techs + parents[1].known_techs))
        vocab = dict(parents[0].personal_vocabulary)
        vocab.update({k: v for k, v in parents[1].personal_vocabulary.items() if k not in vocab or rng.random() < 0.5})
    else:
        preset = PERSONALITY_PRESETS.get(distribution)
        base = {}
        for trait in PERSONALITY_TRAITS:
            anchor = preset[trait] if preset else 0.5
            value = clamp(anchor + rng.gauss(0, 0.16), 0.02, 0.98)
            if trait == "cooperation":
                value = clamp(value + cooperation_bias, 0.02, 0.99)
            base[trait] = value
        # Give every agent a distinct cognitive and social profile. Two
        # agents can share high ambition but not the whole vector.
        if rng.random() < 0.55:
            specialty = rng.choice(["farming", "gathering", "hunting", "crafting", "construction", "trading", "exploration", "research", "leadership"])
        else:
            specialty = None
        skills = {}
        for skill in SKILLS:
            skills[skill] = clamp(0.08 + rng.random() * 0.18, 0.02, 0.45)
        if specialty:
            skills[specialty] = clamp(0.38 + rng.random() * 0.28, 0.3, 0.8)
        skills["research"] = clamp(skills["research"] + base["curiosity"] * 0.12, 0.02, 0.9)
        skills["leadership"] = clamp(skills["leadership"] + base["ambition"] * 0.12, 0.02, 0.9)
        skills["trading"] = clamp(skills["trading"] + base["cooperation"] * 0.08 + base["honesty"] * 0.05, 0.02, 0.9)
        skills["hunting"] = clamp(skills["hunting"] + base["aggressiveness"] * 0.1, 0.02, 0.9)
        age_years = float(rng.randint(17, 41))
        gender = rng.choice(["woman", "man", "nonbinary"])
        role = _reproductive_role(gender, rng)
        lifespan = rng.randint(58, 88)
        ambition = rng.choice(AMBITIONS)
        inventory = {item: 0.0 for item in INVENTORY_ITEMS}
        wealth_scale = abundance
        inventory["food"] = round(rng.uniform(3.0, 6.0) * min(1.35, wealth_scale), 1)
        inventory["water"] = round(rng.uniform(1.5, 3.5), 1)
        inventory["wood"] = round(rng.uniform(0.5, 2.0), 1)
        inventory["stone"] = round(rng.uniform(0, 1.0), 1)
        if origin_group == 0 and abundance > 1.05:
            inventory["food"] += 2.0
            inventory["wood"] += 1.5
        needs = {
            "hunger": 72.0 + rng.uniform(-8, 8), "thirst": 72.0 + rng.uniform(-8, 8),
            "energy": 78.0 + rng.uniform(-8, 8), "health": 88.0 + rng.uniform(-5, 8),
            "safety": 70.0 + rng.uniform(-10, 9), "social": 58.0 + rng.uniform(-12, 12),
            "shelter": 45.0 + rng.uniform(-10, 15),
        }
        known_techs = list(starting_techs or [])
        vocab = {}
    home_tile = [position[0], position[1]]
    agent = Agent(
        id=agent_id, name=name, gender=gender, birth_day=birth_day,
        birth_location=[position[0], position[1]], generation=generation,
        origin_group=origin_group, personality={k: round(v, 3) for k, v in base.items()},
        skills={k: round(v, 3) for k, v in skills.items()},
        needs={k: round(clamp(v, 0, 100), 1) for k, v in needs.items()},
        inventory={k: round(v, 2) for k, v in inventory.items()},
        position=[position[0], position[1]], home_tile=home_tile,
        lifespan=lifespan, ambition=ambition, reproductive_role=role,
        age_years=round(age_years, 2), family_id=family_id, known_techs=known_techs,
        personal_vocabulary=vocab,
    )
    agent.current_goal = {"kind": "ambition", "label": ambition, "progress": 0.0}
    if parents:
        agent.parent_ids = [parents[0].id, parents[1].id]
        agent.personal_vocabulary = vocab
        agent.memory_add(Memory(
            id=f"m_{agent_id}_birth", tick=0, day=birth_day, kind="family",
            summary=f"Born to {parents[0].name} and {parents[1].name}.",
            importance=0.9, sentiment=0.9, participants=[parents[0].id, parents[1].id],
            tags=["family", "birth"],
        ))
    return agent


def _reproductive_role(gender: str, rng: random.Random) -> str:
    if gender == "woman":
        return "bearer" if rng.random() < 0.92 else "none"
    if gender == "man":
        return "sire" if rng.random() < 0.92 else "none"
    return rng.choices(["bearer", "sire", "none"], weights=[0.3, 0.3, 0.4])[0]


def choose_occupation(agent: Agent) -> str:
    skill_map = [
        ("Farmer", "farming"), ("Builder", "construction"), ("Hunter", "hunting"),
        ("Gatherer", "gathering"), ("Trader", "trading"), ("Craftsperson", "crafting"),
        ("Explorer", "exploration"), ("Scholar", "research"), ("Leader", "leadership"),
    ]
    best = max(skill_map, key=lambda pair: agent.skills.get(pair[1], 0))
    if agent.skills.get(best[1], 0) < 0.2:
        return "Wanderer"
    return best[0]
