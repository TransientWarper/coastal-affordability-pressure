"""
Transform Zillow county ZHVI data for Miami-Dade County and selected counties.

Input:
- data/raw/zillow_zhvi/zillow_zhvi_county_raw.csv
- data/manual/selected_counties.csv

Outputs:
- data/processed/zillow_zhvi_miami_dade_annual_2015_2024.csv  (V0, unchanged behavior)
- data/processed/zillow_zhvi_selected_counties_annual_2015_2024.csv  (pipeline expansion)
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

START_YEAR = 2015
END_YEAR = 2024
EXPECTED_YEARS = set(range(START_YEAR, END_YEAR + 1))
EXPECTED_PIPELINE_FIPS = {"12011", "12086", "12099"}
EXPECTED_PIPELINE_COUNTIES = 3
EXPECTED_PIPELINE_ROWS = 30

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

    months = selected_final["zillow_months_available"]
    if not pd.api.types.is_integer_dtype(months):
        months = pd.to_numeric(months, errors="raise").astype(int)

    if not months.between(1, 12).all():
        raise ValueError("zillow_months_available must be between 1 and 12.")

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

    selected_final.to_csv(SELECTED_OUTPUT_PATH, index=False)

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
    print(f"[PASS] output path written: {SELECTED_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
