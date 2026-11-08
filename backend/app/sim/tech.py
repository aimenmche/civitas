from __future__ import annotations

from typing import Any

from .constants import TECHS, ERA_ORDER


def tech_status(tech_key: str, known: set[str]) -> str:
    if tech_key in known:
        return "discovered"
    prereqs = TECHS[tech_key]["prereq"]
    if all(p in known for p in prereqs):
        return "available"
    return "locked"


def available_techs(known: set[str]) -> list[str]:
    return [k for k in TECHS if k not in known and all(p in known for p in TECHS[k]["prereq"])]


def tech_tree_view(known: set[str], progress: dict[str, float] | None = None) -> list[dict[str, Any]]:
    progress = progress or {}
    output = []
    for key, spec in TECHS.items():
        status = tech_status(key, known)
        output.append({
            "key": key,
            "name": spec["name"],
            "era": spec["era"],
            "cost": spec["cost"],
            "prereq": spec["prereq"],
            "effect": spec["effect"],
            "status": status,
            "progress": round(progress.get(key, 0.0), 1),
            "conditions": spec.get("conditions", {}),
        })
    era_rank = {era: i for i, era in enumerate(ERA_ORDER)}
    output.sort(key=lambda t: (era_rank.get(t["era"], 9), t["cost"]))
    return output


def current_era(known: set[str]) -> str:
    best = "Survival"
    for key in known:
        era = TECHS.get(key, {}).get("era", "Survival")
        if ERA_ORDER.index(era) > ERA_ORDER.index(best):
            best = era
    return best


def effects_for(known: set[str]) -> dict[str, Any]:
    """Aggregate real effects from the knowledge a community actually holds."""
    combined: dict[str, Any] = {
        "gather_food": 0.0, "gather_wood": 0.0, "build_speed": 0.0,
        "food_keep": 0.0, "farm_yield": 0.0, "research": 0.0, "trade": 0.0,
        "health_recovery": 0.0, "birth_survival": 0.0, "tool_yield": 0.0,
        "build_unlock": [], "currency": False, "governance": 0.0,
        "happiness": 0.0, "memory": 0.0, "drought_resist": 0.0,
        "winter_food": 0.0, "water": 0.0, "warmth": 0.0,
    }
    for key in known:
        spec = TECHS.get(key)
        if not spec:
            continue
        for effect, value in spec.get("effects", {}).items():
            if isinstance(value, bool):
                combined[effect] = combined.get(effect, False) or value
            elif isinstance(value, (int, float)):
                combined[effect] = round(float(combined.get(effect, 0.0)) + float(value), 3)
            elif isinstance(value, list):
                bucket = combined.setdefault(effect, [])
                for item in value:
                    if item not in bucket:
                        bucket.append(item)
            else:
                combined[effect] = value
    return combined


def discovery_conditions_met(
    tech_key: str,
    population: int,
    settlement_count: int,
    total_fertility: float,
    storage: dict[str, float],
    has_market: bool,
) -> tuple[bool, list[str]]:
    conditions = TECHS[tech_key].get("conditions", {})
    missing: list[str] = []
    if population < int(conditions.get("population", 0)):
        missing.append(f"population {int(conditions.get('population', 0))}")
    if settlement_count < int(conditions.get("settlements", 0)):
        missing.append(f"{int(conditions.get('settlements', 0))} settlement(s)")
    if "fertility" in conditions and total_fertility < float(conditions["fertility"]):
        missing.append("fertile land")
    if "stone" in conditions and storage.get("stone", 0) < float(conditions["stone"]):
        missing.append(f"{int(conditions['stone'])} stone")
    if "herbs" in conditions and storage.get("herbs", 0) < float(conditions["herbs"]):
        missing.append(f"{int(conditions['herbs'])} herbs")
    if "ore" in conditions and storage.get("ore", 0) < float(conditions["ore"]):
        missing.append(f"{int(conditions['ore'])} ore")
    if "water" in conditions and total_fertility < float(conditions["water"]):
        missing.append("water access")
    if conditions.get("market") and not has_market:
        missing.append("a market")
    return len(missing) == 0, missing
