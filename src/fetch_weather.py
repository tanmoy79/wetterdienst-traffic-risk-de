"""Fetch hourly DWD weather observations via the wetterdienst library.

This script replaces the upstream project's two-step
``download_weather.py`` + ``prepare_weather.py`` flow (parsing HTML index
pages, downloading per-station ZIPs, unpacking and reshaping DWD product
files) with a single CLI tool built on top of
`wetterdienst <https://github.com/earthobservations/wetterdienst>`_.

It produces exactly the same two artifacts the rest of the pipeline
(``join_data``, ``build_features``, ``analyze_rq``, ``plot_results``,
``make_report``) expects, so no downstream code needs to change:

  ``--stations-out``  CSV with columns
                      ``station_id, name, state, lat, lon, has_solar``
  ``--weather-out``   CSV with columns
                      ``station_id, timestamp, temp_c, precip_mm,
                      solar_j_cm2`` -- timestamps in Europe/Berlin local
                      time, reindexed to a gap-free hourly series.

DWD native units are kept (``ts_convert_units=False``) because the
downstream thresholds in ``config/config.yaml`` are expressed in mm/h,
deg C and J/cm^2.

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


log = logging.getLogger("fetch_weather")

# (resolution, dataset, parameter, downstream column name)
PARAMETERS = [
    ("hourly", "temperature_air", "temperature_air_mean_2m", "temp_c"),
    ("hourly", "precipitation", "precipitation_height", "precip_mm"),
    ("hourly", "solar", "radiation_global", "solar_j_cm2"),
]

OUT_COLUMNS = ["station_id", "timestamp", "temp_c", "precip_mm", "solar_j_cm2"]


def _settings():
    """Build the wetterdienst Settings used everywhere in this module."""
    # imported lazily so unit tests can patch the module before import
    from wetterdienst import Settings

    return Settings(
        ts_shape="long",
        ts_humanize=True,
        ts_convert_units=False,
    )


def _make_request(parameters, start_year, end_year):
    """Construct a DwdObservationRequest for the given parameter triples."""
    from wetterdienst.provider.dwd.observation import DwdObservationRequest

    return DwdObservationRequest(
        parameters=parameters,
        start_date=datetime(start_year, 1, 1),
        end_date=datetime(end_year, 12, 31, 23, 59),
        settings=_settings(),
    )


def _to_pandas(df):
    """Convert a wetterdienst (polars) DataFrame to pandas if needed."""
    return df.to_pandas() if hasattr(df, "to_pandas") else df


def stations_for(resolution, dataset, parameter, start_year, end_year):
    """Return a pandas DataFrame of stations that carry one DWD parameter.

    Only stations whose measurement period fully covers the analysis window
    are returned (``start_date <= period start`` and ``end_date >= period
    end``).
    """
    request = _make_request([(resolution, dataset, parameter)], start_year, end_year)
    df = _to_pandas(request.all().df)
    if df.empty:
        return df

    period_start = pd.Timestamp(f"{start_year}-01-01", tz="UTC")
    period_end = pd.Timestamp(f"{end_year}-12-31", tz="UTC")
    df = df.copy()
    df["start_date"] = pd.to_datetime(df["start_date"], utc=True)
    df["end_date"] = pd.to_datetime(df["end_date"], utc=True)
    covering = df[(df["start_date"] <= period_start) & (df["end_date"] >= period_end)]
    log.info("%s/%s/%s: %d of %d stations cover %d-%d",
             resolution, dataset, parameter, len(covering), len(df),
             start_year, end_year)
    return covering


def select_stations(temp_df, precip_df, solar_df, per_state):
    """Pick at most ``per_state`` stations per federal state.

    Temperature and precipitation are required (these networks are dense).
    Solar radiation is measured at only a few dozen stations, so it is
    optional -- but stations that also carry solar are preferred so as
    many of them as possible end up in the selection.
    """
    temp_ids = set(temp_df["station_id"].astype(str))
    precip_ids = set(precip_df["station_id"].astype(str))
    solar_ids = set(solar_df["station_id"].astype(str)) if not solar_df.empty else set()

    required = temp_ids & precip_ids
    columns = ["station_id", "name", "state", "lat", "lon", "has_solar"]
    if not required:
        return pd.DataFrame(columns=columns)

    meta = temp_df.copy()
    meta["station_id"] = meta["station_id"].astype(str)
    meta = meta[meta["station_id"].isin(required)].copy()
    meta["has_solar"] = meta["station_id"].isin(solar_ids)
    meta = meta.sort_values(["has_solar", "station_id"], ascending=[False, True])
    picked = meta.groupby("state").head(per_state).sort_values("station_id")

    out = picked.rename(columns={"latitude": "lat", "longitude": "lon"})
    out = out[columns].reset_index(drop=True)
    # the rest of the pipeline reads station_id as int; DWD ids are numeric
    out["station_id"] = out["station_id"].astype(int)
    return out


def fetch_values(station_ids, start_year, end_year):
    """Fetch all three parameters for the selected stations (long format)."""
    request = _make_request([(r, ds, p) for r, ds, p, _ in PARAMETERS],
                            start_year, end_year)
    filtered = request.filter_by_station_id(
        station_id=[str(sid) for sid in station_ids]
    )
    return _to_pandas(filtered.values.all().df)


def pivot_to_wide(values_long):
    """Pivot wetterdienst's long-format values into one row per (station, hour)."""
    name_map = {p: out for _, _, p, out in PARAMETERS}
    df = values_long[values_long["parameter"].isin(name_map)].copy()
    df["column"] = df["parameter"].map(name_map)
    df["station_id"] = df["station_id"].astype(int)

    wide = df.pivot_table(
        index=["station_id", "date"],
        columns="column",
        values="value",
        aggfunc="first",
    ).reset_index()
    wide.columns.name = None
    for col in ("temp_c", "precip_mm", "solar_j_cm2"):
        if col not in wide.columns:
            wide[col] = float("nan")
    return wide


def to_local_complete_series(values_wide, start_year, end_year):
    """Convert UTC timestamps to Europe/Berlin and reindex to a gap-free series."""
    if values_wide.empty:
        return pd.DataFrame(columns=OUT_COLUMNS)

    full_index = pd.date_range(
        start=f"{start_year}-01-01 00:00",
        end=f"{end_year}-12-31 23:00",
        freq="h",
        tz="Europe/Berlin",
    )

    frames = []
    for station_id, group in values_wide.groupby("station_id"):
        ts = pd.to_datetime(group["date"], utc=True).dt.tz_convert("Europe/Berlin")
        local = group.drop(columns=["station_id", "date"]).assign(timestamp=ts)
        local = local.set_index("timestamp").sort_index()
        local = local[~local.index.duplicated(keep="first")]
        local = local.reindex(full_index)
        local["station_id"] = station_id
        frames.append(local.reset_index(names="timestamp"))

    weather = pd.concat(frames, ignore_index=True)
    return weather[OUT_COLUMNS]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start-year", type=int, default=2020)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--stations-per-state", type=int, default=2,
                        help="maximum number of stations per federal state")
    parser.add_argument("--stations-out", default="data/raw_weather/stations.csv")
    parser.add_argument("--weather-out", default="data/climate/weather_hourly.csv")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    temp_df = stations_for(*PARAMETERS[0][:3], args.start_year, args.end_year)
    precip_df = stations_for(*PARAMETERS[1][:3], args.start_year, args.end_year)
    solar_df = stations_for(*PARAMETERS[2][:3], args.start_year, args.end_year)

    if temp_df.empty or precip_df.empty:
        log.error("wetterdienst returned no covering stations; "
                  "check the period and your internet connection")
        sys.exit(1)

    selected = select_stations(temp_df, precip_df, solar_df, args.stations_per_state)
    if selected.empty:
        log.error("no stations cover the requested period %d-%d",
                  args.start_year, args.end_year)
        sys.exit(1)
    log.info("selected %d stations in %d states (%d with solar)",
             len(selected), selected["state"].nunique(),
             int(selected["has_solar"].sum()))

    os.makedirs(os.path.dirname(args.stations_out) or ".", exist_ok=True)
    selected.to_csv(args.stations_out, index=False)
    log.info("wrote station list to %s", args.stations_out)

    values_long = fetch_values(selected["station_id"].tolist(),
                               args.start_year, args.end_year)
    wide = pivot_to_wide(values_long)
    weather = to_local_complete_series(wide, args.start_year, args.end_year)

    os.makedirs(os.path.dirname(args.weather_out) or ".", exist_ok=True)
    weather.to_csv(args.weather_out, index=False)
    log.info("wrote %d hourly rows for %d stations to %s",
             len(weather), weather["station_id"].nunique(), args.weather_out)


if __name__ == "__main__":
    main()
