"""Tests for build_features.py."""

import argparse

import pandas as pd

import build_features

DEFAULT_ARGS = argparse.Namespace(
    rain_threshold=0.1, heavy_rain_threshold=4.0, frost_threshold=0.0,
    heat_threshold=30.0, strong_sun_threshold=200.0)


def test_classify_weather_hours_thresholds():
    weather = pd.DataFrame({
        "timestamp": ["2020-01-01 00:00"] * 4,
        "temp_c": [-2.0, 5.0, 31.0, 10.0],
        "precip_mm": [0.0, 0.5, 0.0, 6.0],
        "solar_j_cm2": [0.0, None, 250.0, 10.0],
    })
    result = build_features.classify_weather_hours(weather, DEFAULT_ARGS)

    assert list(result["is_frost"]) == [True, False, False, False]
    assert list(result["is_rain"]) == [False, True, False, True]
    assert list(result["is_light_rain"]) == [False, True, False, False]
    assert list(result["is_heavy_rain"]) == [False, False, False, True]
    assert list(result["is_hot"]) == [False, False, True, False]
    assert list(result["is_strong_sun"]) == [False, False, True, False]


def test_classify_drops_hours_without_measurements():
    weather = pd.DataFrame({
        "timestamp": ["2020-01-01 00:00"] * 2,
        "temp_c": [5.0, None],
        "precip_mm": [0.0, 1.0],
        "solar_j_cm2": [0.0, 0.0],
    })
    result = build_features.classify_weather_hours(weather, DEFAULT_ARGS)
    assert len(result) == 1


def test_aggregate_weather_handles_mixed_utc_offsets():
    # the hourly CSV mixes +01:00 (winter) and +02:00 (summer) offsets
    weather = pd.DataFrame({
        "station_id": [1, 1],
        "timestamp": ["2020-01-06 05:00:00+01:00", "2020-07-06 05:00:00+02:00"],
        "temp_c": [0.0, 20.0],
        "precip_mm": [0.0, 0.0],
        "solar_j_cm2": [0.0, 0.0],
        "is_rain": [False, False], "is_light_rain": [False, False],
        "is_heavy_rain": [False, False], "is_frost": [False, False],
        "is_hot": [False, False], "is_strong_sun": [False, False],
    })
    cells = build_features.aggregate_weather(weather)
    # both hours must keep their local hour of day (5:00) and month
    assert list(cells["hour"]) == [5, 5]
    assert sorted(cells["month"]) == [1, 7]


def test_aggregate_accidents_counts_and_weekend():
    accidents = pd.DataFrame({
        "station_id": [1, 1, 1],
        "year": [2020] * 3, "month": [6] * 3, "hour": [8] * 3,
        "weekday": [1, 2, 2],          # 1 = Sunday (weekend), 2 = Monday
        "severity": [1, 2, 3],
        "accident_type": [1, 1, 5],
        "road_condition": [0, 1, 2],
    })
    cells = build_features.aggregate_accidents(accidents)

    weekend = cells[cells["is_weekend"]]
    weekday = cells[~cells["is_weekend"]]
    assert weekend["n_accidents"].iloc[0] == 1
    assert weekday["n_accidents"].iloc[0] == 2
    assert weekday["n_loss_control"].iloc[0] == 1
    assert weekday["n_icy_road"].iloc[0] == 1


def test_add_features_commuter_flag():
    cells = pd.DataFrame({
        "n_hours": [10, 10, 10],
        "hours_rain": [5, 0, 0],
        "hours_heavy_rain": [0, 0, 0],
        "hours_frost": [0, 0, 0],
        "hours_hot": [0, 0, 0],
        "hours_strong_sun": [0, 0, 0],
        "is_weekend": [False, False, True],
        "hour": [8, 12, 8],
    })
    result = build_features.add_features(cells)
    assert result["rain_share"].iloc[0] == 0.5
    # only the weekday cell at 8:00 is a commuter cell
    assert list(result["is_commuter_hour"]) == [True, False, False]
