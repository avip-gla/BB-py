"""Display and compare results across multiple cities.

Usage:
    python scripts/compare_cities.py --cities Atlanta Charlotte Nashville Memphis
    python scripts/compare_cities.py --cities Atlanta Charlotte --plot
    python scripts/compare_cities.py --all --top 10
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np

from bau.config import CITIES
from bau.city import City
from bau.data_loader import load_all_data


def format_number(val: float, decimals: int = 0) -> str:
    """Format a number with commas and optional decimals."""
    if abs(val) >= 1e6:
        return f"{val/1e6:,.{decimals}f}M"
    elif abs(val) >= 1e3:
        return f"{val/1e3:,.{decimals}f}K"
    return f"{val:,.{decimals}f}"


def format_pct(val: float) -> str:
    """Format a fraction as percentage."""
    return f"{val*100:+.1f}%"


def print_header(title: str, width: int = 80) -> None:
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def print_comparison_table(cities: list, all_data: dict) -> None:
    """Print a formatted comparison table across cities."""

    # Collect results
    results = []
    for name in cities:
        city = City(name=name, all_data=all_data)
        trends = city.get_trends()

        bld_2027 = city.buildings_emissions(2027)["total"]
        bld_2050 = city.buildings_emissions(2050)["total"]
        tpt_2027 = city.transport_emissions(2027)
        tpt_2050 = city.transport_emissions(2050)
        total_2027 = bld_2027 + tpt_2027
        total_2050 = bld_2050 + tpt_2050

        results.append({
            "city": name,
            "region": city.region,
            "bld_2027": bld_2027,
            "bld_2050": bld_2050,
            "bld_savings": bld_2027 - bld_2050,
            "bld_pct": trends[2050]["buildings"]["total_delta"],
            "tpt_2027": tpt_2027,
            "tpt_2050": tpt_2050,
            "tpt_savings": tpt_2027 - tpt_2050,
            "tpt_pct": trends[2050]["transport"]["total_delta"],
            "total_2027": total_2027,
            "total_2050": total_2050,
            "total_savings": total_2027 - total_2050,
            "total_pct": trends[2050]["total"]["total_delta"],
        })

    df = pd.DataFrame(results)

    # ---- Emissions Summary Table ----
    print_header("EMISSIONS SUMMARY (MT CO2e)")

    col_w = 14
    city_w = max(len(c) for c in cities) + 2
    header = (
        f"{'City':<{city_w}} {'Region':>6}"
        f" {'Bld 2027':>{col_w}} {'Bld 2050':>{col_w}} {'Bld Chg':>{col_w}}"
        f" {'Tpt 2027':>{col_w}} {'Tpt 2050':>{col_w}} {'Tpt Chg':>{col_w}}"
        f" {'Total 2027':>{col_w}} {'Total 2050':>{col_w}} {'Total Chg':>{col_w}}"
    )
    print(header)
    print("-" * len(header))

    for r in results:
        line = (
            f"{r['city']:<{city_w}} {r['region']:>6}"
            f" {format_number(r['bld_2027']):>{col_w}}"
            f" {format_number(r['bld_2050']):>{col_w}}"
            f" {format_pct(r['bld_pct']):>{col_w}}"
            f" {format_number(r['tpt_2027']):>{col_w}}"
            f" {format_number(r['tpt_2050']):>{col_w}}"
            f" {format_pct(r['tpt_pct']):>{col_w}}"
            f" {format_number(r['total_2027']):>{col_w}}"
            f" {format_number(r['total_2050']):>{col_w}}"
            f" {format_pct(r['total_pct']):>{col_w}}"
        )
        print(line)

    # ---- Savings Rankings ----
    print_header("GHG SAVINGS RANKINGS (2027 -> 2050)")

    df_sorted = df.sort_values("total_savings", ascending=False)
    print(f"\n  {'Rank':<6} {'City':<{city_w}} {'Buildings':>14} {'Transport':>14} {'Total':>14} {'% Reduction':>12}")
    print(f"  {'':<6} {'':>{city_w}} {'Savings':>14} {'Savings':>14} {'Savings':>14} {'':>12}")
    print("  " + "-" * (6 + city_w + 14*3 + 12 + 4))

    for i, (_, r) in enumerate(df_sorted.iterrows(), 1):
        print(
            f"  {i:<6} {r['city']:<{city_w}}"
            f" {format_number(r['bld_savings']):>14}"
            f" {format_number(r['tpt_savings']):>14}"
            f" {format_number(r['total_savings']):>14}"
            f" {format_pct(r['total_pct']):>12}"
        )

    # ---- Year-by-Year Trajectory ----
    print_header("YEAR-BY-YEAR TOTAL EMISSIONS (MT CO2e)")

    milestone_years = [2027, 2030, 2035, 2040, 2045, 2050]
    col_w2 = 12

    header2 = f"  {'City':<{city_w}}"
    for yr in milestone_years:
        header2 += f" {yr:>{col_w2}}"
    print(header2)
    print("  " + "-" * (city_w + len(milestone_years) * (col_w2 + 1)))

    for name in cities:
        city = City(name=name, all_data=all_data)
        line = f"  {name:<{city_w}}"
        for yr in milestone_years:
            total = city.total_emissions(yr)
            line += f" {format_number(total):>{col_w2}}"
        print(line)

    # ---- Sector Breakdown for Base Year ----
    print_header("SECTOR BREAKDOWN - 2027 (MT CO2e)")

    print(f"\n  {'City':<{city_w}} {'Buildings':>14} {'  % of Total':>12} {'Transport':>14} {'  % of Total':>12} {'Total':>14}")
    print("  " + "-" * (city_w + 14*3 + 12*2 + 5))

    for name in cities:
        city = City(name=name, all_data=all_data)
        bld = city.buildings_emissions(2027)["total"]
        tpt = city.transport_emissions(2027)
        total = bld + tpt
        bld_pct = bld / total if total > 0 else 0
        tpt_pct = tpt / total if total > 0 else 0
        print(
            f"  {name:<{city_w}}"
            f" {format_number(bld):>14}"
            f" {bld_pct*100:>11.1f}%"
            f" {format_number(tpt):>14}"
            f" {tpt_pct*100:>11.1f}%"
            f" {format_number(total):>14}"
        )

    print()


def plot_results(cities: list, all_data: dict) -> None:
    """Generate matplotlib plots comparing cities."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed. Install with: pip install matplotlib")
        return

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("IAM Model - Multi-City GHG Emissions Comparison", fontsize=14, fontweight="bold")

    city_dfs = {}
    for name in cities:
        city = City(name=name, all_data=all_data)
        city_dfs[name] = city.run_all_years()

    # Plot 1: Total emissions over time
    ax = axes[0, 0]
    for name, df in city_dfs.items():
        ax.plot(df["year"], df["total_mt_co2e"] / 1e6, label=name, linewidth=2)
    ax.set_title("Total Emissions Over Time")
    ax.set_xlabel("Year")
    ax.set_ylabel("MT CO2e (millions)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # Plot 2: Buildings emissions
    ax = axes[0, 1]
    for name, df in city_dfs.items():
        ax.plot(df["year"], df["buildings_total_mt_co2e"] / 1e6, label=name, linewidth=2)
    ax.set_title("Buildings Emissions Over Time")
    ax.set_xlabel("Year")
    ax.set_ylabel("MT CO2e (millions)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # Plot 3: Total savings over time
    ax = axes[1, 0]
    for name, df in city_dfs.items():
        ax.plot(df["year"], df["total_savings_mtco2e"] / 1e6, label=name, linewidth=2)
    ax.set_title("Cumulative GHG Savings vs 2027 Baseline")
    ax.set_xlabel("Year")
    ax.set_ylabel("MT CO2e Saved (millions)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # Plot 4: Bar chart of 2050 savings by sector
    ax = axes[1, 1]
    x = np.arange(len(cities))
    width = 0.35

    bld_savings = [city_dfs[c].iloc[-1]["buildings_savings_mtco2e"] / 1e6 for c in cities]
    tpt_savings = [city_dfs[c].iloc[-1]["transport_savings_mtco2e"] / 1e6 for c in cities]

    ax.bar(x - width/2, bld_savings, width, label="Buildings", color="#2196F3")
    ax.bar(x + width/2, tpt_savings, width, label="Transport", color="#FF9800")
    ax.set_title("2050 GHG Savings by Sector")
    ax.set_xlabel("City")
    ax.set_ylabel("MT CO2e Saved (millions)")
    ax.set_xticks(x)
    ax.set_xticklabels(cities, rotation=30, ha="right", fontsize=8)
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    output_path = Path(__file__).parent.parent / "outputs" / "comparison_plot.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"\nPlot saved to: {output_path}")
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare IAM results across cities.")
    parser.add_argument("--cities", nargs="+", help="Cities to compare.")
    parser.add_argument("--all", action="store_true", help="Compare all 25 cities.")
    parser.add_argument("--top", type=int, default=None, help="Show only top N cities by total savings.")
    parser.add_argument("--plot", action="store_true", help="Generate comparison plots.")

    args = parser.parse_args()

    if args.all:
        city_names = CITIES
    elif args.cities:
        city_names = [c.strip().title() for c in args.cities]
        # Fix multi-word cities
        fixed = []
        for c in city_names:
            if c.startswith("St"):
                fixed.append("St. Louis")
            elif c == "Kansas":
                continue  # handled with "City"
            elif c == "City" and fixed and fixed[-1] == "Kansas":
                fixed[-1] = "Kansas City"
            elif c == "Newport":
                continue
            elif c == "News" and fixed and fixed[-1] == "Newport":
                fixed[-1] = "Newport News"
            else:
                fixed.append(c)
        city_names = fixed

        for c in city_names:
            if c not in CITIES:
                print(f"Error: '{c}' not found. Available: {', '.join(CITIES)}")
                sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

    print("Loading data...")
    all_data = load_all_data()

    if args.top and args.all:
        # Pre-compute to find top N
        savings = []
        for name in city_names:
            city = City(name=name, all_data=all_data)
            s = city.total_emissions_saved(2050)
            savings.append((name, s))
        savings.sort(key=lambda x: x[1], reverse=True)
        city_names = [s[0] for s in savings[:args.top]]
        print(f"Showing top {args.top} cities by total savings...")

    print_comparison_table(city_names, all_data)

    if args.plot:
        plot_results(city_names, all_data)


if __name__ == "__main__":
    main()
