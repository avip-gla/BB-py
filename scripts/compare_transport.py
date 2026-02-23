"""Compare transport emissions: reference city (old) vs city-specific (new).

Runs both calculation paths for all 25 cities across all projection years
and outputs a side-by-side comparison CSV plus a terminal summary table.

Usage:
    python scripts/compare_transport.py
    python scripts/compare_transport.py --output outputs/csv/transport_comparison.csv
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from iam.config import CITIES, PROJECTION_YEARS
from iam.data_loader import load_all_data
from iam.city import City


def build_comparison(cities: list, years: list, all_data: dict) -> pd.DataFrame:
    """Build a DataFrame comparing old (reference city) vs new (city-specific) transport.

    Args:
        cities: List of city names.
        years: List of projection years.
        all_data: Pre-loaded data dict from load_all_data().

    Returns:
        DataFrame with columns: city, year, transport_old_mt_co2,
        transport_new_mt_co2, delta_mt_co2, pct_change.
    """
    rows = []
    for name in cities:
        city = City(name=name, all_data=all_data)
        for yr in years:
            old_val = city._get_transport_emissions_from_data(yr)
            new_val = city.transport_emissions(yr)
            delta = new_val - old_val
            pct = (delta / old_val * 100) if old_val != 0 else 0.0
            rows.append({
                "city": name,
                "year": yr,
                "transport_old_mt_co2": old_val,
                "transport_new_mt_co2": new_val,
                "delta_mt_co2": delta,
                "pct_change": pct,
            })
    return pd.DataFrame(rows)


def print_summary(df: pd.DataFrame) -> None:
    """Print a terminal summary table showing 2027 and 2050 for each city."""
    summary_years = [2027, 2036, 2050]
    sub = df[df["year"].isin(summary_years)].copy()

    pd.set_option("display.float_format", lambda x: f"{x:,.1f}")
    pd.set_option("display.max_rows", 100)
    pd.set_option("display.width", 160)

    print("=" * 120)
    print("TRANSPORT EMISSIONS COMPARISON: Reference City (Old) vs City-Specific (New)")
    print("=" * 120)
    print()
    print("Old = pre-calculated values from Excel Transport tab (same for all cities, based on Atlanta)")
    print("New = city-specific pipeline (FHWA VMT -> AFDC fuel split -> AEO growth -> fuel consumption -> emissions)")
    print()
    print(sub.to_string(index=False))
    print()

    # Overall statistics
    for yr in summary_years:
        yr_df = df[df["year"] == yr]
        print(f"--- Year {yr} ---")
        print(f"  Mean old:  {yr_df['transport_old_mt_co2'].mean():>14,.1f} MT CO2")
        print(f"  Mean new:  {yr_df['transport_new_mt_co2'].mean():>14,.1f} MT CO2")
        print(f"  Mean delta:{yr_df['delta_mt_co2'].mean():>14,.1f} MT CO2")
        print(f"  Pct range: {yr_df['pct_change'].min():>+.1f}% to {yr_df['pct_change'].max():>+.1f}%")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Compare old vs new transport emissions for all 25 cities."
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Path to save the full comparison CSV. If omitted, prints summary only.",
    )
    parser.add_argument(
        "--cities",
        nargs="*",
        default=None,
        help="Specific cities to compare. Defaults to all 25.",
    )
    args = parser.parse_args()

    cities = args.cities if args.cities else CITIES
    print(f"Loading data for {len(cities)} cities...")
    all_data = load_all_data()

    print("Running comparison...")
    df = build_comparison(cities, PROJECTION_YEARS, all_data)

    print_summary(df)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=False)
        print(f"Full comparison saved to: {out_path}")


if __name__ == "__main__":
    main()
