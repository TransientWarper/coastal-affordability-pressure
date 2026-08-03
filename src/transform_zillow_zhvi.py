"""
Transform Zillow county ZHVI data for Miami-Dade County, selected counties, Florida,
and the eighteen-state pipeline county reference.

Input:
- data/raw/zillow_zhvi/zillow_zhvi_county_raw.csv
- data/manual/selected_counties.csv
- data/manual/pipeline_counties.csv

Outputs:
- data/processed/zillow_zhvi_miami_dade_annual_2015_2024.csv  (V0, unchanged behavior)
- data/processed/zillow_zhvi_selected_counties_annual_2015_2024.csv  (pipeline expansion)
- data/processed/zillow_zhvi_florida_counties_annual_2015_2024.csv  (statewide expansion)
- data/processed/zillow_zhvi_pipeline_counties_annual_2015_2024.csv  (eighteen-state expansion)
"""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_PATH = PROJECT_ROOT / "data" / "raw" / "zillow_zhvi" / "zillow_zhvi_county_raw.csv"
SELECTED_COUNTIES_PATH = PROJECT_ROOT / "data" / "manual" / "selected_counties.csv"
MIAMI_OUTPUT_PATH = (
    PROJECT_ROOT / "data" / "processed" / "zillow_zhvi_miami_dade_annual_2015_2024.csv"
)
SELECTED_OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "zillow_zhvi_selected_counties_annual_2015_2024.csv"
)
FLORIDA_OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "zillow_zhvi_florida_counties_annual_2015_2024.csv"
)
PIPELINE_COUNTY_REFERENCE_PATH = (
    PROJECT_ROOT / "data" / "manual" / "pipeline_counties.csv"
)
PIPELINE_COUNTIES_OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "zillow_zhvi_pipeline_counties_annual_2015_2024.csv"
)

START_YEAR = 2015
END_YEAR = 2024
EXPECTED_YEARS = set(range(START_YEAR, END_YEAR + 1))
EXPECTED_PIPELINE_FIPS = {"12011", "12086", "12099"}
EXPECTED_PIPELINE_COUNTIES = 3
EXPECTED_PIPELINE_ROWS = 30
EXPECTED_FL_COUNTIES = 67
EXPECTED_FL_ROWS = 670
EXPECTED_PIPELINE_REF_COUNTIES = 1085
EXPECTED_PIPELINE_REF_ROWS = 10850
EXPECTED_PIPELINE_STATE_COUNTS = {
    "FL": 67,
    "GA": 159,
    "SC": 46,
    "NC": 100,
    "VA": 133,
    "MD": 24,
    "DE": 3,
    "NJ": 21,
    "NY": 62,
    "RI": 5,
    "MA": 14,
    "NH": 10,
    "ME": 16,
    "PA": 67,
    "WV": 55,
    "OH": 88,
    "KY": 120,
    "TN": 95,
}
MIN_COMPARABLE_MONTHS = 10
FULL_YEAR_MONTHS = 12

SOURCE_EXCEPTION_FIPS = "12087"
SOURCE_EXCEPTION_YEAR = 2015
SOURCE_EXCEPTION_NAME = "Monroe County"

STATUS_COMPLETE = "complete_12_months"
STATUS_PARTIAL = "partial_10_11_months"
STATUS_PARTIAL_LOW = "partial_1_9_months"
STATUS_UNAVAILABLE = "source_data_unavailable"
APPROVED_PIPELINE_STATUSES = {
    STATUS_COMPLETE,
    STATUS_PARTIAL,
    STATUS_PARTIAL_LOW,
    STATUS_UNAVAILABLE,
}

OUTPUT_COLUMNS = [
    "state",
    "county_fips",
    "county_name",
    "year",
    "typical_home_value",
    "zillow_months_available",
    "home_value_source",
    "home_value_year_method",
]

FLORIDA_OUTPUT_COLUMNS = OUTPUT_COLUMNS + ["zillow_data_status"]
PIPELINE_OUTPUT_COLUMNS = FLORIDA_OUTPUT_COLUMNS
FLORIDA_REGRESSION_COLUMNS = [
    "state",
    "county_fips",
    "year",
    "typical_home_value",
    "zillow_months_available",
    "home_value_source",
    "home_value_year_method",
    "zillow_data_status",
]

ID_COLUMNS = [
    "RegionID",
    "SizeRank",
    "RegionName",
    "RegionType",
    "StateName",
    "State",
    "Metro",
    "StateCodeFIPS",
    "MunicipalCodeFIPS",
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


def construct_zillow_county_fips(df: pd.DataFrame) -> pd.Series:
    """Build five-digit county FIPS from Zillow FIPS columns."""
    state_fips = df["StateCodeFIPS"].astype(int).astype(str).str.zfill(2)
    county_fips = df["MunicipalCodeFIPS"].astype(int).astype(str).str.zfill(3)
    return state_fips + county_fips


def annualize_county_rows(county_df: pd.DataFrame) -> pd.DataFrame:
    """Convert monthly ZHVI values to annual means for one county row."""
    date_columns = [
        col
        for col in county_df.columns
        if col[:4].isdigit() and START_YEAR <= int(col[:4]) <= END_YEAR
    ]

    long_df = county_df[ID_COLUMNS + date_columns].melt(
        id_vars=ID_COLUMNS,
        value_vars=date_columns,
        var_name="month",
        value_name="typical_home_value",
    )

    long_df["month"] = pd.to_datetime(long_df["month"])
    long_df["year"] = long_df["month"].dt.year

    annual = (
        long_df.groupby(
            [
                "RegionName",
                "State",
                "StateCodeFIPS",
                "MunicipalCodeFIPS",
                "year",
            ],
            as_index=False,
        )
        .agg(
            typical_home_value=("typical_home_value", "mean"),
            zillow_months_available=("typical_home_value", "count"),
        )
    )

    annual["county_fips"] = construct_zillow_county_fips(annual)
    annual["home_value_source"] = "Zillow ZHVI county"
    annual["home_value_year_method"] = "annual_mean_zhvi"
    annual["typical_home_value"] = annual["typical_home_value"].round(2)

    return annual


def format_annual_output(
    annual: pd.DataFrame,
    state,
    county_fips,
    county_name,
) -> pd.DataFrame:
    """Map annualized ZHVI rows to the standard output schema."""
    final = pd.DataFrame(
        {
            "state": state,
            "county_fips": county_fips,
            "county_name": county_name,
            "year": annual["year"],
            "typical_home_value": annual["typical_home_value"],
            "zillow_months_available": annual["zillow_months_available"],
            "home_value_source": annual["home_value_source"],
            "home_value_year_method": annual["home_value_year_method"],
        }
    )
    final["county_fips"] = normalize_county_fips(final["county_fips"])
    return final[OUTPUT_COLUMNS].sort_values(["county_fips", "year"]).reset_index(drop=True)


def build_miami_dade_v0(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Filter Miami-Dade by legacy V0 name/state keys and annualize."""
    miami = raw_df[
        (raw_df["RegionName"] == "Miami-Dade County") & (raw_df["State"] == "FL")
    ].copy()

    if miami.empty:
        raise ValueError("No Miami-Dade County, FL row found in Zillow data.")

    if len(miami) > 1:
        raise ValueError(f"Expected 1 Miami-Dade row, found {len(miami)} rows.")

    annual = annualize_county_rows(miami)
    return format_annual_output(
        annual,
        state=annual["State"],
        county_fips=annual["county_fips"],
        county_name=annual["RegionName"],
    )


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


def build_selected_counties(
    raw_df: pd.DataFrame,
    selection: pd.DataFrame,
) -> pd.DataFrame:
    """Annualize ZHVI for pipeline counties using FIPS-based selection."""
    raw = raw_df.copy()
    raw["county_fips"] = construct_zillow_county_fips(raw)

    records = []
    for _, county in selection.iterrows():
        county_fips = county["county_fips"]
        matches = raw[raw["county_fips"] == county_fips]

        if matches.empty:
            raise ValueError(
                f"Selected county FIPS {county_fips} ({county['county_name']}) "
                "is absent from Zillow raw data."
            )

        if len(matches) > 1:
            raise ValueError(
                f"Selected county FIPS {county_fips} ({county['county_name']}) "
                f"maps to {len(matches)} Zillow rows; exactly one is expected."
            )

        annual = annualize_county_rows(matches)
        records.append(
            format_annual_output(
                annual,
                state=county["state"],
                county_fips=county_fips,
                county_name=county["county_name"],
            )
        )

    return pd.concat(records, ignore_index=True)


def build_florida_counties(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Annualize ZHVI for all Florida counties using FIPS-based selection."""
    raw = raw_df[raw_df["State"] == "FL"].copy()
    raw["county_fips"] = construct_zillow_county_fips(raw)

    county_fips = sorted(normalize_county_fips(raw["county_fips"]).unique())
    if len(county_fips) != EXPECTED_FL_COUNTIES:
        raise ValueError(
            f"Expected {EXPECTED_FL_COUNTIES} Florida counties in Zillow raw data, "
            f"found {len(county_fips)}."
        )

    records = []
    for fips in county_fips:
        matches = raw[normalize_county_fips(raw["county_fips"]) == fips]

        if matches.empty:
            raise ValueError(f"Florida county FIPS {fips} is absent from Zillow raw data.")

        if len(matches) > 1:
            raise ValueError(
                f"Florida county FIPS {fips} maps to {len(matches)} Zillow rows; "
                "exactly one is expected."
            )

        row = matches.iloc[0]
        annual = annualize_county_rows(matches)
        records.append(
            format_annual_output(
                annual,
                state=row["State"],
                county_fips=fips,
                county_name=row["RegionName"],
            )
        )

    florida = pd.concat(records, ignore_index=True)
    return apply_florida_data_status(florida)


def is_source_exception_row(df: pd.DataFrame) -> pd.Series:
    """Identify the approved Monroe County 2015 source-data exception row."""
    return (
        normalize_county_fips(df["county_fips"]) == SOURCE_EXCEPTION_FIPS
    ) & (df["year"] == SOURCE_EXCEPTION_YEAR)


def apply_florida_data_status(florida: pd.DataFrame) -> pd.DataFrame:
    """Assign zillow_data_status and apply the Monroe 2015 null exception."""
    df = florida.copy()
    months = normalize_months_series(df["zillow_months_available"])

    df["zillow_data_status"] = STATUS_COMPLETE
    df.loc[months.between(MIN_COMPARABLE_MONTHS, FULL_YEAR_MONTHS - 1), "zillow_data_status"] = (
        STATUS_PARTIAL
    )

    exception_mask = is_source_exception_row(df)
    if not exception_mask.any():
        raise ValueError(
            f"Florida output is missing required county-year row "
            f"({SOURCE_EXCEPTION_FIPS}, {SOURCE_EXCEPTION_YEAR})."
        )

    exception_row = df.loc[exception_mask].iloc[0]
    exception_months = int(exception_row["zillow_months_available"])

    if exception_months >= MIN_COMPARABLE_MONTHS:
        print(
            f"[INFO] Previously documented source-data exception for "
            f"{SOURCE_EXCEPTION_FIPS} {SOURCE_EXCEPTION_NAME} {SOURCE_EXCEPTION_YEAR} "
            f"is no longer needed ({exception_months} months available)."
        )
        df.loc[exception_mask, "zillow_data_status"] = (
            STATUS_COMPLETE if exception_months == FULL_YEAR_MONTHS else STATUS_PARTIAL
        )
        return df[FLORIDA_OUTPUT_COLUMNS].sort_values(["county_fips", "year"]).reset_index(
            drop=True
        )

    if exception_months != 0:
        raise ValueError(
            f"Approved source exception ({SOURCE_EXCEPTION_FIPS}, {SOURCE_EXCEPTION_YEAR}) "
            f"has {exception_months} months; only 0 months is permitted."
        )

    if pd.notna(exception_row["typical_home_value"]):
        raise ValueError(
            f"Approved source exception ({SOURCE_EXCEPTION_FIPS}, {SOURCE_EXCEPTION_YEAR}) "
            "must have null typical_home_value when zillow_months_available is 0."
        )

    df.loc[exception_mask, "typical_home_value"] = pd.NA
    df.loc[exception_mask, "zillow_data_status"] = STATUS_UNAVAILABLE

    return df[FLORIDA_OUTPUT_COLUMNS].sort_values(["county_fips", "year"]).reset_index(drop=True)


def normalize_months_series(series: pd.Series) -> pd.Series:
    """Coerce zillow_months_available to integer month counts."""
    months = series.copy()
    if not pd.api.types.is_integer_dtype(months):
        months = pd.to_numeric(months, errors="raise").astype(int)
    return months


def print_month_coverage_distribution(df: pd.DataFrame) -> None:
    """Print county-year counts by monthly observation coverage."""
    months = normalize_months_series(df["zillow_months_available"])
    print("Month coverage distribution:")
    for month_count in [12, 11, 10]:
        print(f"  {month_count} months: {(months == month_count).sum()} rows")
    print(f"  fewer than 10 months: {(months < MIN_COMPARABLE_MONTHS).sum()} rows")


def validate_zillow_month_coverage(df: pd.DataFrame, output_label: str) -> None:
    """Enforce comparable annual-average month coverage before output write."""
    months = normalize_months_series(df["zillow_months_available"])
    print_month_coverage_distribution(df)

    partial = df.loc[
        months.between(MIN_COMPARABLE_MONTHS, FULL_YEAR_MONTHS - 1)
    ].copy()
    if not partial.empty:
        print(
            f"[WARN] {output_label}: {len(partial)} county-year row(s) have "
            f"{MIN_COMPARABLE_MONTHS}-11 months (annual mean uses partial coverage):"
        )
        for _, row in partial.sort_values(["county_fips", "year"]).iterrows():
            print(
                f"[WARN]   {row['county_fips']} {row['county_name']} "
                f"{int(row['year'])}: {int(row['zillow_months_available'])} months"
            )

    insufficient = df.loc[months < MIN_COMPARABLE_MONTHS].copy()
    if not insufficient.empty:
        details = []
        for _, row in insufficient.sort_values(["county_fips", "year"]).iterrows():
            details.append(
                f"  {row['county_fips']} {row['county_name']} "
                f"{int(row['year'])}: {int(row['zillow_months_available'])} months"
            )
        raise ValueError(
            f"{output_label}: {len(insufficient)} county-year row(s) have fewer than "
            f"{MIN_COMPARABLE_MONTHS} monthly observations:\n" + "\n".join(details)
        )


def load_committed_selected_counties() -> pd.DataFrame:
    """Load the committed selected-counties output for regression comparison."""
    if not SELECTED_OUTPUT_PATH.exists():
        raise FileNotFoundError(
            f"Committed selected-counties output not found: {SELECTED_OUTPUT_PATH}"
        )

    committed = pd.read_csv(
        SELECTED_OUTPUT_PATH,
        dtype={"county_fips": "string"},
    )
    committed["county_fips"] = normalize_county_fips(committed["county_fips"])
    return committed.sort_values(["county_fips", "year"]).reset_index(drop=True)


def validate_pipeline_subset_regression(
    florida_df: pd.DataFrame,
    selected_reference: pd.DataFrame,
) -> None:
    """Confirm pipeline counties match the committed selected-counties output."""
    florida_subset = (
        florida_df.loc[
            normalize_county_fips(florida_df["county_fips"]).isin(EXPECTED_PIPELINE_FIPS)
        ]
        .sort_values(["county_fips", "year"])
        .reset_index(drop=True)
    )

    pd.testing.assert_frame_equal(
        florida_subset[OUTPUT_COLUMNS],
        selected_reference[OUTPUT_COLUMNS],
        check_dtype=False,
        check_exact=False,
        rtol=1e-12,
        atol=1e-9,
    )


def validate_selected_output(selected_final: pd.DataFrame, miami_v0: pd.DataFrame) -> None:
    """Validate the selected-counties output and Miami-Dade regression."""
    if len(selected_final) != EXPECTED_PIPELINE_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_PIPELINE_ROWS} selected-county rows, "
            f"found {len(selected_final)}."
        )

    selected_fips = set(normalize_county_fips(selected_final["county_fips"]))
    if selected_fips != EXPECTED_PIPELINE_FIPS:
        raise ValueError(
            f"Expected county_fips {sorted(EXPECTED_PIPELINE_FIPS)}, "
            f"found {sorted(selected_fips)}."
        )

    if selected_final.duplicated(["county_fips", "year"]).any():
        raise ValueError("Duplicate county_fips/year keys in selected-counties output.")

    null_counts = selected_final[OUTPUT_COLUMNS].isna().sum()
    if null_counts.any():
        raise ValueError(
            "Null values in required selected-counties columns:\n"
            f"{null_counts[null_counts > 0]}"
        )

    if not pd.api.types.is_numeric_dtype(selected_final["typical_home_value"]):
        raise ValueError("typical_home_value is not numeric.")

    if not (selected_final["typical_home_value"] > 0).all():
        raise ValueError("typical_home_value must be greater than zero.")

    validate_zillow_month_coverage(
        selected_final,
        "selected-counties output",
    )

    for county_fips in sorted(EXPECTED_PIPELINE_FIPS):
        county = selected_final[selected_final["county_fips"] == county_fips]
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

    new_miami = (
        selected_final.loc[selected_final["county_fips"] == "12086"]
        .sort_values("year")
        .reset_index(drop=True)
    )
    old_miami = miami_v0.sort_values("year").reset_index(drop=True)

    pd.testing.assert_frame_equal(
        new_miami[OUTPUT_COLUMNS],
        old_miami[OUTPUT_COLUMNS],
        check_dtype=False,
        check_exact=False,
        rtol=1e-12,
        atol=1e-9,
    )


def validate_florida_month_coverage(florida_final: pd.DataFrame) -> None:
    """Enforce month coverage with the approved Monroe 2015 null exception."""
    months = normalize_months_series(florida_final["zillow_months_available"])
    print_month_coverage_distribution(florida_final)

    zero_month_rows = florida_final.loc[months == 0].copy()
    exception_mask = is_source_exception_row(florida_final)

    if len(zero_month_rows) > 1:
        raise ValueError(
            f"Florida output has {len(zero_month_rows)} zero-month county-year rows; "
            "only one approved exception is permitted."
        )

    if len(zero_month_rows) == 1:
        zero_row = zero_month_rows.iloc[0]
        if not (
            normalize_county_fips(pd.Series([zero_row["county_fips"]])).iloc[0]
            == SOURCE_EXCEPTION_FIPS
            and int(zero_row["year"]) == SOURCE_EXCEPTION_YEAR
        ):
            raise ValueError(
                "Unapproved zero-month county-year row: "
                f"{zero_row['county_fips']} {zero_row['county_name']} "
                f"{int(zero_row['year'])}."
            )

    if exception_mask.any():
        exception_row = florida_final.loc[exception_mask].iloc[0]
        exception_months = int(exception_row["zillow_months_available"])
        if exception_months == 0:
            if pd.notna(exception_row["typical_home_value"]):
                raise ValueError(
                    f"{SOURCE_EXCEPTION_FIPS} {SOURCE_EXCEPTION_YEAR} has a non-null "
                    "typical_home_value with zero source months."
                )
            if exception_row["zillow_data_status"] != STATUS_UNAVAILABLE:
                raise ValueError(
                    f"{SOURCE_EXCEPTION_FIPS} {SOURCE_EXCEPTION_YEAR} must have "
                    f"zillow_data_status={STATUS_UNAVAILABLE}."
                )
            print(
                f"[WARN] documented source-data exception: {SOURCE_EXCEPTION_FIPS} "
                f"{SOURCE_EXCEPTION_NAME} {SOURCE_EXCEPTION_YEAR}\n"
                "       0 months; typical_home_value left null; no imputation"
            )
        elif 0 < exception_months < MIN_COMPARABLE_MONTHS:
            raise ValueError(
                f"{SOURCE_EXCEPTION_FIPS} {SOURCE_EXCEPTION_YEAR} has "
                f"{exception_months} months; values below 10 are not permitted."
            )

    insufficient = florida_final.loc[months < MIN_COMPARABLE_MONTHS].copy()
    unapproved = insufficient.loc[~is_source_exception_row(insufficient)]
    if not unapproved.empty:
        details = []
        for _, row in unapproved.sort_values(["county_fips", "year"]).iterrows():
            details.append(
                f"  {row['county_fips']} {row['county_name']} "
                f"{int(row['year'])}: {int(row['zillow_months_available'])} months"
            )
        raise ValueError(
            "Unapproved county-year row(s) have fewer than "
            f"{MIN_COMPARABLE_MONTHS} monthly observations:\n" + "\n".join(details)
        )

    partial = florida_final.loc[
        months.between(MIN_COMPARABLE_MONTHS, FULL_YEAR_MONTHS - 1)
    ].copy()
    for _, row in partial.sort_values(["county_fips", "year"]).iterrows():
        print(
            f"[WARN] partial annual coverage: {row['county_fips']} {row['county_name']} "
            f"{int(row['year'])}\n"
            f"       {int(row['zillow_months_available'])} months; "
            "annual mean calculated from available months"
        )

    print("[PASS] no unapproved county-year has fewer than 10 months")


def validate_florida_output(florida_final: pd.DataFrame) -> None:
    """Validate Florida output structure and month coverage before write."""
    if list(florida_final.columns) != FLORIDA_OUTPUT_COLUMNS:
        raise ValueError(
            f"Unexpected Florida output columns: {list(florida_final.columns)}"
        )

    if len(florida_final) != EXPECTED_FL_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_FL_ROWS} Florida county-year rows, found {len(florida_final)}."
        )

    florida_fips = set(normalize_county_fips(florida_final["county_fips"]))
    if len(florida_fips) != EXPECTED_FL_COUNTIES:
        raise ValueError(
            f"Expected {EXPECTED_FL_COUNTIES} Florida county FIPS codes, "
            f"found {len(florida_fips)}."
        )

    if not all(str(fips).startswith("12") for fips in florida_fips):
        raise ValueError("Florida output contains non-Florida county_fips values.")

    if set(florida_final["year"]) != EXPECTED_YEARS:
        raise ValueError(
            f"Expected years {sorted(EXPECTED_YEARS)}, "
            f"found {sorted(set(florida_final['year']))}."
        )

    if florida_final.duplicated(["county_fips", "year"]).any():
        raise ValueError("Duplicate county_fips/year keys in Florida output.")

    validate_florida_month_coverage(florida_final)

    null_rows = florida_final[florida_final["typical_home_value"].isna()]
    if len(null_rows) != 1:
        raise ValueError(
            f"Expected exactly one null typical_home_value row, found {len(null_rows)}."
        )

    null_row = null_rows.iloc[0]
    if not (
        normalize_county_fips(pd.Series([null_row["county_fips"]])).iloc[0]
        == SOURCE_EXCEPTION_FIPS
        and int(null_row["year"]) == SOURCE_EXCEPTION_YEAR
    ):
        raise ValueError(
            "Null typical_home_value is only permitted for the approved "
            f"({SOURCE_EXCEPTION_FIPS}, {SOURCE_EXCEPTION_YEAR}) exception."
        )

    non_null = florida_final[florida_final["typical_home_value"].notna()]
    if not pd.api.types.is_numeric_dtype(non_null["typical_home_value"]):
        raise ValueError("typical_home_value is not numeric for non-null rows.")

    if not (non_null["typical_home_value"] > 0).all():
        raise ValueError("typical_home_value must be greater than zero for non-null rows.")

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
    null_counts = florida_final[required_non_null].isna().sum()
    if null_counts.any():
        raise ValueError(
            "Null values in required non-value Florida columns:\n"
            f"{null_counts[null_counts > 0]}"
        )

    status_counts = florida_final["zillow_data_status"].value_counts().to_dict()
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

    unavailable = florida_final[florida_final["zillow_data_status"] == STATUS_UNAVAILABLE]
    if len(unavailable) != 1 or not is_source_exception_row(unavailable).all():
        raise ValueError("source_data_unavailable is only permitted for the approved exception.")

    partial = florida_final[florida_final["zillow_data_status"] == STATUS_PARTIAL]
    if len(partial) != 1:
        raise ValueError("Expected exactly one partial_10_11_months row.")
    partial_row = partial.iloc[0]
    if not (
        normalize_county_fips(pd.Series([partial_row["county_fips"]])).iloc[0]
        == SOURCE_EXCEPTION_FIPS
        and int(partial_row["year"]) == SOURCE_EXCEPTION_YEAR + 1
        and int(partial_row["zillow_months_available"]) == 11
    ):
        raise ValueError(
            "partial_10_11_months row must be Monroe County 2016 with 11 months."
        )

    for county_fips in sorted(florida_fips):
        county = florida_final[
            normalize_county_fips(florida_final["county_fips"]) == county_fips
        ]
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
        year_rows = florida_final[florida_final["year"] == year]
        if len(year_rows) != EXPECTED_FL_COUNTIES:
            raise ValueError(
                f"Year {year} has {len(year_rows)} counties; "
                f"expected {EXPECTED_FL_COUNTIES}."
            )

    usable_values = florida_final["typical_home_value"].notna().sum()
    print(
        f"[PASS] Florida county-year panel: {EXPECTED_FL_ROWS} rows, "
        f"{EXPECTED_FL_COUNTIES} counties, {START_YEAR}-{END_YEAR}"
    )
    print(f"[PASS] usable annual Zillow values: {usable_values}")


def pass_line(message: str) -> None:
    print(f"[PASS] {message}")


def load_pipeline_county_reference() -> pd.DataFrame:
    """Load and validate the eighteen-state pipeline county reference."""
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

    if reference.duplicated(["county_fips"]).any():
        raise ValueError("Duplicate county_fips values in pipeline_counties.csv.")

    if not reference["county_fips"].str.fullmatch(r"\d{5}").all():
        raise ValueError("county_fips in pipeline_counties.csv must match ^\\d{5}$.")

    if not (reference["county_fips"].str[:2] == reference["state_fips"]).all():
        raise ValueError(
            "state_fips must match the first two characters of county_fips "
            "in pipeline_counties.csv."
        )

    for column in ["state", "county_name"]:
        if reference[column].isna().any():
            raise ValueError(f"Null {column} values in pipeline_counties.csv.")
        if reference[column].astype(str).str.strip().eq("").any():
            raise ValueError(f"Blank {column} values in pipeline_counties.csv.")

    state_counts = reference.groupby("state").size().to_dict()
    if state_counts != EXPECTED_PIPELINE_STATE_COUNTS:
        raise ValueError(
            f"Unexpected pipeline county counts by state: {state_counts}; "
            f"expected {EXPECTED_PIPELINE_STATE_COUNTS}."
        )

    pass_line(f"pipeline reference loaded: {EXPECTED_PIPELINE_REF_COUNTIES} counties")
    return reference.sort_values(["state_fips", "county_fips"]).reset_index(drop=True)


def apply_pipeline_data_status(pipeline: pd.DataFrame) -> pd.DataFrame:
    """Assign zillow_data_status for the multistate pipeline output."""
    df = pipeline.copy()
    months = normalize_months_series(df["zillow_months_available"])

    df["zillow_data_status"] = STATUS_COMPLETE
    df.loc[months.between(MIN_COMPARABLE_MONTHS, FULL_YEAR_MONTHS - 1), "zillow_data_status"] = (
        STATUS_PARTIAL
    )
    df.loc[months.between(1, MIN_COMPARABLE_MONTHS - 1), "zillow_data_status"] = (
        STATUS_PARTIAL_LOW
    )
    df.loc[months == 0, "zillow_data_status"] = STATUS_UNAVAILABLE
    df.loc[months == 0, "typical_home_value"] = pd.NA

    return df[PIPELINE_OUTPUT_COLUMNS].sort_values(["county_fips", "year"]).reset_index(drop=True)


def build_pipeline_counties(
    raw_df: pd.DataFrame,
    reference: pd.DataFrame,
) -> pd.DataFrame:
    """Annualize ZHVI for pipeline reference counties using FIPS-based selection."""
    raw = raw_df.copy()
    raw["county_fips"] = construct_zillow_county_fips(raw)

    annual_records = []
    for county_fips in reference["county_fips"]:
        matches = raw[normalize_county_fips(raw["county_fips"]) == county_fips]

        if len(matches) > 1:
            raise ValueError(
                f"Pipeline county FIPS {county_fips} maps to {len(matches)} Zillow rows; "
                "exactly one is expected."
            )

        if matches.empty:
            annual_records.append(
                pd.DataFrame(
                    {
                        "county_fips": county_fips,
                        "year": sorted(EXPECTED_YEARS),
                        "typical_home_value": pd.NA,
                        "zillow_months_available": 0,
                        "home_value_source": "Zillow ZHVI county",
                        "home_value_year_method": "annual_mean_zhvi",
                    }
                )
            )
            continue

        annual = annualize_county_rows(matches)
        annual_records.append(
            annual[
                [
                    "county_fips",
                    "year",
                    "typical_home_value",
                    "zillow_months_available",
                    "home_value_source",
                    "home_value_year_method",
                ]
            ].copy()
        )

    annual_panel = pd.concat(annual_records, ignore_index=True)
    annual_panel["county_fips"] = normalize_county_fips(annual_panel["county_fips"])

    years = pd.DataFrame({"year": sorted(EXPECTED_YEARS)})
    skeleton = reference.merge(years, how="cross")

    merged = skeleton.merge(
        annual_panel,
        on=["county_fips", "year"],
        how="left",
        validate="one_to_one",
    )

    if merged["home_value_source"].isna().any():
        raise ValueError("Pipeline panel is missing annualized Zillow rows after merge.")

    final = pd.DataFrame(
        {
            "state": merged["state"],
            "county_fips": merged["county_fips"],
            "county_name": merged["county_name"],
            "year": merged["year"],
            "typical_home_value": merged["typical_home_value"],
            "zillow_months_available": merged["zillow_months_available"],
            "home_value_source": merged["home_value_source"],
            "home_value_year_method": merged["home_value_year_method"],
        }
    )
    final["county_fips"] = normalize_county_fips(final["county_fips"])

    return apply_pipeline_data_status(final)


def load_committed_florida_counties() -> pd.DataFrame:
    """Load the committed Florida output for regression comparison."""
    if not FLORIDA_OUTPUT_PATH.exists():
        raise FileNotFoundError(
            f"Committed Florida output not found: {FLORIDA_OUTPUT_PATH}"
        )

    committed = pd.read_csv(
        FLORIDA_OUTPUT_PATH,
        dtype={"county_fips": "string"},
    )
    committed["county_fips"] = normalize_county_fips(committed["county_fips"])
    return committed.sort_values(["county_fips", "year"]).reset_index(drop=True)


def validate_pipeline_florida_regression(
    pipeline_final: pd.DataFrame,
    committed_florida: pd.DataFrame,
) -> None:
    """Confirm Florida subset matches the committed Florida Zillow output."""
    pipeline_fl = (
        pipeline_final.loc[pipeline_final["state"] == "FL"]
        .sort_values(["county_fips", "year"])
        .reset_index(drop=True)
    )
    committed_fl = committed_florida.sort_values(["county_fips", "year"]).reset_index(drop=True)

    if len(pipeline_fl) != EXPECTED_FL_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_FL_ROWS} Florida rows in pipeline output, "
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

    pass_line(
        "Florida regression comparison "
        "(state, county_fips, year, values, months, sources, status)"
    )


def print_pipeline_coverage_summary(
    reference: pd.DataFrame,
    raw_df: pd.DataFrame,
    pipeline_final: pd.DataFrame,
) -> None:
    """Print Zillow coverage and status summary for the pipeline output."""
    raw = raw_df.copy()
    raw["county_fips"] = construct_zillow_county_fips(raw)
    raw_fips = set(normalize_county_fips(raw["county_fips"]))
    ref_fips = set(reference["county_fips"])
    found = ref_fips & raw_fips
    absent = ref_fips - raw_fips

    print("\nPipeline Zillow coverage summary:")
    print(f"  reference counties found in Zillow raw: {len(found)}")
    print(f"  reference counties absent from Zillow raw: {len(absent)}")
    if absent:
        absent_by_state = (
            reference.loc[reference["county_fips"].isin(absent)]
            .groupby("state")
            .size()
            .sort_index()
        )
        print("  absent counties by state:")
        for state, count in absent_by_state.items():
            print(f"    {state}: {count}")

    status_counts = pipeline_final["zillow_data_status"].value_counts().sort_index()
    print("  county-years by zillow_data_status:")
    for status, count in status_counts.items():
        print(f"    {status}: {count}")

    null_count = int(pipeline_final["typical_home_value"].isna().sum())
    print(f"  county-years with null typical_home_value: {null_count}")

    months = normalize_months_series(pipeline_final["zillow_months_available"])
    low_months = pipeline_final.loc[months.between(1, MIN_COMPARABLE_MONTHS - 1)].copy()
    print(f"  county-years with 1-9 available months: {len(low_months)}")
    if not low_months.empty:
        for _, row in low_months.sort_values(["county_fips", "year"]).iterrows():
            print(
                f"    {row['county_fips']} {row['county_name']} "
                f"{int(row['year'])}: {int(row['zillow_months_available'])} months "
                f"({row['zillow_data_status']})"
            )

    non_null = pipeline_final["typical_home_value"].dropna()
    print(
        "  non-null typical_home_value range: "
        f"{non_null.min():.2f} to {non_null.max():.2f}"
    )
    print(f"  output path: {PIPELINE_COUNTIES_OUTPUT_PATH}")


def validate_pipeline_counties_output(
    pipeline_final: pd.DataFrame,
    reference: pd.DataFrame,
) -> None:
    """Validate the eighteen-state pipeline Zillow output before write."""
    if list(pipeline_final.columns) != PIPELINE_OUTPUT_COLUMNS:
        raise ValueError(
            f"Unexpected pipeline output columns: {list(pipeline_final.columns)}"
        )

    if len(pipeline_final) != EXPECTED_PIPELINE_REF_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_PIPELINE_REF_ROWS} pipeline county-year rows, "
            f"found {len(pipeline_final)}."
        )

    pass_line(f"final panel coverage: {EXPECTED_PIPELINE_REF_ROWS} rows")

    if not pipeline_final.groupby("county_fips").size().eq(len(EXPECTED_YEARS)).all():
        raise ValueError("Each pipeline county must have exactly 10 county-year rows.")

    pass_line("10 rows for every county")

    if not pipeline_final.groupby("year").size().eq(EXPECTED_PIPELINE_REF_COUNTIES).all():
        raise ValueError("Each year must have exactly 1,085 county rows.")

    pass_line("1,085 rows for every year")

    if set(pipeline_final["year"]) != EXPECTED_YEARS:
        raise ValueError(
            f"Expected years {sorted(EXPECTED_YEARS)}, "
            f"found {sorted(set(pipeline_final['year']))}."
        )

    pass_line(f"years exactly {START_YEAR}-{END_YEAR}")

    if pipeline_final.duplicated(["county_fips", "year"]).any():
        raise ValueError("Duplicate county_fips/year keys in pipeline output.")

    pass_line("unique key: county_fips + year")

    if not pipeline_final["county_fips"].str.fullmatch(r"\d{5}").all():
        raise ValueError("county_fips values must be exactly five digits.")

    pass_line("county_fips values exactly five digits")

    required_non_null = ["state", "county_fips", "county_name", "year"]
    if pipeline_final[required_non_null].isna().any().any():
        raise ValueError("Null values found in required pipeline label columns.")

    pass_line("no null state, county_fips, county_name, or year")

    non_null = pipeline_final["typical_home_value"].dropna()
    if not non_null.gt(0).all():
        raise ValueError("Non-null typical_home_value values must be positive.")

    pass_line("home values positive where non-null")

    months = normalize_months_series(pipeline_final["zillow_months_available"])
    if not months.between(0, FULL_YEAR_MONTHS).all():
        raise ValueError("zillow_months_available must be between 0 and 12.")

    pass_line("zillow_months_available between 0 and 12")

    null_value_rows = pipeline_final["typical_home_value"].isna()
    if not months.loc[null_value_rows].eq(0).all():
        raise ValueError("Null typical_home_value rows must have zero available months.")

    pass_line("null typical_home_value rows have zero available months")

    unavailable = pipeline_final["zillow_data_status"] == STATUS_UNAVAILABLE
    if not pipeline_final.loc[unavailable, "typical_home_value"].isna().all():
        raise ValueError("source_data_unavailable rows must have null typical_home_value.")

    pass_line("source_data_unavailable rows have null typical_home_value")

    complete = pipeline_final["zillow_data_status"] == STATUS_COMPLETE
    if not months.loc[complete].eq(FULL_YEAR_MONTHS).all():
        raise ValueError("complete_12_months rows must have exactly 12 months.")

    pass_line("complete_12_months rows have exactly 12 months")

    partial = pipeline_final["zillow_data_status"] == STATUS_PARTIAL
    if not months.loc[partial].isin([10, 11]).all():
        raise ValueError("partial_10_11_months rows must have 10 or 11 months.")

    pass_line("partial_10_11_months rows have 10 or 11 months")

    partial_low = pipeline_final["zillow_data_status"] == STATUS_PARTIAL_LOW
    if not months.loc[partial_low].between(1, MIN_COMPARABLE_MONTHS - 1).all():
        raise ValueError("partial_1_9_months rows must have 1-9 months.")

    if not set(pipeline_final["zillow_data_status"]).issubset(APPROVED_PIPELINE_STATUSES):
        raise ValueError("Pipeline output contains unapproved zillow_data_status values.")

    pass_line("status values belong to the approved set")

    output_fips = set(normalize_county_fips(pipeline_final["county_fips"]))
    reference_fips = set(reference["county_fips"])
    if output_fips != reference_fips:
        raise ValueError("Pipeline output county_fips must match pipeline_counties.csv.")

    pass_line("every output county exists in pipeline_counties.csv")

    reference_labels = reference.set_index("county_fips")[["state", "county_name"]]
    output_labels = (
        pipeline_final.drop_duplicates("county_fips")
        .set_index("county_fips")[["state", "county_name"]]
    )
    if not output_labels.equals(reference_labels):
        raise ValueError(
            "Pipeline output state and county names must match pipeline_counties.csv."
        )

    pass_line("output state and county names match pipeline_counties.csv")


def main() -> None:
    """Annualize Zillow ZHVI for Miami-Dade V0 and selected pipeline counties."""
    print(f"Reading {INPUT_PATH}")
    raw_df = pd.read_csv(INPUT_PATH)

    miami_v0 = build_miami_dade_v0(raw_df)
    MIAMI_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    miami_v0.to_csv(MIAMI_OUTPUT_PATH, index=False)
    print(f"Saved {len(miami_v0)} rows to {MIAMI_OUTPUT_PATH}")

    selection = load_pipeline_selection()
    selected_final = build_selected_counties(raw_df, selection)
    validate_selected_output(selected_final, miami_v0)
    committed_selected = load_committed_selected_counties()

    pipeline_months = (
        selected_final.sort_values(["county_fips", "year"])["zillow_months_available"]
        .reset_index(drop=True)
    )
    committed_months = (
        committed_selected.sort_values(["county_fips", "year"])["zillow_months_available"]
        .reset_index(drop=True)
    )
    pd.testing.assert_series_equal(
        pipeline_months,
        committed_months,
        check_dtype=False,
        check_names=False,
    )

    print(
        f"[PASS] pipeline counties: {EXPECTED_PIPELINE_COUNTIES} "
        f"({', '.join(sorted(EXPECTED_PIPELINE_FIPS))})"
    )
    print(
        f"[PASS] row/year coverage: {len(selected_final)} rows, "
        f"10 per county, {START_YEAR}-{END_YEAR}"
    )
    print("[PASS] keys, nulls, home values, and month coverage validated")
    print("[PASS] Miami-Dade rows match V0 output")
    print("[PASS] pipeline month counts match committed selected-counties output")

    florida_final = build_florida_counties(raw_df)
    validate_florida_output(florida_final)
    validate_pipeline_subset_regression(florida_final, selected_final)

    florida_final.to_csv(FLORIDA_OUTPUT_PATH, index=False)

    print("[PASS] pipeline subset matches in-memory selected-counties output")
    print(f"[PASS] Florida output path written: {FLORIDA_OUTPUT_PATH}")

    pipeline_reference = load_pipeline_county_reference()
    pipeline_final = build_pipeline_counties(raw_df, pipeline_reference)
    validate_pipeline_counties_output(pipeline_final, pipeline_reference)
    committed_florida = load_committed_florida_counties()
    validate_pipeline_florida_regression(pipeline_final, committed_florida)
    print_pipeline_coverage_summary(pipeline_reference, raw_df, pipeline_final)

    pipeline_final.to_csv(PIPELINE_COUNTIES_OUTPUT_PATH, index=False)
    pass_line(f"pipeline output path written ({PIPELINE_COUNTIES_OUTPUT_PATH})")


if __name__ == "__main__":
    main()
