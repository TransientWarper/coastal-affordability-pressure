# QA Report V0

## Scope

Miami-Dade County, Florida  
Years: 2015-2024

## Checks To Complete

- Confirm selected county FIPS is 12086
- Confirm ACS income rows exist for each year 2015-2024
- Confirm Zillow ZHVI rows exist for Miami-Dade County
- Confirm monthly ZHVI values are available for each year 2015-2024
- Confirm no duplicate county-year rows in final output
- Confirm no null values in required final fields
- Confirm ratio calculation is numeric and reasonable

## Final Output Checks

Expected final grain:

One row per county per year.

Expected row count for V0:

10 rows.
