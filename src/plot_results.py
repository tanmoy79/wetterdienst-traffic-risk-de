"""Plot the results of one research question.

Reads the tidy result CSV written by analyze_rq.py and produces one figure
(PNG) per research question.

Usage:
    python src/plot_results.py --rq 1 --results results/rq1_results.csv \
        --output results/figures/rq1.png
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

log = logging.getLogger("plot_results")


def get_values(results, section, metric):
    """Return group -> value for one section/metric as a series."""
    subset = results[(results["section"] == section) & (results["metric"] == metric)]
    return subset.set_index("group")["value"]


def plot_rq1(results):
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))

    ratios = pd.concat([
        get_values(results, "condition_ratios", "rate_ratio"),
        get_values(results, "standardized_ratios", "rate_ratio"),
    ])
    ratios = ratios.reindex(["wet_road", "icy_road", "light_rain", "heavy_rain"])
    ratios.plot(kind="bar", ax=axes[0, 0], color="steelblue")
    axes[0, 0].axhline(1.0, color="black", linewidth=0.8)
    axes[0, 0].set_title("Standardized rate ratios vs. dry (1 = no effect)\n"
                         "wet/icy: per weather hour; light/heavy: cell level (diluted)")
    axes[0, 0].set_ylabel("observed / expected accidents")

    order = ["none", "low", "medium", "high"]
    rain = get_values(results, "rate_by_rain_share", "rate_per_1000h").reindex(order)
    rain.plot(kind="bar", ax=axes[0, 1], color="darkcyan")
    axes[0, 1].set_title("Raw accident rate by share of rainy hours\n"
                         "(not adjusted for time of day or season)")
    axes[0, 1].set_ylabel("accidents per 1000 station-hours")

    severe = get_values(results, "severity_by_road_condition", "share_severe")
    severe = severe.reindex(["dry", "wet", "icy"])
    severe.plot(kind="bar", ax=axes[1, 0], color="indianred")
    axes[1, 0].set_title("Share of severe accidents by road condition")

    loss = get_values(results, "type_by_road_condition", "share_loss_of_control")
    loss = loss.reindex(["dry", "wet", "icy"])
    loss.plot(kind="bar", ax=axes[1, 1], color="slategray")
    axes[1, 1].set_title("Share of loss-of-control accidents by road condition")

    for ax in axes.flat:
        ax.tick_params(axis="x", rotation=0)
        ax.set_xlabel("")
    fig.suptitle("RQ1: Precipitation, frost and accident risk")
    fig.tight_layout()
    return fig


def plot_rq2(results):
    fig, ax = plt.subplots(figsize=(8, 5))
    order = ["neutral", "strong_sun", "hot", "rainy"]
    rates = get_values(results, "commuter_rate_by_condition", "rate_per_1000h")
    rates.reindex(order).plot(kind="bar", ax=ax,
                              color=["gray", "orange", "darkred", "steelblue"])
    ax.set_ylabel("accidents per 1000 station-hours")
    ax.set_title("RQ2: Summer commuter-hour accident rate by weather condition")
    ax.tick_params(axis="x", rotation=0)

    r = get_values(results, "solar_rate_correlation", "pearson_r").iloc[0]
    p = get_values(results, "solar_rate_correlation", "p_value").iloc[0]
    ax.annotate(f"solar vs. rate: r = {r:.2f} (p = {p:.3f})",
                xy=(0.02, 0.95), xycoords="axes fraction")
    return fig


def plot_rq3(results):
    sensitivity = get_values(results, "state_sensitivity", "sensitivity_index")
    sensitivity = sensitivity.sort_values()
    kinds = results[results["section"] == "state_kind"].set_index("group")["metric"]
    colors = ["indianred" if kinds.get(state) == "city_state" else "steelblue"
              for state in sensitivity.index]

    fig, ax = plt.subplots(figsize=(8, 6))
    sensitivity.plot(kind="barh", ax=ax, color=colors)
    ax.axvline(1.0, color="black", linewidth=0.8)
    ax.set_xlabel("weather sensitivity index (rate ratio, 1 = no effect)")
    ax.set_title("RQ3: Weather sensitivity by federal state\n"
                 "(red = city states, blue = territorial states)")
    return fig


def plot_rq4(results):
    yearly = results[results["section"] == "yearly_risk"]
    yearly = yearly.pivot(index="group", columns="metric", values="value")
    yearly.index = yearly.index.astype(int)

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    axes[0].plot(yearly.index, yearly["rain_ratio"], marker="o", label="rain")
    axes[0].plot(yearly.index, yearly["frost_ratio"], marker="s", label="frost")
    axes[0].axhline(1.0, color="black", linewidth=0.8)
    axes[0].set_title("Weather rate ratios per year")
    axes[0].legend()

    axes[1].plot(yearly.index, yearly["share_severe_on_wet_or_icy"],
                 marker="o", color="indianred")
    axes[1].set_title("Share of severe accidents\non wet/icy roads")

    axes[2].plot(yearly.index, yearly["n_accidents"], marker="o", color="gray")
    axes[2].set_title("Accidents per year (joined data)")

    slope = get_values(results, "rain_ratio_trend", "slope_per_year").iloc[0]
    p = get_values(results, "rain_ratio_trend", "p_value").iloc[0]
    axes[0].annotate(f"rain trend: {slope:+.3f}/year (p = {p:.3f})",
                     xy=(0.02, 0.02), xycoords="axes fraction", fontsize=9)
    fig.suptitle(f"RQ4: Evolution of weather-related accident risk "
                 f"{yearly.index.min()}-{yearly.index.max()}")
    fig.tight_layout()
    return fig


PLOTS = {1: plot_rq1, 2: plot_rq2, 3: plot_rq3, 4: plot_rq4}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rq", type=int, required=True, choices=PLOTS)
    parser.add_argument("--results", default=None,
                        help="result CSV (default: results/rq<N>_results.csv)")
    parser.add_argument("--output", default=None,
                        help="output PNG (default: results/figures/rq<N>.png)")
    args = parser.parse_args(argv)
    results_file = args.results or f"results/rq{args.rq}_results.csv"
    output = args.output or f"results/figures/rq{args.rq}.png"

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    sns.set_theme(style="whitegrid")

    if not os.path.exists(results_file):
        log.error("result file %s not found, run analyze_rq.py first", results_file)
        sys.exit(1)
    results = pd.read_csv(results_file)

    fig = PLOTS[args.rq](results)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    fig.savefig(output, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("wrote %s", output)


if __name__ == "__main__":
    main()
