"""Emergence detector.

The detector does not invent conclusions. It reads the same persisted event log
and daily metrics the rest of the observatory reads, then reports structural
firsts, transitions and statistical anomalies with the evidence that produced
them. Anything causal is labelled a hypothesis and says plainly that the log
does not establish it.

Two rules matter here:

* every finding points at real event rows or real metric rows;
* "measured" means a difference between two recorded metric days, not a guess.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

from sqlalchemy.orm import Session

from ..models import RunEvent, RunMetric
from ..sim.constants import BUILDINGS, TECHS

SEASONS = ("Spring", "Summer", "Autumn", "Winter")
DAYS_PER_SEASON = 10
DAYS_PER_YEAR = 40

BUILDING_RE = re.compile(r"^(.+?) completes its (.+)$")
TECH_RE = re.compile(r"^(.+) discovered$")
CURRENCY_RE = re.compile(r"^Currency is adopted in (.+)$")
GOVERNMENT_RE = re.compile(r"^(.+) changes its government$")
LEADER_RE = re.compile(r"^(.+) becomes leader of (.+)$")
FACTION_RE = re.compile(r"^Factions form in (.+)$")
FOUNDED_RE = re.compile(r"^(.+) is founded$")
ABANDONED_RE = re.compile(r"^(.+) is abandoned$")
GENERATION_RE = re.compile(r"into generation (\d+)")
EXCHANGE_RE = re.compile(r"^First exchange between (.+?) and (.+)$")

# Routine structures (houses) are excluded: the first house is not a social
# novelty. Everything a community has to organise to build is kept.
WATCHED_BUILDINGS = {
    "farm", "well", "granary", "storage", "workshop", "market", "palisade",
    "shrine", "archive", "school", "town_hall", "agora", "aqueduct",
}

NAME_TO_BUILDING = {
    str(spec.get("name", key)).lower(): key for key, spec in BUILDINGS.items()
}
NAME_TO_TECH = {
    str(spec.get("name", key)).lower(): key for key, spec in TECHS.items()
}

CAUSE_CATEGORIES = {"disaster", "conflict", "survival", "demography", "economy"}


def year_of(day: int) -> int:
    return (max(1, day) - 1) // DAYS_PER_YEAR + 1


def season_of(day: int) -> str:
    return SEASONS[((max(1, day) - 1) % DAYS_PER_YEAR) // DAYS_PER_SEASON]


def _load_events(session: Session, run_id: str) -> list[dict[str, Any]]:
    rows = (
        session.query(RunEvent)
        .filter(RunEvent.run_id == run_id)
        .order_by(RunEvent.day.asc(), RunEvent.id.asc())
        .all()
    )
    return [
        {
            "event_id": row.event_id,
            "day": row.day,
            "category": row.category,
            "importance": row.importance,
            "title": row.title,
            "description": row.description or "",
            "related": _safe_json(row.related_json, {}),
        }
        for row in rows
    ]


def _load_metrics(session: Session, run_id: str) -> list[dict[str, Any]]:
    rows = (
        session.query(RunMetric)
        .filter(RunMetric.run_id == run_id)
        .order_by(RunMetric.day.asc())
        .all()
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        data = _safe_json(row.metrics_json, {})
        if isinstance(data, dict) and data:
            data["day"] = int(data.get("day", row.day))
            out.append(data)
    return out


def _safe_json(raw: str | None, fallback: Any) -> Any:
    try:
        return json.loads(raw) if raw else fallback
    except (TypeError, ValueError):
        return fallback


def _metric_at(metrics: list[dict[str, Any]], day: int) -> dict[str, Any] | None:
    """Latest recorded metric on or before `day` (metrics are day-sorted).

    Binary search rather than a linear scan: the anomaly pass calls this once
    per metric row, and worlds past day 8,000 carry thousands of rows.
    """
    low, high = 0, len(metrics)
    while low < high:
        middle = (low + high) // 2
        if metrics[middle]["day"] <= day:
            low = middle + 1
        else:
            high = middle
    return metrics[low - 1] if low else None


def _measured_change(
    metrics: list[dict[str, Any]],
    day: int,
    window: int = 60,
) -> list[str]:
    """Differences between raw metric rows around a finding, as plain facts."""
    before = _metric_at(metrics, day)
    after = _metric_at(metrics, day + window)
    if not before or not after or after["day"] <= before["day"]:
        return []
    rows: list[str] = []
    checks = (
        ("population", "population", 3, 0),
        ("settlements", "settlements", 1, 0),
        ("tech_count", "technologies known", 1, 0),
        ("avg_happiness", "mean happiness", 3, 1),
        ("inequality", "inequality index", 0.05, 3),
    )
    for key, label, threshold, digits in checks:
        a, b = before.get(key), after.get(key)
        if a is None or b is None:
            continue
        delta = float(b) - float(a)
        if abs(delta) < threshold:
            continue
        span = after["day"] - before["day"]
        rows.append(f"{label} {delta:+.{digits}f} over the {span} days after day {before['day']}")
    return rows


def _evidence(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"event_id": event["event_id"], "day": event["day"], "title": event["title"]}
        for event in events
    ]


def _finding(
    kind: str,
    title: str,
    day: int,
    observed: str,
    *,
    evidence: Iterable[dict[str, Any]] = (),
    measured: Iterable[str] = (),
    hypothesis: str | None = None,
    participants: Iterable[str] = (),
    index: int = 0,
) -> dict[str, Any]:
    return {
        "id": f"{kind}-{day}-{index}",
        "kind": kind,
        "title": title,
        "day": int(day),
        "year": year_of(day),
        "season": season_of(day),
        "observed": observed,
        "evidence": list(evidence),
        "measured": list(measured),
        "hypothesis": hypothesis,
        "confidence": "hypothesis" if hypothesis else "observation",
        "participants": list(participants),
    }


def _first_buildings(
    events: list[dict[str, Any]], metrics: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    findings = []
    seen: set[str] = set()
    for event in events:
        match = BUILDING_RE.match(event["title"])
        if not match:
            continue
        settlement, name = match.group(1), match.group(2)
        building_type = NAME_TO_BUILDING.get(name.lower())
        if not building_type or building_type not in WATCHED_BUILDINGS or building_type in seen:
            continue
        seen.add(building_type)
        detail = event["description"].strip()
        observed = (
            f"{settlement} completed the first {name.lower()} recorded in this world on day {event['day']}."
            + (f" {detail}" if detail else "")
        )
        findings.append(
            _finding(
                "institution",
                f"First {name.lower()} — {settlement}",
                event["day"],
                observed,
                evidence=[event],
                measured=_measured_change(metrics, event["day"]),
                index=len(findings),
            )
        )
    return findings


def _first_technologies(
    events: list[dict[str, Any]], metrics: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    findings = []
    seen: set[str] = set()
    for event in events:
        match = TECH_RE.match(event["title"])
        if not match:
            continue
        tech_key = NAME_TO_TECH.get(match.group(1).lower())
        if not tech_key or tech_key in seen:
            continue
        seen.add(tech_key)
        observed = (
            f"{match.group(1)} was worked out for the first time on day {event['day']}."
            + (f" {event['description'].strip()}" if event["description"] else "")
        )
        findings.append(
            _finding(
                "technology",
                f"First discovery: {match.group(1)}",
                event["day"],
                observed,
                evidence=[event],
                measured=_measured_change(metrics, event["day"]),
                index=len(findings),
            )
        )
    return findings


def _political_firsts(
    events: list[dict[str, Any]], metrics: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    findings = []
    seen: set[str] = set()
    # Later laws are routine; only the first formal law in the world is a
    # structural change worth flagging. The same applies to leaders,
    # government changes and organised factions.
    rules = (
        ("law", "First formal law enacted", lambda title: " enacted in " in title, ""),
        ("leader", "First named leader", lambda title: bool(LEADER_RE.match(title)), ""),
        ("government", "First change of government", lambda title: bool(GOVERNMENT_RE.match(title)), ""),
        ("faction", "First organised faction", lambda title: bool(FACTION_RE.match(title)), ""),
    )
    for key, label, predicate, _ in rules:
        for event in events:
            if key in seen or not predicate(event["title"]):
                continue
            seen.add(key)
            observed = event["description"].strip() or event["title"]
            findings.append(
                _finding(
                    "politics",
                    label,
                    event["day"],
                    f"On day {event['day']}: {observed}",
                    evidence=[event],
                    measured=_measured_change(metrics, event["day"]),
                    index=len(findings),
                )
            )
    return findings


def _diplomatic_firsts(
    events: list[dict[str, Any]], metrics: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    findings = []
    patterns = (
        ("tension", "First recorded tension between polities", "Tensions between "),
        ("war", "First war", "War between "),
        ("peace", "First peace settlement", "Peace between "),
        ("alliance", "First alliance", "Alliance between "),
    )
    for key, label, prefix in patterns:
        for event in events:
            if not event["title"].startswith(prefix):
                continue
            observed = event["description"].strip() or event["title"]
            findings.append(
                _finding(
                    "diplomacy",
                    label,
                    event["day"],
                    f"On day {event['day']}: {observed}",
                    evidence=[event],
                    measured=_measured_change(metrics, event["day"]),
                    index=len(findings),
                )
            )
            break
    return findings


def _economic_firsts(
    events: list[dict[str, Any]], metrics: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    findings = []
    first_exchange = next(
        (event for event in events if EXCHANGE_RE.match(event["title"])), None
    )
    if first_exchange:
        findings.append(
            _finding(
                "economy",
                "First recorded exchange",
                first_exchange["day"],
                first_exchange["description"].strip() or first_exchange["title"],
                evidence=[first_exchange],
                measured=_measured_change(metrics, first_exchange["day"]),
                index=len(findings),
            )
        )
    first_currency = next(
        (event for event in events if CURRENCY_RE.match(event["title"])), None
    )
    if first_currency:
        findings.append(
            _finding(
                "economy",
                "First adoption of a currency",
                first_currency["day"],
                first_currency["description"].strip() or first_currency["title"],
                evidence=[first_currency],
                measured=_measured_change(metrics, first_currency["day"]),
                hypothesis=(
                    "Monetary exchange may have changed how surplus was stored and traded, "
                    "but the log records adoption and prices separately; it does not prove the effect."
                ),
                index=len(findings),
            )
        )
    return findings


def _settlement_structure(
    events: list[dict[str, Any]], metrics: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    findings = []
    first_founded = next(
        (event for event in events if FOUNDED_RE.match(event["title"])), None
    )
    if first_founded:
        findings.append(
            _finding(
                "settlement",
                "First permanent settlement",
                first_founded["day"],
                first_founded["description"].strip() or first_founded["title"],
                evidence=[first_founded],
                measured=_measured_change(metrics, first_founded["day"]),
                index=len(findings),
            )
        )
    first_abandoned = next(
        (event for event in events if ABANDONED_RE.match(event["title"])), None
    )
    if first_abandoned:
        findings.append(
            _finding(
                "collapse",
                "First settlement abandoned",
                first_abandoned["day"],
                first_abandoned["description"].strip() or first_abandoned["title"],
                evidence=[first_abandoned],
                measured=_measured_change(metrics, first_abandoned["day"]),
                index=len(findings),
            )
        )
    peak = max(
        (row for row in metrics if row.get("settlements") is not None),
        key=lambda row: row["settlements"],
        default=None,
    )
    if peak and int(peak.get("settlements", 0)) >= 2:
        findings.append(
            _finding(
                "structure",
                f"Peak settlement network — {int(peak['settlements'])} polities",
                peak["day"],
                (
                    f"The largest number of simultaneously occupied settlements recorded was "
                    f"{int(peak['settlements'])} on day {peak['day']}. The metric is the count the "
                    f"engine wrote that day, not a later reconstruction."
                ),
                measured=_measured_change(metrics, peak["day"]),
                index=len(findings),
            )
        )
    return findings


def _language_divergence(
    engine: Any,
    events: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    languages = list(getattr(engine, "languages", {}).values())
    if len(languages) < 2:
        return []
    root = min(languages, key=lambda lang: getattr(lang, "created_day", 1))
    descendants = sorted(
        (lang for lang in languages if getattr(lang, "created_day", 1) > getattr(root, "created_day", 1)),
        key=lambda lang: getattr(lang, "created_day", 1),
    )
    if not descendants:
        return []
    first = descendants[0]
    shared = sum(
        1
        for concept, word in getattr(first, "lexicon", {}).items()
        if getattr(root, "lexicon", {}).get(concept) == word
    )
    words = max(1, len(getattr(first, "lexicon", {})))
    origin = (getattr(first, "origins", None) or ["an unattributed parent"])[0]
    observed = (
        f"{first.name} was recorded as a distinct speech community on day "
        f"{getattr(first, 'created_day', 1)}, descending from {origin}. It shares "
        f"{shared} of {words} recorded concepts verbatim with {root.name}; the rest "
        f"have diverged through use."
    )
    return [
        _finding(
            "language",
            f"Language divergence — {first.name}",
            int(getattr(first, "created_day", 1)),
            observed,
            measured=_measured_change(metrics, int(getattr(first, "created_day", 1))),
            index=0,
        )
    ]


def _generations(
    events: list[dict[str, Any]], metrics: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    findings = []
    highest = 0
    for event in events:
        match = GENERATION_RE.search(event["description"])
        if not match:
            continue
        generation = int(match.group(1))
        if generation <= highest or generation < 2:
            continue
        highest = generation
        findings.append(
            _finding(
                "demography",
                f"First birth in generation {generation}",
                event["day"],
                event["description"].strip(),
                evidence=[event],
                measured=_measured_change(metrics, event["day"]),
                index=len(findings),
            )
        )
    return findings


def _nearby_events(events: list[dict[str, Any]], day: int, span: int = 4) -> list[dict[str, Any]]:
    return [
        event
        for event in events
        if abs(event["day"] - day) <= span and event["category"] in CAUSE_CATEGORIES
    ][:3]


def _anomalies(
    events: list[dict[str, Any]], metrics: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Statistical outliers in the recorded daily series, not opinions."""
    if len(metrics) < 10:
        return []
    findings: list[dict[str, Any]] = []
    used_days: list[int] = []

    def fresh(day: int, spacing: int = 60) -> bool:
        return all(abs(day - other) >= spacing for other in used_days)

    # Population shocks.
    shocks: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    for previous, current in zip(metrics, metrics[1:]):
        if current["day"] - previous["day"] > 3:
            continue
        before = previous.get("population")
        after = current.get("population")
        if before is None or after is None:
            continue
        delta = float(after) - float(before)
        threshold = max(3.0, float(before) * 0.08)
        if abs(delta) >= threshold:
            shocks.append((abs(delta), previous, current))
    for magnitude, previous, current in sorted(shocks, key=lambda item: item[0], reverse=True):
        if len(findings) >= 3 or not fresh(current["day"]):
            continue
        used_days.append(current["day"])
        delta = int(current["population"]) - int(previous["population"])
        direction = "fell" if delta < 0 else "rose"
        near = _nearby_events(events, current["day"])
        hypothesis = None
        if near:
            hypothesis = (
                "Temporal association only: "
                + "; ".join(f"day {event['day']} {event['title']}" for event in near)
                + ". The log records these nearby, not that they caused the change."
            )
        findings.append(
            _finding(
                "anomaly",
                f"Population {direction} {abs(delta)} in one step",
                current["day"],
                (
                    f"The recorded population moved from {int(previous['population'])} on day "
                    f"{previous['day']} to {int(current['population'])} on day {current['day']} "
                    f"({delta:+d}). That is a larger single-step change than the 8% threshold "
                    f"used to scan the series."
                ),
                evidence=_evidence(near),
                hypothesis=hypothesis,
                index=len(findings),
            )
        )

    # Inequality jump over any 30-day window.
    best: tuple[float, dict[str, Any], dict[str, Any]] | None = None
    for start in metrics:
        if start.get("inequality") is None:
            continue
        end = _metric_at(metrics, start["day"] + 30)
        if not end or end["day"] - start["day"] < 20 or end.get("inequality") is None:
            continue
        delta = float(end["inequality"]) - float(start["inequality"])
        if delta >= 0.12 and (best is None or delta > best[0]):
            best = (delta, start, end)
    if best:
        delta, start, end = best
        findings.append(
            _finding(
                "anomaly",
                f"Inequality rose {delta:.2f} in {end['day'] - start['day']} days",
                end["day"],
                (
                    f"The recorded Gini-style inequality index rose from {float(start['inequality']):.3f} "
                    f"on day {start['day']} to {float(end['inequality']):.3f} on day {end['day']}. "
                    f"This is a measured change in the metric, not an interpretation of it."
                ),
                measured=[f"inequality index {delta:+.3f}"],
                index=len(findings),
            )
        )

    # Technology acceleration.
    for start in metrics:
        if start.get("tech_count") is None:
            continue
        end = _metric_at(metrics, start["day"] + 10)
        if not end or end["day"] - start["day"] < 5 or end.get("tech_count") is None:
            continue
        delta = int(end["tech_count"]) - int(start["tech_count"])
        if delta >= 3 and fresh(end["day"]):
            used_days.append(end["day"])
            findings.append(
                _finding(
                    "anomaly",
                    f"{delta} technologies added in {end['day'] - start['day']} days",
                    end["day"],
                    (
                        f"The count of known technologies jumped from {int(start['tech_count'])} on day "
                        f"{start['day']} to {int(end['tech_count'])} on day {end['day']}. Whether this was "
                        f"diffusion, a research push, or immigration is not established by the count alone."
                    ),
                    measured=[f"technologies known {delta:+d}"],
                    index=len(findings),
                )
            )
            break

    return findings


def detect_emergence(run_id: str, engine: Any, session: Session) -> dict[str, Any]:
    events = _load_events(session, run_id)
    metrics = _load_metrics(session, run_id)

    findings: list[dict[str, Any]] = []
    findings.extend(_first_buildings(events, metrics))
    findings.extend(_first_technologies(events, metrics))
    findings.extend(_political_firsts(events, metrics))
    findings.extend(_diplomatic_firsts(events, metrics))
    findings.extend(_economic_firsts(events, metrics))
    findings.extend(_settlement_structure(events, metrics))
    findings.extend(_language_divergence(engine, events, metrics))
    findings.extend(_generations(events, metrics))
    findings.extend(_anomalies(events, metrics))

    findings.sort(key=lambda item: (item["day"], item["kind"], item["id"]))
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding["kind"]] = counts.get(finding["kind"], 0) + 1

    return {
        "run_id": run_id,
        "day": getattr(engine, "day", 0),
        "event_count": len(events),
        "metric_days": len(metrics),
        "counts": counts,
        "findings": findings[:100],
    }
