"""Tests for prepare_accidents.py."""

import pandas as pd
import pytest

import prepare_accidents


HEADER_2024 = ("OID_;UIDENTSTLAE;ULAND;UREGBEZ;UKREIS;UGEMEINDE;UJAHR;UMONAT;"
               "USTUNDE;UWOCHENTAG;UKATEGORIE;UART;UTYP1;ULICHTVERH;"
               "IstStrassenzustand;IstRad;IstPKW;IstFuss;IstKrad;IstGkfz;"
               "IstSonstige;LINREFX;LINREFY;XGCSWGS84;YGCSWGS84;PLST")
ROW_2024 = ("1;0124;01;0;59;044;2024;05;23;1;3;1;5;2;0;0;1;0;0;0;0;"
            "525162,37;6045497,20;9,389075;54,556379;1")

HEADER_2020 = ("OBJECTID;UIDENTSTLAE;ULAND;UREGBEZ;UKREIS;UGEMEINDE;UJAHR;UMONAT;"
               "USTUNDE;UWOCHENTAG;UKATEGORIE;UART;UTYP1;ULICHTVERH;IstRad;"
               "IstPKW;IstFuss;IstKrad;IstGkfz;IstSonstige;LINREFX;LINREFY;"
               "XGCSWGS84;YGCSWGS84;STRZUSTAND")
ROW_2020 = ("1;0120;01;0;53;120;2020;01;09;5;2;8;1;0;0;1;0;0;0;0;"
            "606982,39;5954659,92;10,621659;53,729614;1")


def write_file(path, header, rows):
    path.write_text("\n".join([header] + rows), encoding="utf-8")


def test_load_raw_file_handles_2024_format(tmp_path):
    path = tmp_path / "Unfallorte2024_LinRef.csv"
    write_file(path, HEADER_2024, [ROW_2024])
    df = prepare_accidents.load_raw_file(str(path))
    assert list(df["year"]) == [2024]
    assert list(df["road_condition"]) == [0]
    assert df["lon"].iloc[0] == pytest.approx(9.389075)


def test_load_raw_file_handles_2020_format(tmp_path):
    path = tmp_path / "Unfallorte2020_LinRef.csv"
    write_file(path, HEADER_2020, [ROW_2020])
    df = prepare_accidents.load_raw_file(str(path))
    assert list(df["year"]) == [2020]
    assert list(df["road_condition"]) == [1]
    assert list(df["severity"]) == [2]


def test_load_raw_file_fails_without_road_condition(tmp_path):
    path = tmp_path / "Unfallorte_broken.csv"
    write_file(path, HEADER_2024.replace("IstStrassenzustand", "Unknown"), [ROW_2024])
    with pytest.raises(ValueError, match="road condition"):
        prepare_accidents.load_raw_file(str(path))


def test_clean_accidents_drops_invalid_rows():
    df = pd.DataFrame({
        "state_id": [1, 1, 99, 1],
        "region_id": [0, 0, 0, 0],
        "district_id": [59, 59, 59, 59],
        "year": [2020] * 4, "month": [1] * 4, "hour": [12] * 4,
        "weekday": [2] * 4,
        "severity": [1, 9, 2, 3],          # 9 is invalid
        "accident_type": [1] * 4,
        "road_condition": [0, 0, 0, 0],
        "lon": [10.0, 10.0, 10.0, 200.0],  # 200 is outside Germany
        "lat": [50.0, 50.0, 50.0, 50.0],
    })
    cleaned = prepare_accidents.clean_accidents(df)
    # row 1 invalid severity, row 2 unknown state, row 3 bad longitude
    assert len(cleaned) == 1
    assert cleaned["state_name"].iloc[0] == "Schleswig-Holstein"
