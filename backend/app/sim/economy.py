"""Market prices, barter valuation, inequality and economic stages."""
from __future__ import annotations

import math
from typing import Any

from .constants import INVENTORY_ITEMS

BASE_PRICES = {
    "food": 2.0, "water": 1.4, "wood": 2.2, "stone": 2.6, "tools": 9.0,
    "herbs": 3.4, "ore": 5.0, "salt": 3.0, "currency": 1.0,
}

ITEM_NEED = {
    "food": "hunger", "water": "thirst", "wood": "shelter",
    "stone": "shelter", "tools": "energy", "herbs": "health",
}


def stage_for(settlement: Any) -> int:
    if settlement.population < 4:
        return 1
    if settlement.uses_currency:
        return 4 if settlement.population >= 16 else 3
    if settlement.has_building("market") and settlement.trade_volume > 8:
        return 2
    if settlement.population >= 7:
        return 2
    return 1


def update_prices(settlement: Any, days: int, rng: Any) -> dict[str, float]:
    """Prices respond to real stock and real demand, with bounded noise."""
    prices: dict[str, float] = {}
    pop = max(1, settlement.population)
    consumption = {"food": pop * 0.5, "water": pop * 0.8, "wood": pop * 0.15, "stone": pop * 0.08,
                   "tools": pop * 0.02, "herbs": pop * 0.02, "ore": pop * 0.02, "salt": pop * 0.01}
    for item, base in BASE_PRICES.items():
        if item == "currency":
            continue
        # Stock can briefly be driven below zero by a purchase that lands just
        # before restock; a negative value made (stock + 1) zero and crashed the
        # whole step with a ZeroDivisionError. Clamp it and guard the divisor.
        stock = max(0.0, float(settlement.storage.get(item, 0.0)))
        # Abundance pushes price toward a floor; scarcity raises it steeply.
        stock_factor = max(0.35, min(3.2, (consumption.get(item, 0) * 4 + 1) / (stock + 1.0)))
        demand_factor = 1.0
        if item == "food":
            demand_factor += 0.4 if settlement.happiness < 45 else 0.0
        if settlement.uses_currency:
            demand_factor += 0.1
        price = base * (0.6 + stock_factor * 0.55) * demand_factor
        # Slow adaptation avoids price teleporting.
        old = settlement.market_prices.get(item, base)
        blended = old * 0.7 + price * 0.3 + rng.uniform(-0.05, 0.05)
        prices[item] = round(max(0.3, blended), 2)
    settlement.market_prices = prices
    return prices


def agent_valuation(agent: Any, item: str) -> float:
    base = BASE_PRICES.get(item, 2.0)
    need = ITEM_NEED.get(item)
    if need:
        satisfaction = agent.needs.get(need, 60)
        base *= 1.0 + max(0.0, (70 - satisfaction) / 70) * 0.9
    if item == "food":
        base *= 1.0 + max(0.0, (40 - agent.inventory.get("food", 0)) / 40) * 0.5
    if item == "water":
        base *= 1.0 + max(0.0, (30 - agent.inventory.get("water", 0)) / 30) * 0.4
    if item == "tools":
        base *= 1.0 + max(0.0, (2 - agent.inventory.get("tools", 0)) / 2) * 0.4
    return round(base, 2)


def surplus_offer(agent: Any) -> str | None:
    """What can this agent genuinely afford to part with?"""
    candidates = []
    for item in ("food", "water", "wood", "stone", "herbs", "ore"):
        qty = agent.inventory.get(item, 0)
        reserve = 2.0 if item in ("food", "water") else 1.0
        if qty > reserve:
            candidates.append((qty - reserve, item))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def wanted_item(agent: Any) -> str | None:
    deficits = []
    for item in ("food", "water", "wood", "stone", "herbs", "tools"):
        qty = agent.inventory.get(item, 0)
        need = {"food": agent.needs["hunger"], "water": agent.needs["thirst"],
                "wood": agent.needs["shelter"], "stone": agent.needs["shelter"],
                "herbs": agent.needs["health"], "tools": 50}[item]
        threshold = {"food": 3, "water": 2, "wood": 2, "stone": 3, "herbs": 1, "tools": 1}[item]
        deficit = max(0.0, (65 - need) / 65) + (1.0 if qty < threshold else 0.0)
        if deficit > 0:
            deficits.append((deficit, item))
    if not deficits:
        return None
    deficits.sort(reverse=True)
    return deficits[0][1]


def trade_ratio(agent_a: Any, agent_b: Any, offer: str, want: str) -> float:
    a_value = agent_valuation(agent_a, offer)
    b_value = agent_valuation(agent_b, want)
    return a_value / max(0.1, b_value)


def gini(values: list[float]) -> float:
    if not values:
        return 0.0
    values = sorted(max(0.0, v) for v in values)
    total = sum(values)
    if total <= 0:
        return 0.0
    n = len(values)
    cumulative = 0.0
    for i, value in enumerate(values, 1):
        cumulative += i * value
    return round((2 * cumulative) / (n * total) - (n + 1) / n, 3)


def wealth_distribution(agents: list[Any], settlements: dict[str, Any]) -> dict[str, Any]:
    values = [a.wealth() for a in agents if a.alive]
    values.sort()
    if not values:
        return {"gini": 0.0, "median": 0, "rich": 0, "poor": 0}
    median = values[len(values) // 2]
    return {
        "gini": gini(values),
        "median": round(median, 1),
        "rich": round(values[-1], 1),
        "poor": round(values[0], 1),
    }
