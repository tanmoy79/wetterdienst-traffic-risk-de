"""Tests for classify_region.py."""

import pandas as pd
import pytest

import classify_region


def test_build_kreis_ags_zero_pads_components():
    accidents = pd.DataFrame({
        "state_id": [1, 11],
        "region_id": [0, 0],
        "district_id": [59, 0],
    })
    ags = classify_region.build_kreis_ags(accidents)
    # state 1 / region 0 / district 59 -> "01059"; Berlin -> "11000"
    assert list(ags) == ["01059", "11000"]


def test_build_kreis_ags_requires_columns():
    accidents = pd.DataFrame({"state_id": [1]})
    with pytest.raises(ValueError, match="region_id"):
        classify_region.build_kreis_ags(accidents)


def test_load_reference_maps_types_to_urban_rural(tmp_path):
    content = (
        '"Kreise (2020) Kennziffer";"Kreise (2020) Name";'
        '"Siedlungsstruktureller Kreistyp (2020) Kennziffer";'
        '"Siedlungsstruktureller Kreistyp (2020) Name"\n'
        '"01002000";"Kiel";"1";"kreisfreie Grossstadt"\n'
        '"01059000";"Schleswig-Flensburg";"4";"laendlich"\n'
    )
    path = tmp_path / "bbsr.csv"
    path.write_text(content, encoding="latin-1")

    ref = classify_region.load_reference(str(path))
    by_ags = ref.set_index("kreis_ags")
    assert by_ags.loc["01002", "region_class"] == "urban"     # type 1
    assert by_ags.loc["01059", "region_class"] == "rural"     # type 4


def test_classify_attaches_region_and_flags_unknown():
    accidents = pd.DataFrame({
        "state_id": [1, 1],
        "region_id": [0, 0],
        "district_id": [2, 99],          # 01002 known, 01099 not in reference
        "severity": [1, 3],
    })
    reference = pd.DataFrame({
        "kreis_ags": ["01002"],
        "region_type": ["kreisfreie Grossstadt"],
        "region_class": ["urban"],
    })
    out = classify_region.classify(accidents, reference)
    assert list(out["region_class"]) == ["urban", "unknown"]
    assert "kreis_ags" not in out.columns        # helper column is dropped
    assert list(out["severity"]) == [1, 3]       # original columns preserved
