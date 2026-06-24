"""Tag every accident as urban or rural using the BBSR district types.

The published Unfallatlas has no road-class attribute (Autobahn vs.
Landstrasse), so RQ1 cannot be answered on that axis. Instead this step
attaches a spatial dimension the data *does* support: it builds the
five-digit district key (``ULAND`` + ``UREGBEZ`` + ``UKREIS``) for every
accident and joins the BBSR *siedlungsstruktureller Kreistyp* reference
(see ``data/reference/README.md``), which classifies each German district
into one of four settlement-structure types. Types 1-2 are mapped to
``urban`` and types 3-4 to ``rural``.

This is the third dataset of the project (accidents + DWD weather + BBSR
district types) and turns RQ1 into an urban-vs-rural comparison.

Usage:
    python src/classify_region.py \\
        --accidents data/processed/accidents_clean.csv \\
        --reference data/reference/bbsr_kreistypen_2020.csv \\
        --output data/processed/accidents_classified.csv
"""

import argparse
import logging
import os
import sys

import pandas as pd

log = logging.getLogger("classify_region")

# BBSR settlement-structure type code -> readable label
TYPE_LABEL = {
    1: "kreisfreie Grossstadt",
    2: "staedtischer Kreis",
    3: "laendlicher Kreis mit Verdichtung",
    4: "duenn besiedelter laendlicher Kreis",
}
# which of those types count as urban vs. rural
URBAN_RURAL = {1: "urban", 2: "urban", 3: "rural", 4: "rural"}

KENNZIFFER_COL = "Kreise (2020) Kennziffer"
KREISTYP_COL = "Siedlungsstruktureller Kreistyp (2020) Kennziffer"


def build_kreis_ags(accidents):
    """Build the 5-digit district key from the administrative columns.

    ``ULAND`` (2 digits) + ``UREGBEZ`` (1 digit) + ``UKREIS`` (2 digits),
    each zero-padded, e.g. state 1 / region 0 / district 59 -> ``01059``.
    """
    for col in ("state_id", "region_id", "district_id"):
        if col not in accidents.columns:
            raise ValueError(f"accident table is missing the '{col}' column; "
                             f"re-run prepare_accidents.py first")
    state = accidents["state_id"].astype(int).map("{:02d}".format)
    region = accidents["region_id"].astype(int).map("{:01d}".format)
    district = accidents["district_id"].astype(int).map("{:02d}".format)
    return state + region + district


def load_reference(path):
    """Read the BBSR Kreistyp CSV into kreis_ags -> region_type/region_class."""
    ref = pd.read_csv(path, sep=";", encoding="latin-1", dtype=str)
    if KENNZIFFER_COL not in ref.columns or KREISTYP_COL not in ref.columns:
        raise ValueError(f"unexpected BBSR reference layout in {path}")

    ref = ref.rename(columns={KENNZIFFER_COL: "kennziffer",
                              KREISTYP_COL: "kreistyp"})
    # the first 5 digits of the Kennziffer are the district key (ULAND+UREGBEZ+UKREIS)
    ref["kreis_ags"] = ref["kennziffer"].str.strip().str[:5]
    ref["kreistyp"] = pd.to_numeric(ref["kreistyp"], errors="coerce")
    ref = ref[ref["kreistyp"].isin(TYPE_LABEL)].copy()
    ref["region_type"] = ref["kreistyp"].map(TYPE_LABEL)
    ref["region_class"] = ref["kreistyp"].map(URBAN_RURAL)
    return ref[["kreis_ags", "region_type", "region_class"]].drop_duplicates("kreis_ags")


def classify(accidents, reference):
    """Attach region_type / region_class to the accident table."""
    accidents = accidents.copy()
    accidents["kreis_ags"] = build_kreis_ags(accidents)
    merged = accidents.merge(reference, on="kreis_ags", how="left")
    merged["region_type"] = merged["region_type"].fillna("unknown")
    merged["region_class"] = merged["region_class"].fillna("unknown")
    return merged.drop(columns=["kreis_ags"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--accidents", default="data/processed/accidents_clean.csv")
    parser.add_argument("--reference",
                        default="data/reference/bbsr_kreistypen_2020.csv")
    parser.add_argument("--output",
                        default="data/processed/accidents_classified.csv")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    for path in (args.accidents, args.reference):
        if not os.path.exists(path):
            log.error("input file %s not found", path)
            sys.exit(1)

    accidents = pd.read_csv(args.accidents)
    try:
        reference = load_reference(args.reference)
        classified = classify(accidents, reference)
    except ValueError as err:
        log.error("%s", err)
        sys.exit(1)

    known = classified["region_class"] != "unknown"
    shares = classified.loc[known, "region_class"].value_counts(normalize=True)
    log.info("classified %d accidents: %.1f%% matched a district (%.0f%% urban, "
             "%.0f%% rural); %d unmatched",
             len(classified), known.mean() * 100,
             shares.get("urban", 0) * 100, shares.get("rural", 0) * 100,
             int((~known).sum()))

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    classified.to_csv(args.output, index=False)
    log.info("wrote %d classified accidents to %s", len(classified), args.output)


if __name__ == "__main__":
    main()
