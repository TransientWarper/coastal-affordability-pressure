"""
build_county_geospatial.py

Joins the Miami-Dade affordability analytical dataset to authoritative
US Census county geometry and exports a validated GeoPackage.

Boundary source:
  US Census Bureau Cartographic Boundary File, county level, 500k resolution
  Vintage: 2023  (used as a consistent current geometry for records 2015–2024;
                  does NOT represent year-specific historical boundaries)
  URL: https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_500k.zip

Output:
  data/processed/miami_dade_affordability_2015_2024.gpkg
  layer: miami_dade_affordability
"""

import io
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Paths (resolved relative to this script, so the repo is portable)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent

RAW_TIGER_DIR = REPO_ROOT / "data" / "raw" / "census_tiger"
SOURCE_NOTES  = RAW_TIGER_DIR / "source_notes.md"

CENSUS_URL      = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_500k.zip"
CENSUS_VINTAGE  = "2023"
CENSUS_FILENAME = "cb_2023_us_county_500k.zip"
LOCAL_ZIP       = RAW_TIGER_DIR / CENSUS_FILENAME

ANALYTICAL_CSV  = REPO_ROOT / "data" / "processed" / "coastal_affordability_county_v0.csv"
OUTPUT_GPKG     = REPO_ROOT / "data" / "processed" / "miami_dade_affordability_2015_2024.gpkg"
LAYER_NAME      = "miami_dade_affordability"

TARGET_GEOID    = "12086"
EXPECTED_YEARS  = set(range(2015, 2025))  # 2015 through 2024 inclusive


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def separator(title: str) -> None:
    width = 70
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}")


def check(label: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    line = f"  [{status}] {label}"
    if detail:
        line += f"  ({detail})"
    print(line)
    if not condition:
        raise AssertionError(f"Validation failed: {label}. {detail}")


# ---------------------------------------------------------------------------
# Step 1 – Acquire Census county boundary ZIP
# ---------------------------------------------------------------------------

def acquire_boundary() -> None:
    separator("Step 1 – Acquire Census county boundary")

    RAW_TIGER_DIR.mkdir(parents=True, exist_ok=True)

    if LOCAL_ZIP.exists():
        print(f"  ZIP already present: {LOCAL_ZIP}")
        print("  Reusing existing file. Raw source will NOT be overwritten.")
        if not SOURCE_NOTES.exists():
            SOURCE_NOTES.write_text(
                "# Census Tiger Boundary – Source Notes\n\n"
                f"**Local file:** `{CENSUS_FILENAME}`\n\n"
                "**Note:** The ZIP was already present when this note was "
                "created. Its original retrieval date is unknown.\n\n"
                f"**Source URL:** {CENSUS_URL}\n\n"
                f"**Vintage:** {CENSUS_VINTAGE} "
                "(consistent current geometry; does not represent "
                "year-specific historical county boundaries)\n"
            )
            print(f"  source_notes.md did not exist – created with unknown-date note.")
        else:
            print(f"  source_notes.md already exists – leaving untouched.")
        return

    print(f"  Downloading {CENSUS_URL} …")
    response = requests.get(CENSUS_URL, timeout=120)
    response.raise_for_status()

    file_size = len(response.content)
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    LOCAL_ZIP.write_bytes(response.content)
    print(f"  Saved to: {LOCAL_ZIP}  ({file_size:,} bytes)")

    SOURCE_NOTES.write_text(
        "# Census Tiger Boundary – Source Notes\n\n"
        f"**Source URL:** {CENSUS_URL}\n\n"
        f"**Vintage:** {CENSUS_VINTAGE} "
        "(consistent current geometry; does not represent "
        "year-specific historical county boundaries)\n\n"
        f"**Retrieved:** {retrieved_at}\n\n"
        f"**Local file:** `{CENSUS_FILENAME}`\n\n"
        f"**File size:** {file_size:,} bytes\n"
    )
    print(f"  source_notes.md written with URL, vintage, retrieval timestamp, "
          f"filename, and size.")


# ---------------------------------------------------------------------------
# Step 2 – Load and filter boundary geometry
# ---------------------------------------------------------------------------

def load_boundary() -> gpd.GeoDataFrame:
    separator("Step 2 – Load and filter county boundary geometry")

    with zipfile.ZipFile(LOCAL_ZIP) as zf:
        # Read the shapefile directly from inside the ZIP
        shp_name = next(n for n in zf.namelist() if n.endswith(".shp"))
        print(f"  Reading shapefile from ZIP: {shp_name}")
        with zf.open(shp_name) as f:
            # GeoPandas can read a shapefile from a virtual path inside a zip
            pass  # fallback to path-based read below

    # GeoPandas + pyogrio supports reading directly from a zip path
    zip_path = f"zip://{LOCAL_ZIP}!{shp_name}"
    counties = gpd.read_file(zip_path)
    print(f"  Loaded {len(counties):,} county geometries (nationwide).")
    print(f"  Columns: {counties.columns.tolist()}")
    print(f"  CRS: {counties.crs}")

    # Normalize GEOID to 5-character zero-padded string
    counties["GEOID"] = counties["GEOID"].astype(str).str.zfill(5)

    miami_dade = counties[counties["GEOID"] == TARGET_GEOID].copy()
    check(
        f"Boundary contains exactly one GEOID {TARGET_GEOID} row",
        len(miami_dade) == 1,
        f"found {len(miami_dade)} rows",
    )
    print(f"  Filtered to Miami-Dade (GEOID {TARGET_GEOID}): 1 row retained.")
    return miami_dade


# ---------------------------------------------------------------------------
# Step 3 – Load and validate analytical dataset
# ---------------------------------------------------------------------------

def load_analytical() -> pd.DataFrame:
    separator("Step 3 – Load and validate analytical dataset")

    df = pd.read_csv(ANALYTICAL_CSV)
    print(f"  Loaded {len(df)} rows from {ANALYTICAL_CSV.name}.")
    print(f"  Columns: {df.columns.tolist()}")

    df["geoid"] = df["county_fips"].astype(str).str.zfill(5)

    check(
        "Analytical dataset has exactly 10 rows",
        len(df) == 10,
        f"found {len(df)}",
    )
    check(
        "Years are exactly 2015–2024",
        set(df["year"].tolist()) == EXPECTED_YEARS,
        f"found {sorted(df['year'].tolist())}",
    )
    check(
        f"All county FIPS normalize to {TARGET_GEOID}",
        (df["geoid"] == TARGET_GEOID).all(),
        f"unique geoids: {df['geoid'].unique().tolist()}",
    )
    print("  Pre-join analytical validations passed.")
    return df


# ---------------------------------------------------------------------------
# Step 4 – Merge: keyed many-to-one join
# ---------------------------------------------------------------------------

def merge_data(
    df_analytical: pd.DataFrame,
    gdf_boundary: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    separator("Step 4 – Merge analytical records to geometry (many-to-one)")

    # Prepare a geometry-only frame keyed on geoid
    geom_df = gdf_boundary[["GEOID", "geometry"]].rename(columns={"GEOID": "geoid"})

    # Snapshot analytical values before merge for change-detection check
    value_cols = [
        "median_household_income",
        "typical_home_value",
        "home_value_to_income_ratio",
    ]
    pre_merge_values = df_analytical[["year"] + value_cols].copy()

    merged = df_analytical.merge(
        geom_df,
        on="geoid",
        how="left",
        validate="many_to_one",
    )
    print(f"  Merge complete.  Output rows: {len(merged)}")

    gdf = gpd.GeoDataFrame(merged, geometry="geometry", crs=gdf_boundary.crs)
    print(f"  CRS assigned from boundary source: {gdf.crs}")

    # Verify analytical values are unchanged
    post_values = gdf[["year"] + value_cols].sort_values("year").reset_index(drop=True)
    pre_sorted  = pre_merge_values.sort_values("year").reset_index(drop=True)
    values_unchanged = pre_sorted.equals(post_values)
    check("Analytical values unchanged after merge", values_unchanged)

    return gdf


# ---------------------------------------------------------------------------
# Step 5 – Post-merge validation
# ---------------------------------------------------------------------------

def validate_output(gdf: gpd.GeoDataFrame, stage: str = "pre-export") -> None:
    separator(f"Step 5 – Output validation ({stage})")

    check("Exactly 10 output rows",    len(gdf) == 10,                f"found {len(gdf)}")
    check(
        "Output years are exactly 2015–2024",
        set(gdf["year"].tolist()) == EXPECTED_YEARS,
        f"found {sorted(gdf['year'].tolist())}",
    )
    check(
        f"GEOID is {TARGET_GEOID} for every row",
        (gdf["geoid"] == TARGET_GEOID).all(),
        f"unique geoids: {gdf['geoid'].unique().tolist()}",
    )
    check("No missing geometries",     gdf.geometry.isna().sum() == 0,
          f"{gdf.geometry.isna().sum()} null(s)")
    check("All geometries are valid",  (~gdf.geometry.is_valid).sum() == 0,
          f"{(~gdf.geometry.is_valid).sum()} invalid")
    check("CRS is present",            gdf.crs is not None,          f"crs={gdf.crs}")
    print(f"  CRS: {gdf.crs}")
    print("  All output validations passed.")


# ---------------------------------------------------------------------------
# Step 6 – Export GeoPackage
# ---------------------------------------------------------------------------

def export_gpkg(gdf: gpd.GeoDataFrame) -> None:
    separator("Step 6 – Export GeoPackage")

    if OUTPUT_GPKG.exists():
        print(f"  NOTE: Replacing existing generated output: {OUTPUT_GPKG.name}")

    gdf.to_file(OUTPUT_GPKG, layer=LAYER_NAME, driver="GPKG")
    print(f"  Exported: {OUTPUT_GPKG}")
    print(f"  Layer:    {LAYER_NAME}")
    print(f"  Size:     {OUTPUT_GPKG.stat().st_size:,} bytes")


# ---------------------------------------------------------------------------
# Step 7 – Round-trip validation (reopen GeoPackage)
# ---------------------------------------------------------------------------

def validate_roundtrip() -> None:
    separator("Step 7 – Round-trip validation (reopen GeoPackage)")

    gdf_rt = gpd.read_file(OUTPUT_GPKG, layer=LAYER_NAME)
    print(f"  Reopened layer '{LAYER_NAME}' from {OUTPUT_GPKG.name}.")
    print(f"  Rows: {len(gdf_rt)}  |  CRS: {gdf_rt.crs}")

    validate_output(gdf_rt, stage="round-trip")

    print("\n  Sample output (year, geoid, income, home_value, ratio):")
    display_cols = [
        "year", "geoid",
        "median_household_income", "typical_home_value",
        "home_value_to_income_ratio",
    ]
    print(gdf_rt[display_cols].sort_values("year").to_string(index=False))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    separator("build_county_geospatial.py – Miami-Dade GeoPackage build")
    print(f"  Repo root:  {REPO_ROOT}")
    print(f"  Python:     {sys.version.split()[0]}")

    acquire_boundary()
    gdf_boundary   = load_boundary()
    df_analytical  = load_analytical()
    gdf_merged     = merge_data(df_analytical, gdf_boundary)
    validate_output(gdf_merged, stage="pre-export")
    export_gpkg(gdf_merged)
    validate_roundtrip()

    separator("BUILD COMPLETE")
    print(f"  Output: {OUTPUT_GPKG}")
    print(f"  Layer:  {LAYER_NAME}")
    print()


if __name__ == "__main__":
    main()
