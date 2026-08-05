"""
Fetch ACS 5-year median household income for selected, Florida, and pipeline counties.

Inputs:
- data/manual/selected_counties.csv
- data/manual/florida_counties.csv
- data/manual/pipeline_states.csv
- data/manual/pipeline_counties.csv
- CENSUS_API_KEY in project-root .env

Outputs:
- data/raw/acs_income/acs_b19013_miami_dade_2015_2024.csv  (legacy Miami-Dade)
- data/processed/acs_b19013_florida_counties_2015_2024.csv  (statewide expansion)
- data/processed/acs_b19013_pipeline_counties_2015_2024.csv  (29-state expansion)
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
PIPELINE_STATES_PATH = PROJECT_ROOT / "data" / "manual" / "pipeline_states.csv"
PIPELINE_COUNTY_REFERENCE_PATH = (
    PROJECT_ROOT / "data" / "manual" / "pipeline_counties.csv"
)
PIPELINE_OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "acs_b19013_pipeline_counties_2015_2024.csv"
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
EXPECTED_PIPELINE_REF_COUNTIES = 2052
EXPECTED_PIPELINE_REF_ROWS = 20520
EXPECTED_PIPELINE_STATE_COUNTS = {
    "DE": 3,
    "FL": 67,
    "GA": 159,
    "IA": 99,
    "IL": 102,
    "IN": 92,
    "KS": 105,
    "KY": 120,
    "MA": 14,
    "MD": 24,
    "ME": 16,
    "MI": 83,
    "MN": 87,
    "MO": 115,
    "NC": 100,
    "ND": 53,
    "NE": 93,
    "NH": 10,
    "NJ": 21,
    "NY": 62,
    "OH": 88,
    "PA": 67,
    "RI": 5,
    "SC": 46,
    "SD": 66,
    "TN": 95,
    "VA": 133,
    "WI": 72,
    "WV": 55,
}
EXPECTED_ENABLED_STATES = {
    "DE",
    "FL",
    "GA",
    "IA",
    "IL",
    "IN",
    "KS",
    "KY",
    "MA",
    "MD",
    "ME",
    "MI",
    "MN",
    "MO",
    "ND",
    "NE",
    "NH",
    "NJ",
    "NY",
    "NC",
    "OH",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "VA",
    "WI",
    "WV",
}
EXPECTED_STATE_YEAR_REQUESTS = 290
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

PIPELINE_COLUMNS = FLORIDA_COLUMNS + ["acs_data_status"]

STATUS_AVAILABLE = "available"
STATUS_UNAVAILABLE = "source_data_unavailable"
APPROVED_PIPELINE_STATUSES = {STATUS_AVAILABLE, STATUS_UNAVAILABLE}

FLORIDA_REGRESSION_COLUMNS = [
    "state",
    "county_fips",
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


def pass_line(message: str) -> None:
    print(f"[PASS] {message}")


def parse_include_pipeline(value) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    raise ValueError(f"Unrecognized include_pipeline value: {value!r}")


def load_pipeline_states() -> pd.DataFrame:
    """Load and validate enabled states from the pipeline state manifest."""
    if not PIPELINE_STATES_PATH.exists():
        raise FileNotFoundError(f"Pipeline state manifest not found: {PIPELINE_STATES_PATH}")

    states = pd.read_csv(
        PIPELINE_STATES_PATH,
        dtype={"state": "string", "state_fips": "string"},
    )
    expected_columns = ["state", "state_fips", "include_pipeline"]
    if list(states.columns) != expected_columns:
        raise ValueError(
            f"Unexpected pipeline_states.csv columns: {list(states.columns)}"
        )

    states["state_fips"] = (
        states["state_fips"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(2)
    )
    enabled = states[states["include_pipeline"].map(parse_include_pipeline)].copy()

    if set(enabled["state"]) != EXPECTED_ENABLED_STATES:
        raise ValueError(
            f"Enabled states must be {sorted(EXPECTED_ENABLED_STATES)}; "
            f"found {sorted(enabled['state'])}."
        )

    pass_line(f"enabled states loaded: {', '.join(sorted(enabled['state']))}")
    return enabled.sort_values("state_fips").reset_index(drop=True)


def load_pipeline_county_reference() -> pd.DataFrame:
    """Load and validate the 29-state pipeline county reference."""
    if not PIPELINE_COUNTY_REFERENCE_PATH.exists():
        raise FileNotFoundError(
            f"Pipeline county reference not found: {PIPELINE_COUNTY_REFERENCE_PATH}"
        )

    reference = pd.read_csv(
        PIPELINE_COUNTY_REFERENCE_PATH,
        dtype={
            "state": "string",
            "state_fips": "string",
            "county_fips": "string",
            "county_name": "string",
        },
    )
    expected_columns = ["state", "state_fips", "county_fips", "county_name"]
    if list(reference.columns) != expected_columns:
        raise ValueError(
            f"Unexpected pipeline_counties.csv columns: {list(reference.columns)}"
        )

    reference["county_fips"] = normalize_county_fips(reference["county_fips"])
    reference["state_fips"] = (
        reference["state_fips"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(2)
    )

    if len(reference) != EXPECTED_PIPELINE_REF_COUNTIES:
        raise ValueError(
            f"Expected exactly {EXPECTED_PIPELINE_REF_COUNTIES} pipeline reference counties, "
            f"found {len(reference)}."
        )

    if reference["county_fips"].nunique() != EXPECTED_PIPELINE_REF_COUNTIES:
        raise ValueError(
            f"Expected {EXPECTED_PIPELINE_REF_COUNTIES} unique county_fips values, "
            f"found {reference['county_fips'].nunique()}."
        )

    state_counts = reference.groupby("state").size().to_dict()
    if state_counts != EXPECTED_PIPELINE_STATE_COUNTS:
        raise ValueError(
            f"Unexpected pipeline county counts by state: {state_counts}; "
            f"expected {EXPECTED_PIPELINE_STATE_COUNTS}."
        )

    pass_line(f"pipeline reference loaded: {EXPECTED_PIPELINE_REF_COUNTIES} counties")
    return reference.sort_values(["state_fips", "county_fips"]).reset_index(drop=True)


def parse_pipeline_income_value(
    raw_value,
    year: int,
    county_fips: str,
) -> tuple[int | None, str]:
    """Parse B19013_001E for pipeline output, retaining unavailable county-years."""
    if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
        return None, STATUS_UNAVAILABLE

    text = str(raw_value).strip().replace(",", "")
    try:
        income = int(text)
    except ValueError:
        return None, STATUS_UNAVAILABLE

    if income in INCOME_SUPPRESSION_SENTINELS or income <= 0:
        return None, STATUS_UNAVAILABLE

    return income, STATUS_AVAILABLE


def fetch_pipeline_state_for_year(
    year: int,
    state_fips: str,
    state_abbr: str,
    api_key: str,
    expected_fips: set[str],
) -> tuple[list[dict], int]:
    """Fetch ACS income for one state-year and retain unavailable county-years."""
    url = f"https://api.census.gov/data/{year}/acs/acs5"
    params = {
        "get": "NAME,B19013_001E",
        "for": "county:*",
        "in": f"state:{state_fips}",
        "key": api_key,
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    rows = response.json()
    if not rows or not isinstance(rows, list):
        raise ValueError(
            f"Unexpected ACS response for {state_abbr} {year}: empty or non-list payload."
        )

    header = rows[0]
    if not isinstance(header, list):
        raise ValueError(f"Unexpected ACS header for {state_abbr} {year}: {header!r}")

    missing_fields = REQUIRED_API_FIELDS - set(header)
    if missing_fields:
        raise ValueError(
            f"ACS response for {state_abbr} {year} missing required fields: "
            f"{sorted(missing_fields)}"
        )

    data_rows = rows[1:]
    records = []
    for values in data_rows:
        record = dict(zip(header, values))
        response_state_fips = str(record["state"]).zfill(2)
        if response_state_fips != str(state_fips).zfill(2):
            raise ValueError(
                f"ACS response for {state_abbr} {year} includes state "
                f"{response_state_fips}; expected {state_fips}."
            )

        county_fips = response_state_fips + str(record["county"]).zfill(3)
        if county_fips not in expected_fips:
            raise ValueError(
                f"ACS response for {state_abbr} {year} returned unexpected county FIPS "
                f"{county_fips}."
            )

        income, status = parse_pipeline_income_value(
            record["B19013_001E"],
            year,
            county_fips,
        )
        records.append(
            {
                "county_fips": county_fips,
                "year": year,
                "median_household_income": income,
                "income_source": f"ACS {year} 5-year B19013",
                "acs_data_status": status,
            }
        )

    returned_fips = [record["county_fips"] for record in records]
    if len(returned_fips) != len(set(returned_fips)):
        raise ValueError(
            f"Duplicate county FIPS values in ACS response for {state_abbr} {year}."
        )

    return records, len(data_rows)


def florida_records_to_pipeline_records(records: list[dict]) -> list[dict]:
    """Convert strict Florida acquisition records to pipeline ACS records."""
    return [
        {
            "county_fips": record["county_fips"],
            "year": record["year"],
            "median_household_income": record["median_household_income"],
            "income_source": record["source"],
            "acs_data_status": STATUS_AVAILABLE,
        }
        for record in records
    ]


def build_pipeline_output(
    reference: pd.DataFrame,
    acs_records: list[dict],
) -> pd.DataFrame:
    """Build the 29-state pipeline ACS panel from reference and parsed responses."""
    years = pd.DataFrame({"year": YEARS})
    skeleton = reference.merge(years, how="cross")

    acs_df = pd.DataFrame(acs_records)
    acs_df["county_fips"] = normalize_county_fips(acs_df["county_fips"])

    merged = skeleton.merge(
        acs_df,
        on=["county_fips", "year"],
        how="left",
        validate="one_to_one",
    )

    merged["income_source"] = merged["year"].map(lambda year: f"ACS {year} 5-year B19013")
    merged.loc[merged["acs_data_status"].isna(), "acs_data_status"] = STATUS_UNAVAILABLE

    output = pd.DataFrame(
        {
            "state": merged["state"],
            "county_fips": merged["county_fips"],
            "county_name": merged["county_name"],
            "year": merged["year"],
            "median_household_income": merged["median_household_income"],
            "income_source": merged["income_source"],
            "acs_data_status": merged["acs_data_status"],
        }
    )
    output["county_fips"] = normalize_county_fips(output["county_fips"])
    return output[PIPELINE_COLUMNS].sort_values(["county_fips", "year"]).reset_index(drop=True)


def load_committed_florida_counties() -> pd.DataFrame:
    """Load the committed Florida ACS output for regression comparison."""
    if not FLORIDA_OUTPUT_PATH.exists():
        raise FileNotFoundError(
            f"Committed Florida ACS output not found: {FLORIDA_OUTPUT_PATH}"
        )

    committed = pd.read_csv(
        FLORIDA_OUTPUT_PATH,
        dtype={"county_fips": "string"},
    )
    committed["county_fips"] = normalize_county_fips(committed["county_fips"])
    return committed.sort_values(["county_fips", "year"]).reset_index(drop=True)


def compare_pipeline_florida_county_names(
    pipeline_reference: pd.DataFrame,
    committed_florida: pd.DataFrame,
) -> list[tuple[str, str, str]]:
    """Report Florida county-name label differences between references."""
    pipeline_fl = (
        pipeline_reference.loc[pipeline_reference["state"] == "FL", ["county_fips", "county_name"]]
        .drop_duplicates()
        .set_index("county_fips")["county_name"]
    )
    committed_fl = (
        committed_florida[["county_fips", "county_name"]]
        .drop_duplicates()
        .set_index("county_fips")["county_name"]
    )
    differences = []
    for county_fips in sorted(set(pipeline_fl.index) & set(committed_fl.index)):
        pipeline_name = pipeline_fl.loc[county_fips]
        committed_name = committed_fl.loc[county_fips]
        if pipeline_name != committed_name:
            differences.append((county_fips, committed_name, pipeline_name))
    return differences


def validate_pipeline_florida_regression(
    pipeline: pd.DataFrame,
    committed_florida: pd.DataFrame,
) -> None:
    """Confirm Florida subset matches committed Florida ACS output."""
    pipeline_fl = (
        pipeline.loc[pipeline["state"] == "FL"]
        .sort_values(["county_fips", "year"])
        .reset_index(drop=True)
    )
    committed_fl = committed_florida.sort_values(["county_fips", "year"]).reset_index(drop=True)

    if len(pipeline_fl) != EXPECTED_FL_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_FL_ROWS} Florida rows in pipeline ACS output, "
            f"found {len(pipeline_fl)}."
        )

    pd.testing.assert_frame_equal(
        pipeline_fl[FLORIDA_REGRESSION_COLUMNS],
        committed_fl[FLORIDA_REGRESSION_COLUMNS],
        check_dtype=False,
    )

    pass_line("Florida analytical regression passes")


def validate_pipeline_output(
    pipeline: pd.DataFrame,
    reference: pd.DataFrame,
) -> None:
    """Validate the 29-state pipeline ACS output before write."""
    if list(pipeline.columns) != PIPELINE_COLUMNS:
        raise ValueError(f"Unexpected pipeline output columns: {list(pipeline.columns)}")

    if len(pipeline) != EXPECTED_PIPELINE_REF_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_PIPELINE_REF_ROWS} pipeline county-year rows, "
            f"found {len(pipeline)}."
        )

    pass_line(f"final panel contains {EXPECTED_PIPELINE_REF_ROWS} rows")

    if not pipeline.groupby("county_fips").size().eq(len(YEARS)).all():
        raise ValueError("Each pipeline county must have exactly 10 rows.")

    pass_line("every county has 10 rows")

    if not pipeline.groupby("year").size().eq(EXPECTED_PIPELINE_REF_COUNTIES).all():
        raise ValueError("Each year must have exactly 2052 county rows.")

    pass_line("every year has 2052 rows")

    state_year_counts = pipeline.groupby("state").size().to_dict()
    expected_state_year_counts = {
        state: count * len(YEARS)
        for state, count in EXPECTED_PIPELINE_STATE_COUNTS.items()
    }
    if state_year_counts != expected_state_year_counts:
        raise ValueError(
            f"Unexpected pipeline state row counts: {state_year_counts}; "
            f"expected {expected_state_year_counts}."
        )

    pass_line("every state has its expected annual county count")

    if set(pipeline["year"]) != EXPECTED_YEARS:
        raise ValueError(
            f"Expected years {sorted(EXPECTED_YEARS)}, "
            f"found {sorted(set(pipeline['year']))}."
        )

    pass_line(f"years exactly {START_YEAR}-{END_YEAR}")

    if pipeline.duplicated(["county_fips", "year"]).any():
        raise ValueError("Duplicate county_fips/year keys in pipeline output.")

    pass_line("unique key: county_fips + year")

    if not pipeline["county_fips"].str.fullmatch(r"\d{5}").all():
        raise ValueError("county_fips values must be exactly five digits.")

    pass_line("county_fips values exactly five digits")

    required_non_null = ["state", "county_fips", "county_name", "year"]
    if pipeline[required_non_null].isna().any().any():
        raise ValueError("Null values found in required pipeline label columns.")

    pass_line("no null state, county_fips, county_name, or year")

    non_null = pipeline["median_household_income"].dropna()
    if not non_null.gt(0).all():
        raise ValueError("median_household_income must be positive where non-null.")

    pass_line("median household income positive where non-null")

    available = pipeline["acs_data_status"] == STATUS_AVAILABLE
    unavailable = pipeline["acs_data_status"] == STATUS_UNAVAILABLE

    if not pipeline.loc[available, "median_household_income"].notna().all():
        raise ValueError("available rows must have non-null median_household_income.")

    pass_line("available rows have non-null income")

    if not pipeline.loc[unavailable, "median_household_income"].isna().all():
        raise ValueError("source_data_unavailable rows must have null income.")

    pass_line("source_data_unavailable rows have null income")

    if not set(pipeline["acs_data_status"]).issubset(APPROVED_PIPELINE_STATUSES):
        raise ValueError("Pipeline output contains unapproved acs_data_status values.")

    pass_line("status values belong to the approved set")

    reference_labels = reference.set_index("county_fips")[["state", "county_name"]]
    output_labels = (
        pipeline.drop_duplicates("county_fips")
        .set_index("county_fips")[["state", "county_name"]]
    )
    if not output_labels.equals(reference_labels):
        raise ValueError(
            "Pipeline output state and county names must match pipeline_counties.csv."
        )

    pass_line("labels match pipeline_counties.csv")


def print_pipeline_coverage_summary(
    reference: pd.DataFrame,
    response_counts: list[tuple[str, int, int]],
    pipeline: pd.DataFrame,
    acs_records: list[dict],
    name_differences: list[tuple[str, str, str]],
) -> None:
    """Print ACS acquisition coverage and status summary for the pipeline output."""
    print("\nPipeline ACS coverage summary:")
    print("  response row count by state-year:")
    for state_abbr, year, row_count in response_counts:
        print(f"    {state_abbr} {year}: {row_count}")

    print("  counties returned by state and year:")
    acs_df = pd.DataFrame(acs_records)
    if not acs_df.empty:
        ref_index = reference.set_index("county_fips")["state"].to_dict()
        acs_df["county_fips"] = normalize_county_fips(acs_df["county_fips"])
        acs_df["state"] = acs_df["county_fips"].map(ref_index)
        for (state_abbr, year), group in acs_df.groupby(["state", "year"]):
            print(f"    {state_abbr} {year}: {len(group)}")

    years = pd.DataFrame({"year": YEARS})
    skeleton = reference.merge(years, how="cross")
    skeleton_keys = set(zip(skeleton["county_fips"], skeleton["year"]))
    acs_keys = {
        (normalize_county_fips(pd.Series([record["county_fips"]])).iloc[0], record["year"])
        for record in acs_records
    }
    absent_keys = sorted(skeleton_keys - acs_keys)
    print(f"  reference county-years absent from ACS response: {len(absent_keys)}")
    if absent_keys:
        for county_fips, year in absent_keys:
            county = reference.loc[reference["county_fips"] == county_fips].iloc[0]
            print(
                f"    {county['state']} {county_fips} {county['county_name']} {year}"
            )

    unavailable_rows = pipeline.loc[
        pipeline["acs_data_status"] == STATUS_UNAVAILABLE
    ].sort_values(["county_fips", "year"])
    print(
        "  county-years with suppressed, malformed, or missing income values: "
        f"{len(unavailable_rows)}"
    )
    for _, row in unavailable_rows.iterrows():
        print(
            f"    {row['state']} {row['county_fips']} {row['county_name']} "
            f"{int(row['year'])}"
        )

    print("  acs_data_status distribution:")
    for status, count in pipeline["acs_data_status"].value_counts().sort_index().items():
        print(f"    {status}: {count}")

    null_count = int(pipeline["median_household_income"].isna().sum())
    print(f"  null median-household-income count: {null_count}")

    non_null = pipeline["median_household_income"].dropna()
    print(
        "  non-null median household income range: "
        f"{int(non_null.min())} to {int(non_null.max())}"
    )

    if name_differences:
        print("  Census/TIGER county-name differences (Florida committed vs pipeline):")
        for county_fips, committed_name, pipeline_name in name_differences:
            print(
                f"    {county_fips}: committed={committed_name!r}; "
                f"pipeline={pipeline_name!r}"
            )
    else:
        print("  Census/TIGER county-name differences: none")

    print(f"  output path: {PIPELINE_OUTPUT_PATH}")


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

    pipeline_states = load_pipeline_states()
    pipeline_reference = load_pipeline_county_reference()
    pipeline_records = florida_records_to_pipeline_records(records)
    response_counts: list[tuple[str, int, int]] = []

    non_fl_states = pipeline_states[pipeline_states["state"] != "FL"]
    for _, state_row in non_fl_states.iterrows():
        state_abbr = state_row["state"]
        state_fips = state_row["state_fips"]
        expected_state_fips = set(
            pipeline_reference.loc[
                pipeline_reference["state"] == state_abbr, "county_fips"
            ]
        )
        for year in YEARS:
            print(f"Fetching ACS income for {state_abbr} {year}...")
            state_records, row_count = fetch_pipeline_state_for_year(
                year,
                state_fips,
                state_abbr,
                api_key,
                expected_state_fips,
            )
            pipeline_records.extend(state_records)
            response_counts.append((state_abbr, year, row_count))

    for year in YEARS:
        response_counts.append(("FL", year, EXPECTED_FL_COUNTIES))

    pass_line(f"{EXPECTED_STATE_YEAR_REQUESTS} state-year ACS responses completed")
    pass_line("each response contains only the requested state")
    pass_line("response county FIPS values are unique")
    pass_line("returned counties are all present in pipeline_counties.csv")

    pipeline = build_pipeline_output(pipeline_reference, pipeline_records)
    validate_pipeline_output(pipeline, pipeline_reference)

    committed_florida = load_committed_florida_counties()
    validate_pipeline_florida_regression(pipeline, committed_florida)
    validate_miami_regression(florida, legacy)
    validate_pipeline_subset_regression(florida, committed_selected)

    pass_line("existing Miami-Dade regression checks still pass")
    pass_line("existing selected-county regression checks still pass")

    name_differences = compare_pipeline_florida_county_names(
        pipeline_reference,
        committed_florida,
    )
    print_pipeline_coverage_summary(
        pipeline_reference,
        sorted(response_counts, key=lambda item: (item[0], item[1])),
        pipeline,
        pipeline_records,
        name_differences,
    )

    PIPELINE_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pipeline.to_csv(PIPELINE_OUTPUT_PATH, index=False)
    pass_line(f"pipeline output path written ({PIPELINE_OUTPUT_PATH})")


if __name__ == "__main__":
    main()
