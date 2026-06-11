"""
Fetch Zillow ZHVI county-level home value data.

V0 scope:
- County-level Zillow ZHVI
- Miami-Dade County, FL
- Years: 2015-2024
"""

from pathlib import Path

import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "data" / "raw" / "zillow_zhvi" / "zillow_zhvi_county_raw.csv"

ZILLOW_URL = "https://files.zillowstatic.com/research/public_csvs/zhvi/County_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"


def download_file(url: str, output_path: Path) -> None:
    """Download a file with a longer timeout and browser-like headers."""
    headers = {
        "User-Agent": "Mozilla/5.0 coastal-affordability-pressure research project"
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Downloading from: {url}")
    response = requests.get(url, headers=headers, timeout=180)
    response.raise_for_status()

    output_path.write_bytes(response.content)
    print(f"Downloaded {len(response.content):,} bytes to {output_path}")


def main() -> None:
    """Download Zillow county ZHVI CSV and inspect raw copy."""
    print("Downloading Zillow ZHVI county data...")

    download_file(ZILLOW_URL, OUTPUT_PATH)

    print("Reading downloaded CSV...")
    df = pd.read_csv(OUTPUT_PATH)

    print(f"Loaded {len(df)} rows")
    print("First 15 columns:")
    print(list(df.columns[:15]))
    print("Last 5 columns:")
    print(list(df.columns[-5:]))


if __name__ == "__main__":
    main()
