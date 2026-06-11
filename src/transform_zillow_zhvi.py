"""
Transform Zillow county ZHVI data for Miami-Dade County.

Input:
- data/raw/zillow_zhvi/zillow_zhvi_county_raw.csv

Output:
- data/processed/zillow_zhvi_miami_dade_annual_2015_2024.csv
"""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_PATH = PROJECT_ROOT / "data" / "raw" / "zillow_zhvi" / "zillow_zhvi_county_raw.csv"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "zillow_zhvi_miami_dade_annual_2015_2024.csv"

START_YEAR = 2015
END_YEAR = 2024


def main() -> None:
    """Filter Miami-Dade Zillow ZHVI and annualize monthly values."""
    print(f"Reading {INPUT_PATH}")
    df = pd.read_csv(INPUT_PATH)

    miami = df[
        (df["RegionName"] == "Miami-Dade County")
        & (df["State"] == "FL")
    ].copy()

    if miami.empty:
        raise ValueError("No Miami-Dade County, FL row found in Zillow data.")

    if len(miami) > 1:
        raise ValueError(f"Expected 1 Miami-Dade row, found {len(miami)} rows.")

    id_columns = [
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

    date_columns = [
        col for col in miami.columns
        if col[:4].isdigit() and START_YEAR <= int(col[:4]) <= END_YEAR
    ]

    long_df = miami[id_columns + date_columns].melt(
        id_vars=id_columns,
        value_vars=date_columns,
        var_name="month",
        value_name="typical_home_value",
    )

    long_df["month"] = pd.to_datetime(long_df["month"])
    long_df["year"] = long_df["month"].dt.year

    annual = (
        long_df
        .groupby(
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

    annual["state"] = annual["State"]
    annual["county_name"] = annual["RegionName"]
    annual["state_fips"] = annual["StateCodeFIPS"].astype(int).astype(str).str.zfill(2)
    annual["county_fips_short"] = annual["MunicipalCodeFIPS"].astype(int).astype(str).str.zfill(3)
    annual["county_fips"] = annual["state_fips"] + annual["county_fips_short"]
    annual["home_value_source"] = "Zillow ZHVI county"
    annual["home_value_year_method"] = "annual_mean_zhvi"

    final = annual[
        [
            "state",
            "county_fips",
            "county_name",
            "year",
            "typical_home_value",
            "zillow_months_available",
            "home_value_source",
            "home_value_year_method",
        ]
    ].copy()

    final["typical_home_value"] = final["typical_home_value"].round(2)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved {len(final)} rows to {OUTPUT_PATH}")
    print(final)


if __name__ == "__main__":
    main()
