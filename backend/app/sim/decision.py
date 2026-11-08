"""Hybrid agent decision engine.

Layers:
  1. utility scoring for immediate survival and daily action choice
  2. persistent goals that bias those utilities
  3. committed travel/behavior execution (in the engine)
  4. an optional LLM narrative layer for a small number of significant events

Every explanation is assembled from the scores and facts that produced the
decision. Nothing is written after the fact to justify a random outcome.
"""
from __future__ import annotations

import random
import zlib
from typing import Any

from .constants import SEASON_GROWTH, TECHS
from .economy import agent_valuation, surplus_offer, wanted_item

MAX_ACTION_CHOICES = 4


def _fmt_need(value: float) -> str:
    return f"{round(value)}/100"


def _remembered_tiles(agent: Any, tag: str) -> list[tuple[int, int]]:
    tiles: list[tuple[int, int]] = []
    for memory in reversed(agent.memory.short_term + agent.memory.long_term):
        if tag in memory.tags and memory.location:
            tiles.append((int(memory.location[0]), int(memory.location[1])))
        if len(tiles) >= 6:
            break
    return tiles


def _nearby_agents(engine: Any, agent: Any, radius: int = 5) -> list[Any]:
    return [
        other for other in engine.alive_agents()
        if other.id != agent.id and abs(other.position[0] - agent.position[0]) <= radius
        and abs(other.position[1] - agent.position[1]) <= radius
    ]


def _distance(ax: int, ay: int, bx: int, by: int) -> int:
    return abs(ax - bx) + abs(ay - by)


def decide(agent: Any, engine: Any) -> dict[str, Any]:
    world = engine.world
    day = engine.day
    settlement = engine.settlements.get(agent.settlement_id or "")
    nearby = _nearby_agents(engine, agent, 6)
    at_tile = world.tile_or_raise(agent.position[0], agent.position[1])
    at_settlement_water = bool(
        settlement is not None
        and (settlement.has_building("well") or settlement.has_building("aqueduct"))
        and abs(agent.position[0] - settlement.position[0]) <= 2
        and abs(agent.position[1] - settlement.position[1]) <= 2
    )
    at_water = at_tile.freshwater or at_settlement_water
    has_settlement_stores = bool(settlement and settlement.member_ids and settlement.storage.get("food", 0) > 0.5)
    food_secured = agent.inventory.get("food", 0) + (settlement.storage.get("food", 0) if settlement else 0.0)
    hunger_pressure = max(0.0, 100.0 - agent.needs["hunger"])
    thirst_pressure = max(0.0, 100.0 - agent.needs["thirst"])
    energy_pressure = max(0.0, 100.0 - agent.needs["energy"])
    social_pressure = max(0.0, 100.0 - agent.needs["social"])
    danger = engine.agent_danger(agent)
    season_growth = SEASON_GROWTH.get(engine.season, 1.0)
    rng = random.Random(zlib.crc32(f"{agent.id}:{day}:{world.seed}".encode("utf-8")))
    options: list[dict[str, Any]] = []

    def add(kind: str, label: str, score: float, reasons: list[str], target: dict[str, Any] | None = None) -> None:
        if score <= 0:
            return
        options.append({
            "kind": kind, "label": label, "score": round(score, 1),
            "reasons": reasons, "target": target or {},
        })

    # ---------------------------------------------------------------- survival
    if agent.needs["hunger"] < 86 and agent.inventory.get("food", 0) >= 0.9:
        score = hunger_pressure * 0.95 + (14 if agent.needs["hunger"] < 35 else 0)
        add("eat", "Eat from personal stores", score, [
            f"food need is {_fmt_need(agent.needs['hunger'])}",
            f"{agent.inventory.get('food', 0):.1f} food is carried",
        ])
    if agent.needs["thirst"] < 88:
        if at_water:
            score = thirst_pressure * 1.12 + (16 if agent.needs["thirst"] < 35 else 0)
            add("drink", "Drink from the freshwater source", score, [
                f"water need is {_fmt_need(agent.needs['thirst'])}",
                "a freshwater source is at this location",
            ])
        elif agent.inventory.get("water", 0) >= 0.9:
            score = thirst_pressure * 0.88
            add("drink_stored", "Drink from water carried", score, [
                f"water need is {_fmt_need(agent.needs['thirst'])}",
                f"{agent.inventory.get('water', 0):.1f} water is carried",
            ])
        else:
            target = world.find_resource(tuple(agent.position), "water", max_radius=16)
            if target:
                dist = _distance(agent.position[0], agent.position[1], target.x, target.y)
                score = thirst_pressure * 1.18 + max(0, 8 - dist) * 1.2
                add("seek_water", f"Travel to water {dist} tiles away", score, [
                    f"water need is {_fmt_need(agent.needs['thirst'])}",
                    "the nearest freshwater is reachable",
                ], {"tile": [target.x, target.y]})

    # Food: eat from settlement stores before individual foraging if available.
    if has_settlement_stores and settlement and agent.needs["hunger"] < 75:
        score = hunger_pressure * 0.82 + 4
        add("settlement_meal", "Draw a meal from the settlement stores", score, [
            f"food need is {_fmt_need(agent.needs['hunger'])}",
            f"the settlement holds {settlement.storage.get('food', 0):.1f} food",
        ], {"settlement_id": settlement.id, "tile": list(settlement.position)})

    food_tile = None
    remembered_food = _remembered_tiles(agent, "food_source")
    if agent.needs["hunger"] < 92 or food_secured < 4:
        food_tile = world.find_resource(tuple(agent.position), "food", max_radius=18, remembered=remembered_food)
    if food_tile:
        dist = _distance(agent.position[0], agent.position[1], food_tile.x, food_tile.y)
        local_bonus = 10 if dist == 0 else max(0, 8 - dist) * 0.8
        score = (
            hunger_pressure * 0.62
            + max(0.0, 7 - food_secured) * 4.5
            + agent.skills["gathering"] * 16
            + local_bonus
            + season_growth * 4
            + (6 if settlement and settlement.storage.get("food", 0) < settlement.population else 0)
        )
        label = "Forage at this location" if dist == 0 else f"Forage {dist} tiles away"
        add("forage", label, score, [
            f"food need is {_fmt_need(agent.needs['hunger'])} and {food_secured:.1f} food is available",
            f"gathering skill is {agent.skills['gathering']:.2f}",
        ], {"tile": [food_tile.x, food_tile.y], "resource": "food"})

    game_tile = None
    if agent.needs["hunger"] < 88 or food_secured < 5:
        game_tile = world.find_resource(tuple(agent.position), "food", max_radius=16, remembered=_remembered_tiles(agent, "hunt"))
        if game_tile and "game" in game_tile.resources:
            dist = _distance(agent.position[0], agent.position[1], game_tile.x, game_tile.y)
            score = (
                hunger_pressure * 0.48
                + agent.skills["hunting"] * 26
                + agent.personality["aggressiveness"] * 10
                + max(0, 5 - food_secured) * 3
                + (8 if agent.personality["risk_tolerance"] > 0.6 else 0)
                - dist * 0.4
            )
            add("hunt", f"Hunt game {dist} tiles away", score, [
                f"hunger is {_fmt_need(agent.needs['hunger'])}",
                f"hunting skill is {agent.skills['hunting']:.2f}",
            ], {"tile": [game_tile.x, game_tile.y], "resource": "game"})

    # ------------------------------------------------------------- energy/rest
    if agent.needs["energy"] < 80:
        shelter_bonus = 8 if agent.needs["shelter"] > 55 or (settlement and settlement.has_building("house")) else 0
        score = energy_pressure * 0.92 + shelter_bonus + (6 if agent.needs["health"] < 45 else 0)
        add("rest", "Rest and recover strength", score, [
            f"energy is {_fmt_need(agent.needs['energy'])}",
            "rest restores energy and health",
        ])

    # ------------------------------------------------------------ social life
    potential_friends = [
        other for other in nearby
        if other.relationships.get(agent.id) is None or other.relationships[agent.id].trust >= -20
    ]
    if social_pressure > 18 and potential_friends:
        other = min(potential_friends, key=lambda o: _distance(agent.position[0], agent.position[1], o.position[0], o.position[1]))
        dist = _distance(agent.position[0], agent.position[1], other.position[0], other.position[1])
        rel = agent.relationships.get(other.id)
        familiarity = 8 if rel and rel.interactions > 0 else 0
        score = social_pressure * 0.5 + agent.personality["sociability"] * 18 + familiarity + max(0, 5 - dist)
        add("socialize", f"Seek out {other.name}", score, [
            f"social need is {_fmt_need(agent.needs['social'])}",
            f"{other.name} is {dist} tiles away",
        ], {"agent_id": other.id, "tile": list(other.position)})

    if agent.partner_id:
        partner = engine.agents.get(agent.partner_id)
        if partner and partner.alive and _distance(agent.position[0], agent.position[1], partner.position[0], partner.position[1]) <= 8:
            if social_pressure > 10 or agent.needs["shelter"] < 55 or partner.pregnant:
                score = social_pressure * 0.35 + agent.personality["empathy"] * 12 + (14 if partner.pregnant else 0)
                add("visit_partner", f"Spend time with {partner.name}", score, [
                    f"social need is {_fmt_need(agent.needs['social'])}",
                    "a committed partner lives nearby",
                ], {"agent_id": partner.id, "tile": list(partner.position)})

    # Help someone who is worse off, if this agent can afford it.
    for other in nearby:
        if other.needs["hunger"] < 35 and agent.inventory.get("food", 0) > 2.0 and agent.personality["empathy"] > 0.45:
            dist = _distance(agent.position[0], agent.position[1], other.position[0], other.position[1])
            score = agent.personality["empathy"] * 22 + agent.personality["cooperation"] * 10 + max(0, 5 - dist)
            add("help_food", f"Offer food to {other.name}", score, [
                f"{other.name}'s food need is {_fmt_need(other.needs['hunger'])}",
                f"empathy is {agent.personality['empathy']:.2f} and food is in surplus",
            ], {"agent_id": other.id, "tile": list(other.position)})
            break

    # Trade: requires a counterpart, something to offer and a real want.
    offer = surplus_offer(agent)
    want = wanted_item(agent)
    if offer and want and nearby:
        partner_candidates = []
        for other in nearby:
            other_offer = surplus_offer(other)
            other_want = wanted_item(other)
            if other_want == offer or other_offer == want:
                dist = _distance(agent.position[0], agent.position[1], other.position[0], other.position[1])
                partner_candidates.append((dist, other))
        if partner_candidates:
            dist, other = min(partner_candidates, key=lambda pair: pair[0])
            ratio = agent_valuation(agent, want) / max(0.1, agent_valuation(other, offer))
            score = (
                agent.skills["trading"] * 22
                + agent.personality["cooperation"] * 7
                + (6 if settlement and settlement.has_building("market") else 0)
                + (4 if "trade" in settlement.known_techs else 0) if settlement else 0
                + max(0, 4 - dist)
                + (5 if agent.ambition == "become the wealthiest trader" else 0)
                - abs(ratio - 1.0) * 2
            )
            add("trade", f"Trade with {other.name}", score, [
                f"surplus {offer} and unmet need for {want}",
                f"trading skill is {agent.skills['trading']:.2f}",
            ], {"agent_id": other.id, "tile": list(other.position), "offer": offer, "want": want})

    # Courting and family formation.
    if agent.partner_id is None and agent.is_adult and agent.age <= 60:
        candidates = [
            other for other in nearby
            if other.is_adult and other.partner_id is None and other.alive
            and abs(other.age - agent.age) <= 22
            and (agent.reproductive_role in ("bearer", "sire") or other.reproductive_role in ("bearer", "sire"))
        ]
        if candidates:
            def bond_score(other: Any) -> float:
                rel = agent.relationships.get(other.id)
                affinity = rel.affinity if rel else 0
                # Prefer a partner a family is possible with. Without this the
                # marriage market filled with same-sex and reproductively
                # incompatible couples (6 of 9 couples at one point) and the
                # birth rate collapsed even though everyone was partnered.
                complement = 0.0
                if {agent.reproductive_role, other.reproductive_role} == {"bearer", "sire"}:
                    complement = 45.0
                return affinity + agent.personality["sociability"] * 8 + other.personality["cooperation"] * 5 + complement
            other = max(candidates, key=bond_score)
            rel = agent.relationships.get(other.id)
            affinity = rel.affinity if rel else 0
            # Requiring an existing affinity of 18 just to *consider* courtship
            # meant couples never formed at all: affinity only rises through
            # repeated chance conversations with one specific person, and the
            # court action never appeared in a 1500-day run. Adults actively
            # look for a partner; the affinity that decides whether a bond forms
            # is built by the courtship itself, below.
            if affinity > -5 or agent.personality["sociability"] > 0.3:
                compatible_near = sum(
                    1 for o in candidates
                    if {agent.reproductive_role, o.reproductive_role} == {"bearer", "sire"}
                )
                score = (
                    26
                    + agent.personality["sociability"] * 9
                    + agent.personality["empathy"] * 7
                    + max(0, affinity) * 0.25
                    + (8 if "build a large family" in agent.ambition else 0)
                    + (10 if not agent.child_ids else 0)
                    + (10 if compatible_near and agent.reproductive_role == "bearer" and agent.age_years >= 30 else 0)
                    - (8 if agent.needs["hunger"] < 35 else 0)
                )
                add("court", f"Court {other.name}", score, [
                    f"affinity with {other.name} is {affinity:.0f}",
                    "both are unpartnered adults",
                ], {"agent_id": other.id, "tile": list(other.position)})

    # ------------------------------------------------------------ production
    if settlement and settlement.member_ids:
        # Deposit surplus into commons; cooperation and citizenship reward.
        if agent.inventory.get("food", 0) > 5 or agent.inventory.get("wood", 0) > 6 or agent.inventory.get("stone", 0) > 1.5:
            if any(settlement.has_room_for(item) for item in ("food", "wood", "stone", "herbs", "ore")):
                score = 6 + agent.personality["cooperation"] * 10 + (4 if "common_land" in {law["key"] for law in settlement.laws} else 0)
                carried_materials = agent.inventory.get("wood", 0) + agent.inventory.get("stone", 0)
                if carried_materials >= 2 and (settlement.build_queue or settlement.housing_capacity() < settlement.population):
                    score += 10 + min(26.0, carried_materials * 1.5)
                add("deposit", "Contribute surplus to the settlement", score, [
                    f"carrying {agent.inventory.get('food', 0):.1f} food and {agent.inventory.get('wood', 0):.1f} wood",
                    "settlement storage has room",
                ], {"settlement_id": settlement.id, "tile": list(settlement.position)})

        if settlement.build_queue:
            project = settlement.build_queue[0]
            score = (
                agent.skills["construction"] * 26
                + 14
                + (14 if settlement.housing_capacity() < settlement.population else 0)
                + (8 if agent.occupation == "Builder" else 0)
            )
            add("build", f"Work on {project['name']}", score, [
                f"the settlement is building a {project['name'].lower()}",
                f"construction skill is {agent.skills['construction']:.2f}",
            ], {"settlement_id": settlement.id, "project_id": project.get("id"), "tile": list(settlement.position)})

        farm_count = settlement.building_count("farm")
        if farm_count and engine.season in ("Spring", "Summer", "Autumn"):
            food_short = settlement.storage.get("food", 0) < settlement.population * 1.2
            score = (
                agent.skills["farming"] * 26
                + SEASON_GROWTH.get(engine.season, 1.0) * 8
                + (10 if food_short else 0)
                + (5 if agent.occupation == "Farmer" else 0)
            )
            add("farm", "Work the settlement farms", score, [
                f"farming skill is {agent.skills['farming']:.2f}",
                "the season supports cultivation",
            ], {"settlement_id": settlement.id, "tile": list(settlement.position)})

        if settlement.has_building("market") and settlement.uses_currency:
            currency = agent.inventory.get("currency", 0)
            trade_score = 5 + agent.skills["trading"] * 10 + (currency * 0.12)
            if currency < 4 and settlement.storage.get("food", 0) >= 4:
                trade_score += 3
            add("market", f"Visit the market in {settlement.name}", trade_score, [
                f"carrying {currency:.1f} currency",
                "the settlement has a market",
            ], {"settlement_id": settlement.id, "tile": list(settlement.position)})

    # Resource gathering for construction and tools.
    build_need = 1 if (settlement and settlement.build_queue) else 0
    storage_wood = settlement.storage.get("wood", 0.0) if settlement else 0.0
    storage_stone = settlement.storage.get("stone", 0.0) if settlement else 0.0
    stock_target_wood = 12.0 + (settlement.population * 1.5 if settlement else 0.0)
    stock_target_stone = 4.0 + (settlement.population * 0.7 if settlement else 0.0)
    wood_shortfall = max(0.0, stock_target_wood - storage_wood)
    stone_shortfall = max(0.0, stock_target_stone - storage_stone)
    has_masonry = "masonry" in (set(settlement.known_techs) if settlement else set(agent.known_techs))
    wood_target = world.find_resource(tuple(agent.position), "wood", max_radius=16, remembered=_remembered_tiles(agent, "wood_source"))
    if wood_target and (agent.inventory.get("wood", 0) < 8 or wood_shortfall > 0):
        dist = _distance(agent.position[0], agent.position[1], wood_target.x, wood_target.y)
        personal_wood_gap = max(0.0, 5.0 - agent.inventory.get("wood", 0))
        score = (
            9
            + personal_wood_gap * 9.0
            + min(20.0, wood_shortfall * 1.6)
            + build_need * 10
            + agent.skills["construction"] * 10
            + (6 if agent.settlement_id is None and agent.inventory.get("food", 0) >= 3 else 0)
            - dist * 0.35
        )
        add("gather_wood", f"Gather wood {dist} tiles away", score, [
            f"carrying {agent.inventory.get('wood', 0):.1f} wood; the settlement holds {storage_wood:.1f}",
            "wood is needed for shelter and construction",
        ], {"tile": [wood_target.x, wood_target.y], "resource": "wood"})
    stone_target = world.find_resource(tuple(agent.position), "stone", max_radius=18, remembered=_remembered_tiles(agent, "stone_source"))
    if stone_target and (has_masonry or build_need or stone_shortfall > 0 or agent.inventory.get("stone", 0) < 3):
        dist = _distance(agent.position[0], agent.position[1], stone_target.x, stone_target.y)
        score = (
            7
            + min(16.0, stone_shortfall * 1.6)
            + max(0, 5 - agent.inventory.get("stone", 0)) * 3
            + (10 if settlement and settlement.housing_capacity() < settlement.population and settlement.storage.get("stone", 0) < 4 else 0)
            + build_need * 8
            + agent.skills["construction"] * 6
            - dist * 0.35
        )
        add("gather_stone", f"Quarry stone {dist} tiles away", score, [
            f"the settlement holds {storage_stone:.1f} stone and needs more for building",
            f"stone is {dist} tiles distant",
        ], {"tile": [stone_target.x, stone_target.y], "resource": "stone"})
    if agent.needs["health"] < 55:
        herb_target = world.find_resource(tuple(agent.position), "herbs", max_radius=14)
        if herb_target:
            dist = _distance(agent.position[0], agent.position[1], herb_target.x, herb_target.y)
            score = (100 - agent.needs["health"]) * 0.65 + max(0, 6 - dist)
            add("gather_herbs", f"Seek herbs {dist} tiles away", score, [
                f"health is {_fmt_need(agent.needs['health'])}",
                "herbs can aid recovery",
            ], {"tile": [herb_target.x, herb_target.y], "resource": "herbs"})

    if agent.inventory.get("tools", 0) < 2 and agent.inventory.get("wood", 0) >= 2:
        score = 6 + agent.skills["crafting"] * 22 + (8 if settlement and settlement.has_building("workshop") else 0)
        add("craft_tools", "Craft tools", score, [
            f"tool stock is {agent.inventory.get('tools', 0):.1f}",
            f"crafting skill is {agent.skills['crafting']:.2f}",
        ])

    # ---------------------------------------------------------------- research
    research_candidates = engine.research_candidates(agent)
    if research_candidates:
        key = research_candidates[0]
        known_count = len(settlement.known_techs) if settlement else len(agent.known_techs)
        food_ok = agent.needs["hunger"] > 45 and agent.needs["thirst"] > 45
        score = (
            agent.personality["curiosity"] * 15
            + agent.personality["intelligence"] * 12
            + agent.skills["research"] * 26
            + (7 if "discover knowledge that outlives me" in agent.ambition else 0)
            + (5 if settlement and settlement.has_building("workshop") else 0)
            + (5 if food_ok else -12)
            + (3 if known_count < 4 else 0)
        )
        add("research", f"Study {TECHS[key]['name']}", score, [
            f"curiosity is {agent.personality['curiosity']:.2f} and research skill is {agent.skills['research']:.2f}",
            f"{TECHS[key]['name']} is within reach of current knowledge",
        ], {"tech": key})

    # ----------------------------------------------------------- settlement
    if agent.settlement_id is None and day >= 4:
        site = engine.find_founding_site(agent)
        if site:
            reasons = [
                f"carrying {agent.inventory.get('food', 0):.1f} food, {agent.inventory.get('wood', 0):.1f} wood, {agent.inventory.get('stone', 0):.1f} stone",
                "the site has freshwater and fertile land",
            ]
            resources_ok = agent.inventory.get("food", 0) >= 5 and agent.inventory.get("wood", 0) >= 4
            score = (
                agent.personality["ambition"] * 30
                + agent.skills["leadership"] * 24
                + agent.personality["cooperation"] * 10
                + (14 if "found a lasting settlement" in agent.ambition else 0)
                + (8 if resources_ok else -15)
            )
            if site.get("distance", 99) <= 2:
                score += 8
            add("found_settlement", f"Found a settlement at ({site['tile'][0]}, {site['tile'][1]})", score, reasons, site)

    if settlement and settlement.member_ids:
        member_happiness = settlement.happiness
        if member_happiness < 38 or settlement.stability < 32 or danger > 40:
            other = engine.best_migration_target(agent)
            score = (45 - member_happiness) * 0.75 + (40 - settlement.stability) * 0.4 + danger * 0.4
            if other:
                score += 8
            add("migrate", "Leave for a better life" if other is None else f"Migrate to {other['name']}", score, [
                f"settlement happiness is {member_happiness:.0f}",
                f"stability is {settlement.stability:.0f}",
            ], other or {})
        if danger > 35:
            if agent.inventory.get("food", 0) > 1:
                score = danger * 1.1 + agent.personality["risk_tolerance"] * 5
                add("flee", "Retreat to safety", score, [
                    f"threat level is {danger:.0f}",
                    "there is a hostile presence nearby",
                ])

    # ---------------------------------------------------------- self/explore
    if agent.personality["curiosity"] > 0.45 and hunger_pressure < 55 and thirst_pressure < 55 and energy_pressure < 55:
        target = engine.exploration_target(agent, rng)
        if target:
            dist = _distance(agent.position[0], agent.position[1], target[0], target[1])
            score = (
                agent.personality["curiosity"] * 16
                + agent.personality["risk_tolerance"] * 10
                + agent.skills["exploration"] * 14
                + (7 if "explore every corner of the world" in agent.ambition else 0)
                - dist * 0.15
                + rng.uniform(0, 3)
            )
            add("explore", "Explore unfamiliar terrain", score, [
                f"curiosity is {agent.personality['curiosity']:.2f}",
                "basic needs are stable enough to range out",
            ], {"tile": list(target)})

    if agent.needs["shelter"] < 45 and agent.inventory.get("wood", 0) >= 4 and not (settlement and settlement.has_building("house")):
        score = (100 - agent.needs["shelter"]) * 0.6 + 5
        add("build_shelter", "Build a personal shelter", score, [
            f"shelter need is {_fmt_need(agent.needs['shelter'])}",
            "enough wood is carried",
        ])

    # ------------------------------------------------------------- conflict
    hostile = [
        other for other in nearby
        if other.id in agent.relationships and agent.relationships[other.id].affinity < -20
    ]
    if hostile and agent.personality["aggressiveness"] > 0.45 and agent.needs["safety"] > 25:
        other = min(hostile, key=lambda o: _distance(agent.position[0], agent.position[1], o.position[0], o.position[1]))
        rel = agent.relationships[other.id]
        score = agent.personality["aggressiveness"] * 15 + max(0, -rel.affinity) * 0.25 + danger * 0.2 - (8 if agent.needs["health"] < 45 else 0)
        add("confront", f"Confront {other.name}", score, [
            f"relationship with {other.name} is hostile (affinity {rel.affinity:.0f})",
            f"aggressiveness is {agent.personality['aggressiveness']:.2f}",
        ], {"agent_id": other.id, "tile": list(other.position)})

    if agent.needs["hunger"] < 26 and agent.inventory.get("food", 0) < 0.5 and agent.personality["honesty"] < 0.5:
        victims = [o for o in nearby if o.inventory.get("food", 0) >= 1]
        if victims:
            other = max(victims, key=lambda o: o.inventory.get("food", 0))
            dist = _distance(agent.position[0], agent.position[1], other.position[0], other.position[1])
            score = (26 - agent.needs["hunger"]) * 1.6 + (0.5 - agent.personality["honesty"]) * 30 + max(0, 4 - dist)
            add("steal", f"Take food from {other.name}", score, [
                f"hunger is critical ({_fmt_need(agent.needs['hunger'])})",
                f"honesty is low ({agent.personality['honesty']:.2f})",
            ], {"agent_id": other.id, "tile": list(other.position)})

    # --------------------------------------------------------------- goal bias
    for option in options:
        if "found a lasting settlement" in agent.ambition and option["kind"] in ("found_settlement", "build", "gather_wood", "deposit"):
            option["score"] = round(option["score"] + 4, 1)
        if "become a respected leader" in agent.ambition and option["kind"] in ("socialize", "build", "deposit", "help_food"):
            option["score"] = round(option["score"] + 3, 1)
        if "master the art of farming" in agent.ambition and option["kind"] in ("farm", "forage"):
            option["score"] = round(option["score"] + 4, 1)
        if "build a large family" in agent.ambition and option["kind"] in ("court", "visit_partner"):
            option["score"] = round(option["score"] + 5, 1)
        if "become the wealthiest trader" in agent.ambition and option["kind"] in ("trade",):
            option["score"] = round(option["score"] + 6, 1)
        if "discover knowledge that outlives me" in agent.ambition and option["kind"] == "research":
            option["score"] = round(option["score"] + 5, 1)
        if "craft tools of unmatched quality" in agent.ambition and option["kind"] == "craft_tools":
            option["score"] = round(option["score"] + 6, 1)
        if "explore every corner of the world" in agent.ambition and option["kind"] == "explore":
            option["score"] = round(option["score"] + 5, 1)

    # A person in immediate danger does not calmly decide to study astronomy.
    if agent.needs["thirst"] < 18:
        options = [o for o in options if o["kind"] in ("drink", "drink_stored", "seek_water", "eat")]
    elif agent.needs["hunger"] < 14:
        options = [o for o in options if o["kind"] in ("eat", "settlement_meal", "forage", "hunt", "steal")]
    if not options:
        options.append({
            "kind": "rest", "label": "Wait and watch", "score": 1.0,
            "reasons": ["no worthwhile action was available"], "target": {},
        })

    options.sort(key=lambda option: option["score"], reverse=True)
    for option in options:
        option["score"] += rng.uniform(0, 0.9)
    options.sort(key=lambda option: option["score"], reverse=True)
    chosen = options[0]

    reasons = list(chosen["reasons"])
    if chosen.get("target", {}).get("tile"):
        tile = chosen["target"]["tile"]
        if tile != agent.position:
            reasons.append(f"the destination is {_distance(agent.position[0], agent.position[1], tile[0], tile[1])} tiles away")
    runner_up = next((o for o in options[1:] if o["kind"] != chosen["kind"]), None)
    thought = f"{agent.name} chose to {chosen['label'][0].lower() + chosen['label'][1:]}. " + "; ".join(reasons) + "."
    if runner_up:
        thought += f" Alternative '{runner_up['label']}' scored {runner_up['score']:.0f}."

    alternatives = [
        {"kind": o["kind"], "label": o["label"], "score": o["score"]}
        for o in options[:MAX_ACTION_CHOICES]
    ]
    return {
        "kind": chosen["kind"],
        "label": chosen["label"],
        "score": round(chosen["score"], 1),
        "target": chosen.get("target", {}),
        "reasons": chosen["reasons"],
        "thought": thought,
        "alternatives": alternatives,
        "needs_snapshot": {k: round(v, 1) for k, v in agent.needs.items()},
        "context": {
            "food": round(food_secured, 1),
            "local_food": round(at_tile.resources.get("berries", 0) + at_tile.resources.get("game", 0), 2),
            "water_access": at_water,
            "nearby_agents": len(nearby),
            "danger": round(danger, 1),
            "settlement": settlement.name if settlement else None,
        },
    }
