"""Fetch hourly DWD weather data with the wetterdienst library.

Picks a few DWD stations per federal state that measure air temperature,
precipitation and solar radiation for the whole analysis period, downloads
their hourly values, converts the times to local time (Europe/Berlin) and
saves a gap-free hourly table.

Outputs (used by the rest of the workflow):
  --stations-out  station_id, name, state, lat, lon, has_solar
  --weather-out   station_id, timestamp, temp_c, precip_mm, solar_j_cm2

Usage:
    python src/fetch_weather.py --start-year 2020 --end-year 2024 \\
        --stations-per-state 2 \\
        --stations-out data/raw_weather/stations.csv \\
        --weather-out data/climate/weather_hourly.csv
"""

import argparse
import logging
import os
import sys
from datetime import datetime

import pandas as pd
from wetterdienst import Settings
from wetterdienst.provider.dwd.observation import DwdObservationRequest

log = logging.getLogger("fetch_weather")

# Each row: (resolution, dataset, DWD parameter name, our column name)
PARAMETERS = [
    ("hourly", "temperature_air", "temperature_air_mean_2m", "temp_c"),
    ("hourly", "precipitation", "precipitation_height", "precip_mm"),
    ("hourly", "solar", "radiation_global", "solar_j_cm2"),
]
OUT_COLUMNS = ["station_id", "timestamp", "temp_c", "precip_mm", "solar_j_cm2"]

# long table shape, human-readable names, keep DWD's own units
SETTINGS = Settings(ts_shape="long", ts_humanize=True, ts_convert_units=False)


def make_request(parameters, start_year, end_year):
    """Build a wetterdienst request for the given parameters and years."""
    return DwdObservationRequest(
        parameters=parameters,
        start_date=datetime(start_year, 1, 1),
        end_date=datetime(end_year, 12, 31, 23, 59),
        settings=SETTINGS,
    )


def get_stations(resolution, dataset, parameter, start_year, end_year):
    """Return the stations that measure one parameter for the whole period."""
    request = make_request([(resolution, dataset, parameter)], start_year, end_year)
    stations = request.all().df.to_pandas()
    if stations.empty:
        return stations

    # keep only stations whose record covers the whole analysis period
    start = pd.Timestamp(f"{start_year}-01-01", tz="UTC")
    end = pd.Timestamp(f"{end_year}-12-31", tz="UTC")
    stations["start_date"] = pd.to_datetime(stations["start_date"], utc=True)
    stations["end_date"] = pd.to_datetime(stations["end_date"], utc=True)
    covering = stations[(stations["start_date"] <= start)
                        & (stations["end_date"] >= end)]
    log.info("%s: %d of %d stations cover %d-%d",
             parameter, len(covering), len(stations), start_year, end_year)
    return covering


def select_stations(temp_df, precip_df, solar_df, per_state):
    """Pick up to `per_state` stations per federal state.

    Temperature and precipitation are required; solar is optional but
    preferred, because only a few dozen stations measure it.
    """
    temp_ids = set(temp_df["station_id"].astype(str))
    precip_ids = set(precip_df["station_id"].astype(str))
    solar_ids = set(solar_df["station_id"].astype(str)) if not solar_df.empty else set()

    columns = ["station_id", "name", "state", "lat", "lon", "has_solar"]
    required = temp_ids & precip_ids
    if not required:
        return pd.DataFrame(columns=columns)

    stations = temp_df.copy()
    stations["station_id"] = stations["station_id"].astype(str)
    stations = stations[stations["station_id"].isin(required)]
    stations["has_solar"] = stations["station_id"].isin(solar_ids)
    stations = stations.rename(columns={"latitude": "lat", "longitude": "lon"})

    # prefer stations that also have solar, then take the first few per state
    stations = stations.sort_values(["has_solar", "station_id"],
                                    ascending=[False, True])
    chosen = stations.groupby("state").head(per_state).sort_values("station_id")

    chosen = chosen[columns].reset_index(drop=True)
    chosen["station_id"] = chosen["station_id"].astype(int)
    return chosen


def fetch_values(station_ids, start_year, end_year):
    """Download the hourly values for the chosen stations (long table)."""
    all_params = [(res, dataset, param) for res, dataset, param, _ in PARAMETERS]
    request = make_request(all_params, start_year, end_year)
    chosen = request.filter_by_station_id([str(sid) for sid in station_ids])
    return chosen.values.all().df.to_pandas()


def pivot_to_wide(values):
    """Turn the long value table into one row per station and hour."""
    rename = {param: column for _, _, param, column in PARAMETERS}
    values = values[values["parameter"].isin(rename)].copy()
    values["column"] = values["parameter"].map(rename)
    values["station_id"] = values["station_id"].astype(int)

    wide = values.pivot_table(index=["station_id", "date"], columns="column",
                              values="value", aggfunc="first").reset_index()
    wide.columns.name = None
    for column in ("temp_c", "precip_mm", "solar_j_cm2"):
        if column not in wide.columns:
            wide[column] = float("nan")
    return wide


def to_local_complete_series(wide, start_year, end_year):
    """Convert UTC to local time and fill in any missing hours."""
    if wide.empty:
        return pd.DataFrame(columns=OUT_COLUMNS)

    full_hours = pd.date_range(f"{start_year}-01-01 00:00",
                               f"{end_year}-12-31 23:00",
                               freq="h", tz="Europe/Berlin")
    frames = []
    for station_id, group in wide.groupby("station_id"):
        local_time = pd.to_datetime(group["date"], utc=True).dt.tz_convert("Europe/Berlin")
        series = group.drop(columns=["station_id", "date"]).assign(timestamp=local_time)
        series = series.set_index("timestamp").sort_index()
        series = series[~series.index.duplicated(keep="first")]
        series = series.reindex(full_hours)
        series["station_id"] = station_id
        frames.append(series.reset_index(names="timestamp"))

    weather = pd.concat(frames, ignore_index=True)
    return weather[OUT_COLUMNS]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start-year", type=int, default=2020)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--stations-per-state", type=int, default=2,
                        help="how many stations to use per federal state")
    parser.add_argument("--stations-out", default="data/raw_weather/stations.csv")
    parser.add_argument("--weather-out", default="data/climate/weather_hourly.csv")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # 1. find the stations for each parameter
    temp_df = get_stations(*PARAMETERS[0][:3], args.start_year, args.end_year)
    precip_df = get_stations(*PARAMETERS[1][:3], args.start_year, args.end_year)
    solar_df = get_stations(*PARAMETERS[2][:3], args.start_year, args.end_year)
    if temp_df.empty or precip_df.empty:
        log.error("no stations found - check your internet connection")
        sys.exit(1)

    # 2. choose the stations and save the list
    stations = select_stations(temp_df, precip_df, solar_df, args.stations_per_state)
    if stations.empty:
        log.error("no station covers the whole period %d-%d",
                  args.start_year, args.end_year)
        sys.exit(1)
    log.info("selected %d stations in %d states",
             len(stations), stations["state"].nunique())
    os.makedirs(os.path.dirname(args.stations_out), exist_ok=True)
    stations.to_csv(args.stations_out, index=False)

    # 3. download the values and reshape them
    values = fetch_values(stations["station_id"].tolist(),
                          args.start_year, args.end_year)
    wide = pivot_to_wide(values)
    weather = to_local_complete_series(wide, args.start_year, args.end_year)

    # 4. save the hourly weather table
    os.makedirs(os.path.dirname(args.weather_out), exist_ok=True)
    weather.to_csv(args.weather_out, index=False)
    log.info("wrote %d hourly rows for %d stations to %s",
             len(weather), weather["station_id"].nunique(), args.weather_out)


if __name__ == "__main__":
    main()
