"""Tests for descriptive_stats.py."""

import pandas as pd

import descriptive_stats


def get(summary, section, group, metric):
    """Look up one value from the long-format summary table."""
    match = summary[(summary["section"] == section) &
                    (summary["group"] == group) &
                    (summary["metric"] == metric)]
    return match["value"].iloc[0]


def test_summarise_overview_counts():
    accidents = pd.DataFrame({
        "year": [2020, 2020, 2021],
        "severity": [1, 3, 2],
        "station_distance_km": [10.0, 20.0, 30.0],
    })
    cells = pd.DataFrame({
        "year": [2020, 2021], "station_id": [1, 2],
        "hours_rain": [100, 200], "n_hours": [1000, 1000],
        "mean_temp": [10.0, 12.0],
    })
    summary = descriptive_stats.summarise(cells, accidents)
    assert get(summary, "overview", "all", "n_accidents") == 3
    assert get(summary, "overview", "all", "n_stations") == 2
    assert get(summary, "overview", "all", "median_station_distance_km") == 20.0


def test_summarise_share_severe_per_year():
    accidents = pd.DataFrame({
        "year": [2020, 2020, 2020, 2020],
        "severity": [1, 2, 3, 3],          # 2 of 4 are severe (severity <= 2)
        "station_distance_km": [10.0, 10.0, 10.0, 10.0],
    })
    cells = pd.DataFrame({
        "year": [2020], "station_id": [1],
        "hours_rain": [100], "n_hours": [1000], "mean_temp": [10.0],
    })
    summary = descriptive_stats.summarise(cells, accidents)
    assert get(summary, "accidents_per_year", "2020", "share_severe") == 0.5
