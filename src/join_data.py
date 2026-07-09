"""Assign every accident to its nearest DWD weather station.

For each accident we measure the distance to every weather station and keep the
closest one. Accidents farther than --max-distance-km from any station are
dropped, because weather measured far away would not represent the accident
location.

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

import numpy as np
import pandas as pd

log = logging.getLogger("join_data")

KM_PER_DEGREE_LAT = 110.6  # one degree of latitude is about 110.6 km


def to_xy_km(lon, lat, reference_lat):
    """Turn longitude/latitude degrees into simple x/y kilometres."""
    km_per_degree_lon = 111.3 * math.cos(math.radians(reference_lat))
    return lon * km_per_degree_lon, lat * KM_PER_DEGREE_LAT


def nearest_station(accidents, stations):
    """For each accident, find the closest station id and its distance in km."""
    reference_lat = stations["lat"].mean()
    station_x, station_y = to_xy_km(stations["lon"], stations["lat"], reference_lat)
    accident_x, accident_y = to_xy_km(accidents["lon"], accidents["lat"], reference_lat)

    # work with plain numpy arrays so the maths is fast
    station_x = station_x.to_numpy()
    station_y = station_y.to_numpy()
    station_ids = stations["station_id"].to_numpy()
    accident_x = accident_x.to_numpy()
    accident_y = accident_y.to_numpy()

    best_distance = None
    best_id = None
    for i in range(len(station_ids)):
        distance = np.sqrt((accident_x - station_x[i]) ** 2 +
                           (accident_y - station_y[i]) ** 2)
        if best_distance is None:              # first station, nothing to compare yet
            best_distance = distance
            best_id = np.full(len(accident_x), station_ids[i])
        else:
            closer = distance < best_distance  # accidents nearer THIS station
            best_distance = np.where(closer, distance, best_distance)
            best_id = np.where(closer, station_ids[i], best_id)
    return best_id, best_distance


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

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    accidents.to_csv(args.output, index=False)
    log.info("wrote %d accidents with station ids to %s", len(accidents), args.output)


if __name__ == "__main__":
    main()
