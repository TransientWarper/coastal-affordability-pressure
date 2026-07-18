"""
Fetch ACS 5-year median household income for selected and Florida counties.

Inputs:
- data/manual/selected_counties.csv
- data/manual/florida_counties.csv
- CENSUS_API_KEY in project-root .env

Outputs:
- data/raw/acs_income/acs_b19013_miami_dade_2015_2024.csv  (legacy Miami-Dade)
- data/processed/acs_b19013_florida_counties_2015_2024.csv  (statewide expansion)
"""

from pathlib import Path

import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
SELECTED_COUNTIES_PATH = PROJECT_ROOT / "data" / "manual" / "selected_counties.csv"
FLORIDA_REFERENCE_PATH = PROJECT_ROOT / "data" / "manual" / "florida_counties.csv"
COMMITTED_SELECTED_PATH = (
    PROJECT_ROOT / "data" / "processed" / "acs_b19013_selected_counties_2015_2024.csv"
)
MIAMI_OUTPUT_PATH = (
    PROJECT_ROOT / "data" / "raw" / "acs_income" / "acs_b19013_miami_dade_2015_2024.csv"
)
FLORIDA_OUTPUT_PATH = (
    PROJECT_ROOT / "data" / "processed" / "acs_b19013_florida_counties_2015_2024.csv"
)

START_YEAR = 2015
END_YEAR = 2024
YEARS = list(range(START_YEAR, END_YEAR + 1))
EXPECTED_YEARS = set(YEARS)

STATE_FIPS = "12"
EXPECTED_PIPELINE_FIPS = {"12011", "12086", "12099"}
EXPECTED_PIPELINE_COUNTIES = 3
EXPECTED_FL_COUNTIES = 67
EXPECTED_FL_ROWS = 670
MIAMI_LEGACY_FIPS = "12086"
MIAMI_LEGACY_MD5 = "ef5b8d6f5e911b9bafc087862238ebbf"

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

FLORIDA_COLUMNS = [
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


def load_florida_reference() -> pd.DataFrame:
    """Load and validate the authoritative 67-county Florida reference."""
    if not FLORIDA_REFERENCE_PATH.exists():
        raise FileNotFoundError(
            f"Florida county reference not found: {FLORIDA_REFERENCE_PATH}"
        )

    reference = pd.read_csv(
        FLORIDA_REFERENCE_PATH,
        dtype={"county_fips": "string", "county_name": "string", "state": "string"},
    )

    if list(reference.columns) != ["state", "county_fips", "county_name"]:
        raise ValueError(
            f"Unexpected florida_counties.csv columns: {list(reference.columns)}"
        )

    reference["county_fips"] = normalize_county_fips(reference["county_fips"])

    if len(reference) != EXPECTED_FL_COUNTIES:
        raise ValueError(
            f"Expected exactly {EXPECTED_FL_COUNTIES} Florida reference rows, "
            f"found {len(reference)}."
        )

    if reference["county_fips"].nunique() != EXPECTED_FL_COUNTIES:
        raise ValueError(
            f"Expected {EXPECTED_FL_COUNTIES} unique county_fips values, "
            f"found {reference['county_fips'].nunique()}."
        )

    if reference.duplicated(["county_fips"]).any():
        raise ValueError("Duplicate county_fips values in florida_counties.csv.")

    if not reference["state"].eq("FL").all():
        raise ValueError("All florida_counties.csv state values must be FL.")

    if not reference["county_fips"].str.fullmatch(r"12\d{3}").all():
        raise ValueError("county_fips in florida_counties.csv must match ^12\\d{3}$.")

    if reference["county_name"].isna().any():
        raise ValueError("Null county_name values in florida_counties.csv.")

    if reference["county_name"].astype(str).str.strip().eq("").any():
        raise ValueError("Blank county_name values in florida_counties.csv.")

    return reference.sort_values("county_fips").reset_index(drop=True)


def load_committed_selected_counties() -> pd.DataFrame:
    """Load the committed three-county pilot output for regression comparison."""
    if not COMMITTED_SELECTED_PATH.exists():
        raise FileNotFoundError(
            f"Committed selected-counties output not found: {COMMITTED_SELECTED_PATH}"
        )

    committed = pd.read_csv(
        COMMITTED_SELECTED_PATH,
        dtype={"county_fips": "string"},
    )
    committed["county_fips"] = normalize_county_fips(committed["county_fips"])
    return committed.sort_values(["county_fips", "year"]).reset_index(drop=True)


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


def fetch_florida_for_year(
    year: int,
    api_key: str,
    expected_fips: set[str],
) -> list[dict]:
    """Fetch median household income for all Florida counties in one year."""
    url = f"https://api.census.gov/data/{year}/acs/acs5"
    params = {
        "get": "NAME,B19013_001E",
        "for": "county:*",
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
    if len(data_rows) != EXPECTED_FL_COUNTIES:
        raise ValueError(
            f"ACS response for {year} returned {len(data_rows)} county records; "
            f"expected {EXPECTED_FL_COUNTIES}."
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
    if returned_fips != expected_fips:
        raise ValueError(
            f"ACS response for {year} returned county FIPS {sorted(returned_fips)}; "
            f"expected {sorted(expected_fips)}."
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


def build_florida_output(
    records: list[dict],
    reference: pd.DataFrame,
) -> pd.DataFrame:
    """Build statewide Florida ACS output using the authoritative county reference."""
    reference_index = reference.set_index("county_fips")
    rows = []

    for record in records:
        county_fips = record["county_fips"]
        county_meta = reference_index.loc[county_fips]
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
    return df[FLORIDA_COLUMNS].sort_values(["county_fips", "year"]).reset_index(drop=True)


def validate_florida_output(florida: pd.DataFrame, reference: pd.DataFrame) -> None:
    """Validate Florida ACS output before write."""
    if len(florida) != EXPECTED_FL_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_FL_ROWS} Florida county-year rows, found {len(florida)}."
        )

    if list(florida.columns) != FLORIDA_COLUMNS:
        raise ValueError(f"Unexpected Florida output columns: {list(florida.columns)}")

    florida_fips = set(normalize_county_fips(florida["county_fips"]))
    reference_fips = set(normalize_county_fips(reference["county_fips"]))
    if florida_fips != reference_fips:
        raise ValueError(
            f"Florida output FIPS {sorted(florida_fips)} do not match reference "
            f"{sorted(reference_fips)}."
        )

    if len(florida_fips) != EXPECTED_FL_COUNTIES:
        raise ValueError(
            f"Expected {EXPECTED_FL_COUNTIES} unique county_fips values, "
            f"found {len(florida_fips)}."
        )

    if set(florida["year"]) != EXPECTED_YEARS:
        raise ValueError(
            f"Expected years {sorted(EXPECTED_YEARS)}, "
            f"found {sorted(set(florida['year']))}."
        )

    if florida.duplicated(["county_fips", "year"]).any():
        raise ValueError("Duplicate county_fips/year keys in Florida output.")

    if not florida["county_fips"].str.fullmatch(r"12\d{3}").all():
        raise ValueError("county_fips must match ^12\\d{3}$.")

    null_counts = florida[FLORIDA_COLUMNS].isna().sum()
    if null_counts.any():
        raise ValueError(
            "Null values in required Florida columns:\n"
            f"{null_counts[null_counts > 0]}"
        )

    if not pd.api.types.is_numeric_dtype(florida["median_household_income"]):
        raise ValueError("median_household_income is not numeric.")

    if not (florida["median_household_income"] > 0).all():
        raise ValueError("median_household_income must be greater than zero.")

    expected_labels = reference.set_index("county_fips")["county_name"].to_dict()
    actual_labels = (
        florida[["county_fips", "county_name"]]
        .drop_duplicates()
        .set_index("county_fips")["county_name"]
        .to_dict()
    )
    if actual_labels != expected_labels:
        raise ValueError(
            f"County labels do not match Florida reference: {actual_labels}"
        )

    expected_sources = florida["year"].map(lambda year: f"ACS {year} 5-year B19013")
    if not florida["income_source"].equals(expected_sources):
        raise ValueError("income_source values do not match the required pattern.")

    expected_order = florida.sort_values(["county_fips", "year"]).reset_index(drop=True)
    if not florida.reset_index(drop=True).equals(expected_order):
        raise ValueError("Florida output is not sorted by county_fips, then year.")

    for county_fips in sorted(florida_fips):
        county = florida[normalize_county_fips(florida["county_fips"]) == county_fips]
        if len(county) != len(EXPECTED_YEARS):
            raise ValueError(
                f"County FIPS {county_fips} has {len(county)} rows; "
                f"expected {len(EXPECTED_YEARS)}."
            )
        if set(county["year"]) != EXPECTED_YEARS:
            raise ValueError(
                f"County FIPS {county_fips} years must be exactly "
                f"{START_YEAR} through {END_YEAR}."
            )

    for year in sorted(EXPECTED_YEARS):
        year_rows = florida[florida["year"] == year]
        if len(year_rows) != EXPECTED_FL_COUNTIES:
            raise ValueError(
                f"Year {year} has {len(year_rows)} counties; "
                f"expected {EXPECTED_FL_COUNTIES}."
            )


def validate_miami_regression(florida: pd.DataFrame, legacy: pd.DataFrame) -> None:
    """Confirm Miami-Dade rows match between Florida and legacy outputs."""
    new_miami = (
        florida.loc[normalize_county_fips(florida["county_fips"]) == MIAMI_LEGACY_FIPS]
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


def validate_pipeline_subset_regression(
    florida: pd.DataFrame,
    committed_selected: pd.DataFrame,
) -> None:
    """Confirm pipeline counties match the committed selected-counties output."""
    florida_subset = (
        florida.loc[
            normalize_county_fips(florida["county_fips"]).isin(EXPECTED_PIPELINE_FIPS)
        ]
        .sort_values(["county_fips", "year"])
        .reset_index(drop=True)
    )

    pd.testing.assert_frame_equal(
        florida_subset[FLORIDA_COLUMNS],
        committed_selected[FLORIDA_COLUMNS],
        check_dtype=False,
    )


def verify_legacy_checksum() -> None:
    """Confirm the Miami legacy output matches the known committed checksum."""
    import hashlib

    digest = hashlib.md5(MIAMI_OUTPUT_PATH.read_bytes()).hexdigest()
    if digest != MIAMI_LEGACY_MD5:
        raise ValueError(
            f"Miami legacy MD5 {digest} does not match expected {MIAMI_LEGACY_MD5}."
        )


def main() -> None:
    """Fetch ACS income for Florida counties and write legacy and Florida outputs."""
    reference = load_florida_reference()
    expected_fips = set(normalize_county_fips(reference["county_fips"]))
    committed_selected = load_committed_selected_counties()
    api_key = load_census_api_key()

    records = []
    for year in YEARS:
        print(f"Fetching ACS income for {year}...")
        records.extend(fetch_florida_for_year(year, api_key, expected_fips))

    legacy = build_legacy_miami_output(records)
    florida = build_florida_output(records, reference)

    validate_florida_output(florida, reference)
    validate_miami_regression(florida, legacy)
    validate_pipeline_subset_regression(florida, committed_selected)

    MIAMI_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    FLORIDA_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    legacy.to_csv(MIAMI_OUTPUT_PATH, index=False)
    florida.to_csv(FLORIDA_OUTPUT_PATH, index=False)
    verify_legacy_checksum()

    print(
        f"[PASS] Florida reference counties: {EXPECTED_FL_COUNTIES} "
        f"({START_YEAR}-{END_YEAR})"
    )
    print(
        f"[PASS] annual response/FIPS coverage: {len(YEARS)} years, "
        f"{EXPECTED_FL_COUNTIES} counties per year"
    )
    print(
        f"[PASS] final county-year coverage: {len(florida)} rows, "
        f"10 per county, {START_YEAR}-{END_YEAR}"
    )
    print("[PASS] keys, nulls, FIPS, income values, and labels validated")
    print("[PASS] Miami-Dade regression comparison: Florida rows match legacy output")
    print(
        "[PASS] pipeline subset matches committed selected-counties output "
        f"({', '.join(sorted(EXPECTED_PIPELINE_FIPS))})"
    )
    print(f"[PASS] Miami legacy MD5 verified: {MIAMI_LEGACY_MD5}")
    print(f"[PASS] legacy output written: {MIAMI_OUTPUT_PATH}")
    print(f"[PASS] Florida output written: {FLORIDA_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
