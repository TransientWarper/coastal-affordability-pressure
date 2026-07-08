# Data Dictionary

## processed/coastal_affordability_county_v0.csv

Final V0 output for Miami-Dade County. One row per county per year.

| Field | Type | Units | Description |
|---|---|---|---|
| state | string | — | Two-letter state abbreviation (e.g. `FL`) |
| county_fips | string | — | Five-character county FIPS code (state + county, zero-padded), e.g. `12086` |
| county_name | string | — | County name |
| year | integer | calendar year | Reference year for the county-year observation |
| median_household_income | integer | US dollars | ACS 5-year median household income (table B19013) |
| typical_home_value | float | US dollars | Annualized Zillow ZHVI typical home value for the county |
| home_value_to_income_ratio | float | ratio (unitless) | `typical_home_value / median_household_income`, rounded to four decimal places |
| income_source | string | — | Source label for the income estimate (e.g. `ACS 2015 5-year B19013`) |
| home_value_source | string | — | Source label for the home value estimate (e.g. `Zillow ZHVI county`) |
| home_value_year_method | string | — | Method used to convert monthly ZHVI to an annual value (e.g. `annual_mean_zhvi`) |
| zillow_months_available | integer | count (months) | Number of monthly ZHVI observations used to compute the annual mean for that year; retained to document annualization completeness when future years may have partial coverage |
| notes | string | — | Optional project notes for the selected county |

### Ratio formula

```
home_value_to_income_ratio = typical_home_value / median_household_income
```

The ratio is stored rounded to four decimal places. It is a unitless multiple (home value expressed as a multiple of median household income).

### V0 validated record

- Geography: Miami-Dade County, Florida (`county_fips` = `12086`)
- Years: 2015–2024
- Row count: 10
- Nulls: 0
- Duplicate county-year keys: 0
- `zillow_months_available`: 12 for all rows

---

## processed/bea_income_miami_dade_2015_2024.csv

Processed BEA CAINC1 Line 1 total personal income for Miami-Dade County,
normalized from the raw BEA source file. One row per year.

| Field | Type | Units | Description |
|---|---|---|---|
| county_fips | string | — | Five-character county FIPS code, e.g. `12086` |
| county_name | string | — | County name as returned by the BEA API |
| year | integer | calendar year | Reference year |
| personal_income | integer | US dollars | Total personal income converted to whole dollars (`data_value × 1000`) |
| personal_income_thousands | integer | thousands of US dollars | Total personal income as reported by BEA (raw unit preserved for audit) |
| unit | string | — | BEA-reported unit label, e.g. `Thousands of dollars` |
| unit_mult | integer | — | BEA UNIT_MULT field; `3` means values are in thousands (10³) |
| code | string | — | BEA composite code, e.g. `CAINC1-1` (table name + line code) |
| line_code | integer | — | Integer line code extracted from `code`; `1` = Personal income |

### Notes

`personal_income` is the analytically useful field for joining to other dollar-denominated series. `personal_income_thousands` is retained to allow verification of the unit conversion without consulting the raw source.

BEA total personal income and ACS median household income measure different concepts. See `docs/methodology_v0.md` for a discussion.

---

## processed/miami_dade_bea_growth_comparison_2015_2024.csv

Growth comparison table joining the affordability dataset to the processed BEA
personal income series. Adds four 2015-indexed series and a home-value/income
growth gap measure. One row per year.

| Field | Type | Units | Description |
|---|---|---|---|
| county_fips | string | — | Five-character county FIPS code, e.g. `12086` |
| county_name | string | — | County name |
| year | integer | calendar year | Reference year |
| typical_home_value | float | US dollars | Annualized Zillow ZHVI typical home value |
| median_household_income | integer | US dollars | ACS 5-year median household income |
| personal_income | integer | US dollars | BEA total personal income (whole dollars) |
| home_value_to_income_ratio | float | ratio (unitless) | `typical_home_value / median_household_income`, four decimal places |
| typical_home_value_index_2015 | float | index (2015 = 100) | `typical_home_value / 2015 value × 100` |
| median_household_income_index_2015 | float | index (2015 = 100) | `median_household_income / 2015 value × 100` |
| personal_income_index_2015 | float | index (2015 = 100) | `personal_income / 2015 value × 100` |
| affordability_ratio_index_2015 | float | index (2015 = 100) | `home_value_to_income_ratio / 2015 value × 100` |
| home_value_growth_minus_personal_income_growth | float | index points | `typical_home_value_index_2015 − personal_income_index_2015`; positive means home values have grown faster than total personal income since 2015 |

### Index formula

All index columns are calculated as:

```
index = (value in year / value in 2015) × 100
```

Every index column equals exactly 100.0000 in 2015 by construction.

### V0 validated record

- Geography: Miami-Dade County, Florida (`county_fips` = `12086`)
- Years: 2015–2024
- Row count: 10
- Nulls: 0
- All index columns equal 100.0000 in 2015
- `typical_home_value_index_2015` in 2024: 221.31
- `personal_income_index_2015` in 2024: 189.67
- `home_value_growth_minus_personal_income_growth` in 2024: 31.65
