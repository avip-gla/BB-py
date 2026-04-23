"""Run the EVE (EV Electrification) policy module.

Computes annual GHG savings from:
  - Charger deployment (VMT shift: gasoline → electric)
  - Fleet electrification (city + airport vehicles by class)

Usage:
    python scripts/run_eve.py --city Atlanta
    python scripts/run_eve.py --city Atlanta --output outputs/csv/eve_atlanta.csv
    python scripts/run_eve.py --city Atlanta --detail
"""
import argparse
import sys
sys.path.insert(0, ".")

import pandas as pd

from bau.data_loader import load_all_data
from eve.config import EVE_YEARS
from eve.data_loader import load_eve_inputs, load_bau_transport_series
from eve.charger_calculator import compute_charger_savings
from eve.fleet_calculator import compute_fleet_savings


def run_eve(city_name: str) -> pd.DataFrame:
    """Run the full EVE calculation for one city.

    Args:
        city_name: City name matching the CSV in data/inputs/eve/.

    Returns:
        DataFrame with columns:
            year, charger_savings_mt_co2, fleet_savings_mt_co2,
            total_eve_savings_mt_co2
    """
    print(f"Loading BAU data...")
    all_data = load_all_data()

    print(f"Loading EVE inputs for {city_name}...")
    eve_inputs = load_eve_inputs(city_name)

    print(f"Computing BAU transport series for {city_name}...")
    bau_series = load_bau_transport_series(city_name, all_data, EVE_YEARS)

    print(f"Computing charger savings...")
    charger_df = compute_charger_savings(bau_series, eve_inputs, EVE_YEARS)

    print(f"Computing fleet savings...")
    fleet_df = compute_fleet_savings(eve_inputs, EVE_YEARS)

    # Merge and compute total
    result = charger_df[["year", "charger_savings_mt_co2"]].merge(
        fleet_df[["year", "fleet_savings_mt_co2"]], on="year"
    )
    result["total_eve_savings_mt_co2"] = (
        result["charger_savings_mt_co2"] + result["fleet_savings_mt_co2"]
    )
    result.insert(0, "city", city_name)

    return result


def print_summary(df: pd.DataFrame) -> None:
    """Print a formatted summary table."""
    print(f"\n{'='*72}")
    print(f"EVE Savings Summary: {df['city'].iloc[0]}")
    print(f"{'='*72}")
    print(f"{'Year':>6}  {'Charger (MT CO2)':>18}  {'Fleet (MT CO2)':>15}  {'Total (MT CO2)':>15}")
    print(f"{'-'*6}  {'-'*18}  {'-'*15}  {'-'*15}")
    for _, row in df.iterrows():
        print(
            f"{int(row['year']):>6}  "
            f"{row['charger_savings_mt_co2']:>18,.1f}  "
            f"{row['fleet_savings_mt_co2']:>15,.1f}  "
            f"{row['total_eve_savings_mt_co2']:>15,.1f}"
        )
    cumulative = df["total_eve_savings_mt_co2"].sum()
    print(f"\nCumulative savings {df['year'].min()}–{df['year'].max()}: {cumulative:,.1f} MT CO2")


def main():
    parser = argparse.ArgumentParser(description="Run EVE EV Electrification policy module.")
    parser.add_argument("--city", required=True, help="City name (e.g. Atlanta)")
    parser.add_argument("--output", help="Path to save CSV output")
    parser.add_argument("--detail", action="store_true",
                        help="Print detailed charger and fleet breakdown")
    args = parser.parse_args()

    result = run_eve(args.city)

    print_summary(result)

    if args.detail:
        # Recompute for detail
        from bau.data_loader import load_all_data
        all_data = load_all_data()
        eve_inputs = load_eve_inputs(args.city)
        bau_series = load_bau_transport_series(args.city, all_data, EVE_YEARS)

        charger_df = compute_charger_savings(bau_series, eve_inputs, EVE_YEARS)
        fleet_df = compute_fleet_savings(eve_inputs, EVE_YEARS)

        print(f"\n--- Charger Detail ---")
        print(charger_df[["year", "multiplier", "shifted_vmt",
                           "delta_gasoline_mt_co2", "delta_electricity_mt_co2",
                           "charger_savings_mt_co2"]].to_string(index=False))

        print(f"\n--- Fleet Detail ---")
        print(fleet_df[["year", "ramp_ldv", "ramp_mdv", "ramp_hdv",
                         "fleet_savings_mt_co2"]].to_string(index=False))

    if args.output:
        result.to_csv(args.output, index=False)
        print(f"\nSaved: {args.output}")


if __name__ == "__main__":
    main()
