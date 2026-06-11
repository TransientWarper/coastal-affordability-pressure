# Methodology V0

## Project Thesis

Housing capital is entering some coastal places faster than local income can keep up.

## V0 Geography

V0 uses Miami-Dade County, Florida as a single-county case study.

County FIPS: 12086

## V0 Time Window

2015-2024

## V0 Grain

County-year.

Each row should represent one county in one year.

## Income Metric

Median household income.

Source target:
ACS 5-year table B19013.

## Home Value Metric

Typical home value.

Source target:
Zillow ZHVI county-level data.

## Annual Home Value Method

Zillow ZHVI is monthly. V0 will convert monthly ZHVI into annual values using the mean of available monthly values for each calendar year.

Field name:
typical_home_value

Method label:
annual_mean_zhvi

## Affordability Pressure Metric

home_value_to_income_ratio = typical_home_value / median_household_income

## V0 Exclusions

V0 does not include rent data, mortgage payment estimates, interest rates, insurance costs, property taxes, permit data, tract-level analysis, maps, or scoring labels.
