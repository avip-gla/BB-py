"""Run the SOL (Solar) policy module.

Computes annual energy cost savings and GHG emissions avoided from
residential rooftop solar installations for a city or city group.

Usage examples:
    # Run a named group (averages cities, scales to program HH count)
    python scripts/run_sol.py --group oh
    python scripts/run_sol.py --group va

    # Run a single city (per-household metrics only)
    python scripts/run_sol.py --city akron

    # Custom city group with explicit program parameters
    python scripts/run_sol.py --cities akron cleveland --system-kw 16.3 --households 5500

    # Custom year range
    python scripts/run_sol.py --group oh --start-year 2026 --end-year 2050

    # Save output to CSV
    python scripts/run_sol.py --group oh --output outputs/csv/solar_oh.csv
    python scripts/run_sol.py --group va --output outputs/csv/solar_va.csv
"""
import argparse
import os
import sys

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sol.config import CITY_GROUPS, DEFAULT_START_YEAR, DEFAULT_END_YEAR
from sol.data_loader import load_sol_inputs, load_carbon_intensity
from sol.calculator import compute_city_solar, scale_to_program


def run_group(group_name: str, start_year: int, end_year: int):
    """Run the solar module for a named city group."""
    cfg = CITY_GROUPS[group_name]
    cities = cfg["cities"]
    system_kw = cfg["system_kw"]
    num_hh = cfg["num_households"]
    label = cfg["label"]

    print(f"\n{'='*60}")
    print(f"Solar Policy: {label}")
    print(f"  Cities   : {', '.join(c.title() for c in cities)}")
    print(f"  System   : {system_kw} kW/home  (scale factor {system_kw/5.0:.2f}×)")
    print(f"  HH count : {num_hh:,}")
    print(f"  Years    : {start_year}–{end_year}")
    print(f"{'='*60}\n")

    years = list(range(start_year, end_year + 1))
    city_dfs = []

    for city in cities:
        inputs = load_sol_inputs(city)
        ci = load_carbon_intensity(inputs["aeo_region"])
        df = compute_city_solar(inputs, ci, years)
        city_dfs.append(df)
        print(f"  {city.title():15s}  base={inputs['base_kwh_5kw']:,} kWh  "
              f"rate={inputs['elec_rate_2026']:.3f}$/kWh  "
              f"region={inputs['aeo_region']}")

    result = scale_to_program(city_dfs, system_kw, num_hh)
    return result, label


def run_single_city(city: str, start_year: int, end_year: int,
                    system_kw: float = 5.0, num_hh: int = 1):
    """Run the solar module for a single city."""
    inputs = load_sol_inputs(city)
    ci = load_carbon_intensity(inputs["aeo_region"])
    years = list(range(start_year, end_year + 1))

    print(f"\n{'='*60}")
    print(f"Solar Policy: {city.title()}")
    print(f"  Base production : {inputs['base_kwh_5kw']:,} kWh/yr (5 kW PVWatts)")
    print(f"  Electricity rate: ${inputs['elec_rate_2026']:.3f}/kWh "
          f"({inputs['elec_rate_escalation']*100:.1f}%/yr escalation)")
    print(f"  AEO region      : {inputs['aeo_region']}")
    print(f"  System size     : {system_kw} kW  (scale {system_kw/5.0:.2f}×)")
    print(f"  HH count        : {num_hh:,}")
    print(f"  Years           : {start_year}–{end_year}")
    print(f"{'='*60}\n")

    df = compute_city_solar(inputs, ci, years)

    if system_kw != 5.0 or num_hh > 1:
        result = scale_to_program([df], system_kw, num_hh)
    else:
        result = df

    return result, city.title()


def print_results(df, label: str):
    """Print results table to console."""
    print(f"\nResults — {label}")
    print("-" * 80)

    if "total_ghg_avoided_mt" in df.columns:
        # Group / scaled output
        print(f"{'Year':>6}  {'Avg kWh':>10}  {'Avg Rate':>9}  "
              f"{'Total Savings':>14}  {'Cumul Savings':>14}  {'GHG Avoided MT':>14}")
        print("-" * 80)
        for _, row in df.iterrows():
            print(f"{int(row['year']):>6}  "
                  f"{row['avg_annual_kwh_5kw']:>10,.0f}  "
                  f"${row['avg_elec_rate']:>8.4f}  "
                  f"${row['total_annual_savings_usd']:>13,.0f}  "
                  f"${row['total_cumulative_savings_usd']:>13,.0f}  "
                  f"{row['total_ghg_avoided_mt']:>14.1f}")
        print("-" * 80)
        print(f"{'TOTALS':>6}  {'':>10}  {'':>9}  "
              f"${df['total_annual_savings_usd'].sum():>13,.0f}  "
              f"{'':>14}  "
              f"{df['total_ghg_avoided_mt'].sum():>14.1f}")
    else:
        # Single city / per-5kW output
        print(f"{'Year':>6}  {'kWh':>8}  {'Rate $/kWh':>10}  "
              f"{'Savings $':>10}  {'Cumul $':>10}  {'GHG MT':>8}")
        print("-" * 60)
        for _, row in df.iterrows():
            print(f"{int(row['year']):>6}  "
                  f"{row['annual_kwh']:>8,.0f}  "
                  f"${row['elec_rate']:>9.4f}  "
                  f"${row['annual_savings_usd']:>9,.2f}  "
                  f"${row['cumulative_savings_usd']:>9,.2f}  "
                  f"{row['ghg_avoided_mt']:>8.4f}")
        print("-" * 60)
        print(f"{'TOTALS':>6}  "
              f"{df['annual_kwh'].sum():>8,.0f}  "
              f"{'':>10}  "
              f"${df['annual_savings_usd'].sum():>9,.2f}  "
              f"{'':>10}  "
              f"{df['ghg_avoided_mt'].sum():>8.4f}")


def main():
    parser = argparse.ArgumentParser(
        description="Run solar policy module for a city or city group."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--group", choices=list(CITY_GROUPS.keys()),
                      help="Named city group (e.g. oh, va)")
    mode.add_argument("--city", help="Single city name (e.g. akron, hampton)")
    mode.add_argument("--cities", nargs="+",
                      help="Custom city list (requires --system-kw and --households)")

    parser.add_argument("--system-kw", type=float, default=5.0,
                        help="Actual system size per household (kW). Default: 5.0")
    parser.add_argument("--households", type=int, default=1,
                        help="Number of households. Default: 1 (per-HH output)")
    parser.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    parser.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR)
    parser.add_argument("--output", help="Save results to CSV at this path")

    args = parser.parse_args()

    if args.group:
        result, label = run_group(args.group, args.start_year, args.end_year)
    elif args.city:
        result, label = run_single_city(
            args.city, args.start_year, args.end_year,
            args.system_kw, args.households
        )
    else:
        # Custom city list
        if args.system_kw == 5.0 and args.households == 1:
            print("Warning: using default system-kw=5.0 and households=1. "
                  "Pass --system-kw and --households for scaled totals.")
        years = list(range(args.start_year, args.end_year + 1))
        city_dfs = []
        first_region = None
        for city in args.cities:
            inputs = load_sol_inputs(city)
            if first_region is None:
                first_region = inputs["aeo_region"]
            ci = load_carbon_intensity(inputs["aeo_region"])
            city_dfs.append(compute_city_solar(inputs, ci, years))
        result = scale_to_program(city_dfs, args.system_kw, args.households)
        label = ", ".join(c.title() for c in args.cities)

    print_results(result, label)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        result.to_csv(args.output, index=False)
        print(f"\nSaved to: {args.output}")


if __name__ == "__main__":
    main()
