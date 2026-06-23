# Coastal Affordability Pressure Tracker

This project tracks coastal affordability pressure by comparing typical home values to median household income.

## V0 Scope

V0 focuses on Miami-Dade County, Florida from 2015-2024.

The first project output is a clean county-year table showing:

- median household income
- typical home value
- home value-to-income ratio

## V0 Question

How has the typical home value-to-income ratio changed in Miami-Dade County from 2015 to 2024?

## V0 Grain

One row per county per year.

## V0 Metric

home_value_to_income_ratio = typical_home_value / median_household_income

## V0 Sources

Income:
ACS 5-year median household income, table B19013.

Home value:
Zillow ZHVI county-level typical home value.

## Current Status

The Miami-Dade V0 analytical pipeline is complete through final dataset generation.

Pipeline stages:

1. **Acquisition** — fetch ACS income (`src/fetch_acs_income.py`) and Zillow county ZHVI (`src/fetch_zillow_zhvi.py`)
2. **Transformation** — annualize Miami-Dade ZHVI from monthly values (`src/transform_zillow_zhvi.py`)
3. **Join and validation** — merge income and home value on county FIPS and year with input checks (`src/build_affordability_table.py`)
4. **Output** — write the validated county-year affordability table

Final output:

`data/processed/coastal_affordability_county_v0.csv`

Rebuild the final table from the repository root:

```bash
.venv/bin/python src/build_affordability_table.py
```

Mapping, statewide Florida expansion, and geospatial analysis are not part of V0 and are not complete.
