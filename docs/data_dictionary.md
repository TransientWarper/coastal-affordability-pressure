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

## manual/florida_counties.csv

Source-neutral authoritative reference for all 67 Florida counties used by
statewide pipeline stages. County FIPS—not county name—is the authoritative join
and selection key.

| Field | Type | Description |
|---|---|---|
| state | string | Two-letter state abbreviation (`FL`) |
| county_fips | string | Five-character county GEOID/FIPS code (state + county, zero-padded), e.g. `12086` |
| county_name | string | Census cartographic county label (`NAMELSAD`) |

### Provenance

- **Source:** US Census Bureau Cartographic Boundary File, county level, 500k
  resolution, vintage 2023
- **Archive path:** `data/raw/census_tiger/cb_2023_us_county_500k.zip`
- **Row count:** 67 (one row per Florida county)
- **FIPS rule:** five-character strings matching `^12\d{3}$`

### Role

Shared geographic reference for statewide pipelines. ACS acquisition loads this
file directly and does **not** depend on processed Zillow outputs. County names
are used for output labeling only; joins and validation use `county_fips`.

---

## manual/pipeline_states.csv

State manifest for the multistate county-reference layer and future pipeline
expansion. Defines which states are included in the southeastern pilot scope.

| Field | Type | Description |
|---|---|---|
| state | string | Two-letter state abbreviation (e.g. `FL`) |
| state_fips | string | Two-character Census state FIPS code, zero-padded (e.g. `12`) |
| include_pipeline | boolean | When true, state counties are included in `pipeline_counties.csv` |

### Validated record (southeastern pilot)

| state | state_fips | include_pipeline |
|---|---|---|
| FL | 12 | true |
| GA | 13 | true |
| SC | 45 | true |
| NC | 37 | true |

Four enabled states; all rows currently have `include_pipeline=true`.

---

## manual/pipeline_counties.csv

Authoritative multistate county reference for the four-state southeastern pilot
(Florida, Georgia, South Carolina, North Carolina). County FIPS—not county
name—is the authoritative join and selection key.

| Field | Type | Description |
|---|---|---|
| state | string | Two-letter state abbreviation from TIGER `STUSPS` |
| state_fips | string | Two-character Census state FIPS code from TIGER `STATEFP` |
| county_fips | string | Five-character county GEOID/FIPS code from TIGER `GEOID` |
| county_name | string | Census cartographic county label from TIGER `NAMELSAD` |

### Provenance

- **Source:** US Census Bureau Cartographic Boundary File, county level, 500k
  resolution, vintage 2023
- **Archive path:** `data/raw/census_tiger/cb_2023_us_county_500k.zip`
- **Generation script:** `src/build_pipeline_county_reference.py`
- **State filter:** enabled `state_fips` values from `pipeline_states.csv`
- **Row count:** 372 (one row per county in the enabled states)

### Expected state counts

| state | state_fips | counties |
|---|---|---:|
| FL | 12 | 67 |
| GA | 13 | 159 |
| SC | 45 | 46 |
| NC | 37 | 100 |
| **Total** | | **372** |

### Role

Shared geographic reference for multistate pipeline expansion. Generated
deterministically from TIGER; not hand-edited. County names are used for output
labeling only; joins and validation use `county_fips`.

### Relationship to florida_counties.csv

`pipeline_counties.csv` is the multistate successor reference for new pipeline
stages. `florida_counties.csv` is preserved unchanged for existing Florida-only
scripts and validated outputs. The Florida subset of `pipeline_counties.csv`
must exactly match `florida_counties.csv` on `state`, `county_fips`, and
`county_name`.

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

## processed/zillow_zhvi_pipeline_counties_annual_2015_2024.csv

FIPS-based annualized Zillow ZHVI for the four-state southeastern pipeline
reference (Florida, Georgia, South Carolina, North Carolina). One row per county
per year.

| Field | Type | Units | Description |
|---|---|---|---|
| state | string | — | Two-letter state abbreviation from `pipeline_counties.csv` |
| county_fips | string | — | Five-character county FIPS code; authoritative selection and join key |
| county_name | string | — | County name from `pipeline_counties.csv` (TIGER `NAMELSAD`) |
| year | integer | calendar year | Reference year for the county-year observation |
| typical_home_value | float | US dollars | Arithmetic mean of monthly county ZHVI within the calendar year; null when source months are unavailable |
| zillow_months_available | integer | count (months) | Number of monthly ZHVI observations used in the annual mean |
| zillow_data_status | string | — | Month-coverage status (see below) |
| home_value_source | string | — | Source label (`Zillow ZHVI county`) |
| home_value_year_method | string | — | Annualization method (`annual_mean_zhvi`) |

### Grain and key

- **Grain:** county-year
- **Primary key:** (`county_fips`, `year`)
- **Expected scale:** 3,720 rows (372 counties × 10 years)
- **Geography:** FL (67), GA (159), SC (46), NC (100)
- **Years:** 2015–2024
- **County reference:** `data/manual/pipeline_counties.csv`
- **Selection key:** five-digit `county_fips` matched to Zillow
  `StateCodeFIPS` + `MunicipalCodeFIPS`; county name is not used for selection

### Annualization method

Monthly ZHVI is converted to an annual value using the **arithmetic mean** of
all available monthly county ZHVI values within each calendar year. Missing
months are not interpolated, imputed, or backfilled.

### zillow_data_status

| Value | Meaning |
|---|---|
| `complete_12_months` | All 12 monthly ZHVI observations present for the calendar year |
| `partial_10_11_months` | Annual mean calculated from 10 or 11 available months |
| `partial_1_9_months` | Annual mean calculated from 1–9 available months; retained when usable monthly values exist but coverage is below the Florida comparable threshold |
| `source_data_unavailable` | No usable monthly observations (0 months); `typical_home_value` is null |

### Counties absent from Zillow

The pipeline builds a complete county-year panel from
`pipeline_counties.csv`. Counties absent from the Zillow raw file retain all
10 county-year rows with null `typical_home_value`, `zillow_months_available = 0`,
and `zillow_data_status = source_data_unavailable`.

### Relationship to Florida output

The Florida subset (`state = FL`) matches the committed
`zillow_zhvi_florida_counties_annual_2015_2024.csv` on analytical columns:
`state`, `county_fips`, `year`, `typical_home_value`,
`zillow_months_available`, `home_value_source`, `home_value_year_method`, and
`zillow_data_status`. Output labels use TIGER-based county names from
`pipeline_counties.csv`, which may differ in spelling from Zillow `RegionName`
for a small number of Florida counties.

The existing Florida output file is not overwritten by the pipeline build path
beyond the unchanged Florida transformation stage.

### Generation

Built by `src/transform_zillow_zhvi.py` from:

- `data/raw/zillow_zhvi/zillow_zhvi_county_raw.csv`
- `data/manual/pipeline_counties.csv`

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

## processed/acs_b19013_florida_counties_2015_2024.csv

FIPS-based ACS 5-year median household income for all 67 Florida counties. One
row per county per year.

| Field | Type | Units | Description |
|---|---|---|---|
| state | string | — | Two-letter state abbreviation (`FL`) |
| county_fips | string | — | Five-character county FIPS code; authoritative selection and join key |
| county_name | string | — | County name from the established Florida county reference panel |
| year | integer | ACS release year | ACS 5-year estimate release year (2015–2024) |
| median_household_income | integer | US dollars | ACS table B19013 variable `B19013_001E` |
| income_source | string | — | Source label (`ACS {year} 5-year B19013`) |

### Grain and key

- **Grain:** county-year
- **Primary key:** (`county_fips`, `year`)
- **Expected scale:** 670 rows (67 counties × 10 years)
- **County reference:** five-digit `county_fips` values and labels from
  `data/manual/florida_counties.csv` (Census TIGER 2023); county name is not
  used for selection or joins

### Census acquisition

- **Dataset:** ACS 5-year (`acs/acs5`)
- **Variable:** B19013 / `B19013_001E` (median household income)
- **Request pattern:** one Florida-wide request per release year:
  - `get=NAME,B19013_001E`
  - `for=county:*`
  - `in=state:12`
- **Total requests:** 10 (2015–2024)
- **FIPS construction:** `state` (2-digit) + `county` (3-digit), zero-padded to
  five characters

### Validation rules

- Each annual response must contain exactly 67 Florida counties
- Returned FIPS must exactly match the authoritative Florida county reference
- Fail on duplicate keys, missing county-years, unexpected FIPS, null or
  nonnumeric income, nonpositive income, and Census suppression sentinels
- No imputation or manual value entry

### Relationship to legacy and pilot outputs

- Miami-Dade legacy file
  `data/raw/acs_income/acs_b19013_miami_dade_2015_2024.csv` is regenerated from
  the same acquisition snapshot; Miami-Dade rows match on income fields
- Three-county pilot file
  `data/processed/acs_b19013_selected_counties_2015_2024.csv` is **not**
  overwritten; Broward, Miami-Dade, and Palm Beach rows in this Florida output
  match the committed pilot file on all comparable ACS fields

### Validated record

- Geography: all 67 Florida counties
- Years: 2015–2024 per county
- Row count: 670
- Nulls: 0
- Duplicate county-year keys: 0

---

## processed/acs_b19013_pipeline_counties_2015_2024.csv

FIPS-based ACS 5-year median household income for the four-state southeastern
pipeline reference (Florida, Georgia, South Carolina, North Carolina). One row
per county per year.

| Field | Type | Units | Description |
|---|---|---|---|
| state | string | — | Two-letter state abbreviation from `pipeline_counties.csv` |
| county_fips | string | — | Five-character county FIPS code; authoritative selection and join key |
| county_name | string | — | County name from `pipeline_counties.csv` (TIGER `NAMELSAD`) |
| year | integer | ACS release year | ACS 5-year estimate release year (2015–2024) |
| median_household_income | integer | US dollars | ACS table B19013 variable `B19013_001E`; null when unavailable |
| income_source | string | — | Source label (`ACS {year} 5-year B19013`) |
| acs_data_status | string | — | Availability status (`available`, `source_data_unavailable`) |

### Grain and key

- **Grain:** county-year
- **Primary key:** (`county_fips`, `year`)
- **Expected scale:** 3,720 rows (372 counties × 10 years)
- **Geography:** FL (67), GA (159), SC (46), NC (100)
- **Years:** 2015–2024
- **County reference:** `data/manual/pipeline_counties.csv`

### Census acquisition

- **Dataset:** ACS 5-year (`acs/acs5`)
- **Variable:** B19013 / `B19013_001E` (median household income)
- **Request pattern:** one state-scoped request per release year for each
  enabled state in `pipeline_states.csv`:
  - `get=NAME,B19013_001E`
  - `for=county:*`
  - `in=state:{state_fips}`
- **Total requests:** 40 (4 states × 10 years)
- **FIPS construction:** `state` (2-digit) + `county` (3-digit), zero-padded to
  five characters

### acs_data_status

| Value | Meaning |
|---|---|
| `available` | Valid positive median household income returned by ACS |
| `source_data_unavailable` | Missing, suppressed, malformed, or absent ACS value; `median_household_income` is null |

### Missing-value policy

County-year rows are retained even when ACS returns suppression sentinels,
missing values, malformed values, or omits the county from a response. Missing
values are never imputed or interpolated.

### Relationship to Florida output

The Florida subset (`state = FL`) matches the committed
`acs_b19013_florida_counties_2015_2024.csv` on analytical columns:
`state`, `county_fips`, `year`, `median_household_income`, and
`income_source`. Output labels use TIGER-based county names from
`pipeline_counties.csv`, which may differ in spelling from
`florida_counties.csv` for a small number of Florida counties.

### Generation

Built by `src/fetch_acs_income.py` from:

- `data/manual/pipeline_states.csv`
- `data/manual/pipeline_counties.csv`
- Census ACS 5-year API (`acs/acs5`, table B19013)

---

## processed/coastal_affordability_pipeline_2015_2024.csv

Four-state pipeline affordability table joining validated Zillow home values and
ACS median household income. One row per county per year.

| Field | Type | Units | Description |
|---|---|---|---|
| state | string | — | Two-letter state abbreviation from `pipeline_counties.csv` |
| county_fips | string | — | Five-character county FIPS code; authoritative join key |
| county_name | string | — | County name from `pipeline_counties.csv` |
| year | integer | calendar year | Reference year for the county-year observation |
| typical_home_value | float | US dollars | Annualized Zillow ZHVI typical home value; null when source months are unavailable |
| median_household_income | integer | US dollars | ACS 5-year median household income (table B19013) |
| home_value_to_income_ratio | float | ratio (unitless) | `typical_home_value / median_household_income`; null when home value is null |
| zillow_months_available | integer | count (months) | Number of monthly ZHVI observations used in the annual mean |
| zillow_data_status | string | — | Zillow month-coverage status from the pipeline ZHVI input |
| acs_data_status | string | — | ACS availability status from the pipeline income input |
| affordability_data_status | string | — | Combined affordability availability status (see below) |
| home_value_source | string | — | Source label for the home value estimate (`Zillow ZHVI county`) |
| home_value_year_method | string | — | Annualization method (`annual_mean_zhvi`) |
| income_source | string | — | Source label for the income estimate (`ACS {year} 5-year B19013`) |

### Grain and key

- **Grain:** county-year
- **Primary key:** (`county_fips`, `year`)
- **Expected scale:** 3,720 rows (372 counties × 10 years)
- **Geography:** FL (67), GA (159), SC (46), NC (100)
- **Years:** 2015–2024
- **Join keys:** `county_fips` and `year` only; county name is not used for joining

### Source inputs

- `data/processed/zillow_zhvi_pipeline_counties_annual_2015_2024.csv`
- `data/processed/acs_b19013_pipeline_counties_2015_2024.csv`
- `data/manual/pipeline_counties.csv` (authoritative county labels)

### Ratio formula

```
home_value_to_income_ratio = typical_home_value / median_household_income
```

The ratio is stored rounded to four decimal places. It is a unitless multiple:
home value expressed as a multiple of median household income. It is not stored
as a percentage. When `typical_home_value` is null, the ratio is left null.

Baseline-change and growth-index fields are deferred to a later checkpoint.

### affordability_data_status

| Value | Meaning |
|---|---|
| `available_complete` | 12 Zillow months, ACS available, both values present, ratio calculated |
| `available_partial` | Partial Zillow month coverage (1–11 months), ACS available, both values present, ratio calculated |
| `source_data_unavailable` | Missing or unavailable Zillow and/or ACS value; ratio is null |

Original `zillow_data_status` and `acs_data_status` columns are retained.

### Missing-value policy

Missing home values are never imputed, interpolated, forward-filled, or
substituted. County-year rows with unavailable Zillow data are retained with
null `typical_home_value` and null `home_value_to_income_ratio`.

### Relationship to Florida output

The Florida subset (`state = FL`) matches the committed
`coastal_affordability_florida_2015_2024.csv` on shared analytical columns.
Output labels use `pipeline_counties.csv`, which matches `florida_counties.csv`
for Florida counties.

### Generation

Built by `src/build_pipeline_affordability_table.py`.

---

## processed/coastal_affordability_florida_2015_2024.csv

Statewide Florida affordability table joining validated Zillow home values and
ACS median household income. One row per county per year.

| Field | Type | Units | Description |
|---|---|---|---|
| state | string | — | Two-letter state abbreviation (`FL`) |
| county_fips | string | — | Five-character county FIPS code; authoritative join key |
| county_name | string | — | County name from `data/manual/florida_counties.csv` |
| year | integer | calendar year | Reference year for the county-year observation |
| typical_home_value | float | US dollars | Annualized Zillow ZHVI typical home value; null when source months are unavailable |
| median_household_income | integer | US dollars | ACS 5-year median household income (table B19013) |
| home_value_to_income_ratio | float | ratio (unitless) | `typical_home_value / median_household_income`; null when home value is null |
| zillow_months_available | integer | count (months) | Number of monthly ZHVI observations used in the annual mean |
| zillow_data_status | string | — | Zillow month-coverage status from the Florida ZHVI input |
| home_value_source | string | — | Source label for the home value estimate (`Zillow ZHVI county`) |
| home_value_year_method | string | — | Annualization method (`annual_mean_zhvi`) |
| income_source | string | — | Source label for the income estimate (`ACS {year} 5-year B19013`) |

### Grain and key

- **Grain:** county-year
- **Primary key:** (`county_fips`, `year`)
- **Expected scale:** 670 rows (67 counties × 10 years)
- **Join keys:** `county_fips` and `year` only; county name is not used for joining

### Source inputs

- `data/processed/zillow_zhvi_florida_counties_annual_2015_2024.csv`
- `data/processed/acs_b19013_florida_counties_2015_2024.csv`
- `data/manual/florida_counties.csv` (authoritative 67-county FIPS reference)

### Ratio formula

```
home_value_to_income_ratio = typical_home_value / median_household_income
```

The ratio is stored rounded to four decimal places. It is a unitless multiple:
home value expressed as a multiple of median household income. When
`typical_home_value` is null, the ratio is left null.

### Monroe County 2015 null policy

Monroe County (`12087`) 2015 retains the documented Zillow source-data exception.
That county-year row is kept in the 670-row panel with:

- null `typical_home_value`
- null `home_value_to_income_ratio`
- populated `median_household_income`
- `zillow_data_status = source_data_unavailable`

Missing home values are never imputed, interpolated, or replaced with zero.

### Zillow status distribution (validated)

| zillow_data_status | row count |
|---|---|
| `complete_12_months` | 668 |
| `partial_10_11_months` | 1 |
| `source_data_unavailable` | 1 |

### Relationship to V0 and pilot outputs

- Miami-Dade rows match `coastal_affordability_county_v0.csv` on comparable
  analytical columns; the V0 file retains a `notes` column and does not include
  `zillow_data_status`
- Broward, Miami-Dade, and Palm Beach rows match a direct join of the statewide
  Zillow and ACS input files

### Validated record

- Geography: all 67 Florida counties
- Years: 2015–2024 per county
- Row count: 670
- Null home values: 1 (Monroe 2015 only)
- Null ratios: 1 (Monroe 2015 only)
- Duplicate county-year keys: 0

---

## processed/florida_affordability_2015_2024.gpkg

QGIS-ready GeoPackage joining the statewide Florida affordability table to
authoritative Census county geometry.

| Property | Value |
|---|---|
| **Path** | `data/processed/florida_affordability_2015_2024.gpkg` |
| **Layer** | `florida_affordability_county_year` |
| **Feature grain** | county-year (one geometry-bearing feature per county per year) |
| **Feature count** | 670 |
| **Primary key** | (`county_fips`, `year`) |
| **Join key** | `county_fips` (analytical) = `GEOID` (TIGER) |
| **Boundary source** | `data/raw/census_tiger/cb_2023_us_county_500k.zip` |
| **TIGER vintage** | 2023 |
| **CRS** | EPSG:4269 (NAD83) |
| **Geometry type** | county polygons (`Polygon`, `MultiPolygon`) |

### Analytical attributes

Each feature retains the statewide affordability fields:

- `state`, `county_fips`, `county_name`, `year`
- `typical_home_value`, `median_household_income`, `home_value_to_income_ratio`
- `zillow_months_available`, `zillow_data_status`
- `home_value_source`, `home_value_year_method`, `income_source`
- `geometry`

Redundant TIGER attributes are not retained. `county_fips` is the analytical
join key and matches TIGER `GEOID`; a duplicate GEOID column is not exported.

### Geometry note

County geometry is repeated for each year: 67 county polygons × 10 years =
670 features. The 2023 TIGER boundaries represent a consistent current geometry
for all years 2015–2024; they do not represent year-specific historical
boundaries.

### Monroe County 2015 null treatment

Monroe County (`12087`) 2015 retains geometry with:

- null `typical_home_value`
- null `home_value_to_income_ratio`
- populated `median_household_income`
- `zillow_data_status = source_data_unavailable`

No imputation is applied.

### Intended QGIS usage

Load the layer `florida_affordability_county_year` for statewide choropleth or
filtered mapping by `year`, `home_value_to_income_ratio`, or
`zillow_data_status`. Style and layout work are out of scope for this artifact.

### Source table

Built from `data/processed/coastal_affordability_florida_2015_2024.csv`.

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
