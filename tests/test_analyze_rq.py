"""Tests for analyze_rq.py."""

import pandas as pd
import pytest

import analyze_rq


def test_rate_per_1000h():
    cells = pd.DataFrame({"n_hours": [500, 500], "n_accidents": [1, 2]})
    assert analyze_rq.rate_per_1000h(cells) == pytest.approx(3.0)


def test_rate_per_1000h_empty():
    cells = pd.DataFrame({"n_hours": [], "n_accidents": []})
    assert pd.isna(analyze_rq.rate_per_1000h(cells))


def test_rates_by_share_bins():
    cells = pd.DataFrame({
        "rain_share": [0.0, 0.1, 0.5],
        "n_hours": [1000, 1000, 1000],
        "n_accidents": [10, 20, 40],
    })
    rows = analyze_rq.rates_by_share(cells, "rain_share", "test")
    result = pd.DataFrame(rows, columns=["section", "group", "metric", "value"])
    rates = result[result["metric"] == "rate_per_1000h"].set_index("group")["value"]

    assert rates["none"] == pytest.approx(10.0)
    assert rates["low"] == pytest.approx(20.0)
    assert rates["high"] == pytest.approx(40.0)


def make_cells(rows):
    """Build a small cell table; rows are (hour, rain_share, n_hours, n_accidents)."""
    return pd.DataFrame({
        "station_id": 1,
        "month": 1,
        "is_weekend": False,
        "hour": [r[0] for r in rows],
        "rain_share": [r[1] for r in rows],
        "frost_share": [r[1] for r in rows],
        "n_hours": [r[2] for r in rows],
        "n_accidents": [r[3] for r in rows],
    })


def test_standardized_ratio_recovers_true_effect():
    # within the same stratum (hour 8), rainy cells have twice the rate
    cells = make_cells([(8, 0.0, 1000, 10), (8, 0.0, 1000, 10),
                        (8, 0.5, 1000, 20), (8, 0.5, 1000, 20)])
    ratio = analyze_rq.standardized_ratio(cells[cells["rain_share"] > 0.35],
                                          cells[cells["rain_share"] == 0])
    assert ratio == pytest.approx(2.0)


def test_standardized_ratio_controls_for_traffic_volume():
    # rain happens at the quiet hour 3, but within each hour the rate is
    # identical, so the standardized ratio must be 1 (a naive comparison
    # of raw rates would give 0.1)
    cells = make_cells([(8, 0.0, 1000, 100), (8, 0.5, 1000, 100),
                        (3, 0.0, 1000, 10), (3, 0.5, 1000, 10)])
    ratio = analyze_rq.standardized_ratio(cells[cells["rain_share"] > 0.35],
                                          cells[cells["rain_share"] == 0])
    assert ratio == pytest.approx(1.0)


def make_condition_cells(rows):
    """Cell table for the road-condition ratios; rows are
    (hour, n_hours, hours_rain, n_wet_road, n_dry_road)."""
    df = pd.DataFrame({
        "station_id": 1,
        "month": 1,
        "is_weekend": False,
        "hour": [r[0] for r in rows],
        "n_hours": [r[1] for r in rows],
        "hours_rain": [r[2] for r in rows],
        "hours_frost": [r[2] for r in rows],
        "n_wet_road": [r[3] for r in rows],
        "n_icy_road": [r[3] for r in rows],
    })
    df["n_accidents"] = df["n_wet_road"] + df["n_icy_road"] + [r[4] for r in rows]
    return analyze_rq.add_exposure_columns(df)


def test_condition_ratio_recovers_true_effect():
    # wet-road accidents happen at twice the rate per rainy hour
    # (dry-road rate: 90 accidents / 900 dry hours = 0.1 per hour)
    cells = make_condition_cells([(8, 1000, 100, 20, 90)])
    ratio = analyze_rq.condition_ratio(cells, "n_wet_road", "hours_rain",
                                       "n_dry_road", "hours_no_rain")
    assert ratio == pytest.approx(2.0)


def test_condition_ratio_controls_for_traffic_volume():
    # all the rain falls in the quiet night hour, but within each hour the
    # wet rate equals the dry rate, so the ratio must be 1
    cells = make_condition_cells([(8, 900, 0, 0, 900),
                                  (3, 900, 500, 50, 40)])
    ratio = analyze_rq.condition_ratio(cells, "n_wet_road", "hours_rain",
                                       "n_dry_road", "hours_no_rain")
    assert ratio == pytest.approx(1.0)


def test_weather_ratios_on_synthetic_cells():
    cells = make_condition_cells([(8, 1000, 100, 20, 90)])
    rain_ratio, frost_ratio = analyze_rq.weather_ratios(cells)
    assert rain_ratio == pytest.approx(2.0)
    assert frost_ratio == pytest.approx(2.0)  # month 1 counts as winter
