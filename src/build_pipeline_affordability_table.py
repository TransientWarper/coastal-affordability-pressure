"""
Build four-state pipeline coastal affordability table.

Joins validated 3,720-row Zillow and ACS county-year outputs for the
southeastern pipeline reference (FL, GA, SC, NC), 2015-2024.
"""

from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
MANUAL_DIR = PROJECT_ROOT / "data" / "manual"

ZILLOW_PATH = (
    PROCESSED_DIR / "zillow_zhvi_pipeline_counties_annual_2015_2024.csv"
)
ACS_PATH = PROCESSED_DIR / "acs_b19013_pipeline_counties_2015_2024.csv"
REFERENCE_PATH = MANUAL_DIR / "pipeline_counties.csv"
FLORIDA_AFFORDABILITY_PATH = (
    PROCESSED_DIR / "coastal_affordability_florida_2015_2024.csv"
)
OUTPUT_PATH = PROCESSED_DIR / "coastal_affordability_pipeline_2015_2024.csv"

START_YEAR = 2015
END_YEAR = 2024
EXPECTED_YEARS = set(range(START_YEAR, END_YEAR + 1))
EXPECTED_PIPELINE_COUNTIES = 372
EXPECTED_PIPELINE_ROWS = 3720
EXPECTED_STATE_ROW_COUNTS = {
    "FL": 670,
    "GA": 1590,
    "SC": 460,
    "NC": 1000,
}
EXPECTED_AFFORDABILITY_STATUS_COUNTS = {
    "available_complete": 3671,
    "available_partial": 20,
    "source_data_unavailable": 29,
}

ZILLOW_STATUS_COMPLETE = "complete_12_months"
ZILLOW_STATUS_PARTIAL = {"partial_10_11_months", "partial_1_9_months"}
ZILLOW_STATUS_UNAVAILABLE = "source_data_unavailable"
ACS_STATUS_AVAILABLE = "available"
ACS_STATUS_UNAVAILABLE = "source_data_unavailable"

AFFORDABILITY_STATUS_COMPLETE = "available_complete"
AFFORDABILITY_STATUS_PARTIAL = "available_partial"
AFFORDABILITY_STATUS_UNAVAILABLE = "source_data_unavailable"
APPROVED_AFFORDABILITY_STATUSES = {
    AFFORDABILITY_STATUS_COMPLETE,
    AFFORDABILITY_STATUS_PARTIAL,
    AFFORDABILITY_STATUS_UNAVAILABLE,
}

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
    "acs_data_status",
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
    "acs_data_status",
    "affordability_data_status",
    "home_value_source",
    "home_value_year_method",
    "income_source",
]

FLORIDA_REGRESSION_COLUMNS = [
    "state",
    "county_fips",
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


def pass_line(message: str) -> None:
    print(f"[PASS] {message}")


def normalize_county_fips(series: pd.Series) -> pd.Series:
    """Convert county FIPS values to five-character strings."""
    return series.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)


def normalize_year(series: pd.Series) -> pd.Series:
    """Convert year values to integers."""
    return pd.to_numeric(series, errors="raise").astype(int)


def load_pipeline_reference() -> pd.DataFrame:
    """Load and validate the authoritative pipeline county reference."""
    reference = pd.read_csv(
        REFERENCE_PATH,
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
    if len(reference) != EXPECTED_PIPELINE_COUNTIES:
        raise ValueError(
            f"Expected {EXPECTED_PIPELINE_COUNTIES} reference counties, "
            f"found {len(reference)}."
        )
    if reference["county_fips"].nunique() != EXPECTED_PIPELINE_COUNTIES:
        raise ValueError("Reference must contain 372 unique county_fips values.")

    pass_line(f"reference contains {EXPECTED_PIPELINE_COUNTIES} counties")
    return reference.sort_values(["state_fips", "county_fips"]).reset_index(drop=True)


def validate_input_labels(
    df: pd.DataFrame,
    reference: pd.DataFrame,
    source_name: str,
) -> None:
    """Fail if input state or county_name labels conflict with the reference."""
    reference_labels = reference.set_index("county_fips")[["state", "county_name"]]
    input_labels = (
        df.drop_duplicates("county_fips")
        .set_index("county_fips")[["state", "county_name"]]
    )

    shared_fips = reference_labels.index.intersection(input_labels.index)
    for county_fips in sorted(shared_fips):
        ref_state = reference_labels.loc[county_fips, "state"]
        ref_name = reference_labels.loc[county_fips, "county_name"]
        in_state = input_labels.loc[county_fips, "state"]
        in_name = input_labels.loc[county_fips, "county_name"]
        if in_state != ref_state or in_name != ref_name:
            raise ValueError(
                f"{source_name} label conflict for county_fips {county_fips}: "
                f"reference=({ref_state!r}, {ref_name!r}), "
                f"input=({in_state!r}, {in_name!r})."
            )


def load_and_validate_zillow(reference: pd.DataFrame) -> pd.DataFrame:
    """Load and validate the pipeline Zillow input."""
    zillow = pd.read_csv(ZILLOW_PATH, dtype={"county_fips": "string"})
    missing_columns = [col for col in ZILLOW_REQUIRED_COLUMNS if col not in zillow.columns]
    if missing_columns:
        raise ValueError(f"Zillow input missing required columns: {missing_columns}")

    df = zillow.copy()
    df["county_fips"] = normalize_county_fips(df["county_fips"])
    df["year"] = normalize_year(df["year"])

    if len(df) != EXPECTED_PIPELINE_ROWS:
        raise ValueError(
            f"Zillow input must contain exactly {EXPECTED_PIPELINE_ROWS} rows, "
            f"found {len(df)}."
        )
    if df.duplicated(["county_fips", "year"]).any():
        raise ValueError("Zillow input contains duplicate county-year keys.")

    pass_line(f"Zillow input contains {EXPECTED_PIPELINE_ROWS} rows")
    pass_line("Zillow key county_fips + year is unique")
    validate_input_labels(df, reference, "Zillow")
    return df.sort_values(["county_fips", "year"]).reset_index(drop=True)


def load_and_validate_acs(reference: pd.DataFrame) -> pd.DataFrame:
    """Load and validate the pipeline ACS input."""
    acs = pd.read_csv(ACS_PATH, dtype={"county_fips": "string"})
    missing_columns = [col for col in ACS_REQUIRED_COLUMNS if col not in acs.columns]
    if missing_columns:
        raise ValueError(f"ACS input missing required columns: {missing_columns}")

    df = acs.copy()
    df["county_fips"] = normalize_county_fips(df["county_fips"])
    df["year"] = normalize_year(df["year"])

    if len(df) != EXPECTED_PIPELINE_ROWS:
        raise ValueError(
            f"ACS input must contain exactly {EXPECTED_PIPELINE_ROWS} rows, "
            f"found {len(df)}."
        )
    if df.duplicated(["county_fips", "year"]).any():
        raise ValueError("ACS input contains duplicate county-year keys.")

    pass_line(f"ACS input contains {EXPECTED_PIPELINE_ROWS} rows")
    pass_line("ACS key county_fips + year is unique")
    validate_input_labels(df, reference, "ACS")
    return df.sort_values(["county_fips", "year"]).reset_index(drop=True)


def calculate_ratio(home_value: pd.Series, income: pd.Series) -> pd.Series:
    """Calculate home value-to-income ratio, leaving null when home value is null."""
    ratio = home_value / income
    ratio = ratio.where(home_value.notna())
    return ratio.round(4)


def assign_affordability_status(df: pd.DataFrame) -> pd.Series:
    """Assign affordability_data_status from Zillow and ACS source statuses."""
    zillow_complete = df["zillow_data_status"] == ZILLOW_STATUS_COMPLETE
    zillow_partial = df["zillow_data_status"].isin(ZILLOW_STATUS_PARTIAL)
    acs_available = df["acs_data_status"] == ACS_STATUS_AVAILABLE
    home_ok = df["typical_home_value"].notna()
    income_ok = df["median_household_income"].notna() & (df["median_household_income"] > 0)

    complete_mask = zillow_complete & acs_available & home_ok & income_ok
    partial_mask = zillow_partial & acs_available & home_ok & income_ok

    status = pd.Series(AFFORDABILITY_STATUS_UNAVAILABLE, index=df.index, dtype="string")
    status.loc[partial_mask] = AFFORDABILITY_STATUS_PARTIAL
    status.loc[complete_mask] = AFFORDABILITY_STATUS_COMPLETE
    return status


def build_affordability_table(
    zillow: pd.DataFrame,
    acs: pd.DataFrame,
    reference: pd.DataFrame,
) -> pd.DataFrame:
    """Join Zillow and ACS inputs into the pipeline affordability table."""
    merged = zillow.merge(
        acs[
            [
                "county_fips",
                "year",
                "median_household_income",
                "income_source",
                "acs_data_status",
            ]
        ],
        on=["county_fips", "year"],
        how="inner",
        validate="one_to_one",
    )

    pass_line("one-to-one join succeeds")

    if len(merged) != EXPECTED_PIPELINE_ROWS:
        raise ValueError(
            f"Merge must produce exactly {EXPECTED_PIPELINE_ROWS} rows, found {len(merged)}."
        )

    reference_index = reference.set_index("county_fips")
    ratio = calculate_ratio(merged["typical_home_value"], merged["median_household_income"])

    final = pd.DataFrame(
        {
            "state": merged["county_fips"].map(reference_index["state"]),
            "county_fips": merged["county_fips"],
            "county_name": merged["county_fips"].map(reference_index["county_name"]),
            "year": merged["year"],
            "typical_home_value": merged["typical_home_value"],
            "median_household_income": merged["median_household_income"],
            "home_value_to_income_ratio": ratio,
            "zillow_months_available": merged["zillow_months_available"],
            "zillow_data_status": merged["zillow_data_status"],
            "acs_data_status": merged["acs_data_status"],
            "home_value_source": merged["home_value_source"],
            "home_value_year_method": merged["home_value_year_method"],
            "income_source": merged["income_source"],
        }
    )
    final["affordability_data_status"] = assign_affordability_status(final)
    final["county_fips"] = normalize_county_fips(final["county_fips"])
    return final[OUTPUT_COLUMNS].sort_values(["county_fips", "year"]).reset_index(drop=True)


def validate_output(final: pd.DataFrame, reference: pd.DataFrame) -> None:
    """Validate the pipeline affordability output."""
    if list(final.columns) != OUTPUT_COLUMNS:
        raise ValueError(f"Unexpected output columns: {list(final.columns)}")

    if len(final) != EXPECTED_PIPELINE_ROWS:
        raise ValueError(
            f"Final output must contain exactly {EXPECTED_PIPELINE_ROWS} rows, "
            f"found {len(final)}."
        )

    pass_line(f"final output contains {EXPECTED_PIPELINE_ROWS} rows")

    if not final.groupby("county_fips").size().eq(len(EXPECTED_YEARS)).all():
        raise ValueError("Final output must contain exactly 10 rows per county.")

    pass_line("every county has 10 rows")

    if not final.groupby("year").size().eq(EXPECTED_PIPELINE_COUNTIES).all():
        raise ValueError("Final output must contain exactly 372 rows per year.")

    pass_line("every year has 372 rows")

    state_counts = final.groupby("state").size().to_dict()
    if state_counts != EXPECTED_STATE_ROW_COUNTS:
        raise ValueError(
            f"Unexpected state row counts: {state_counts}; "
            f"expected {EXPECTED_STATE_ROW_COUNTS}."
        )

    pass_line("every state has expected row count")

    if set(final["year"]) != EXPECTED_YEARS:
        raise ValueError("Final output years must be exactly 2015 through 2024.")

    pass_line(f"years exactly {START_YEAR}-{END_YEAR}")

    if final.duplicated(["county_fips", "year"]).any():
        raise ValueError("Final output contains duplicate county-year keys.")

    pass_line("county_fips + year uniqueness confirmed")

    if not final["county_fips"].str.fullmatch(r"\d{5}").all():
        raise ValueError("county_fips values must be exactly five digits.")

    pass_line("county_fips values exactly five digits")

    required_non_null = ["state", "county_fips", "county_name", "year"]
    if final[required_non_null].isna().any().any():
        raise ValueError("Null values found in required label columns.")

    pass_line("no null state, county_fips, county_name, or year")

    reference_labels = reference.set_index("county_fips")[["state", "county_name"]]
    output_labels = (
        final.drop_duplicates("county_fips")
        .set_index("county_fips")[["state", "county_name"]]
    )
    if not output_labels.equals(reference_labels):
        raise ValueError("Output labels must match pipeline_counties.csv.")

    pass_line("output labels match pipeline_counties.csv")

    if not final["median_household_income"].notna().all():
        raise ValueError("median_household_income must be populated for all rows.")
    if not (final["median_household_income"] > 0).all():
        raise ValueError("median_household_income must be positive.")

    pass_line("median household income is positive and non-null")

    valid_home = final["typical_home_value"].dropna()
    if not (valid_home > 0).all():
        raise ValueError("Non-null typical_home_value values must be positive.")

    pass_line("typical home value is positive where non-null")

    valid_ratio = final["home_value_to_income_ratio"].dropna()
    if not (valid_ratio > 0).all():
        raise ValueError("Non-null home_value_to_income_ratio values must be positive.")

    pass_line("ratio is positive where non-null")

    expected_ratio = calculate_ratio(
        final["typical_home_value"],
        final["median_household_income"],
    )
    ratio_mask = final["home_value_to_income_ratio"].notna()
    if not np.allclose(
        final.loc[ratio_mask, "home_value_to_income_ratio"],
        expected_ratio.loc[ratio_mask],
        rtol=0,
        atol=0.0001,
    ):
        raise ValueError("home_value_to_income_ratio does not match the expected formula.")

    pass_line("ratio equals home value divided by income within rounding tolerance")

    null_home = final["typical_home_value"].isna()
    if not final.loc[null_home, "home_value_to_income_ratio"].isna().all():
        raise ValueError("Null typical_home_value must produce null ratio.")

    pass_line("null typical_home_value produces null ratio")

    unavailable = final["affordability_data_status"] == AFFORDABILITY_STATUS_UNAVAILABLE
    if not final.loc[unavailable, "home_value_to_income_ratio"].isna().all():
        raise ValueError("source_data_unavailable must produce null ratio.")

    pass_line("source_data_unavailable produces null ratio")

    complete = final["affordability_data_status"] == AFFORDABILITY_STATUS_COMPLETE
    if not final.loc[complete, "zillow_months_available"].eq(12).all():
        raise ValueError("available_complete rows must have 12 Zillow months.")

    pass_line("available_complete rows have 12 Zillow months")

    partial = final["affordability_data_status"] == AFFORDABILITY_STATUS_PARTIAL
    if not final.loc[partial, "zillow_months_available"].between(1, 11).all():
        raise ValueError("available_partial rows must have 1-11 Zillow months.")

    pass_line("available_partial rows have 1-11 Zillow months")

    status_counts = final["affordability_data_status"].value_counts().to_dict()
    if status_counts != EXPECTED_AFFORDABILITY_STATUS_COUNTS:
        raise ValueError(
            f"Unexpected affordability_data_status counts: {status_counts}; "
            f"expected {EXPECTED_AFFORDABILITY_STATUS_COUNTS}."
        )

    if not set(final["affordability_data_status"]).issubset(APPROVED_AFFORDABILITY_STATUSES):
        raise ValueError("Output contains unapproved affordability_data_status values.")

    pass_line("status values belong to the approved set")

    for status_value, zillow_ok, acs_ok, home_ok, income_ok, ratio_ok in [
        (
            AFFORDABILITY_STATUS_COMPLETE,
            lambda row: row["zillow_data_status"] == ZILLOW_STATUS_COMPLETE,
            lambda row: row["acs_data_status"] == ACS_STATUS_AVAILABLE,
            lambda row: pd.notna(row["typical_home_value"]),
            lambda row: pd.notna(row["median_household_income"])
            and row["median_household_income"] > 0,
            lambda row: pd.notna(row["home_value_to_income_ratio"]),
        ),
        (
            AFFORDABILITY_STATUS_PARTIAL,
            lambda row: row["zillow_data_status"] in ZILLOW_STATUS_PARTIAL,
            lambda row: row["acs_data_status"] == ACS_STATUS_AVAILABLE,
            lambda row: pd.notna(row["typical_home_value"]),
            lambda row: pd.notna(row["median_household_income"])
            and row["median_household_income"] > 0,
            lambda row: pd.notna(row["home_value_to_income_ratio"]),
        ),
        (
            AFFORDABILITY_STATUS_UNAVAILABLE,
            lambda row: True,
            lambda row: True,
            lambda row: True,
            lambda row: True,
            lambda row: pd.isna(row["home_value_to_income_ratio"]),
        ),
    ]:
        subset = final[final["affordability_data_status"] == status_value]
        for _, row in subset.iterrows():
            if status_value == AFFORDABILITY_STATUS_UNAVAILABLE:
                if (
                    row["zillow_data_status"] == ZILLOW_STATUS_COMPLETE
                    and row["acs_data_status"] == ACS_STATUS_AVAILABLE
                    and pd.notna(row["typical_home_value"])
                    and pd.notna(row["median_household_income"])
                    and row["median_household_income"] > 0
                ):
                    raise ValueError(
                        f"Row classified unavailable but has complete inputs: "
                        f"{row['county_fips']} {int(row['year'])}."
                    )
                if pd.notna(row["home_value_to_income_ratio"]):
                    raise ValueError(
                        f"Unavailable row has non-null ratio: "
                        f"{row['county_fips']} {int(row['year'])}."
                    )
            else:
                if not (
                    zillow_ok(row)
                    and acs_ok(row)
                    and home_ok(row)
                    and income_ok(row)
                    and ratio_ok(row)
                ):
                    raise ValueError(
                        f"Status logic inconsistent for {status_value} row "
                        f"{row['county_fips']} {int(row['year'])}."
                    )

    pass_line("status logic is internally consistent")


def compare_florida_county_names(
    reference: pd.DataFrame,
    committed_florida: pd.DataFrame,
) -> list[tuple[str, str, str]]:
    """Report Florida county-name differences between references."""
    pipeline_fl = (
        reference.loc[reference["state"] == "FL", ["county_fips", "county_name"]]
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


def validate_florida_regression(final: pd.DataFrame) -> None:
    """Confirm Florida subset matches committed Florida affordability output."""
    if not FLORIDA_AFFORDABILITY_PATH.exists():
        raise FileNotFoundError(
            f"Committed Florida affordability output not found: {FLORIDA_AFFORDABILITY_PATH}"
        )

    committed = pd.read_csv(
        FLORIDA_AFFORDABILITY_PATH,
        dtype={"county_fips": "string"},
    )
    committed["county_fips"] = normalize_county_fips(committed["county_fips"])

    pipeline_fl = (
        final.loc[final["state"] == "FL"]
        .sort_values(["county_fips", "year"])
        .reset_index(drop=True)
    )
    committed_fl = committed.sort_values(["county_fips", "year"]).reset_index(drop=True)

    if len(pipeline_fl) != EXPECTED_STATE_ROW_COUNTS["FL"]:
        raise ValueError(
            f"Expected {EXPECTED_STATE_ROW_COUNTS['FL']} Florida rows, "
            f"found {len(pipeline_fl)}."
        )

    pd.testing.assert_frame_equal(
        pipeline_fl[FLORIDA_REGRESSION_COLUMNS],
        committed_fl[FLORIDA_REGRESSION_COLUMNS],
        check_dtype=False,
        check_exact=False,
        rtol=1e-12,
        atol=1e-9,
    )

    pass_line("Florida analytical regression passes")


def print_coverage_summary(
    final: pd.DataFrame,
    name_differences: list[tuple[str, str, str]],
) -> None:
    """Print pipeline affordability coverage summary."""
    print("\nPipeline affordability coverage summary:")
    print("  row count by state:")
    for state, count in final.groupby("state").size().sort_index().items():
        print(f"    {state}: {count}")

    print("  county count by state:")
    for state, count in (
        final.drop_duplicates("county_fips").groupby("state").size().sort_index().items()
    ):
        print(f"    {state}: {count}")

    print("  affordability_data_status distribution:")
    for status, count in (
        final["affordability_data_status"].value_counts().sort_index().items()
    ):
        print(f"    {status}: {count}")

    print("  Zillow status distribution:")
    for status, count in final["zillow_data_status"].value_counts().sort_index().items():
        print(f"    {status}: {count}")

    print("  ACS status distribution:")
    for status, count in final["acs_data_status"].value_counts().sort_index().items():
        print(f"    {status}: {count}")

    null_ratio_count = int(final["home_value_to_income_ratio"].isna().sum())
    print(f"  null ratio count: {null_ratio_count}")

    unavailable = final.loc[
        final["affordability_data_status"] == AFFORDABILITY_STATUS_UNAVAILABLE
    ].sort_values(["state", "county_fips", "year"])
    print(f"  source_data_unavailable county-years: {len(unavailable)}")
    for _, row in unavailable.iterrows():
        print(
            f"    {row['state']} {row['county_fips']} {row['county_name']} "
            f"{int(row['year'])} "
            f"(zillow={row['zillow_data_status']}, acs={row['acs_data_status']})"
        )

    partial = final.loc[
        final["affordability_data_status"] == AFFORDABILITY_STATUS_PARTIAL
    ].sort_values(["state", "county_fips", "year"])
    print(f"  available_partial county-years: {len(partial)}")
    for _, row in partial.iterrows():
        print(
            f"    {row['state']} {row['county_fips']} {row['county_name']} "
            f"{int(row['year'])}: {int(row['zillow_months_available'])} months "
            f"({row['zillow_data_status']})"
        )

    valid_ratio = final["home_value_to_income_ratio"].dropna()
    print(
        "  non-null ratio range: "
        f"{valid_ratio.min():.4f} to {valid_ratio.max():.4f}"
    )

    top10 = (
        final.dropna(subset=["home_value_to_income_ratio"])
        .nlargest(10, "home_value_to_income_ratio")
        .sort_values("home_value_to_income_ratio", ascending=False)
    )
    print("  top 10 highest ratios:")
    for _, row in top10.iterrows():
        print(
            f"    {row['state']} {row['county_fips']} {row['county_name']} "
            f"{int(row['year'])}: {row['home_value_to_income_ratio']:.4f}"
        )

    bottom10 = (
        final.dropna(subset=["home_value_to_income_ratio"])
        .nsmallest(10, "home_value_to_income_ratio")
        .sort_values("home_value_to_income_ratio")
    )
    print("  bottom 10 lowest non-null ratios:")
    for _, row in bottom10.iterrows():
        print(
            f"    {row['state']} {row['county_fips']} {row['county_name']} "
            f"{int(row['year'])}: {row['home_value_to_income_ratio']:.4f}"
        )

    if name_differences:
        print("  county-name differences (Florida committed vs pipeline reference):")
        for county_fips, committed_name, pipeline_name in name_differences:
            print(
                f"    {county_fips}: committed={committed_name!r}; "
                f"pipeline={pipeline_name!r}"
            )
    else:
        print("  county-name differences: none")

    print(f"  output path: {OUTPUT_PATH}")


def main() -> None:
    """Build the four-state pipeline affordability table."""
    reference = load_pipeline_reference()
    zillow = load_and_validate_zillow(reference)
    acs = load_and_validate_acs(reference)

    final = build_affordability_table(zillow, acs, reference)
    validate_output(final, reference)

    committed_florida = pd.read_csv(
        FLORIDA_AFFORDABILITY_PATH,
        dtype={"county_fips": "string"},
    )
    name_differences = compare_florida_county_names(reference, committed_florida)
    validate_florida_regression(final)
    print_coverage_summary(final, name_differences)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(OUTPUT_PATH, index=False)
    pass_line(f"output written ({OUTPUT_PATH})")


if __name__ == "__main__":
    main()
