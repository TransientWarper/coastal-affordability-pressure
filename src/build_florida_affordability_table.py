"""
Build statewide Florida coastal affordability table.

Joins validated 670-row Zillow and ACS county-year outputs for all Florida
counties, 2015-2024.
"""

from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
MANUAL_DIR = PROJECT_ROOT / "data" / "manual"

ZILLOW_PATH = PROCESSED_DIR / "zillow_zhvi_florida_counties_annual_2015_2024.csv"
ACS_PATH = PROCESSED_DIR / "acs_b19013_florida_counties_2015_2024.csv"
REFERENCE_PATH = MANUAL_DIR / "florida_counties.csv"
V0_OUTPUT_PATH = PROCESSED_DIR / "coastal_affordability_county_v0.csv"
OUTPUT_PATH = PROCESSED_DIR / "coastal_affordability_florida_2015_2024.csv"

START_YEAR = 2015
END_YEAR = 2024
EXPECTED_YEARS = set(range(START_YEAR, END_YEAR + 1))
EXPECTED_FL_COUNTIES = 67
EXPECTED_FL_ROWS = 670
EXPECTED_PIPELINE_FIPS = {"12011", "12086", "12099"}

MONROE_EXCEPTION_FIPS = "12087"
MONROE_EXCEPTION_YEAR = 2015

STATUS_COMPLETE = "complete_12_months"
STATUS_PARTIAL = "partial_10_11_months"
STATUS_UNAVAILABLE = "source_data_unavailable"

ZILLOW_REQUIRED_COLUMNS = [
    "state",
    "county_fips",
    "county_name",
    "year",
    "typical_home_value",
    "zillow_months_available",
    "home_value_source",
    "home_value_year_method",
    "zillow_data_status",
]

ACS_REQUIRED_COLUMNS = [
    "state",
    "county_fips",
    "county_name",
    "year",
    "median_household_income",
    "income_source",
]

OUTPUT_COLUMNS = [
    "state",
    "county_fips",
    "county_name",
    "year",
    "typical_home_value",
    "median_household_income",
    "home_value_to_income_ratio",
    "zillow_months_available",
    "zillow_data_status",
    "home_value_source",
    "home_value_year_method",
    "income_source",
]

V0_COMPARABLE_COLUMNS = [
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
]


def normalize_county_fips(series: pd.Series) -> pd.Series:
    """Convert county FIPS values to five-character strings."""
    return series.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)


def normalize_year(series: pd.Series) -> pd.Series:
    """Convert year values to integers."""
    return pd.to_numeric(series, errors="raise").astype(int)


def county_year_keys(df: pd.DataFrame) -> set[tuple[str, int]]:
    """Return normalized county-year keys from a dataframe."""
    normalized = df.copy()
    normalized["county_fips"] = normalize_county_fips(normalized["county_fips"])
    normalized["year"] = normalize_year(normalized["year"])
    return set(zip(normalized["county_fips"], normalized["year"], strict=False))


def load_florida_reference() -> pd.DataFrame:
    """Load and validate the authoritative Florida county reference."""
    reference = pd.read_csv(
        REFERENCE_PATH,
        dtype={"county_fips": "string", "county_name": "string", "state": "string"},
    )
    reference["county_fips"] = normalize_county_fips(reference["county_fips"])

    if list(reference.columns) != ["state", "county_fips", "county_name"]:
        raise ValueError(
            f"Unexpected florida_counties.csv columns: {list(reference.columns)}"
        )
    if len(reference) != EXPECTED_FL_COUNTIES:
        raise ValueError(
            f"Expected {EXPECTED_FL_COUNTIES} Florida reference rows, found {len(reference)}."
        )
    if reference["county_fips"].nunique() != EXPECTED_FL_COUNTIES:
        raise ValueError("Florida reference must contain 67 unique county_fips values.")
    if not reference["state"].eq("FL").all():
        raise ValueError("Florida reference state values must all be FL.")
    if not reference["county_fips"].str.fullmatch(r"12\d{3}").all():
        raise ValueError("Florida reference county_fips must match ^12\\d{3}$.")

    return reference.sort_values("county_fips").reset_index(drop=True)


def validate_zillow_input(zillow: pd.DataFrame, expected_keys: set[tuple[str, int]]) -> pd.DataFrame:
    """Validate Florida Zillow input before joining."""
    missing_columns = [col for col in ZILLOW_REQUIRED_COLUMNS if col not in zillow.columns]
    if missing_columns:
        raise ValueError(f"Zillow input missing required columns: {missing_columns}")

    df = zillow.copy()
    df["county_fips"] = normalize_county_fips(df["county_fips"])
    df["year"] = normalize_year(df["year"])

    if len(df) != EXPECTED_FL_ROWS:
        raise ValueError(f"Zillow input must contain exactly {EXPECTED_FL_ROWS} rows.")
    if df["county_fips"].nunique() != EXPECTED_FL_COUNTIES:
        raise ValueError("Zillow input must contain exactly 67 unique county_fips values.")
    if set(df["year"]) != EXPECTED_YEARS:
        raise ValueError("Zillow input years must be exactly 2015 through 2024.")
    if df.duplicated(["county_fips", "year"]).any():
        raise ValueError("Zillow input contains duplicate county-year keys.")
    if county_year_keys(df) != expected_keys:
        raise ValueError("Zillow input county-year keys do not match the expected Florida panel.")
    if not df["county_fips"].str.fullmatch(r"12\d{3}").all():
        raise ValueError("Zillow input county_fips must match ^12\\d{3}$.")

    null_home = df[df["typical_home_value"].isna()]
    if len(null_home) != 1:
        raise ValueError(
            f"Zillow input must contain exactly one null typical_home_value row, "
            f"found {len(null_home)}."
        )
    null_row = null_home.iloc[0]
    if not (
        null_row["county_fips"] == MONROE_EXCEPTION_FIPS
        and int(null_row["year"]) == MONROE_EXCEPTION_YEAR
    ):
        raise ValueError(
            "Null typical_home_value is only permitted for Monroe County 2015."
        )

    valid_home = df["typical_home_value"].dropna()
    if not (valid_home > 0).all():
        raise ValueError("Non-null typical_home_value values must be greater than zero.")

    status_counts = df["zillow_data_status"].value_counts().to_dict()
    expected_status_counts = {
        STATUS_COMPLETE: 668,
        STATUS_PARTIAL: 1,
        STATUS_UNAVAILABLE: 1,
    }
    if status_counts != expected_status_counts:
        raise ValueError(
            f"Unexpected zillow_data_status counts: {status_counts}; "
            f"expected {expected_status_counts}."
        )

    required_non_null = [
        "state",
        "county_fips",
        "county_name",
        "year",
        "zillow_months_available",
        "zillow_data_status",
        "home_value_source",
        "home_value_year_method",
    ]
    null_counts = df[required_non_null].isna().sum()
    if null_counts.any():
        raise ValueError(
            "Zillow input contains nulls in required non-value fields:\n"
            f"{null_counts[null_counts > 0]}"
        )

    return df.sort_values(["county_fips", "year"]).reset_index(drop=True)


def validate_acs_input(acs: pd.DataFrame, expected_keys: set[tuple[str, int]]) -> pd.DataFrame:
    """Validate Florida ACS input before joining."""
    missing_columns = [col for col in ACS_REQUIRED_COLUMNS if col not in acs.columns]
    if missing_columns:
        raise ValueError(f"ACS input missing required columns: {missing_columns}")

    df = acs.copy()
    df["county_fips"] = normalize_county_fips(df["county_fips"])
    df["year"] = normalize_year(df["year"])

    if len(df) != EXPECTED_FL_ROWS:
        raise ValueError(f"ACS input must contain exactly {EXPECTED_FL_ROWS} rows.")
    if df["county_fips"].nunique() != EXPECTED_FL_COUNTIES:
        raise ValueError("ACS input must contain exactly 67 unique county_fips values.")
    if set(df["year"]) != EXPECTED_YEARS:
        raise ValueError("ACS input years must be exactly 2015 through 2024.")
    if df.duplicated(["county_fips", "year"]).any():
        raise ValueError("ACS input contains duplicate county-year keys.")
    if county_year_keys(df) != expected_keys:
        raise ValueError("ACS input county-year keys do not match the expected Florida panel.")
    if not df["county_fips"].str.fullmatch(r"12\d{3}").all():
        raise ValueError("ACS input county_fips must match ^12\\d{3}$.")

    null_counts = df[ACS_REQUIRED_COLUMNS].isna().sum()
    if null_counts.any():
        raise ValueError(
            "ACS input contains nulls in required fields:\n"
            f"{null_counts[null_counts > 0]}"
        )
    if not (df["median_household_income"] > 0).all():
        raise ValueError("median_household_income must be greater than zero.")

    return df.sort_values(["county_fips", "year"]).reset_index(drop=True)


def build_expected_keys(reference: pd.DataFrame) -> set[tuple[str, int]]:
    """Build the complete Florida county-year key set from the reference."""
    keys = {
        (fips, year)
        for fips in normalize_county_fips(reference["county_fips"])
        for year in EXPECTED_YEARS
    }
    if len(keys) != EXPECTED_FL_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_FL_ROWS} county-year keys from reference, found {len(keys)}."
        )
    return keys


def calculate_ratio(home_value: pd.Series, income: pd.Series) -> pd.Series:
    """Calculate home value-to-income ratio, leaving null when home value is null."""
    ratio = home_value / income
    ratio = ratio.where(home_value.notna())
    return ratio.round(4)


def validate_output(final: pd.DataFrame, expected_keys: set[tuple[str, int]]) -> None:
    """Validate the final Florida affordability table."""
    if list(final.columns) != OUTPUT_COLUMNS:
        raise ValueError(f"Unexpected output columns: {list(final.columns)}")
    if len(final) != EXPECTED_FL_ROWS:
        raise ValueError(f"Final output must contain exactly {EXPECTED_FL_ROWS} rows.")
    if final["county_fips"].nunique() != EXPECTED_FL_COUNTIES:
        raise ValueError("Final output must contain exactly 67 unique county_fips values.")
    if set(final["year"]) != EXPECTED_YEARS:
        raise ValueError("Final output years must be exactly 2015 through 2024.")
    if final.duplicated(["county_fips", "year"]).any():
        raise ValueError("Final output contains duplicate county-year keys.")
    if county_year_keys(final) != expected_keys:
        raise ValueError("Final output is missing expected county-year keys.")
    if not final["county_fips"].str.fullmatch(r"12\d{3}").all():
        raise ValueError("Final output county_fips must match ^12\\d{3}$.")
    if not (final.groupby("county_fips").size() == 10).all():
        raise ValueError("Final output must contain exactly 10 rows per county.")
    if not (final.groupby("year").size() == EXPECTED_FL_COUNTIES).all():
        raise ValueError("Final output must contain exactly 67 rows per year.")

    if not final["median_household_income"].notna().all():
        raise ValueError("median_household_income must be populated for all rows.")

    home_nulls = final[final["typical_home_value"].isna()]
    ratio_nulls = final[final["home_value_to_income_ratio"].isna()]
    if len(home_nulls) != 1 or len(ratio_nulls) != 1:
        raise ValueError(
            "Final output must contain exactly one null typical_home_value and one "
            "null home_value_to_income_ratio."
        )
    for missing in (home_nulls.iloc[0], ratio_nulls.iloc[0]):
        if not (
            missing["county_fips"] == MONROE_EXCEPTION_FIPS
            and int(missing["year"]) == MONROE_EXCEPTION_YEAR
        ):
            raise ValueError(
                "Null home value and ratio are only permitted for Monroe County 2015."
            )

    required_non_null = [
        "state",
        "county_fips",
        "county_name",
        "year",
        "median_household_income",
        "zillow_months_available",
        "zillow_data_status",
        "home_value_source",
        "home_value_year_method",
        "income_source",
    ]
    null_counts = final[required_non_null].isna().sum()
    if null_counts.any():
        raise ValueError(
            "Final output contains nulls in required non-ratio fields:\n"
            f"{null_counts[null_counts > 0]}"
        )

    valid_home = final["typical_home_value"].dropna()
    valid_ratio = final["home_value_to_income_ratio"].dropna()
    if not (valid_home > 0).all():
        raise ValueError("Non-null typical_home_value values must be greater than zero.")
    if not (final["median_household_income"] > 0).all():
        raise ValueError("median_household_income must be greater than zero.")
    if not (valid_ratio > 0).all():
        raise ValueError("Non-null home_value_to_income_ratio values must be greater than zero.")
    if not np.isfinite(valid_ratio).all():
        raise ValueError("home_value_to_income_ratio must be finite.")

    status_counts = final["zillow_data_status"].value_counts().to_dict()
    expected_status_counts = {
        STATUS_COMPLETE: 668,
        STATUS_PARTIAL: 1,
        STATUS_UNAVAILABLE: 1,
    }
    if status_counts != expected_status_counts:
        raise ValueError(
            f"Unexpected zillow_data_status counts: {status_counts}; "
            f"expected {expected_status_counts}."
        )

    unavailable = final[final["zillow_data_status"] == STATUS_UNAVAILABLE].iloc[0]
    if not (
        unavailable["county_fips"] == MONROE_EXCEPTION_FIPS
        and int(unavailable["year"]) == MONROE_EXCEPTION_YEAR
    ):
        raise ValueError("source_data_unavailable must be Monroe County 2015 only.")

    partial = final[final["zillow_data_status"] == STATUS_PARTIAL].iloc[0]
    if not (
        partial["county_fips"] == MONROE_EXCEPTION_FIPS
        and int(partial["year"]) == MONROE_EXCEPTION_YEAR + 1
    ):
        raise ValueError("partial_10_11_months must be Monroe County 2016 only.")


def validate_miami_v0_regression(final: pd.DataFrame) -> None:
    """Compare Miami-Dade rows against the existing V0 affordability output."""
    if not V0_OUTPUT_PATH.exists():
        raise FileNotFoundError(f"V0 output not found: {V0_OUTPUT_PATH}")

    v0 = pd.read_csv(V0_OUTPUT_PATH, dtype={"county_fips": "string"})
    v0["county_fips"] = normalize_county_fips(v0["county_fips"])

    florida_miami = (
        final.loc[normalize_county_fips(final["county_fips"]) == "12086"]
        .sort_values("year")
        .reset_index(drop=True)
    )
    v0_miami = v0.sort_values("year").reset_index(drop=True)

    pd.testing.assert_frame_equal(
        florida_miami[V0_COMPARABLE_COLUMNS],
        v0_miami[V0_COMPARABLE_COLUMNS],
        check_dtype=False,
        check_exact=False,
        rtol=1e-12,
        atol=1e-9,
    )


def validate_pipeline_direct_join(final: pd.DataFrame, zillow: pd.DataFrame, acs: pd.DataFrame) -> None:
    """Confirm pipeline counties match a direct Zillow-ACS join."""
    z = zillow.loc[zillow["county_fips"].isin(EXPECTED_PIPELINE_FIPS)].copy()
    a = acs.loc[acs["county_fips"].isin(EXPECTED_PIPELINE_FIPS)].copy()

    direct = z.merge(
        a,
        on=["county_fips", "year"],
        how="inner",
        validate="one_to_one",
        suffixes=("_zillow", "_acs"),
    )

    reference = load_florida_reference().set_index("county_fips")
    direct_final = pd.DataFrame(
        {
            "state": direct["county_fips"].map(reference["state"]),
            "county_fips": direct["county_fips"],
            "county_name": direct["county_fips"].map(reference["county_name"]),
            "year": direct["year"],
            "typical_home_value": direct["typical_home_value"],
            "median_household_income": direct["median_household_income"],
            "home_value_to_income_ratio": calculate_ratio(
                direct["typical_home_value"],
                direct["median_household_income"],
            ),
            "zillow_months_available": direct["zillow_months_available"],
            "zillow_data_status": direct["zillow_data_status"],
            "home_value_source": direct["home_value_source"],
            "home_value_year_method": direct["home_value_year_method"],
            "income_source": direct["income_source"],
        }
    ).sort_values(["county_fips", "year"]).reset_index(drop=True)

    pipeline_subset = (
        final.loc[final["county_fips"].isin(EXPECTED_PIPELINE_FIPS)]
        .sort_values(["county_fips", "year"])
        .reset_index(drop=True)
    )

    pd.testing.assert_frame_equal(
        pipeline_subset[OUTPUT_COLUMNS],
        direct_final[OUTPUT_COLUMNS],
        check_dtype=False,
    )


def main() -> None:
    """Build the statewide Florida affordability table."""
    reference = load_florida_reference()
    expected_keys = build_expected_keys(reference)

    zillow = validate_zillow_input(pd.read_csv(ZILLOW_PATH), expected_keys)
    acs = validate_acs_input(pd.read_csv(ACS_PATH), expected_keys)

    if county_year_keys(zillow) != county_year_keys(acs):
        raise ValueError("Zillow and ACS inputs do not contain identical county-year keys.")

    merged = zillow.merge(
        acs[["county_fips", "year", "median_household_income", "income_source"]],
        on=["county_fips", "year"],
        how="inner",
        validate="one_to_one",
    )

    if len(merged) != EXPECTED_FL_ROWS:
        raise ValueError(
            f"Merge must produce exactly {EXPECTED_FL_ROWS} rows, found {len(merged)}."
        )

    reference_index = reference.set_index("county_fips")
    final = pd.DataFrame(
        {
            "state": merged["county_fips"].map(reference_index["state"]),
            "county_fips": merged["county_fips"],
            "county_name": merged["county_fips"].map(reference_index["county_name"]),
            "year": merged["year"],
            "typical_home_value": merged["typical_home_value"],
            "median_household_income": merged["median_household_income"],
            "home_value_to_income_ratio": calculate_ratio(
                merged["typical_home_value"],
                merged["median_household_income"],
            ),
            "zillow_months_available": merged["zillow_months_available"],
            "zillow_data_status": merged["zillow_data_status"],
            "home_value_source": merged["home_value_source"],
            "home_value_year_method": merged["home_value_year_method"],
            "income_source": merged["income_source"],
        }
    )
    final = final[OUTPUT_COLUMNS].sort_values(["county_fips", "year"]).reset_index(drop=True)

    validate_output(final, expected_keys)
    validate_miami_v0_regression(final)
    validate_pipeline_direct_join(final, zillow, acs)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(OUTPUT_PATH, index=False)

    usable_ratios = final["home_value_to_income_ratio"].notna().sum()
    print(f"Output path: {OUTPUT_PATH}")
    print(f"Row count: {len(final)}")
    print(f"County count: {final['county_fips'].nunique()}")
    print(f"Year range: {final['year'].min()}-{final['year'].max()}")
    print(f"Usable home_value_to_income_ratio rows: {usable_ratios}")
    print(
        "home_value_to_income_ratio range: "
        f"{final['home_value_to_income_ratio'].min(skipna=True):.4f}-"
        f"{final['home_value_to_income_ratio'].max():.4f}"
    )
    print("[PASS] Zillow and ACS inputs validated")
    print("[PASS] county-year keys matched before join")
    print("[PASS] final Florida affordability table validated")
    print("[PASS] Miami-Dade rows match V0 comparable columns")
    print("[PASS] pipeline counties match direct Zillow-ACS join")


if __name__ == "__main__":
    main()
