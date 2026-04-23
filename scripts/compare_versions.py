"""Compare transport emissions: v1 (Excel) vs current Python implementation.

Runs the v1 (Excel reference city) and current Python transport pipelines
for all 25 cities across projection years and produces:
  - Terminal summary table for key years (2027, 2036, 2050)
  - Detailed per-city breakdown with deltas
  - Fuel-type breakdown comparison for a selected city
  - Optional CSV export of full results

Usage:
    python scripts/compare_versions.py
    python scripts/compare_versions.py --detail Atlanta
    python scripts/compare_versions.py --years 2027 2030 2040 2050
    python scripts/compare_versions.py --output outputs/csv/version_comparison.csv
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from bau.config import (
    CITIES, CITY_REGION_MAP, CITY_STATE_MAP,
    PROJECTION_YEARS, CITY_AEO_SALES_REGION_MAP,
)
from bau.data_loader import load_all_data, get_carbon_intensity, get_ldv_sales_share
from bau.city import City
from bau.transport import (
    calculate_fuel_consumption, calculate_transport_emissions,
)


# ============================================================
# v1: Reference city emissions (from pre-calculated Excel data)
# ============================================================

def compute_v1(all_data: dict, years: list) -> dict:
    """Get v1 (Excel reference city) emissions for all cities.

    v1 uses the same pre-calculated transport emissions for all 25 cities,
    taken from the Excel Transport tab (Atlanta as reference city).

    Returns:
        Dict keyed by city name -> dict keyed by year -> emissions dict.
    """
    transport_df = all_data["transport_emissions"]
    city_results = {}
    for name in CITIES:
        by_year = {}
        for yr in years:
            row = transport_df[transport_df["year"] == yr]
            if row.empty:
                continue
            total = float(row["total_emissions_mt_co2"].iloc[0])
            by_year[yr] = {
                "total_mt_co2": total,
                "gasoline_mt_co2": None,
                "diesel_mt_co2": None,
                "ethanol_mt_co2": None,
                "electricity_mt_co2": None,
            }
        city_results[name] = by_year
    return city_results


# ============================================================
# Current: Python implementation (dynamic fractions, separate MPG)
# ============================================================

def compute_current(all_data: dict, years: list) -> dict:
    """Run current Python transport pipeline for all 25 cities."""
    city_results = {}
    for name in CITIES:
        city = City(name=name, all_data=all_data)
        vmt_df = city._get_projected_vmt()
        by_year = {}

        for yr in years:
            year_row = vmt_df[vmt_df["year"] == yr]
            if year_row.empty:
                continue
            year_row = year_row.iloc[0]
            vmt_by_fuel = {
                "conventional_gasoline": year_row["vmt_conventional_gasoline"],
                "tdi_diesel": year_row["vmt_tdi_diesel"],
                "flex_fuel": year_row["vmt_flex_fuel"],
                "electric": year_row["vmt_electric"],
                "plugin_hybrid": year_row["vmt_plugin_hybrid"],
                "electric_hybrid": year_row["vmt_electric_hybrid"],
            }
            sales_region = CITY_AEO_SALES_REGION_MAP.get(name, "South Atlantic")
            car_frac = get_ldv_sales_share(sales_region, "Cars", yr, all_data["aeo_ldv_sales"])
            truck_frac = get_ldv_sales_share(sales_region, "Pick Up Trucks", yr, all_data["aeo_ldv_sales"])
            fuel = calculate_fuel_consumption(
                vmt_by_fuel, yr, all_data["aeo_mpg"],
                car_fraction=car_frac, truck_fraction=truck_frac,
                aeo_freight=all_data["aeo_freight"],
            )
            ci = get_carbon_intensity(city.region, yr, all_data["aeo_ci"])
            emissions = calculate_transport_emissions(fuel, ci)
            by_year[yr] = emissions
        city_results[name] = by_year
    return city_results


# ============================================================
# Build comparison DataFrame
# ============================================================

def build_comparison(v1: dict, current: dict, years: list) -> pd.DataFrame:
    """Build a DataFrame comparing v1 (Excel) vs current Python for all cities and years."""
    rows = []
    for name in CITIES:
        for yr in years:
            v1_total = v1[name][yr]["total_mt_co2"] if yr in v1[name] else None
            cur_em = current[name].get(yr, {})
            cur_total = cur_em.get("total_mt_co2")

            delta = (cur_total - v1_total) if v1_total and cur_total else None
            pct = (delta / v1_total * 100) if v1_total and delta is not None else None

            rows.append({
                "city": name,
                "state": CITY_STATE_MAP[name],
                "region": CITY_REGION_MAP[name],
                "year": yr,
                "v1_excel_mt_co2": v1_total,
                "python_mt_co2": cur_total,
                "delta": delta,
                "delta_pct": pct,
                "gasoline": cur_em.get("gasoline_mt_co2"),
                "diesel": cur_em.get("diesel_mt_co2"),
                "ethanol": cur_em.get("ethanol_mt_co2"),
                "electricity": cur_em.get("electricity_mt_co2"),
            })
    return pd.DataFrame(rows)


# ============================================================
# Terminal output
# ============================================================

def fmt(val, decimals=0) -> str:
    """Format a number with commas."""
    if val is None:
        return "N/A"
    return f"{val:>,.{decimals}f}"


def fmt_pct(val) -> str:
    """Format a percentage with sign."""
    if val is None:
        return "N/A"
    return f"{val:>+.1f}%"


def print_summary(df: pd.DataFrame, summary_years: list) -> None:
    """Print the main comparison summary table."""
    sub = df[df["year"].isin(summary_years)].copy()

    print()
    print("=" * 100)
    print("  TRANSPORT EMISSIONS: EXCEL vs PYTHON (MT CO2)")
    print("=" * 100)
    print()
    print("  v1 = Excel (reference city Atlanta, same for all cities)")
    print("  Python = City-specific VMT/fuel/CI, dynamic car/truck fractions, separate MPG")
    print()

    for yr in summary_years:
        yr_df = sub[sub["year"] == yr].copy()
        print(f"  --- Year {yr} ---")
        print()
        header = (
            f"  {'City':<16} {'State':<14} {'Region':<6}"
            f" {'v1 (Excel)':>14} {'Python':>14}"
            f" {'Delta':>10}"
        )
        print(header)
        print("  " + "-" * (len(header) - 2))

        for _, r in yr_df.iterrows():
            print(
                f"  {r['city']:<16} {r['state']:<14} {r['region']:<6}"
                f" {fmt(r['v1_excel_mt_co2']):>14}"
                f" {fmt(r['python_mt_co2']):>14}"
                f" {fmt_pct(r['delta_pct']):>10}"
            )

        # Aggregate stats
        print()
        print(f"  {'MEAN':<16} {'':14} {'':6}"
              f" {fmt(yr_df['v1_excel_mt_co2'].mean()):>14}"
              f" {fmt(yr_df['python_mt_co2'].mean()):>14}"
              f" {fmt_pct(yr_df['delta_pct'].mean()):>10}")
        print(f"  {'MIN':<16} {'':14} {'':6}"
              f" {'':>14} {'':>14}"
              f" {fmt_pct(yr_df['delta_pct'].min()):>10}")
        print(f"  {'MAX':<16} {'':14} {'':6}"
              f" {'':>14} {'':>14}"
              f" {fmt_pct(yr_df['delta_pct'].max()):>10}")
        print()


def print_city_detail(df: pd.DataFrame, city_name: str) -> None:
    """Print detailed fuel-type breakdown for a specific city."""
    city_df = df[df["city"] == city_name].copy()
    if city_df.empty:
        print(f"  City '{city_name}' not found.")
        return

    print()
    print("=" * 80)
    print(f"  FUEL-TYPE BREAKDOWN: {city_name}")
    print(f"  State: {CITY_STATE_MAP[city_name]}  |  Region: {CITY_REGION_MAP[city_name]}")
    print("=" * 80)

    detail_years = [2027, 2036, 2050]
    detail_df = city_df[city_df["year"].isin(detail_years)]

    for _, r in detail_df.iterrows():
        yr = int(r["year"])
        print(f"\n  --- {yr} ---")
        print(f"  {'Fuel Type':<20} {'MT CO2':>14}")
        print(f"  {'-'*34}")

        for fuel, key in [
            ("Gasoline", "gasoline"),
            ("Diesel", "diesel"),
            ("Ethanol", "ethanol"),
            ("Electricity", "electricity"),
        ]:
            print(f"  {fuel:<20} {fmt(r[key], 1):>14}")

        print(f"  {'-'*34}")
        print(f"  {'TOTAL':<20} {fmt(r['python_mt_co2'], 1):>14}")

    print()


def print_notes() -> None:
    """Print explanation of differences between Excel and Python."""
    print()
    print("=" * 80)
    print("  DIFFERENCES: EXCEL vs PYTHON")
    print("=" * 80)
    print("""
  Python improvements over Excel:
    1. City-specific VMT from FHWA (Excel used Atlanta for all cities)
    2. State-specific AFDC fuel shares (Excel used Georgia for all)
    3. Region-specific carbon intensity (Excel used SRSE for all)
    4. Car/truck MPG split: car=AEO R9, truck=AEO R24 (Excel used same MPG)
    5. Dynamic car/truck fractions from AEO LDV sales shares (Excel used 0.42/0.58)
    6. SPPC carbon intensity available directly (Excel only had SRSE)
    7. Freight efficiency uses average across weight classes (Excel used first match)
    8. freight_ehybrid correctly allocated to gasoline

  Known Excel Bug:
    Transport R21 references E46 (diesel VMT) instead of E47 (flex VMT).
    This causes Python to be ~1.47% higher than Excel for Atlanta 2027.
    Difference: ~23,567 MT CO2 (exactly explained by the extra ethanol).
""")


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Compare transport emissions: v1 (Excel) vs current Python."
    )
    parser.add_argument(
        "--years", nargs="*", type=int, default=None,
        help="Summary years to display. Default: 2027 2036 2050.",
    )
    parser.add_argument(
        "--detail", type=str, default=None,
        help="City name to show fuel-type breakdown (e.g., --detail Atlanta).",
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Path to save full comparison CSV (all cities, all years).",
    )
    parser.add_argument(
        "--notes", action="store_true",
        help="Print differences summary.",
    )
    args = parser.parse_args()

    summary_years = args.years if args.years else [2027, 2036, 2050]

    print("Loading data...")
    all_data = load_all_data()

    print("Computing v1 (Excel reference city)...")
    v1 = compute_v1(all_data, PROJECTION_YEARS)

    print("Computing current Python transport emissions...")
    current = compute_current(all_data, PROJECTION_YEARS)

    print("Building comparison...")
    df = build_comparison(v1, current, PROJECTION_YEARS)

    # Summary table
    print_summary(df, summary_years)

    # Optional fuel-type detail
    if args.detail:
        print_city_detail(df, args.detail)

    # Notes
    if args.notes:
        print_notes()

    # CSV export
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=False)
        print(f"Full comparison saved to: {out_path}")
        print(f"  {len(CITIES)} cities x {len(PROJECTION_YEARS)} years = {len(df)} rows")

    # Quick verification printout
    print()
    print("Quick verification (Atlanta 2027):")
    atl = df[(df["city"] == "Atlanta") & (df["year"] == 2027)].iloc[0]
    print(f"  v1 (Excel):  {fmt(atl['v1_excel_mt_co2'])} MT CO2")
    print(f"  Python:      {fmt(atl['python_mt_co2'])} MT CO2  ({fmt_pct(atl['delta_pct'])} vs Excel)")


if __name__ == "__main__":
    main()
