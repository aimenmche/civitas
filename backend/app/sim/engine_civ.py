"""Settlement, governance, economy, technology and cultural evolution."""
from __future__ import annotations

import random
import zlib
from typing import Any

from .agent import Agent, choose_occupation
from .constants import BUILDINGS, SEASON_GROWTH, TECHS, WEATHER_GROWTH
from .culture import (
    Language, add_tradition, borrow_words, coin_word, create_culture, create_language,
    drift_language,
)
from .economy import gini, stage_for, update_prices
from .names import language_name, settlement_name
from .politics import (
    choose_leader, consider_laws, evaluate_governance, refresh_government_legitimacy,
    update_factions,
)
from .settlement import (
    MATERIAL_GOODS, PERISHABLE_GOODS, WATER_GOODS, Settlement, blank_government, plan_building,
)
from .tech import current_era, discovery_conditions_met, effects_for


class CivilizationMixin:
    # ---------------------------------------------------------- settlement phase
    def _settlement_phase(self) -> None:
        for settlement in list(self.settlements.values()):
            if settlement.ruins:
                continue
            # Remove the dead from the roster.
            settlement.member_ids = [aid for aid in settlement.member_ids if aid in self.agents and self.agents[aid].alive]
            for aid in list(settlement.occupation):
                if aid not in settlement.member_ids:
                    settlement.occupation.pop(aid, None)
            if settlement.population == 0:
                self._abandon_settlement(settlement)
                continue
            settlement.population_peak = max(settlement.population_peak, settlement.population)
            self._settlement_production(settlement)
            self._settlement_tech_diffusion(settlement)
            self._settlement_prices(settlement)
            self._settlement_taxes(settlement)
            self._settlement_plan_building(settlement)
            self._settlement_construction_progress(settlement)
            self._settlement_assign_occupations(settlement)
            self._claim_territory(settlement)
            self._settlement_stats(settlement)
            self._settlement_take_in_newcomers(settlement)
            settlement.stats["meals_today"] = 0
            if settlement.population == 0:
                self._abandon_settlement(settlement)

    def _settlement_production(self, settlement: Settlement) -> None:
        members = [self.agents[aid] for aid in settlement.member_ids if aid in self.agents and self.agents[aid].alive]
        if not members:
            return
        farms = settlement.building_count("farm")
        tile = self.world.tile_or_raise(settlement.position[0], settlement.position[1])
        effects = effects_for(set(settlement.known_techs))
        season_factor = {"Spring": 1.05, "Summer": 1.15, "Autumn": 0.85, "Winter": 0.18}.get(self.season, 1.0)
        weather_factor = WEATHER_GROWTH.get(self.world.weather, 1.0)
        farmers = sorted(members, key=lambda a: a.skills["farming"], reverse=True)[: max(1, min(len(members), farms * 2))]
        farming_skill = sum(a.skills["farming"] for a in farmers) / max(1, len(farmers))
        production = 0.0
        if farms:
            production = farms * (0.8 + tile.fertility * 2.4 + farming_skill * 2.0) * season_factor * weather_factor
            production *= 1.0 + effects.get("farm_yield", 0.0)
            if self.world.weather == "Drought":
                production *= 1.0 + effects.get("drought_resist", 0.0)
            if self.season == "Winter":
                production *= 1.0 + effects.get("winter_food", 0.0)
            # No one working the fields means the weeds win.
            if farms and not any(a.skills["farming"] > 0.12 for a in members):
                production *= 0.45
        # Foraging residents also bring something home even without farms.
        production += len(members) * 0.10 * (1.0 + tile.fertility * 0.2) * season_factor
        if settlement.stats.get("epidemic_until", 0) >= self.day:
            production *= 0.8
        storage_cap = settlement.storage_capacity()
        # Water is not bulk cargo like wood or grain: it is a small daily
        # reserve. It used to fill the shared storage pool (the well produced
        # ~49/day), which left no room for food — a settlement with farms
        # producing 30 food/day starved to death with its store full of water.
        room = max(0.0, storage_cap - settlement.stored_perishables())
        new_food = min(room, production)
        settlement.storage["food"] = round(settlement.storage.get("food", 0.0) + max(0.0, new_food), 2)
        settlement.food_production = round(production, 1)
        # Spoilage is reduced by pottery, granaries, and food preservation.
        keep = min(0.8, effects.get("food_keep", 0.0) + (0.1 if settlement.has_building("granary") else 0.0))
        if settlement.storage.get("food", 0) > 0:
            spoil = settlement.storage["food"] * (0.015 * (1.0 - keep))
            settlement.storage["food"] = round(max(0.0, settlement.storage["food"] - spoil), 2)
        # Wells and aqueducts provide stored fresh water, held to a small
        # reserve so it can never crowd out the harvest.
        if settlement.has_building("well") or settlement.has_building("aqueduct"):
            water_rate = 2.5 * settlement.population * (1.4 if settlement.has_building("aqueduct") else 0.7)
            water_cap = settlement.water_capacity()
            settlement.storage["water"] = round(
                min(water_cap, settlement.storage.get("water", 0) + water_rate), 2
            )
        # Clamp the grain store and the materials yard independently. The old
        # single-pool clamp cut wood and stone first, so a full granary erased
        # every settlement's ability to build.
        for keys, cap, cut_order in (
            (PERISHABLE_GOODS, storage_cap, ("herbs", "food")),
            (WATER_GOODS, settlement.water_capacity(), ("water",)),
            (MATERIAL_GOODS, settlement.material_capacity(), ("ore", "stone", "wood", "tools")),
        ):
            total = sum(float(settlement.storage.get(k, 0.0)) for k in keys)
            overflow = total - cap
            if overflow <= 0:
                continue
            for key in cut_order:
                if overflow <= 0:
                    break
                cut = min(float(settlement.storage.get(key, 0.0)), overflow)
                settlement.storage[key] = round(float(settlement.storage.get(key, 0.0)) - cut, 2)
                overflow -= cut
        settlement.food_consumption = round(settlement.stats.get("meals_today", 0) + settlement.population * 0.12, 1)
        self._maybe_adopt_currency(settlement)

    def _settlement_tech_diffusion(self, settlement: Settlement) -> None:
        """Knowledge spreads between communities; it does not stay where it began.

        Technologies used to be tracked in a global ``run_techs`` pool that
        blocked every *other* settlement from ever researching them, while
        nothing propagated them either. One tiny community discovered
        agriculture and writing, and the large settlements around it stayed in
        the Stone Age and starved with no farms. Real knowledge travels with
        people: traders, in-laws, migrants and letters. Model that as a small
        daily chance per (settlement, technology) pair, higher for neighbours,
        for communities that trade, and for those that can write.
        """
        if settlement.ruins:
            return
        known = set(settlement.known_techs)
        interest: dict[str, float] = {}
        for other in self.settlements.values():
            if other.id == settlement.id or other.ruins or not other.known_techs:
                continue
            relations = settlement.diplomacy.get(other.id) or {}
            status = relations.get("status", "neutral")
            if status in ("war", "hostile"):
                continue
            dx = other.position[0] - settlement.position[0]
            dy = other.position[1] - settlement.position[1]
            distance = (dx * dx + dy * dy) ** 0.5
            if distance <= 8:
                reach = 0.09
            elif distance <= 16:
                reach = 0.045
            elif distance <= 30:
                reach = 0.02
            else:
                reach = 0.006
            if settlement.has_building("market") or other.has_building("market"):
                reach *= 1.6
            if "writing" in known or "writing" in other.known_techs:
                reach *= 1.8
            if status == "trade" or relations.get("trust", 0) > 20:
                reach *= 1.5
            for tech in other.known_techs:
                if tech in known:
                    continue
                interest[tech] = max(interest.get(tech, 0.0), reach)
        if not interest:
            return
        rng = random.Random(zlib.crc32(f"diffuse:{settlement.id}:{self.day}".encode()))
        adopted = sorted(tech for tech, chance in interest.items() if rng.random() < chance)
        if not adopted:
            return
        for tech in adopted:
            settlement.known_techs.append(tech)
            self.run_techs.add(tech)
        for aid in settlement.member_ids:
            member = self.agents.get(aid)
            if not member:
                continue
            for tech in adopted:
                if tech not in member.known_techs:
                    member.known_techs.append(tech)
        for tech in adopted:
            spec = TECHS[tech]
            self.add_event(
                "technology", f"{spec['name']} reaches {settlement.name}",
                f"Travellers and kin carried knowledge of {spec['name']} into {settlement.name}. "
                f"{spec['effect']} The community did not have to rediscover it alone.",
                importance=3, location=list(settlement.position), location_name=settlement.name,
                related={"tech": tech, "settlement_id": settlement.id},
            )
            if settlement.leader_id and settlement.leader_id in self.agents:
                self._memory(
                    self.agents[settlement.leader_id], "observation",
                    f"Learned of {spec['name']} from visitors to {settlement.name}.",
                    0.5, 0.4, tags=["research", "diffusion", tech],
                )

    def _settlement_prices(self, settlement: Settlement) -> None:
        rng = random.Random(zlib.crc32(f"prices:{settlement.id}:{self.day}".encode()))
        update_prices(settlement, self.day, rng)
        settlement.economic_stage = stage_for(settlement)

    def _settlement_taxes(self, settlement: Settlement) -> None:
        if not settlement.uses_currency:
            settlement.tax_revenue = max(0.0, settlement.tax_revenue * 0.995)
            return
        gov = settlement.government or {}
        rate = float(gov.get("tax_rate", 0.05))
        if rate <= 0:
            return
        collected = 0.0
        for aid in settlement.member_ids:
            agent = self.agents.get(aid)
            if not agent or not agent.alive:
                continue
            balance = agent.inventory.get("currency", 0)
            if balance <= 0.2:
                continue
            tax = min(balance * rate, 2.0)
            agent.inventory["currency"] = round(balance - tax, 2)
            collected += tax
        if collected > 0:
            settlement.storage["currency"] = round(settlement.storage.get("currency", 0) + collected, 2)
            settlement.tax_revenue = round(settlement.tax_revenue + collected, 2)

    def _settlement_plan_building(self, settlement: Settlement) -> None:
        if settlement.build_queue:
            return
        if self.day - settlement.founded_day < 1:
            return
        rng = random.Random(zlib.crc32(f"build:{settlement.id}:{self.day}".encode()))
        known = set(settlement.known_techs)
        candidate = plan_building(settlement, known, rng, self.day)
        if not candidate:
            return
        spec = BUILDINGS[candidate]
        if candidate in ("house",) and "stone_house" in settlement.known_techs and settlement.storage.get("stone", 0) >= 12:
            candidate = "stone_house"
            spec = BUILDINGS[candidate]
        if not all(settlement.storage.get(item, 0) >= amount for item, amount in spec["cost"].items()):
            return
        for item, amount in spec["cost"].items():
            settlement.storage[item] = round(settlement.storage.get(item, 0) - amount, 2)
        project = {
            "id": f"{settlement.id}_build{len(settlement.build_queue) + len(settlement.buildings) + 1}",
            "type": candidate, "name": spec["name"],
            "work_required": spec["build_days"] * 2.2, "work_done": 0.0,
            "started_day": self.day, "cost": spec["cost"],
        }
        settlement.build_queue.append(project)
        self.add_event(
            "settlement", f"{settlement.name} begins a {spec['name'].lower()}",
            f"The community committed {', '.join(f'{v:g} {k}' for k, v in spec['cost'].items())} to build a {spec['name'].lower()}. "
            f"Construction will need {spec['build_days']} days of labor.",
            importance=2, location=list(settlement.position), location_name=settlement.name,
            related={"settlement_id": settlement.id, "building": candidate},
        )
        if settlement.leader_id and settlement.leader_id in self.agents:
            leader = self.agents[settlement.leader_id]
            self._memory(leader, "social", f"Organized the building of a {spec['name'].lower()} in {settlement.name}.", 0.4, 0.4,
                         tags=["settlement", "building"])

    def _settlement_assign_occupations(self, settlement: Settlement) -> None:
        """People take up work that matches the skills they actually have.

        Occupations used to be chosen once at birth, so every child grew into a
        permanent "Wanderer" even after decades of farming or building. The
        settlement roster, and the Farmer/Builder bonuses in decision-making,
        therefore described nobody's real life.
        """
        if self.day % 10 != 0:
            return
        for aid in settlement.member_ids:
            member = self.agents.get(aid)
            if not member or not member.alive:
                continue
            if member.age_years < 16:
                occupation = "Child"
            elif member.id == settlement.leader_id:
                occupation = "Leader"
            else:
                occupation = choose_occupation(member)
            member.occupation = occupation
            settlement.occupation[aid] = occupation

    def _settlement_construction_progress(self, settlement: Settlement) -> None:
        if not settlement.build_queue:
            return
        project = settlement.build_queue[0]
        members = [self.agents[aid] for aid in settlement.member_ids if aid in self.agents and self.agents[aid].alive]
        passive = 0.12
        for member in members:
            if member.skills["construction"] > 0.25 and self._at_settlement(member, settlement, 3):
                passive += 0.18 + member.skills["construction"] * 0.2
        project["work_done"] = round(project.get("work_done", 0) + passive, 2)
        if project["work_done"] >= project["work_required"]:
            self._complete_building(settlement, project)

    def _complete_building(self, settlement: Settlement, project: dict[str, Any]) -> None:
        if project not in settlement.build_queue:
            return
        settlement.build_queue.remove(project)
        building = settlement.add_building(project["type"], self.day)
        if not building:
            return
        self.add_event(
            "settlement", f"{settlement.name} completes its {building['name'].lower()}",
            f"After {self.day - project.get('started_day', self.day)} days, the {building['name'].lower()} was completed. "
            f"{BUILDINGS[project['type']]['effect']}",
            importance=3, location=list(settlement.position), location_name=settlement.name,
            consequences=[BUILDINGS[project["type"]]["effect"]],
            related={"settlement_id": settlement.id, "building": project["type"]},
        )
        if settlement.leader_id and settlement.leader_id in self.agents:
            leader = self.agents[settlement.leader_id]
            leader.influence = min(100, leader.influence + 2.0)
            leader.reputation = min(100, leader.reputation + 1.5)
        if project["type"] == "shrine":
            self._culture_from_event(settlement, "shrine")
        elif project["type"] == "farm":
            self._culture_from_event(settlement, "first_farm")
        elif project["type"] == "market":
            settlement.stats["market_established_day"] = self.day
            self._culture_from_event(settlement, "market")

    def _maybe_adopt_currency(self, settlement: Settlement) -> None:
        if self.config.no_currency or settlement.uses_currency:
            return
        if "currency" not in settlement.known_techs or not settlement.has_building("market"):
            return
        settlement.uses_currency = True
        settlement.economic_stage = max(3, settlement.economic_stage)
        members = [self.agents[aid] for aid in settlement.member_ids if aid in self.agents and self.agents[aid].alive]
        coin_name = f"{settlement.name} marks"
        settlement.stats["currency_name"] = coin_name
        # A new monetary convention needs a supply of tokens. This is a
        # political act by the settlement, not an automatic game rule.
        minted_to_members = 0.0
        for member in members:
            member.inventory["currency"] = round(member.inventory.get("currency", 0) + 5.0, 2)
            minted_to_members += 5.0
        treasury = 6.0 + len(members) * 1.5
        settlement.storage["currency"] = round(settlement.storage.get("currency", 0) + treasury, 2)
        self.add_event(
            "economy", f"Currency is adopted in {settlement.name}",
            f"{settlement.name} adopted {coin_name} as a common medium of exchange. "
            f"{minted_to_members:.0f} marks were issued to {len(members)} residents and {treasury:.0f} to the public treasury. "
            "Prices, wages and taxes can now be expressed in coin.",
            importance=5, participants=[m.id for m in members], location=list(settlement.position),
            location_name=settlement.name,
            consequences=[
                f"Economic stage advanced to {settlement.economic_stage}",
                "Wealth can now be accumulated as currency",
                "Wages and taxes are possible",
            ],
            related={"settlement_id": settlement.id, "currency": coin_name, "tech": "currency"},
        )
        for member in members:
            self._memory(member, "trade", f"Adopted {coin_name} as common currency in {settlement.name}.", 0.65, 0.5,
                         participants=[], tags=["economy", "currency"], location=list(settlement.position))

    def _claim_territory(self, settlement: Settlement) -> None:
        radius = min(6, 2 + settlement.population // 10 + len(settlement.buildings) // 7)
        settlement.territory_radius = radius
        for ty in range(settlement.position[1] - radius, settlement.position[1] + radius + 1):
            for tx in range(settlement.position[0] - radius, settlement.position[0] + radius + 1):
                tile = self.world.tile(tx, ty)
                if not tile or not tile.passable:
                    continue
                if self.distance(tx, ty, settlement.position[0], settlement.position[1]) > radius:
                    continue
                if tile.owner is None or tile.owner == settlement.id:
                    tile.owner = settlement.id

    def _settlement_stats(self, settlement: Settlement) -> None:
        members = [self.agents[aid] for aid in settlement.member_ids if aid in self.agents and self.agents[aid].alive]
        if not members:
            return
        avg_happiness = sum(m.happiness() for m in members) / len(members)
        food = settlement.storage.get("food", 0)
        food_need = settlement.population * 1.1
        food_security = min(1.0, food / max(1.0, food_need))
        palisade = 10 if settlement.has_building("palisade") else 0
        legitimacy = float(settlement.government.get("legitimacy", 55))
        laws_bonus = sum(float(law.get("effects", {}).get("stability", 0)) for law in settlement.laws) * 0.6
        war_penalty = 10 if settlement.stats.get("at_war_with") else 0
        epidemic_penalty = 12 if settlement.stats.get("epidemic_until", 0) >= self.day else 0
        prosperity = 0.0
        if settlement.economic_stage >= 2:
            prosperity = min(6, settlement.trade_volume * 0.1)
        wealth = [m.wealth() for m in members]
        inequality = gini(wealth)
        settlement.happiness = round(max(0.0, min(100.0, avg_happiness + prosperity - (0 if food_security > 0.5 else 18))), 1)
        settlement.safety = round(max(0.0, min(100.0, 55 + palisade + legitimacy * 0.15 - war_penalty - epidemic_penalty - self._local_threat(settlement) * 0.4)), 1)
        settlement.stability = round(max(
            0.0, min(100.0, avg_happiness * 0.38 + legitimacy * 0.22 + food_security * 18 + laws_bonus + palisade * 0.2
                 - inequality * 16 - war_penalty - epidemic_penalty)
        ), 1)
        settlement.food_consumption = round(settlement.stats.get("meals_today", 0) + settlement.population * 0.1, 1)

    def _local_threat(self, settlement: Settlement) -> float:
        threat = 0.0
        for other in self.settlements.values():
            if other.id == settlement.id or other.ruins:
                continue
            d = self.distance(settlement.position[0], settlement.position[1], other.position[0], other.position[1])
            if d <= 12:
                status = settlement.diplomacy.get(other.id, {}).get("status", "neutral")
                if status == "war":
                    threat += 22
                elif status == "hostile":
                    threat += 10
        return threat

    def _settlement_take_in_newcomers(self, settlement: Settlement) -> None:
        if settlement.population >= settlement.housing_capacity() + 2:
            return
        if settlement.storage.get("food", 0) < settlement.population * 0.45:
            return
        rng = random.Random(zlib.crc32(f"join:{settlement.id}:{self.day}".encode()))
        candidates = [
            a for a in self.alive_agents()
            if a.settlement_id is None and a.age >= 12
            and abs(a.position[0] - settlement.position[0]) <= 4
            and abs(a.position[1] - settlement.position[1]) <= 4
        ]
        for agent in candidates:
            if rng.random() > 0.35:
                continue
            self._join_settlement(agent, settlement, reason="drawn by the safety of its stores")

    def _abandon_settlement(self, settlement: Settlement) -> None:
        if settlement.ruins:
            return
        settlement.ruins = True
        settlement.abandoned_day = self.day
        for aid in list(settlement.member_ids):
            agent = self.agents.get(aid)
            if agent and agent.alive:
                agent.settlement_id = None
        settlement.member_ids = []
        settlement.leader_id = None
        settlement.build_queue = []
        self.add_event(
            "settlement", f"{settlement.name} is abandoned",
            f"The last residents left {settlement.name} after {self.day - settlement.founded_day} days. "
            f"Its buildings remain as ruins; its farms and stores are empty.",
            importance=4, location=list(settlement.position), location_name=settlement.name,
            consequences=["Settlement marked as ruins"],
            related={"settlement_id": settlement.id},
        )

    # --------------------------------------------------------------- founding
    def find_founding_site(self, agent: Agent) -> dict[str, Any] | None:
        if agent.settlement_id:
            return None
        if agent.inventory.get("food", 0) < 4 or agent.inventory.get("wood", 0) < 5:
            return None
        active = [s for s in self.settlements.values() if not s.ruins]
        if len(active) >= max(2, len(self.alive_agents()) // 7):
            return None
        candidates: list[tuple[float, Any, int]] = []
        for dy in range(-5, 6):
            for dx in range(-5, 6):
                tile = self.world.tile(agent.position[0] + dx, agent.position[1] + dy)
                if tile is None or not tile.passable or not tile.buildable:
                    continue
                if tile.terrain in ("coast", "river", "lake", "ocean", "deep_ocean"):
                    continue
                dist = self.distance(agent.position[0], agent.position[1], tile.x, tile.y)
                if dist > 5:
                    continue
                if tile.water < 0.5 or tile.fertility < 0.3:
                    continue
                if any(self.distance(tile.x, tile.y, s.position[0], s.position[1]) < 7 for s in active):
                    continue
                score = tile.fertility * 2 + tile.water * 1.3 - dist * 0.08
                candidates.append((score, tile, dist))
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        score, tile, dist = candidates[0]
        return {
            "tile": [tile.x, tile.y],
            "distance": dist,
            "terrain": tile.terrain,
            "fertility": round(tile.fertility, 2),
            "water": round(tile.water, 2),
            "score": round(score, 2),
        }

    def _found_settlement(self, agent: Agent, tile_coords: tuple[int, int]) -> bool:
        if agent.settlement_id:
            return False
        tile = self.world.tile(tile_coords[0], tile_coords[1])
        if not tile or not tile.passable or tile.water < 0.45:
            agent.state = "The chosen site lacked water"
            return False
        if agent.inventory.get("food", 0) < 4 or agent.inventory.get("wood", 0) < 5:
            agent.state = "Lacked the provisions to found a settlement"
            return False
        active = [s for s in self.settlements.values() if not s.ruins]
        if any(self.distance(tile.x, tile.y, s.position[0], s.position[1]) < 6 for s in active):
            agent.state = "The site was too close to an existing settlement"
            return False
        used_names = {s.name for s in self.settlements.values()}
        rng = random.Random(zlib.crc32(f"found:{agent.id}:{self.day}".encode()))
        name = settlement_name(rng, used_names, tile.terrain)
        agent.inventory["food"] = round(agent.inventory["food"] - 4, 2)
        agent.inventory["wood"] = round(agent.inventory["wood"] - 5, 2)
        settlement_id = self._next_settlement_id()
        culture = create_culture(zlib.crc32(f"culture:{settlement_id}".encode()) % 10**9, settlement_id, agent.personality, self.day)
        self.cultures[culture.id] = culture
        base_language = next((self.languages[lid] for lid in agent.known_languages if lid in self.languages), None)
        lang_seed = zlib.crc32(f"settlement-lang:{settlement_id}".encode())
        language = create_language(lang_seed, settlement_id, self.day, origin=base_language.name if base_language else "")
        if base_language:
            language.lexicon = dict(base_language.lexicon)
            used_words = set(language.lexicon.values())
            for concept in rng.sample(sorted(language.lexicon), k=min(4, len(language.lexicon))):
                language.lexicon[concept] = coin_word(rng, used_words)
            language.origins = [base_language.name]
        self.languages[language.id] = language
        government = blank_government(agent.id, self.day)
        if self.config.no_leader:
            government.update({
                "system": "assembly", "label": "Leaderless Assembly",
                "leader_id": None, "legitimacy": 52.0,
                "members": [agent.id],
            })
        settlement = Settlement(
            id=settlement_id, name=name, position=[tile.x, tile.y],
            founded_day=self.day, founder_id=agent.id,
            leader_id=None if self.config.no_leader else agent.id,
            member_ids=[agent.id], storage={"food": 2.0, "water": 1.0, "wood": 1.0, "stone": 0.0, "tools": 0.0, "currency": 0.0},
            culture_id=culture.id, language_id=language.id,
            known_techs=sorted(set(agent.known_techs)),
            capital_tile=[tile.x, tile.y],
            government=government,
        )
        settlement.add_building("shelter", self.day)
        settlement.happiness = agent.happiness()
        settlement.stability = 62.0
        settlement.safety = 58.0
        self.settlements[settlement.id] = settlement
        agent.settlement_id = settlement.id
        agent.home_tile = [tile.x, tile.y]
        agent.occupation = "Leader" if not self.config.no_leader else "Founder"
        agent.founder_of = settlement.id
        agent.influence = min(100, agent.influence + 18)
        agent.reputation = min(100, agent.reputation + 12)
        agent.known_languages.append(language.id) if language.id not in agent.known_languages else None
        agent.personal_vocabulary.update(language.lexicon)
        settlement.occupation[agent.id] = agent.occupation
        settlement.stats["founded_fertility"] = tile.fertility
        self._claim_territory(settlement)
        for other in self.settlements.values():
            if other.id == settlement.id or other.ruins:
                continue
            settlement.diplomacy[other.id] = {"status": "neutral", "trust": 0.0, "since_day": self.day}
            other.diplomacy[settlement.id] = {"status": "neutral", "trust": 0.0, "since_day": self.day}
        self.add_event(
            "settlement", f"{name} is founded",
            f"{agent.name} founded {name} at ({tile.x}, {tile.y}) on {tile.terrain.replace('_', ' ')} land. "
            f"Fertility {tile.fertility:.2f}, water access {tile.water:.2f}. The founder contributed 4 food and 5 wood.",
            importance=5, participants=[agent.id], location=[tile.x, tile.y], location_name=name,
            consequences=[
                "A new settlement exists",
                f"Government: {settlement.gov_label()}",
                f"Language: {language.name}",
                f"Culture: {culture.name}",
            ],
            related={"settlement_id": settlement.id, "culture_id": culture.id, "language_id": language.id},
        )
        self._memory(agent, "social", f"Founded the settlement of {name}.", 1.0, 0.9,
                     location=[tile.x, tile.y], tags=["settlement", "founding"], detail={"settlement_id": settlement.id})
        add_tradition(
            culture, self.day, "Founding Day",
            f"Each year the people of {name} remember {agent.name}'s first fire on this ground.",
            "communal", f"Founded by {agent.name}",
        )
        # Kin and close companions at the site may join, but do not teleport.
        for other in self.alive_agents():
            if other.id == agent.id:
                continue
            if abs(other.position[0] - tile.x) <= 3 and abs(other.position[1] - tile.y) <= 3:
                rel = agent.relationships.get(other.id)
                is_child = other.id in agent.child_ids
                if is_child or (rel and rel.affinity > 30) or other.partner_id == agent.id:
                    self._join_settlement(other, settlement, reason="joined the founder")
        return True

    def _join_settlement(self, agent: Agent, settlement: Settlement, reason: str = "joined") -> bool:
        if settlement.ruins or agent.settlement_id == settlement.id:
            return False
        if agent.settlement_id:
            self._leave_settlement(agent, reason=f"left to {settlement.name}")
        settlement.member_ids.append(agent.id)
        agent.settlement_id = settlement.id
        agent.home_tile = list(settlement.position)
        agent.occupation = agent.occupation if agent.occupation != "Wanderer" else "Citizen"
        settlement.occupation[agent.id] = agent.occupation
        contributed: dict[str, float] = {}
        for item in ("food", "wood", "stone"):
            amount = agent.inventory.get(item, 0) * 0.25
            if amount > 0 and settlement.has_room_for(item, amount):
                agent.inventory[item] = round(agent.inventory[item] - amount, 2)
                settlement.storage[item] = round(settlement.storage.get(item, 0) + amount, 2)
                contributed[item] = round(amount, 1)
        language = self.languages.get(settlement.language_id)
        if language:
            if language.id not in agent.known_languages:
                agent.known_languages.append(language.id)
            agent.personal_vocabulary.update(language.lexicon)
            language.speakers = max(language.speakers, settlement.population)
        new_techs = [t for t in agent.known_techs if t not in settlement.known_techs]
        for tech in new_techs:
            settlement.known_techs.append(tech)
        for aid in settlement.member_ids:
            member = self.agents.get(aid)
            if member:
                for tech in new_techs:
                    if tech not in member.known_techs:
                        member.known_techs.append(tech)
        if agent.family_id and agent.family_id in self.families:
            self.families[agent.family_id]["home_settlement_id"] = settlement.id
        agent.needs["shelter"] = min(100, agent.needs["shelter"] + 25)
        agent.influence = min(100, agent.influence + 1.0)
        settlement.stability = min(100, settlement.stability + 1)
        self._memory(agent, "social", f"Joined {settlement.name}; {reason}.", 0.65, 0.5,
                     location=list(settlement.position), tags=["settlement", "membership"])
        self._memory(agent, "social", f"Contributed {sum(contributed.values()):.1f} goods to the stores of {settlement.name}.", 0.35, 0.4,
                     tags=["settlement", "cooperation"]) if contributed else None
        self.add_event(
            "settlement", f"{agent.name} joins {settlement.name}",
            f"{agent.name} became a resident of {settlement.name}; {reason}. "
            + (f"Contributed {', '.join(f'{v:g} {k}' for k, v in contributed.items())}." if contributed else ""),
            importance=2 if reason == "joined" else 3,
            participants=[agent.id], location=list(settlement.position), location_name=settlement.name,
            related={"settlement_id": settlement.id, "new_techs": new_techs},
        )
        if new_techs:
            self.add_event(
                "technology", f"New knowledge reaches {settlement.name}",
                f"{agent.name} brought knowledge of {', '.join(TECHS[t]['name'] for t in new_techs)} to {settlement.name}.",
                importance=3, participants=[agent.id], location=list(settlement.position),
                location_name=settlement.name, related={"settlement_id": settlement.id, "techs": new_techs},
            )
        # Dependent children join their parent's household.
        for child_id in agent.child_ids:
            child = self.agents.get(child_id)
            if child and child.alive and child.age < 16 and child.settlement_id is None:
                child.settlement_id = settlement.id
                child.home_tile = list(settlement.position)
                settlement.member_ids.append(child.id)
                settlement.occupation[child.id] = "Child"
        return True

    def _leave_settlement(self, agent: Agent, reason: str = "left") -> bool:
        settlement = self.settlements.get(agent.settlement_id or "")
        if not settlement:
            return False
        settlement.member_ids = [aid for aid in settlement.member_ids if aid != agent.id]
        settlement.occupation.pop(agent.id, None)
        was_leader = settlement.leader_id == agent.id
        if was_leader:
            settlement.leader_id = None
            settlement.government["leader_id"] = None
        agent.settlement_id = None
        agent.needs["shelter"] = max(0.0, agent.needs["shelter"] - 20)
        self._memory(agent, "social", f"Left {settlement.name}; {reason}.", 0.55, -0.1,
                     location=list(settlement.position), tags=["settlement", "migration"])
        self.add_event(
            "settlement", f"{agent.name} leaves {settlement.name}",
            f"{agent.name} departed {settlement.name}; {reason}." + (" The settlement has no leader." if was_leader else ""),
            importance=2 if not was_leader else 3, participants=[agent.id],
            location=list(settlement.position), location_name=settlement.name,
            related={"settlement_id": settlement.id},
        )
        return True

    def best_migration_target(self, agent: Agent) -> dict[str, Any] | None:
        candidates: list[tuple[float, Settlement]] = []
        for settlement in self.settlements.values():
            if settlement.ruins or settlement.id == agent.settlement_id:
                continue
            if settlement.storage.get("food", 0) < settlement.population * 0.35:
                continue
            space = settlement.housing_capacity() - settlement.population
            dist = self.distance(agent.position[0], agent.position[1], settlement.position[0], settlement.position[1])
            score = settlement.happiness * 0.5 + settlement.stability * 0.2 + min(15, space * 3) - dist * 0.4
            candidates.append((score, settlement))
        if not candidates:
            return None
        candidates.sort(key=lambda pair: pair[0], reverse=True)
        settlement = candidates[0][1]
        return {
            "settlement_id": settlement.id,
            "name": settlement.name,
            "tile": list(settlement.position),
        }

    # -------------------------------------------------------------- research
    def _research_material_view(self, settlement: Settlement | None, agent: Agent) -> dict[str, float]:
        """Knowledge conditions should see what the community actually owns.

        Stone, herbs and ore are often carried by individuals rather than
        deposited, so a settlement that is materially ready should not be
        blocked by an empty common storehouse.
        """
        if settlement is None:
            return dict(agent.inventory)
        view = dict(settlement.storage)
        for aid in settlement.member_ids:
            member = self.agents.get(aid)
            if not member or not member.alive:
                continue
            for key in ("stone", "herbs", "ore", "wood", "food", "water"):
                view[key] = round(view.get(key, 0.0) + member.inventory.get(key, 0.0), 2)
        return view

    def research_candidates(self, agent: Agent) -> list[str]:
        settlement = self.settlements.get(agent.settlement_id or "")
        known = set(settlement.known_techs) if settlement else set(agent.known_techs)
        if agent.research_target and agent.research_target not in known:
            target = TECHS.get(agent.research_target)
            if target and all(p in known for p in target["prereq"]):
                return [agent.research_target]
        candidates = []
        for key, spec in TECHS.items():
            if key in known:
                continue
            if self.config.no_currency and key == "currency":
                continue
            if not all(p in known for p in spec["prereq"]):
                continue
            candidates.append(key)
        if settlement:
            population = len(self.alive_agents())
            storage = self._research_material_view(settlement, agent)
            has_market = settlement.has_building("market")
            total_fertility = self.world.tile_or_raise(settlement.position[0], settlement.position[1]).fertility
        else:
            population = len(self.alive_agents())
            storage = agent.inventory
            has_market = False
            total_fertility = self.world.tile_or_raise(agent.position[0], agent.position[1]).fertility
        def readiness(key: str) -> tuple[int, float]:
            met, _ = discovery_conditions_met(key, population, len([s for s in self.settlements.values() if not s.ruins]), total_fertility, storage, has_market)
            return (0 if met else 1, TECHS[key]["cost"])
        candidates.sort(key=readiness)
        return candidates[:6]

    def _attempt_discovery(self, agent: Agent, tech_key: str) -> bool:
        if self.config.no_currency and tech_key == "currency":
            agent.research_progress[tech_key] = TECHS[tech_key]["cost"] - 0.1
            return False
        settlement = self.settlements.get(agent.settlement_id or "")
        known = set(settlement.known_techs) if settlement else set(agent.known_techs)
        if tech_key in known:
            return False
        # A technology known elsewhere in the world can still be worked out
        # again here. Blocking that made the global pool a trap: the first
        # settlement to discover farming locked every other settlement out of
        # it permanently, so they never built farms and starved.
        independently_reached = tech_key in self.run_techs
        if not all(p in known for p in TECHS[tech_key]["prereq"]):
            return False
        if settlement:
            population = len(self.alive_agents())
            storage = self._research_material_view(settlement, agent)
            conditions_met, missing = discovery_conditions_met(
                tech_key, population, len([s for s in self.settlements.values() if not s.ruins]),
                self.world.tile_or_raise(settlement.position[0], settlement.position[1]).fertility,
                storage, settlement.has_building("market"),
            )
        else:
            conditions_met, missing = discovery_conditions_met(
                tech_key, len(self.alive_agents()), len([s for s in self.settlements.values() if not s.ruins]),
                self.world.tile_or_raise(agent.position[0], agent.position[1]).fertility,
                agent.inventory, False,
            )
        if not conditions_met:
            agent.research_progress[tech_key] = min(TECHS[tech_key]["cost"] - 0.1, agent.research_progress.get(tech_key, 0))
            agent.stats["research_blocked"] = {"tech": tech_key, "missing": missing, "day": self.day}
            if agent.research_target == tech_key:
                agent.research_target = None
            if self.day % 5 == 0:
                self._memory(agent, "observation", f"Research into {TECHS[tech_key]['name']} is blocked: missing {', '.join(missing)}.", 0.5, -0.1,
                             tags=["research", "blocked"])
            return False
        self.run_techs.add(tech_key)
        spec = TECHS[tech_key]
        if tech_key not in self.tech_discoveries:
            self.tech_discoveries[tech_key] = {
                "day": self.day, "year": self.year, "agent_id": agent.id,
                "agent_name": agent.name, "settlement_id": settlement.id if settlement else None,
                "settlement_name": settlement.name if settlement else None,
                "initial": False,
            }
        if settlement:
            if tech_key not in settlement.known_techs:
                settlement.known_techs.append(tech_key)
            for aid in settlement.member_ids:
                member = self.agents.get(aid)
                if member and tech_key not in member.known_techs:
                    member.known_techs.append(tech_key)
            if tech_key == "currency" and settlement.has_building("market") and not self.config.no_currency:
                self._maybe_adopt_currency(settlement)
        if tech_key not in agent.known_techs:
            agent.known_techs.append(tech_key)
        agent.influence = min(100, agent.influence + 6)
        agent.reputation = min(100, agent.reputation + 4)
        agent.research_target = None
        agent.research_progress.pop(tech_key, None)
        self._memory(agent, "social", f"Discovered {spec['name']}: {spec['effect']}", 0.95, 0.9,
                     tags=["research", "discovery"], detail={"tech": tech_key})
        if independently_reached:
            event_title = f"{spec['name']} is worked out again in {settlement.name if settlement else 'the field'}"
            event_body = (
                f"{agent.name} reached {spec['name']} independently, without the scholars who first "
                f"recorded it. {spec['effect']} Knowledge had reached other communities first, but "
                f"{settlement.name if settlement else 'these people'} had to make the leap themselves."
            )
        else:
            event_title = f"{spec['name']} discovered"
            event_body = (
                f"{agent.name} established {spec['name']} in {settlement.name if settlement else 'the field'}. "
                f"{spec['effect']} The discovery required {len(spec['prereq'])} prerequisite knowledge and met all material conditions."
            )
        self.add_event(
            "technology", event_title,
            event_body,
            importance=5, participants=[agent.id],
            location=list(agent.position) if not settlement else list(settlement.position),
            location_name=settlement.name if settlement else None,
            consequences=[spec["effect"], f"Era: {spec['era']}"],
            related={"tech": tech_key, "settlement_id": settlement.id if settlement else None, "era": spec["era"]},
        )
        if settlement:
            self._culture_from_event(settlement, "discovery", tech=tech_key, discoverer=agent)
            language = self.languages.get(settlement.language_id)
            if language:
                used = set(language.lexicon.values())
                title = spec["name"].lower()
                if title not in language.lexicon:
                    language.lexicon[title] = coin_word(random.Random(zlib.crc32(f"{language.id}:{tech_key}".encode())), used)
                if "knowledge" not in language.lexicon:
                    language.lexicon["knowledge"] = coin_word(random.Random(zlib.crc32(f"{language.id}:knowledge".encode())), set(language.lexicon.values()) | used)
            for member in self.alive_agents():
                if member.settlement_id == settlement.id and member.id != agent.id:
                    self._memory(member, "social", f"Learned of {spec['name']} from {agent.name}.", 0.55, 0.5,
                                 participants=[agent.id], tags=["technology", "knowledge"], location=list(settlement.position))
        return True

    def _research_diffusion_phase(self) -> None:
        """Language contact that accompanies trade. Technology diffusion is
        handled per-settlement in _settlement_tech_diffusion, which also covers
        neighbours that are not formal trade partners."""
        if self.day % 3 != 0:
            return
        rng = self.daily_rng("tech-diffusion")
        active = [s for s in self.settlements.values() if not s.ruins and s.population >= 3]
        for settlement in active:
            for other in active:
                if other.id == settlement.id:
                    continue
                relation = settlement.diplomacy.get(other.id, {})
                if relation.get("status") not in ("trade", "alliance") or relation.get("trust", 0) < 5:
                    continue
                # Language contact accompanies trade.
                lang_a = self.languages.get(settlement.language_id)
                lang_b = self.languages.get(other.language_id)
                if lang_a and lang_b and lang_a.id != lang_b.id and rng.random() < 0.3:
                    loans = borrow_words(lang_b, lang_a, rng, self.day, amount=1)
                    if loans:
                        loan = loans[0]
                        self.add_event(
                            "culture", f"A word crosses into {lang_a.name}",
                            f"'{loan['word']}' ({loan['concept']}) passed from {lang_b.name} speakers into the speech of {settlement.name}.",
                            importance=2, location=list(settlement.position), location_name=settlement.name,
                            related={"language_id": lang_a.id, "from_language": lang_b.id, "concept": loan["concept"]},
                        )

    # --------------------------------------------------------------- politics
    def _politics_phase(self) -> None:
        if self.day % 2 != 0:
            return
        rng = self.daily_rng("politics")
        for settlement in self.settlements.values():
            if settlement.ruins or settlement.population < 2:
                continue
            members = [self.agents[aid] for aid in settlement.member_ids if aid in self.agents and self.agents[aid].alive]
            if not members:
                continue
            if self.config.no_leader:
                if settlement.government.get("system") != "assembly":
                    self._set_government_from_change(settlement, evaluate_governance(
                        settlement, self.agents, self.cultures.get(settlement.culture_id),
                        set(settlement.known_techs), self.day, rng, no_leader=True,
                    ))
                settlement.leader_id = None
            else:
                if not settlement.leader_id or settlement.leader_id not in self.agents or not self.agents[settlement.leader_id].alive:
                    leader_id, selection = choose_leader(settlement, self.agents, rng, self.day, mode=settlement.government.get("system", "tribal"))
                    previous = settlement.leader_id
                    settlement.leader_id = leader_id
                    settlement.government["leader_id"] = leader_id
                    if leader_id:
                        settlement.government["legitimacy"] = max(35.0, float(settlement.government.get("legitimacy", 50)))
                        settlement.government["members"] = list(dict.fromkeys(settlement.government.get("members", []) + [leader_id]))
                        new_leader = self.agents[leader_id]
                        new_leader.influence = min(100, new_leader.influence + 5)
                        if previous != leader_id:
                            self.add_event(
                                "politics", f"{new_leader.name} becomes leader of {settlement.name}",
                                f"After the position fell vacant, {new_leader.name} was chosen to lead {settlement.name} "
                                f"as {settlement.gov_label()}. Support was drawn from {selection['candidates']} candidates.",
                                importance=4, participants=[leader_id], location=list(settlement.position),
                                location_name=settlement.name,
                                related={"settlement_id": settlement.id, "government": settlement.government.get("system")},
                            )
            refresh_government_legitimacy(settlement)
            if self.day % 4 == 0:
                old_factions = len(settlement.factions)
                update_factions(settlement, self.agents, self.cultures.get(settlement.culture_id), rng)
                if old_factions == 0 and settlement.factions:
                    self.add_event(
                        "politics", f"Factions form in {settlement.name}",
                        f"Political divisions appeared: " + ", ".join(f"{f['name']} ({f['share']*100:.0f}%)" for f in settlement.factions) + ".",
                        importance=3, location=list(settlement.position), location_name=settlement.name,
                        consequences=[f"{f['name']}: {f['description']}" for f in settlement.factions],
                        related={"settlement_id": settlement.id},
                    )
            culture = self.cultures.get(settlement.culture_id)
            enacted = consider_laws(settlement, self.agents, culture, self.day, settlement.stats, self.config.no_currency)
            for law in enacted:
                self.add_event(
                    "politics", f"{law['title']} enacted in {settlement.name}",
                    f"{law['description']} Support for the measure was {law['support']:.0f}%. "
                    f"Effects: {', '.join(f'{k}: {v}' for k, v in law['effects'].items())}.",
                    importance=3, location=list(settlement.position), location_name=settlement.name,
                    related={"settlement_id": settlement.id, "law": law["key"]},
                )
                if settlement.leader_id and settlement.leader_id in self.agents:
                    self._memory(self.agents[settlement.leader_id], "social", f"Enacted '{law['title']}' in {settlement.name}.", 0.55, 0.4,
                                 tags=["politics", "law"])
            # A government change is a real transition with a new selector and
            # new legitimacy, not a cosmetic label.
            if self.day % 8 == 0:
                change = evaluate_governance(
                    settlement, self.agents, culture, set(settlement.known_techs),
                    self.day, rng, no_leader=self.config.no_leader,
                )
                if change:
                    self._set_government_from_change(settlement, change)
            if not self.config.no_leader and settlement.government.get("legitimacy", 55) < 30 and self.day % 10 == 0:
                leader_id, selection = choose_leader(settlement, self.agents, rng, self.day, mode=settlement.government.get("system", "tribal"))
                if leader_id and leader_id != settlement.leader_id:
                    old = settlement.leader_id
                    settlement.leader_id = leader_id
                    settlement.government["leader_id"] = leader_id
                    settlement.government["legitimacy"] = 48.0
                    settlement.government["members"] = [leader_id]
                    self.add_event(
                        "politics", f"Leadership challenge in {settlement.name}",
                        f"With legitimacy at {settlement.government.get('legitimacy', 0):.0f}, {self.agents[leader_id].name} replaced "
                        f"{self.agents[old].name if old and old in self.agents else 'the previous leader'} as leader.",
                        importance=4, participants=[leader_id] + ([old] if old else []),
                        location=list(settlement.position), location_name=settlement.name,
                        consequences=["A new leader took office"],
                        related={"settlement_id": settlement.id, "system": settlement.government.get("system")},
                    )

    def _set_government_from_change(self, settlement: Settlement, change: dict[str, Any] | None) -> None:
        if not change:
            return
        settlement.leader_id = change.get("leader_id")
        system = change["to"]
        self.add_event(
            "politics", f"{settlement.name} changes its government",
            f"{settlement.name} moved from {change['from'].replace('_', ' ')} rule to {system.replace('_', ' ')}: {change['reason']}." if change.get("reason") else
            f"{settlement.name} moved from {change['from'].replace('_', ' ')} rule to {system.replace('_', ' ')}.",
            importance=5, location=list(settlement.position), location_name=settlement.name,
            consequences=[
                f"System: {settlement.gov_label()}",
                f"Leader: {self.agents[settlement.leader_id].name if settlement.leader_id and settlement.leader_id in self.agents else 'none'}",
                f"Tax rate: {settlement.government.get('tax_rate', 0) * 100:.1f}%",
            ],
            related={"settlement_id": settlement.id, "from": change["from"], "to": system},
        )
        for member in self.alive_agents():
            if member.settlement_id == settlement.id:
                self._memory(member, "social", f"Witnessed a change of government in {settlement.name}: {change['from']} to {system}.", 0.7, 0.1,
                             tags=["politics", "government"], location=list(settlement.position))

    # -------------------------------------------------------------- diplomacy
    def _diplomacy_phase(self) -> None:
        if self.day % 5 != 0:
            return
        active = [s for s in self.settlements.values() if not s.ruins]
        if len(active) < 2:
            return
        rng = self.daily_rng("diplomacy")
        for i, a in enumerate(active):
            for b in active[i + 1:]:
                rel = a.diplomacy.setdefault(b.id, {"status": "neutral", "trust": 0.0, "since_day": self.day})
                b.diplomacy.setdefault(a.id, {"status": "neutral", "trust": 0.0, "since_day": self.day})
                dist = self.distance(a.position[0], a.position[1], b.position[0], b.position[1])
                status = rel.get("status", "neutral")
                if status == "war":
                    self._war_tick(a, b, rel, rng)
                    continue
                if status in ("trade", "alliance"):
                    rel["trust"] = round(min(100, rel.get("trust", 0) + 1.2), 2)
                    b.diplomacy[a.id]["trust"] = rel["trust"]
                    if status == "trade" and rel["trust"] > 55 and "philosophy" in a.known_techs and "philosophy" in b.known_techs and rng.random() < 0.4:
                        rel["status"] = "alliance"
                        b.diplomacy[a.id]["status"] = "alliance"
                        self.add_event(
                            "politics", f"Alliance between {a.name} and {b.name}",
                            f"Long trade and growing trust led {a.name} and {b.name} to swear a defensive alliance.",
                            importance=4, location=list(a.position), location_name=a.name,
                            related={"settlements": [a.id, b.id], "status": "alliance"},
                        )
                    continue
                # New agreements require trade knowledge and some goodwill.
                if "trade" in a.known_techs and "trade" in b.known_techs and rel.get("trust", 0) > 6 and rng.random() < 0.45:
                    rel["status"] = "trade"
                    rel["since_day"] = self.day
                    b.diplomacy[a.id]["status"] = "trade"
                    b.diplomacy[a.id]["since_day"] = self.day
                    self.add_event(
                        "economy", f"Trade agreement: {a.name} and {b.name}",
                        f"Traders from {a.name} and {b.name} agreed to regular exchange. The distance between them is {dist} tiles.",
                        importance=3, location=list(a.position), location_name=a.name,
                        consequences=["Goods and knowledge may now spread between settlements"],
                        related={"settlements": [a.id, b.id], "agreement": "trade"},
                    )
                    continue
                # Rivalry grows from proximity, hunger and martial culture.
                culture_a = self.cultures.get(a.culture_id)
                culture_b = self.cultures.get(b.culture_id)
                martial = max(culture_a.values.get("martial", 0.5) if culture_a else 0.5, culture_b.values.get("martial", 0.5) if culture_b else 0.5)
                scarcity = 1 if (a.storage.get("food", 0) < a.population or b.storage.get("food", 0) < b.population) else 0
                if dist < 20 and (scarcity or rng.random() < 0.18 + martial * 0.2):
                    drift = 1.0 + martial * 2 + scarcity * 2
                    rel["trust"] = round(rel.get("trust", 0) - drift, 2)
                    b.diplomacy[a.id]["trust"] = rel["trust"]
                    if rel["trust"] < -25 and status == "neutral":
                        rel["status"] = "hostile"
                        b.diplomacy[a.id]["status"] = "hostile"
                        self.add_event(
                            "politics", f"Tensions between {a.name} and {b.name}",
                            f"Competition for land and food pushed {a.name} and {b.name} toward open hostility. Trust fell to {rel['trust']:.0f}.",
                            importance=3, location=list(a.position), location_name=a.name,
                            related={"settlements": [a.id, b.id]},
                        )
                    if rel["trust"] < -38 and self.day > 20 and a.population >= 4 and b.population >= 4 and rng.random() < 0.5:
                        rel["status"] = "war"
                        rel["war_started"] = self.day
                        b.diplomacy[a.id]["status"] = "war"
                        b.diplomacy[a.id]["war_started"] = self.day
                        a.stats["at_war_with"] = b.id
                        b.stats["at_war_with"] = a.id
                        self.conflicts += 1
                        self.add_event(
                            "conflict", f"War between {a.name} and {b.name}",
                            f"After trust collapsed to {rel['trust']:.0f}, {a.name} and {b.name} declared war. "
                            f"Their populations are {a.population} and {b.population}, and they are {dist} tiles apart.",
                            importance=5, location=list(a.position), location_name=a.name,
                            consequences=["Raids will reduce health, safety and stores", "Trade is suspended"],
                            related={"settlements": [a.id, b.id], "war": True},
                        )

    def _war_tick(self, a: Settlement, b: Settlement, rel: dict[str, Any], rng: random.Random) -> None:
        # Battles are small, destructive events, not a separate game system.
        raiders_a = [self.agents[aid] for aid in a.member_ids if aid in self.agents and self.agents[aid].alive and self.agents[aid].age >= 16]
        raiders_b = [self.agents[aid] for aid in b.member_ids if aid in self.agents and self.agents[aid].alive and self.agents[aid].age >= 16]
        if raiders_a and raiders_b and rng.random() < 0.7:
            attacker = rng.choice(raiders_a)
            defender = rng.choice(raiders_b)
            damage = rng.uniform(4, 12)
            defender.needs["health"] = max(0.0, defender.needs["health"] - damage)
            attacker.needs["health"] = max(0.0, attacker.needs["health"] - damage * 0.45)
            a.storage["food"] = round(a.storage.get("food", 0) * 0.93, 2)
            b.storage["food"] = round(b.storage.get("food", 0) * 0.93, 2)
            a.safety = max(0.0, a.safety - 4)
            b.safety = max(0.0, b.safety - 4)
            self.add_event(
                "conflict", f"Skirmish between {a.name} and {b.name}",
                f"Raiders from {a.name} and defenders from {b.name} clashed. "
                f"{defender.name} was hurt (health {defender.needs['health']:.0f}); {attacker.name} returned wounded. Both settlements lost food.",
                importance=3, participants=[attacker.id, defender.id], location=list(defender.position),
                location_name=b.name, related={"settlements": [a.id, b.id], "war": True},
            )
            self.conflicts += 1
        # Exhaustion, or one side's collapse, ends wars.
        elapsed = self.day - int(rel.get("war_started", self.day))
        exhausted = a.stability < 32 or b.stability < 32 or a.storage.get("food", 0) < a.population * 0.4 or b.storage.get("food", 0) < b.population * 0.4
        if elapsed >= 6 and (exhausted or rng.random() < 0.35):
            rel["status"] = "peace"
            rel["since_day"] = self.day
            rel["trust"] = 0.0
            b.diplomacy[a.id]["status"] = "peace"
            b.diplomacy[a.id]["since_day"] = self.day
            b.diplomacy[a.id]["trust"] = 0.0
            a.stats.pop("at_war_with", None)
            b.stats.pop("at_war_with", None)
            self.add_event(
                "conflict", f"Peace between {a.name} and {b.name}",
                f"After {elapsed} days, the war between {a.name} and {b.name} ended from exhaustion. "
                f"Both sides retain their settlements; trust begins again at zero.",
                importance=5, location=list(a.position), location_name=a.name,
                consequences=["War ended", "Trade may resume"],
                related={"settlements": [a.id, b.id], "peace": True},
            )
            for settlement in (a, b):
                self._culture_from_event(settlement, "peace")

    # --------------------------------------------------------------- culture
    def _culture_phase(self) -> None:
        if self.day % 2 != 0:
            return
        rng = self.daily_rng("culture")
        for settlement in self.settlements.values():
            if settlement.ruins or settlement.population < 2:
                continue
            culture = self.cultures.get(settlement.culture_id)
            if not culture:
                continue
            members = [self.agents[aid] for aid in settlement.member_ids if aid in self.agents and self.agents[aid].alive]
            if not members:
                continue
            # Values move with the people who actually live here.
            averages = {
                "cooperation": sum(m.personality["cooperation"] for m in members) / len(members),
                "tradition": sum(m.personality["honesty"] for m in members) / len(members),
                "hierarchy": sum(m.personality["ambition"] for m in members) / len(members),
                "innovation": sum(m.personality["curiosity"] for m in members) / len(members),
                "hospitality": sum(m.personality["empathy"] for m in members) / len(members),
                "martial": sum(m.personality["aggressiveness"] for m in members) / len(members),
            }
            for key, value in averages.items():
                culture.values[key] = round(culture.values.get(key, value) * 0.94 + value * 0.06, 3)
            # Milestone customs rooted in actual events.
            if self.day - settlement.founded_day == 20:
                self._culture_from_event(settlement, "twentieth_day")
            if settlement.population >= 10 and not any(t["name"] == "Tenth Resident" for t in culture.traditions):
                self._culture_from_event(settlement, "tenth_resident", member=members[-1])
            # Creative work arises from real leisure and morale.
            creative = [m for m in members if m.needs["energy"] > 65 and m.happiness() > 65 and m.age >= 16]
            if creative and rng.random() < 0.05:
                artist = max(creative, key=lambda m: m.personality["curiosity"] + m.skills["crafting"])
                form = rng.choice(["a song", "a carving", "a woven pattern", "a story", "a dance"])
                subject = rng.choice(["the river", "the first winter", "the mountain", "the harvest", "the dead", "the stars"])
                record = {
                    "name": f"{form.capitalize()} of {subject}",
                    "by": artist.name, "day": self.day, "form": form, "subject": subject,
                }
                culture.art_forms.append(record)
                if len(culture.art_forms) > 20:
                    culture.art_forms.pop(0)
                artist.stats["artworks"] = artist.stats.get("artworks", 0) + 1
                self._memory(artist, "social", f"Created {form} about {subject}.", 0.55, 0.7, tags=["culture", "art"])
                self.add_event(
                    "culture", f"{artist.name} creates {form}",
                    f"In {settlement.name}, {artist.name} made {form} about {subject}. It became part of the settlement's shared culture.",
                    importance=2, participants=[artist.id], location=list(settlement.position),
                    location_name=settlement.name, related={"culture_id": culture.id, "art": record["name"]},
                )
                if len(culture.art_forms) == 1:
                    add_tradition(culture, self.day, "Evening of Making", f"The people of {settlement.name} set aside evenings for song, carving and story.", "artistic", f"First work by {artist.name}")
            # Language drifts at generation boundaries.
            if self.day % 40 == 0:
                language = self.languages.get(settlement.language_id)
                if language:
                    drift_rng = random.Random(zlib.crc32(f"drift:{language.id}:{self.day}".encode()))
                    changes = drift_language(language, drift_rng, self.day, rate=0.05)
                    if changes:
                        self.add_event(
                            "culture", f"The speech of {settlement.name} shifts",
                            f"{len(changes)} words changed form across a generation in {language.name}. "
                            f"Example: '{changes[0]['concept']}' became '{changes[0]['new']}' (was '{changes[0]['old']}').",
                            importance=2, location=list(settlement.position), location_name=settlement.name,
                            related={"language_id": language.id, "changes": changes[:6]},
                        )
                    language.speakers = settlement.population

    def _culture_from_event(self, settlement: Settlement, kind: str, **payload: Any) -> None:
        culture = self.cultures.get(settlement.culture_id)
        if not culture:
            return
        tradition = None
        if kind == "partnership":
            tradition = add_tradition(culture, self.day, "Bonding Day", "Partnerships are publicly witnessed and remembered in song.", "kinship", "The first recorded partnership")
        elif kind == "birth":
            tradition = add_tradition(culture, self.day, "Naming Day", "Newborns are named before the assembled household.", "kinship", "The first birth in the settlement")
        elif kind == "first_farm":
            tradition = add_tradition(culture, self.day, "First Harvest", "The community gives the first sheaf to the common store.", "subsistence", "The first farm was completed")
        elif kind == "shrine":
            tradition = add_tradition(culture, self.day, "Evening Song", "Songs are sung at the shrine when the work is done.", "ritual", "The shrine was raised")
            culture.art_forms.append({"name": "Evening Song", "by": "the community", "day": self.day, "form": "song", "subject": "the hearth"})
        elif kind == "market":
            tradition = add_tradition(culture, self.day, "Market Day", "Every fifth day, goods are brought to the open square.", "economic", "The first market was built")
        elif kind == "discovery":
            discovery_traditions = {
                "agriculture": ("Sowing Rite", "The first seeds of spring are blessed before planting."),
                "writing": ("Keeper of Records", "Names and agreements are carved so the dead and the living may be remembered."),
                "currency": ("Weighing Day", "Coins are counted aloud in public at the end of each market."),
                "medicine": ("Herb Gathering", "The sick are tended by those who know the plants."),
                "philosophy": ("Question Night", "Any resident may question the leader without punishment."),
            }
            if payload.get("tech") in discovery_traditions:
                name, desc = discovery_traditions[payload["tech"]]
                tradition = add_tradition(culture, self.day, name, desc, "knowledge", f"Discovery of {TECHS[payload['tech']]['name']}")
        elif kind == "peace":
            tradition = add_tradition(culture, self.day, "Reconciliation", "The end of a war is marked by a shared meal and the names of the dead.", "memory", "The war ended")
        elif kind == "twentieth_day":
            tradition = add_tradition(culture, self.day, "Founders' Day", f"The settlement remembers its first twenty days and the names of its founders.", "memory", "Twenty days since founding")
        elif kind == "tenth_resident":
            member = payload.get("member")
            tradition = add_tradition(culture, self.day, "Tenth Resident", f"When the settlement reaches ten people, a feast welcomes the newest resident.", "communal", f"Population reached ten in the time of {member.name if member else 'the community'}")
        if tradition:
            self.add_event(
                "culture", f"New tradition in {settlement.name}: {tradition['name']}",
                f"{tradition['description']} (Origin: {tradition['origin']}.)",
                importance=3, location=list(settlement.position), location_name=settlement.name,
                related={"culture_id": culture.id, "tradition": tradition["name"]},
            )
            for member in self.alive_agents():
                if member.settlement_id == settlement.id:
                    self._memory(member, "social", f"A new tradition took root: {tradition['name']}.", 0.5, 0.5,
                                 tags=["culture", "tradition"], location=list(settlement.position))
