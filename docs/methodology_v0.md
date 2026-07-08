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

---

## BEA Total Personal Income (added after initial V0)

The pipeline was extended to include a second income series from the U.S. Bureau
of Economic Analysis.

**Source:** BEA Regional Economic Accounts, CAINC1 (County and MSA Personal
Income Summary), Line 1.

**Concept:** Total personal income — the aggregate income received by all
residents of the county from all sources in a given year. This is an
economy-wide total, not a per-household or per-person figure.

**Unit as received:** Thousands of current dollars.

**Unit in processed output:** Whole dollars (`personal_income = data_value × 1000`).

**Raw file:** `data/raw/bea_income/bea_cainc1_miami_dade_2015_2024.csv`

**Processed file:** `data/processed/bea_income_miami_dade_2015_2024.csv`

**Why a second income series?**
ACS median household income and BEA total personal income measure different
things. ACS B19013 is a point in the income distribution — the household income
at the 50th percentile, based on a survey sample. BEA CAINC1 is an aggregate
flow — the sum of all income accruing to county residents, derived from
administrative records and national accounts. Comparing home value growth to
both series is more informative than relying on either alone. Neither series is
a measure of total housing-market capitalization.

---

## Growth Comparison Metrics (added after initial V0)

The growth comparison table (`miami_dade_bea_growth_comparison_2015_2024.csv`)
is built by `src/build_bea_growth_comparison.py` from the two processed inputs
above. It adds four indexed series and one gap measure to the existing
county-year affordability data.

**2015-indexed series**

Each index is calculated as:

```
index = (value in year / value in 2015) × 100
```

All four index columns equal exactly 100.00 in 2015 by construction.

| Column | Source field |
|---|---|
| `typical_home_value_index_2015` | `typical_home_value` |
| `median_household_income_index_2015` | `median_household_income` |
| `personal_income_index_2015` | `personal_income` |
| `affordability_ratio_index_2015` | `home_value_to_income_ratio` |

**Growth gap**

```
home_value_growth_minus_personal_income_growth =
    typical_home_value_index_2015 - personal_income_index_2015
```

A positive value means representative home values have grown faster than total
personal income since 2015, expressed in index points. The gap is zero in 2015
by construction.

---

## Current Miami-Dade Findings (2015–2024)

These figures are drawn from the generated processed files and should be
updated if source data is refreshed.

**Home-value-to-income ratio (ACS median household income)**

| Year | Ratio |
|---|---|
| 2015 | 5.6107 |
| 2024 | 7.4636 |

A typical Miami-Dade home cost roughly 5.6 times the county's median annual
household income in 2015. By 2024 that multiple had risen to roughly 7.5.

**2015-indexed growth comparison**

| Series | 2015 index | 2024 index |
|---|---|---|
| Typical home value | 100.00 | 221.31 |
| BEA total personal income | 100.00 | 189.67 |
| Gap (home value minus personal income) | 0.00 | 31.65 |

Representative home values grew roughly 121 percent between 2015 and 2024;
total personal income grew roughly 90 percent over the same period. The gap
widened steadily from 2015 through 2020, accelerated sharply between 2021 and
2022 (the gap jumped from about 7 to about 25 index points), and continued
widening through 2024.

**Interpretation**

Representative home value growth in Miami-Dade outpaced both median household
income growth and total personal income growth over this period. This is a
descriptive finding. It does not by itself establish why the gap widened or
what would be required to close it.

This is not a measure of the total residential asset base. ZHVI is a modeled
estimate of a representative home value, not a count of housing units or an
aggregate housing market value. Estimating total residential asset-base growth
would require housing unit counts, assessed values, parcel data, or a similar
housing-stock measure, which are not part of this pipeline.

---

## Limitations (extended)

The limitations in the original section above apply to the BEA comparison as
well. Additional limitations specific to the growth comparison:

- **Miami-Dade only.** The growth patterns observed here may not hold in other
  counties. This is a proof of concept, not a representative sample.
- **County-level only.** County aggregates conceal variation across
  neighborhoods, income groups, and housing types.
- **ACS and BEA measure different concepts.** ACS B19013 is a median derived
  from a household survey. BEA CAINC1 is an aggregate from administrative and
  national accounts data. Both are reported in nominal dollars with no inflation
  adjustment applied here.
- **ZHVI is not total housing market capitalization.** The index represents a
  modeled typical home value within a county-level distribution. It is not the
  same as total county residential asset value.
- **2024 data comparability.** Both ACS and BEA 2024 estimates are recent
  releases. Their methodologies and revisions should be checked as sources
  update over time.
- **No causal identification.** The gap between home value growth and income
  growth is documented here. The pipeline does not test any causal explanation.

---

## Next Steps

The following are potential directions, listed roughly in order of incremental
effort. None of these is currently implemented.

1. **Housing unit counts or assessed values.** To estimate total residential
   asset-base growth rather than just representative home value growth, add a
   housing unit or assessed-value series (e.g., from the Census ACS B25001,
   county property records, or CoreLogic) and join it to the existing pipeline.

2. **Additional Florida coastal counties.** The pipeline is designed around a
   county-FIPS join key and should extend naturally to other Florida counties
   once the selected_counties.csv and acquisition scripts are updated.

3. **Map and table outputs.** Produce county-level choropleth or ranked-table
   outputs only after the county-level pipeline is stable for multiple counties.
   Single-county maps add little value.

4. **README update.** Update the README with a concise project summary that
   reflects both the ACS/ZHVI ratio and the BEA growth comparison once the
   methodology is stable.
