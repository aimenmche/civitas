"""Static game data for CIVITAS.

Everything here is data, not narrative. Outcomes are produced by the simulation.
"""
from __future__ import annotations

TERRAINS = [
    "deep_ocean", "ocean", "coast", "lake", "river", "plains", "fertile",
    "forest", "mountain", "desert", "tundra", "swamp",
]

TERRAIN_LABELS = {
    "deep_ocean": "Deep Ocean", "ocean": "Ocean", "coast": "Coast", "lake": "Lake",
    "river": "River", "plains": "Plains", "fertile": "Fertile Land", "forest": "Forest",
    "mountain": "Mountain", "desert": "Desert", "tundra": "Tundra", "swamp": "Wetland",
}

TERRAIN_COLORS = {
    "deep_ocean": "#07141f", "ocean": "#0a2030", "coast": "#1a3a45", "lake": "#123c50",
    "river": "#1d5d72", "plains": "#56663d", "fertile": "#788b4b", "forest": "#2d4634",
    "mountain": "#6e685d", "desert": "#a68e62", "tundra": "#7c8f8e", "swamp": "#3c5142",
}

SEASONS = ["Spring", "Summer", "Autumn", "Winter"]
DAYS_PER_SEASON = 10
DAYS_PER_YEAR = DAYS_PER_SEASON * len(SEASONS)
SEASON_TEMP = {"Spring": 0.0, "Summer": 0.16, "Autumn": -0.04, "Winter": -0.2}
SEASON_GROWTH = {"Spring": 1.15, "Summer": 0.95, "Autumn": 1.2, "Winter": 0.4}

WEATHER = ["Clear", "Cloudy", "Rain", "Storm", "Snow", "Drought", "Fog"]
WEATHER_GROWTH = {
    "Clear": 1.0, "Cloudy": 0.9, "Rain": 1.3, "Storm": 0.7,
    "Snow": 0.35, "Drought": 0.3, "Fog": 0.95,
}

RESOURCE_LABELS = {
    "berries": "Wild berries", "game": "Game", "fish": "Fish", "wood": "Wood",
    "stone": "Stone", "clay": "Clay", "ore": "Ore", "herbs": "Herbs", "salt": "Salt",
}

INVENTORY_ITEMS = ["food", "water", "wood", "stone", "tools", "currency", "herbs", "ore"]
INVENTORY_CAPS = {
    "food": 24, "water": 12, "wood": 24, "stone": 24, "tools": 6,
    "currency": 999, "herbs": 8, "ore": 12,
}

NEEDS = ["hunger", "thirst", "energy", "health", "safety", "social", "shelter"]
NEED_LABELS = {
    "hunger": "Food", "thirst": "Water", "energy": "Energy", "health": "Health",
    "safety": "Safety", "social": "Social", "shelter": "Shelter",
}

PERSONALITY_TRAITS = [
    "ambition", "intelligence", "curiosity", "aggressiveness", "cooperation",
    "risk_tolerance", "sociability", "honesty", "empathy",
]
PERSONALITY_LABELS = {t: t.replace("_", " ").title() for t in PERSONALITY_TRAITS}

SKILLS = [
    "farming", "construction", "hunting", "gathering", "trading", "crafting",
    "exploration", "leadership", "research",
]
SKILL_LABELS = {t: t.replace("_", " ").title() for t in SKILLS}

PERSONALITY_PRESETS = {
    "balanced": {t: 0.5 for t in PERSONALITY_TRAITS},
    "cooperative": {
        "ambition": 0.45, "intelligence": 0.55, "curiosity": 0.55,
        "aggressiveness": 0.25, "cooperation": 0.78, "risk_tolerance": 0.4,
        "sociability": 0.72, "honesty": 0.7, "empathy": 0.75,
    },
    "competitive": {
        "ambition": 0.72, "intelligence": 0.6, "curiosity": 0.45,
        "aggressiveness": 0.68, "cooperation": 0.3, "risk_tolerance": 0.65,
        "sociability": 0.5, "honesty": 0.42, "empathy": 0.35,
    },
    "ambitious": {
        "ambition": 0.82, "intelligence": 0.64, "curiosity": 0.6,
        "aggressiveness": 0.5, "cooperation": 0.5, "risk_tolerance": 0.6,
        "sociability": 0.6, "honesty": 0.55, "empathy": 0.5,
    },
    "random": None,
}

# --- Technology ------------------------------------------------------------
# Each technology has prerequisites, a research cost, conditions, and a
# description of its real mechanical effect. Nothing is granted "for free".
TECHS: dict[str, dict] = {
    "foraging": {
        "name": "Foraging Lore", "era": "Survival", "cost": 0,
        "prereq": [], "conditions": {}, "year": 0,
        "effect": "Improves gathering yields by 10%.",
        "effects": {"gather_food": 0.10, "gather_wood": 0.05},
    },
    "fire": {
        "name": "Fire", "era": "Survival", "cost": 24,
        "prereq": [], "conditions": {"population": 4}, "year": 0,
        "effect": "Warmth: reduces cold exposure and food spoilage.",
        "effects": {"health_cold": 0.25, "food_keep": 0.15, "happiness": 3},
    },
    "basic_tools": {
        "name": "Basic Tools", "era": "Survival", "cost": 32,
        "prereq": ["fire"], "conditions": {"population": 5}, "year": 0,
        "effect": "+15% gathering, +10% construction.",
        "effects": {"gather_food": 0.15, "gather_wood": 0.15, "build_speed": 0.1},
    },
    "pottery": {
        "name": "Pottery", "era": "Agrarian", "cost": 44,
        "prereq": ["fire"], "conditions": {"population": 6}, "year": 0,
        "effect": "Food storage keeps 25% longer; enables granaries.",
        "effects": {"food_keep": 0.25, "build_unlock": ["granary"]},
    },
    "agriculture": {
        "name": "Agriculture", "era": "Agrarian", "cost": 58,
        "prereq": ["basic_tools"], "conditions": {"population": 6, "fertility": 0.3}, "year": 0,
        "effect": "Unlocks farms; settlements produce reliable food.",
        "effects": {"farm_yield": 0.6, "build_unlock": ["farm"]},
    },
    "animal_husbandry": {
        "name": "Animal Husbandry", "era": "Agrarian", "cost": 52,
        "prereq": ["agriculture"], "conditions": {"population": 9}, "year": 0,
        "effect": "+20% farm output and +10% food storage.",
        "effects": {"farm_yield": 0.2, "food_keep": 0.1},
    },
    "masonry": {
        "name": "Masonry", "era": "Agrarian", "cost": 66,
        "prereq": ["basic_tools"], "conditions": {"stone": 18}, "year": 0,
        "effect": "Enables stone buildings and stronger shelters.",
        "effects": {"build_unlock": ["stone_house", "palisade", "well"], "build_speed": 0.1},
    },
    "food_preservation": {
        "name": "Food Preservation", "era": "Agrarian", "cost": 48,
        "prereq": ["pottery"], "conditions": {"population": 8}, "year": 0,
        "effect": "Reduces harvest spoilage and winter hunger.",
        "effects": {"food_keep": 0.3, "winter_food": 0.2},
    },
    "construction": {
        "name": "Construction", "era": "Agrarian", "cost": 72,
        "prereq": ["masonry"], "conditions": {"population": 10, "settlements": 1}, "year": 0,
        "effect": "Enables workshops, town halls and faster building.",
        "effects": {"build_unlock": ["workshop", "town_hall"], "build_speed": 0.15},
    },
    "trade": {
        "name": "Trade Routes", "era": "Classical", "cost": 64,
        "prereq": ["basic_tools"], "conditions": {"population": 8, "settlements": 1}, "year": 0,
        "effect": "Enables markets; improves prices and barter gains.",
        "effects": {"build_unlock": ["market"], "trade": 0.15},
    },
    "writing": {
        "name": "Writing", "era": "Classical", "cost": 78,
        "prereq": ["agriculture", "trade"], "conditions": {"population": 12, "settlements": 1}, "year": 0,
        "effect": "Records laws and memories; +20% research and knowledge transmission.",
        "effects": {"research": 0.2, "build_unlock": ["archive"], "memory": 0.1},
    },
    "mathematics": {
        "name": "Mathematics", "era": "Classical", "cost": 92,
        "prereq": ["writing"], "conditions": {"population": 14}, "year": 0,
        "effect": "Improves research and enables currency and engineering.",
        "effects": {"research": 0.2, "trade": 0.1},
    },
    "medicine": {
        "name": "Medicine", "era": "Classical", "cost": 84,
        "prereq": ["pottery"], "conditions": {"herbs": 12}, "year": 0,
        "effect": "+35% recovery from illness, births are safer.",
        "effects": {"health_recovery": 0.35, "birth_survival": 0.1},
    },
    "metallurgy": {
        "name": "Metallurgy", "era": "Classical", "cost": 96,
        "prereq": ["masonry", "fire"], "conditions": {"ore": 10}, "year": 0,
        "effect": "+25% tool crafting, +15% construction.",
        "effects": {"tool_yield": 0.25, "build_speed": 0.15},
    },
    "irrigation": {
        "name": "Irrigation", "era": "Classical", "cost": 88,
        "prereq": ["agriculture", "masonry"], "conditions": {"water": 0.4}, "year": 0,
        "effect": "Farms produce +30% even in dry seasons.",
        "effects": {"farm_yield": 0.3, "drought_resist": 0.3},
    },
    "currency": {
        "name": "Currency", "era": "Civic", "cost": 110,
        "prereq": ["trade", "mathematics"], "conditions": {"population": 12, "market": True}, "year": 0,
        "effect": "Enables coins, wages, prices, taxes and wealth accumulation.",
        "effects": {"currency": True, "trade": 0.2},
    },
    "philosophy": {
        "name": "Philosophy", "era": "Civic", "cost": 104,
        "prereq": ["writing"], "conditions": {"population": 12}, "year": 0,
        "effect": "Enables councils, formal law and political legitimacy.",
        "effects": {"governance": 0.2, "happiness": 3, "build_unlock": ["agora"]},
    },
    "engineering": {
        "name": "Engineering", "era": "Civic", "cost": 128,
        "prereq": ["mathematics", "masonry"], "conditions": {"population": 16, "settlements": 1},
        "year": 0,
        "effect": "Enables aqueducts, roads and large public works.",
        "effects": {"build_unlock": ["aqueduct", "road"], "build_speed": 0.2, "farm_yield": 0.1},
    },
}

ERA_ORDER = ["Survival", "Agrarian", "Classical", "Civic"]

BUILDINGS: dict[str, dict] = {
    "shelter": {
        "name": "Shelter", "cost": {"wood": 4}, "build_days": 2, "housing": 1,
        "requires_tech": None, "effect": "Protects one person from weather.",
    },
    "house": {
        "name": "House", "cost": {"wood": 8, "stone": 2}, "build_days": 3, "housing": 4,
        "requires_tech": None, "effect": "Housing for four people.",
    },
    "stone_house": {
        "name": "Stone House", "cost": {"wood": 6, "stone": 12}, "build_days": 5, "housing": 6,
        "requires_tech": "masonry", "effect": "Durable housing for six people.",
    },
    "farm": {
        "name": "Farm", "cost": {"wood": 8, "stone": 2}, "build_days": 4, "requires_tech": "agriculture",
        "effect": "Produces food daily according to land fertility.", "jobs": 2,
    },
    "well": {
        "name": "Well", "cost": {"stone": 10, "wood": 2}, "build_days": 3, "requires_tech": "masonry",
        "effect": "Reliable clean water inside the settlement.",
    },
    "granary": {
        "name": "Granary", "cost": {"wood": 14, "stone": 4}, "build_days": 4, "requires_tech": "pottery",
        "effect": "Increases food storage and reduces spoilage.", "storage": 120,
    },
    "storage": {
        "name": "Storehouse", "cost": {"wood": 10}, "build_days": 2, "requires_tech": None,
        "effect": "Increases settlement storage capacity.", "storage": 80,
    },
    "workshop": {
        "name": "Workshop", "cost": {"wood": 12, "stone": 6}, "build_days": 4, "requires_tech": "construction",
        "effect": "Crafts tools and improves research.", "jobs": 2,
    },
    "market": {
        "name": "Market", "cost": {"wood": 12, "stone": 4}, "build_days": 4, "requires_tech": "trade",
        "effect": "Agents exchange goods using emergent prices.", "jobs": 2,
    },
    "palisade": {
        "name": "Palisade", "cost": {"wood": 18, "stone": 4}, "build_days": 5, "requires_tech": "masonry",
        "effect": "Raises settlement safety against raids and disaster.",
    },
    "shrine": {
        "name": "Shrine", "cost": {"wood": 6, "stone": 6}, "build_days": 3, "requires_tech": None,
        "effect": "A place for shared ritual; improves morale.", "culture": 1,
    },
    "archive": {
        "name": "Archive", "cost": {"wood": 8, "stone": 10}, "build_days": 5, "requires_tech": "writing",
        "effect": "Stores knowledge and accelerates research.", "research": 0.15,
    },
    "school": {
        "name": "School", "cost": {"wood": 12, "stone": 12}, "build_days": 6, "requires_tech": "writing",
        "effect": "Transmits skills and technology to the young.",
    },
    "town_hall": {
        "name": "Town Hall", "cost": {"wood": 16, "stone": 14}, "build_days": 6, "requires_tech": "construction",
        "effect": "Seat of government; improves legitimacy and law.",
    },
    "agora": {
        "name": "Agora", "cost": {"stone": 18, "wood": 8}, "build_days": 6, "requires_tech": "philosophy",
        "effect": "Public assembly space; strengthens civic culture.",
    },
    "aqueduct": {
        "name": "Aqueduct", "cost": {"stone": 26, "wood": 4}, "build_days": 8, "requires_tech": "engineering",
        "effect": "Provides abundant water and improves health.", "water": 1,
    },
}

# Concepts the language engine can ground in shared experience.
LANGUAGE_CONCEPTS = [
    "food", "water", "friend", "danger", "help", "trade", "home", "river",
    "forest", "mountain", "sun", "rain", "fire", "stone", "wood", "hunt",
    "farm", "child", "leader", "law", "spirit", "thanks", "welcome", "good",
    "bad", "many", "few", "far", "near", "together", "mine", "yours", "gift",
]

EVENT_CATEGORIES = [
    "world", "survival", "social", "settlement", "economy", "politics",
    "culture", "technology", "demography", "conflict", "disaster", "milestone",
]

AMBITIONS = [
    "found a lasting settlement",
    "become a respected leader",
    "master the art of farming",
    "build a large family",
    "discover knowledge that outlives me",
    "become the wealthiest trader",
    "explore every corner of the world",
    "craft tools of unmatched quality",
]

GOVERNMENTS = {
    "tribal": {
        "label": "Tribal Leadership",
        "description": "Authority rests with the founder and their circle.",
        "legitimacy": 55, "tax": 0.0,
    },
    "council": {
        "label": "Council",
        "description": "Elders and skilled members deliberate collectively.",
        "legitimacy": 62, "tax": 0.05,
    },
    "monarchy": {
        "label": "Monarchy",
        "description": "A hereditary ruler holds executive power.",
        "legitimacy": 58, "tax": 0.1,
    },
    "republic": {
        "label": "Republic",
        "description": "Property-holding citizens elect representatives.",
        "legitimacy": 64, "tax": 0.08,
    },
    "democracy": {
        "label": "Assembly Democracy",
        "description": "Decisions are made by the assembled people.",
        "legitimacy": 68, "tax": 0.06,
    },
    "oligarchy": {
        "label": "Oligarchy",
        "description": "A small wealthy group controls the settlement.",
        "legitimacy": 50, "tax": 0.12,
    },
    "authoritarian": {
        "label": "Authoritarian Rule",
        "description": "Power is concentrated and enforced.",
        "legitimacy": 45, "tax": 0.15,
    },
}

LAW_TEMPLATES = {
    "rationing": {
        "title": "Rationing of Stores",
        "description": "Settlement food is distributed by need rather than claim.",
        "effects": {"food_share": 0.1, "happiness": -2, "stability": 4},
    },
    "hospitality": {
        "title": "Duty of Hospitality",
        "description": "Travelers and the hungry must be offered shelter for a night.",
        "effects": {"trust": 0.05, "food_cost": 0.02, "culture": "hospitality"},
    },
    "punishment": {
        "title": "Law of Restitution",
        "description": "Those who take from others must repay double.",
        "effects": {"theft": -0.4, "safety": 3, "happiness": -1},
    },
    "common_land": {
        "title": "Commons Charter",
        "description": "Nearby woods and waters belong to all members.",
        "effects": {"gather": 0.08, "cooperation": 0.05},
    },
    "elders": {
        "title": "Council of Elders",
        "description": "Disputes are judged by those with the longest memory.",
        "effects": {"legitimacy": 5, "stability": 3},
    },
    "tax": {
        "title": "Public Levy",
        "description": "A share of production funds shared works.",
        "effects": {"stockpile": 0.04, "happiness": -2},
    },
}
