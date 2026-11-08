from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from .constants import BUILDINGS, GOVERNMENTS, LAW_TEMPLATES

# Food and herbs share the granary, water has its own cistern reserve, and
# building materials share the yard.
PERISHABLE_GOODS = ("food", "herbs")
WATER_GOODS = ("water",)
MATERIAL_GOODS = ("wood", "stone", "ore", "tools")


@dataclass
class Settlement:
    id: str
    name: str
    position: list[int]
    founded_day: int
    founder_id: str
    leader_id: str | None
    member_ids: list[str]
    storage: dict[str, float]
    culture_id: str
    language_id: str
    known_techs: list[str] = field(default_factory=list)
    capital_tile: list[int] | None = None
    occupation: dict[str, str] = field(default_factory=dict)
    buildings: list[dict[str, Any]] = field(default_factory=list)
    build_queue: list[dict[str, Any]] = field(default_factory=list)
    government: dict[str, Any] = field(default_factory=dict)
    laws: list[dict[str, Any]] = field(default_factory=list)
    factions: list[dict[str, Any]] = field(default_factory=list)
    diplomacy: dict[str, dict[str, Any]] = field(default_factory=dict)
    territory_radius: int = 2
    uses_currency: bool = False
    economic_stage: int = 1
    market_prices: dict[str, float] = field(default_factory=dict)
    trade_volume: float = 0.0
    tax_revenue: float = 0.0
    safety: float = 60.0
    stability: float = 60.0
    happiness: float = 60.0
    food_production: float = 0.0
    food_consumption: float = 0.0
    population_peak: int = 1
    history: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    abandoned_day: int | None = None
    ruins: bool = False

    @property
    def population(self) -> int:
        return len(self.member_ids)

    def housing_capacity(self) -> int:
        return 2 + sum(int(b.get("housing", 0)) for b in self.buildings)

    def storage_capacity(self) -> float:
        return 70.0 + sum(float(b.get("storage", 0)) for b in self.buildings)

    def material_capacity(self) -> float:
        """Timber, stone and ore are stacked in yards, not in the grain store.

        They used to share one pool with food, and once a granary was full the
        overflow clamp deleted wood and stone first. Settlements then starved
        with 176 food in store, zero timber, and no way to build another house
        or farm.
        """
        return max(60.0, self.storage_capacity() * 0.8)

    def stored_perishables(self) -> float:
        return sum(float(self.storage.get(k, 0.0)) for k in PERISHABLE_GOODS)

    def water_capacity(self) -> float:
        """A few days of drinking water, not a second granary.

        Well output used to fill the shared pool until it displaced the
        harvest. Water is now held in its own small cistern reserve.
        """
        return max(12.0, self.population * 0.8)

    def stored_materials(self) -> float:
        return sum(float(self.storage.get(k, 0.0)) for k in MATERIAL_GOODS)

    def room_for(self, item: str) -> float:
        if item in MATERIAL_GOODS:
            return max(0.0, self.material_capacity() - self.stored_materials())
        if item in WATER_GOODS:
            return max(0.0, self.water_capacity() - sum(float(self.storage.get(k, 0.0)) for k in WATER_GOODS))
        # Currency is not physical cargo and never consumes storage.
        if item == "currency":
            return float("inf")
        return max(0.0, self.storage_capacity() - self.stored_perishables())

    def has_room_for(self, item: str, amount: float = 1.0) -> bool:
        return self.room_for(item) >= amount

    def has_building(self, building_type: str) -> bool:
        if building_type in ("shelter", "house"):
            return any(b["type"] in ("shelter", "house", "stone_house") for b in self.buildings)
        return any(b["type"] == building_type for b in self.buildings)

    def building_count(self, building_type: str) -> int:
        return sum(1 for b in self.buildings if b["type"] == building_type)

    def add_building(self, building_type: str, day: int) -> dict[str, Any] | None:
        spec = BUILDINGS.get(building_type)
        if spec is None:
            return None
        building = {
            "id": f"{self.id}_b{len(self.buildings) + 1}",
            "type": building_type,
            "name": spec["name"],
            "level": 1,
            "built_day": day,
            "condition": 100.0,
        }
        for key in ("housing", "storage", "jobs", "research", "culture", "water", "effect"):
            if key in spec:
                building[key] = spec[key]
        self.buildings.append(building)
        return building

    def leader(self, agents_by_id: dict[str, Any]) -> Any | None:
        return agents_by_id.get(self.leader_id) if self.leader_id else None

    def gov_label(self) -> str:
        system = self.government.get("system", "tribal")
        return GOVERNMENTS.get(system, {}).get("label", system.title())

    def treasury(self) -> float:
        return float(self.storage.get("currency", 0.0))

    def to_summary(self, agents_by_id: dict[str, Any] | None = None) -> dict[str, Any]:
        leader = agents_by_id.get(self.leader_id) if agents_by_id and self.leader_id else None
        return {
            "id": self.id, "name": self.name, "x": self.position[0], "y": self.position[1],
            "population": self.population, "founded_day": self.founded_day,
            "founder_id": self.founder_id, "leader_id": self.leader_id,
            "leader_name": leader.name if leader else None,
            "territory_radius": self.territory_radius,
            "government": self.government.get("system", "tribal"),
            "government_label": self.gov_label(),
            "economic_stage": self.economic_stage,
            "uses_currency": self.uses_currency,
            "culture_id": self.culture_id, "language_id": self.language_id,
            "buildings": len(self.buildings),
            "housing_capacity": self.housing_capacity(),
            "food": round(float(self.storage.get("food", 0)), 1),
            "water": round(float(self.storage.get("water", 0)), 1),
            "wealth": round(sum(float(self.storage.get(k, 0)) for k in ("food", "water", "wood", "stone", "tools", "currency")), 1),
            "safety": round(self.safety), "stability": round(self.stability),
            "happiness": round(self.happiness), "food_production": round(self.food_production, 1),
            "abandoned_day": self.abandoned_day, "ruins": self.ruins,
            "population_peak": self.population_peak,
        }

    def to_detail(self, agents_by_id: dict[str, Any], cultures: dict[str, Any], languages: dict[str, Any]) -> dict[str, Any]:
        data = self.to_summary(agents_by_id)
        data.update({
            "storage": {k: round(v, 1) for k, v in self.storage.items() if v > 0},
            "storage_capacity": self.storage_capacity(),
            "buildings_detail": self.buildings,
            "build_queue": self.build_queue,
            "government": self.government,
            "laws": self.laws,
            "factions": self.factions,
            "diplomacy": self.diplomacy,
            "known_techs": self.known_techs,
            "market_prices": self.market_prices,
            "trade_volume": round(self.trade_volume, 1),
            "tax_revenue": round(self.tax_revenue, 1),
            "culture": cultures.get(self.culture_id).to_dict() if self.culture_id in cultures else None,
            "language": languages.get(self.language_id).to_dict() if self.language_id in languages else None,
            "history": self.history[-25:],
            "stats": self.stats,
            "members": [
                {
                    "id": aid, "name": agents_by_id[aid].name,
                    "age": agents_by_id[aid].age,
                    "occupation": self.occupation.get(aid, agents_by_id[aid].occupation),
                    "role": "leader" if aid == self.leader_id else "citizen",
                }
                for aid in self.member_ids if aid in agents_by_id
            ],
        })
        return data

    def to_snapshot(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "position": self.position,
            "founded_day": self.founded_day, "founder_id": self.founder_id,
            "leader_id": self.leader_id, "member_ids": self.member_ids,
            "storage": self.storage, "culture_id": self.culture_id,
            "language_id": self.language_id, "known_techs": self.known_techs,
            "capital_tile": self.capital_tile,
            "occupation": self.occupation, "buildings": self.buildings,
            "build_queue": self.build_queue, "government": self.government,
            "laws": self.laws, "factions": self.factions, "diplomacy": self.diplomacy,
            "territory_radius": self.territory_radius, "uses_currency": self.uses_currency,
            "economic_stage": self.economic_stage, "market_prices": self.market_prices,
            "trade_volume": self.trade_volume, "tax_revenue": self.tax_revenue,
            "safety": self.safety, "stability": self.stability, "happiness": self.happiness,
            "food_production": self.food_production, "food_consumption": self.food_consumption,
            "population_peak": self.population_peak, "history": self.history,
            "stats": self.stats, "abandoned_day": self.abandoned_day, "ruins": self.ruins,
        }

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> "Settlement":
        return cls(
            id=data["id"], name=data["name"], position=data["position"],
            founded_day=data["founded_day"], founder_id=data["founder_id"],
            leader_id=data.get("leader_id"), member_ids=data.get("member_ids", []),
            storage=data.get("storage", {}), culture_id=data.get("culture_id", ""),
            language_id=data.get("language_id", ""), known_techs=data.get("known_techs", []),
            capital_tile=data.get("capital_tile"),
            occupation=data.get("occupation", {}), buildings=data.get("buildings", []),
            build_queue=data.get("build_queue", []), government=data.get("government", {}),
            laws=data.get("laws", []), factions=data.get("factions", []),
            diplomacy=data.get("diplomacy", {}), territory_radius=data.get("territory_radius", 2),
            uses_currency=data.get("uses_currency", False),
            economic_stage=data.get("economic_stage", 1),
            market_prices=data.get("market_prices", {}),
            trade_volume=data.get("trade_volume", 0.0),
            tax_revenue=data.get("tax_revenue", 0.0), safety=data.get("safety", 60.0),
            stability=data.get("stability", 60.0), happiness=data.get("happiness", 60.0),
            food_production=data.get("food_production", 0.0),
            food_consumption=data.get("food_consumption", 0.0),
            population_peak=data.get("population_peak", 1),
            history=data.get("history", []), stats=data.get("stats", {}),
            abandoned_day=data.get("abandoned_day"), ruins=data.get("ruins", False),
        )


def blank_government(leader_id: str, day: int) -> dict[str, Any]:
    return {
        "system": "tribal",
        "label": GOVERNMENTS["tribal"]["label"],
        "leader_id": leader_id,
        "legitimacy": 55.0,
        "tax_rate": 0.0,
        "since_day": day,
        "members": [leader_id],
        "elections": 0,
    }


def plan_building(settlement: Settlement, techs: set[str], rng: random.Random, day: int) -> str | None:
    """Choose a needed structure from real deficits, not a scripted build order."""
    has = {b["type"] for b in settlement.buildings}
    queued = {b["type"] for b in settlement.build_queue}
    pop = settlement.population
    occupied = has | queued

    def unlocked(key: str) -> bool:
        req = BUILDINGS[key].get("requires_tech")
        return req is None or req in techs

    candidates: list[tuple[float, str]] = []
    if "house" not in occupied and "stone_house" not in occupied and pop > settlement.housing_capacity() - 1:
        candidates.append((9.0, "house"))
    if settlement.housing_capacity() < pop + 2 and pop >= 4:
        candidates.append((4.0, "house"))
    if "storage" not in occupied and pop >= 4 and settlement.storage_capacity() < pop * 3 + 20:
        candidates.append((5.0, "storage"))
    if "farm" not in occupied and "agriculture" in techs and pop >= 5:
        candidates.append((7.0, "farm"))
    if "well" not in occupied and "masonry" in techs and pop >= 6:
        candidates.append((6.0, "well"))
    if "market" not in occupied and "trade" in techs and pop >= 7:
        candidates.append((6.0, "market"))
    if "granary" not in occupied and "pottery" in techs and pop >= 7:
        candidates.append((5.0, "granary"))
    if "workshop" not in occupied and "construction" in techs and pop >= 8:
        candidates.append((4.0, "workshop"))
    if "palisade" not in occupied and "masonry" in techs and (settlement.safety < 55 or pop >= 10):
        candidates.append((5.0, "palisade"))
    if "shrine" not in occupied and pop >= 6:
        candidates.append((3.0, "shrine"))
    if "school" not in occupied and "writing" in techs and pop >= 12:
        candidates.append((3.5, "school"))
    if "town_hall" not in occupied and "construction" in techs and pop >= 10:
        candidates.append((4.0, "town_hall"))
    if "archive" not in occupied and "writing" in techs and pop >= 12:
        candidates.append((3.0, "archive"))
    if "agora" not in occupied and "philosophy" in techs and pop >= 14:
        candidates.append((2.5, "agora"))
    if "aqueduct" not in occupied and "engineering" in techs and pop >= 16:
        candidates.append((2.5, "aqueduct"))
    # Farms beyond the first once population is growing.
    if "farm" in has and pop >= 8 + settlement.building_count("farm") * 6:
        candidates.append((4.5, "farm"))
    if "house" in has and settlement.housing_capacity() < pop + 2:
        candidates.append((4.0, "house"))
    candidates = [(score, key) for score, key in candidates if unlocked(key)]
    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0] + rng.random() * 0.2, reverse=True)
    # Affordability is a real constraint; do not queue impossible projects.
    for _, key in candidates:
        if all(settlement.storage.get(item, 0) >= amount * 0.75 for item, amount in BUILDINGS[key]["cost"].items()):
            return key
    return None


def enact_law(settlement: Settlement, law_key: str, day: int, support: float) -> dict[str, Any] | None:
    if any(law["key"] == law_key for law in settlement.laws):
        return None
    template = LAW_TEMPLATES[law_key]
    law = {
        "id": f"{settlement.id}_law{len(settlement.laws) + 1}",
        "key": law_key,
        "title": template["title"],
        "description": template["description"],
        "effects": template["effects"],
        "enacted_day": day,
        "support": round(support, 1),
    }
    settlement.laws.append(law)
    return law
