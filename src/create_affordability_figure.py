"""
create_affordability_figure.py

Generates a two-panel static figure showing the Miami-Dade housing
affordability trend from 2015 to 2024.

Top panel:    Home-value-to-income ratio, 2015–2024
Bottom panel: Typical home value and median household income,
              both indexed to 100 in 2015

Source:  data/processed/coastal_affordability_county_v0.csv
Output:  reports/figures/miami_dade_affordability_trend.png
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend; safe in all environments
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT  = Path(__file__).resolve().parent.parent
CSV_PATH   = REPO_ROOT / "data" / "processed" / "coastal_affordability_county_v0.csv"
FIG_DIR    = REPO_ROOT / "reports" / "figures"
FIG_PATH   = FIG_DIR / "miami_dade_affordability_trend.png"

TARGET_GEOID   = "12086"
EXPECTED_YEARS = set(range(2015, 2025))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(df: pd.DataFrame) -> None:
    errors = []

    if len(df) != 10:
        errors.append(f"Expected 10 rows, found {len(df)}")

    if set(df["year"].tolist()) != EXPECTED_YEARS:
        errors.append(f"Years do not match 2015–2024: {sorted(df['year'].tolist())}")

    if df.duplicated(subset=["county_fips", "year"]).any():
        errors.append("Duplicate county-year rows detected")

    null_cols = ["year", "typical_home_value", "median_household_income",
                 "home_value_to_income_ratio"]
    for col in null_cols:
        n = df[col].isnull().sum()
        if n:
            errors.append(f"Null values in '{col}': {n}")

    geoids = df["county_fips"].astype(str).str.zfill(5).unique().tolist()
    if geoids != [TARGET_GEOID]:
        errors.append(f"Unexpected county FIPS values: {geoids}")

    if errors:
        for e in errors:
            print(f"  [FAIL] {e}")
        sys.exit(1)

    print("  [PASS] 10 rows")
    print("  [PASS] Years 2015–2024")
    print("  [PASS] No duplicate county-year rows")
    print("  [PASS] No nulls in analytical columns")
    print(f"  [PASS] County FIPS normalizes to {TARGET_GEOID}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("  create_affordability_figure.py")
    print("=" * 60)

    # --- Load and validate ---
    print(f"\nSource: {CSV_PATH.relative_to(REPO_ROOT)}")
    df = pd.read_csv(CSV_PATH).sort_values("year").reset_index(drop=True)
    print("Validating source data …")
    validate(df)

    # --- Derived series (calculated from source data, never hardcoded) ---
    years = df["year"].tolist()
    ratio = df["home_value_to_income_ratio"].tolist()

    base_hv = df.loc[df["year"] == 2015, "typical_home_value"].iloc[0]
    base_inc = df.loc[df["year"] == 2015, "median_household_income"].iloc[0]
    hv_idx  = (df["typical_home_value"] / base_hv * 100).tolist()
    inc_idx = (df["median_household_income"] / base_inc * 100).tolist()

    ratio_2015 = df.loc[df["year"] == 2015, "home_value_to_income_ratio"].iloc[0]
    ratio_2024 = df.loc[df["year"] == 2024, "home_value_to_income_ratio"].iloc[0]
    ratio_abs  = ratio_2024 - ratio_2015
    ratio_pct  = (ratio_abs / ratio_2015) * 100

    hv_2015  = df.loc[df["year"] == 2015, "typical_home_value"].iloc[0]
    hv_2024  = df.loc[df["year"] == 2024, "typical_home_value"].iloc[0]
    hv_pct   = (hv_2024 - hv_2015) / hv_2015 * 100

    inc_2015 = df.loc[df["year"] == 2015, "median_household_income"].iloc[0]
    inc_2024 = df.loc[df["year"] == 2024, "median_household_income"].iloc[0]
    inc_pct  = (inc_2024 - inc_2015) / inc_2015 * 100

    hv_idx_2024  = hv_idx[-1]
    inc_idx_2024 = inc_idx[-1]

    print(f"\nCalculated values:")
    print(f"  Ratio 2015 = {ratio_2015:.4f}  |  Ratio 2024 = {ratio_2024:.4f}")
    print(f"  Ratio change: +{ratio_abs:.2f} ({ratio_pct:+.1f}%)")
    print(f"  Home value: {hv_2015:,.0f} → {hv_2024:,.0f} ({hv_pct:+.1f}%)")
    print(f"  Income:     {inc_2015:,.0f} → {inc_2024:,.0f} ({inc_pct:+.1f}%)")

    # --- Prepare output directory ---
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    if FIG_PATH.exists():
        print(f"\nNOTE: Replacing existing figure: {FIG_PATH.relative_to(REPO_ROOT)}")

    # --- Color palette (restrained, colorblind-accessible) ---
    BLUE   = "#1a6faf"   # ratio / home value
    ORANGE = "#c1612f"   # income
    GREY   = "#555555"
    LGREY  = "#dddddd"

    # --- Figure layout ---
    fig, (ax_top, ax_bot) = plt.subplots(
        nrows=2, ncols=1,
        figsize=(9, 7.5),
        gridspec_kw={"height_ratios": [3, 2]},
        sharex=True,
    )
    fig.subplots_adjust(hspace=0.08, top=0.88, bottom=0.11, left=0.10, right=0.95)

    # ----------------------------------------------------------------
    # Top panel – ratio trend
    # ----------------------------------------------------------------
    ax_top.plot(years, ratio, color=BLUE, linewidth=2.2, zorder=3)
    ax_top.scatter(years, ratio, color=BLUE, s=40, zorder=4, clip_on=False)

    # Emphasise endpoints
    ax_top.scatter([years[0], years[-1]], [ratio[0], ratio[-1]],
                   color=BLUE, s=90, zorder=5, clip_on=False)

    # 2015 annotation (above-left)
    ax_top.annotate(
        f"{ratio_2015:.2f}",
        xy=(years[0], ratio_2015),
        xytext=(-4, 10),
        textcoords="offset points",
        ha="center", va="bottom",
        fontsize=9, color=BLUE, fontweight="bold",
    )

    # 2024 annotation (above-right)
    ax_top.annotate(
        f"{ratio_2024:.2f}",
        xy=(years[-1], ratio_2024),
        xytext=(4, 10),
        textcoords="offset points",
        ha="center", va="bottom",
        fontsize=9, color=BLUE, fontweight="bold",
    )

    # Change callout box
    ax_top.annotate(
        f"+{ratio_abs:.2f} ({ratio_pct:+.1f}%) 2015–2024",
        xy=(2019.5, (ratio_2015 + ratio_2024) / 2),
        fontsize=8.5, color=GREY, ha="center", va="center",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                  edgecolor=LGREY, linewidth=0.8),
    )

    ax_top.set_ylabel("Home value ÷ income", fontsize=10, color=GREY)
    ax_top.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.1f×"))
    ax_top.set_ylim(bottom=4.8)
    ax_top.grid(axis="y", color=LGREY, linewidth=0.7, zorder=0)
    ax_top.spines[["top", "right"]].set_visible(False)
    ax_top.spines[["left", "bottom"]].set_color(LGREY)
    ax_top.tick_params(colors=GREY, labelsize=9)
    ax_top.set_title(
        "Home-Value-to-Income Ratio, Miami-Dade County",
        fontsize=11, color=GREY, loc="left", pad=6, fontweight="bold",
    )

    # ----------------------------------------------------------------
    # Bottom panel – indexed growth
    # ----------------------------------------------------------------
    ax_bot.plot(years, hv_idx,  color=BLUE,   linewidth=2.0,
                label="Typical home value", zorder=3)
    ax_bot.plot(years, inc_idx, color=ORANGE, linewidth=2.0,
                label="Median household income", zorder=3)

    ax_bot.scatter(years, hv_idx,  color=BLUE,   s=30, zorder=4)
    ax_bot.scatter(years, inc_idx, color=ORANGE, s=30, zorder=4)

    # Endpoint labels
    ax_bot.annotate(
        f"+{hv_pct:.1f}%",
        xy=(years[-1], hv_idx_2024),
        xytext=(5, 0), textcoords="offset points",
        ha="left", va="center", fontsize=8.5,
        color=BLUE, fontweight="bold",
    )
    ax_bot.annotate(
        f"+{inc_pct:.1f}%",
        xy=(years[-1], inc_idx_2024),
        xytext=(5, 0), textcoords="offset points",
        ha="left", va="center", fontsize=8.5,
        color=ORANGE, fontweight="bold",
    )

    ax_bot.axhline(100, color=LGREY, linewidth=0.8, zorder=0)
    ax_bot.set_ylabel("Index (2015 = 100)", fontsize=10, color=GREY)
    ax_bot.set_xlabel("Year", fontsize=10, color=GREY)
    ax_bot.set_xlim(years[0] - 0.3, years[-1] + 1.2)
    ax_bot.xaxis.set_major_locator(ticker.MultipleLocator(1))
    ax_bot.xaxis.set_major_formatter(ticker.FormatStrFormatter("%d"))
    ax_bot.grid(axis="y", color=LGREY, linewidth=0.7, zorder=0)
    ax_bot.spines[["top", "right"]].set_visible(False)
    ax_bot.spines[["left", "bottom"]].set_color(LGREY)
    ax_bot.tick_params(colors=GREY, labelsize=9)
    ax_bot.legend(
        fontsize=8.5, frameon=True, framealpha=0.9,
        edgecolor=LGREY, loc="upper left",
    )
    ax_bot.set_title(
        "Component Growth (2015 = 100)",
        fontsize=10, color=GREY, loc="left", pad=4,
    )

    # ----------------------------------------------------------------
    # Figure-level title and source note
    # ----------------------------------------------------------------
    fig.suptitle(
        "Miami-Dade County Housing Affordability Pressure, 2015–2024",
        fontsize=13, fontweight="bold", color="#222222", x=0.52, y=0.97,
    )
    fig.text(
        0.10, 0.025,
        "Sources: Zillow ZHVI (county-level typical home value); "
        "U.S. Census Bureau ACS 5-year estimates, table B19013 "
        "(median household income). Nominal dollars.",
        fontsize=7.5, color="#888888", ha="left", va="bottom",
        wrap=True,
    )

    # ----------------------------------------------------------------
    # Save
    # ----------------------------------------------------------------
    fig.savefig(FIG_PATH, dpi=150, bbox_inches="tight")
    plt.close(fig)

    size_kb = FIG_PATH.stat().st_size / 1024
    print(f"\nFigure saved:  {FIG_PATH.relative_to(REPO_ROOT)}")
    print(f"File size:     {size_kb:.1f} KB")
    print("Done.")


if __name__ == "__main__":
    main()
