# Methodology V0

## Project Thesis

Housing capital is entering some coastal places faster than local income can keep up.

## V0 Geography

V0 uses Miami-Dade County, Florida as a single-county case study.

County FIPS: 12086

Statewide Florida expansion, mapping, and geospatial analysis are out of scope for V0.

## V0 Time Window

2015-2024

## V0 Grain

County-year.

Each row represents one county in one year.

## Income Metric

Median household income from the ACS 5-year estimate, table B19013 (`B19013_001E`).

Source file: `data/raw/acs_income/acs_b19013_miami_dade_2015_2024.csv`

Each row corresponds to one ACS 5-year release year (2015 through 2024).

## Home Value Metric

Typical home value from Zillow ZHVI county-level data.

Processed file: `data/processed/zillow_zhvi_miami_dade_annual_2015_2024.csv`

## Annual Home Value Method

Zillow ZHVI is published monthly at the county level. V0 converts monthly ZHVI into an annual value using the **arithmetic mean** of all available monthly county ZHVI values within each calendar year.

Field name: `typical_home_value`

Method label: `annual_mean_zhvi`

Observation count field: `zillow_months_available`

For the current V0 dataset, all years 2015–2024 use **12** monthly observations.

## Join

Income and home value are joined on:

- `county_fips` (five-character string)
- `year` (integer)

The join is an inner merge with one-to-one validation on county-year keys. County names are not used as join keys.

Build script: `src/build_affordability_table.py`

## Affordability Pressure Metric

```
home_value_to_income_ratio = typical_home_value / median_household_income
```

The ratio is rounded to **four decimal places** in the final output.

V0 observed range for Miami-Dade: **5.6107** (2015) to **7.4636** (2024).

## Limitations

**ACS 5-year estimates are overlapping multi-year estimates.** Each release pools five years of survey data. They are useful for stable county-level comparisons but are not single-year point-in-time measurements.

**Zillow ZHVI and ACS income measure different concepts.** ZHVI reflects a modeled typical home value for the county; ACS B19013 reflects median household income across all households. The ratio describes county-level pressure between these two aggregate measures. It should not be interpreted as an individual household purchase-qualification metric, mortgage affordability score, or cost-of-living index.

## V0 Exclusions

V0 does not include rent data, mortgage payment estimates, interest rates, insurance costs, property taxes, permit data, tract-level analysis, maps, statewide expansion, or scoring labels.
