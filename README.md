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

Project foundation created. Data ingestion and transformation not yet started.
