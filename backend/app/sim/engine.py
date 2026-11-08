"""The CIVITAS simulation engine.

One tick = one day. A year is 40 days (four 10-day seasons). Deterministic
routine behavior; emergent outcomes. Split into mixins:

  engine.py            core clock, needs, demography, persistence, telemetry
  engine_actions.py    daily decisions, movement, gathering, work, conflict
  engine_social.py     conversation, relationships, family, language use
  engine_civ.py        settlements, governance, economy, technology, diplomacy

Nothing in the simulation calls an LLM. Optional narrative enrichment is
layered on top by the API and can be switched off without changing behavior.
"""
from __future__ import annotations

import random
import math
import zlib
from typing import Any

from .agent import Agent, choose_occupation, make_agent
from .constants import DAYS_PER_YEAR, GOVERNMENTS, NEEDS, SEASONS, TECHS
from .culture import Culture, Language, create_culture, create_language
from .engine_actions import ActionsMixin
from .engine_civ import CivilizationMixin
from .engine_social import SocialMixin
from .economy import wealth_distribution
from .memory import Memory
from .names import pick_name
from .settlement import Settlement
from .tech import current_era
from .world import World, WorldConfig

STARTING_TECH_MAP = {
    "none": [],
    "fire": ["fire"],
    "basic_tools": ["fire", "basic_tools"],
    "early_agriculture": ["fire", "basic_tools", "agriculture"],
}


class SimulationEngine(ActionsMixin, SocialMixin, CivilizationMixin):
    version = 1

    def __init__(self, run_id: str, config: WorldConfig, state: dict[str, Any] | None = None) -> None:
        self.run_id = run_id
        self.config = config.model_copy(deep=True)
        self.world = World.generate(config)
        self.config.seed = self.world.seed
        self.seed = self.world.seed
        self.status = "running"
        self.tick = 0
        self.day = 1
        self.agents: dict[str, Agent] = {}
        self.settlements: dict[str, Settlement] = {}
        self.cultures: dict[str, Culture] = {}
        self.languages: dict[str, Language] = {}
        self.families: dict[str, dict[str, Any]] = {}
        self.run_techs: set[str] = set()
        self.tech_discoveries: dict[str, dict[str, Any]] = {}
        self.events: list[dict[str, Any]] = []
        self.outbox: list[dict[str, Any]] = []
        self.metrics_history: list[dict[str, Any]] = []
        self.recent_transactions: list[dict[str, Any]] = []
        self.counters: dict[str, int] = {"agent": 0, "settlement": 0, "family": 0, "event": 0, "memory": 0}
        self.births = 0
        self.deaths = 0
        self.conflicts = 0
        self.trades = 0
        self.latest_metrics: dict[str, Any] = {}
        self.gate_stats: dict[str, int] = {}
        self.created_day = 1
        self.last_error: str | None = None
        self.weather = self.world.weather
        if state is None:
            self._initialise_new()
        else:
            self._restore(state)

    # ------------------------------------------------------------- utilities
    def daily_rng(self, label: str) -> random.Random:
        return random.Random(zlib.crc32(f"{self.seed}:{self.day}:{label}".encode("utf-8")))

    def _new_id(self, kind: str) -> str:
        self.counters[kind] = self.counters.get(kind, 0) + 1
        prefix = {"agent": "ag", "settlement": "set", "family": "fam", "event": "evt", "memory": "mem"}[kind]
        width = 4 if kind != "event" else 6
        return f"{prefix}_{self.counters[kind]:0{width}d}"

    def _next_agent_id(self) -> str:
        return self._new_id("agent")

    def _next_settlement_id(self) -> str:
        return self._new_id("settlement")

    def _next_family_id(self) -> str:
        return self._new_id("family")

    def _memory(
        self,
        agent: Agent,
        kind: str,
        summary: str,
        importance: float,
        sentiment: float = 0.0,
        participants: list[str] | None = None,
        location: list[int] | None = None,
        tags: list[str] | None = None,
        detail: dict[str, Any] | None = None,
    ) -> Memory:
        memory = Memory(
            id=self._new_id("memory"), tick=self.tick, day=self.day, kind=kind,
            summary=summary, importance=importance, sentiment=sentiment,
            participants=participants or [], location=location or list(agent.position),
            tags=tags or [], detail=detail or {},
        )
        agent.memory_add(memory)
        return memory

    def add_event(
        self,
        category: str,
        title: str,
        description: str,
        importance: int = 3,
        participants: list[str] | None = None,
        location: list[int] | None = None,
        consequences: list[str] | None = None,
        related: dict[str, Any] | None = None,
        location_name: str | None = None,
    ) -> dict[str, Any]:
        participants = participants or []
        names = [self.agents[aid].name for aid in participants if aid in self.agents]
        event = {
            "id": self._new_id("event"),
            "run_id": self.run_id,
            "tick": self.tick,
            "day": self.day,
            "year": self.year,
            "season": self.season,
            "category": category,
            "importance": importance,
            "title": title,
            "description": description,
            "location": list(location) if location else None,
            "location_name": location_name,
            "participants": participants,
            "participant_names": names,
            "consequences": consequences or [],
            "related": related or {},
            "narrative": None,
        }
        self.events.append(event)
        if len(self.events) > 2500:
            self.events = self.events[-2500:]
        self.outbox.append(event)
        if len(self.outbox) > 200:
            self.outbox = self.outbox[-200:]
        return event

    def drain_outbox(self, limit: int = 40) -> list[dict[str, Any]]:
        events = self.outbox[-limit:]
        self.outbox = []
        return events

    def alive_agents(self) -> list[Agent]:
        return [a for a in self.agents.values() if a.alive]

    @property
    def season(self) -> str:
        return SEASONS[((max(1, self.day) - 1) // 10) % 4]

    @property
    def year(self) -> int:
        return ((max(1, self.day) - 1) // DAYS_PER_YEAR) + 1

    @property
    def day_of_season(self) -> int:
        return ((max(1, self.day) - 1) % 10) + 1

    @property
    def time_label(self) -> str:
        return f"Year {self.year} · {self.season} · Day {self.day_of_season}"

    def distance(self, ax: int, ay: int, bx: int, by: int) -> int:
        return abs(ax - bx) + abs(ay - by)

    def agent_by_id(self, agent_id: str) -> Agent | None:
        return self.agents.get(agent_id)

    # ------------------------------------------------------------- bootstrap
    def _initialise_new(self) -> None:
        rng = random.Random(self.seed)
        positions = self.world.spawn_positions(rng, self.config.initial_population)
        used_names: set[str] = set()
        starting_techs = STARTING_TECH_MAP.get(self.config.starting_technology, [])
        base_techs = set(starting_techs)
        # Foraging is baseline knowledge held by every band.
        self.run_techs = set(base_techs)
        self.tech_discoveries = {
            key: {"day": 0, "agent_id": None, "settlement_id": None, "initial": True}
            for key in base_techs
        }
        for index, (x, y, group) in enumerate(positions):
            gender = rng.choices(["woman", "man", "nonbinary"], weights=[48, 48, 4])[0]
            name = pick_name(rng, gender, used_names)
            agent = make_agent(
                rng=rng,
                agent_id=self._next_agent_id(),
                name=name,
                position=(x, y),
                origin_group=group,
                distribution=self.config.personality_distribution,
                cooperation_bias=self.config.cooperation_bias,
                abundance=self.config.resource_abundance,
                starting_techs=sorted(base_techs),
                birth_day=1,
            )
            agent.birth_day = 1 - int(agent.age_years * DAYS_PER_YEAR)
            agent.influence = round(3 + agent.personality["ambition"] * 5, 1)
            agent.reputation = round(42 + agent.personality["honesty"] * 18 + agent.personality["cooperation"] * 10, 1)
            agent.occupation = choose_occupation(agent)
            if self.config.asymmetric_groups:
                if group == 0:
                    agent.inventory["food"] = round(agent.inventory["food"] + 4, 1)
                    agent.inventory["wood"] = round(agent.inventory["wood"] + 2, 1)
                    agent.inventory["stone"] = round(agent.inventory["stone"] + 1, 1)
                elif group >= 2:
                    agent.inventory["food"] = round(max(1.0, agent.inventory["food"] - 2.0), 1)
                    agent.inventory["wood"] = 0.0
            self._memory(
                agent, "survival",
                f"Made camp near a {self.world.tile_or_raise(x, y).terrain.replace('_', ' ')} with the band.",
                0.35, 0.1, tags=["home", "origin"], location=[x, y],
                detail={"origin_group": group},
            )
            self.agents[agent.id] = agent

        # Every founding band carries a small proto-lexicon. It is not a full
        # language: meanings are shared, words are few, and divergence begins
        # with the first settlements.
        groups: dict[int, list[Agent]] = {}
        for agent in self.agents.values():
            groups.setdefault(agent.origin_group, []).append(agent)
        used_words: set[str] = set()
        for group, members in sorted(groups.items()):
            site = self.world.start_sites[group] if group < len(self.world.start_sites) else self.world.start_sites[0]
            lang_seed = zlib.crc32(f"proto:{self.seed}:{group}".encode("utf-8"))
            language = create_language(lang_seed, settlement_id="", day=1)
            # Keep only common concepts in a proto-lexicon; the rest are coined later.
            keep = sorted(language.lexicon)[:16]
            language.lexicon = {k: language.lexicon[k] for k in keep}
            language.name = f"Old {language.name}"
            language.speakers = len(members)
            language.origins = ["founding bands"]
            for member in members:
                member.known_languages = [language.id]
                member.personal_vocabulary = dict(language.lexicon)
            self.languages[language.id] = language
            used_words.update(language.lexicon.values())
            self.add_event(
                "culture", "A founding band arrives",
                f"{len(members)} settlers made camp in the {site['terrain'].replace('_', ' ')} at ({site['x']}, {site['y']}), carrying a small shared vocabulary.",
                importance=4, participants=[m.id for m in members],
                location=[site["x"], site["y"]],
                consequences=[f"Group {group + 1} of {len(groups)} established"],
                related={"group": group, "language_id": language.id},
                location_name=f"Band {group + 1}",
            )

        self.add_event(
            "world", f"The land of {self.config.world_name} takes shape",
            f"A {self.world.width}×{self.world.height} world was generated from seed {self.world.seed}: "
            f"{round(self.world.land_ratio * 100)}% land, {self.world.rivers} rivers, {self.world.lakes} lakes, "
            f"climate {self.config.climate}, resource abundance {self.config.resource_abundance:.1f}.",
            importance=5, location=None,
            consequences=[
                f"{self.config.initial_population} people in {len(groups)} founding bands",
                "No settlements yet",
            ],
            related={"seed": self.world.seed, "preset": self.config.preset},
        )
        if base_techs:
            names = ", ".join(TECHS[t]["name"] for t in sorted(base_techs))
            self.add_event(
                "technology", "Founding knowledge",
                f"The first bands already possess: {names}.",
                importance=3, related={"techs": sorted(base_techs)},
            )
        if self.config.no_currency:
            self.add_event(
                "world", "Constraint: no currency",
                "This run forbids the emergence of coinage and monetary exchange. Barter and sharing only.",
                importance=3,
            )
        if self.config.no_leader:
            self.add_event(
                "world", "Constraint: no central leaders",
                "This run forbids the concentration of executive authority. Settlements must coordinate without a leader.",
                importance=3,
            )
        self._update_metrics(initial=True)

    # ------------------------------------------------------------- lifecycle
    def step(self) -> dict[str, Any]:
        if self.status == "ended":
            return self.latest_metrics
        self.tick += 1
        self.day = self.tick
        self._environment_phase()
        alive = list(self.alive_agents())
        for agent in alive:
            if agent.alive:
                self._update_needs(agent)
        for agent in alive:
            if not agent.alive:
                continue
            self._agent_day(agent)
        self._social_phase()
        self._settlement_phase()
        self._demography_phase()
        self._politics_phase()
        self._diplomacy_phase()
        self._culture_phase()
        self._research_diffusion_phase()
        self._daily_metric()
        if not self.alive_agents():
            self.status = "ended"
            self.add_event(
                "milestone", "The last light goes out",
                f"No living agents remain on day {self.day}. The simulation has ended.",
                importance=5,
            )
        return self.latest_metrics

    def _environment_phase(self) -> None:
        previous = self.world.active_disaster
        env = self.world.environment_tick(self.day)
        disaster = self.world.active_disaster
        if disaster and (previous is None or previous.kind != disaster.kind):
            self._on_disaster_start(disaster)
        elif previous and disaster is None:
            self.add_event(
                "disaster", f"{previous.kind.replace('_', ' ').title()} subsides",
                f"The {previous.kind.replace('_', ' ')} that struck on day {self.day - previous.remaining - 1} has passed.",
                importance=3,
            )
        self.weather = env["weather"]

    def _update_needs(self, agent: Agent) -> None:
        settlement = self.settlements.get(agent.settlement_id or "")
        cold = self.season == "Winter" or self.world.weather == "Snow"
        hot = self.season == "Summer" or self.world.weather == "Drought"
        difficulty = self.config.environmental_difficulty
        agent.needs["hunger"] = max(0.0, agent.needs["hunger"] - (8.0 * difficulty + (2 if cold else 0)))
        agent.needs["thirst"] = max(0.0, agent.needs["thirst"] - (11.0 * difficulty + (4 if hot else 0)))
        energy_cost = 7.0 + (2 if cold else 0) + (2 if self.world.weather == "Storm" else 0)
        if agent.pregnant:
            energy_cost += 2
        agent.needs["energy"] = max(0.0, agent.needs["energy"] - energy_cost)
        # Household provisioning. Eating, drinking and sleeping were whole-day
        # actions, so survival consumed most of every life and almost nobody
        # had a day left to farm, build, court or invent. A person actually
        # eats and drinks while going about the day; provision small amounts
        # automatically from what the household has, and keep the explicit
        # eat/drink/rest actions for shortages and emergencies.
        if agent.needs["hunger"] < 60:
            if agent.inventory.get("food", 0) >= 0.45:
                agent.inventory["food"] = round(agent.inventory["food"] - 0.45, 2)
                agent.needs["hunger"] = min(100.0, agent.needs["hunger"] + 18)
            elif settlement and settlement.storage.get("food", 0) >= 0.45 and self._at_settlement(agent, settlement, 3):
                settlement.storage["food"] = round(settlement.storage["food"] - 0.45, 2)
                settlement.stats["meals_today"] = round(settlement.stats.get("meals_today", 0) + 0.45, 2)
                agent.needs["hunger"] = min(100.0, agent.needs["hunger"] + 18)
        if agent.needs["thirst"] < 60:
            if self.world.tile_or_raise(agent.position[0], agent.position[1]).freshwater:
                agent.needs["thirst"] = min(100.0, agent.needs["thirst"] + 20)
            elif settlement and self._at_settlement(agent, settlement, 2) and (
                settlement.has_building("well") or settlement.has_building("aqueduct")
            ):
                agent.needs["thirst"] = min(100.0, agent.needs["thirst"] + 20)
            elif agent.inventory.get("water", 0) >= 0.3:
                agent.inventory["water"] = round(agent.inventory["water"] - 0.3, 2)
                agent.needs["thirst"] = min(100.0, agent.needs["thirst"] + 20)
            elif settlement and self._water_near(settlement.position):
                agent.needs["thirst"] = min(100.0, agent.needs["thirst"] + 20)
        # Sleep. Without a nightly recovery every adult depended on spending a
        # quarter of their days doing nothing but resting.
        if agent.needs["energy"] < 60:
            sheltered = bool(settlement and settlement.housing_capacity() >= settlement.population)
            agent.needs["energy"] = min(100.0, agent.needs["energy"] + (9 if sheltered else 5))
        agent.needs["social"] = max(0.0, agent.needs["social"] - 5.5)
        danger = self.agent_danger(agent)
        safety_target = 68.0 + (10 if settlement and settlement.has_building("palisade") else 0) - danger * 0.55
        agent.needs["safety"] = max(0.0, min(100.0, agent.needs["safety"] + (safety_target - agent.needs["safety"]) * 0.35))
        if settlement and settlement.member_ids:
            housing = settlement.housing_capacity() >= settlement.population
            shelter_target = 82.0 if housing else 38.0
        else:
            shelter_target = 30.0
        if agent.shelter_until and agent.shelter_until >= self.day:
            shelter_target = max(shelter_target, 58.0)
        if cold and shelter_target < 50:
            shelter_target -= 8
        agent.needs["shelter"] = max(0.0, min(100.0, agent.needs["shelter"] + (shelter_target - agent.needs["shelter"]) * 0.22))
        # Weather and disaster exposure.
        if cold and agent.needs["shelter"] < 35:
            agent.needs["health"] = max(0.0, agent.needs["health"] - 1.8 * difficulty)
        if self.world.weather == "Storm" and agent.needs["shelter"] < 30:
            agent.needs["health"] = max(0.0, agent.needs["health"] - 1.2)
        if self.world.active_disaster and self.world.active_disaster.center:
            cx, cy = self.world.active_disaster.center
            if self.distance(agent.position[0], agent.position[1], cx, cy) <= 2:
                kind = self.world.active_disaster.kind
                if kind in ("wildfire", "flood"):
                    agent.needs["health"] = max(0.0, agent.needs["health"] - 2.5 * self.world.active_disaster.severity)
                    agent.needs["safety"] = max(0.0, agent.needs["safety"] - 5)
        if settlement and settlement.stats.get("epidemic_until", 0) >= self.day:
            agent.needs["health"] = max(0.0, agent.needs["health"] - 1.4 * difficulty)
        # Health recovery or decline.
        if agent.needs["hunger"] <= 0.5:
            agent.needs["health"] = max(0.0, agent.needs["health"] - 9.0)
        if agent.needs["thirst"] <= 0.5:
            agent.needs["health"] = max(0.0, agent.needs["health"] - 12.0)
        if agent.needs["hunger"] > 35 and agent.needs["thirst"] > 35 and agent.needs["energy"] > 12:
            recovery = 1.1
            if settlement and "medicine" in settlement.known_techs:
                recovery += 0.5
            if agent.needs["shelter"] > 55:
                recovery += 0.3
            agent.needs["health"] = min(100.0, agent.needs["health"] + recovery)
        elif agent.needs["energy"] < 8:
            agent.needs["health"] = max(0.0, agent.needs["health"] - 0.6)
        if agent.age_years > 55:
            agent.needs["health"] = max(0.0, agent.needs["health"] - 0.09)
        if agent.needs["health"] <= 22 and agent.needs["hunger"] < 30 and agent.inventory.get("herbs", 0) >= 1:
            agent.inventory["herbs"] -= 1
            agent.needs["health"] = min(100.0, agent.needs["health"] + 10)
            self._memory(agent, "survival", "Used herbs to treat a dangerous illness.", 0.55, 0.2, tags=["health"])
        for key in NEEDS:
            agent.needs[key] = round(max(0.0, min(100.0, agent.needs[key])), 1)

    def _on_disaster_start(self, disaster: Any) -> None:
        kind = disaster.kind
        center = disaster.center or (self.world.width // 2, self.world.height // 2)
        affected = 0
        if kind == "wildfire":
            for tile in self.world.tiles:
                if self.distance(tile.x, tile.y, center[0], center[1]) <= 3 and tile.terrain == "forest":
                    tile.resources["wood"] = 0.0
                    tile.resources.pop("game", None)
                    affected += 1
        elif kind == "flood":
            for settlement in self.settlements.values():
                if settlement.ruins:
                    continue
                if abs(settlement.position[0] - center[0]) <= 5 and abs(settlement.position[1] - center[1]) <= 5:
                    settlement.storage["food"] = round(settlement.storage.get("food", 0) * 0.7, 1)
                    settlement.storage["wood"] = round(settlement.storage.get("wood", 0) * 0.6, 1)
                    settlement.safety = max(0.0, settlement.safety - 12)
                    affected += 1
        elif kind == "epidemic":
            candidates = [s for s in self.settlements.values() if not s.ruins and s.population >= 3]
            if candidates:
                target = min(candidates, key=lambda s: self.distance(s.position[0], s.position[1], center[0], center[1]))
                target.stats["epidemic_until"] = self.day + disaster.remaining
                center = (target.position[0], target.position[1])
                affected = target.population
        self.add_event(
            "disaster", f"{kind.replace('_', ' ').title()} strikes",
            f"A {kind.replace('_', ' ')} of severity {disaster.severity:.2f} begins. "
            + (f"{affected} forest tiles are stripped." if kind == "wildfire" else
               f"{affected} settlement(s) are affected." if affected else
               "The whole region feels its effects."),
            importance=5, location=[center[0], center[1]],
            consequences=[f"The event is expected to last {disaster.remaining} days"],
            related={"disaster": kind, "severity": disaster.severity},
        )

    # -------------------------------------------------------------- demography
    def _demography_phase(self) -> None:
        rng = self.daily_rng("demography")
        # Deaths
        for agent in list(self.alive_agents()):
            reason = None
            if agent.needs["health"] <= 0.2:
                if agent.needs["hunger"] < 5:
                    reason = "starvation"
                elif agent.needs["thirst"] < 5:
                    reason = "dehydration"
                else:
                    reason = "illness or exposure"
            if reason is None and agent.age_years >= agent.lifespan:
                years_past = agent.age_years - agent.lifespan
                chance = min(0.9, 0.012 + years_past * 0.006)
                if rng.random() < chance:
                    reason = "old age"
            if reason is None and agent.age_years > 50 and rng.random() < 0.0007 * self.config.environmental_difficulty:
                reason = "sudden illness"
            if reason:
                self._kill_agent(agent, reason)
        # Pregnancies come due
        for agent in list(self.alive_agents()):
            if agent.pregnant and agent.pregnant.get("due_day", 10**9) <= self.day:
                self._deliver_baby(agent, rng)
        # Conceptions
        if len(self.alive_agents()) < self.config.max_population:
            handled: set[str] = set()
            for agent in self.alive_agents():
                if not agent.partner_id or agent.id in handled:
                    continue
                partner = self.agents.get(agent.partner_id)
                if not partner or not partner.alive or partner.id in handled:
                    continue
                handled.add(agent.id)
                handled.add(partner.id)
                couple = [agent, partner]
                bearer = next((a for a in couple if a.can_bear), None)
                sire = next((a for a in couple if a.can_sire), None)
                if not bearer or not sire:
                    self.gate_stats["no_fertile_role"] = self.gate_stats.get("no_fertile_role", 0) + 1
                    continue
                if bearer.last_birth_day and self.day - bearer.last_birth_day < 80:
                    self.gate_stats["cooldown"] = self.gate_stats.get("cooldown", 0) + 1
                    continue
                if bearer.needs["hunger"] < 32 or sire.needs["hunger"] < 32:
                    # Malnutrition suppresses fertility. Beyond realism this is
                    # the feedback that stops a settlement from breeding far
                    # past the food it can actually produce and then crashing.
                    self.gate_stats["hungry"] = self.gate_stats.get("hungry", 0) + 1
                    continue
                if bearer.needs["health"] < 55 or sire.needs["health"] < 45:
                    self.gate_stats["health"] = self.gate_stats.get("health", 0) + 1
                    continue
                settlement = self.settlements.get(bearer.settlement_id or "")
                if settlement and settlement.housing_capacity() < settlement.population:
                    self.gate_stats["housing"] = self.gate_stats.get("housing", 0) + 1
                    continue
                near = self.distance(agent.position[0], agent.position[1], partner.position[0], partner.position[1]) <= 1
                same_settlement = bool(
                    bearer.settlement_id and bearer.settlement_id == sire.settlement_id
                )
                if not near and not same_settlement:
                    self.gate_stats["apart"] = self.gate_stats.get("apart", 0) + 1
                    continue
                cohabiting = near or same_settlement
                food_ok = (
                    (settlement and settlement.storage.get("food", 0) > settlement.population * 0.7)
                    or (agent.inventory.get("food", 0) + partner.inventory.get("food", 0) > 6)
                )
                if not food_ok:
                    self.gate_stats["food"] = self.gate_stats.get("food", 0) + 1
                    continue
                rel = agent.relationships.get(partner.id)
                if rel and rel.affinity < 12:
                    self.gate_stats["affinity"] = self.gate_stats.get("affinity", 0) + 1
                    continue
                self.gate_stats["rolled"] = self.gate_stats.get("rolled", 0) + 1
                chance = 0.22 if cohabiting else 0.05
                chance *= 0.6 + min(0.4, self.config.resource_abundance * 0.2)
                if rng.random() < chance:
                    bearer.pregnant = {
                        "partner_id": sire.id, "due_day": self.day + 6,
                        "conceived_day": self.day, "father_id": sire.id,
                    }
                    bearer.needs["social"] = min(100, bearer.needs["social"] + 8)
                    self._memory(bearer, "family", f"Learned that a child with {sire.name} is expected.", 0.85, 0.7, participants=[sire.id], tags=["family", "pregnancy"])
                    self._memory(sire, "family", f"Learned that {bearer.name} expects their child.", 0.8, 0.7, participants=[bearer.id], tags=["family", "pregnancy"])
        # Aging (annual)
        for agent in self.alive_agents():
            agent.age_years = round((self.day - agent.birth_day) / DAYS_PER_YEAR, 2)

    def _kill_agent(self, agent: Agent, reason: str) -> None:
        if not agent.alive:
            return
        agent.alive = False
        agent.death_day = self.day
        agent.death_cause = reason
        agent.state = "dead"
        agent.action = {"kind": "dead", "label": f"Died of {reason}", "phase": "done"}
        self.deaths += 1
        settlement = self.settlements.get(agent.settlement_id or "")
        was_leader = bool(settlement and settlement.leader_id == agent.id)
        if settlement:
            settlement.member_ids = [aid for aid in settlement.member_ids if aid != agent.id]
            if was_leader:
                settlement.leader_id = None
                settlement.government["leader_id"] = None
            settlement.occupation.pop(agent.id, None)
        # Inheritance: partner, then children, then settlement commons.
        heirs: list[Agent] = []
        if agent.partner_id and agent.partner_id in self.agents and self.agents[agent.partner_id].alive:
            heirs.append(self.agents[agent.partner_id])
        heirs.extend(self.agents[cid] for cid in agent.child_ids if cid in self.agents and self.agents[cid].alive)
        if heirs:
            share_items = {k: v for k, v in agent.inventory.items() if v > 0}
            for item, amount in share_items.items():
                portion = amount / len(heirs)
                for heir in heirs:
                    heir.add_item(item, portion)
                    self._memory(heir, "family", f"Inherited {portion:.1f} {item} from {agent.name}.", 0.6, -0.1, participants=[agent.id], tags=["inheritance", "family"])
            inherited = True
        else:
            inherited = False
            if settlement:
                for item, amount in agent.inventory.items():
                    settlement.storage[item] = round(settlement.storage.get(item, 0) + amount, 2)
        # A death has to free the survivor's partnership slot. Without this the
        # widow keeps a dangling partner_id for the rest of their life: they
        # never remarry (partner search requires partner_id is None) and the
        # conception loop skips them because their partner is dead. Over a long
        # run that quietly sterilises the whole population.
        widow = self.agents.get(agent.partner_id) if agent.partner_id else None
        if widow and widow.alive:
            widow.partner_id = None
            widow.needs["social"] = max(0.0, widow.needs["social"] - 12)
            self._memory(
                widow, "family", f"Lost {agent.name}, their partner.", 1.0, -1.0,
                participants=[agent.id], tags=["family", "grief"],
            )
        for other in self.alive_agents():
            rel = other.relationships.get(agent.id)
            if rel and rel.affinity > 25:
                other.needs["social"] = min(100, other.needs["social"] + 4)
                self._memory(other, "social", f"Lost {agent.name}, with whom they shared a meaningful bond.", 0.8, -0.8, participants=[agent.id], tags=["death", "grief"])
                rel.add_history(self.day, f"Died of {reason}", -1.0)
        importance = 5 if (was_leader or agent.founder_of or agent.generation == 0) else 3
        children_names = [self.agents[cid].name for cid in agent.child_ids if cid in self.agents]
        consequences = [f"Age {agent.age}; cause: {reason}"]
        if was_leader:
            consequences.append("The settlement has no leader")
        if children_names:
            consequences.append(f"Survived by {', '.join(children_names[:4])}")
        if inherited:
            consequences.append("Possessions passed to family")
        elif settlement:
            consequences.append("Possessions entered the settlement commons")
        self.add_event(
            "demography", f"{agent.name} dies",
            f"{agent.name} ({agent.occupation}, generation {agent.generation}) died on day {self.day} of {reason} at age {agent.age}.",
            importance=importance, participants=[agent.id],
            location=list(agent.position),
            location_name=settlement.name if settlement else None,
            consequences=consequences,
            related={"agent_id": agent.id, "cause": reason, "settlement_id": settlement.id if settlement else None},
        )

    def _deliver_baby(self, bearer: Agent, rng: random.Random) -> None:
        father = self.agents.get((bearer.pregnant or {}).get("father_id", ""))
        if father is None:
            father = self.agents.get(bearer.partner_id or "")
        # A dead father does not cancel a pregnancy. The old code returned here,
        # so every child conceived by a man who later died was silently
        # discarded — a second, quieter way the population sterilised itself.
        parents = (bearer, father) if father is not None else None
        father_name = father.name if father is not None else "an unrecorded father"
        father_participant = [father.id] if father is not None else []
        settlement = self.settlements.get(bearer.settlement_id or "")
        survival = 0.955
        if settlement and "medicine" in settlement.known_techs:
            survival += 0.025
        survival -= max(0.0, (self.config.environmental_difficulty - 1.0)) * 0.06
        if bearer.needs["health"] < 50:
            survival -= 0.12
        if rng.random() > survival:
            self.add_event(
                "demography", "A child is lost at birth",
                f"{bearer.name} gave birth, but the child did not survive. The household mourns.",
                importance=4, participants=[bearer.id] + father_participant, location=list(bearer.position),
                location_name=settlement.name if settlement else None,
            )
            bearer.pregnant = None
            bearer.last_birth_day = self.day
            self._memory(bearer, "family", "Lost a child at birth.", 0.95, -0.95, participants=father_participant, tags=["family", "grief"])
            return
        used_names = {a.name for a in self.agents.values()}
        gender = rng.choices(["woman", "man", "nonbinary"], weights=[49, 49, 2])[0]
        name = pick_name(rng, gender, used_names)
        child = make_agent(
            rng=rng, agent_id=self._next_agent_id(), name=name,
            position=(bearer.position[0], bearer.position[1]),
            origin_group=bearer.origin_group,
            distribution=self.config.personality_distribution,
            cooperation_bias=self.config.cooperation_bias,
            abundance=self.config.resource_abundance,
            generation=max(bearer.generation, father.generation if father is not None else 0) + 1,
            age_years=0.0, parents=parents, birth_day=self.day,
            family_id=bearer.family_id or (father.family_id if father is not None else None),
        )
        child.birth_location = list(bearer.position)
        child.home_tile = list(bearer.position)
        child.settlement_id = bearer.settlement_id
        father_techs = father.known_techs if father is not None else []
        father_languages = father.known_languages if father is not None else []
        child.known_techs = sorted(set(bearer.known_techs) | set(father_techs))
        child.known_languages = list(dict.fromkeys(bearer.known_languages + father_languages))
        child.personal_vocabulary = dict(bearer.personal_vocabulary)
        if father is not None:
            child.personal_vocabulary.update(father.personal_vocabulary)
        child.inventory = {k: 0.0 for k in child.inventory}
        child.state = "newborn"
        child.current_goal = {"kind": "childhood", "label": "Grow up and learn", "progress": 0.0}
        self.agents[child.id] = child
        self.births += 1
        bearer.pregnant = None
        bearer.last_birth_day = self.day
        bearer.child_ids.append(child.id)
        if father is not None:
            father.child_ids.append(child.id)
        if bearer.family_id and bearer.family_id in self.families:
            family = self.families[bearer.family_id]
            family["member_ids"].append(child.id)
            family["children"].append(child.id)
            child.family_id = family["id"]
        if settlement:
            settlement.member_ids.append(child.id)
            settlement.occupation[child.id] = "Child"
        self._memory(bearer, "family", f"Gave birth to {child.name}.", 1.0, 0.95, participants=[child.id] + father_participant, tags=["family", "birth"])
        if father is not None:
            self._memory(father, "family", f"Became a parent to {child.name}.", 0.95, 0.9, participants=[child.id, bearer.id], tags=["family", "birth"])
        self.add_event(
            "demography", f"Newborn: {child.name}",
            f"{bearer.name} and {father_name} welcomed {child.name} into generation {child.generation}. "
            f"Born in {settlement.name if settlement else 'the open country'}.",
            importance=4, participants=[child.id, bearer.id] + father_participant,
            location=list(bearer.position), location_name=settlement.name if settlement else None,
            consequences=[f"Population is now {len(self.alive_agents())}"],
            related={"child_id": child.id, "family_id": child.family_id, "generation": child.generation},
        )
        if settlement:
            self._culture_from_event(settlement, "birth", child=child, parents=[bearer, father])

    # ------------------------------------------------------------ persistence
    def snapshot(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "config": self.config.model_dump(mode="json"),
            "tick": self.tick,
            "day": self.day,
            "status": self.status,
            "seed": self.seed,
            "agents": [a.to_snapshot() for a in self.agents.values()],
            "settlements": [s.to_snapshot() for s in self.settlements.values()],
            "cultures": [c.to_dict() for c in self.cultures.values()],
            "languages": [dict(l.to_dict(), loans_all=l.loans, lexicon=l.lexicon) for l in self.languages.values()],
            "families": self.families,
            "run_techs": sorted(self.run_techs),
            "tech_discoveries": self.tech_discoveries,
            "counters": self.counters,
            "births": self.births,
            "deaths": self.deaths,
            "conflicts": self.conflicts,
            "trades": self.trades,
            "metrics_history": self.metrics_history[-2500:],
            "latest_metrics": self.latest_metrics,
            "events": self.events[-400:],
            "recent_transactions": self.recent_transactions[-200:],
            "world_state": {
                "resources": [t.resources for t in self.world.tiles],
                "owners": [t.owner for t in self.world.tiles],
                "weather": self.world.weather,
                "weather_severity": self.world.weather_severity,
                "active_disaster": self.world.active_disaster.to_dict() if self.world.active_disaster else None,
            },
        }

    def _restore(self, state: dict[str, Any]) -> None:
        self.tick = int(state["tick"])
        self.day = int(state["day"])
        self.status = state.get("status", "paused")
        self.agents = {raw["id"]: Agent.from_snapshot(raw) for raw in state.get("agents", [])}
        self.settlements = {raw["id"]: Settlement.from_snapshot(raw) for raw in state.get("settlements", [])}
        self.cultures = {raw["id"]: Culture.from_dict(raw) for raw in state.get("cultures", [])}
        self.languages = {}
        for raw in state.get("languages", []):
            lexicon = raw.get("lexicon", {})
            lang = Language.from_dict({**raw, "lexicon": lexicon})
            loans = raw.get("loans_all") or raw.get("loans", [])
            lang.loans = loans
            self.languages[lang.id] = lang
        self.families = state.get("families", {})
        self.run_techs = set(state.get("run_techs", []))
        self.tech_discoveries = state.get("tech_discoveries", {})
        self.counters = state.get("counters", self.counters)
        self.births = int(state.get("births", 0))
        self.deaths = int(state.get("deaths", 0))
        self.conflicts = int(state.get("conflicts", 0))
        self.trades = int(state.get("trades", 0))
        self.metrics_history = state.get("metrics_history", [])
        self.latest_metrics = state.get("latest_metrics", {})
        self.events = state.get("events", [])
        self.outbox = []
        self.recent_transactions = state.get("recent_transactions", [])
        world_state = state.get("world_state", {})
        resources = world_state.get("resources", [])
        owners = world_state.get("owners", [])
        for index, tile in enumerate(self.world.tiles):
            if index < len(resources):
                tile.resources = resources[index]
            if index < len(owners):
                tile.owner = owners[index]
        self.world.weather = world_state.get("weather", "Clear")
        self.world.weather_severity = world_state.get("weather_severity", 0.0)
        disaster = world_state.get("active_disaster")
        if disaster:
            from .world import Disaster
            self.world.active_disaster = Disaster(
                kind=disaster["kind"], severity=disaster["severity"],
                remaining=disaster["remaining_days"], center=tuple(disaster["center"]) if disaster.get("center") else None,
            )
        for agent in self.agents.values():
            if agent.alive:
                agent.age_years = round(max(0.0, (self.day - agent.birth_day) / DAYS_PER_YEAR), 2)

    @classmethod
    def from_snapshot(cls, run_id: str, state: dict[str, Any]) -> "SimulationEngine":
        import copy

        # Deep-copy so a live engine and its restored copy never share mutable
        # action, settlement or memory structures.
        state = copy.deepcopy(state)
        config = WorldConfig(**state["config"])
        return cls(run_id=run_id, config=config, state=state)

    # --------------------------------------------------------------- queries
    def agent_danger(self, agent: Agent) -> float:
        danger = 0.0
        settlement = self.settlements.get(agent.settlement_id or "")
        if settlement:
            danger += max(0.0, 55 - settlement.safety) * 0.35
        for other in self.alive_agents():
            if other.id == agent.id:
                continue
            if abs(other.position[0] - agent.position[0]) <= 2 and abs(other.position[1] - agent.position[1]) <= 2:
                rel = agent.relationships.get(other.id)
                if rel and rel.affinity < -25:
                    danger += 14 + abs(rel.affinity) * 0.12
                elif rel and rel.type == "enemy":
                    danger += 8
        if self.world.active_disaster and self.world.active_disaster.center:
            cx, cy = self.world.active_disaster.center
            if self.distance(agent.position[0], agent.position[1], cx, cy) <= 4:
                danger += self.world.active_disaster.severity * 18
        if settlement and settlement.stats.get("at_war_with"):
            danger += 8
        return round(min(100.0, danger), 1)

    def exploration_target(self, agent: Agent, rng: random.Random) -> tuple[int, int] | None:
        for _ in range(12):
            angle = rng.uniform(0, 6.283185)
            distance = rng.randint(7, 15)
            x = int(agent.position[0] + math.cos(angle) * distance)
            y = int(agent.position[1] + math.sin(angle) * distance)
            tile = self.world.tile(x, y)
            if tile and tile.passable and tile.terrain not in ("mountain",):
                return (x, y)
        return None

    # ---------------------------------------------------------- serialization
    def _event_view(self, event: dict[str, Any]) -> dict[str, Any]:
        return event

    def to_state(self, recent_events: int = 120) -> dict[str, Any]:
        settlements = [s.to_summary(self.agents) for s in self.settlements.values()]
        culture_view = [c.to_dict() for c in self.cultures.values()]
        language_view = [l.to_dict() for l in self.languages.values()]
        return {
            "run": {
                "id": self.run_id,
                "world_name": self.config.world_name,
                "seed": self.seed,
                "day": self.day,
                "tick": self.tick,
                "year": self.year,
                "season": self.season,
                "day_of_season": self.day_of_season,
                "time_label": self.time_label,
                "status": self.status,
                "weather": getattr(self, "weather", self.world.weather),
                "disaster": self.world.active_disaster.to_dict() if self.world.active_disaster else None,
                "config": self.config.model_dump(mode="json"),
                "population": len(self.alive_agents()),
                "settlements": len([s for s in self.settlements.values() if not s.ruins]),
                "births": self.births,
                "deaths": self.deaths,
                "techs": sorted(self.run_techs),
                "era": current_era(self.run_techs),
                "language_count": len(self.languages),
                "culture_count": len(self.cultures),
                "family_count": len(self.families),
            },
            "metrics": self.latest_metrics,
            "agents": [a.to_summary() for a in self.agents.values()],
            "settlements": settlements,
            "cultures": culture_view,
            "languages": language_view,
            "families": list(self.families.values()),
            "events": self.events[-recent_events:],
            "metrics_history": self.metrics_history[-600:],
            "technology": {
                "era": current_era(self.run_techs),
                "known": sorted(self.run_techs),
                "discoveries": self.tech_discoveries,
            },
            "transactions": self.recent_transactions[-60:],
            "world": {
                "width": self.world.width, "height": self.world.height,
                "seed": self.world.seed, "land_ratio": round(self.world.land_ratio, 3),
                "rivers": self.world.rivers, "lakes": self.world.lakes,
                "biomes": self.world.biome_counts(),
                "start_sites": self.world.start_sites,
                "disaster": self.world.active_disaster.to_dict() if self.world.active_disaster else None,
            },
        }

    def tick_payload(self, include_events: bool = True) -> dict[str, Any]:
        alive = self.alive_agents()
        return {
            "type": "tick",
            "run_id": self.run_id,
            "tick": self.tick,
            "day": self.day,
            "year": self.year,
            "season": self.season,
            "day_of_season": self.day_of_season,
            "time_label": self.time_label,
            "weather": getattr(self, "weather", self.world.weather),
            "status": self.status,
            "population": len(alive),
            "births": self.births,
            "deaths": self.deaths,
            "metrics": self.latest_metrics,
            "agents": [a.to_summary() for a in alive],
            "settlements": [s.to_summary(self.agents) for s in self.settlements.values() if not s.ruins],
            "events": self.drain_outbox(30) if include_events else [],
        }

    def agent_detail(self, agent_id: str) -> dict[str, Any] | None:
        agent = self.agents.get(agent_id)
        if not agent:
            return None
        data = agent.to_detail()
        relationships = []
        for rel in data["relationships"]:
            other = self.agents.get(rel["other_id"])
            rel["other_name"] = other.name if other else "Unknown"
            rel["other_alive"] = other.alive if other else False
            rel["social_memories"] = agent.memory.social_history(rel["other_id"])
            relationships.append(rel)
        data["relationships"] = relationships
        family = self.families.get(agent.family_id or "")
        family_members = []
        if family:
            for member_id in family.get("member_ids", []):
                member = self.agents.get(member_id)
                if member:
                    family_members.append({
                        "id": member.id, "name": member.name, "age": member.age,
                        "alive": member.alive, "generation": member.generation,
                        "relation": "self" if member.id == agent.id else "kin",
                    })
        data["family"] = {**family, "members_detail": family_members} if family else None
        data["parents"] = [
            {"id": pid, "name": self.agents[pid].name, "alive": self.agents[pid].alive}
            for pid in agent.parent_ids if pid in self.agents
        ]
        data["children"] = [
            {"id": cid, "name": self.agents[cid].name, "age": self.agents[cid].age, "alive": self.agents[cid].alive}
            for cid in agent.child_ids if cid in self.agents
        ]
        data["partner"] = (
            {"id": agent.partner_id, "name": self.agents[agent.partner_id].name, "alive": self.agents[agent.partner_id].alive}
            if agent.partner_id in self.agents else None
        )
        settlement = self.settlements.get(agent.settlement_id or "")
        data["settlement"] = {"id": settlement.id, "name": settlement.name} if settlement else None
        data["herbs_known"] = agent.needs.get("health", 0) < 60
        return data

    def settlement_detail(self, settlement_id: str) -> dict[str, Any] | None:
        settlement = self.settlements.get(settlement_id)
        if not settlement:
            return None
        return settlement.to_detail(self.agents, self.cultures, self.languages)

    def settlement_by_leader(self, agent_id: str) -> Settlement | None:
        for settlement in self.settlements.values():
            if settlement.leader_id == agent_id:
                return settlement
        return None

    # ---------------------------------------------------------------- metrics
    def _daily_metric(self) -> None:
        self._update_metrics()
        if self.day % 5 == 0:
            for settlement in self.settlements.values():
                if settlement.ruins:
                    continue
                settlement.history.append({
                    "day": self.day,
                    "population": settlement.population,
                    "food": round(float(settlement.storage.get("food", 0)), 1),
                    "wood": round(float(settlement.storage.get("wood", 0)), 1),
                    "happiness": round(settlement.happiness),
                    "stability": round(settlement.stability),
                    "leader_id": settlement.leader_id,
                    "buildings": len(settlement.buildings),
                    "government": settlement.government.get("system", "tribal"),
                })
                if len(settlement.history) > 160:
                    settlement.history = settlement.history[-160:]

    def _update_metrics(self, initial: bool = False) -> None:
        alive = self.alive_agents()
        settlements = [s for s in self.settlements.values() if not s.ruins]
        wealth = wealth_distribution(alive, self.settlements)
        avg_happiness = round(sum(a.happiness() for a in alive) / max(1, len(alive)), 1)
        avg_health = round(sum(a.needs["health"] for a in alive) / max(1, len(alive)), 1)
        avg_trust = 0.0
        rel_count = 0
        for agent in alive:
            for rel in agent.relationships.values():
                avg_trust += rel.trust
                rel_count += 1
        avg_trust = round(avg_trust / max(1, rel_count), 1)
        food_agents = sum(a.inventory.get("food", 0) for a in alive)
        food_settlements = sum(s.storage.get("food", 0) for s in settlements)
        water_agents = sum(a.inventory.get("water", 0) for a in alive)
        water_settlements = sum(s.storage.get("water", 0) for s in settlements)
        children = sum(1 for a in alive if a.age < 16)
        elders = sum(1 for a in alive if a.age >= 55)
        generations = len({a.generation for a in alive})
        trades_today = sum(1 for t in self.recent_transactions if t.get("day") == self.day)
        stability = round(sum(s.stability for s in settlements) / max(1, len(settlements)), 1)
        self.latest_metrics = {
            "day": self.day,
            "year": self.year,
            "season": self.season,
            "population": len(alive),
            "births": self.births,
            "deaths": self.deaths,
            "settlements": len(settlements),
            "buildings": sum(len(s.buildings) for s in settlements),
            "avg_happiness": avg_happiness,
            "avg_health": avg_health,
            "avg_trust": avg_trust,
            "food": round(food_agents + food_settlements, 1),
            "food_stores": round(food_settlements, 1),
            "water": round(water_agents + water_settlements, 1),
            "inequality": wealth["gini"],
            "wealth_median": wealth["median"],
            "wealth_max": wealth["rich"],
            "tech_count": len(self.run_techs),
            "era": current_era(self.run_techs),
            "conflicts": self.conflicts,
            "trades": self.trades,
            "trades_today": trades_today,
            "stability": stability,
            "children": children,
            "elders": elders,
            "generations": generations,
            "families": len(self.families),
            "languages": len(self.languages),
        }
        if not initial:
            self.metrics_history.append({
                "day": self.day,
                **{k: v for k, v in self.latest_metrics.items() if k != "day"},
            })
            if len(self.metrics_history) > 3000:
                self.metrics_history = self.metrics_history[-3000:]

    # ------------------------------------------------------------ for API
    def technology_view(self) -> dict[str, Any]:
        from .tech import tech_tree_view
        progress: dict[str, float] = {}
        for agent in self.alive_agents():
            for tech, value in agent.research_progress.items():
                progress[tech] = max(progress.get(tech, 0.0), value)
        return {
            "era": current_era(self.run_techs),
            "known": sorted(self.run_techs),
            "tree": tech_tree_view(self.run_techs, progress),
            "discoveries": self.tech_discoveries,
            "researching": [
                {"agent_id": a.id, "name": a.name, "tech": a.research_target, "progress": round(a.research_progress.get(a.research_target or "", 0), 1)}
                for a in self.alive_agents() if a.research_target
            ],
        }

    def history_view(self, category: str | None = None, limit: int = 200, before_day: int | None = None) -> list[dict[str, Any]]:
        events = self.events
        if category and category != "all":
            events = [e for e in events if e["category"] == category]
        if before_day is not None:
            events = [e for e in events if e["day"] < before_day]
        return events[-limit:]
