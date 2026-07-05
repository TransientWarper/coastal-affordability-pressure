"""
fetch_bea_income.py

Fetch BEA CAINC1 total personal income for Miami-Dade County, 2015–2024.

Source:
  U.S. Bureau of Economic Analysis — Regional Economic Accounts
  Dataset:   Regional
  TableName: CAINC1  (County and MSA Personal Income Summary)
  LineCode:  1       (Personal income, thousands of dollars)
  GeoFips:   12086   (Miami-Dade County, FL)
  Years:     2015 through 2024

The raw CSV preserves BEA's reported unit (thousands of dollars).
Conversion to whole dollars belongs in a downstream transformation step.
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH     = PROJECT_ROOT / ".env"
RAW_DIR      = PROJECT_ROOT / "data" / "raw" / "bea_income"
OUTPUT_CSV   = RAW_DIR / "bea_cainc1_miami_dade_2015_2024.csv"
SOURCE_NOTES = RAW_DIR / "source_notes.md"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BEA_ENDPOINT     = "https://apps.bea.gov/api/data"
TARGET_GEO_FIPS  = "12086"
TARGET_YEARS     = list(range(2015, 2025))
EXPECTED_ROWS    = 10
EXPECTED_YEAR_SET = set(TARGET_YEARS)
LINE_CODE        = 1

# Nonnumeric markers BEA uses to indicate suppressed or unavailable data
NONNUMERIC_MARKERS = {"(d)", "(na)", "(l)", "(x)", "(s)", "n.a.", "na", "(nd)"}

# BEA response field → snake_case output column
FIELD_MAP = {
    "GeoFips":                "geo_fips",   # live API returns "GeoFips", not "GeoFIPS"
    "GeoName":                "geo_name",
    "Region":                 "region",
    "TableName":              "table_name",
    # Live API returns "Code" with a composite value like "CAINC1-1".
    # "LineCode" is absent from the actual response.
    # "code" preserves the raw value; "line_code" is derived from it in parse_rows.
    "Code":                   "code",
    "UNIT_MULT":              "unit_mult",  # live API field; e.g. 3 = thousands
    "IndustryClassification": "industry_classification",
    "Description":            "description",
    "Unit":                   "unit",         # fallback; live API uses "CL_UNIT"
    "CL_UNIT":                "unit",         # live API field name for unit
    "TimePeriod":             "time_period",
    "DataValue":              "data_value",
    "NoteRef":                "note_ref",
}

# Deterministic output column order
OUTPUT_COLUMNS = [
    "geo_fips",
    "geo_name",
    "region",
    "table_name",
    "code",        # raw BEA composite code, e.g. "CAINC1-1"
    "line_code",   # integer derived from code suffix
    "industry_classification",
    "description",
    "unit",
    "unit_mult",   # BEA UNIT_MULT; 3 = values are in thousands
    "time_period",
    "data_value",
    "note_ref",
]


# ---------------------------------------------------------------------------
# Credential loading — same manual .env pattern as fetch_acs_income.py
# ---------------------------------------------------------------------------

def load_bea_api_key() -> str:
    """Load BEA API key from the project-root .env file."""
    if not ENV_PATH.exists():
        raise FileNotFoundError(
            f".env file not found at {ENV_PATH}. "
            "Add a BEA_API_KEY=<your_key> line to that file."
        )
    for line in ENV_PATH.read_text().splitlines():
        if line.startswith("BEA_API_KEY="):
            value = line.split("=", 1)[1].strip()
            if not value:
                raise ValueError("BEA_API_KEY is present in .env but its value is blank.")
            return value
    raise ValueError(
        "BEA_API_KEY not found in .env. "
        "Add a BEA_API_KEY=<your_key> line to that file."
    )


# ---------------------------------------------------------------------------
# API request
# ---------------------------------------------------------------------------

def fetch_bea_data(api_key: str) -> list[dict]:
    """
    Request CAINC1 LineCode 1 for GeoFips 12086, years 2015–2024.
    Returns the raw list of data-row dicts from the BEA JSON response.
    Raises informative exceptions on HTTP errors and BEA API errors.
    Does not print the API key or the prepared request URL.
    """
    years_param = ",".join(str(y) for y in TARGET_YEARS)

    params = {
        "UserID":       api_key,
        "method":       "GetData",
        "datasetname":  "Regional",
        "TableName":    "CAINC1",
        "LineCode":     str(LINE_CODE),
        "GeoFips":      TARGET_GEO_FIPS,
        "Year":         years_param,
        "ResultFormat": "JSON",
    }

    print(
        f"  Requesting BEA Regional/CAINC1 "
        f"LineCode={LINE_CODE} GeoFips={TARGET_GEO_FIPS} Years={years_param}"
    )

    response = requests.get(BEA_ENDPOINT, params=params, timeout=30)
    response.raise_for_status()

    payload = response.json()

    # ---- Structural checks ----
    if "BEAAPI" not in payload:
        raise ValueError(
            "Unexpected BEA response: top-level key 'BEAAPI' is missing. "
            f"Keys present: {list(payload.keys())}"
        )

    beaapi = payload["BEAAPI"]

    # BEA may return an Error object at this level
    if "Error" in beaapi:
        err = beaapi["Error"]
        raise ValueError(
            "BEA API error — "
            f"APIErrorCode: {err.get('APIErrorCode', '?')}, "
            f"APIErrorDescription: {err.get('APIErrorDescription', '?')}"
        )

    if "Results" not in beaapi:
        raise ValueError(
            "BEA response missing 'Results'. "
            f"Keys under BEAAPI: {list(beaapi.keys())}"
        )

    results = beaapi["Results"]

    # BEA may also surface errors inside Results
    if "Error" in results:
        err = results["Error"]
        raise ValueError(
            "BEA Results error — "
            f"APIErrorCode: {err.get('APIErrorCode', '?')}, "
            f"APIErrorDescription: {err.get('APIErrorDescription', '?')}"
        )

    if "Data" not in results:
        raise ValueError(
            "BEA Results missing 'Data'. "
            f"Keys under Results: {list(results.keys())}"
        )

    data_rows = results["Data"]

    if not isinstance(data_rows, list) or len(data_rows) == 0:
        raise ValueError(
            f"BEA returned an empty or non-list Data field: {type(data_rows)}"
        )

    return data_rows


# ---------------------------------------------------------------------------
# Parse raw rows into a normalized DataFrame
# ---------------------------------------------------------------------------

def parse_rows(raw_rows: list[dict]) -> pd.DataFrame:
    """
    Map BEA response field names → snake_case columns.
    Normalize geo_fips, time_period, line_code, and data_value types.
    Report unmapped fields without failing.
    """
    returned_fields = set(raw_rows[0].keys()) if raw_rows else set()
    unmapped = returned_fields - set(FIELD_MAP.keys())
    if unmapped:
        print(
            f"  Note: BEA response contains fields not in mapping "
            f"(preserved as additional context if needed): {sorted(unmapped)}"
        )

    records = []
    for row in raw_rows:
        record = {}
        for bea_key, col_name in FIELD_MAP.items():
            if bea_key in row:
                record[col_name] = row[bea_key]
            # Optional fields absent from the response are simply omitted
        records.append(record)

    # Build with deterministic column order; include only columns that exist
    present_cols = [c for c in OUTPUT_COLUMNS if c in records[0]]
    df = pd.DataFrame(records, columns=present_cols)

    # geo_fips → 5-character zero-padded string
    df["geo_fips"] = df["geo_fips"].astype(str).str.strip().str.zfill(5)

    # time_period → int for sorting
    df["time_period"] = pd.to_numeric(df["time_period"], errors="raise").astype(int)

    # code: raw BEA composite value (e.g. "CAINC1-1") — preserved as-is.
    df["code"] = df["code"].astype(str).str.strip()

    # line_code: integer extracted from the suffix of code after the last hyphen.
    df["line_code"] = (
        df["code"].str.split("-").str[-1]
        .pipe(pd.to_numeric, errors="raise").astype(int)
    )

    # unit_mult → numeric integer (e.g. 3 means values are in thousands)
    if "unit_mult" in df.columns:
        df["unit_mult"] = pd.to_numeric(df["unit_mult"], errors="raise").astype(int)

    # data_value: strip presentation commas and whitespace, check for
    # suppression markers, then convert to float
    raw_dv = df["data_value"].astype(str).str.replace(",", "", regex=False).str.strip()

    suppressed = raw_dv.str.lower().isin(NONNUMERIC_MARKERS)
    if suppressed.any():
        bad = df.loc[suppressed, ["geo_fips", "time_period", "data_value"]].to_string(
            index=False
        )
        raise ValueError(
            f"BEA returned suppressed or unavailable data markers:\n{bad}"
        )

    df["data_value"] = pd.to_numeric(raw_dv, errors="raise")

    # Sort ascending by year
    df = df.sort_values("time_period").reset_index(drop=True)

    # Enforce deterministic column order (only columns that exist)
    df = df[[c for c in OUTPUT_COLUMNS if c in df.columns]]

    return df


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(df: pd.DataFrame) -> None:
    """
    Enforce all required output checks before writing any file.
    Raises ValueError listing all failures if any check fails.
    """
    errors = []

    # 1. Row count
    if len(df) != EXPECTED_ROWS:
        errors.append(f"Expected {EXPECTED_ROWS} rows; got {len(df)}")

    # 2. Year coverage
    returned_years = set(df["time_period"].tolist())
    if returned_years != EXPECTED_YEAR_SET:
        missing = sorted(EXPECTED_YEAR_SET - returned_years)
        extra   = sorted(returned_years - EXPECTED_YEAR_SET)
        errors.append(
            f"Year mismatch — missing: {missing}, unexpected: {extra}"
        )

    # 3. One row per year (duplicate geo_fips-time_period keys)
    dups = int(df.duplicated(["geo_fips", "time_period"]).sum())
    if dups:
        errors.append(f"{dups} duplicate geo_fips-time_period key(s)")

    # 4. geo_fips
    bad_fips = df.loc[df["geo_fips"] != TARGET_GEO_FIPS, "geo_fips"].unique()
    if len(bad_fips):
        errors.append(f"Unexpected geo_fips values: {bad_fips.tolist()}")

    # 5. line_code
    bad_lc = df.loc[df["line_code"] != LINE_CODE, "line_code"].unique()
    if len(bad_lc):
        errors.append(f"Unexpected line_code values: {bad_lc.tolist()}")

    # 6. data_value is numeric
    if not pd.api.types.is_numeric_dtype(df["data_value"]):
        errors.append("data_value column is not numeric after conversion")

    # 7. No null data_value
    null_dv = int(df["data_value"].isna().sum())
    if null_dv:
        errors.append(f"{null_dv} null data_value(s)")

    # 8–9 combined: suppression markers and positivity
    # (suppression is already checked in parse_rows; positivity here)
    if pd.api.types.is_numeric_dtype(df["data_value"]):
        non_pos = int((df["data_value"] <= 0).sum())
        if non_pos:
            errors.append(f"{non_pos} non-positive data_value(s)")

    # code: present, nonblank, consistent, and identifies CAINC1 Line 1
    if "code" not in df.columns:
        errors.append("'code' column is absent from response")
    else:
        null_code = int(df["code"].isna().sum())
        if null_code:
            errors.append(f"{null_code} null code value(s)")
        blank_code = int(df["code"].astype(str).str.strip().eq("").sum())
        if blank_code:
            errors.append(f"{blank_code} blank code value(s)")
        n_codes = df["code"].nunique(dropna=False)
        if n_codes != 1:
            errors.append(
                f"code is not consistent — {n_codes} distinct values: "
                f"{df['code'].unique().tolist()}"
            )
        else:
            code_val = df["code"].iloc[0]
            # Verify the code identifies CAINC1 Line 1 by checking both parts
            parts = code_val.split("-")
            if len(parts) < 2 or "CAINC1" not in parts[0].upper() or parts[-1] != str(LINE_CODE):
                errors.append(
                    f"code '{code_val}' does not identify CAINC1 Line {LINE_CODE}"
                )

    # unit_mult: numeric, non-null, consistent
    if "unit_mult" not in df.columns:
        errors.append("'unit_mult' column is absent from response")
    else:
        if not pd.api.types.is_numeric_dtype(df["unit_mult"]):
            errors.append("unit_mult column is not numeric")
        null_um = int(df["unit_mult"].isna().sum())
        if null_um:
            errors.append(f"{null_um} null unit_mult value(s)")
        n_um = df["unit_mult"].nunique(dropna=False)
        if n_um != 1:
            errors.append(
                f"unit_mult is not consistent — {n_um} distinct values: "
                f"{df['unit_mult'].unique().tolist()}"
            )

    # 10–11. unit present and consistent
    if "unit" not in df.columns:
        errors.append("'unit' column is absent from response")
    else:
        null_unit = int(df["unit"].isna().sum())
        if null_unit:
            errors.append(f"{null_unit} null unit value(s)")
        n_units = df["unit"].nunique(dropna=False)
        if n_units != 1:
            errors.append(
                f"unit is not consistent — {n_units} distinct values: "
                f"{df['unit'].unique().tolist()}"
            )

    # 13. description consistent with personal income
    if "description" in df.columns:
        descs = df["description"].unique().tolist()
        if len(descs) != 1:
            errors.append(f"Inconsistent descriptions across rows: {descs}")
        elif "personal income" not in descs[0].lower():
            errors.append(
                f"Description does not mention 'personal income': '{descs[0]}'"
            )

    # 14. table_name consistent with CAINC1 (when present)
    if "table_name" in df.columns:
        tables = df["table_name"].unique().tolist()
        if len(tables) == 1 and "CAINC1" not in tables[0].upper():
            errors.append(f"table_name does not match CAINC1: '{tables[0]}'")

    if errors:
        raise ValueError(
            "Pre-write validation failed:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    # All passed — report
    print(f"  [PASS] Exactly {EXPECTED_ROWS} rows")
    print(f"  [PASS] Years exactly {sorted(returned_years)}")
    print("  [PASS] No duplicate geo_fips-time_period keys")
    print(f"  [PASS] geo_fips == '{TARGET_GEO_FIPS}' for all rows")
    print(f"  [PASS] line_code == {LINE_CODE} for all rows")
    print("  [PASS] data_value is numeric")
    print("  [PASS] No null data_values")
    print("  [PASS] All data_values are positive")
    if "code" in df.columns:
        print(f"  [PASS] code present, consistent, and identifies CAINC1-{LINE_CODE}: "
              f"'{df['code'].iloc[0]}'")
    if "unit_mult" in df.columns:
        print(f"  [PASS] unit_mult numeric and consistent: {df['unit_mult'].iloc[0]}")
    if "unit" in df.columns:
        print(f"  [PASS] unit present and consistent: '{df['unit'].iloc[0]}'")
    if "description" in df.columns:
        print(f"  [PASS] description consistent with personal income: "
              f"'{df['description'].iloc[0]}'")
    if "table_name" in df.columns:
        print(f"  [PASS] table_name consistent with CAINC1: "
              f"'{df['table_name'].iloc[0]}'")


# ---------------------------------------------------------------------------
# Provenance notes
# ---------------------------------------------------------------------------

def write_source_notes(df: pd.DataFrame, retrieved_at: str, file_size: int) -> None:
    """
    Write source_notes.md with full provenance.
    No credentials, API key, or prepared URLs containing UserID are written.
    """
    description = df["description"].iloc[0] if "description" in df.columns else "N/A"
    geo_name    = df["geo_name"].iloc[0]    if "geo_name" in df.columns    else "N/A"
    unit        = df["unit"].iloc[0]        if "unit" in df.columns        else "N/A"
    table_name  = df["table_name"].iloc[0]  if "table_name" in df.columns  else "CAINC1"
    code_val    = df["code"].iloc[0]        if "code" in df.columns        else "N/A"
    unit_mult   = int(df["unit_mult"].iloc[0]) if "unit_mult" in df.columns else "N/A"
    years_returned = sorted(df["time_period"].tolist())
    years_str = ", ".join(str(y) for y in years_returned)
    years_req = ", ".join(str(y) for y in TARGET_YEARS)

    content = f"""\
# BEA Income Source Notes

## Source Agency

U.S. Bureau of Economic Analysis (BEA)
https://www.bea.gov/

## Dataset

Regional Economic Accounts

## Table

{table_name} — County and MSA Personal Income Summary:
Personal Income, Population, Per Capita Personal Income

## Line Code

1

## Returned Description

{description}

## Geography

County-level

## County

{geo_name}
FIPS: {TARGET_GEO_FIPS}

## Requested Years

{years_req}

## Returned Years

{years_str}

## Returned Code

{code_val}

The BEA `Code` field is a composite identifier combining table name and line
number. `CAINC1-1` denotes CAINC1 Line Code 1 (Personal income).
The raw `code` column in the CSV preserves this value; the derived `line_code`
column holds the integer suffix (1).

## Returned Unit

{unit}

## Returned Unit Multiplier (UNIT_MULT)

{unit_mult}

UNIT_MULT=3 corresponds to values reported in thousands of dollars
(10^3). The raw CSV preserves this field as `unit_mult`; no multiplication
is applied here. Conversion to whole dollars belongs in a downstream
transformation step.

## Retrieval Timestamp (UTC)

{retrieved_at}

## API Endpoint (no key)

{BEA_ENDPOINT}

## Non-Secret Request Parameters

method=GetData
datasetname=Regional
TableName=CAINC1
LineCode=1
GeoFips={TARGET_GEO_FIPS}
Year={years_req}
ResultFormat=JSON

## Output File

`{OUTPUT_CSV.name}`

## Output Row Count

{len(df)}

## Output File Size

{file_size:,} bytes

## Unit Preservation

The CSV preserves BEA's reported unit ({unit}).
Conversion from thousands of dollars to whole dollars belongs in a
downstream transformation step and is not performed here.

## Dollar Basis

Values are current-dollar nominal figures unless BEA metadata indicates
otherwise. The returned unit "{unit}" does not indicate inflation adjustment.
"""
    SOURCE_NOTES.write_text(content)
    print(f"  Source notes written to: {SOURCE_NOTES.relative_to(PROJECT_ROOT)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Fetch BEA CAINC1 personal income for Miami-Dade, 2015–2024."""
    print("=" * 60)
    print("  fetch_bea_income.py")
    print("=" * 60)
    print(f"  Repo root: {PROJECT_ROOT}")

    # ---- No-overwrite guard ----
    if OUTPUT_CSV.exists():
        print(
            f"\nExisting raw file preserved — no API request made.\n"
            f"  {OUTPUT_CSV.relative_to(PROJECT_ROOT)}\n"
            "Remove that file to re-fetch from BEA."
        )
        return

    # ---- Credential ----
    api_key = load_bea_api_key()
    print("  BEA_API_KEY loaded successfully from .env.")

    # ---- Fetch ----
    print()
    raw_rows = fetch_bea_data(api_key)
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"  Received {len(raw_rows)} row(s) from BEA API.")

    # ---- Parse ----
    df = parse_rows(raw_rows)

    # ---- Validate ----
    print("\nValidating …")
    validate(df)

    # ---- Write CSV (only after validation passes) ----
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)
    file_size = OUTPUT_CSV.stat().st_size

    print(f"\nSaved: {OUTPUT_CSV.relative_to(PROJECT_ROOT)}")
    print(f"  Rows:        {len(df)}")
    print(f"  Year range:  {df['time_period'].min()}–{df['time_period'].max()}")
    print(f"  County FIPS: {df['geo_fips'].iloc[0]}")
    unit_str = df["unit"].iloc[0] if "unit" in df.columns else "N/A"
    print(f"  Unit:        {unit_str}")
    print(f"  File size:   {file_size:,} bytes")

    # ---- Provenance notes ----
    print()
    write_source_notes(df, retrieved_at, file_size)

    print("\nDone.")


if __name__ == "__main__":
    main()
