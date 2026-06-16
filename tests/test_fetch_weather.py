"""Tests for fetch_weather.py.

These tests cover the pure helpers (station selection, long->wide pivot,
local-time reindex) with synthetic dataframes; they do not exercise the
wetterdienst network calls.
"""

import pandas as pd
import pytest

import fetch_weather


# ----- select_stations ---------------------------------------------------


def _station_row(station_id, state, has_solar_in_dataset, name=None):
    return {
        "station_id": str(station_id),
        "name": name or f"Station {station_id}",
        "state": state,
        "latitude": 50.0,
        "longitude": 10.0,
    }


def test_select_stations_intersects_temp_and_precip_and_prefers_solar():
    temp = pd.DataFrame([
        _station_row(1, "Berlin", True),
        _station_row(2, "Berlin", True),
        _station_row(3, "Berlin", False),
        _station_row(4, "Bayern", False),
    ])
    precip = pd.DataFrame([
        _station_row(1, "Berlin", True),
        _station_row(2, "Berlin", True),
        _station_row(3, "Berlin", False),
        _station_row(4, "Bayern", False),
    ])
    # only station 1 carries solar
    solar = pd.DataFrame([_station_row(1, "Berlin", True)])

    picked = fetch_weather.select_stations(temp, precip, solar, per_state=2)

    assert list(picked.columns) == [
        "station_id", "name", "state", "lat", "lon", "has_solar"
    ]
    # 2 stations from Berlin (per_state=2), 1 station from Bayern (only one available)
    assert sorted(picked["state"].tolist()) == ["Bayern", "Berlin", "Berlin"]
    # Berlin's solar-carrying station 1 must be in the picked set
    berlin = picked[picked["state"] == "Berlin"]
    assert 1 in berlin["station_id"].tolist()
    assert berlin[berlin["station_id"] == 1]["has_solar"].iloc[0] is True or \
           berlin[berlin["station_id"] == 1]["has_solar"].iloc[0] == True  # noqa: E712


def test_select_stations_drops_stations_missing_either_required_parameter():
    temp = pd.DataFrame([_station_row(1, "Berlin", False),
                         _station_row(2, "Berlin", False)])
    precip = pd.DataFrame([_station_row(1, "Berlin", False)])  # station 2 has no precip
    solar = pd.DataFrame(columns=["station_id", "name", "state",
                                  "latitude", "longitude"])

    picked = fetch_weather.select_stations(temp, precip, solar, per_state=5)
    assert picked["station_id"].tolist() == [1]
    assert picked["has_solar"].tolist() == [False]


def test_select_stations_empty_when_no_overlap():
    temp = pd.DataFrame([_station_row(1, "Berlin", False)])
    precip = pd.DataFrame([_station_row(2, "Berlin", False)])
    solar = pd.DataFrame(columns=["station_id", "name", "state",
                                  "latitude", "longitude"])
    picked = fetch_weather.select_stations(temp, precip, solar, per_state=2)
    assert picked.empty
    assert list(picked.columns) == [
        "station_id", "name", "state", "lat", "lon", "has_solar"
    ]


# ----- pivot_to_wide -----------------------------------------------------


def test_pivot_to_wide_maps_parameters_to_downstream_columns():
    ts = pd.Timestamp("2020-01-01 00:00", tz="UTC")
    long = pd.DataFrame([
        {"station_id": 44, "parameter": "temperature_air_mean_2m",
         "date": ts, "value": 5.2},
        {"station_id": 44, "parameter": "precipitation_height",
         "date": ts, "value": 0.3},
        {"station_id": 44, "parameter": "radiation_global",
         "date": ts, "value": 12.0},
    ])
    wide = fetch_weather.pivot_to_wide(long)
    row = wide.iloc[0]
    assert row["station_id"] == 44
    assert row["temp_c"] == pytest.approx(5.2)
    assert row["precip_mm"] == pytest.approx(0.3)
    assert row["solar_j_cm2"] == pytest.approx(12.0)


def test_pivot_to_wide_fills_missing_columns_with_nan():
    ts = pd.Timestamp("2020-01-01 00:00", tz="UTC")
    long = pd.DataFrame([
        {"station_id": 44, "parameter": "temperature_air_mean_2m",
         "date": ts, "value": 5.2},
        {"station_id": 44, "parameter": "precipitation_height",
         "date": ts, "value": 0.3},
    ])
    wide = fetch_weather.pivot_to_wide(long)
    assert "solar_j_cm2" in wide.columns
    assert pd.isna(wide["solar_j_cm2"].iloc[0])


# ----- to_local_complete_series ------------------------------------------


def test_to_local_complete_series_converts_and_fills_gaps():
    wide = pd.DataFrame([
        {"station_id": 44,
         "date": pd.Timestamp("2020-06-01 10:00", tz="UTC"),
         "temp_c": 15.0, "precip_mm": 0.0, "solar_j_cm2": 80.0},
        {"station_id": 44,
         "date": pd.Timestamp("2020-06-01 13:00", tz="UTC"),
         "temp_c": 18.0, "precip_mm": 0.5, "solar_j_cm2": 90.0},
    ])
    result = fetch_weather.to_local_complete_series(wide, 2020, 2020)

    # 2020 is a leap year: 366 * 24 hours per station
    assert len(result) == 366 * 24
    assert list(result.columns) == [
        "station_id", "timestamp", "temp_c", "precip_mm", "solar_j_cm2"
    ]
    # 10:00 UTC is 12:00 local in June (CEST)
    row = result[result["timestamp"] == pd.Timestamp(
        "2020-06-01 12:00", tz="Europe/Berlin")].iloc[0]
    assert row["temp_c"] == 15.0
    # 11:00 UTC has no observation -> gap is NaN at 13:00 local
    gap = result[result["timestamp"] == pd.Timestamp(
        "2020-06-01 13:00", tz="Europe/Berlin")].iloc[0]
    assert pd.isna(gap["temp_c"])


def test_to_local_complete_series_handles_empty_input():
    empty = pd.DataFrame(columns=["station_id", "date",
                                  "temp_c", "precip_mm", "solar_j_cm2"])
    result = fetch_weather.to_local_complete_series(empty, 2020, 2020)
    assert result.empty
    assert list(result.columns) == [
        "station_id", "timestamp", "temp_c", "precip_mm", "solar_j_cm2"
    ]
