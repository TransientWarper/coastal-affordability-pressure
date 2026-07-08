"""
build_bea_growth_comparison.py

Join the Miami-Dade affordability table to the processed BEA personal income
table and produce a 2015-indexed growth comparison.

Inputs:
  data/processed/coastal_affordability_county_v0.csv
  data/processed/bea_income_miami_dade_2015_2024.csv

Output:
  data/processed/miami_dade_bea_growth_comparison_2015_2024.csv
"""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED    = PROJECT_ROOT / "data" / "processed"

AFFORDABILITY_PATH = PROCESSED / "coastal_affordability_county_v0.csv"
BEA_PATH           = PROCESSED / "bea_income_miami_dade_2015_2024.csv"
OUTPUT_PATH        = PROCESSED / "miami_dade_bea_growth_comparison_2015_2024.csv"

EXPECTED_ROWS  = 10
EXPECTED_YEARS = set(range(2015, 2025))
EXPECTED_FIPS  = "12086"
BASE_YEAR      = 2015

OUTPUT_COLUMNS = [
    "county_fips",
    "county_name",
    "year",
    "typical_home_value",
    "median_household_income",
    "personal_income",
    "home_value_to_income_ratio",
    "typical_home_value_index_2015",
    "median_household_income_index_2015",
    "personal_income_index_2015",
    "affordability_ratio_index_2015",
    "home_value_growth_minus_personal_income_growth",
]


def index_to_base(series: pd.Series, df: pd.DataFrame, base_year: int) -> pd.Series:
    """Return series / value-in-base-year * 100, rounded to 4 decimal places."""
    base_val = df.loc[df["year"] == base_year, series.name].iloc[0]
    return (series / base_val * 100).round(4)


def validate(df: pd.DataFrame) -> None:
    """Enforce all output checks. Raises ValueError listing all failures."""
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

    index_cols = [
        "typical_home_value_index_2015",
        "median_household_income_index_2015",
        "personal_income_index_2015",
        "affordability_ratio_index_2015",
    ]
    for col in index_cols:
        if col not in df.columns:
            continue
        base_val = df.loc[df["year"] == BASE_YEAR, col]
        if not base_val.empty and round(float(base_val.iloc[0]), 2) != 100.0:
            errors.append(f"{col} is {base_val.iloc[0]} in {BASE_YEAR}, expected 100.0")

    for col in index_cols:
        if col in df.columns and not (df[col] > 0).all():
            errors.append(f"Non-positive values in {col}")

    for col in ["personal_income", "typical_home_value", "median_household_income"]:
        if col in df.columns and not (df[col] > 0).all():
            errors.append(f"Non-positive values in {col}")

    dups = df.duplicated(["county_fips", "year"]).sum()
    if dups:
        errors.append(f"{dups} duplicate county_fips-year key(s)")

    if errors:
        raise ValueError("Validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

    print(f"  [PASS] Exactly {EXPECTED_ROWS} rows")
    print(f"  [PASS] Years exactly {sorted(returned_years)}")
    print(f"  [PASS] county_fips == '{EXPECTED_FIPS}' for all rows")
    print("  [PASS] No nulls in output columns")
    for col in index_cols:
        print(f"  [PASS] {col} == 100.0 in {BASE_YEAR}")
    print("  [PASS] All index values are positive")
    print("  [PASS] personal_income, typical_home_value, median_household_income are positive")
    print("  [PASS] Join is one-to-one by county_fips/year")


def main() -> None:
    """Build the BEA growth comparison table."""
    print("=" * 60)
    print("  build_bea_growth_comparison.py")
    print("=" * 60)
    print(f"  Input 1: {AFFORDABILITY_PATH.relative_to(PROJECT_ROOT)}")
    print(f"  Input 2: {BEA_PATH.relative_to(PROJECT_ROOT)}")
    print(f"  Output:  {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")

    for p in (AFFORDABILITY_PATH, BEA_PATH):
        if not p.exists():
            raise FileNotFoundError(f"Required input not found: {p}")

    # --- Load inputs ---
    aff = pd.read_csv(AFFORDABILITY_PATH, dtype={"county_fips": "string"})
    bea = pd.read_csv(BEA_PATH,           dtype={"county_fips": "string"})

    aff["county_fips"] = aff["county_fips"].astype(str).str.zfill(5)
    bea["county_fips"] = bea["county_fips"].astype(str).str.zfill(5)
    aff["year"] = pd.to_numeric(aff["year"], errors="raise").astype(int)
    bea["year"] = pd.to_numeric(bea["year"], errors="raise").astype(int)

    print(f"\nLoaded {len(aff)} rows from affordability table.")
    print(f"Loaded {len(bea)} rows from BEA income table.")

    # --- Join ---
    merged = aff.merge(
        bea[["county_fips", "year", "personal_income"]],
        on=["county_fips", "year"],
        how="inner",
        validate="one_to_one",
    )
    print(f"Joined result: {len(merged)} rows.")

    merged = merged.sort_values("year").reset_index(drop=True)

    # --- Index columns (2015 = 100) ---
    for raw_col, idx_col in [
        ("typical_home_value",        "typical_home_value_index_2015"),
        ("median_household_income",   "median_household_income_index_2015"),
        ("personal_income",           "personal_income_index_2015"),
        ("home_value_to_income_ratio","affordability_ratio_index_2015"),
    ]:
        base_val = merged.loc[merged["year"] == BASE_YEAR, raw_col].iloc[0]
        merged[idx_col] = (merged[raw_col] / base_val * 100).round(4)

    # --- Growth gap ---
    merged["home_value_growth_minus_personal_income_growth"] = (
        merged["typical_home_value_index_2015"] - merged["personal_income_index_2015"]
    ).round(4)

    # --- Select and order output columns ---
    df = merged[OUTPUT_COLUMNS].copy()

    # --- Validate ---
    print("\nValidating …")
    validate(df)

    # --- Write ---
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    file_size = OUTPUT_PATH.stat().st_size

    print(f"\nSaved: {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    print(f"  Rows:      {len(df)}")
    print(f"  File size: {file_size:,} bytes")

    # --- Summary ---
    r2015 = df[df["year"] == 2015].iloc[0]
    r2024 = df[df["year"] == 2024].iloc[0]
    print("\n" + "-" * 60)
    print("  Summary (2015 → 2024)")
    print("-" * 60)
    print(f"  typical_home_value_index_2015:      "
          f"{r2015['typical_home_value_index_2015']:.2f} → {r2024['typical_home_value_index_2015']:.2f}")
    print(f"  personal_income_index_2015:         "
          f"{r2015['personal_income_index_2015']:.2f} → {r2024['personal_income_index_2015']:.2f}")
    print(f"  home_value_growth_minus_pi_growth:  "
          f"{r2015['home_value_growth_minus_personal_income_growth']:.2f} → "
          f"{r2024['home_value_growth_minus_personal_income_growth']:.2f}")
    print(f"  home_value_to_income_ratio:         "
          f"{r2015['home_value_to_income_ratio']:.4f} → {r2024['home_value_to_income_ratio']:.4f}")


if __name__ == "__main__":
    main()
