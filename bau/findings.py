"""Top-level GHG savings aggregation module — mirrors the Excel 'Findings' tab.

The Findings tab is the summary sheet that pulls together results from
Buildings and Transport calculations for a given city, showing:
  - Absolute emissions by sector and year
  - Emissions trends (total delta and annual delta)
  - Energy consumption breakdowns
  - Sense check comparisons against inventory/EIE data

Key Excel formulas:
  R35 (Residential): =XLOOKUP($B3, Buildings!$A33:$A57, Buildings!C33:C57)
  R36 (Commercial):  =XLOOKUP($B3, Buildings!$A60:$A84, Buildings!C60:C84)
  R37 (Transport):   =Transport!E4
  R38 (Total):       =XLOOKUP($B3, Buildings!$A6:$A30, Buildings!C6:C30) + Transport!E4
  R10 (Res trend):   =(L35-C35)/C35  (2036 total delta, where L=2036, C=2027)
  R40 (CI Forecast): =XLOOKUP($B5, AEO!$A39:$A50, AEO!E39:E50)
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional

from bau.buildings import calculate_total_buildings_emissions
from bau.emissions import calculate_trend


def calculate_findings_for_year(
    city_name: str,
    year: int,
    buildings_emissions: dict,
    transport_emissions_mt_co2: float,
) -> dict:
    """Calculate the Findings summary for a city in a given year.

    Source: Excel 'Findings' tab R34-R58.

    This aggregates buildings (residential + commercial) and transport
    emissions into the summary format used in the Findings tab.

    Args:
        city_name: City name.
        year: Projection year.
        buildings_emissions: Dict from calculate_total_buildings_emissions()
            with keys: residential, commercial, total, and sub-components.
        transport_emissions_mt_co2: Total transport emissions in MT CO2.

    Returns:
        Dict with findings summary including sector emissions and total.
    """
    return {
        "city": city_name,
        "year": year,
        "buildings_residential_mt_co2e": buildings_emissions["residential"],
        "buildings_commercial_mt_co2e": buildings_emissions["commercial"],
        "buildings_total_mt_co2e": buildings_emissions["total"],
        "transport_mt_co2": transport_emissions_mt_co2,
        "total_mt_co2e": buildings_emissions["total"] + transport_emissions_mt_co2,
        # Sub-components for debugging/plotting
        "residential_electricity_mt_co2": buildings_emissions.get("residential_electricity", 0),
        "residential_ng_mt_co2e": buildings_emissions.get("residential_ng", 0),
        "commercial_electricity_mt_co2": buildings_emissions.get("commercial_electricity", 0),
        "commercial_ng_mt_co2e": buildings_emissions.get("commercial_ng", 0),
    }


def calculate_trends(
    findings_series: List[dict],
    base_year: int = 2027,
    target_years: Optional[List[int]] = None,
) -> dict:
    """Calculate emissions trends between base year and target years.

    Source: Excel 'Findings' tab R7-R13 (Trends section).

    Excel formulas:
      2036 Total Delta (R10): =(L35-C35)/C35
      2036 Annual Delta (R10): Total_Delta / (2036-2027+1) = Total_Delta / 10
      2050 Total Delta: =(Z35-C35)/C35
      2050 Annual Delta: Total_Delta / (2050-2027+1) = Total_Delta / 23

    Args:
        findings_series: List of findings dicts from calculate_findings_for_year(),
            one per year.
        base_year: Reference year for trend calculation (default 2027).
        target_years: Years to calculate trends for. Defaults to [2036, 2050].

    Returns:
        Dict with trends for each target year, by sector.
    """
    if target_years is None:
        target_years = [2036, 2050]

    # Index findings by year
    by_year = {f["year"]: f for f in findings_series}
    base = by_year.get(base_year)
    if base is None:
        raise ValueError(f"Base year {base_year} not found in findings series")

    trends = {}
    for ty in target_years:
        target = by_year.get(ty)
        if target is None:
            continue

        years_elapsed = ty - base_year + 1
        trends[ty] = {
            "residential": calculate_trend(
                base["buildings_residential_mt_co2e"],
                target["buildings_residential_mt_co2e"],
                years_elapsed,
            ),
            "commercial": calculate_trend(
                base["buildings_commercial_mt_co2e"],
                target["buildings_commercial_mt_co2e"],
                years_elapsed,
            ),
            "transport": calculate_trend(
                base["transport_mt_co2"],
                target["transport_mt_co2"],
                years_elapsed,
            ),
            "total": calculate_trend(
                base["total_mt_co2e"],
                target["total_mt_co2e"],
                years_elapsed,
            ),
        }

    return trends


def findings_to_dataframe(findings_series: List[dict]) -> pd.DataFrame:
    """Convert a list of findings dicts to a DataFrame.

    Produces the output format specified in CLAUDE.md:
      - city, year, buildings_savings_mtco2e, transport_savings_mtco2e,
        total_savings_mtco2e, plus intermediate values.

    Args:
        findings_series: List of findings dicts.

    Returns:
        DataFrame with one row per year.
    """
    return pd.DataFrame(findings_series)


def calculate_savings_series(
    findings_series: List[dict],
    base_year: int = 2027,
) -> pd.DataFrame:
    """Calculate GHG savings relative to base year for all projection years.

    Source: Derived from Findings tab trends logic.
    Savings = base_year_emissions - projected_year_emissions

    Args:
        findings_series: List of findings dicts, one per year.
        base_year: Year to use as baseline.

    Returns:
        DataFrame with columns: city, year, buildings_savings_mtco2e,
        transport_savings_mtco2e, total_savings_mtco2e.
    """
    by_year = {f["year"]: f for f in findings_series}
    base = by_year.get(base_year)
    if base is None:
        raise ValueError(f"Base year {base_year} not found in findings series")

    rows = []
    for f in findings_series:
        rows.append({
            "city": f["city"],
            "year": f["year"],
            "buildings_savings_mtco2e": (
                base["buildings_total_mt_co2e"] - f["buildings_total_mt_co2e"]
            ),
            "transport_savings_mtco2e": (
                base["transport_mt_co2"] - f["transport_mt_co2"]
            ),
            "total_savings_mtco2e": (
                base["total_mt_co2e"] - f["total_mt_co2e"]
            ),
            # Intermediate values
            "buildings_residential_mt_co2e": f["buildings_residential_mt_co2e"],
            "buildings_commercial_mt_co2e": f["buildings_commercial_mt_co2e"],
            "transport_mt_co2": f["transport_mt_co2"],
            "total_mt_co2e": f["total_mt_co2e"],
        })

    return pd.DataFrame(rows)
