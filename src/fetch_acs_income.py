"""
Fetch ACS 5-year median household income for selected Florida counties.

Inputs:
- data/manual/selected_counties.csv
- CENSUS_API_KEY in project-root .env

Outputs:
- data/raw/acs_income/acs_b19013_miami_dade_2015_2024.csv  (legacy Miami-Dade)
- data/processed/acs_b19013_selected_counties_2015_2024.csv  (pipeline expansion)
"""

from pathlib import Path

import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
SELECTED_COUNTIES_PATH = PROJECT_ROOT / "data" / "manual" / "selected_counties.csv"
MIAMI_OUTPUT_PATH = (
    PROJECT_ROOT / "data" / "raw" / "acs_income" / "acs_b19013_miami_dade_2015_2024.csv"
)
SELECTED_OUTPUT_PATH = (
    PROJECT_ROOT / "data" / "processed" / "acs_b19013_selected_counties_2015_2024.csv"
)

START_YEAR = 2015
END_YEAR = 2024
YEARS = list(range(START_YEAR, END_YEAR + 1))
EXPECTED_YEARS = set(YEARS)

STATE_FIPS = "12"
COUNTY_CODES = "011,086,099"
EXPECTED_PIPELINE_FIPS = {"12011", "12086", "12099"}
EXPECTED_PIPELINE_COUNTIES = 3
EXPECTED_PIPELINE_ROWS = 30
MIAMI_LEGACY_FIPS = "12086"

REQUIRED_API_FIELDS = {"NAME", "B19013_001E", "state", "county"}
INCOME_SUPPRESSION_SENTINELS = {
    -666666666,
    -555555555,
    -444444444,
    -333333333,
    -222222222,
}

LEGACY_COLUMNS = [
    "year",
    "name",
    "median_household_income",
    "state_fips",
    "county_fips_short",
    "county_fips",
    "source",
]

SELECTED_COLUMNS = [
    "state",
    "county_fips",
    "county_name",
    "year",
    "median_household_income",
    "income_source",
]


def normalize_county_fips(series: pd.Series) -> pd.Series:
    """Convert county FIPS values to five-character strings."""
    return series.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)


def is_truthy(value) -> bool:
    """Interpret boolean-like CSV values as true."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not pd.isna(value):
        return int(value) == 1
    return str(value).strip().lower() in {"true", "1", "yes", "t"}


def load_census_api_key() -> str:
    """Load Census API key from local .env file."""
    if not ENV_PATH.exists():
        raise FileNotFoundError("Missing .env file with CENSUS_API_KEY.")

    for line in ENV_PATH.read_text().splitlines():
        if line.startswith("CENSUS_API_KEY="):
            return line.split("=", 1)[1].strip()

    raise ValueError("CENSUS_API_KEY not found in .env file.")


def load_pipeline_selection() -> pd.DataFrame:
    """Load and validate selected counties for pipeline expansion."""
    selection = pd.read_csv(SELECTED_COUNTIES_PATH, dtype={"county_fips": "string"})
    if "include_pipeline" not in selection.columns:
        raise ValueError("selected_counties.csv is missing required column: include_pipeline")

    selection["county_fips"] = normalize_county_fips(selection["county_fips"])
    selected = selection[selection["include_pipeline"].map(is_truthy)].copy()

    if len(selected) != EXPECTED_PIPELINE_COUNTIES:
        raise ValueError(
            f"Expected exactly {EXPECTED_PIPELINE_COUNTIES} pipeline counties, "
            f"found {len(selected)}."
        )

    selected_fips = set(selected["county_fips"])
    if selected_fips != EXPECTED_PIPELINE_FIPS:
        raise ValueError(
            f"Expected pipeline county_fips {sorted(EXPECTED_PIPELINE_FIPS)}, "
            f"found {sorted(selected_fips)}."
        )

    return selected.sort_values("county_fips").reset_index(drop=True)


def parse_income_value(raw_value, year: int, county_fips: str) -> int:
    """Parse and validate B19013_001E for one county-year."""
    if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
        raise ValueError(
            f"Missing median household income for year {year}, county FIPS {county_fips}."
        )

    text = str(raw_value).strip().replace(",", "")
    try:
        income = int(text)
    except ValueError as exc:
        raise ValueError(
            f"Nonnumeric median household income for year {year}, "
            f"county FIPS {county_fips}: {raw_value!r}."
        ) from exc

    if income in INCOME_SUPPRESSION_SENTINELS or income <= 0:
        raise ValueError(
            f"Invalid or suppressed median household income for year {year}, "
            f"county FIPS {county_fips}: {income}."
        )

    return income


def fetch_counties_for_year(year: int, api_key: str) -> list[dict]:
    """Fetch median household income for three pipeline counties in one year."""
    url = f"https://api.census.gov/data/{year}/acs/acs5"
    params = {
        "get": "NAME,B19013_001E",
        "for": f"county:{COUNTY_CODES}",
        "in": f"state:{STATE_FIPS}",
        "key": api_key,
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    rows = response.json()
    if not rows or not isinstance(rows, list):
        raise ValueError(f"Unexpected ACS response for {year}: empty or non-list payload.")

    header = rows[0]
    if not isinstance(header, list):
        raise ValueError(f"Unexpected ACS header for {year}: {header!r}")

    missing_fields = REQUIRED_API_FIELDS - set(header)
    if missing_fields:
        raise ValueError(
            f"ACS response for {year} missing required fields: {sorted(missing_fields)}"
        )

    data_rows = rows[1:]
    if len(data_rows) != EXPECTED_PIPELINE_COUNTIES:
        raise ValueError(
            f"ACS response for {year} returned {len(data_rows)} county records; "
            f"expected {EXPECTED_PIPELINE_COUNTIES}."
        )

    records = []
    for values in data_rows:
        record = dict(zip(header, values))
        county_fips = record["state"].zfill(2) + record["county"].zfill(3)
        income = parse_income_value(record["B19013_001E"], year, county_fips)
        records.append(
            {
                "year": year,
                "name": record["NAME"],
                "median_household_income": income,
                "state_fips": record["state"],
                "county_fips_short": record["county"],
                "county_fips": county_fips,
                "source": f"ACS {year} 5-year B19013",
            }
        )

    returned_fips = {record["county_fips"] for record in records}
    if returned_fips != EXPECTED_PIPELINE_FIPS:
        raise ValueError(
            f"ACS response for {year} returned county FIPS {sorted(returned_fips)}; "
            f"expected {sorted(EXPECTED_PIPELINE_FIPS)}."
        )

    return records


def build_legacy_miami_output(records: list[dict]) -> pd.DataFrame:
    """Filter Miami-Dade rows from the shared acquisition snapshot."""
    miami = [record for record in records if record["county_fips"] == MIAMI_LEGACY_FIPS]
    if len(miami) != len(YEARS):
        raise ValueError(
            f"Expected {len(YEARS)} Miami-Dade records, found {len(miami)}."
        )

    df = pd.DataFrame(miami)[LEGACY_COLUMNS]
    return df.sort_values("year").reset_index(drop=True)


def build_selected_output(
    records: list[dict],
    selection: pd.DataFrame,
) -> pd.DataFrame:
    """Build pipeline-ready selected-counties ACS output."""
    selection_index = selection.set_index("county_fips")
    rows = []

    for record in records:
        county_fips = record["county_fips"]
        county_meta = selection_index.loc[county_fips]
        rows.append(
            {
                "state": county_meta["state"],
                "county_fips": county_fips,
                "county_name": county_meta["county_name"],
                "year": record["year"],
                "median_household_income": record["median_household_income"],
                "income_source": record["source"],
            }
        )

    df = pd.DataFrame(rows)
    df["county_fips"] = normalize_county_fips(df["county_fips"])
    return df[SELECTED_COLUMNS].sort_values(["county_fips", "year"]).reset_index(drop=True)


def validate_selected_output(selected: pd.DataFrame, selection: pd.DataFrame) -> None:
    """Validate selected-counties ACS output before write."""
    if len(selected) != EXPECTED_PIPELINE_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_PIPELINE_ROWS} selected-county rows, found {len(selected)}."
        )

    if list(selected.columns) != SELECTED_COLUMNS:
        raise ValueError(
            f"Unexpected selected output columns: {list(selected.columns)}"
        )

    selected_fips = set(normalize_county_fips(selected["county_fips"]))
    if selected_fips != EXPECTED_PIPELINE_FIPS:
        raise ValueError(
            f"Expected county_fips {sorted(EXPECTED_PIPELINE_FIPS)}, "
            f"found {sorted(selected_fips)}."
        )

    if set(selected["year"]) != EXPECTED_YEARS:
        raise ValueError(
            f"Expected years {sorted(EXPECTED_YEARS)}, "
            f"found {sorted(set(selected['year']))}."
        )

    if selected.duplicated(["county_fips", "year"]).any():
        raise ValueError("Duplicate county_fips/year keys in selected-counties output.")

    null_counts = selected[SELECTED_COLUMNS].isna().sum()
    if null_counts.any():
        raise ValueError(
            "Null values in required selected-counties columns:\n"
            f"{null_counts[null_counts > 0]}"
        )

    if not selected["county_fips"].str.fullmatch(r"\d{5}").all():
        raise ValueError("county_fips must be five-character numeric strings.")

    if not pd.api.types.is_numeric_dtype(selected["median_household_income"]):
        raise ValueError("median_household_income is not numeric.")

    if not (selected["median_household_income"] > 0).all():
        raise ValueError("median_household_income must be greater than zero.")

    expected_labels = selection.set_index("county_fips")["county_name"].to_dict()
    actual_labels = (
        selected[["county_fips", "county_name"]]
        .drop_duplicates()
        .set_index("county_fips")["county_name"]
        .to_dict()
    )
    if actual_labels != expected_labels:
        raise ValueError(
            f"County labels do not match selected_counties.csv: {actual_labels}"
        )

    expected_sources = selected["year"].map(lambda year: f"ACS {year} 5-year B19013")
    if not selected["income_source"].equals(expected_sources):
        raise ValueError("income_source values do not match the required pattern.")

    expected_order = selected.sort_values(["county_fips", "year"]).reset_index(drop=True)
    if not selected.reset_index(drop=True).equals(expected_order):
        raise ValueError("Selected output is not sorted by county_fips, then year.")


def validate_miami_regression(selected: pd.DataFrame, legacy: pd.DataFrame) -> None:
    """Confirm Miami-Dade rows match between selected and legacy outputs."""
    new_miami = (
        selected.loc[selected["county_fips"] == MIAMI_LEGACY_FIPS]
        .sort_values("year")
        .reset_index(drop=True)
    )
    old_miami = legacy.sort_values("year").reset_index(drop=True)

    pd.testing.assert_frame_equal(
        new_miami[["year", "county_fips", "median_household_income"]],
        old_miami[["year", "county_fips", "median_household_income"]],
        check_dtype=False,
    )
    pd.testing.assert_series_equal(
        new_miami["income_source"],
        old_miami["source"],
        check_dtype=False,
        check_names=False,
    )


def main() -> None:
    """Fetch ACS income for pipeline counties and write legacy and selected outputs."""
    selection = load_pipeline_selection()
    api_key = load_census_api_key()

    records = []
    for year in YEARS:
        print(f"Fetching ACS income for {year}...")
        records.extend(fetch_counties_for_year(year, api_key))

    legacy = build_legacy_miami_output(records)
    selected = build_selected_output(records, selection)

    validate_selected_output(selected, selection)
    validate_miami_regression(selected, legacy)

    MIAMI_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SELECTED_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    legacy.to_csv(MIAMI_OUTPUT_PATH, index=False)
    selected.to_csv(SELECTED_OUTPUT_PATH, index=False)

    print(
        f"[PASS] selected county configuration: {EXPECTED_PIPELINE_COUNTIES} counties "
        f"({', '.join(sorted(EXPECTED_PIPELINE_FIPS))})"
    )
    print(
        f"[PASS] annual response/FIPS coverage: {len(YEARS)} years, "
        f"{EXPECTED_PIPELINE_COUNTIES} counties per year"
    )
    print(
        f"[PASS] final county-year coverage: {len(selected)} rows, "
        f"10 per county, {START_YEAR}-{END_YEAR}"
    )
    print("[PASS] keys, nulls, FIPS, income values, and labels validated")
    print("[PASS] Miami-Dade regression comparison: selected rows match legacy output")
    print(f"[PASS] legacy output written: {MIAMI_OUTPUT_PATH}")
    print(f"[PASS] selected output written: {SELECTED_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
