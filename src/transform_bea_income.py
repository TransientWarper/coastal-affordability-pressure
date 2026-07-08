"""
transform_bea_income.py

Transform raw BEA CAINC1 personal income data for Miami-Dade County
into a normalized processed CSV suitable for downstream analysis.

Input:
  data/raw/bea_income/bea_cainc1_miami_dade_2015_2024.csv

Output:
  data/processed/bea_income_miami_dade_2015_2024.csv

Unit conversion:
  BEA reports personal income in thousands of dollars.
  personal_income = personal_income_thousands * 1000
"""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_PATH  = PROJECT_ROOT / "data" / "raw" / "bea_income" / "bea_cainc1_miami_dade_2015_2024.csv"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "bea_income_miami_dade_2015_2024.csv"

EXPECTED_ROWS     = 10
EXPECTED_YEARS    = set(range(2015, 2025))
EXPECTED_FIPS     = "12086"
EXPECTED_UNIT     = "Thousands of dollars"
EXPECTED_UNIT_MULT = 3
EXPECTED_LINE_CODE = 1

OUTPUT_COLUMNS = [
    "county_fips",
    "county_name",
    "year",
    "personal_income",
    "personal_income_thousands",
    "unit",
    "unit_mult",
    "code",
    "line_code",
]


def validate(df: pd.DataFrame) -> None:
    """Enforce all output checks. Raises ValueError on any failure."""
    errors = []

    if len(df) != EXPECTED_ROWS:
        errors.append(f"Expected {EXPECTED_ROWS} rows; got {len(df)}")

    returned_years = set(df["year"].tolist())
    if returned_years != EXPECTED_YEARS:
        missing = sorted(EXPECTED_YEARS - returned_years)
        extra   = sorted(returned_years - EXPECTED_YEARS)
        errors.append(f"Year mismatch — missing: {missing}, unexpected: {extra}")

    fips_vals = df["county_fips"].unique().tolist()
    if fips_vals != [EXPECTED_FIPS]:
        errors.append(f"Expected county_fips ['{EXPECTED_FIPS}']; got {fips_vals}")

    null_totals = df[OUTPUT_COLUMNS].isnull().sum()
    if null_totals.any():
        errors.append(f"Nulls in output: {null_totals[null_totals > 0].to_dict()}")

    if not (df["personal_income_thousands"] > 0).all():
        errors.append("Not all personal_income_thousands values are positive")

    derived = (df["personal_income_thousands"] * 1000).round(0)
    if not (derived == df["personal_income"]).all():
        errors.append("personal_income does not equal personal_income_thousands * 1000")

    unit_vals = df["unit"].unique().tolist()
    if unit_vals != [EXPECTED_UNIT]:
        errors.append(f"Expected unit ['{EXPECTED_UNIT}']; got {unit_vals}")

    um_vals = df["unit_mult"].unique().tolist()
    if um_vals != [EXPECTED_UNIT_MULT]:
        errors.append(f"Expected unit_mult [{EXPECTED_UNIT_MULT}]; got {um_vals}")

    lc_vals = df["line_code"].unique().tolist()
    if lc_vals != [EXPECTED_LINE_CODE]:
        errors.append(f"Expected line_code [{EXPECTED_LINE_CODE}]; got {lc_vals}")

    if errors:
        raise ValueError("Validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

    print(f"  [PASS] Exactly {EXPECTED_ROWS} rows")
    print(f"  [PASS] Years exactly {sorted(returned_years)}")
    print(f"  [PASS] county_fips == '{EXPECTED_FIPS}' for all rows")
    print(f"  [PASS] No nulls in output columns")
    print(f"  [PASS] All personal_income_thousands values are positive")
    print(f"  [PASS] personal_income == personal_income_thousands * 1000")
    print(f"  [PASS] unit consistently '{EXPECTED_UNIT}'")
    print(f"  [PASS] unit_mult consistently {EXPECTED_UNIT_MULT}")
    print(f"  [PASS] line_code identifies CAINC1 line {EXPECTED_LINE_CODE}")


def main() -> None:
    """Read raw BEA CSV, normalize, validate, and write processed CSV."""
    print("=" * 60)
    print("  transform_bea_income.py")
    print("=" * 60)
    print(f"  Input:  {INPUT_PATH.relative_to(PROJECT_ROOT)}")
    print(f"  Output: {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")

    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Raw BEA input not found: {INPUT_PATH}\n"
            "Run src/fetch_bea_income.py first."
        )

    raw = pd.read_csv(INPUT_PATH, dtype={"geo_fips": "string"})
    print(f"\nRead {len(raw)} rows from raw input.")

    # --- Rename and normalize ---
    df = raw.rename(columns={
        "geo_fips":   "county_fips",
        "geo_name":   "county_name",
        "time_period": "year",
        "data_value": "personal_income_thousands",
    })

    df["county_fips"] = df["county_fips"].astype(str).str.strip().str.zfill(5)
    df["year"]        = pd.to_numeric(df["year"], errors="raise").astype(int)

    df["personal_income_thousands"] = pd.to_numeric(
        df["personal_income_thousands"], errors="raise"
    )
    df["personal_income"] = (df["personal_income_thousands"] * 1000).astype("int64")

    df["unit_mult"]  = pd.to_numeric(df["unit_mult"], errors="raise").astype(int)
    df["line_code"]  = pd.to_numeric(df["line_code"], errors="raise").astype(int)

    df = df.sort_values("year").reset_index(drop=True)
    df = df[OUTPUT_COLUMNS]

    # --- Validate ---
    print("\nValidating …")
    validate(df)

    # --- Write ---
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    file_size = OUTPUT_PATH.stat().st_size

    print(f"\nSaved: {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    print(f"  Rows:      {len(df)}")
    print(f"  Columns:   {df.columns.tolist()}")
    print(f"  File size: {file_size:,} bytes")
    print(f"\n{df.to_string(index=False)}")


if __name__ == "__main__":
    main()
