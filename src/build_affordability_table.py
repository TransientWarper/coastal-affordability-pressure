"""
Build Coastal Affordability Pressure V0 table.

V0 scope:
- Miami-Dade County, Florida
- Years 2015-2024
- County-year grain
- Metric: typical_home_value / median_household_income
"""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MANUAL_DIR = DATA_DIR / "manual"

ZILLOW_PATH = PROCESSED_DIR / "zillow_zhvi_miami_dade_annual_2015_2024.csv"
ACS_PATH = RAW_DIR / "acs_income" / "acs_b19013_miami_dade_2015_2024.csv"
SELECTED_COUNTIES_PATH = MANUAL_DIR / "selected_counties.csv"
OUTPUT_PATH = PROCESSED_DIR / "coastal_affordability_county_v0.csv"

EXPECTED_YEARS = set(range(2015, 2025))
EXPECTED_ROW_COUNT = 10
EXPECTED_COUNTY_FIPS = "12086"

ZILLOW_REQUIRED_COLUMNS = [
    "state",
    "county_fips",
    "county_name",
    "year",
    "typical_home_value",
    "zillow_months_available",
    "home_value_source",
    "home_value_year_method",
]

ACS_REQUIRED_COLUMNS = [
    "year",
    "median_household_income",
    "county_fips",
    "source",
]

OUTPUT_COLUMNS = [
    "state",
    "county_fips",
    "county_name",
    "year",
    "median_household_income",
    "typical_home_value",
    "home_value_to_income_ratio",
    "income_source",
    "home_value_source",
    "home_value_year_method",
    "zillow_months_available",
    "notes",
]


def normalize_county_fips(series: pd.Series) -> pd.Series:
    """Convert county FIPS values to five-character strings."""
    return series.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)


def normalize_year(series: pd.Series) -> pd.Series:
    """Convert year values to integers."""
    return pd.to_numeric(series, errors="raise").astype(int)


def is_include_v0(value) -> bool:
    """Interpret include_v0 values as boolean true."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not pd.isna(value):
        return int(value) == 1
    return str(value).strip().lower() in {"true", "1", "yes", "t"}


def validate_selected_counties(df: pd.DataFrame) -> pd.Series:
    """Validate selected counties file and return the V0 county record."""
    if "include_v0" not in df.columns or "county_fips" not in df.columns:
        raise ValueError("selected_counties.csv is missing required columns.")

    df = df.copy()
    df["county_fips"] = normalize_county_fips(df["county_fips"])

    selected = df[df["include_v0"].map(is_include_v0)]
    if len(selected) != 1:
        raise ValueError(
            f"Expected exactly one selected V0 county, found {len(selected)}."
        )

    record = selected.iloc[0]
    if record["county_fips"] != EXPECTED_COUNTY_FIPS:
        raise ValueError(
            f"Expected selected county_fips '{EXPECTED_COUNTY_FIPS}', "
            f"found '{record['county_fips']}'."
        )

    return record


def require_columns(df: pd.DataFrame, required_columns: list[str], label: str) -> None:
    """Raise if required columns are missing."""
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def validate_analytical_input(
    df: pd.DataFrame,
    label: str,
    required_columns: list[str],
    value_checks: dict[str, callable],
) -> pd.DataFrame:
    """Validate one analytical input before joining."""
    require_columns(df, required_columns, label)

    normalized = df.copy()
    normalized["county_fips"] = normalize_county_fips(normalized["county_fips"])
    normalized["year"] = normalize_year(normalized["year"])

    if len(normalized) != EXPECTED_ROW_COUNT:
        raise ValueError(f"{label} must contain exactly {EXPECTED_ROW_COUNT} rows.")

    if set(normalized["year"]) != EXPECTED_YEARS:
        raise ValueError(
            f"{label} years must be exactly 2015 through 2024, "
            f"found {sorted(normalized['year'].unique().tolist())}."
        )

    if not (normalized["county_fips"] == EXPECTED_COUNTY_FIPS).all():
        raise ValueError(f"{label} county_fips must be '{EXPECTED_COUNTY_FIPS}' on every row.")

    duplicate_keys = int(normalized.duplicated(["county_fips", "year"]).sum())
    if duplicate_keys:
        raise ValueError(f"{label} contains {duplicate_keys} duplicate county-year keys.")

    null_counts = normalized[required_columns].isna().sum()
    if null_counts.any():
        raise ValueError(
            f"{label} contains nulls in required fields:\n{null_counts[null_counts > 0]}"
        )

    for column, check in value_checks.items():
        invalid = ~normalized[column].map(check)
        if invalid.any():
            raise ValueError(f"{label} contains invalid values in '{column}'.")

    return normalized


def validate_merge(
    merged: pd.DataFrame,
    zillow_count: int,
    acs_count: int,
) -> None:
    """Validate merged affordability table keys and row counts."""
    if len(merged) != EXPECTED_ROW_COUNT:
        raise ValueError(
            f"Merged result must contain exactly {EXPECTED_ROW_COUNT} rows, "
            f"found {len(merged)}."
        )

    if set(merged["year"]) != EXPECTED_YEARS:
        raise ValueError(
            "Merged result years must be exactly 2015 through 2024, "
            f"found {sorted(merged['year'].unique().tolist())}."
        )

    duplicate_keys = int(merged.duplicated(["county_fips", "year"]).sum())
    if duplicate_keys:
        raise ValueError(
            f"Merged result contains {duplicate_keys} duplicate county-year keys."
        )

    if len(merged) != zillow_count or len(merged) != acs_count:
        raise ValueError(
            "Not every Zillow and ACS row matched during the merge."
        )


def main() -> None:
    """Build the V0 affordability table."""
    selected_counties = pd.read_csv(SELECTED_COUNTIES_PATH)
    zillow = pd.read_csv(ZILLOW_PATH)
    acs = pd.read_csv(ACS_PATH)

    selected_county = validate_selected_counties(selected_counties)

    zillow = validate_analytical_input(
        zillow,
        "Zillow processed input",
        ZILLOW_REQUIRED_COLUMNS,
        {
            "typical_home_value": lambda value: value > 0,
            "zillow_months_available": lambda value: 1 <= value <= 12,
        },
    )
    acs = validate_analytical_input(
        acs,
        "ACS raw input",
        ACS_REQUIRED_COLUMNS,
        {
            "median_household_income": lambda value: value > 0,
        },
    )

    merged = zillow.merge(
        acs,
        on=["county_fips", "year"],
        how="inner",
        validate="one_to_one",
        indicator=True,
    )

    if not merged["_merge"].eq("both").all():
        unmatched = merged.loc[merged["_merge"] != "both", ["county_fips", "year", "_merge"]]
        raise ValueError(f"Merge produced unmatched rows:\n{unmatched}")

    merged = merged.drop(columns=["_merge"])
    validate_merge(merged, len(zillow), len(acs))

    notes = ""
    if "notes" in selected_county.index and pd.notna(selected_county["notes"]):
        notes = str(selected_county["notes"])

    final = pd.DataFrame(
        {
            "state": selected_county["state"],
            "county_fips": merged["county_fips"],
            "county_name": selected_county["county_name"],
            "year": merged["year"],
            "median_household_income": merged["median_household_income"],
            "typical_home_value": merged["typical_home_value"],
            "home_value_to_income_ratio": (
                merged["typical_home_value"] / merged["median_household_income"]
            ).round(4),
            "income_source": merged["source"],
            "home_value_source": merged["home_value_source"],
            "home_value_year_method": merged["home_value_year_method"],
            "zillow_months_available": merged["zillow_months_available"],
            "notes": notes,
        }
    )

    final = final[OUTPUT_COLUMNS]
    final["county_fips"] = normalize_county_fips(final["county_fips"])
    final = final.sort_values(["county_fips", "year"], ascending=True).reset_index(drop=True)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(OUTPUT_PATH, index=False)

    duplicate_county_year = int(final.duplicated(["county_fips", "year"]).sum())
    null_count = int(final.isna().sum().sum())

    print(f"Output path: {OUTPUT_PATH}")
    print(f"Row count: {len(final)}")
    print(f"Year range: {final['year'].min()}-{final['year'].max()}")
    print(f"County FIPS: {final['county_fips'].iloc[0]}")
    print(
        "home_value_to_income_ratio range: "
        f"{final['home_value_to_income_ratio'].min():.4f}-"
        f"{final['home_value_to_income_ratio'].max():.4f}"
    )
    print(f"Duplicate county-year count: {duplicate_county_year}")
    print(f"Null count: {null_count}")


if __name__ == "__main__":
    main()
