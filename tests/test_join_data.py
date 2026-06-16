"""Tests for join_data.py."""

import pandas as pd
import pytest

import join_data


def test_nearest_station_assigns_closest():
    stations = pd.DataFrame({
        "station_id": [100, 200],
        "lon": [10.0, 13.0],
        "lat": [50.0, 52.5],
    })
    accidents = pd.DataFrame({
        "lon": [10.1, 13.1, 11.5],
        "lat": [50.1, 52.4, 51.2],
    })
    ids, distances = join_data.nearest_station(accidents, stations)
    assert list(ids[:2]) == [100, 200]
    assert distances[0] < 20  # ~13 km away
    assert distances[2] > 50  # the midpoint is far from both


def test_to_xy_km_scales_longitude():
    # at 60 degrees latitude one degree of longitude is only ~55 km
    x, y = join_data.to_xy_km(1.0, 1.0, 60.0)
    assert x == pytest.approx(55.65, abs=1)
    assert y == pytest.approx(110.6, abs=1)
