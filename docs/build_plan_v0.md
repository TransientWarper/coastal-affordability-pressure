# Build Plan V0

## Goal

Build a clean county-year table for Miami-Dade County showing median household income, typical home value, and the home value-to-income ratio from 2015-2024.

## Planned Steps

1. Load selected county list from data/manual/selected_counties.csv
2. Fetch or load ACS B19013 median household income data
3. Fetch or load Zillow ZHVI county-level home value data
4. Filter both sources to Miami-Dade County
5. Convert monthly ZHVI values to annual mean values
6. Join income and home value data by county and year
7. Calculate home_value_to_income_ratio
8. Export final CSV to data/processed/coastal_affordability_county_v0.csv
9. Update QA report
10. Commit working output

## V0 Output

data/processed/coastal_affordability_county_v0.csv

## Expected Grain

One row per county per year.

## Expected Row Count

10 rows.
