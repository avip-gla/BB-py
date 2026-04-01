"""CLI entry point for BPS (Building Performance Standards) calculations.

Usage:
    python scripts/run_bps.py --city Philadelphia
    python scripts/run_bps.py --city Philadelphia --detail
    python scripts/run_bps.py --city Philadelphia --output outputs/csv/bps_philadelphia.csv
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bps.config import CITY_BPS_POLICIES
from bps.data_loader import load_all_bps_data
from bps.calculator import run_bps


def print_summary(city: str, results: dict, policy: dict) -> None:
    """Print summary table of BPS GHG reductions."""
    print(f"\n{'='*80}")
    print(f"BPS Results: {city}")
    policy_type = policy.get("policy_type", "retrocommissioning")
    print(f"Policy: {policy['savings_rate']*100:.0f}% {policy_type} savings")
    print(f"Region: {policy['region']}")
    print(f"{'='*80}")

    bins = results["bins"]
    years = results["years"]

    header = f"{'Year':>6}" + "".join(f"{b:>14}" for b in bins) + f"{'Total':>14}"
    print(header)
    print("-" * len(header))

    for yr in years:
        vals = [results["ghg_reduction"][b][yr] for b in bins]
        total = results["total_ghg_by_year"][yr]
        row = f"{yr:>6}" + "".join(f"{v:>14,.0f}" for v in vals) + f"{total:>14,.0f}"
        print(row)

    print("-" * len(header))
    totals = [sum(results["ghg_reduction"][b][yr] for yr in years) for b in bins]
    total_row = f"{'Total':>6}" + "".join(f"{t:>14,.0f}" for t in totals) + f"{results['total_ghg']:>14,.0f}"
    print(total_row)
    print()


def print_detail(city: str, results: dict, data: dict) -> None:
    """Print detailed energy savings breakdown."""
    bins = results["bins"]
    years = results["years"]

    print(f"\nArea Percentages:")
    for label, pct in data["area_pcts"].items():
        print(f"  {label}: {pct:.4%}")

    print(f"\nElectricity Savings (MMBtu):")
    for yr in years:
        vals = [results["elec_savings"][b][yr] for b in bins]
        total = sum(vals)
        if total > 0:
            print(f"  {yr}: {total:>14,.0f}")

    print(f"\nNatural Gas Savings (MMBtu):")
    for yr in years:
        vals = [results["ng_savings"][b][yr] for b in bins]
        total = sum(vals)
        if total > 0:
            print(f"  {yr}: {total:>14,.0f}")


def export_csv(results: dict, city: str, output_path: str) -> None:
    """Export BPS results to CSV."""
    rows = []
    for yr in results["years"]:
        for label in results["bins"]:
            rows.append({
                "city": city,
                "year": yr,
                "bin": label,
                "elec_savings_mmbtu": results["elec_savings"][label][yr],
                "ng_savings_mmbtu": results["ng_savings"][label][yr],
                "elec_savings_mwh": results["elec_savings_mwh"][label][yr],
                "ghg_reduction_mt_co2": results["ghg_reduction"][label][yr],
            })
        # Add total row
        rows.append({
            "city": city,
            "year": yr,
            "bin": "Total",
            "elec_savings_mmbtu": sum(results["elec_savings"][b][yr] for b in results["bins"]),
            "ng_savings_mmbtu": sum(results["ng_savings"][b][yr] for b in results["bins"]),
            "elec_savings_mwh": sum(results["elec_savings_mwh"][b][yr] for b in results["bins"]),
            "ghg_reduction_mt_co2": results["total_ghg_by_year"][yr],
        })

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Results exported to {path}")


def main():
    parser = argparse.ArgumentParser(description="Run BPS calculations")
    parser.add_argument("--city", required=True, help="City name (e.g., Philadelphia)")
    parser.add_argument("--detail", action="store_true", help="Show detailed breakdown")
    parser.add_argument("--output", help="Export results to CSV path")
    args = parser.parse_args()

    if args.city not in CITY_BPS_POLICIES:
        available = ", ".join(CITY_BPS_POLICIES.keys())
        print(f"Error: No BPS policy defined for '{args.city}'.")
        print(f"Available cities: {available}")
        sys.exit(1)

    policy = CITY_BPS_POLICIES[args.city]
    data = load_all_bps_data(args.city, policy)
    results = run_bps(args.city, data, policy)

    print_summary(args.city, results, policy)

    if args.detail:
        print_detail(args.city, results, data)

    if args.output:
        export_csv(results, args.city, args.output)


if __name__ == "__main__":
    main()
