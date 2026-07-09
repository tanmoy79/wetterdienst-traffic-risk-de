"""Tests for plot_results.py."""

import pandas as pd

import plot_results


def test_get_values_returns_group_value_series():
    results = pd.DataFrame({
        "section": ["s", "s", "other"],
        "group": ["a", "b", "c"],
        "metric": ["m", "m", "m"],
        "value": [1.0, 2.0, 9.0],
    })
    series = plot_results.get_values(results, "s", "m")
    assert series["a"] == 1.0
    assert series["b"] == 2.0
    assert "c" not in series.index


def test_main_writes_png(tmp_path):
    results = pd.DataFrame({
        "section": (["commuter_rate_by_condition"] * 4
                    + ["solar_rate_correlation"] * 2),
        "group": ["neutral", "strong_sun", "hot", "rainy",
                  "station_months", "station_months"],
        "metric": ["rate_per_1000h"] * 4 + ["pearson_r", "p_value"],
        "value": [1000, 1100, 1050, 1200, 0.1, 0.3],
    })
    results_file = tmp_path / "rq2_results.csv"
    results.to_csv(results_file, index=False)
    output = tmp_path / "rq2.png"

    plot_results.main(["--rq", "2", "--results", str(results_file),
                       "--output", str(output)])
    assert output.exists()
    assert output.stat().st_size > 0
