"""Build the final analytical table that combines weather and accidents.

The Unfallatlas does not contain the exact accident date (only year, month,
hour and weekday), so accidents and weather hours cannot be matched one to
one. Instead both datasets are aggregated into "time cells":

    (station, year, month, weekend/weekday, hour of day)

For every cell the script counts the weather hours by condition (rain
intensity, frost, heat, strong sun) and the accidents by severity and type.
Accident rates under different weather conditions can then be compared via
the share of e.g. rainy hours per cell. Thresholds are configurable.

Usage:
    python src/build_features.py --weather data/climate/weather_hourly.csv \
        --accidents data/joined/accidents_stations.csv \
        --stations data/raw_weather/stations.csv \
        --output data/processed/analysis_table.csv
"""

import argparse
import logging
import os
import sys

import pandas as pd

log = logging.getLogger("build_features")

CELL_KEY = ["station_id", "year", "month", "is_weekend", "hour"]


def classify_weather_hours(weather, args):
    """Add boolean condition columns to the hourly weather table."""
    weather = weather.dropna(subset=["temp_c", "precip_mm"]).copy()

    weather["is_rain"] = weather["precip_mm"] >= args.rain_threshold
    weather["is_light_rain"] = (weather["precip_mm"] >= args.rain_threshold) & \
                               (weather["precip_mm"] < args.heavy_rain_threshold)
    weather["is_heavy_rain"] = weather["precip_mm"] >= args.heavy_rain_threshold
    weather["is_frost"] = weather["temp_c"] < args.frost_threshold
    weather["is_hot"] = weather["temp_c"] >= args.heat_threshold
    # solar is NaN for stations without a radiation sensor (comparison gives False);
    # the analysis of RQ2 only uses cells where mean_solar is available
    weather["is_strong_sun"] = weather["solar_j_cm2"] >= args.strong_sun_threshold
    return weather


def aggregate_weather(weather):
    """Aggregate the classified hours into time cells."""
    # the stored local timestamps mix +01:00 and +02:00 offsets (CET/CEST),
    # so parse them as UTC first and convert back to local time
    timestamp = pd.to_datetime(weather["timestamp"], utc=True)
    timestamp = timestamp.dt.tz_convert("Europe/Berlin")
    weather["year"] = timestamp.dt.year
    weather["month"] = timestamp.dt.month
    weather["hour"] = timestamp.dt.hour
    weather["is_weekend"] = timestamp.dt.dayofweek >= 5

    cells = weather.groupby(CELL_KEY).agg(
        n_hours=("temp_c", "size"),
        hours_rain=("is_rain", "sum"),
        hours_light_rain=("is_light_rain", "sum"),
        hours_heavy_rain=("is_heavy_rain", "sum"),
        hours_frost=("is_frost", "sum"),
        hours_hot=("is_hot", "sum"),
        hours_strong_sun=("is_strong_sun", "sum"),
        mean_temp=("temp_c", "mean"),
        mean_precip=("precip_mm", "mean"),
        mean_solar=("solar_j_cm2", "mean"),
    ).reset_index()
    return cells


def aggregate_accidents(accidents):
    """Count accidents by severity, type and road condition per time cell."""
    # Unfallatlas weekday coding: 1 = Sunday, ..., 7 = Saturday
    accidents["is_weekend"] = accidents["weekday"].isin([1, 7])

    counts = accidents.groupby(CELL_KEY).agg(
        n_accidents=("severity", "size"),
        n_fatal=("severity", lambda s: (s == 1).sum()),
        n_serious=("severity", lambda s: (s == 2).sum()),
        n_loss_control=("accident_type", lambda s: (s == 1).sum()),
        n_wet_road=("road_condition", lambda s: (s == 1).sum()),
        n_icy_road=("road_condition", lambda s: (s == 2).sum()),
    ).reset_index()
    return counts


def add_features(cells):
    """Add share and helper columns used by the analysis scripts."""
    cells["rain_share"] = cells["hours_rain"] / cells["n_hours"]
    cells["heavy_rain_share"] = cells["hours_heavy_rain"] / cells["n_hours"]
    cells["frost_share"] = cells["hours_frost"] / cells["n_hours"]
    cells["hot_share"] = cells["hours_hot"] / cells["n_hours"]
    cells["strong_sun_share"] = cells["hours_strong_sun"] / cells["n_hours"]
    cells["is_commuter_hour"] = (~cells["is_weekend"]) & \
        cells["hour"].isin([7, 8, 9, 16, 17, 18])
    return cells


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--weather", default="data/climate/weather_hourly.csv")
    parser.add_argument("--accidents", default="data/joined/accidents_stations.csv")
    parser.add_argument("--stations", default="data/raw_weather/stations.csv")
    parser.add_argument("--output", default="data/processed/analysis_table.csv")
    parser.add_argument("--rain-threshold", type=float, default=0.1,
                        help="precipitation (mm/h) from which an hour counts as rainy")
    parser.add_argument("--heavy-rain-threshold", type=float, default=4.0,
                        help="precipitation (mm/h) from which rain counts as heavy")
    parser.add_argument("--frost-threshold", type=float, default=0.0,
                        help="temperature (deg C) below which an hour counts as frost")
    parser.add_argument("--heat-threshold", type=float, default=30.0,
                        help="temperature (deg C) from which an hour counts as hot")
    parser.add_argument("--strong-sun-threshold", type=float, default=200.0,
                        help="global radiation (J/cm2) from which sun counts as strong")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    for path in (args.weather, args.accidents, args.stations):
        if not os.path.exists(path):
            log.error("input file %s not found", path)
            sys.exit(1)

    weather = pd.read_csv(args.weather)
    accidents = pd.read_csv(args.accidents)
    stations = pd.read_csv(args.stations)

    weather = classify_weather_hours(weather, args)
    log.info("classified %d weather hours (%.1f%% rainy, %.1f%% frost)",
             len(weather), weather["is_rain"].mean() * 100,
             weather["is_frost"].mean() * 100)

    cells = aggregate_weather(weather)
    counts = aggregate_accidents(accidents)
    table = cells.merge(counts, on=CELL_KEY, how="left")
    count_columns = [c for c in counts.columns if c.startswith("n_")]
    table[count_columns] = table[count_columns].fillna(0).astype(int)

    # attach the federal state of the station (used for the per-state analysis)
    table = table.merge(stations[["station_id", "state"]], on="station_id", how="left")
    table = add_features(table)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    table.to_csv(args.output, index=False)
    log.info("wrote analysis table with %d time cells and %d accidents to %s",
             len(table), table["n_accidents"].sum(), args.output)


if __name__ == "__main__":
    main()
