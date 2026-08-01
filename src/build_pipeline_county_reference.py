"""
Build multistate county reference CSV from TIGER 2023 county boundaries.

Reads enabled states from data/manual/pipeline_states.csv and writes
data/manual/pipeline_counties.csv for the four-state southeastern pilot
(Florida, Georgia, South Carolina, North Carolina).
"""

from pathlib import Path
import zipfile

import geopandas as gpd
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

PIPELINE_STATES_PATH = PROJECT_ROOT / "data" / "manual" / "pipeline_states.csv"
PIPELINE_COUNTIES_PATH = PROJECT_ROOT / "data" / "manual" / "pipeline_counties.csv"
FLORIDA_REFERENCE_PATH = PROJECT_ROOT / "data" / "manual" / "florida_counties.csv"
TIGER_ZIP = PROJECT_ROOT / "data" / "raw" / "census_tiger" / "cb_2023_us_county_500k.zip"

STATE_MANIFEST_COLUMNS = ["state", "state_fips", "include_pipeline"]
COUNTY_REFERENCE_COLUMNS = ["state", "state_fips", "county_fips", "county_name"]

EXPECTED_ENABLED_STATES = {"FL", "GA", "SC", "NC"}
EXPECTED_STATE_COUNTS = {
    "FL": 67,
    "GA": 159,
    "SC": 46,
    "NC": 100,
}
EXPECTED_TOTAL_COUNTIES = 372

REQUIRED_TIGER_COLUMNS = ["STUSPS", "STATEFP", "GEOID", "NAMELSAD", "geometry"]


def pass_line(message: str) -> None:
    print(f"[PASS] {message}")


def fail(message: str) -> None:
    raise ValueError(message)


def normalize_county_fips(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)


def normalize_state_fips(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(2)


def parse_include_pipeline(value) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    fail(f"Unrecognized include_pipeline value: {value!r}")


def load_enabled_states() -> pd.DataFrame:
    if not PIPELINE_STATES_PATH.exists():
        fail(f"Pipeline state manifest not found: {PIPELINE_STATES_PATH}")

    states = pd.read_csv(
        PIPELINE_STATES_PATH,
        dtype={"state": "string", "state_fips": "string"},
    )

    if list(states.columns) != STATE_MANIFEST_COLUMNS:
        fail(
            f"Unexpected pipeline_states.csv columns: {list(states.columns)}; "
            f"expected {STATE_MANIFEST_COLUMNS}"
        )

    states["state_fips"] = normalize_state_fips(states["state_fips"])

    if states["state"].isna().any() or states["state_fips"].isna().any():
        fail("Null state or state_fips values in pipeline_states.csv.")

    if not states["state_fips"].str.fullmatch(r"\d{2}").all():
        fail("state_fips values must be exactly two numeric characters.")

    if states["state"].nunique() != len(states):
        fail("Duplicate state values in pipeline_states.csv.")

    if states["state_fips"].nunique() != len(states):
        fail("Duplicate state_fips values in pipeline_states.csv.")

    enabled_mask = states["include_pipeline"].map(parse_include_pipeline)
    enabled = states.loc[enabled_mask].copy()

    if set(enabled["state"]) != EXPECTED_ENABLED_STATES:
        fail(
            f"Enabled states must be {sorted(EXPECTED_ENABLED_STATES)}; "
            f"found {sorted(enabled['state'])}"
        )

    pass_line(
        "enabled-state configuration "
        f"({len(enabled)} states: {', '.join(sorted(enabled['state']))})"
    )

    return enabled.sort_values("state_fips").reset_index(drop=True)


def load_tiger_counties(enabled_state_fips: set[str]) -> gpd.GeoDataFrame:
    if not TIGER_ZIP.exists():
        fail(f"TIGER boundary archive not found: {TIGER_ZIP}")

    with zipfile.ZipFile(TIGER_ZIP) as zf:
        shp_name = next(name for name in zf.namelist() if name.endswith(".shp"))
    zip_path = f"zip://{TIGER_ZIP}!{shp_name}"

    counties = gpd.read_file(zip_path)

    missing_columns = [col for col in REQUIRED_TIGER_COLUMNS if col not in counties.columns]
    if missing_columns:
        fail(f"TIGER archive missing required columns: {missing_columns}")

    counties["STATEFP"] = normalize_state_fips(counties["STATEFP"])
    counties["GEOID"] = normalize_county_fips(counties["GEOID"])

    selected = counties[counties["STATEFP"].isin(enabled_state_fips)].copy()

    if selected.geometry.isna().any():
        fail(
            f"Null geometry in selected TIGER records: "
            f"{int(selected.geometry.isna().sum())}"
        )

    return selected


def build_county_reference(
    enabled_states: pd.DataFrame,
    tiger_selected: gpd.GeoDataFrame,
) -> pd.DataFrame:
    reference = pd.DataFrame(
        {
            "state": tiger_selected["STUSPS"].astype("string"),
            "state_fips": tiger_selected["STATEFP"].astype("string"),
            "county_fips": tiger_selected["GEOID"].astype("string"),
            "county_name": tiger_selected["NAMELSAD"].astype("string"),
        }
    )

    reference["state_fips"] = normalize_state_fips(reference["state_fips"])
    reference["county_fips"] = normalize_county_fips(reference["county_fips"])

    if len(reference) != EXPECTED_TOTAL_COUNTIES:
        fail(
            f"Expected exactly {EXPECTED_TOTAL_COUNTIES} counties, found {len(reference)}"
        )

    for state_abbr, expected_count in EXPECTED_STATE_COUNTS.items():
        actual_count = int((reference["state"] == state_abbr).sum())
        if actual_count != expected_count:
            fail(
                f"Expected {expected_count} counties for {state_abbr}, found {actual_count}"
            )
        pass_line(f"{state_abbr} county count ({actual_count})")

    pass_line(f"total county count ({len(reference)})")

    if not reference["county_fips"].str.fullmatch(r"\d{5}").all():
        fail("county_fips values must match exactly five digits.")

    if reference["county_fips"].nunique() != len(reference):
        fail("county_fips values must be unique.")

    if not (reference["county_fips"].str[:2] == reference["state_fips"]).all():
        fail("state_fips must match the first two characters of county_fips.")

    for column in ["state", "state_fips", "county_name"]:
        if reference[column].isna().any():
            fail(f"Null values found in {column}.")
        if reference[column].astype(str).str.strip().eq("").any():
            fail(f"Blank values found in {column}.")

    pass_line("FIPS, uniqueness, and required-value validation")

    enabled_state_set = set(enabled_states["state"])
    if not reference["state"].isin(enabled_state_set).all():
        fail("County reference contains states outside the enabled manifest.")

    return reference.sort_values(["state_fips", "county_fips"]).reset_index(drop=True)


def compare_florida_subset(reference: pd.DataFrame) -> None:
    if not FLORIDA_REFERENCE_PATH.exists():
        fail(f"Florida county reference not found: {FLORIDA_REFERENCE_PATH}")

    florida_existing = pd.read_csv(
        FLORIDA_REFERENCE_PATH,
        dtype={"state": "string", "county_fips": "string", "county_name": "string"},
    )
    florida_existing["county_fips"] = normalize_county_fips(florida_existing["county_fips"])

    florida_generated = (
        reference.loc[reference["state"] == "FL", ["state", "county_fips", "county_name"]]
        .sort_values("county_fips")
        .reset_index(drop=True)
    )
    florida_existing = florida_existing.sort_values("county_fips").reset_index(drop=True)

    if not florida_generated.equals(florida_existing):
        mismatch = florida_generated.compare(florida_existing, keep_shape=True, keep_equal=False)
        fail(
            "Generated Florida subset does not match florida_counties.csv:\n"
            f"{mismatch.to_string()}"
        )

    pass_line("Florida regression comparison (state, county_fips, county_name)")


def main() -> None:
    enabled_states = load_enabled_states()
    enabled_state_fips = set(enabled_states["state_fips"])

    tiger_selected = load_tiger_counties(enabled_state_fips)
    reference = build_county_reference(enabled_states, tiger_selected)
    compare_florida_subset(reference)

    reference.to_csv(PIPELINE_COUNTIES_PATH, index=False)
    pass_line(f"output written ({PIPELINE_COUNTIES_PATH})")


if __name__ == "__main__":
    main()
