"""Procedural world generation and environmental simulation."""
from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field, field_validator

from . import noise
from .constants import (
    DAYS_PER_YEAR, DAYS_PER_SEASON, SEASON_GROWTH, SEASON_TEMP, SEASONS,
    WEATHER, WEATHER_GROWTH,
)

Preset = Literal["fertile_valley", "desert_world", "frozen_continent", "island_civilization", "random_world"]
Climate = Literal["temperate", "warm", "cold", "arid"]


class WorldConfig(BaseModel):
    world_name: str = Field(default="Aureth", min_length=1, max_length=64)
    preset: Preset = "fertile_valley"
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)
    width: int = Field(default=72, ge=40, le=128)
    height: int = Field(default=48, ge=28, le=96)
    initial_population: int = Field(default=30, ge=5, le=300)
    climate: Climate = "temperate"
    resource_abundance: float = Field(default=1.0, ge=0.3, le=2.0)
    environmental_difficulty: float = Field(default=1.0, ge=0.4, le=2.0)
    personality_distribution: Literal["balanced", "cooperative", "competitive", "ambitious", "random"] = "balanced"
    starting_technology: Literal["none", "fire", "basic_tools", "early_agriculture"] = "none"
    starting_groups: int = Field(default=3, ge=1, le=6)
    cooperation_bias: float = Field(default=0.0, ge=-0.5, le=0.5)
    no_currency: bool = False
    no_leader: bool = False
    asymmetric_groups: bool = False
    max_population: int = Field(default=220, ge=10, le=2000)
    notation: str = Field(default="", max_length=280)

    @field_validator("world_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip() or "Aureth"


@dataclass
class Tile:
    x: int
    y: int
    terrain: str
    elevation: float
    moisture: float
    temperature: float
    fertility: float
    water: float
    river: bool = False
    resources: dict[str, float] = field(default_factory=dict)
    owner: str | None = None

    @property
    def passable(self) -> bool:
        return self.terrain not in ("deep_ocean", "ocean", "lake")

    @property
    def freshwater(self) -> bool:
        return self.river or self.terrain == "lake" or self.water >= 0.72

    @property
    def buildable(self) -> bool:
        return self.passable and self.terrain not in ("coast", "swamp")


@dataclass
class Disaster:
    kind: str
    severity: float
    remaining: int
    center: tuple[int, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "severity": round(self.severity, 2),
            "remaining_days": self.remaining,
            "center": list(self.center) if self.center else None,
        }


class World:
    def __init__(self, config: WorldConfig, seed: int):
        self.config = config
        self.seed = seed
        self.width = config.width
        self.height = config.height
        self.tiles: list[Tile] = []
        self.start_sites: list[dict[str, Any]] = []
        self.land_ratio = 0.0
        self.active_disaster: Disaster | None = None
        self.weather = "Clear"
        self.weather_severity = 0.0
        self.rivers = 0
        self.lakes = 0

    # ---------------------------------------------------------------- lookups
    def idx(self, x: int, y: int) -> int:
        return y * self.width + x

    def tile(self, x: int, y: int) -> Tile | None:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.tiles[self.idx(x, y)]
        return None

    def neighbors(self, x: int, y: int) -> list[Tile]:
        out = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            t = self.tile(x + dx, y + dy)
            if t is not None:
                out.append(t)
        return out

    def tile_or_raise(self, x: int, y: int) -> Tile:
        tile = self.tile(x, y)
        if tile is None:
            raise ValueError(f"Tile ({x},{y}) is outside the world")
        return tile

    def season(self, day: int) -> str:
        return SEASONS[((max(1, day) - 1) // DAYS_PER_SEASON) % 4]

    def year(self, day: int) -> int:
        return ((max(1, day) - 1) // DAYS_PER_YEAR) + 1

    def day_of_year(self, day: int) -> int:
        return ((max(1, day) - 1) % DAYS_PER_YEAR) + 1

    def effective_temperature(self, tile: Tile, day: int) -> float:
        season = self.season(day)
        return max(0.0, min(1.2, tile.temperature + SEASON_TEMP[season] + (0.04 if self.weather == "Drought" else 0.0)))

    def water_at(self, tile: Tile) -> bool:
        return tile.freshwater

    # ----------------------------------------------------------- generation
    @classmethod
    def generate(cls, config: WorldConfig) -> "World":
        seed = config.seed if config.seed is not None else random.SystemRandom().randint(0, 2**31 - 1)
        world = cls(config, seed)
        world._generate()
        return world

    def _generate(self) -> None:
        cfg = self.config
        seed = self.seed
        w, h = self.width, self.height
        rng = random.Random(seed)
        preset_cfg = {
            "fertile_valley": dict(land=0.64, mountain_q=0.90, moist=0.10, temp=0.04, forest=0.20),
            "desert_world": dict(land=0.58, mountain_q=0.93, moist=-0.16, temp=0.20, forest=-0.10),
            "frozen_continent": dict(land=0.58, mountain_q=0.86, moist=0.0, temp=-0.32, forest=0.0),
            "island_civilization": dict(land=0.36, mountain_q=0.88, moist=0.12, temp=0.06, forest=0.16),
            "random_world": dict(land=rng.uniform(0.45, 0.66), mountain_q=rng.uniform(0.85, 0.94), moist=0.02, temp=0.02, forest=0.05),
        }[cfg.preset]
        climate_shift = {"temperate": 0.0, "warm": 0.13, "cold": -0.16, "arid": 0.1}[cfg.climate]
        moisture_shift = cfg.climate == "arid" and -0.06 or cfg.climate == "warm" and -0.02 or cfg.climate == "cold" and -0.01 or 0.0

        raw: list[tuple[float, float]] = []
        for y in range(h):
            for x in range(w):
                nx, ny = x / max(1, w - 1), y / max(1, h - 1)
                base = noise.fbm(nx * w * 0.055, ny * h * 0.055, seed, 5)
                ridges = noise.ridge_noise(nx * w * 0.034, ny * h * 0.034, seed + 771, 4)
                detail = noise.fbm(nx * w * 0.18, ny * h * 0.18, seed + 33, 3)
                elevation = base * 0.63 + ridges * 0.28 + detail * 0.09
                # Mild continental warp and edge falloff keeps coasts coherent.
                dx, dy = nx - 0.5, ny - 0.5
                edge = min(nx, 1 - nx, ny, 1 - ny)
                elevation -= max(0.0, 0.045 - edge) * 1.9
                if cfg.preset == "island_civilization":
                    elevation -= (dx * dx + dy * dy) * 0.52
                    elevation = elevation * 0.92 + 0.06
                elif cfg.preset != "random_world":
                    elevation -= (dx * dx + dy * dy) * 0.055
                moisture = noise.fbm(nx * w * 0.043 + 91, ny * h * 0.043 + 17, seed + 500, 4)
                moisture += moisture_shift + preset_cfg["moist"]
                moisture = max(0.0, min(1.0, moisture))
                raw.append((elevation, moisture))

        elevations = sorted(e[0] for e in raw)
        target_land = preset_cfg["land"]
        sea_level = elevations[int((1 - target_land) * (len(elevations) - 1))]
        mountain_threshold = elevations[int(preset_cfg["mountain_q"] * (len(elevations) - 1))]

        # Place lakes on low-lying inland candidate points.
        lake_centers: list[tuple[int, int]] = []
        land_candidates = [
            (t[0], t[1]) for t in raw
        ]
        attempts = 0
        lake_target = max(1, (w * h) // 1400)
        while len(lake_centers) < lake_target and attempts < 120:
            attempts += 1
            x = rng.randint(3, w - 4)
            y = rng.randint(3, h - 4)
            elev, moist = raw[self.idx(x, y)]
            if elev < sea_level + 0.035:
                continue
            if any((x - cx) ** 2 + (y - cy) ** 2 < 64 for cx, cy in lake_centers):
                continue
            lake_centers.append((x, y))
        lake_tiles: set[tuple[int, int]] = set()
        for cx, cy in lake_centers:
            radius = rng.choice([1, 1, 2, 2, 3])
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if dx * dx + dy * dy <= radius * radius + rng.random() * 1.2:
                        x, y = cx + dx, cy + dy
                        if 0 <= x < w and 0 <= y < h:
                            lake_tiles.add((x, y))

        tiles: list[Tile] = []
        for y in range(h):
            for x in range(w):
                elev, moist = raw[self.idx(x, y)]
                temp = (
                    0.80 - abs((y / max(1, h - 1)) - 0.5) * 0.52
                    + preset_cfg["temp"] + climate_shift
                    + (noise.value_noise(x * 0.11, y * 0.11, seed + 2) - 0.5) * 0.12
                    - max(0.0, elev - 0.55) * 0.5
                )
                temp = max(0.03, min(1.15, temp))
                if (x, y) in lake_tiles:
                    terrain = "lake"
                elif elev < sea_level - 0.09:
                    terrain = "deep_ocean"
                elif elev < sea_level:
                    terrain = "ocean"
                elif elev < sea_level + 0.018:
                    terrain = "coast"
                elif elev > mountain_threshold:
                    terrain = "mountain"
                elif temp < 0.19:
                    terrain = "tundra"
                elif moist < 0.31 and temp > 0.33:
                    terrain = "desert"
                elif moist > 0.72 and elev < sea_level + 0.11:
                    terrain = "swamp"
                elif moist > 0.54 + preset_cfg["forest"]:
                    terrain = "forest"
                elif moist > 0.43:
                    terrain = "fertile"
                else:
                    terrain = "plains"
                moisture = min(1.0, moist + (0.08 if terrain in ("river", "lake") else 0.0))
                tile = Tile(
                    x=x, y=y, terrain=terrain, elevation=round(elev, 4),
                    moisture=round(moisture, 4), temperature=round(temp, 4),
                    fertility=0.0, water=0.0,
                )
                tiles.append(tile)
        self.tiles = tiles
        self.land_ratio = sum(1 for t in tiles if t.passable) / len(tiles)

        self._carve_rivers(rng, sea_level)
        self._compute_water_access()
        self._compute_fertility(rng)
        self._distribute_resources(rng)
        self._choose_start_sites(rng)

    def _carve_rivers(self, rng: random.Random, sea_level: float) -> None:
        w, h = self.width, self.height
        sources = [t for t in self.tiles if t.passable and t.terrain in ("mountain", "forest", "fertile") and t.elevation > sea_level + 0.16]
        sources.sort(key=lambda t: t.elevation, reverse=True)
        if not sources:
            return
        river_target = max(2, (w * h) // 460)
        chosen: list[tuple[int, int]] = []
        for src in sources[: max(40, len(sources) // 3)]:
            if len(chosen) >= river_target:
                break
            if any((src.x - cx) ** 2 + (src.y - cy) ** 2 < 36 for cx, cy in chosen):
                continue
            chosen.append((src.x, src.y))
            x, y = src.x, src.y
            path: list[tuple[int, int]] = []
            visited: set[tuple[int, int]] = set()
            for _ in range(max(w, h) * 2):
                if (x, y) in visited:
                    break
                visited.add((x, y))
                path.append((x, y))
                current = self.tile_or_raise(x, y)
                if current.terrain in ("ocean", "lake", "deep_ocean") or (len(path) > 3 and current.freshwater):
                    break
                neighbors = [n for n in self.neighbors(x, y) if n.passable or n.terrain == "lake"]
                if not neighbors:
                    break
                # Prefer heading downhill, but keep a little momentum so rivers
                # do not immediately stall in local depressions.
                downhill = [n for n in neighbors if n.elevation < current.elevation + 0.002]
                pool = downhill if downhill and rng.random() < 0.88 else neighbors
                nxt = min(pool, key=lambda n: n.elevation + rng.random() * 0.012)
                # Slight wander makes valleys honest rather than ruler-straight.
                if rng.random() < 0.16:
                    nxt = rng.choice(neighbors)
                x, y = nxt.x, nxt.y
            if len(path) < 6:
                continue
            for px, py in path:
                tile = self.tile_or_raise(px, py)
                if tile.terrain in ("ocean", "deep_ocean", "lake"):
                    continue
                tile.river = True
                tile.terrain = "river"
                tile.water = 1.0
            self.rivers += 1
        self.lakes = sum(1 for t in self.tiles if t.terrain == "lake")

    def _compute_water_access(self) -> None:
        w, h = self.width, self.height
        dist = [[-1] * w for _ in range(h)]
        queue: deque[tuple[int, int]] = deque()
        for t in self.tiles:
            if t.terrain == "lake" or t.river:
                dist[t.y][t.x] = 0
                queue.append((t.x, t.y))
        while queue:
            x, y = queue.popleft()
            d = dist[y][x]
            if d >= 6:
                continue
            for n in self.neighbors(x, y):
                if not n.passable:
                    continue
                if dist[n.y][n.x] == -1:
                    dist[n.y][n.x] = d + 1
                    queue.append((n.x, n.y))
        for t in self.tiles:
            d = dist[t.y][t.x]
            if t.freshwater:
                t.water = 1.0
            elif d >= 0:
                t.water = max(0.0, 1.0 - d / 6.2)
                if t.terrain == "desert" and t.river:
                    t.water = 1.0
            else:
                t.water = 0.0
            # Coast is adjacent to salt water, useful for fish but not drinking.
            if t.terrain == "coast":
                t.water = max(t.water, 0.15)

    def _compute_fertility(self, rng: random.Random) -> None:
        base = {
            "fertile": 0.72, "plains": 0.46, "forest": 0.5, "river": 0.7,
            "swamp": 0.38, "coast": 0.22, "desert": 0.08, "mountain": 0.06,
            "tundra": 0.1, "lake": 0.0, "ocean": 0.0, "deep_ocean": 0.0,
        }
        for t in self.tiles:
            f = base.get(t.terrain, 0.2) + t.water * 0.24 + (t.moisture - 0.5) * 0.2
            f += (rng.random() - 0.5) * 0.08
            if t.temperature < 0.2:
                f -= 0.08
            if t.temperature > 0.95:
                f -= 0.05
            t.fertility = round(max(0.0, min(1.0, f)), 3)

    def _distribute_resources(self, rng: random.Random) -> None:
        abundance = self.config.resource_abundance
        for t in self.tiles:
            res: dict[str, float] = {}
            if t.terrain in ("ocean", "coast", "deep_ocean"):
                if t.terrain == "coast" and rng.random() < 0.35:
                    res["fish"] = round(rng.uniform(3, 9) * abundance, 1)
            elif t.terrain == "lake":
                res["fish"] = round(rng.uniform(5, 14) * abundance, 1)
            elif t.terrain == "river":
                res["fish"] = round(rng.uniform(4, 11) * abundance, 1)
                res["clay"] = round(rng.uniform(1, 4) * abundance, 1)
            elif t.terrain == "forest":
                res["wood"] = round(rng.uniform(18, 46) * abundance, 1)
                res["game"] = round(rng.uniform(1.5, 5) * abundance, 1)
                if rng.random() < 0.25:
                    res["herbs"] = round(rng.uniform(1, 4) * abundance, 1)
                if rng.random() < 0.2:
                    res["berries"] = round(rng.uniform(1, 3) * abundance, 1)
            elif t.terrain == "mountain":
                res["stone"] = round(rng.uniform(28, 70) * abundance, 1)
                if rng.random() < 0.42:
                    res["ore"] = round(rng.uniform(2, 9) * abundance, 1)
            elif t.terrain == "desert":
                res["salt"] = round(rng.uniform(1, 4) * abundance, 1)
                if t.water > 0.7:
                    res["herbs"] = round(rng.uniform(1, 3) * abundance, 1)
                if rng.random() < 0.18:
                    res["stone"] = round(rng.uniform(3, 10) * abundance, 1)
            elif t.terrain == "tundra":
                if rng.random() < 0.5:
                    res["game"] = round(rng.uniform(1, 3) * abundance, 1)
                if rng.random() < 0.25:
                    res["wood"] = round(rng.uniform(2, 8) * abundance, 1)
            elif t.terrain == "plains":
                if rng.random() < 0.8:
                    res["berries"] = round(rng.uniform(1.5, 5) * abundance, 1)
                if rng.random() < 0.5:
                    res["game"] = round(rng.uniform(1, 3.5) * abundance, 1)
                if rng.random() < 0.16:
                    res["wood"] = round(rng.uniform(2, 7) * abundance, 1)
            elif t.terrain == "fertile":
                if rng.random() < 0.9:
                    res["berries"] = round(rng.uniform(2.5, 7) * abundance, 1)
                if rng.random() < 0.4:
                    res["game"] = round(rng.uniform(1, 3) * abundance, 1)
                if rng.random() < 0.3:
                    res["herbs"] = round(rng.uniform(1, 3) * abundance, 1)
                if rng.random() < 0.2:
                    res["wood"] = round(rng.uniform(2, 6) * abundance, 1)
            elif t.terrain == "swamp":
                res["wood"] = round(rng.uniform(6, 18) * abundance, 1)
                res["herbs"] = round(rng.uniform(1, 4) * abundance, 1)
            elif t.terrain == "coast":
                if rng.random() < 0.45:
                    res["fish"] = round(rng.uniform(2, 6) * abundance, 1)
                res["clay"] = round(rng.uniform(1, 4) * abundance, 1)
            if t.terrain not in ("ocean", "deep_ocean"):
                res = {k: v for k, v in res.items() if v > 0}
            t.resources = res
        # Guarantee fresh-water fishing near every starting region: the world
        # should be survivable, not generous.
        for t in self.tiles:
            if t.river and "fish" not in t.resources:
                t.resources["fish"] = round(rng.uniform(2, 5) * abundance, 1)

    def _choose_start_sites(self, rng: random.Random) -> None:
        candidates = [
            t for t in self.tiles
            if t.passable and t.terrain in ("fertile", "plains", "forest", "river")
            and t.water >= 0.45 and t.fertility >= 0.28
        ]
        candidates.sort(key=lambda t: (t.fertility * 0.55 + t.water * 0.3 + (0.15 if t.terrain == "river" else 0) + rng.random() * 0.1), reverse=True)
        groups = max(1, min(self.config.starting_groups, max(1, self.config.initial_population // 9)))
        chosen: list[Tile] = []
        min_sep = max(8, int(min(self.width, self.height) * 0.22))
        for t in candidates:
            if len(chosen) >= groups:
                break
            if all((t.x - c.x) ** 2 + (t.y - c.y) ** 2 >= min_sep ** 2 for c in chosen):
                chosen.append(t)
        if not chosen:
            chosen = [candidates[0]] if candidates else [next(t for t in self.tiles if t.passable)]
        # If the world is fragmented, fall back to progressively smaller separation.
        if len(chosen) < groups:
            for t in candidates:
                if len(chosen) >= groups:
                    break
                if all((t.x - c.x) ** 2 + (t.y - c.y) ** 2 >= 4 for c in chosen):
                    chosen.append(t)
        self.start_sites = [
            {
                "x": t.x, "y": t.y, "terrain": t.terrain,
                "fertility": t.fertility, "water": round(t.water, 2),
                "group": i,
            }
            for i, t in enumerate(chosen)
        ]

    def spawn_positions(self, rng: random.Random, count: int) -> list[tuple[int, int, int]]:
        """Return (x, y, starting_group) near viable initial sites."""
        positions: list[tuple[int, int, int]] = []
        if not self.start_sites:
            return positions
        groups = len(self.start_sites)
        for i in range(count):
            site = self.start_sites[i % groups]
            for attempt in range(80):
                radius = 0 if attempt == 0 else rng.randint(1, 4)
                x = site["x"] + rng.randint(-radius, radius)
                y = site["y"] + rng.randint(-radius, radius)
                tile = self.tile(x, y)
                if tile and tile.passable:
                    positions.append((x, y, site["group"]))
                    break
            else:
                positions.append((site["x"], site["y"], site["group"]))
        return positions

    # ------------------------------------------------------- environment tick
    def environment_tick(self, day: int) -> dict[str, Any]:
        """Advance weather and resource regeneration one day. Deterministic."""
        season = self.season(day)
        rng = random.Random(self.seed * 100_003 + day * 7919)
        cold = season == "Winter" or self.config.preset == "frozen_continent"
        if self.active_disaster:
            self.active_disaster.remaining -= 1
            if self.active_disaster.remaining <= 0:
                self.active_disaster = None
        # New disasters are rare and difficulty-scaled.
        if self.active_disaster is None:
            chance = 0.006 * self.config.environmental_difficulty
            if rng.random() < chance:
                kind = rng.choices(
                    ["drought", "wildfire", "flood", "epidemic", "harsh_winter"],
                    weights=[3, 2, 2, 2, 1 if cold else 0.3],
                )[0]
                center = (rng.randrange(self.width), rng.randrange(self.height))
                severity = round(rng.uniform(0.45, 1.0) * self.config.environmental_difficulty, 2)
                self.active_disaster = Disaster(kind, severity, remaining=rng.randint(3, 9), center=center)
        weights = [40, 18, 24, 7, 0, 0, 6]
        if cold:
            weights = [30, 18, 8, 4, 28, 1, 6]
        elif season == "Summer":
            weights = [38, 14, 15, 10, 0, 9, 5]
        weather = rng.choices(WEATHER, weights=weights)[0]
        if self.active_disaster and self.active_disaster.kind == "drought":
            weather = "Drought"
        self.weather = weather
        self.weather_severity = round(rng.uniform(0.3, 1.0), 2)
        growth = WEATHER_GROWTH.get(weather, 1.0) * SEASON_GROWTH[season]
        if self.active_disaster:
            if self.active_disaster.kind in ("drought", "harsh_winter"):
                growth *= 0.35 if self.active_disaster.kind == "drought" else 0.5
        # Resource regeneration. Wood and stone regenerate slowly; food faster.
        for tile in self.tiles:
            if not tile.resources:
                continue
            for key in list(tile.resources.keys()):
                if key in ("wood",):
                    tile.resources[key] = min(60 * self.config.resource_abundance, tile.resources[key] + 0.25 * growth)
                elif key in ("stone", "ore", "salt"):
                    continue
                elif key == "herbs":
                    tile.resources[key] = min(8 * self.config.resource_abundance, tile.resources[key] + 0.08 * growth)
                else:
                    cap = 12.0 * self.config.resource_abundance
                    tile.resources[key] = min(cap, tile.resources[key] + 0.45 * growth)
        return {
            "weather": self.weather,
            "season": season,
            "growth": round(growth, 2),
            "disaster": self.active_disaster.to_dict() if self.active_disaster else None,
        }

    # -------------------------------------------------------------- querying
    def nearest_tile(
        self,
        origin: tuple[int, int],
        predicate: Callable[[Tile], bool],
        max_radius: int = 12,
        passable_only: bool = True,
    ) -> Tile | None:
        ox, oy = origin
        if not (0 <= ox < self.width and 0 <= oy < self.height):
            return None
        visited = {(ox, oy)}
        queue: deque[tuple[int, int, int]] = deque([(ox, oy, 0)])
        while queue:
            x, y, d = queue.popleft()
            tile = self.tile_or_raise(x, y)
            if predicate(tile) and (not passable_only or tile.passable):
                return tile
            if d >= max_radius:
                continue
            for n in self.neighbors(x, y):
                if (n.x, n.y) in visited:
                    continue
                if passable_only and not n.passable:
                    continue
                visited.add((n.x, n.y))
                queue.append((n.x, n.y, d + 1))
        return None

    def find_resource(
        self,
        origin: tuple[int, int],
        item: str,
        min_amount: float = 0.4,
        max_radius: int = 14,
        remembered: list[tuple[int, int]] | None = None,
    ) -> Tile | None:
        keys = {
            "food": ("berries", "game", "fish"),
            "wood": ("wood",),
            "stone": ("stone",),
            "herbs": ("herbs",),
            "ore": ("ore",),
            "water": (),
        }[item]
        if remembered:
            for rx, ry in remembered:
                tile = self.tile(rx, ry)
                if tile and tile.passable and any(tile.resources.get(k, 0) >= min_amount for k in keys):
                    return tile
        if item == "water":
            return self.nearest_tile(origin, lambda t: t.freshwater, max_radius=max_radius)
        return self.nearest_tile(origin, lambda t: any(t.resources.get(k, 0) >= min_amount for k in keys), max_radius=max_radius)

    def path_to(self, start: tuple[int, int], goal: tuple[int, int], max_nodes: int = 900) -> list[tuple[int, int]] | None:
        """Small deterministic A*; returns path excluding the starting tile."""
        if start == goal:
            return []
        sx, sy = start
        gx, gy = goal
        if not (0 <= gx < self.width and 0 <= gy < self.height):
            return None
        import heapq

        def h(x: int, y: int) -> float:
            return abs(x - gx) + abs(y - gy)

        open_heap: list[tuple[float, int, int]] = [(h(sx, sy), sx, sy)]
        came: dict[tuple[int, int], tuple[int, int]] = {}
        gscore: dict[tuple[int, int], float] = {(sx, sy): 0.0}
        seen = 0
        while open_heap and seen < max_nodes:
            _, x, y = heapq.heappop(open_heap)
            seen += 1
            if (x, y) == (gx, gy):
                path = []
                cur = (gx, gy)
                while cur != (sx, sy):
                    path.append(cur)
                    cur = came[cur]
                path.reverse()
                return path
            tile = self.tile_or_raise(x, y)
            for n in self.neighbors(x, y):
                if not n.passable:
                    continue
                cost = 1.0
                if n.terrain == "mountain":
                    cost += 1.4
                elif n.river:
                    cost += 0.5
                elif n.terrain == "swamp":
                    cost += 0.8
                tentative = gscore[(x, y)] + cost
                if tentative < gscore.get((n.x, n.y), 1e9):
                    came[(n.x, n.y)] = (x, y)
                    gscore[(n.x, n.y)] = tentative
                    heapq.heappush(open_heap, (tentative + h(n.x, n.y), n.x, n.y))
        return None

    def resource_totals(self) -> dict[str, float]:
        totals: dict[str, float] = {}
        for tile in self.tiles:
            for key, amount in tile.resources.items():
                totals[key] = totals.get(key, 0.0) + amount
        return {k: round(v, 1) for k, v in totals.items()}

    # ---------------------------------------------------------- serialization
    def resource_mask(self, tile: Tile) -> int:
        bits = {"wood": 1, "stone": 2, "game": 4, "fish": 8, "ore": 16, "herbs": 32, "clay": 64, "berries": 128}
        mask = 0
        for key in tile.resources:
            mask |= bits.get(key, 0)
        return mask

    def serialize(self, include_owners: bool = False) -> dict[str, Any]:
        tiles = self.tiles
        return {
            "width": self.width,
            "height": self.height,
            "seed": self.seed,
            "preset": self.config.preset,
            "climate": self.config.climate,
            "land_ratio": round(self.land_ratio, 3),
            "rivers": self.rivers,
            "lakes": self.lakes,
            "start_sites": self.start_sites,
            "terrain": [t.terrain for t in tiles],
            "elevation": [round(t.elevation, 3) for t in tiles],
            "fertility": [round(t.fertility, 2) for t in tiles],
            "water": [round(t.water, 2) for t in tiles],
            "temperature": [round(t.temperature, 2) for t in tiles],
            "river": [t.river for t in tiles],
            "resources": [self.resource_mask(t) for t in tiles],
            "owners": [t.owner for t in tiles] if include_owners else None,
            "disaster": self.active_disaster.to_dict() if self.active_disaster else None,
        }

    def biome_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for t in self.tiles:
            counts[t.terrain] = counts.get(t.terrain, 0) + 1
        return counts
