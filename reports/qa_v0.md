# QA Report V0

## Scope

Miami-Dade County, Florida

County FIPS: `12086`

Years: 2015–2024

Final output: `data/processed/coastal_affordability_county_v0.csv`

Rebuild command (repository root):

```bash
.venv/bin/python src/build_affordability_table.py
```

## Validated Results

| Check | Result |
|---|---|
| Row count | 10 |
| Year range | 2015–2024 |
| County FIPS | `12086` (all rows) |
| Null count (final dataframe) | 0 |
| Duplicate county-year keys | 0 |
| Zillow month coverage (`zillow_months_available`) | 12 for all rows |
| Ratio range (`home_value_to_income_ratio`) | 5.6107 (2015) to 7.4636 (2024) |

## Checklist

| Check | Status | Evidence |
|---|---|---|
| Selected county FIPS is 12086 | **Passed** | Final output and build validation require `county_fips` = `12086` on every row |
| ACS income rows exist for each year 2015–2024 | **Passed** | Build script validates 10 ACS rows covering years 2015–2024 before join |
| Zillow ZHVI rows exist for Miami-Dade County | **Passed** | Processed Zillow input contains 10 Miami-Dade rows, one per year |
| Monthly ZHVI values available for each year 2015–2024 | **Passed** | `zillow_months_available` = 12 for all 10 final rows |
| No duplicate county-year rows in final output | **Passed** | Duplicate county-year count = 0 |
| No null values in required final fields | **Passed** | Null count = 0 across final dataframe |
| Ratio calculation is numeric and reasonable | **Passed** | Ratios computed as `typical_home_value / median_household_income`, rounded to 4 decimals; range 5.6107–7.4636 with monotonic increase in underlying home values and incomes |

## Final Output Checks

Expected grain: one row per county per year. **Passed** (10 rows, single county, 10 years).

Expected row count for V0: 10. **Passed**.

## Out of Scope for V0 QA

The following have **not** been validated in V0:

- Statewide Florida county coverage
- Geospatial or mapping outputs
- External benchmark or third-party plausibility comparison
- Tract-level or metro-level analysis

## Unresolved Items (Future Work)

- **Geographic expansion** — extend beyond Miami-Dade to additional coastal counties and, eventually, statewide Florida coverage
- **Mapping** — produce geospatial views of affordability pressure (not started)
- **Broader plausibility comparison** — compare county ratios to external benchmarks, peer counties, or independent housing-cost indices
