"""
Build Florida statewide affordability GeoPackage.

Joins the 670-row Florida affordability table to authoritative Census
county geometry and exports a validated GeoPackage.

Boundary source:
  data/raw/census_tiger/cb_2023_us_county_500k.zip
  Vintage 2023 (consistent current geometry for 2015-2024 records)

Output:
  data/processed/florida_affordability_2015_2024.gpkg
  layer: florida_affordability_county_year
"""

from pathlib import Path
import sys
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parent.parent

TIGER_ZIP = REPO_ROOT / "data" / "raw" / "census_tiger" / "cb_2023_us_county_500k.zip"
TIGER_VINTAGE = "2023"
ANALYTICAL_CSV = REPO_ROOT / "data" / "processed" / "coastal_affordability_florida_2015_2024.csv"
OUTPUT_GPKG = REPO_ROOT / "data" / "processed" / "florida_affordability_2015_2024.gpkg"
LAYER_NAME = "florida_affordability_county_year"

START_YEAR = 2015
END_YEAR = 2024
EXPECTED_YEARS = set(range(START_YEAR, END_YEAR + 1))
EXPECTED_FL_COUNTIES = 67
EXPECTED_FL_FEATURES = 670
STATE_FIPS = "12"
MONROE_EXCEPTION_FIPS = "12087"
MONROE_EXCEPTION_YEAR = 2015

ANALYTICAL_COLUMNS = [
    "state",
    "county_fips",
    "county_name",
    "year",
    "typical_home_value",
    "median_household_income",
    "home_value_to_income_ratio",
    "zillow_months_available",
    "zillow_data_status",
    "home_value_source",
    "home_value_year_method",
    "income_source",
]

OUTPUT_COLUMNS = ANALYTICAL_COLUMNS + ["geometry"]


def separator(title: str) -> None:
    print(f"\n{'=' * 70}\n  {title}\n{'=' * 70}")


def check(label: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    line = f"  [{status}] {label}"
    if detail:
        line += f"  ({detail})"
    print(line)
    if not condition:
        raise AssertionError(f"Validation failed: {label}. {detail}")


def normalize_county_fips(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)


def load_florida_boundaries() -> gpd.GeoDataFrame:
    """Load and validate Florida county geometries from the local TIGER archive."""
    separator("Step 1 – Load Florida county boundary geometry")

    if not TIGER_ZIP.exists():
        raise FileNotFoundError(f"TIGER boundary archive not found: {TIGER_ZIP}")

    with zipfile.ZipFile(TIGER_ZIP) as zf:
        shp_name = next(name for name in zf.namelist() if name.endswith(".shp"))
    zip_path = f"zip://{TIGER_ZIP}!{shp_name}"

    counties = gpd.read_file(zip_path)
    print(f"  Loaded {len(counties):,} county geometries (nationwide).")
    print(f"  CRS: {counties.crs}")

    florida = counties[counties["STATEFP"] == STATE_FIPS].copy()
    florida["GEOID"] = normalize_county_fips(florida["GEOID"])

    check(
        "Florida boundary contains exactly 67 county geometries",
        len(florida) == EXPECTED_FL_COUNTIES,
        f"found {len(florida)}",
    )
    check(
        "Florida boundary contains 67 unique GEOID values",
        florida["GEOID"].nunique() == EXPECTED_FL_COUNTIES,
        f"found {florida['GEOID'].nunique()}",
    )
    check(
        "No null Florida geometries",
        florida.geometry.isna().sum() == 0,
        f"{florida.geometry.isna().sum()} null(s)",
    )
    check(
        "No empty Florida geometries",
        florida.geometry.is_empty.sum() == 0,
        f"{florida.geometry.is_empty.sum()} empty",
    )
    check(
        "All Florida geometries are valid",
        florida.geometry.is_valid.all(),
        f"{(~florida.geometry.is_valid).sum()} invalid",
    )

    geom_types = set(florida.geometry.geom_type.unique())
    check(
        "Florida geometry types are county polygons",
        geom_types.issubset({"Polygon", "MultiPolygon"}),
        f"found {sorted(geom_types)}",
    )

    return florida[["GEOID", "geometry"]].sort_values("GEOID").reset_index(drop=True)


def load_analytical() -> pd.DataFrame:
    """Load and validate the Florida affordability table."""
    separator("Step 2 – Load and validate analytical dataset")

    if not ANALYTICAL_CSV.exists():
        raise FileNotFoundError(f"Analytical CSV not found: {ANALYTICAL_CSV}")

    df = pd.read_csv(ANALYTICAL_CSV, dtype={"county_fips": "string"})
    df["county_fips"] = normalize_county_fips(df["county_fips"])
    df["year"] = pd.to_numeric(df["year"], errors="raise").astype(int)

    missing_columns = [col for col in ANALYTICAL_COLUMNS if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Analytical CSV missing required columns: {missing_columns}")

    check(
        "Analytical dataset has exactly 670 rows",
        len(df) == EXPECTED_FL_FEATURES,
        f"found {len(df)}",
    )
    check(
        "Analytical dataset has 67 unique county_fips values",
        df["county_fips"].nunique() == EXPECTED_FL_COUNTIES,
        f"found {df['county_fips'].nunique()}",
    )
    check(
        "Analytical years are exactly 2015–2024",
        set(df["year"]) == EXPECTED_YEARS,
        f"found {sorted(df['year'].unique())}",
    )
    check(
        "No duplicate county_fips/year keys in analytical dataset",
        not df.duplicated(["county_fips", "year"]).any(),
    )
    check(
        "All analytical county_fips match ^12\\d{3}$",
        df["county_fips"].str.fullmatch(r"12\d{3}").all(),
    )

    return df[ANALYTICAL_COLUMNS].sort_values(["county_fips", "year"]).reset_index(drop=True)


def merge_data(df_analytical: pd.DataFrame, gdf_boundary: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Join analytical records to county geometry using county_fips = GEOID."""
    separator("Step 3 – Merge analytical records to geometry (many-to-one)")

    pre_merge_values = df_analytical.copy()

    merged = df_analytical.merge(
        gdf_boundary,
        left_on="county_fips",
        right_on="GEOID",
        how="left",
        validate="many_to_one",
    )

    if "GEOID" in merged.columns:
        merged = merged.drop(columns=["GEOID"])

    check(
        "Merge produced exactly 670 features",
        len(merged) == EXPECTED_FL_FEATURES,
        f"found {len(merged)}",
    )
    check(
        "Every analytical row received a geometry",
        merged["geometry"].notna().all(),
    )
    check(
        "All 67 county geometries are represented",
        merged["county_fips"].nunique() == EXPECTED_FL_COUNTIES,
        f"found {merged['county_fips'].nunique()}",
    )

    unmatched_boundary = set(gdf_boundary["GEOID"]) - set(merged["county_fips"])
    check(
        "No unmatched Florida boundary geometries",
        len(unmatched_boundary) == 0,
        f"unmatched GEOIDs: {sorted(unmatched_boundary)}",
    )

    gdf = gpd.GeoDataFrame(merged, geometry="geometry", crs=gdf_boundary.crs)
    post_values = gdf[ANALYTICAL_COLUMNS].reset_index(drop=True)
    check(
        "Analytical values unchanged after merge",
        pre_merge_values.reset_index(drop=True).equals(post_values),
    )

    return gdf[OUTPUT_COLUMNS]


def validate_output(gdf: gpd.GeoDataFrame, stage: str) -> None:
    """Validate merged or persisted GeoPackage features."""
    separator(f"Step 4 – Output validation ({stage})")

    gdf = gdf.copy()
    gdf["county_fips"] = normalize_county_fips(gdf["county_fips"])

    check("Exactly 670 features", len(gdf) == EXPECTED_FL_FEATURES, f"found {len(gdf)}")
    check(
        "67 unique county_fips values",
        gdf["county_fips"].nunique() == EXPECTED_FL_COUNTIES,
        f"found {gdf['county_fips'].nunique()}",
    )
    check(
        "Years are exactly 2015–2024",
        set(gdf["year"]) == EXPECTED_YEARS,
        f"found {sorted(gdf['year'].unique())}",
    )
    check(
        "No duplicate county_fips/year keys",
        not gdf.duplicated(["county_fips", "year"]).any(),
    )
    check(
        "Exactly 10 features per county",
        (gdf.groupby("county_fips").size() == 10).all(),
    )
    check(
        "Exactly 67 features per year",
        (gdf.groupby("year").size() == EXPECTED_FL_COUNTIES).all(),
    )
    check("670 non-null geometries", gdf.geometry.notna().all())
    check("670 non-empty geometries", (~gdf.geometry.is_empty).all())
    check("All geometries are valid", gdf.geometry.is_valid.all())
    check("CRS is present", gdf.crs is not None, f"crs={gdf.crs}")

    geom_types = set(gdf.geometry.geom_type.unique())
    check(
        "Geometry types are county polygons",
        geom_types.issubset({"Polygon", "MultiPolygon"}),
        f"found {sorted(geom_types)}",
    )
    check(
        "Exactly 67 distinct county geometries represented",
        gdf.geometry.nunique(dropna=False) == EXPECTED_FL_COUNTIES,
        f"found {gdf.geometry.nunique(dropna=False)}",
    )

    home_nulls = gdf[gdf["typical_home_value"].isna()]
    ratio_nulls = gdf[gdf["home_value_to_income_ratio"].isna()]
    check(
        "Exactly one null typical_home_value",
        len(home_nulls) == 1,
        f"found {len(home_nulls)}",
    )
    check(
        "Exactly one null home_value_to_income_ratio",
        len(ratio_nulls) == 1,
        f"found {len(ratio_nulls)}",
    )
    for missing in (home_nulls.iloc[0], ratio_nulls.iloc[0]):
        check(
            "Null values occur only at Monroe County 2015",
            missing["county_fips"] == MONROE_EXCEPTION_FIPS
            and int(missing["year"]) == MONROE_EXCEPTION_YEAR,
            f"found {missing['county_fips']} {int(missing['year'])}",
        )

    check("All median_household_income values populated", gdf["median_household_income"].notna().all())
    check(
        "All median_household_income values are positive",
        (gdf["median_household_income"] > 0).all(),
    )

    valid_ratio = gdf["home_value_to_income_ratio"].dropna()
    check(
        "All non-null ratios are positive",
        (valid_ratio > 0).all(),
    )
    check(
        "All non-null ratios are finite",
        np.isfinite(valid_ratio).all(),
    )

    status_counts = gdf["zillow_data_status"].value_counts().to_dict()
    expected_status_counts = {
        "complete_12_months": 668,
        "partial_10_11_months": 1,
        "source_data_unavailable": 1,
    }
    check(
        "Expected zillow_data_status counts",
        status_counts == expected_status_counts,
        f"found {status_counts}",
    )


def print_ratio_extremes(gdf: gpd.GeoDataFrame) -> None:
    """Print the five lowest and highest non-null affordability ratios."""
    separator("Step 5 – Affordability ratio extremes (inspection only)")

    ranked = (
        gdf[gdf["home_value_to_income_ratio"].notna()]
        .sort_values("home_value_to_income_ratio")
        .reset_index(drop=True)
    )
    display_cols = [
        "county_fips",
        "county_name",
        "year",
        "typical_home_value",
        "median_household_income",
        "home_value_to_income_ratio",
    ]

    print("\n  Five lowest home_value_to_income_ratio records:")
    print(ranked[display_cols].head(5).to_string(index=False))

    print("\n  Five highest home_value_to_income_ratio records:")
    print(ranked[display_cols].tail(5).to_string(index=False))


def export_gpkg(gdf: gpd.GeoDataFrame) -> None:
    """Write the Florida affordability layer to GeoPackage."""
    separator("Step 6 – Export GeoPackage")

    if OUTPUT_GPKG.exists():
        print(f"  NOTE: Replacing existing generated output: {OUTPUT_GPKG.name}")
        OUTPUT_GPKG.unlink()

    gdf.to_file(OUTPUT_GPKG, layer=LAYER_NAME, driver="GPKG")
    print(f"  Exported: {OUTPUT_GPKG}")
    print(f"  Layer:    {LAYER_NAME}")
    print(f"  Size:     {OUTPUT_GPKG.stat().st_size:,} bytes")


def validate_roundtrip() -> gpd.GeoDataFrame:
    """Reopen the persisted GeoPackage and validate the layer."""
    separator("Step 7 – Round-trip validation (reopen GeoPackage)")

    gdf_rt = gpd.read_file(OUTPUT_GPKG, layer=LAYER_NAME)
    print(f"  Reopened layer '{LAYER_NAME}' from {OUTPUT_GPKG.name}.")
    print(f"  Rows: {len(gdf_rt)}  |  CRS: {gdf_rt.crs}")

    validate_output(gdf_rt, stage="round-trip")
    return gdf_rt


def print_crs_report(crs) -> None:
    separator("CRS report")
    print(f"  EPSG: {crs.to_epsg() if crs else 'unknown'}")
    print(f"  Name: {crs.name if crs else 'unknown'}")


def main() -> None:
    separator("build_florida_geospatial.py – Florida GeoPackage build")
    print(f"  Repo root: {REPO_ROOT}")
    print(f"  Python:    {sys.version.split()[0]}")
    print(f"  TIGER:     {TIGER_ZIP.name} (vintage {TIGER_VINTAGE})")

    gdf_boundary = load_florida_boundaries()
    df_analytical = load_analytical()
    gdf_merged = merge_data(df_analytical, gdf_boundary)
    validate_output(gdf_merged, stage="pre-export")
    print_ratio_extremes(gdf_merged)
    export_gpkg(gdf_merged)
    gdf_persisted = validate_roundtrip()
    print_crs_report(gdf_persisted.crs)

    separator("BUILD COMPLETE")
    print(f"  Output: {OUTPUT_GPKG}")
    print(f"  Layer:  {LAYER_NAME}")
    print(f"  Features: {len(gdf_persisted)}")
    print()


if __name__ == "__main__":
    main()
