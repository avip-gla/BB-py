"""SOL calculator.

Estimates annual energy cost savings and GHG emissions avoided from
residential rooftop solar installations.

Calculation chain (verified against GLA Priority Modeling March 26.xlsx):

  Per-year, per-5kW-system:
    degradation(Y)         = (1 - degradation_rate) ^ (Y - start_year)
    annual_kwh(Y)          = base_kwh_5kw × degradation(Y)
    annual_mwh(Y)          = annual_kwh(Y) / 1000
    elec_rate(Y)           = elec_rate_2026 × (1 + escalation) ^ (Y - 2026)
    annual_savings_usd(Y)  = annual_kwh(Y) × elec_rate(Y)       [$/5kW-system]
    ghg_avoided_mt(Y)      = annual_mwh(Y) × carbon_intensity(Y) [MT CO2/5kW-system]

  Scale-up to actual system and household count:
    scale_factor           = system_kw / 5.0  (e.g. 3.26 for 16.3kW system)
    total_savings_usd(Y)   = annual_savings_usd(Y) × scale_factor × num_households
    total_ghg_avoided_mt(Y)= ghg_avoided_mt(Y)  × scale_factor × num_households

  For a city GROUP (e.g. 6 OH cities), the per-5kW metrics are first averaged
  across all cities before scaling to num_households.

Source: NREL PVWatts v8, EIA Electric Power Monthly, AEO 2025 Table 54.
Verified against GLA Priority Modeling March 26.xlsx (Tabs: 9. OH+Pittsburgh PA,
10. VA (hampton, Newport News)).
"""
from typing import Dict, List

import pandas as pd

from sol.config import BASELINE_SYSTEM_KW


def compute_city_solar(
    sol_inputs: Dict,
    carbon_intensity: Dict[int, float],
    years: List[int],
) -> pd.DataFrame:
    """Compute annual solar metrics for a single city (per 5 kW baseline system).

    This is the city-level building block. Results are per-5kW-system and
    should be aggregated (averaged for groups, then scaled) by the caller.

    Args:
        sol_inputs:       Dict from data_loader.load_sol_inputs().
        carbon_intensity: Dict of year → MT CO2/MWh from load_carbon_intensity().
        years:            Projection years.

    Returns:
        DataFrame with columns:
            year, degradation_factor,
            annual_kwh, annual_mwh,
            elec_rate,
            annual_savings_usd,    (per 5kW system)
            cumulative_savings_usd,(per 5kW system)
            carbon_intensity_mt_mwh,
            ghg_avoided_mt         (per 5kW system)
    """
    base_kwh     = sol_inputs["base_kwh_5kw"]
    rate_2026    = sol_inputs["elec_rate_2026"]
    escalation   = sol_inputs["elec_rate_escalation"]
    degradation  = sol_inputs["degradation_rate"]
    start_year   = years[0]

    rows = []
    cumulative_savings = 0.0

    for yr in years:
        n = yr - start_year
        deg_factor  = (1 - degradation) ** n
        annual_kwh  = base_kwh * deg_factor
        annual_mwh  = annual_kwh / 1000.0
        elec_rate   = rate_2026 * (1 + escalation) ** (yr - 2026)
        savings_usd = annual_kwh * elec_rate
        ci          = carbon_intensity.get(yr, None)
        ghg_mt      = annual_mwh * ci if ci is not None else None
        cumulative_savings += savings_usd

        rows.append({
            "year":                    yr,
            "degradation_factor":      round(deg_factor, 6),
            "annual_kwh":              round(annual_kwh, 1),
            "annual_mwh":              round(annual_mwh, 4),
            "elec_rate":               round(elec_rate, 4),
            "annual_savings_usd":      round(savings_usd, 2),
            "cumulative_savings_usd":  round(cumulative_savings, 2),
            "carbon_intensity_mt_mwh": round(ci, 8) if ci else None,
            "ghg_avoided_mt":          round(ghg_mt, 6) if ghg_mt else None,
        })

    return pd.DataFrame(rows)


def scale_to_program(
    city_dfs: List[pd.DataFrame],
    system_kw: float,
    num_households: int,
) -> pd.DataFrame:
    """Average per-5kW metrics across cities, then scale to program total.

    For a single city, pass a one-element list. For a group of cities,
    per-5kW metrics are averaged first (matching the Excel methodology),
    then scaled by scale_factor × num_households.

    Args:
        city_dfs:       List of per-city DataFrames from compute_city_solar().
        system_kw:      Actual installed system size per household (kW).
        num_households: Total households in the program.

    Returns:
        DataFrame with columns:
            year,
            avg_annual_kwh_5kw, avg_annual_mwh_5kw,   (average per 5kW system)
            avg_ghg_avoided_mt_5kw,
            scale_factor, num_households,
            total_annual_kwh,                           (all HH, actual system)
            total_annual_mwh,
            avg_elec_rate,
            total_annual_savings_usd,
            total_cumulative_savings_usd,
            total_ghg_avoided_mt
    """
    scale_factor = system_kw / BASELINE_SYSTEM_KW

    # Stack and average per 5kW system across cities
    combined = pd.concat(city_dfs)
    avg = combined.groupby("year").agg(
        avg_kwh=("annual_kwh", "mean"),
        avg_mwh=("annual_mwh", "mean"),
        avg_elec_rate=("elec_rate", "mean"),
        avg_savings_usd=("annual_savings_usd", "mean"),
        avg_ghg_mt=("ghg_avoided_mt", "mean"),
    ).reset_index()

    avg["scale_factor"]    = scale_factor
    avg["num_households"]  = num_households

    avg["total_annual_kwh"]              = avg["avg_kwh"] * scale_factor * num_households
    avg["total_annual_mwh"]              = avg["avg_mwh"] * scale_factor * num_households
    avg["total_annual_savings_usd"]      = avg["avg_savings_usd"] * scale_factor * num_households
    avg["total_ghg_avoided_mt"]          = avg["avg_ghg_mt"] * scale_factor * num_households
    avg["total_cumulative_savings_usd"]  = avg["total_annual_savings_usd"].cumsum()

    avg = avg.rename(columns={
        "avg_kwh":         "avg_annual_kwh_5kw",
        "avg_mwh":         "avg_annual_mwh_5kw",
        "avg_savings_usd": "avg_annual_savings_usd_5kw",
        "avg_ghg_mt":      "avg_ghg_avoided_mt_5kw",
    })

    # Round output
    round_map = {
        "avg_annual_kwh_5kw":           1,
        "avg_annual_mwh_5kw":           4,
        "avg_elec_rate":                4,
        "avg_annual_savings_usd_5kw":   2,
        "avg_ghg_avoided_mt_5kw":       6,
        "total_annual_kwh":             0,
        "total_annual_mwh":             2,
        "total_annual_savings_usd":     0,
        "total_cumulative_savings_usd": 0,
        "total_ghg_avoided_mt":         2,
    }
    for col, decimals in round_map.items():
        if col in avg.columns:
            avg[col] = avg[col].round(decimals)

    return avg
