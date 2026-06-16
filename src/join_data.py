"""Assign every accident to its nearest DWD weather station.

Builds a KD-tree over the station coordinates and finds the nearest station
for each accident. Accidents that are too far away from any selected station
(--max-distance-km) are dropped, because the weather measured there would not
be representative for the accident location.

Usage:
    python src/join_data.py --accidents data/processed/accidents_clean.csv \
        --stations data/raw_weather/stations.csv \
        --output data/joined/accidents_stations.csv
"""

import argparse
import logging
import math
import os
import sys

import pandas as pd
from scipy.spatial import cKDTree

log = logging.getLogger("join_data")

KM_PER_DEGREE_LAT = 110.6  # rough conversion, good enough for Germany


def to_xy_km(lon, lat, reference_lat):
    """Project lon/lat degrees to a simple x/y plane in kilometres."""
    km_per_degree_lon = 111.3 * math.cos(math.radians(reference_lat))
    return lon * km_per_degree_lon, lat * KM_PER_DEGREE_LAT


def nearest_station(accidents, stations):
    """Return the nearest station id and its distance (km) for each accident."""
    reference_lat = stations["lat"].mean()
    station_x, station_y = to_xy_km(stations["lon"], stations["lat"], reference_lat)
    tree = cKDTree(list(zip(station_x, station_y)))

    accident_x, accident_y = to_xy_km(accidents["lon"], accidents["lat"], reference_lat)
    distances, indices = tree.query(list(zip(accident_x, accident_y)))
    return stations["station_id"].to_numpy()[indices], distances


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--accidents", default="data/processed/accidents_clean.csv")
    parser.add_argument("--stations", default="data/raw_weather/stations.csv")
    parser.add_argument("--max-distance-km", type=float, default=100.0,
                        help="drop accidents farther than this from any station")
    parser.add_argument("--output", default="data/joined/accidents_stations.csv")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    for path in (args.accidents, args.stations):
        if not os.path.exists(path):
            log.error("input file %s not found", path)
            sys.exit(1)

    accidents = pd.read_csv(args.accidents)
    stations = pd.read_csv(args.stations)
    if stations.empty:
        log.error("station list %s is empty", args.stations)
        sys.exit(1)

    station_ids, distances = nearest_station(accidents, stations)
    accidents["station_id"] = station_ids
    accidents["station_distance_km"] = distances.round(1)

    n_before = len(accidents)
    accidents = accidents[accidents["station_distance_km"] <= args.max_distance_km]
    log.info("dropped %d of %d accidents farther than %.0f km from a station",
             n_before - len(accidents), n_before, args.max_distance_km)
    log.info("median distance to assigned station: %.1f km",
             accidents["station_distance_km"].median())

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    accidents.to_csv(args.output, index=False)
    log.info("wrote %d accidents with station ids to %s", len(accidents), args.output)


if __name__ == "__main__":
    main()
