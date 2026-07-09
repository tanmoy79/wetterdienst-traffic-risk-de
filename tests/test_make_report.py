"""Tests for make_report.py."""

import math

import pandas as pd

import make_report


def test_value_finds_existing():
    summary = pd.DataFrame({
        "section": ["overview"], "group": ["all"],
        "metric": ["n_accidents"], "value": [1000],
    })
    assert make_report.value(summary, "overview", "all", "n_accidents") == 1000


def test_value_returns_nan_when_missing():
    summary = pd.DataFrame({
        "section": ["overview"], "group": ["all"],
        "metric": ["n_accidents"], "value": [1000],
    })
    assert math.isnan(make_report.value(summary, "x", "y", "z"))
