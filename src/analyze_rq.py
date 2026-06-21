"""Analyse one research question and write a tidy result table.

The script reads the cell-level analysis table (weather exposure + accident
counts) and the accident table, runs the statistics for the selected research
question and writes a long-format CSV with the columns
section, group, metric, value.

Because rainy or frosty hours are not spread evenly over the day and the year
(e.g. frost happens at night and in winter when there is little traffic), a
naive comparison of rainy vs. dry cells would mostly measure traffic volume.
The rate ratios are therefore standardized: observed accidents in the exposed
cells are divided by the accidents expected from the rates of unexposed cells
in the same stratum (station, month, weekend/weekday, hour of day).

Research questions:
    1 - precipitation/frost vs. accident frequency, severity and type
    2 - summer sun and heat vs. commuter-hour accident rates
    3 - weather sensitivity of the federal states
    4 - evolution of weather-related risk over the analysis period

Usage:
    python src/analyze_rq.py --rq 1 --table data/processed/analysis_table.csv \
        --accidents data/joined/accidents_stations.csv --output results/rq1_results.csv
"""

import argparse
import logging
import os
import sys

import pandas as pd
from scipy import stats

log = logging.getLogger("analyze_rq")

WINTER_MONTHS = [11, 12, 1, 2, 3]
SUMMER_MONTHS = [6, 7, 8]
CITY_STATES = ["Berlin", "Hamburg", "Bremen"]

ROAD_CONDITION_LABELS = {0: "dry", 1: "wet", 2: "icy"}

# strata used for the standardized rate ratios
STRATA = ["station_id", "month", "is_weekend", "hour"]


def rate_per_1000h(cells):
    """Accidents per 1000 station-hours over a set of cells."""
    hours = cells["n_hours"].sum()
    if hours == 0:
        return float("nan")
    return cells["n_accidents"].sum() / hours * 1000


def standardized_ratio(exposed_cells, baseline_cells):
    """Observed/expected accident ratio of exposed vs. baseline cells.

    The expected count comes from the baseline accident rate of the same
    stratum (station, month, weekend, hour), so differences in traffic
    volume between e.g. night and rush hours cancel out. Note that this
    cell-level comparison dilutes the true hourly effect, because even a
    "rainy" cell contains many dry hours.
    """
    baseline = baseline_cells.groupby(STRATA).agg(
        acc=("n_accidents", "sum"), hours=("n_hours", "sum"))
    baseline["rate"] = baseline["acc"] / baseline["hours"]

    exposed = exposed_cells.groupby(STRATA).agg(
        acc=("n_accidents", "sum"), hours=("n_hours", "sum"))
    joined = exposed.join(baseline["rate"], how="inner").dropna()

    expected = (joined["hours"] * joined["rate"]).sum()
    if expected == 0:
        return float("nan")
    return joined["acc"].sum() / expected


def add_exposure_columns(cells):
    """Add the columns needed for the road-condition based rate ratios."""
    cells = cells.copy()
    cells["n_dry_road"] = (cells["n_accidents"] - cells["n_wet_road"]
                           - cells["n_icy_road"])
    cells["hours_no_rain"] = cells["n_hours"] - cells["hours_rain"]
    cells["hours_no_frost"] = cells["n_hours"] - cells["hours_frost"]
    return cells


def condition_ratio(cells, obs_acc, obs_hours, base_acc, base_hours):
    """Accidents on a road condition per matching weather hour, relative to
    dry-road accidents per dry hour (standardized per stratum).

    This works around the missing accident dates: the accident record
    itself says whether the road was wet or icy, and the weather panel
    provides the number of rainy/frost hours as exposure.
    """
    grouped = cells.groupby(STRATA)[[obs_acc, obs_hours, base_acc, base_hours]].sum()
    grouped = grouped[(grouped[obs_hours] > 0) & (grouped[base_hours] > 0)]
    expected = (grouped[obs_hours] * grouped[base_acc] / grouped[base_hours]).sum()
    if expected == 0:
        return float("nan")
    return grouped[obs_acc].sum() / expected


def weather_ratios(cells):
    """Rain (wet road) and frost (icy road) rate ratios for a cell subset."""
    rain_ratio = condition_ratio(cells, "n_wet_road", "hours_rain",
                                 "n_dry_road", "hours_no_rain")
    winter = cells[cells["month"].isin(WINTER_MONTHS)]
    frost_ratio = condition_ratio(winter, "n_icy_road", "hours_frost",
                                  "n_dry_road", "hours_no_frost")
    return rain_ratio, frost_ratio


def rates_by_share(cells, share_column, section):
    """Raw accident rates for cells binned by the share of e.g. rainy hours.

    These rates are purely descriptive (not standardized), the standardized
    ratios are reported separately.
    """
    bins = {
        "none": cells[share_column] == 0,
        "low": (cells[share_column] > 0) & (cells[share_column] <= 0.15),
        "medium": (cells[share_column] > 0.15) & (cells[share_column] <= 0.35),
        "high": cells[share_column] > 0.35,
    }
    rows = []
    for label, mask in bins.items():
        subset = cells[mask]
        rows.append((section, label, "rate_per_1000h", rate_per_1000h(subset)))
        rows.append((section, label, "n_hours", subset["n_hours"].sum()))
        rows.append((section, label, "n_accidents", subset["n_accidents"].sum()))
    return rows


def analyze_rq1(cells, accidents):
    """Precipitation and frost vs. accident frequency, severity and type."""
    cells = add_exposure_columns(cells)
    dry = cells[cells["rain_share"] == 0]
    winter = cells[cells["month"].isin(WINTER_MONTHS)]

    # headline numbers: road-condition accidents per matching weather hour
    rain_ratio, frost_ratio = weather_ratios(cells)
    rows = [("condition_ratios", "wet_road", "rate_ratio", rain_ratio),
            ("condition_ratios", "icy_road", "rate_ratio", frost_ratio)]

    # rain intensity comparison (cell level, diluted but comparable)
    ratios = {
        "light_rain": standardized_ratio(
            cells[(cells["rain_share"] > 0.35) & (cells["heavy_rain_share"] == 0)], dry),
        "heavy_rain": standardized_ratio(cells[cells["heavy_rain_share"] > 0], dry),
    }
    rows += [("standardized_ratios", label, "rate_ratio", value)
             for label, value in ratios.items()]

    # descriptive (unstandardized) rates for the figure
    rows += rates_by_share(cells, "rain_share", "rate_by_rain_share")
    rows += rates_by_share(winter, "frost_share", "rate_by_frost_share_winter")

    # severity and accident type by road condition (directly from the accidents)
    table = pd.crosstab(accidents["road_condition"], accidents["severity"])
    chi2 = stats.chi2_contingency(table)
    for condition, label in ROAD_CONDITION_LABELS.items():
        subset = accidents[accidents["road_condition"] == condition]
        severe = (subset["severity"] <= 2).mean()
        loss = (subset["accident_type"] == 1).mean()
        rows.append(("severity_by_road_condition", label, "share_severe", severe))
        rows.append(("severity_by_road_condition", label, "n_accidents", len(subset)))
        rows.append(("type_by_road_condition", label, "share_loss_of_control", loss))
    rows.append(("severity_by_road_condition", "all", "chi2_p_value", chi2.pvalue))

    # urban vs. rural comparison on adverse-weather road surfaces (wet/icy).
    # The published Unfallatlas has no road class, so the spatial dimension of
    # RQ1 is the settlement-structure type joined in classify_region.py.
    rows += region_adverse_weather(accidents)
    return rows


def region_adverse_weather(accidents):
    """Compare urban vs. rural accidents that happened on wet or icy roads."""
    if "region_class" not in accidents.columns:
        return []
    adverse = accidents[accidents["road_condition"] > 0]
    rows = []
    for region in ("urban", "rural"):
        subset = adverse[adverse["region_class"] == region]
        if subset.empty:
            continue
        rows.append(("region_adverse_weather", region, "share_severe",
                     (subset["severity"] <= 2).mean()))
        rows.append(("region_adverse_weather", region, "share_loss_of_control",
                     (subset["accident_type"] == 1).mean()))
        rows.append(("region_adverse_weather", region, "n_accidents", len(subset)))

    known = adverse[adverse["region_class"].isin(["urban", "rural"])]
    table = pd.crosstab(known["region_class"], known["severity"])
    if table.shape[0] == 2 and table.shape[1] >= 2:
        chi2 = stats.chi2_contingency(table)
        rows.append(("region_severity_test", "urban_vs_rural", "chi2_p_value",
                     chi2.pvalue))
    return rows


def analyze_rq2(cells, accidents):
    """Summer sun, heat and rain vs. commuter-hour accident rates."""
    # only stations with a solar radiation sensor can be used here
    commuter = cells[cells["month"].isin(SUMMER_MONTHS) & cells["is_commuter_hour"] &
                     cells["mean_solar"].notna()]

    groups = {
        "strong_sun": commuter["strong_sun_share"] > 0.5,
        "hot": commuter["hot_share"] > 0.2,
        "rainy": commuter["rain_share"] > 0.35,
    }
    neutral = commuter[(commuter["strong_sun_share"] <= 0.5) &
                       (commuter["rain_share"] <= 0.15) &
                       (commuter["hot_share"] <= 0.2)]

    rows = [("commuter_rate_by_condition", "neutral", "rate_per_1000h",
             rate_per_1000h(neutral)),
            ("commuter_rate_by_condition", "neutral", "n_hours",
             neutral["n_hours"].sum())]
    for label, mask in groups.items():
        subset = commuter[mask]
        rows.append(("commuter_rate_by_condition", label, "rate_per_1000h",
                     rate_per_1000h(subset)))
        rows.append(("commuter_rate_by_condition", label, "n_hours",
                     subset["n_hours"].sum()))
        rows.append(("commuter_rate_by_condition", label, "rate_ratio_vs_neutral",
                     standardized_ratio(subset, neutral)))

    # correlation between solar radiation and the accident rate across
    # station-months (commuter hours only)
    monthly = commuter.groupby(["station_id", "year", "month"]).agg(
        n_accidents=("n_accidents", "sum"), n_hours=("n_hours", "sum"),
        mean_solar=("mean_solar", "mean")).reset_index()
    monthly["rate"] = monthly["n_accidents"] / monthly["n_hours"] * 1000
    r, p = stats.pearsonr(monthly["mean_solar"], monthly["rate"])
    rows.append(("solar_rate_correlation", "station_months", "pearson_r", r))
    rows.append(("solar_rate_correlation", "station_months", "p_value", p))
    rows.append(("solar_rate_correlation", "station_months", "n", len(monthly)))
    return rows


def analyze_rq3(cells, accidents):
    """Weather sensitivity index per federal state."""
    cells = add_exposure_columns(cells)
    rows = []
    for state, state_cells in cells.groupby("state"):
        rain_ratio, frost_ratio = weather_ratios(state_cells)
        sensitivity = (rain_ratio + frost_ratio) / 2
        kind = "city_state" if state in CITY_STATES else "territorial_state"
        rows.append(("state_sensitivity", state, "rain_ratio", rain_ratio))
        rows.append(("state_sensitivity", state, "frost_ratio", frost_ratio))
        rows.append(("state_sensitivity", state, "sensitivity_index", sensitivity))
        rows.append(("state_sensitivity", state, "n_accidents",
                     state_cells["n_accidents"].sum()))
        rows.append(("state_kind", state, kind, 1))
    return rows


def analyze_rq4(cells, accidents):
    """Yearly evolution of the weather-related accident risk."""
    cells = add_exposure_columns(cells)
    rows = []
    yearly_ratios = []
    for year, year_cells in cells.groupby("year"):
        # the ratio is computed within each year, so the growing coverage
        # of the Unfallatlas over the years does not distort the trend
        rain_ratio, frost_ratio = weather_ratios(year_cells)
        year_accidents = accidents[accidents["year"] == year]
        bad_road = year_accidents[year_accidents["road_condition"] > 0]
        severe_share_bad = (bad_road["severity"] <= 2).mean()
        rows.append(("yearly_risk", str(year), "rain_ratio", rain_ratio))
        rows.append(("yearly_risk", str(year), "frost_ratio", frost_ratio))
        rows.append(("yearly_risk", str(year), "n_accidents", len(year_accidents)))
        rows.append(("yearly_risk", str(year), "share_severe_on_wet_or_icy",
                     severe_share_bad))
        yearly_ratios.append((year, rain_ratio))

    years = [y for y, _ in yearly_ratios]
    ratios = [r for _, r in yearly_ratios]
    trend = stats.linregress(years, ratios)
    period = f"{years[0]}-{years[-1]}"
    rows.append(("rain_ratio_trend", period, "slope_per_year", trend.slope))
    rows.append(("rain_ratio_trend", period, "p_value", trend.pvalue))
    return rows


ANALYSES = {1: analyze_rq1, 2: analyze_rq2, 3: analyze_rq3, 4: analyze_rq4}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rq", type=int, required=True, choices=ANALYSES,
                        help="research question to analyse")
    parser.add_argument("--table", default="data/processed/analysis_table.csv")
    parser.add_argument("--accidents", default="data/joined/accidents_stations.csv")
    parser.add_argument("--output", default=None,
                        help="output CSV (default: results/rq<N>_results.csv)")
    args = parser.parse_args(argv)
    output = args.output or f"results/rq{args.rq}_results.csv"

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    for path in (args.table, args.accidents):
        if not os.path.exists(path):
            log.error("input file %s not found", path)
            sys.exit(1)

    cells = pd.read_csv(args.table)
    accidents = pd.read_csv(args.accidents)
    log.info("analysing RQ%d on %d cells / %d accidents",
             args.rq, len(cells), len(accidents))

    rows = ANALYSES[args.rq](cells, accidents)
    result = pd.DataFrame(rows, columns=["section", "group", "metric", "value"])

    os.makedirs(os.path.dirname(output), exist_ok=True)
    result.to_csv(output, index=False)
    log.info("wrote %d result rows to %s", len(result), output)


if __name__ == "__main__":
    main()
