"""Emergent governance, factions, laws and diplomacy.

No political system is installed at world creation. The initial "tribal"
arrangement is simply the founder's personal authority. Systems change when
the settlement's culture, size, technology and internal balance change.
"""
from __future__ import annotations

import random
from typing import Any

from .constants import GOVERNMENTS
from .settlement import Settlement, enact_law


def leader_score(agent: Any, settlement: Settlement) -> float:
    if not agent.alive:
        return -999
    leadership = agent.skills.get("leadership", 0) * 38
    influence = min(25, agent.influence * 0.7)
    reputation = (agent.reputation - 50) * 0.28
    relationships = sum(1 for r in agent.relationships.values() if r.affinity > 20) * 1.2
    age_bonus = min(8, max(0, agent.age - 18) * 0.25)
    legitimacy_bonus = 6 if settlement.leader_id == agent.id else 0
    ambition = agent.personality.get("ambition", 0.5) * 6
    return leadership + influence + reputation + relationships + age_bonus + legitimacy_bonus + ambition


def choose_leader(settlement: Settlement, agents: dict[str, Any], rng: random.Random, day: int, mode: str = "tribal") -> tuple[str | None, dict[str, Any]]:
    members = [agents[aid] for aid in settlement.member_ids if aid in agents and agents[aid].alive]
    if not members:
        return None, {"reason": "no members"}
    scored = sorted(((leader_score(a, settlement), a) for a in members), key=lambda pair: pair[0], reverse=True)
    if mode in ("council", "republic", "democracy"):
        # Collective systems still favor capable people, but wider support matters.
        top = scored[: max(2, min(5, len(scored)))]
        winner = max(top, key=lambda pair: pair[0] + rng.uniform(0, 8))[1]
    elif mode in ("monarchy",):
        leader = agents.get(settlement.leader_id or "")
        heirs = [a for a in members if leader and leader.id in a.parent_ids]
        winner = max(heirs, key=lambda a: leader_score(a, settlement)) if heirs else scored[0][1]
    elif mode in ("oligarchy", "authoritarian"):
        wealthy = sorted(members, key=lambda a: a.wealth() + a.influence * 0.4, reverse=True)
        winner = wealthy[0]
    else:
        winner = scored[0][1]
    return winner.id, {
        "runner_up": scored[1][1].id if len(scored) > 1 else None,
        "score": round(leader_score(winner, settlement), 1),
        "candidates": len(scored),
    }


def evaluate_governance(
    settlement: Settlement,
    agents: dict[str, Any],
    culture: Any,
    known_techs: set[str],
    day: int,
    rng: random.Random,
    no_leader: bool = False,
) -> dict[str, Any] | None:
    """Return a governance-change record if conditions justify one."""
    if settlement.population < 4:
        return None
    old_system = settlement.government.get("system", "tribal")
    if no_leader:
        if old_system != "assembly":
            settlement.government.update({
                "system": "assembly",
                "label": "Leaderless Assembly",
                "leader_id": None,
                "legitimacy": 52.0,
                "tax_rate": 0.02,
                "since_day": day,
                "members": settlement.member_ids[:12],
            })
            settlement.leader_id = None
            return {"from": old_system, "to": "assembly", "reason": "the experiment forbids central leaders"}
        return None

    values = culture.values if culture else {}
    cooperation = values.get("cooperation", 0.5)
    hierarchy = values.get("hierarchy", 0.5)
    innovation = values.get("innovation", 0.5)
    martial = values.get("martial", 0.5)
    writing = "writing" in known_techs
    philosophy = "philosophy" in known_techs
    construction = "construction" in known_techs
    legitimacy = float(settlement.government.get("legitimacy", 55))
    happiness = settlement.happiness

    target = old_system
    reason = ""
    # These are pressures, not a menu. Each branch requires different facts.
    if legitimacy < 28 and happiness < 45 and settlement.population >= 8:
        if cooperation > 0.55 and writing:
            target = "democracy"
            reason = "crisis of legitimacy; popular assembly demanded"
        elif martial > 0.58 or hierarchy > 0.62:
            target = "authoritarian"
            reason = "fear and factional conflict concentrate power"
        else:
            target = "council"
            reason = "leader lost confidence; elders assume authority"
    elif settlement.population >= 18 and philosophy and cooperation > 0.58 and old_system in ("tribal", "monarchy", "oligarchy"):
        target = "republic"
        reason = "a propertied citizenry demands representation"
    elif settlement.population >= 14 and writing and old_system == "tribal" and cooperation > 0.5:
        target = "council"
        reason = "records and deliberation replace personal rule"
    elif settlement.population >= 20 and writing and construction and hierarchy > 0.62 and old_system not in ("monarchy", "authoritarian"):
        target = "monarchy"
        reason = "a powerful lineage consolidates hereditary rule"
    elif settlement.population >= 16 and innovation > 0.62 and old_system in ("tribal", "council") and "philosophy" in known_techs:
        target = "democracy"
        reason = "civic philosophy inspires broader participation"
    elif settlement.population >= 12 and hierarchy > 0.66 and martial > 0.55 and old_system == "tribal":
        target = "oligarchy"
        reason = "wealthy and martial households seize the council"

    if target == old_system:
        return None
    leader_id, selection = choose_leader(settlement, agents, rng, day, mode=target)
    previous = settlement.leader_id
    settlement.government = {
        "system": target,
        "label": GOVERNMENTS.get(target, {}).get("label", target.title()),
        "leader_id": leader_id,
        "legitimacy": float(GOVERNMENTS.get(target, {}).get("legitimacy", 55)),
        "tax_rate": float(GOVERNMENTS.get(target, {}).get("tax", 0.05)),
        "since_day": day,
        "members": _council_members(settlement, agents, rng, target),
        "elections": settlement.government.get("elections", 0) + (1 if target in ("republic", "democracy") else 0),
        "selection": selection,
    }
    settlement.leader_id = leader_id
    return {
        "from": old_system, "to": target, "reason": reason,
        "previous_leader": previous, "leader_id": leader_id, "selection": selection,
    }


def refresh_government_legitimacy(settlement: Settlement) -> None:
    gov = settlement.government
    if not gov:
        return
    base = float(GOVERNMENTS.get(gov.get("system", "tribal"), {}).get("legitimacy", 55))
    effects = sum(law.get("effects", {}).get("legitimacy", 0) for law in settlement.laws)
    loss = max(0.0, 55 - settlement.happiness) * 0.16
    shortage = 6 if settlement.storage.get("food", 0) < settlement.population * 0.7 else 0
    gov["legitimacy"] = round(max(5.0, min(99.0, base + effects + settlement.stability * 0.18 - loss - shortage)), 1)


def _council_members(settlement: Settlement, agents: dict[str, Any], rng: random.Random, system: str) -> list[str]:
    members = [agents[aid] for aid in settlement.member_ids if aid in agents and agents[aid].alive]
    if not members:
        return []
    if system in ("democracy", "republic", "council"):
        ranked = sorted(members, key=lambda a: leader_score(a, settlement), reverse=True)
        return [a.id for a in ranked[: min(7, max(3, len(members) // 4))]]
    return [settlement.leader_id] if settlement.leader_id else []


def update_factions(settlement: Settlement, agents: dict[str, Any], culture: Any, rng: random.Random) -> None:
    """Factions form around real value cleavages, not arbitrary teams."""
    if settlement.population < 7:
        settlement.factions = []
        return
    definitions = [
        ("hearth", "Hearthkeepers", "tradition", "Preserve custom, kin and the old ways."),
        ("common", "Commonweal", "cooperation", "Share surplus, govern together."),
        ("path", "Pathfinders", "innovation", "Expand, experiment and build."),
        ("iron", "Iron Circle", "hierarchy", "Order through strong leadership."),
        ("ledger", "Free Traders", "commerce", "Open exchange and private gain."),
    ]
    buckets: dict[str, list[str]] = {key: [] for key, _, _, _ in definitions}
    for aid in settlement.member_ids:
        agent = agents.get(aid)
        if not agent or not agent.alive:
            continue
        scores = {
            "hearth": agent.personality.get("honesty", 0.5) * 0.6 + (culture.values.get("tradition", 0.5) if culture else 0.5) * 0.8,
            "common": agent.personality.get("cooperation", 0.5) * 0.9 + agent.personality.get("empathy", 0.5) * 0.5,
            "path": agent.personality.get("curiosity", 0.5) * 0.7 + agent.personality.get("risk_tolerance", 0.5) * 0.5,
            "iron": agent.personality.get("aggressiveness", 0.5) * 0.7 + agent.personality.get("ambition", 0.5) * 0.5,
            "ledger": agent.skills.get("trading", 0.2) * 1.1 + agent.personality.get("ambition", 0.5) * 0.3,
        }
        key = max(scores, key=lambda k: scores[k] + rng.uniform(0, 0.08))
        buckets[key].append(aid)
    total = max(1, sum(len(v) for v in buckets.values()))
    settlement.factions = []
    for key, name, value, desc in definitions:
        member_ids = buckets[key]
        if not member_ids:
            continue
        settlement.factions.append({
            "id": f"{settlement.id}_{key}",
            "name": name,
            "value": value,
            "description": desc,
            "members": member_ids,
            "share": round(len(member_ids) / total, 2),
        })
    settlement.factions.sort(key=lambda f: f["share"], reverse=True)


def consider_laws(
    settlement: Settlement,
    agents: dict[str, Any],
    culture: Any,
    day: int,
    flags: dict[str, Any],
    no_currency: bool = False,
) -> list[dict[str, Any]]:
    enacted = []
    if any(law["key"] == "rationing" for law in settlement.laws):
        pass
    else:
        hunger = sum(1 for aid in settlement.member_ids if aid in agents and agents[aid].needs["hunger"] < 35)
        if settlement.storage.get("food", 0) < settlement.population * 0.8 or hunger >= max(2, settlement.population // 3):
            law = enact_law(settlement, "rationing", day, support=60 + culture.values.get("cooperation", 0.5) * 20 if culture else 60)
            if law:
                enacted.append(law)
    if not any(law["key"] == "hospitality" for law in settlement.laws) and culture and culture.values.get("hospitality", 0.5) > 0.6 and settlement.population >= 8:
        law = enact_law(settlement, "hospitality", day, support=55 + culture.values["hospitality"] * 30)
        if law:
            enacted.append(law)
    if flags.get("theft") and not any(law["key"] == "punishment" for law in settlement.laws):
        law = enact_law(settlement, "punishment", day, support=55 + culture.values.get("hierarchy", 0.5) * 25 if culture else 55)
        if law:
            enacted.append(law)
    if culture and culture.values.get("cooperation", 0.5) > 0.6 and settlement.population >= 9 and not any(law["key"] == "common_land" for law in settlement.laws):
        law = enact_law(settlement, "common_land", day, support=58)
        if law:
            enacted.append(law)
    if settlement.population >= 12 and not any(law["key"] == "elders" for law in settlement.laws) and culture and culture.values.get("tradition", 0.5) > 0.52:
        law = enact_law(settlement, "elders", day, support=57)
        if law:
            enacted.append(law)
    if settlement.uses_currency and not no_currency and not any(law["key"] == "tax" for law in settlement.laws) and settlement.population >= 10:
        law = enact_law(settlement, "tax", day, support=48)
        if law:
            enacted.append(law)
    return enacted
