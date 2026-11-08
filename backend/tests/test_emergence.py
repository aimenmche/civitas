from __future__ import annotations

from app.services.emergence import _measured_change, _metric_at, season_of, year_of


def test_year_and_season_rollover() -> None:
    assert year_of(1) == 1
    assert year_of(40) == 1
    assert year_of(41) == 2
    assert year_of(100) == 3

    assert season_of(1) == "Spring"
    assert season_of(10) == "Spring"
    assert season_of(11) == "Summer"
    assert season_of(20) == "Summer"
    assert season_of(21) == "Autumn"
    assert season_of(31) == "Winter"
    assert season_of(40) == "Winter"
    assert season_of(41) == "Spring"


def test_metric_at_returns_latest_row_at_or_before_day() -> None:
    metrics = [
        {"day": 1, "population": 10},
        {"day": 5, "population": 12},
        {"day": 9, "population": 14},
    ]
    assert _metric_at(metrics, 0) is None
    assert _metric_at(metrics, 1)["population"] == 10
    assert _metric_at(metrics, 4)["population"] == 10
    assert _metric_at(metrics, 5)["population"] == 12
    assert _metric_at(metrics, 50)["population"] == 14
    assert _metric_at([], 10) is None


def test_measured_change_reports_only_thresholds_that_clear() -> None:
    metrics = [
        {
            "day": 10,
            "population": 100,
            "settlements": 2,
            "tech_count": 4,
            "avg_happiness": 50.0,
            "inequality": 0.2,
        },
        {
            "day": 70,
            "population": 108,
            "settlements": 2,
            "tech_count": 5,
            "avg_happiness": 51.0,
            "inequality": 0.26,
        },
    ]
    rows = _measured_change(metrics, 10)

    assert any("population +8" in row for row in rows)
    assert any("technologies known +1" in row for row in rows)
    assert any("inequality index +0.060" in row for row in rows)
    # +1 happiness is below the 3-point reporting threshold.
    assert not any("mean happiness" in row for row in rows)
    # No settlement changed, so no line is emitted.
    assert not any("settlements" in row for row in rows)
    assert all("over the 60 days after day 10" in row for row in rows)


def test_measured_change_needs_a_later_row() -> None:
    metrics = [{"day": 10, "population": 100}]
    assert _measured_change(metrics, 10) == []
