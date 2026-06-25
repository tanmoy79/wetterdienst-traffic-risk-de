"""Tests for fetch_weather.py.

These cover the pure helper functions (station selection, long->wide pivot,
local-time reindex) with small made-up dataframes. They do NOT call
wetterdienst, so they run fast and need no internet.
"""

import pandas as pd
import pytest

import fetch_weather


def station_row(station_id, state, name=None):
    """A single fake station row, as wetterdienst would return it."""
    return {
        "station_id": str(station_id),
        "name": name or f"Station {station_id}",
        "state": state,
        "latitude": 50.0,
        "longitude": 10.0,
    }


# ----- select_stations ---------------------------------------------------

def test_select_stations_prefers_solar_and_limits_per_state():
    temp = pd.DataFrame([station_row(1, "Berlin"), station_row(2, "Berlin"),
                         station_row(3, "Berlin"), station_row(4, "Bayern")])
    precip = temp.copy()
    solar = pd.DataFrame([station_row(1, "Berlin")])   # only station 1 has solar

    picked = fetch_weather.select_stations(temp, precip, solar, per_state=2)

    assert list(picked.columns) == ["station_id", "name", "state",
                                    "lat", "lon", "has_solar"]
    # 2 from Berlin (per_state=2), 1 from Bayern (only one exists)
    assert sorted(picked["state"]) == ["Bayern", "Berlin", "Berlin"]
    # the Berlin station that has solar must be among the picks
    berlin = picked[picked["state"] == "Berlin"]
    assert 1 in berlin["station_id"].tolist()


def test_select_stations_drops_stations_missing_a_required_parameter():
    temp = pd.DataFrame([station_row(1, "Berlin"), station_row(2, "Berlin")])
    precip = pd.DataFrame([station_row(1, "Berlin")])   # station 2 has no precip
    solar = pd.DataFrame(columns=["station_id", "name", "state",
                                  "latitude", "longitude"])

    picked = fetch_weather.select_stations(temp, precip, solar, per_state=5)
    assert picked["station_id"].tolist() == [1]
    assert picked["has_solar"].tolist() == [False]


def test_select_stations_empty_when_no_overlap():
    temp = pd.DataFrame([station_row(1, "Berlin")])
    precip = pd.DataFrame([station_row(2, "Berlin")])
    solar = pd.DataFrame(columns=["station_id", "name", "state",
                                  "latitude", "longitude"])
    picked = fetch_weather.select_stations(temp, precip, solar, per_state=2)
    assert picked.empty


# ----- pivot_to_wide -----------------------------------------------------

def test_pivot_to_wide_maps_parameters_to_our_columns():
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
    assert row["temp_c"] == pytest.approx(5.2)
    assert row["precip_mm"] == pytest.approx(0.3)
    assert row["solar_j_cm2"] == pytest.approx(12.0)


def test_pivot_to_wide_fills_missing_solar_with_nan():
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

def test_to_local_complete_series_converts_time_and_fills_gaps():
    wide = pd.DataFrame([
        {"station_id": 44, "date": pd.Timestamp("2020-06-01 10:00", tz="UTC"),
         "temp_c": 15.0, "precip_mm": 0.0, "solar_j_cm2": 80.0},
        {"station_id": 44, "date": pd.Timestamp("2020-06-01 13:00", tz="UTC"),
         "temp_c": 18.0, "precip_mm": 0.5, "solar_j_cm2": 90.0},
    ])
    result = fetch_weather.to_local_complete_series(wide, 2020, 2020)

    assert len(result) == 366 * 24          # 2020 is a leap year
    assert list(result.columns) == ["station_id", "timestamp",
                                    "temp_c", "precip_mm", "solar_j_cm2"]
    # 10:00 UTC is 12:00 local in June (summer time)
    row = result[result["timestamp"] == pd.Timestamp(
        "2020-06-01 12:00", tz="Europe/Berlin")].iloc[0]
    assert row["temp_c"] == 15.0
    # 11:00 UTC was never measured -> the gap is NaN
    gap = result[result["timestamp"] == pd.Timestamp(
        "2020-06-01 13:00", tz="Europe/Berlin")].iloc[0]
    assert pd.isna(gap["temp_c"])


def test_to_local_complete_series_handles_empty_input():
    empty = pd.DataFrame(columns=["station_id", "date",
                                  "temp_c", "precip_mm", "solar_j_cm2"])
    result = fetch_weather.to_local_complete_series(empty, 2020, 2020)
    assert result.empty
