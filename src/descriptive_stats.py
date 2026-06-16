"""Compute descriptive statistics and exploratory overview plots.

Writes a summary CSV (accidents per year, severity distribution, weather
summary) and two overview figures that give a first impression of the data
before the actual research question analyses.

Usage:
    python src/descriptive_stats.py --table data/processed/analysis_table.csv \
        --accidents data/joined/accidents_stations.csv --out-dir results
"""

import argparse
import logging
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

log = logging.getLogger("descriptive_stats")

SEVERITY_LABELS = {1: "fatal", 2: "serious_injury", 3: "light_injury"}


def summarise(cells, accidents):
    """Build a long-format summary table."""
    rows = []
    for year, group in accidents.groupby("year"):
        rows.append(("accidents_per_year", str(year), "n_accidents", len(group)))
        rows.append(("accidents_per_year", str(year), "share_severe",
                     (group["severity"] <= 2).mean()))
    for severity, label in SEVERITY_LABELS.items():
        rows.append(("severity_distribution", label, "share",
                     (accidents["severity"] == severity).mean()))
    for year, group in cells.groupby("year"):
        share_rain = group["hours_rain"].sum() / group["n_hours"].sum()
        rows.append(("weather_per_year", str(year), "share_rainy_hours", share_rain))
        rows.append(("weather_per_year", str(year), "mean_temp",
                     group["mean_temp"].mean()))
    rows.append(("overview", "all", "n_accidents", len(accidents)))
    rows.append(("overview", "all", "n_stations", cells["station_id"].nunique()))
    rows.append(("overview", "all", "median_station_distance_km",
                 accidents["station_distance_km"].median()))
    return pd.DataFrame(rows, columns=["section", "group", "metric", "value"])


def plot_accidents(accidents, path):
    """Accidents by hour of day and by month."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

    by_hour = accidents.groupby(["hour", accidents["weekday"].isin([1, 7])])\
        .size().unstack()
    by_hour.columns = ["weekday", "weekend"]
    by_hour.plot(ax=axes[0])
    axes[0].set_xlabel("hour of day")
    axes[0].set_ylabel("number of accidents")
    axes[0].set_title("Accidents by hour of day")

    accidents.groupby("month").size().plot(kind="bar", ax=axes[1], color="steelblue")
    axes[1].set_xlabel("month")
    axes[1].set_ylabel("number of accidents")
    axes[1].set_title("Accidents by month")

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_weather(cells, path):
    """Monthly mean temperature and share of rainy hours over the years."""
    monthly = cells.groupby(["year", "month"]).agg(
        mean_temp=("mean_temp", "mean"),
        hours_rain=("hours_rain", "sum"),
        n_hours=("n_hours", "sum")).reset_index()
    monthly["share_rain"] = monthly["hours_rain"] / monthly["n_hours"]
    monthly["date"] = pd.to_datetime(dict(year=monthly["year"],
                                          month=monthly["month"], day=1))

    fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
    axes[0].plot(monthly["date"], monthly["mean_temp"], color="darkred")
    axes[0].set_ylabel("mean temperature (degC)")
    axes[0].set_title("Monthly weather at the selected DWD stations")
    axes[1].plot(monthly["date"], monthly["share_rain"], color="steelblue")
    axes[1].set_ylabel("share of rainy hours")

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--table", default="data/processed/analysis_table.csv")
    parser.add_argument("--accidents", default="data/joined/accidents_stations.csv")
    parser.add_argument("--out-dir", default="results")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    sns.set_theme(style="whitegrid")

    for path in (args.table, args.accidents):
        if not os.path.exists(path):
            log.error("input file %s not found", path)
            sys.exit(1)

    cells = pd.read_csv(args.table)
    accidents = pd.read_csv(args.accidents)

    figures_dir = os.path.join(args.out_dir, "figures")
    os.makedirs(figures_dir, exist_ok=True)

    summary = summarise(cells, accidents)
    summary_file = os.path.join(args.out_dir, "summary_statistics.csv")
    summary.to_csv(summary_file, index=False)
    log.info("wrote %s", summary_file)

    plot_accidents(accidents, os.path.join(figures_dir, "overview_accidents.png"))
    plot_weather(cells, os.path.join(figures_dir, "overview_weather.png"))
    log.info("wrote overview figures to %s", figures_dir)


if __name__ == "__main__":
    main()
