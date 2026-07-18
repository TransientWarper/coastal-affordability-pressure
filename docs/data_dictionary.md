# Data Dictionary

## manual/selected_counties.csv

Manual county selection list used to drive pipeline geography. County FIPS—not
county name—is the authoritative join and selection key across pipeline stages.

| Field | Type | Description |
|---|---|---|
| state | string | Two-letter state abbreviation (e.g. `FL`) |
| county_fips | string | Five-character county FIPS code (state + county, zero-padded), e.g. `12086` |
| county_name | string | County name for project metadata and output labeling |
| selection_phase | integer | Selection phase number (1 = V0 case study; 2 = first expansion pilot) |
| selection_reason | string | Brief rationale for county inclusion |
| include_v0 | boolean | When true, county is part of the validated Miami-Dade V0 proof of concept |
| include_pipeline | boolean | When true, county is included in the FIPS-based pipeline expansion outputs |
| notes | string | Optional project notes for the selected county |

### Selection flags

- **`include_v0`** — Marks counties consumed by the original single-county V0
  affordability pipeline. Exactly one county (`12086`, Miami-Dade) has
  `include_v0=true`. Downstream V0 scripts require this constraint.
- **`include_pipeline`** — Marks counties included in multi-county processed
  outputs. The first expansion pilot sets `include_pipeline=true` for Miami-Dade,
  Broward (`12011`), and Palm Beach (`12099`).

A county may have `include_pipeline=true` without `include_v0=true` (expansion
counties). Miami-Dade has both flags set to true.

---

## raw/zillow_zhvi/zillow_zhvi_county_raw.csv

County-level Zillow ZHVI monthly source file used by `src/transform_zillow_zhvi.py`
and `src/fetch_zillow_zhvi.py`.

### Active source vintage

| Property | Value |
|---|---|
| **Path** | `data/raw/zillow_zhvi/zillow_zhvi_county_raw.csv` |
| **Retrieval date** | 2026-07-18 |
| **Source URL** | `https://files.zillowstatic.com/research/public_csvs/zhvi/County_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv` |
| **MD5** | `4c1a295bb2cd26fed8e7f02ac3cb3c66` |
| **Size** | 13,465,693 bytes |
| **Rows** | 3,071 county records |

### Archived prior vintage

| Property | Value |
|---|---|
| **Path** | `data/raw/zillow_zhvi/archive/zillow_zhvi_county_raw_2026-06-11.csv` |
| **File modification date** | 2026-06-11 |
| **MD5** | `cb42706be9f8afef1286417742aa4941` |
| **Size** | 13,347,520 bytes |
| **Rows** | 3,072 county records |

The archived file is a byte-identical preservation of the prior active raw
source. It is not overwritten by fetch runs.

### Source-vintage effects

Zillow may revise historical ZHVI values when a new county-level export is
published. After the 2026-07-18 refresh:

- `data/processed/zillow_zhvi_miami_dade_annual_2015_2024.csv` was regenerated
  from the active raw source and differs from the prior committed version
- `data/processed/coastal_affordability_county_v0.csv` was regenerated accordingly
  because it joins the refreshed Miami-Dade ZHVI series
- `data/processed/zillow_zhvi_selected_counties_annual_2015_2024.csv` was **not**
  overwritten; it remains the prior committed three-county pilot output
- `data/processed/zillow_zhvi_florida_counties_annual_2015_2024.csv` is built
  from the active raw source; its Broward, Miami-Dade, and Palm Beach rows match
  a freshly generated in-memory three-county subset from the same vintage

Missing Zillow months are never imputed. Monroe County (`12087`) 2015 retains a
documented null source exception when the active source supplies 0 monthly
observations (see Florida processed output section below).

---

## processed/zillow_zhvi_selected_counties_annual_2015_2024.csv

FIPS-based annualized Zillow ZHVI for the first Florida pipeline expansion pilot.
One row per county per year.

| Field | Type | Units | Description |
|---|---|---|---|
| state | string | — | Two-letter state abbreviation from `selected_counties.csv` |
| county_fips | string | — | Five-character county FIPS code; authoritative selection and join key |
| county_name | string | — | County name from `selected_counties.csv` (not Zillow `RegionName`) |
| year | integer | calendar year | Reference year for the county-year observation |
| typical_home_value | float | US dollars | Arithmetic mean of monthly county ZHVI within the calendar year |
| zillow_months_available | integer | count (months) | Number of monthly ZHVI observations used in the annual mean |
| home_value_source | string | — | Source label (`Zillow ZHVI county`) |
| home_value_year_method | string | — | Annualization method (`annual_mean_zhvi`) |

### Grain and key

- **Grain:** county-year
- **Primary key:** (`county_fips`, `year`)
- **Selection key:** five-digit `county_fips` matched to Zillow
  `StateCodeFIPS` + `MunicipalCodeFIPS`; county name is not used for selection

### Annualization method

Monthly ZHVI is converted to an annual value using the **arithmetic mean** of
all available monthly county ZHVI values within each calendar year. Missing
months are not interpolated.

### Selected counties (pilot)

| county_fips | county_name |
|---|---|
| 12086 | Miami-Dade County |
| 12011 | Broward County |
| 12099 | Palm Beach County |

### Validated record

- Geography: three pipeline counties listed above
- Years: 2015–2024 per county
- Row count: 30 (10 per county)
- Nulls: 0
- Duplicate county-year keys: 0
- Miami-Dade rows match `zillow_zhvi_miami_dade_annual_2015_2024.csv`

---

## processed/zillow_zhvi_florida_counties_annual_2015_2024.csv

FIPS-based annualized Zillow ZHVI for all 67 Florida counties. One row per
county per year.

| Field | Type | Units | Description |
|---|---|---|---|
| state | string | — | Two-letter state abbreviation (`FL`) |
| county_fips | string | — | Five-character county FIPS code; authoritative selection and join key |
| county_name | string | — | County name from Zillow `RegionName` |
| year | integer | calendar year | Reference year for the county-year observation |
| typical_home_value | float | US dollars | Arithmetic mean of monthly county ZHVI within the calendar year; null when source months are unavailable |
| zillow_months_available | integer | count (months) | Number of monthly ZHVI observations used in the annual mean |
| zillow_data_status | string | — | Month-coverage status (`complete_12_months`, `partial_10_11_months`, `source_data_unavailable`) |
| home_value_source | string | — | Source label (`Zillow ZHVI county`) |
| home_value_year_method | string | — | Annualization method (`annual_mean_zhvi`) |

### Grain and key

- **Grain:** county-year
- **Primary key:** (`county_fips`, `year`)
- **Selection key:** five-digit `county_fips` matched to Zillow
  `StateCodeFIPS` + `MunicipalCodeFIPS`

### Validated record

- Geography: all 67 Florida counties
- Years: 2015–2024 per county
- Row count: 670 (67 counties × 10 years)
- Duplicate county-year keys: 0
- Usable annual Zillow values: 669
- Pipeline subset (Broward, Miami-Dade, Palm Beach) matches a freshly generated
  in-memory three-county subset from the same active raw source vintage on all
  non-status columns; month counts also match the committed
  `zillow_zhvi_selected_counties_annual_2015_2024.csv` pilot file

### zillow_data_status

| Value | Meaning |
|---|---|
| `complete_12_months` | All 12 monthly ZHVI observations present for the calendar year |
| `partial_10_11_months` | Annual mean calculated from 10 or 11 available months; no imputation |
| `source_data_unavailable` | Approved source-data exception only; no annual value calculated |

### Month-coverage policy

- **12 months:** complete annual mean; `complete_12_months`
- **10–11 months:** annual mean from available months only; `partial_10_11_months`
- **Fewer than 10 months:** fail validation, except for the single approved
  exception below

Missing months are never imputed, interpolated, backfilled, or forward-filled.

### Monroe County source-data exception

Confirmed against the live Zillow county file retrieved on **2026-07-18**:

- Monroe County (`12087`), **2015**: 0 of 12 source months populated
- Monroe County (`12087`), **2016**: 11 of 12 source months populated
- All other Florida county-years (2015–2024): 12 source months populated

Approved exception tuple: (`12087`, `2015`).

For that county-year only:

- the row is retained in the 670-row panel
- `zillow_months_available = 0`
- `typical_home_value` is null
- `zillow_data_status = source_data_unavailable`
- no home value is manually supplied or imputed

Monroe County **2016** is not exempted. Its annual mean is calculated from the
11 available months (`2016-02-29` through `2016-12-31`; missing `2016-01-31`)
and is labeled `partial_10_11_months`.

If a future Zillow vintage supplies 10 or more source months for Monroe County
2015, the annual value is calculated normally and the exception is no longer
applied.

### Status distribution (validated)

| zillow_data_status | row count |
|---|---|
| `complete_12_months` | 668 |
| `partial_10_11_months` | 1 |
| `source_data_unavailable` | 1 |

---

## processed/acs_b19013_selected_counties_2015_2024.csv

FIPS-based ACS 5-year median household income for the first Florida pipeline
expansion pilot. One row per county per year.

| Field | Type | Units | Description |
|---|---|---|---|
| state | string | — | Two-letter state abbreviation from `selected_counties.csv` |
| county_fips | string | — | Five-character county FIPS code; authoritative selection and join key |
| county_name | string | — | County name from `selected_counties.csv` |
| year | integer | ACS release year | ACS 5-year estimate release year (2015–2024) |
| median_household_income | integer | US dollars | ACS table B19013 variable `B19013_001E` |
| income_source | string | — | Source label (`ACS {year} 5-year B19013`) |

### Grain and key

- **Grain:** county-year
- **Primary key:** (`county_fips`, `year`)
- **Selection dependency:** counties with `include_pipeline=true` in
  `data/manual/selected_counties.csv`

### ACS concept

- **Table / variable:** B19013 / `B19013_001E`
- **Concept:** median household income in the past 12 months
- **Years:** 2015–2024 ACS 5-year release years

Each `year` value is an ACS **release year** for a 5-year pooled estimate, not a
single-year point-in-time measurement.

### Selected counties (pilot)

| county_fips | county_name |
|---|---|
| 12086 | Miami-Dade County |
| 12011 | Broward County |
| 12099 | Palm Beach County |

### Relationship to legacy Miami-Dade output

The preserved legacy file
`data/raw/acs_income/acs_b19013_miami_dade_2015_2024.csv` contains Miami-Dade
(`12086`) rows derived from the same acquisition snapshot. Miami-Dade rows in
this processed file match the legacy file on `year`, `county_fips`,
`median_household_income`, and source labeling (`income_source` here vs
`source` in the legacy file).

### Validated record

- Geography: three pipeline counties listed above
- Years: 2015–2024 per county
- Row count: 30 (10 per county)
- Nulls: 0
- Duplicate county-year keys: 0

---

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
