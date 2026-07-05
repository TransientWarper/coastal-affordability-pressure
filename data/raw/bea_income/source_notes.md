# BEA Income Source Notes

## Source Agency

U.S. Bureau of Economic Analysis (BEA)
https://www.bea.gov/

## Dataset

Regional Economic Accounts

## Table

CAINC1 — County and MSA Personal Income Summary:
Personal Income, Population, Per Capita Personal Income

## Line Code

1

## Returned Description

N/A

## Geography

County-level

## County

Miami-Dade
FIPS: 12086

## Requested Years

2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024

## Returned Years

2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024

## Returned Code

CAINC1-1

The BEA `Code` field is a composite identifier combining table name and line
number. `CAINC1-1` denotes CAINC1 Line Code 1 (Personal income).
The raw `code` column in the CSV preserves this value; the derived `line_code`
column holds the integer suffix (1).

## Returned Unit

Thousands of dollars

## Returned Unit Multiplier (UNIT_MULT)

3

UNIT_MULT=3 corresponds to values reported in thousands of dollars
(10^3). The raw CSV preserves this field as `unit_mult`; no multiplication
is applied here. Conversion to whole dollars belongs in a downstream
transformation step.

## Retrieval Timestamp (UTC)

2026-07-05T15:25:28Z

## API Endpoint (no key)

https://apps.bea.gov/api/data

## Non-Secret Request Parameters

method=GetData
datasetname=Regional
TableName=CAINC1
LineCode=1
GeoFips=12086
Year=2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024
ResultFormat=JSON

## Output File

`bea_cainc1_miami_dade_2015_2024.csv`

## Output Row Count

10

## Output File Size

731 bytes

## Unit Preservation

The CSV preserves BEA's reported unit (Thousands of dollars).
Conversion from thousands of dollars to whole dollars belongs in a
downstream transformation step and is not performed here.

## Dollar Basis

Values are current-dollar nominal figures unless BEA metadata indicates
otherwise. The returned unit "Thousands of dollars" does not indicate inflation adjustment.
