"""
Build Coastal Affordability Pressure V0 table.

V0 scope:
- Miami-Dade County, Florida
- Years 2015-2024
- County-year grain
- Metric: typical_home_value / median_household_income
"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MANUAL_DIR = DATA_DIR / "manual"


def main():
    """Build the V0 affordability table."""
    print("V0 build script placeholder. Data ingestion not yet implemented.")


if __name__ == "__main__":
    main()
