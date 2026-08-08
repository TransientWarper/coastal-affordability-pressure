# Coastal Affordability Pressure Tracker

A county-level housing affordability pressure pipeline demonstrating
end-to-end data acquisition, transformation, validation, stable geographic
joining, GIS output, and analytical communication. The current release is a
full, almost 31k row csv covering 47 states (CT, HI and AK excluded for now bc reasons)

---

## Research Question

How has the ratio of typical home value to median household income changed in
Miami-Dade County from 2015 to 2024, and how does that change compare with the
growth rates of each underlying measure?

---

## Metric

```
home_value_to_income_ratio = typical_home_value / median_household_income
```

A ratio of 5.0 means a typical home costs five times the county's median
annual household income. Higher ratios indicate that home values have grown
faster than incomes, making purchase less accessible to a median-income
household over time.

This metric is descriptive and is not a mortgage-affordability calculation. It
does not account for interest rates, property taxes, insurance, mortgage terms,
down-payment requirements, household debt, rental costs, or the distribution of
incomes and home values within the county.

---

## Data Sources

| Source | Series | Join key |
|---|---|---|
| Zillow ZHVI (county-level) | Typical home value, monthly → annualized | County FIPS |
| U.S. Census Bureau ACS 5-year estimates, table B19013 | Median household income | County FIPS |
| U.S. Census Cartographic Boundary file, 2023 vintage | County polygon geometry | GEOID (5-character FIPS string) |

Miami-Dade County GEOID/FIPS: **12086**

Geographic joins use the GEOID string identifier rather than county name to
avoid matching ambiguity. The 2023 boundary file is used as a consistent
current geometry across all analytical years; it does not represent
year-specific historical county boundaries.

---

## Pipeline

| Stage | Script |
|---|---|
| Fetch ACS income data | `src/fetch_acs_income.py` |
| Fetch Zillow county ZHVI | `src/fetch_zillow_zhvi.py` |
| Annualize Zillow ZHVI from monthly values | `src/transform_zillow_zhvi.py` |
| Join income and home value; validate | `src/build_affordability_table.py` |
| Join analytical data to county geometry; export GeoPackage | `src/build_county_geospatial.py` |
| Generate affordability trend figure | `src/create_affordability_figure.py` |

Each script preserves its raw source files on reruns and explicitly reports
when it replaces generated output.

---

## Reproduction

From the repository root:

```bash
# Create and activate virtual environment
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# Acquire source data
.venv/bin/python src/fetch_acs_income.py
.venv/bin/python src/fetch_zillow_zhvi.py

# Transform and build analytical table
.venv/bin/python src/transform_zillow_zhvi.py
.venv/bin/python src/build_affordability_table.py

# Join to county geometry and export GeoPackage
.venv/bin/python src/build_county_geospatial.py

# Generate figure
.venv/bin/python src/create_affordability_figure.py
```

---

## Validation and QA

The following checks are enforced inline by the pipeline scripts:

- **10 county-year rows** — one row per year, 2015–2024
- **Year coverage** — exactly 2015 through 2024, no gaps
- **GEOID 12086** — all rows refer to Miami-Dade County
- **No duplicate county-year rows**
- **No null analytical values** (income, home value, ratio)
- **Boundary match** — exactly one GEOID 12086 geometry in the Census file
- **No missing geometry** in the output GeoDataFrame
- **Valid geometry** — all features pass Shapely validity check
- **CRS present** — EPSG:4269 (NAD83 geographic)
- **GeoPackage round-trip** — output reopened and re-validated after write
- **Analytical values preserved** through the spatial join
- **Raw Census boundary ZIP preserved** — not overwritten on reruns;
  provenance timestamp and file size recorded in
  `data/raw/census_tiger/source_notes.md`

---

## Results

![Miami-Dade affordability trend](reports/figures/miami_dade_affordability_trend.png)

| Measure | 2015 | 2024 | Change |
|---|---|---|---|
| Typical home value | $241,982 | $535,536 | +$293,554 (+121.3%) |
| Median household income | $43,129 | $71,753 | +$28,624 (+66.4%) |
| Home-value-to-income ratio | 5.61 | 7.46 | +1.85 (+33.0%) |

Typical home values increased 121.3%, compared with 66.4% growth in median
household income. As a result, the home-value-to-income ratio rose from 5.61
in 2015 to 7.46 in 2024, an increase of 1.85 (33.0%). All figures are in
nominal dollars.

These results describe a widening gap between home-value growth and
income growth over the study period. The dataset does not identify causes.

---

## Limitations

- **Single-county proof of concept.** Results apply to Miami-Dade County only
  and cannot be generalized.
- **County-level aggregation** conceals substantial neighborhood and
  sub-county variation in both home values and incomes.
- **ZHVI is a modeled estimate,** not a transaction price for every property.
  It represents a typical value within the county according to Zillow's
  methodology.
- **ACS estimates** are derived from survey sampling and carry margins of
  error; multi-year pooled estimates reflect conditions over a five-year
  window rather than a single point in time.
- **Nominal dollars.** No inflation adjustment is applied. Real purchasing
  power changes are not captured.
- **The ratio excludes** interest rates, property taxes, insurance, mortgage
  terms, down-payment requirements, household debt, rental costs, and income
  distribution within the county.
- **2023 boundary geometry** is used consistently across 2015–2024 rather than
  year-specific historical boundaries.
- **EPSG:4269** (NAD83 geographic) is appropriate for feature storage and
  display but is not suitable for area or distance calculations without
  reprojection.
- **The ratio is descriptive.** It does not establish a causal relationship
  between home-value growth and any economic, demographic, or policy factor.

---

## Key Outputs

| File | Description |
|---|---|
| `data/processed/coastal_affordability_county_v0.csv` | Validated analytical dataset, 10 county-year rows |
| `data/processed/miami_dade_affordability_2015_2024.gpkg` | GIS-ready GeoPackage, layer `miami_dade_affordability`, CRS EPSG:4269 |
| `data/raw/census_tiger/source_notes.md` | Census boundary provenance — URL, vintage, retrieval date, file size |
| `reports/figures/miami_dade_affordability_trend.png` | Affordability trend figure |

---

## Project Status

The Miami-Dade County proof of concept is complete. The full pipeline from
data acquisition through validated GIS output and analytical figure is
implemented and reproducible.

Expanding the pipeline to additional Florida counties or a statewide dataset
is possible future work and has not been implemented.
