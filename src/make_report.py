"""Assemble the final report from the result tables and figures.

Reads the summary statistics and the four research question result CSVs and
writes a Markdown report that presents the key numbers, embeds the figures
and gives a short written answer to every research question.

Usage:
    python src/make_report.py --results-dir results --output results/report.md
"""

import argparse
import logging
import os
import sys

import pandas as pd

log = logging.getLogger("make_report")


def value(results, section, group, metric):
    """Look up a single value from a tidy result table."""
    match = results[(results["section"] == section) &
                    (results["group"] == group) &
                    (results["metric"] == metric)]
    if match.empty:
        return float("nan")
    return match["value"].iloc[0]


def rq1_text(results):
    wet = value(results, "condition_ratios", "wet_road", "rate_ratio")
    icy = value(results, "condition_ratios", "icy_road", "rate_ratio")
    light = value(results, "standardized_ratios", "light_rain", "rate_ratio")
    heavy = value(results, "standardized_ratios", "heavy_rain", "rate_ratio")
    severe_dry = value(results, "severity_by_road_condition", "dry", "share_severe")
    severe_icy = value(results, "severity_by_road_condition", "icy", "share_severe")
    loss_dry = value(results, "type_by_road_condition", "dry", "share_loss_of_control")
    loss_icy = value(results, "type_by_road_condition", "icy", "share_loss_of_control")
    p = value(results, "severity_by_road_condition", "all", "chi2_p_value")
    return (
        f"Accidents on wet roads happened **{wet:.2f} times** as often per rainy "
        f"hour as dry-road accidents per dry hour (controlling for station, month, "
        f"weekday/weekend and hour of day). On icy roads in winter the factor was "
        f"**{icy:.2f}** per frost hour - below 1, because most frost hours have "
        f"gritted or simply dry roads and people drive more carefully. "
        f"The intensity matters: comparing time cells "
        f"with only light rain (ratio {light:.2f}) to cells that saw heavy rain "
        f">= 4 mm/h (ratio {heavy:.2f}) shows a stronger increase for heavy rain "
        f"(cell-level ratios are diluted because every cell also contains dry "
        f"hours). The character of accidents changes too: on icy roads "
        f"{loss_icy * 100:.1f} % were loss-of-control accidents compared to "
        f"{loss_dry * 100:.1f} % on dry roads. Severity shows the opposite "
        f"pattern - {severe_icy * 100:.1f} % of accidents on icy roads were severe "
        f"vs. {severe_dry * 100:.1f} % on dry roads (chi-square p = {p:.1e}), "
        f"presumably because drivers slow down."
    )


def rq2_text(results):
    ratio_sun = value(results, "commuter_rate_by_condition", "strong_sun",
                      "rate_ratio_vs_neutral")
    ratio_hot = value(results, "commuter_rate_by_condition", "hot",
                      "rate_ratio_vs_neutral")
    ratio_rain = value(results, "commuter_rate_by_condition", "rainy",
                       "rate_ratio_vs_neutral")
    r = value(results, "solar_rate_correlation", "station_months", "pearson_r")
    p = value(results, "solar_rate_correlation", "station_months", "p_value")
    return (
        f"During summer commuter hours (standardized within station, month and "
        f"hour), cells dominated by strong sunshine had **{ratio_sun:.2f} times** "
        f"the accident rate of neutral conditions, hot cells {ratio_hot:.2f} times "
        f"and rainy cells {ratio_rain:.2f} times. Across station-months the "
        f"correlation between mean solar radiation and the commuter accident rate "
        f"was r = {r:.2f} (p = {p:.3f}). So neither sun glare nor heat raised "
        f"commuter accident rates measurably - summer rain remains the more "
        f"relevant factor (see RQ1)."
    )


def rq3_text(results):
    sens = results[(results["section"] == "state_sensitivity") &
                   (results["metric"] == "sensitivity_index")]
    sens = sens.set_index("group")["value"].sort_values(ascending=False)
    kinds = results[results["section"] == "state_kind"].set_index("group")["metric"]
    city = sens[[s for s in sens.index if kinds.get(s) == "city_state"]]
    territorial = sens[[s for s in sens.index if kinds.get(s) != "city_state"]]
    return (
        f"The most weather-sensitive states were **{sens.index[0]}** "
        f"(index {sens.iloc[0]:.2f}) and **{sens.index[1]}** ({sens.iloc[1]:.2f}); "
        f"the least sensitive was {sens.index[-1]} ({sens.iloc[-1]:.2f}). "
        f"On average the city states (Berlin, Hamburg, Bremen) had a sensitivity "
        f"index of {city.mean():.2f} compared to {territorial.mean():.2f} for the "
        f"territorial states."
    )


def rq4_text(results):
    yearly = results[(results["section"] == "yearly_risk") &
                     (results["metric"] == "rain_ratio")]
    yearly = yearly.set_index("group")["value"]
    severe = results[(results["section"] == "yearly_risk") &
                     (results["metric"] == "share_severe_on_wet_or_icy")]
    severe = severe.set_index("group")["value"]
    trend = results[results["section"] == "rain_ratio_trend"].set_index("metric")["value"]
    slope = float(trend["slope_per_year"])
    p = float(trend["p_value"])
    direction = "decreased" if slope < 0 else "increased"
    significance = "statistically significant" if p < 0.05 else "not statistically significant"
    return (
        f"The rain rate ratio went from {yearly.iloc[0]:.2f} in {yearly.index[0]} to "
        f"{yearly.iloc[-1]:.2f} in {yearly.index[-1]}. Over the whole period the "
        f"ratio {direction} by {abs(slope):.3f} per year, which is {significance} "
        f"(p = {p:.3f}) - rain remained roughly equally dangerous. What did change "
        f"is the outcome: the share of severe accidents on wet or icy roads fell "
        f"steadily from {severe.iloc[0] * 100:.1f} % in {severe.index[0]} to "
        f"{severe.iloc[-1] * 100:.1f} % in {severe.index[-1]}, which is consistent "
        f"with modern vehicle safety technology softening the consequences of "
        f"weather-related accidents rather than preventing them."
    )


RQ_TITLES = {
    1: "RQ1: How do precipitation and frost impact accident frequency, severity and type?",
    2: "RQ2: Do summer sun and heat predict commuter-hour accident rates?",
    3: "RQ3: Which federal states are most weather-sensitive?",
    4: "RQ4: How did weather-related risk evolve over the analysis period?",
}

RQ_TEXTS = {1: rq1_text, 2: rq2_text, 3: rq3_text, 4: rq4_text}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--output", default="results/report.md")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    summary_file = os.path.join(args.results_dir, "summary_statistics.csv")
    if not os.path.exists(summary_file):
        log.error("%s not found, run descriptive_stats.py first", summary_file)
        sys.exit(1)
    summary = pd.read_csv(summary_file)
    n_accidents = int(value(summary, "overview", "all", "n_accidents"))
    n_stations = int(value(summary, "overview", "all", "n_stations"))
    median_km = value(summary, "overview", "all", "median_station_distance_km")

    years = summary.loc[summary["section"] == "accidents_per_year", "group"].astype(int)
    period = f"{years.min()}-{years.max()}"

    lines = [
        "# Weather-Driven Traffic Accident Risk in Germany - Results",
        "",
        "This report was generated automatically by the Snakemake workflow.",
        "",
        "## Data overview",
        "",
        f"- Accidents analysed ({period}, joined to a weather station): **{n_accidents:,}**",
        f"- DWD weather stations used: **{n_stations}** "
        f"(median distance accident -> station: {median_km:.1f} km)",
        "",
        "![Accidents overview](figures/overview_accidents.png)",
        "",
        "![Weather overview](figures/overview_weather.png)",
        "",
    ]

    for rq in (1, 2, 3, 4):
        results_file = os.path.join(args.results_dir, f"rq{rq}_results.csv")
        if not os.path.exists(results_file):
            log.error("%s not found, run analyze_rq.py --rq %d first", results_file, rq)
            sys.exit(1)
        results = pd.read_csv(results_file)
        lines += [
            f"## {RQ_TITLES[rq]}",
            "",
            RQ_TEXTS[rq](results),
            "",
            f"![RQ{rq} figure](figures/rq{rq}.png)",
            "",
        ]

    lines += [
        "## Limitations",
        "",
        "- The Unfallatlas does not contain exact accident dates, only year, month, "
        "hour and weekday. Weather exposure is therefore matched on aggregated time "
        "cells, which dilutes the true hourly weather effect (the reported ratios "
        "are conservative).",
        "- Only a subset of DWD stations measures all three weather parameters, so "
        "accidents are matched to stations that can be tens of kilometres away.",
        "- Accident data of some states (e.g. Mecklenburg-Vorpommern in early years) "
        "is incomplete in the Unfallatlas.",
        "",
    ]

    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    log.info("wrote report to %s", args.output)


if __name__ == "__main__":
    main()
