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
