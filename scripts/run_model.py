"""CLI entry point for running the IAM model.

Usage:
    python scripts/run_model.py --cities atlanta
    python scripts/run_model.py --cities atlanta chicago denver --output csv
    python scripts/run_model.py --cities atlanta chicago --output xlsx
    python scripts/run_model.py --all --output csv
"""
import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bau.config import CITIES
from bau.city import City
from bau.data_loader import load_all_data
from bau.output import export_single_city_csv, export_multi_city_csv, export_xlsx


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the IAM model for one or more cities."
    )
    parser.add_argument(
        "--cities",
        nargs="+",
        help="City names to run (case-insensitive, e.g., 'atlanta chicago').",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all 25 cities.",
    )
    parser.add_argument(
        "--output",
        choices=["csv", "xlsx", "both"],
        default="csv",
        help="Output format (default: csv).",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print summary trends to stdout.",
    )

    args = parser.parse_args()

    # Determine which cities to run
    if args.all:
        city_names = CITIES
    elif args.cities:
        # Normalize city names (title case)
        city_names = []
        for c in args.cities:
            # Handle multi-word cities
            normalized = c.strip().title()
            # Special cases
            if normalized == "St. Louis" or normalized == "St Louis":
                normalized = "St. Louis"
            elif normalized == "Kansas City":
                normalized = "Kansas City"
            elif normalized == "Newport News":
                normalized = "Newport News"

            if normalized in CITIES:
                city_names.append(normalized)
            else:
                print(f"Warning: City '{c}' not found. Available cities:")
                for available in CITIES:
                    print(f"  - {available}")
                sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

    print(f"Loading data...")
    all_data = load_all_data()

    print(f"Running model for {len(city_names)} city/cities: {', '.join(city_names)}")

    results = []
    for name in city_names:
        print(f"  Processing {name}...")
        city = City(name=name, all_data=all_data)
        df = city.run_all_years()
        results.append(df)

        if args.summary:
            trends = city.get_trends()
            print(f"\n  {name} Summary:")
            for ty, sectors in trends.items():
                print(f"    {ty} Trends:")
                for sector, vals in sectors.items():
                    td = vals["total_delta"]
                    ad = vals["annual_delta"]
                    print(f"      {sector}: total_delta={td:.4f}, annual_delta={ad:.4f}")

    # Export results
    if args.output in ("csv", "both"):
        if len(city_names) == 1:
            path = export_single_city_csv(results[0], city_names[0])
            print(f"\nCSV saved to: {path}")
        else:
            # Export individual files
            for name, df in zip(city_names, results):
                path = export_single_city_csv(df, name)
                print(f"  CSV saved: {path}")
            # Export combined file
            path = export_multi_city_csv(results)
            print(f"  Combined CSV saved: {path}")

    if args.output in ("xlsx", "both"):
        path = export_xlsx(results, city_names)
        print(f"\nExcel saved to: {path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
