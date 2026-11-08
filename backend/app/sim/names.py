"""Name and word generation.

Names are generated from phoneme pools. They are arbitrary marks, but the
language system that uses them is not: every word is bound to a concept and
spreads through actual communication.
"""
from __future__ import annotations

import random

FEMALE_NAMES = [
    "Adra", "Ayla", "Brenna", "Caelia", "Dara", "Eira", "Elowen", "Fara", "Ilya",
    "Isra", "Juna", "Kael", "Liora", "Maren", "Mira", "Nadia", "Neris", "Oona",
    "Orla", "Rhea", "Sana", "Selia", "Tamsin", "Thea", "Una", "Vela", "Wren",
    "Yara", "Zara", "Aster", "Bela", "Cyra", "Della", "Emi", "Fenna", "Greta",
    "Hana", "Ione", "Jora", "Kira", "Lena", "Mae", "Nia", "Opal", "Pia", "Rosa",
]
MALE_NAMES = [
    "Arven", "Bastian", "Cai", "Dain", "Elias", "Eron", "Finn", "Galen", "Hale",
    "Ivo", "Jarek", "Kaelen", "Kiran", "Lark", "Leif", "Milo", "Nero", "Orin",
    "Oren", "Pavel", "Quill", "Rafe", "Rowan", "Silas", "Tarek", "Thane", "Ulan",
    "Varek", "Wade", "Yorick", "Zane", "Ansel", "Bram", "Cato", "Dorian", "Emil",
    "Ferran", "Gideon", "Hugo", "Ilan", "Jonas", "Kaspar", "Lucian", "Mateo",
]
NEUTRAL_NAMES = [
    "Ash", "Briar", "Cedar", "Ember", "Fern", "Flint", "Haven", "Indigo", "Juniper",
    "Lake", "Moss", "North", "Onyx", "Rain", "Reed", "River", "Sage", "Sky",
    "Stone", "Thorn", "Vale", "Willow", "Wyn", "Yew", "Alder", "Birch", "Clove",
]
SURNAMES = [
    "of the Vale", "Riverborn", "Ashwalker", "Stonehand", "Greenfield", "Dawnwatch",
    "Hollowmere", "Fairwind", "Ironwood", "Longshadow", "Mistwood", "Oakenshield",
    "Redfern", "Stillwater", "Thornfield", "Whitestone", "Wildmere", "Sunward",
    "Marsh", "Hearth", "Skye", "Fallow", "Brook", "Emberly", "Northwind",
]
COLLECTIVE_PREFIX = [
    "Alder", "Bram", "Cinder", "Dawn", "Elder", "Fern", "Glimmer", "Hollow", "Iron",
    "Juniper", "Kestrel", "Lark", "Morrow", "Nettle", "Oak", "Pine", "Quarry",
    "Raven", "Stone", "Thorn", "Vale", "Willow", "Amber", "Basalt", "Cedar",
]
COLLECTIVE_SUFFIX = [
    "hold", "stead", "ford", "field", "mere", "watch", "haven", "gate", "moor",
    "reach", "rest", "rise", "wood", "vale", "burg", "crossing", "hearth",
]
SETTLEMENT_PREFIX = [
    "Aur", "Bel", "Cor", "Dun", "Eld", "Fen", "Gal", "Hal", "Ith", "Kel", "Lor",
    "Mar", "Nor", "Or", "Pel", "Quen", "Rav", "Sel", "Tor", "Ul", "Var", "Wes",
    "Yar", "Zel", "Bram", "Cald", "Dorn", "Esk", "Farrow", "Glen", "Harrow",
]
SETTLEMENT_SUFFIX = [
    "haven", "stead", "ford", "holm", "bury", "gate", "mere", "field", "watch",
    "rest", "reach", "fall", "wick", "moor", "bridge", "cairn", "glen", "tarn",
]

ONSET = ["s", "v", "r", "n", "m", "l", "k", "t", "th", "sh", "d", "b", "g", "f", "p", "h", "w", "y", "ch"]
VOWEL = ["a", "e", "i", "o", "u", "ae", "ia", "ei", "ou", "ua"]
CODA = ["", "", "n", "r", "l", "s", "th", "m", "k", "v", "sh"]


def pick_name(rng: random.Random, gender: str, used: set[str]) -> str:
    pool = FEMALE_NAMES if gender == "woman" else MALE_NAMES if gender == "man" else NEUTRAL_NAMES
    for _ in range(50):
        first = rng.choice(pool)
        surname = rng.choice(SURNAMES) if rng.random() < 0.35 else ""
        full = f"{first} {surname}".strip()
        if full not in used:
            used.add(full)
            return full
    n = 2
    while True:
        candidate = f"{rng.choice(pool)} {rng.choice(SURNAMES)} {n}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        n += 1


def language_name(rng: random.Random, used: set[str]) -> str:
    for _ in range(40):
        name = f"{rng.choice(SETTLEMENT_PREFIX)}{rng.choice(['i', 'a', 'en', 'ori', 'ese'])}{rng.choice(['an', 'ic', 'ish', 'ic', 'al', 'ine'])}"
        name = name.capitalize()
        if name not in used:
            used.add(name)
            return name
    return f"Tongue {rng.randint(100, 999)}"


def culture_name(rng: random.Random, used: set[str]) -> str:
    for _ in range(40):
        name = f"{rng.choice(COLLECTIVE_PREFIX)}{rng.choice(['ic', 'an', 'ene', 'ic', 'ish', 'ene'])}"
        name = name.capitalize()
        if name not in used:
            used.add(name)
            return name
    return f"Culture {rng.randint(100, 999)}"


def settlement_name(rng: random.Random, used: set[str], terrain_hint: str = "") -> str:
    suffix_hint = {
        "river": "ford", "lake": "mere", "forest": "wood", "mountain": "crag",
        "desert": "rest", "tundra": "stead", "plains": "field", "fertile": "field",
    }.get(terrain_hint)
    for _ in range(60):
        name = f"{rng.choice(SETTLEMENT_PREFIX)}{suffix_hint if suffix_hint and rng.random() < 0.4 else rng.choice(SETTLEMENT_SUFFIX)}"
        name = name.capitalize()
        if name not in used:
            used.add(name)
            return name
    return f"{rng.choice(COLLECTIVE_PREFIX)}{rng.choice(COLLECTIVE_SUFFIX).capitalize()}{rng.randint(2, 9)}"


def coin_word(rng: random.Random, used: set[str] | None = None) -> str:
    """Generate a pronounceable word. Used only for grounded concept coinage."""
    used = used or set()
    for _ in range(80):
        syllables = rng.randint(1, 3)
        word = ""
        for _ in range(syllables):
            word += rng.choice(ONSET) + rng.choice(VOWEL) + (rng.choice(CODA) if rng.random() < 0.45 else "")
        if 2 <= len(word) <= 10 and word not in used:
            used.add(word)
            return word
    return f"ka{rng.randint(10, 99)}"


def family_name(rng: random.Random) -> str:
    return rng.choice(SURNAMES)
