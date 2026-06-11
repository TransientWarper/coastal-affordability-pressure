"""
Fetch ACS 5-year median household income for Miami-Dade County.

V0 scope:
- ACS table B19013
- Miami-Dade County, FL
- County FIPS: 12086
- Years: 2015-2024
"""

from pathlib import Path

import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
OUTPUT_PATH = PROJECT_ROOT / "data" / "raw" / "acs_income" / "acs_b19013_miami_dade_2015_2024.csv"

YEARS = list(range(2015, 2025))

STATE_FIPS = "12"
COUNTY_FIPS = "086"


def load_census_api_key() -> str:
    """Load Census API key from local .env file."""
    if not ENV_PATH.exists():
        raise FileNotFoundError("Missing .env file with CENSUS_API_KEY.")

    for line in ENV_PATH.read_text().splitlines():
        if line.startswith("CENSUS_API_KEY="):
            return line.split("=", 1)[1].strip()

    raise ValueError("CENSUS_API_KEY not found in .env file.")


def fetch_income_for_year(year: int, api_key: str) -> dict:
    """Fetch median household income for one ACS 5-year year."""
    url = f"https://api.census.gov/data/{year}/acs/acs5"

    params = {
        "get": "NAME,B19013_001E",
        "for": f"county:{COUNTY_FIPS}",
        "in": f"state:{STATE_FIPS}",
        "key": api_key,
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    rows = response.json()
    header = rows[0]
    values = rows[1]
    record = dict(zip(header, values))

    return {
        "year": year,
        "name": record["NAME"],
        "median_household_income": int(record["B19013_001E"]),
        "state_fips": record["state"],
        "county_fips_short": record["county"],
        "county_fips": record["state"] + record["county"],
        "source": f"ACS {year} 5-year B19013",
    }


def main() -> None:
    """Fetch ACS income data and save raw CSV."""
    api_key = load_census_api_key()
    records = []

    for year in YEARS:
        print(f"Fetching ACS income for {year}...")
        records.append(fetch_income_for_year(year, api_key))

    df = pd.DataFrame(records)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved {len(df)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
