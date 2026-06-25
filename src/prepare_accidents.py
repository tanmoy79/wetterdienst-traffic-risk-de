"""Merge and clean the raw Unfallatlas accident files.

The Federal Statistical Office publishes one accident file per year and the
column names changed a few times over the years. This script reads all yearly
files from the raw data directory, harmonises the column names, keeps only the
columns we need for the analysis and writes one clean CSV file.

Usage:
    python src/prepare_accidents.py --raw-dir data/raw_accidents \
        --start-year 2020 --end-year 2024 --output data/processed/accidents_clean.csv
"""

import argparse
import glob
import logging
import os
import sys

import pandas as pd

log = logging.getLogger("prepare_accidents")

# The road condition column was renamed (2020 / 2021+).
ROAD_CONDITION_NAMES = ["IstStrassenzustand", "STRZUSTAND"]

# Mapping from the raw Unfallatlas names to the names used in this project.
RENAME_MAP = {
    "ULAND": "state_id",
    "UJAHR": "year",
    "UMONAT": "month",
    "USTUNDE": "hour",
    "UWOCHENTAG": "weekday",       # 1 = Sunday ... 7 = Saturday
    "UKATEGORIE": "severity",      # 1 = fatal, 2 = serious injury, 3 = light injury
    "UTYP1": "accident_type",      # 1 = loss-of-control ("Fahrunfall"), 2-7 = other
    "XGCSWGS84": "lon",
    "YGCSWGS84": "lat",
}

STATE_NAMES = {
    1: "Schleswig-Holstein", 2: "Hamburg", 3: "Niedersachsen", 4: "Bremen",
    5: "Nordrhein-Westfalen", 6: "Hessen", 7: "Rheinland-Pfalz",
    8: "Baden-Wuerttemberg", 9: "Bayern", 10: "Saarland", 11: "Berlin",
    12: "Brandenburg", 13: "Mecklenburg-Vorpommern", 14: "Sachsen",
    15: "Sachsen-Anhalt", 16: "Thueringen",
}


def find_raw_files(raw_dir):
    """Return all yearly Unfallatlas files in the raw directory, sorted."""
    files = glob.glob(os.path.join(raw_dir, "Unfallorte*"))
    return sorted(files)


def load_raw_file(path):
    """Read one yearly accident file and return it with harmonised columns."""
    df = pd.read_csv(path, sep=";", decimal=",", encoding="utf-8-sig",
                     low_memory=False)

    # find the road condition column for this year
    road_col = None
    for name in ROAD_CONDITION_NAMES:
        if name in df.columns:
            road_col = name
            break
    if road_col is None:
        raise ValueError(f"no road condition column found in {path}")

    df = df.rename(columns=RENAME_MAP)
    df = df.rename(columns={road_col: "road_condition"})

    wanted = list(RENAME_MAP.values()) + ["road_condition"]
    missing = [c for c in wanted if c not in df.columns]
    if missing:
        raise ValueError(f"columns {missing} missing in {path}")
    return df[wanted]


def clean_accidents(df):
    """Drop rows with invalid values and add the state name."""
    n_before = len(df)
    df = df.dropna(subset=["lon", "lat", "hour", "severity"])
    df = df.astype({"state_id": int, "year": int, "month": int, "hour": int,
                    "weekday": int, "severity": int, "accident_type": int,
                    "road_condition": int})
    # keep only plausible coordinates (Germany) and valid categories
    df = df[df["lon"].between(5.5, 15.5) & df["lat"].between(47.0, 55.2)]
    df = df[df["severity"].isin([1, 2, 3])]
    df = df[df["road_condition"].isin([0, 1, 2])]
    df["state_name"] = df["state_id"].map(STATE_NAMES)
    df = df.dropna(subset=["state_name"])
    log.info("cleaning removed %d of %d rows", n_before - len(df), n_before)
    return df


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", default="data/raw_accidents",
                        help="directory with the raw Unfallatlas files")
    parser.add_argument("--start-year", type=int, default=2020)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--output", default="data/processed/accidents_clean.csv")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    files = find_raw_files(args.raw_dir)
    if not files:
        log.error("no raw accident files found in %s", args.raw_dir)
        sys.exit(1)

    frames = []
    for path in files:
        try:
            df = load_raw_file(path)
        except (ValueError, OSError) as err:
            log.error("could not read %s: %s", path, err)
            sys.exit(1)
        log.info("read %s (%d rows)", os.path.basename(path), len(df))
        frames.append(df)

    accidents = pd.concat(frames, ignore_index=True)
    accidents = accidents[accidents["year"].between(args.start_year, args.end_year)]
    accidents = clean_accidents(accidents)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    accidents.to_csv(args.output, index=False)
    log.info("wrote %d accidents (%d-%d) to %s",
             len(accidents), args.start_year, args.end_year, args.output)


if __name__ == "__main__":
    main()
