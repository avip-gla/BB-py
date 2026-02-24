"""Compare transport emissions across all 3 versions: v1 (Excel), v2 (city-specific), v3 (MPG split).

Runs the v1 (reference city), v2 (hardcoded fractions), and v3 (dynamic fractions)
transport pipelines for all 25 cities across projection years and produces:
  - Terminal summary table for key years (2027, 2036, 2050)
  - Detailed per-city breakdown with deltas between versions
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

import numpy as np
import pandas as pd

from iam.config import (
    CITIES, CITY_REGION_MAP, CITY_STATE_MAP,
    PROJECTION_YEARS, CITY_AEO_SALES_REGION_MAP,
    LDV_SHARE, HDV_SHARE, KWH_PER_GALLON_GASOLINE,
    EMISSION_FACTORS_KG_CO2,
)
from iam.data_loader import load_all_data, get_carbon_intensity, get_ldv_sales_share
from iam.city import City
from iam.transport import (
    calculate_initial_vmt_by_fuel, project_vmt,
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
# v2: City-specific with hardcoded fractions
# ============================================================

def _v2_fuel_consumption(
    vmt_by_fuel: dict,
    year: int,
    aeo_mpg: pd.DataFrame,
    aeo_freight: pd.DataFrame,
) -> dict:
    """v2 fuel consumption: hardcoded 0.42/0.58 fractions, same MPG for car/truck,
    first-match freight efficiency, freight_ehybrid -> diesel."""
    car_fraction = 0.42
    truck_fraction = 0.58
    yr_col = f"y{year}"

    def _mpg(vehicle_type: str) -> float:
        row = aeo_mpg[aeo_mpg["vehicle_type"] == vehicle_type]
        if row.empty:
            raise ValueError(f"MPG not found for '{vehicle_type}'")
        val = row[yr_col].iloc[0]
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return np.inf
        return float(val)

    def _freight(category: str) -> float:
        if aeo_freight is None:
            return np.inf
        row = aeo_freight[aeo_freight["category"] == category]
        if row.empty:
            return np.inf
        val = row[yr_col].iloc[0]  # first match (v2)
        if val is None or val == 0 or (isinstance(val, float) and np.isnan(val)):
            return np.inf
        return float(val)

    # Gasoline
    gas_mpg = _mpg("Gasoline ICE Vehicles")
    car_gas = vmt_by_fuel["conventional_gasoline"] * LDV_SHARE * car_fraction / gas_mpg
    truck_gas = vmt_by_fuel["conventional_gasoline"] * LDV_SHARE * truck_fraction / gas_mpg
    freight_gas = vmt_by_fuel["conventional_gasoline"] * HDV_SHARE / _freight("Conventional Gasoline")
    total_gasoline = car_gas + truck_gas + freight_gas

    # Diesel
    diesel_mpg = _mpg("TDI Diesel ICE")
    truck_diesel = vmt_by_fuel["tdi_diesel"] * LDV_SHARE / diesel_mpg
    freight_diesel = vmt_by_fuel["tdi_diesel"] * HDV_SHARE / _freight("TDI Diesel")
    total_diesel = truck_diesel + freight_diesel

    # Ethanol
    flex_mpg = _mpg("Ethanol-Flex Fuel ICE")
    car_eth = vmt_by_fuel["flex_fuel"] * LDV_SHARE * car_fraction / flex_mpg
    truck_eth = vmt_by_fuel["flex_fuel"] * LDV_SHARE * truck_fraction / flex_mpg
    freight_eth = vmt_by_fuel["flex_fuel"] * HDV_SHARE / _freight("Flex-Fuel")
    total_ethanol = car_eth + truck_eth + freight_eth

    # Electricity
    ev_mpge = _mpg("Average EV")
    car_ev = vmt_by_fuel["electric"] * LDV_SHARE * car_fraction / ev_mpge * KWH_PER_GALLON_GASOLINE / 1000
    truck_ev = vmt_by_fuel["electric"] * LDV_SHARE * truck_fraction / ev_mpge * KWH_PER_GALLON_GASOLINE / 1000
    freight_ev = vmt_by_fuel["electric"] * HDV_SHARE / _freight("Electric") * KWH_PER_GALLON_GASOLINE / 1000
    total_elec = car_ev + truck_ev + freight_ev

    # PHEV
    phev_mpg = _mpg("Average Plug In Hybrid")
    car_phev = vmt_by_fuel["plugin_hybrid"] * LDV_SHARE * car_fraction / phev_mpg
    truck_phev = vmt_by_fuel["plugin_hybrid"] * LDV_SHARE * truck_fraction / phev_mpg
    freight_phev = vmt_by_fuel["plugin_hybrid"] * HDV_SHARE / _freight("Plug-in Diesel Hybrid")

    # Hybrid
    hybrid_mpg = _mpg("Electric-Gasoline Hybrid")
    car_hyb = vmt_by_fuel["electric_hybrid"] * LDV_SHARE * car_fraction / hybrid_mpg
    truck_hyb = vmt_by_fuel["electric_hybrid"] * LDV_SHARE * truck_fraction / hybrid_mpg
    freight_hyb = vmt_by_fuel["electric_hybrid"] * HDV_SHARE / _freight("Electric Hybrid")

    # v2 allocation: freight_ehybrid -> diesel (bug), not gasoline
    total_gasoline += car_phev + truck_phev + car_hyb + truck_hyb
    total_diesel += freight_phev + freight_hyb

    return {
        "gasoline_gallons": total_gasoline,
        "diesel_gallons": total_diesel,
        "ethanol_gallons": total_ethanol,
        "electricity_mwh": total_elec,
    }


def compute_v2(all_data: dict, years: list) -> dict:
    """Run v2 transport pipeline for all 25 cities."""
    city_results = {}
    for name in CITIES:
        city = City(name=name, all_data=all_data)
        vmt_df = city._get_projected_vmt()
        by_year = {}

        # v2: SPPC -> MISC fallback
        ci_region = city.region
        if ci_region == "SPPC":
            ci_region = "MISC"

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
            fuel = _v2_fuel_consumption(vmt_by_fuel, yr, all_data["aeo_mpg"], all_data["aeo_freight"])
            ci = get_carbon_intensity(ci_region, yr, all_data["aeo_ci"])
            emissions = calculate_transport_emissions(fuel, ci)
            by_year[yr] = emissions
        city_results[name] = by_year
    return city_results


# ============================================================
# v3: Current codebase (dynamic fractions, separate MPG)
# ============================================================

def compute_v3(all_data: dict, years: list) -> dict:
    """Run v3 transport pipeline for all 25 cities."""
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

def build_comparison(v1: dict, v2: dict, v3: dict, years: list) -> pd.DataFrame:
    """Build a DataFrame comparing all 3 versions for all cities and years."""
    rows = []
    for name in CITIES:
        for yr in years:
            v1_total = v1[name][yr]["total_mt_co2"] if yr in v1[name] else None
            v2_em = v2[name].get(yr, {})
            v3_em = v3[name].get(yr, {})
            v2_total = v2_em.get("total_mt_co2")
            v3_total = v3_em.get("total_mt_co2")

            # Deltas
            v2v1 = (v2_total - v1_total) if v1_total and v2_total else None
            v3v1 = (v3_total - v1_total) if v1_total and v3_total else None
            v3v2 = (v3_total - v2_total) if v2_total and v3_total else None
            v2v1_pct = (v2v1 / v1_total * 100) if v1_total and v2v1 is not None else None
            v3v1_pct = (v3v1 / v1_total * 100) if v1_total and v3v1 is not None else None
            v3v2_pct = (v3v2 / v2_total * 100) if v2_total and v3v2 is not None else None

            rows.append({
                "city": name,
                "state": CITY_STATE_MAP[name],
                "region": CITY_REGION_MAP[name],
                "year": yr,
                "v1_excel_mt_co2": v1_total,
                "v2_city_specific_mt_co2": v2_total,
                "v3_mpg_split_mt_co2": v3_total,
                "v2_v1_delta": v2v1,
                "v2_v1_pct": v2v1_pct,
                "v3_v1_delta": v3v1,
                "v3_v1_pct": v3v1_pct,
                "v3_v2_delta": v3v2,
                "v3_v2_pct": v3v2_pct,
                # Fuel-type detail for v2
                "v2_gasoline": v2_em.get("gasoline_mt_co2"),
                "v2_diesel": v2_em.get("diesel_mt_co2"),
                "v2_ethanol": v2_em.get("ethanol_mt_co2"),
                "v2_electricity": v2_em.get("electricity_mt_co2"),
                # Fuel-type detail for v3
                "v3_gasoline": v3_em.get("gasoline_mt_co2"),
                "v3_diesel": v3_em.get("diesel_mt_co2"),
                "v3_ethanol": v3_em.get("ethanol_mt_co2"),
                "v3_electricity": v3_em.get("electricity_mt_co2"),
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
    print("=" * 130)
    print("  TRANSPORT EMISSIONS: 3-VERSION COMPARISON (MT CO2)")
    print("=" * 130)
    print()
    print("  v1 = Excel (reference city Atlanta, same for all cities)")
    print("  v2 = City-specific VMT/fuel/CI, hardcoded 0.42/0.58 car/truck, same MPG, SPPC->MISC")
    print("  v3 = Dynamic car/truck fractions, separate car/truck MPG, SPPC direct, freight fix")
    print()

    for yr in summary_years:
        yr_df = sub[sub["year"] == yr].copy()
        print(f"  --- Year {yr} ---")
        print()
        header = (
            f"  {'City':<16} {'State':<14} {'Region':<6}"
            f" {'v1 (Excel)':>14} {'v2 (City)':>14} {'v3 (MPG)':>14}"
            f" {'v2-v1':>10} {'v3-v1':>10} {'v3-v2':>10}"
        )
        print(header)
        print("  " + "-" * (len(header) - 2))

        for _, r in yr_df.iterrows():
            print(
                f"  {r['city']:<16} {r['state']:<14} {r['region']:<6}"
                f" {fmt(r['v1_excel_mt_co2']):>14}"
                f" {fmt(r['v2_city_specific_mt_co2']):>14}"
                f" {fmt(r['v3_mpg_split_mt_co2']):>14}"
                f" {fmt_pct(r['v2_v1_pct']):>10}"
                f" {fmt_pct(r['v3_v1_pct']):>10}"
                f" {fmt_pct(r['v3_v2_pct']):>10}"
            )

        # Aggregate stats
        print()
        print(f"  {'MEAN':<16} {'':14} {'':6}"
              f" {fmt(yr_df['v1_excel_mt_co2'].mean()):>14}"
              f" {fmt(yr_df['v2_city_specific_mt_co2'].mean()):>14}"
              f" {fmt(yr_df['v3_mpg_split_mt_co2'].mean()):>14}"
              f" {fmt_pct(yr_df['v2_v1_pct'].mean()):>10}"
              f" {fmt_pct(yr_df['v3_v1_pct'].mean()):>10}"
              f" {fmt_pct(yr_df['v3_v2_pct'].mean()):>10}")
        print(f"  {'MIN':<16} {'':14} {'':6}"
              f" {'':>14} {'':>14} {'':>14}"
              f" {fmt_pct(yr_df['v2_v1_pct'].min()):>10}"
              f" {fmt_pct(yr_df['v3_v1_pct'].min()):>10}"
              f" {fmt_pct(yr_df['v3_v2_pct'].min()):>10}")
        print(f"  {'MAX':<16} {'':14} {'':6}"
              f" {'':>14} {'':>14} {'':>14}"
              f" {fmt_pct(yr_df['v2_v1_pct'].max()):>10}"
              f" {fmt_pct(yr_df['v3_v1_pct'].max()):>10}"
              f" {fmt_pct(yr_df['v3_v2_pct'].max()):>10}")
        print()


def print_city_detail(df: pd.DataFrame, city_name: str) -> None:
    """Print detailed fuel-type breakdown for a specific city."""
    city_df = df[df["city"] == city_name].copy()
    if city_df.empty:
        print(f"  City '{city_name}' not found.")
        return

    print()
    print("=" * 100)
    print(f"  FUEL-TYPE BREAKDOWN: {city_name}")
    print(f"  State: {CITY_STATE_MAP[city_name]}  |  Region: {CITY_REGION_MAP[city_name]}")
    print("=" * 100)

    detail_years = [2027, 2036, 2050]
    detail_df = city_df[city_df["year"].isin(detail_years)]

    for _, r in detail_df.iterrows():
        yr = int(r["year"])
        print(f"\n  --- {yr} ---")
        print(f"  {'':20} {'v2 (City)':>14} {'v3 (MPG)':>14} {'v3-v2 Delta':>14}")
        print(f"  {'-'*62}")

        for fuel, v2k, v3k in [
            ("Gasoline", "v2_gasoline", "v3_gasoline"),
            ("Diesel", "v2_diesel", "v3_diesel"),
            ("Ethanol", "v2_ethanol", "v3_ethanol"),
            ("Electricity", "v2_electricity", "v3_electricity"),
        ]:
            v2_val = r[v2k]
            v3_val = r[v3k]
            delta = (v3_val - v2_val) if v2_val is not None and v3_val is not None else None
            print(
                f"  {fuel:<20}"
                f" {fmt(v2_val, 1):>14}"
                f" {fmt(v3_val, 1):>14}"
                f" {fmt(delta, 1):>14}"
            )

        v2_tot = r["v2_city_specific_mt_co2"]
        v3_tot = r["v3_mpg_split_mt_co2"]
        delta_tot = (v3_tot - v2_tot) if v2_tot and v3_tot else None
        print(f"  {'-'*62}")
        print(
            f"  {'TOTAL':<20}"
            f" {fmt(v2_tot, 1):>14}"
            f" {fmt(v3_tot, 1):>14}"
            f" {fmt(delta_tot, 1):>14}"
        )

    print()


def print_version_notes() -> None:
    """Print explanation of version differences."""
    print()
    print("=" * 100)
    print("  VERSION DIFFERENCES SUMMARY")
    print("=" * 100)
    print("""
  v1 -> v2 (City-Specific Refactor):
    1. City-specific VMT from FHWA (was: Atlanta 5,598,764,246 for all)
    2. State-specific AFDC fuel shares (was: Georgia for all)
    3. Region-specific carbon intensity (was: SRSE for all; SPPC->MISC fallback)

  v2 -> v3 (MPG Split & Data Corrections):
    4. Car/truck MPG split: car=AEO R9, truck=AEO R24 (was: same MPG)
    5. Dynamic car/truck fractions from AEO LDV sales shares (was: 0.42/0.58)
    6. SPPC carbon intensity available directly (was: MISC fallback)
    7. Freight efficiency uses average across weight classes (was: first match)
    8. freight_ehybrid -> gasoline (was: diesel in v2, bug)

  Known Excel Bug:
    Transport R21 references E46 (diesel VMT) instead of E47 (flex VMT).
    This causes v3 to be ~1.47% higher than Excel for Atlanta 2027.
    Difference: ~23,567 MT CO2 (exactly explained by the extra ethanol).
""")


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Compare transport emissions across v1 (Excel), v2 (city-specific), v3 (MPG split)."
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
        help="Print version differences summary.",
    )
    args = parser.parse_args()

    summary_years = args.years if args.years else [2027, 2036, 2050]

    print("Loading data...")
    all_data = load_all_data()

    print("Computing v1 (Excel reference city)...")
    v1 = compute_v1(all_data, PROJECTION_YEARS)

    print("Computing v2 (city-specific, hardcoded fractions)...")
    v2 = compute_v2(all_data, PROJECTION_YEARS)

    print("Computing v3 (MPG split, dynamic fractions)...")
    v3 = compute_v3(all_data, PROJECTION_YEARS)

    print("Building comparison...")
    df = build_comparison(v1, v2, v3, PROJECTION_YEARS)

    # Summary table
    print_summary(df, summary_years)

    # Optional fuel-type detail
    if args.detail:
        print_city_detail(df, args.detail)

    # Version notes
    if args.notes:
        print_version_notes()

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
    print(f"  v2 (City):   {fmt(atl['v2_city_specific_mt_co2'])} MT CO2  ({fmt_pct(atl['v2_v1_pct'])} vs v1)")
    print(f"  v3 (MPG):    {fmt(atl['v3_mpg_split_mt_co2'])} MT CO2  ({fmt_pct(atl['v3_v1_pct'])} vs v1)")


if __name__ == "__main__":
    main()
