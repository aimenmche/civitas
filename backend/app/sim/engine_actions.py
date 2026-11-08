"""Agent daily behavior and action execution."""
from __future__ import annotations

import random
import zlib
from typing import Any

from .agent import Agent
from .constants import BUILDINGS, TECHS
from .decision import decide


class ActionsMixin:
    # --------------------------------------------------------------- daily
    def _agent_day(self, agent: Agent) -> None:
        if not agent.alive:
            return
        if agent.age_years < 16:
            self._child_day(agent)
            return
        action = agent.action if isinstance(agent.action, dict) else {}
        if action.get("phase") == "moving":
            emergency = (
                (agent.needs["thirst"] < 12 and action.get("kind") not in ("drink", "drink_stored", "seek_water"))
                or (agent.needs["hunger"] < 10 and action.get("kind") not in ("eat", "settlement_meal", "forage", "hunt", "steal"))
                or agent.needs["health"] < 15
            )
            if emergency:
                agent.action = {}
                agent.path = []
                agent.state = "reconsidering"
            else:
                self._advance_travel(agent)
                return
        decision = decide(agent, self)
        agent.decision = decision
        if decision["kind"] == "found_settlement" and agent.settlement_id:
            # Members may not quietly secede while standing in their own town.
            decision = {**decision, "kind": "deposit", "label": "Contribute to the community"}
        self._begin_action(agent, decision)

    def _begin_action(self, agent: Agent, decision: dict[str, Any]) -> None:
        action: dict[str, Any] = {
            "kind": decision["kind"],
            "label": decision["label"],
            "score": decision.get("score", 0),
            "target": decision.get("target", {}),
            "reasons": decision.get("reasons", []),
            "phase": "active",
            "started_day": self.day,
            "started_tick": self.tick,
        }
        agent.action = action
        agent.state = decision["label"]
        target = decision.get("target", {})
        # Leaving is immediate; arrival decides what happens next.
        if decision["kind"] == "migrate" and agent.settlement_id:
            self._leave_settlement(agent, reason="sought a better life")
        # Give flee a concrete direction if the decision did not.
        if decision["kind"] == "flee" and not target.get("tile"):
            rng = random.Random(zlib.crc32(f"flee:{agent.id}:{self.day}".encode()))
            for _ in range(8):
                dx, dy = rng.choice([-1, 1]), rng.choice([-1, 1])
                tx, ty = agent.position[0] + dx * rng.randint(2, 4), agent.position[1] + dy * rng.randint(2, 4)
                tile = self.world.tile(tx, ty)
                if tile and tile.passable:
                    target = {"tile": [tx, ty]}
                    action["target"] = target
                    break
        tile = target.get("tile")
        if tile and tuple(tile) != tuple(agent.position):
            path = self.world.path_to(tuple(agent.position), tuple(tile))
            if path:
                agent.path = [list(p) for p in path]
                action["phase"] = "moving"
                action["destination"] = list(tile)
                self._advance_travel(agent)
                return
            action["phase"] = "unreachable"
            action["label"] = f"Could not find a route to {decision['label'].lower()}"
            agent.state = action["label"]
            self._memory(
                agent, "observation",
                f"Could not find a route to the intended destination at ({tile[0]}, {tile[1]}).",
                0.2, -0.05, tags=["travel", "failure"],
            )
            return
        self._execute_action(agent, action)

    def _advance_travel(self, agent: Agent) -> None:
        if not agent.path:
            agent.action["phase"] = "active"
            self._execute_action(agent, agent.action)
            return
        steps = 2 if agent.skills["exploration"] < 0.6 else 3
        for _ in range(steps):
            if not agent.path:
                break
            nxt = agent.path.pop(0)
            agent.position = [int(nxt[0]), int(nxt[1])]
            agent.needs["energy"] = max(0.0, agent.needs["energy"] - 0.45)
        if agent.skills["exploration"] < 1:
            agent.gain_skill("exploration", 0.0015)
        if not agent.path:
            agent.action["phase"] = "arrived"
            self._execute_action(agent, agent.action)

    # ------------------------------------------------------------- children
    def _child_day(self, agent: Agent) -> None:
        agent.state = "Childhood"
        settlement = self.settlements.get(agent.settlement_id or "")
        mother = None
        if agent.parent_ids:
            mother = self.agents.get(agent.parent_ids[0])
        if agent.age_years < 4 and mother and mother.alive:
            agent.position = list(mother.position)
            agent.home_tile = list(mother.position)
            agent.action = {"kind": "childcare", "label": f"Staying close to {mother.name}", "phase": "done"}
        else:
            agent.action = {"kind": "childhood", "label": "Learning and playing" if agent.age_years < 12 else "Training with adults", "phase": "done"}
        # Children are provisioned by household then by the settlement commons.
        if agent.needs["hunger"] < 68:
            fed = False
            if mother and mother.alive:
                nearby = abs(mother.position[0] - agent.position[0]) <= 2 and abs(mother.position[1] - agent.position[1]) <= 2
                if nearby and mother.inventory.get("food", 0) >= 0.8 and mother.personality["empathy"] > 0.25:
                    mother.inventory["food"] -= 0.7
                    agent.needs["hunger"] = min(100, agent.needs["hunger"] + 34)
                    fed = True
            if not fed and settlement and settlement.storage.get("food", 0) >= 0.7:
                settlement.storage["food"] = round(settlement.storage["food"] - 0.7, 2)
                settlement.stats["meals_today"] = settlement.stats.get("meals_today", 0) + 1
                agent.needs["hunger"] = min(100, agent.needs["hunger"] + 32)
                fed = True
            if fed:
                self._memory(agent, "family", "Was fed by family or the settlement.", 0.1, 0.1, tags=["childhood"]) if agent.age_years < 8 else None
        if agent.needs["thirst"] < 65:
            if settlement and (settlement.has_building("well") or settlement.has_building("aqueduct")):
                agent.needs["thirst"] = min(100, agent.needs["thirst"] + 38)
            elif settlement and settlement.storage.get("water", 0) >= 0.4:
                # Adults fill the settlement stores at the river; a child drinks
                # from that common water. Without this a child in a settlement
                # without a well simply dehydrated to death, since children never
                # take a seek_water action of their own.
                settlement.storage["water"] = round(settlement.storage["water"] - 0.4, 2)
                agent.needs["thirst"] = min(100, agent.needs["thirst"] + 38)
            elif agent.inventory.get("water", 0) > 0:
                agent.inventory["water"] -= 0.5
                agent.needs["thirst"] = min(100, agent.needs["thirst"] + 38)
            elif self.world.tile_or_raise(agent.position[0], agent.position[1]).freshwater:
                agent.needs["thirst"] = min(100, agent.needs["thirst"] + 38)
            elif settlement and self._water_near(settlement.position):
                # A household walks to the stream and brings water back; the
                # child drinks from that. Without this, every child in a
                # settlement without a well died of thirst at four.
                agent.needs["thirst"] = min(100, agent.needs["thirst"] + 38)
        agent.needs["social"] = min(100, agent.needs["social"] + 1.5)
        # Children sleep. Without this they drain the same 7 energy/day as an
        # adult but never take a rest action, so every child hit 0 energy and
        # bled health until they died at three or four years old. That single
        # omission killed whole generations and is the main reason worlds went
        # extinct.
        housed = bool(settlement and settlement.housing_capacity() >= settlement.population)
        agent.needs["energy"] = min(100, agent.needs["energy"] + 36 + (8 if housed else 0))
        # Learning: children inherit fragments of their parents' skills even if
        # they never become identical copies.
        if agent.age_years >= 5:
            rng = random.Random(zlib.crc32(f"child:{agent.id}:{self.day}".encode()))
            if agent.parent_ids:
                parents = [self.agents.get(pid) for pid in agent.parent_ids if pid in self.agents]
                if parents:
                    skill = max(parents[0].skills, key=lambda s: parents[0].skills[s])
                    if rng.random() < 0.5:
                        agent.gain_skill(skill, 0.012 * (1 + agent.personality["intelligence"]))
                        agent.skills["research"] = min(1.0, agent.skills["research"] + 0.003)

    # -------------------------------------------------------- action routing
    def _execute_action(self, agent: Agent, action: dict[str, Any]) -> None:
        kind = action.get("kind")
        action["phase"] = "done"
        action["completed_day"] = self.day
        agent.action = action
        try:
            handler = getattr(self, f"_act_{kind}", None)
            if handler is None:
                agent.state = f"Idle ({kind})"
                return
            handler(agent, action)
        except Exception as exc:  # A single broken action must not kill a run.
            self.last_error = f"{kind}: {exc}"
            agent.state = f"Recovering from a failed action"
            action["phase"] = "error"
            action["error"] = str(exc)

    def _target_agent(self, agent: Agent, action: dict[str, Any], radius: int = 2) -> Agent | None:
        target_id = action.get("target", {}).get("agent_id")
        if target_id and target_id in self.agents:
            other = self.agents[target_id]
            if other.alive and abs(other.position[0] - agent.position[0]) <= radius and abs(other.position[1] - agent.position[1]) <= radius:
                return other
        nearby = [
            o for o in self.alive_agents()
            if o.id != agent.id and abs(o.position[0] - agent.position[0]) <= radius and abs(o.position[1] - agent.position[1]) <= radius
        ]
        return nearby[0] if nearby else None

    def _settlement_of(self, agent: Agent) -> Any:
        return self.settlements.get(agent.settlement_id or "")

    def _at_settlement(self, agent: Agent, settlement: Any, radius: int = 2) -> bool:
        if not settlement:
            return False
        return abs(agent.position[0] - settlement.position[0]) <= radius and abs(agent.position[1] - settlement.position[1]) <= radius

    def _water_near(self, position: list[int] | tuple[int, int], radius: int = 3) -> bool:
        """Is there freshwater close enough for a household to fetch?"""
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                tile = self.world.tile(position[0] + dx, position[1] + dy)
                if tile is not None and tile.freshwater:
                    return True
        return False

    def _pay_wage(self, agent: Agent, settlement: Any, amount: float = 0.5) -> None:
        if not settlement or not settlement.uses_currency:
            return
        if settlement.storage.get("currency", 0) >= amount:
            settlement.storage["currency"] = round(settlement.storage.get("currency", 0) - amount, 2)
            agent.inventory["currency"] = round(agent.inventory.get("currency", 0) + amount, 2)

    def _record_meal(self, settlement: Any, amount: float = 1.0) -> None:
        if settlement:
            settlement.stats["meals_today"] = round(settlement.stats.get("meals_today", 0) + amount, 2)

    # ------------------------------------------------------------- survival
    def _act_eat(self, agent: Agent, action: dict[str, Any]) -> None:
        if agent.inventory.get("food", 0) < 0.5:
            agent.state = "Found nothing to eat"
            self._memory(agent, "survival", "Reached for food and found the pack empty.", 0.35, -0.3, tags=["hunger"])
            return
        agent.inventory["food"] = round(agent.inventory["food"] - 1.0, 2)
        before = agent.needs["hunger"]
        agent.needs["hunger"] = min(100, agent.needs["hunger"] + 45)
        agent.needs["energy"] = min(100, agent.needs["energy"] + 3)
        agent.state = "Eating"
        if agent.needs["hunger"] > 80 and before < 40:
            self._memory(agent, "survival", "Ate a full meal after hunger had set in.", 0.3, 0.4, tags=["food"])

    def _act_drink(self, agent: Agent, action: dict[str, Any]) -> None:
        tile = self.world.tile_or_raise(agent.position[0], agent.position[1])
        settlement = self._settlement_of(agent)
        source = "freshwater"
        if not tile.freshwater:
            if settlement and self._at_settlement(agent, settlement, 2) and (settlement.has_building("well") or settlement.has_building("aqueduct")):
                source = "the settlement well"
            else:
                agent.state = "Sought water but found none"
                return
        agent.needs["thirst"] = min(100, agent.needs["thirst"] + 58)
        agent.state = f"Drinking from {source}"
        if agent.needs["thirst"] > 90:
            self._memory(agent, "survival", f"Drank deeply from {source}.", 0.12, 0.2, tags=["water"], location=list(agent.position))

    def _act_drink_stored(self, agent: Agent, action: dict[str, Any]) -> None:
        if agent.inventory.get("water", 0) < 0.5:
            self._act_seek_water(agent, action)
            return
        agent.inventory["water"] = round(agent.inventory["water"] - 1.0, 2)
        agent.needs["thirst"] = min(100, agent.needs["thirst"] + 58)
        agent.state = "Drinking carried water"

    def _act_seek_water(self, agent: Agent, action: dict[str, Any]) -> None:
        self._act_drink(agent, action)

    def _act_settlement_meal(self, agent: Agent, action: dict[str, Any]) -> None:
        settlement = self._settlement_of(agent)
        if not settlement or not self._at_settlement(agent, settlement, 3):
            self._act_eat(agent, action)
            return
        if settlement.storage.get("food", 0) < 0.8:
            agent.state = "Found the settlement stores empty"
            self._memory(agent, "social", f"Found the stores of {settlement.name} empty.", 0.5, -0.4, tags=["hunger", "settlement"])
            return
        settlement.storage["food"] = round(settlement.storage["food"] - 1.0, 2)
        self._record_meal(settlement, 1.0)
        agent.needs["hunger"] = min(100, agent.needs["hunger"] + 42)
        agent.state = f"Eating from the stores of {settlement.name}"
        agent.influence = min(100, agent.influence + 0.02)

    # ------------------------------------------------------------ gathering
    def _harvest(
        self,
        agent: Agent,
        resource_keys: list[str],
        skill: str,
        item: str = "food",
        base: float = 1.2,
    ) -> float:
        tile = self.world.tile_or_raise(agent.position[0], agent.position[1])
        available = {key: tile.resources.get(key, 0.0) for key in resource_keys}
        best_key = max(available, key=available.get) if available else None
        if not best_key or available[best_key] < 0.15:
            return 0.0
        settlement = self._settlement_of(agent)
        techs = set(settlement.known_techs) if settlement else set(agent.known_techs)
        from .tech import effects_for
        effects = effects_for(techs)
        tool_bonus = min(0.3, agent.inventory.get("tools", 0) * 0.06)
        skill_value = agent.skills.get(skill, 0.1)
        amount = base + skill_value * 3.1 + tool_bonus
        if item == "food":
            amount += effects.get("gather_food", 0.0) * 3
        elif item == "wood":
            amount += effects.get("gather_wood", 0.0) * 3
        amount = min(amount, available[best_key])
        conversion = {"berries": 1.0, "game": 1.15, "fish": 1.25}.get(best_key, 1.0)
        item_amount = amount * conversion
        added = agent.add_item(item, item_amount)
        tile.resources[best_key] = round(available[best_key] - amount, 2)
        if tile.resources[best_key] <= 0:
            del tile.resources[best_key]
        agent.gain_skill(skill, 0.012 + (0.006 if settlement else 0.002))
        if added > 0.1:
            tags = {"food": ["food_source"], "wood": ["wood_source"], "stone": ["stone_source"], "herbs": ["herbs"]}.get(item, [])
            label = {"food": "food", "wood": "wood", "stone": "stone", "herbs": "herbs"}.get(item, item)
            self._memory(
                agent, "survival",
                f"Gathered {added:.1f} {label} at ({tile.x}, {tile.y}).",
                0.32 if added < 3 else 0.42, 0.25,
                location=[tile.x, tile.y], tags=tags + ["gathering"],
                detail={"resource": best_key, "amount": round(added, 2)},
            )
        return added

    def _act_forage(self, agent: Agent, action: dict[str, Any]) -> None:
        amount = self._harvest(agent, ["berries", "game", "fish"], "gathering", "food", base=1.6)
        if amount <= 0:
            # Foraging is uncertain: try a nearby tile next time, but remember
            # this one is exhausted instead of pretending success.
            agent.state = "Searched for food and found the patch exhausted"
            self._memory(agent, "survival", "Returned to a remembered food patch and found it picked clean.", 0.4, -0.25,
                         location=list(agent.position), tags=["failure", "food_source"])
            agent.needs["energy"] = max(0.0, agent.needs["energy"] - 2)
            return
        agent.state = f"Foraged {amount:.1f} food"
        agent.needs["energy"] = max(0.0, agent.needs["energy"] - 1)

    def _act_hunt(self, agent: Agent, action: dict[str, Any]) -> None:
        tile = self.world.tile_or_raise(agent.position[0], agent.position[1])
        rng = random.Random(zlib.crc32(f"hunt:{agent.id}:{self.day}:{tile.x}:{tile.y}".encode()))
        game = tile.resources.get("game", 0.0)
        if game < 0.3:
            agent.state = "The game had moved on"
            self._act_forage(agent, action)
            return
        skill = agent.skills["hunting"]
        amount = min(game, 1.2 + skill * 4.2 + agent.inventory.get("tools", 0) * 0.2)
        tile.resources["game"] = round(game - amount, 2)
        if tile.resources["game"] <= 0:
            del tile.resources["game"]
        food = amount * 1.2
        added = agent.add_item("food", food)
        agent.gain_skill("hunting", 0.018)
        agent.needs["energy"] = max(0.0, agent.needs["energy"] - 4)
        agent.state = f"Hunted {added:.1f} food"
        self._memory(agent, "survival", f"Hunted game at ({tile.x}, {tile.y}) and brought back {added:.1f} food.", 0.45, 0.4,
                     location=[tile.x, tile.y], tags=["hunt", "food_source"], detail={"amount": round(added, 1)})
        injury_chance = max(0.0, 0.07 - skill * 0.05)
        if rng.random() < injury_chance:
            agent.needs["health"] = max(0.0, agent.needs["health"] - rng.uniform(5, 14))
            agent.state = "Was injured while hunting"
            self._memory(agent, "survival", "Was injured while hunting and returned bleeding.", 0.65, -0.7, tags=["injury", "hunt"])
            self.add_event(
                "survival", f"{agent.name} is injured while hunting",
                f"{agent.name} was hurt while hunting near ({tile.x}, {tile.y}).",
                importance=2, participants=[agent.id], location=[tile.x, tile.y],
            )

    def _act_gather_wood(self, agent: Agent, action: dict[str, Any]) -> None:
        amount = self._harvest(agent, ["wood"], "construction", "wood", base=1.8)
        agent.state = f"Gathered {amount:.1f} wood" if amount else "Found no wood here"

    def _act_gather_stone(self, agent: Agent, action: dict[str, Any]) -> None:
        amount = self._harvest(agent, ["stone"], "construction", "stone", base=1.3)
        agent.state = f"Quarried {amount:.1f} stone" if amount else "Found no stone here"

    def _act_gather_herbs(self, agent: Agent, action: dict[str, Any]) -> None:
        amount = self._harvest(agent, ["herbs"], "gathering", "herbs", base=0.8)
        if amount and agent.needs["health"] < 75:
            agent.inventory["herbs"] = max(0.0, agent.inventory.get("herbs", 0) - 1)
            agent.needs["health"] = min(100, agent.needs["health"] + 7)
        agent.state = f"Gathered {amount:.1f} herbs" if amount else "Found no herbs here"

    def _act_craft_tools(self, agent: Agent, action: dict[str, Any]) -> None:
        settlement = self._settlement_of(agent)
        if agent.inventory.get("wood", 0) < 2 or agent.inventory.get("stone", 0) < 1:
            agent.state = "Lacked materials for tools"
            return
        agent.inventory["wood"] = round(agent.inventory["wood"] - 2, 2)
        agent.inventory["stone"] = round(agent.inventory["stone"] - 1, 2)
        quality_bonus = 0
        if settlement and settlement.has_building("workshop") and "metallurgy" in settlement.known_techs:
            quality_bonus = 1
        agent.inventory["tools"] = round(agent.inventory.get("tools", 0) + 1 + quality_bonus, 2)
        agent.gain_skill("crafting", 0.02)
        agent.state = "Crafted tools"
        if agent.inventory.get("tools", 0) >= 3:
            self._memory(agent, "survival", "Crafted a set of tools that will last through the season.", 0.4, 0.3, tags=["craft", "tools"])

    # -------------------------------------------------------------- rest/social
    def _act_rest(self, agent: Agent, action: dict[str, Any]) -> None:
        settlement = self._settlement_of(agent)
        housed = settlement and settlement.housing_capacity() >= settlement.population
        recovery = 36 + (8 if housed else 0) + (5 if self._at_settlement(agent, settlement) else 0)
        agent.needs["energy"] = min(100, agent.needs["energy"] + recovery)
        agent.needs["health"] = min(100, agent.needs["health"] + 1.5)
        agent.state = "Resting" if not housed else "Resting at home"
        if agent.needs["health"] < 35:
            self._memory(agent, "survival", "Rested through an illness.", 0.4, 0.1, tags=["health", "rest"])

    def _act_socialize(self, agent: Agent, action: dict[str, Any]) -> None:
        other = self._target_agent(agent, action, radius=3)
        if not other:
            agent.state = "Looked for company, but no one was near"
            agent.needs["social"] = max(0.0, agent.needs["social"] - 2)
            return
        self._interact(agent, other, strong=True, context="visit")
        agent.state = f"Talking with {other.name}"

    def _act_visit_partner(self, agent: Agent, action: dict[str, Any]) -> None:
        partner = self._target_agent(agent, action, radius=4)
        if not partner:
            agent.state = "Went looking for their partner"
            return
        self._interact(agent, partner, strong=True, context="family")
        if partner.pregnant and agent.inventory.get("food", 0) > 2:
            agent.inventory["food"] = round(agent.inventory["food"] - 1, 2)
            partner.needs["hunger"] = min(100, partner.needs["hunger"] + 22)
            self._memory(agent, "family", f"Brought food to {partner.name} during pregnancy.", 0.55, 0.7, participants=[partner.id], tags=["family", "care"])
        agent.state = f"Spending time with {partner.name}"

    def _act_help_food(self, agent: Agent, action: dict[str, Any]) -> None:
        other = self._target_agent(agent, action, radius=3)
        if not other or agent.inventory.get("food", 0) < 0.9:
            agent.state = "Wanted to help, but had nothing to spare"
            return
        amount = min(2.0, agent.inventory["food"] - 0.5)
        if amount <= 0:
            return
        agent.inventory["food"] = round(agent.inventory["food"] - amount, 2)
        other.add_item("food", amount)
        agent.state = f"Shared food with {other.name}"
        self._record_gift(agent, other, amount)

    def _act_trade(self, agent: Agent, action: dict[str, Any]) -> None:
        other = self._target_agent(agent, action, radius=3)
        if not other:
            agent.state = "Trade partner was not there"
            return
        self._execute_barter(agent, other)

    def _act_court(self, agent: Agent, action: dict[str, Any]) -> None:
        other = self._target_agent(agent, action, radius=3)
        if not other:
            agent.state = "Their intended was nowhere nearby"
            return
        self._court(agent, other)
        agent.state = f"Courting {other.name}"

    # ------------------------------------------------------- settlement work
    def _act_deposit(self, agent: Agent, action: dict[str, Any]) -> None:
        settlement = self._settlement_of(agent)
        if not settlement or not self._at_settlement(agent, settlement, 3):
            agent.state = "Returned to contribute, but the settlement was far"
            return
        deposited = 0.0
        for item, reserve in (("wood", 2.0), ("stone", 1.0), ("food", 3.0), ("herbs", 1.0), ("ore", 1.0)):
            amount = max(0.0, agent.inventory.get(item, 0) - reserve)
            amount = min(amount, settlement.room_for(item))
            if amount <= 0:
                continue
            agent.inventory[item] = round(agent.inventory[item] - amount, 2)
            settlement.storage[item] = round(settlement.storage.get(item, 0) + amount, 2)
            deposited += amount
        if deposited <= 0:
            agent.state = "Had nothing to contribute"
            return
        agent.influence = min(100, agent.influence + 0.3)
        agent.reputation = min(100, agent.reputation + 0.5)
        agent.state = f"Contributed {deposited:.1f} goods to {settlement.name}"
        settlement.stability = min(100, settlement.stability + 0.4)
        if deposited >= 4:
            self._memory(agent, "social", f"Contributed {deposited:.1f} goods to the common stores of {settlement.name}.", 0.5, 0.6,
                         tags=["settlement", "cooperation"], location=list(settlement.position))

    def _act_build(self, agent: Agent, action: dict[str, Any]) -> None:
        settlement = self._settlement_of(agent)
        if not settlement or not self._at_settlement(agent, settlement, 2):
            agent.state = "Could not reach the building site"
            return
        project = next((p for p in settlement.build_queue if p.get("work_done", 0) < p.get("work_required", 1)), None)
        if not project:
            agent.state = "Found no building project underway"
            return
        work = 0.55 + agent.skills["construction"] * 1.6
        if settlement.has_building("workshop"):
            work += 0.25
        project["work_done"] = round(project.get("work_done", 0) + work, 2)
        agent.gain_skill("construction", 0.017)
        agent.state = f"Building {project['name']}"
        agent.needs["energy"] = max(0.0, agent.needs["energy"] - 2.0)
        self._pay_wage(agent, settlement, 0.4)
        if project["work_done"] >= project["work_required"]:
            self._complete_building(settlement, project)

    def _act_farm(self, agent: Agent, action: dict[str, Any]) -> None:
        settlement = self._settlement_of(agent)
        if not settlement or not self._at_settlement(agent, settlement, 3):
            agent.state = "Was too far from the fields"
            return
        farms = settlement.building_count("farm")
        if not farms:
            agent.state = "Found no fields to tend"
            return
        from .tech import effects_for
        effects = effects_for(set(settlement.known_techs))
        tile = self.world.tile_or_raise(settlement.position[0], settlement.position[1])
        season_factor = {"Spring": 1.0, "Summer": 1.15, "Autumn": 0.9, "Winter": 0.22}.get(self.season, 1.0)
        weather_factor = {"Rain": 1.15, "Drought": 0.45, "Storm": 0.7, "Snow": 0.25}.get(self.world.weather, 1.0)
        yield_amount = (
            (0.8 + tile.fertility * 1.9 + agent.skills["farming"] * 2.2)
            * (1 + effects.get("farm_yield", 0.0))
            * season_factor * weather_factor
        )
        if "irrigation" in settlement.known_techs and weather_factor < 0.8:
            yield_amount *= 1.0 + effects.get("drought_resist", 0.0)
        stored = agent.add_item("food", yield_amount)
        settlement.storage["food"] = round(settlement.storage.get("food", 0) + stored, 2)
        agent.inventory["food"] = round(max(0.0, agent.inventory["food"] - stored), 2)
        agent.gain_skill("farming", 0.02)
        agent.needs["energy"] = max(0.0, agent.needs["energy"] - 2.2)
        self._pay_wage(agent, settlement, 0.4)
        agent.state = f"Worked the fields (+{stored:.1f} food to stores)"
        agent.current_goal["progress"] = round(agent.current_goal.get("progress", 0) + 0.01, 3)
        if stored > 1.5:
            self._memory(agent, "social", f"Brought in {stored:.1f} food from the fields of {settlement.name}.", 0.25, 0.35,
                         tags=["farming", "settlement"], location=list(settlement.position))

    def _act_research(self, agent: Agent, action: dict[str, Any]) -> None:
        tech_key = action.get("target", {}).get("tech") or agent.research_target
        settlement = self._settlement_of(agent)
        known = set(settlement.known_techs) if settlement else set(agent.known_techs)
        if not tech_key or tech_key in known:
            agent.research_target = None
            agent.state = "Finished their line of inquiry"
            return
        if not all(p in known for p in TECHS[tech_key]["prereq"]):
            agent.state = "Lacked the knowledge to proceed"
            return
        agent.research_target = tech_key
        rate = 1.5 + agent.skills["research"] * 5.0 + agent.personality["intelligence"] * 3.0 + agent.personality["curiosity"] * 1.5
        from .tech import effects_for
        effects = effects_for(known)
        rate *= 1.0 + effects.get("research", 0.0)
        if settlement:
            if settlement.has_building("archive"):
                rate += 1.0
            if settlement.has_building("workshop"):
                rate += 0.4
            if settlement.has_building("school"):
                rate += 0.8
            if "writing" in settlement.known_techs:
                rate += 0.4
        rate *= 0.9 + self.config.resource_abundance * 0.1
        progress = agent.research_progress.get(tech_key, 0.0) + rate
        agent.research_progress[tech_key] = progress
        agent.gain_skill("research", 0.02)
        agent.needs["energy"] = max(0.0, agent.needs["energy"] - 1.5)
        agent.state = f"Studying {TECHS[tech_key]['name']} ({progress:.0f}/{TECHS[tech_key]['cost']})"
        self._pay_wage(agent, settlement, 0.35)
        if progress >= TECHS[tech_key]["cost"]:
            self._attempt_discovery(agent, tech_key)
        else:
            self._memory(agent, "observation", f"Spent the day studying {TECHS[tech_key]['name']}.", 0.18, 0.1, tags=["research", tech_key]) if progress % 8 < rate else None

    def _act_found_settlement(self, agent: Agent, action: dict[str, Any]) -> None:
        tile = action.get("target", {}).get("tile") or agent.position
        self._found_settlement(agent, tuple(tile))

    def _act_build_shelter(self, agent: Agent, action: dict[str, Any]) -> None:
        if agent.inventory.get("wood", 0) < 4:
            agent.state = "Lacked wood for shelter"
            return
        agent.inventory["wood"] = round(agent.inventory["wood"] - 4, 2)
        agent.shelter_until = self.day + 14
        agent.needs["shelter"] = min(100, agent.needs["shelter"] + 40)
        agent.needs["energy"] = max(0.0, agent.needs["energy"] - 3)
        agent.gain_skill("construction", 0.02)
        agent.state = "Built a lean-to shelter"
        agent.stats["shelters_built"] = agent.stats.get("shelters_built", 0) + 1
        self._memory(agent, "survival", "Built a lean-to against the weather.", 0.5, 0.4, tags=["shelter", "construction"])

    def _act_explore(self, agent: Agent, action: dict[str, Any]) -> None:
        agent.gain_skill("exploration", 0.03)
        agent.state = "Surveyed unfamiliar land"
        self._memory(agent, "observation", f"Explored the country around ({agent.position[0]}, {agent.position[1]}).", 0.35, 0.2,
                     tags=["exploration"], location=list(agent.position))
        # Remember useful visible resources within a short radius.
        for item, tag in (("food", "food_source"), ("wood", "wood_source"), ("stone", "stone_source")):
            found = self.world.find_resource(tuple(agent.position), item, max_radius=4)
            if found:
                self._memory(agent, "observation", f"Noted a source of {item} near ({found.x}, {found.y}) while exploring.", 0.4, 0.2,
                             location=[found.x, found.y], tags=[tag, "discovery"])
        agent.current_goal["progress"] = round(agent.current_goal.get("progress", 0) + 0.02, 3)

    def _act_migrate(self, agent: Agent, action: dict[str, Any]) -> None:
        target_id = action.get("target", {}).get("settlement_id")
        if target_id and target_id in self.settlements:
            settlement = self.settlements[target_id]
            if not settlement.ruins and abs(agent.position[0] - settlement.position[0]) <= 3 and abs(agent.position[1] - settlement.position[1]) <= 3:
                joined = self._join_settlement(agent, settlement, reason="migrated")
                if joined:
                    return
        agent.home_tile = list(agent.position)
        agent.state = "Settled in a new place"
        self._memory(agent, "survival", f"Made a new home in the wild at ({agent.position[0]}, {agent.position[1]}).", 0.6, 0.2,
                     tags=["migration", "home"])

    def _act_flee(self, agent: Agent, action: dict[str, Any]) -> None:
        agent.needs["safety"] = min(100, agent.needs["safety"] + 15)
        agent.state = "Retreated from danger"
        self._memory(agent, "survival", "Retreated from a threatening situation.", 0.4, -0.2, tags=["danger", "flee"])

    def _act_confront(self, agent: Agent, action: dict[str, Any]) -> None:
        other = self._target_agent(agent, action, radius=2)
        if not other:
            agent.state = "Their rival was gone"
            return
        self._conflict(agent, other, lethal_intent=False)

    def _act_steal(self, agent: Agent, action: dict[str, Any]) -> None:
        other = self._target_agent(agent, action, radius=2)
        if not other or other.inventory.get("food", 0) < 0.5:
            agent.state = "Found nothing to take"
            return
        rng = random.Random(zlib.crc32(f"steal:{agent.id}:{other.id}:{self.day}".encode()))
        caught = rng.random() < 0.55 + other.personality["intelligence"] * 0.25 - agent.skills["exploration"] * 0.1
        amount = min(2.0, other.inventory.get("food", 0))
        other.inventory["food"] = round(other.inventory["food"] - amount, 2)
        agent.add_item("food", amount)
        agent.needs["hunger"] = min(100, agent.needs["hunger"] + 30)
        self.conflicts += 1
        rel = agent.relation(other.id, self.day)
        rel.affinity -= 20
        rel.trust -= 35
        rel.conflicts += 1
        rel.add_history(self.day, f"{agent.name} took food", -0.9)
        rel_other = other.relation(agent.id, self.day)
        rel_other.affinity -= 35
        rel_other.trust -= 55
        rel_other.conflicts += 1
        rel_other.add_history(self.day, f"{agent.name} stole food", -1.0)
        other.needs["safety"] = max(0.0, other.needs["safety"] - 20)
        settlement = self._settlement_of(agent)
        if settlement and self._at_settlement(agent, settlement, 4):
            settlement.stats["theft"] = self.day
        self._memory(agent, "betrayal", f"Took {amount:.1f} food from {other.name}.", 0.7, -0.2,
                     participants=[other.id], tags=["theft", "conflict"])
        self._memory(other, "betrayal", f"{agent.name} took {amount:.1f} food without asking.", 0.9, -0.9,
                     participants=[agent.id], tags=["theft", "betrayal"])
        if caught:
            agent.reputation = max(0.0, agent.reputation - 12)
            self.add_event(
                "conflict", f"{agent.name} is caught stealing from {other.name}",
                f"{agent.name} took food from {other.name} and was seen. Hunger had driven them to it; trust will not recover quickly.",
                importance=3, participants=[agent.id, other.id], location=list(agent.position),
                consequences=[f"Relationship became hostile", "Settlement recorded a theft"],
                related={"act": "theft"},
            )
            agent.state = f"Was caught stealing from {other.name}"
        else:
            agent.state = f"Took food from {other.name} unnoticed"
        if other.personality["aggressiveness"] > 0.6 and other.needs["safety"] > 20:
            self._conflict(other, agent, lethal_intent=False)

    def _act_market(self, agent: Agent, action: dict[str, Any]) -> None:
        settlement = self._settlement_of(agent)
        if not settlement or not self._at_settlement(agent, settlement, 2) or not settlement.has_building("market"):
            agent.state = "No market was within reach"
            return
        prices = settlement.market_prices or {}
        bought = 0.0
        if agent.needs["hunger"] < 70 and settlement.storage.get("food", 0) >= 1:
            price = prices.get("food", 2.0)
            if agent.inventory.get("currency", 0) >= price:
                agent.inventory["currency"] = round(agent.inventory["currency"] - price, 2)
                settlement.storage["currency"] = round(settlement.storage.get("currency", 0) + price * 0.92, 2)
                settlement.storage["food"] = round(settlement.storage["food"] - 1, 2)
                agent.inventory["food"] = round(agent.inventory.get("food", 0) + 1, 2)
                agent.needs["hunger"] = min(100, agent.needs["hunger"] + 20)
                bought = 1
                self._record_trade(agent.id, settlement.id, "market_buy", {"food": 1}, price, settlement)
        for item in ("wood", "stone", "herbs"):
            surplus = agent.inventory.get(item, 0) - 3
            if surplus >= 1 and settlement.has_room_for(item, 1):
                price = prices.get(item, 2.0)
                payment = round(price * 0.85, 2)
                if settlement.storage.get("currency", 0) < payment:
                    continue
                settlement.storage[item] = round(settlement.storage.get(item, 0) + 1, 2)
                agent.inventory[item] = round(agent.inventory[item] - 1, 2)
                agent.inventory["currency"] = round(agent.inventory.get("currency", 0) + payment, 2)
                settlement.storage["currency"] = round(settlement.storage.get("currency", 0) - payment, 2)
                self._record_trade(settlement.id, agent.id, "market_sell", {item: 1}, price, settlement)
                if bought == 0:
                    bought = -1
        agent.state = "Traded at the settlement market" if bought else "Found no advantageous trade at the market"

    def _act_wait(self, agent: Agent, action: dict[str, Any]) -> None:
        agent.state = "Watching the world"
        agent.needs["energy"] = min(100, agent.needs["energy"] + 8)
