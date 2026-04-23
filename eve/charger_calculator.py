"""EVE charger deployment calculator.

Estimates GHG savings from public EV charger deployment by shifting
VMT from gasoline to electric, relative to the BAU transport baseline.

Calculation chain (verified against Atlanta - Electrification Coalition
Analysis.xlsx, "Charger Deployment" sheet):

  1. Multiplier — scales with charger deployment progress.
     Phase 1 (base_year → phase1_year): linear ramp 0 → phase1_full
       phase1_full = charger_scale_factor × (new_chargers_p1 / existing)
     Phase 2 (phase1_year → phase2_year): adds phase2 on top of phase1_full
       phase2_full = charger_scale_factor × (new_chargers_p2 / existing)
       multiplier = phase1_full + phase2_full × progress_fraction

  2. Shifted VMT — new electric VMT induced by additional chargers.
     shifted_vmt = multiplier × electric_vmt_baseline(year)

  3. Emissions delta — shifted VMT reduces gasoline emissions and
     increases electricity emissions proportionally to BAU fuel shares.
     delta_gasoline   = -shifted_vmt × (gasoline_mt_co2_bau / total_vmt_bau)
     delta_electricity = +shifted_vmt × (electricity_mt_co2_bau / total_vmt_bau)

  Net GHG savings = -(delta_gasoline + delta_electricity)
                  = shifted_vmt × (gasoline_mt_co2_bau - electricity_mt_co2_bau)
                                   / total_vmt_bau

Source: Atlanta - Electrification Coalition Analysis.xlsx, verified for
2027 (delta_gas ≈ -155.44 MT CO2, delta_elec ≈ +1.424 MT CO2).
"""
from typing import Dict, List

import pandas as pd


def compute_charger_multiplier(
    year: int,
    base_year: int,
    phase1_year: int,
    phase2_year: int,
    existing_chargers: float,
    new_chargers_phase1: float,
    new_chargers_phase2: float,
    charger_scale_factor: float = 3.0,
) -> float:
    """Compute the charger deployment multiplier for a given year.

    The multiplier represents the proportional increase in effective
    electric VMT capacity relative to the existing charger stock.

    Args:
        year: Projection year.
        base_year: First year of deployment (multiplier = 0).
        phase1_year: Year Phase 1 deployment completes.
        phase2_year: Year Phase 2 deployment completes.
        existing_chargers: Existing public EVSE ports at base year.
        new_chargers_phase1: New chargers added in Phase 1.
        new_chargers_phase2: Additional new chargers added in Phase 2.
        charger_scale_factor: Scale factor applied to charger ratio (default 3.0).

    Returns:
        Multiplier value (dimensionless). Zero before base_year;
        held at max after phase2_year.
    """
    if year < base_year:
        return 0.0

    phase1_full = charger_scale_factor * (new_chargers_phase1 / existing_chargers)
    phase2_full = charger_scale_factor * (new_chargers_phase2 / existing_chargers)

    if year <= phase1_year:
        progress = (year - base_year) / (phase1_year - base_year)
        return phase1_full * progress
    elif year <= phase2_year:
        progress = (year - phase1_year) / (phase2_year - phase1_year)
        return phase1_full + phase2_full * progress
    else:
        # Hold at full deployment after phase2
        return phase1_full + phase2_full


def compute_charger_savings(
    bau_series: pd.DataFrame,
    eve_inputs: Dict,
    years: List[int],
) -> pd.DataFrame:
    """Compute annual GHG savings from charger deployment.

    For each year, calculates the VMT shift from gasoline to electric
    induced by new chargers and converts it to MT CO2 delta using the
    BAU fuel emission intensities (MT CO2 per unit VMT).

    Args:
        bau_series: BAU transport DataFrame from eve.data_loader.load_bau_transport_series().
            Required columns: year, total_vmt, vmt_electric,
            gasoline_mt_co2, electricity_mt_co2.
        eve_inputs: Dict of city EVE parameters from eve.data_loader.load_eve_inputs().
        years: List of projection years.

    Returns:
        DataFrame with columns:
            year, multiplier, shifted_vmt,
            delta_gasoline_mt_co2, delta_electricity_mt_co2,
            charger_savings_mt_co2
    """
    base_year      = int(eve_inputs["base_year"])
    phase1_year    = int(eve_inputs["phase1_year"])
    phase2_year    = int(eve_inputs["phase2_year"])
    existing       = eve_inputs["existing_public_chargers"]
    new_p1         = eve_inputs["new_chargers_phase1"]
    new_p2         = eve_inputs["new_chargers_phase2"]
    scale          = eve_inputs["charger_scale_factor"]

    rows = []
    bau = bau_series.set_index("year")

    for yr in years:
        multiplier = compute_charger_multiplier(
            yr, base_year, phase1_year, phase2_year,
            existing, new_p1, new_p2, scale,
        )

        bau_yr = bau.loc[yr]
        electric_vmt   = bau_yr["vmt_electric"]
        total_vmt      = bau_yr["total_vmt"]
        gas_intensity  = bau_yr["gasoline_mt_co2"] / total_vmt   # MT CO2 per VMT mile
        elec_intensity = bau_yr["electricity_mt_co2"] / total_vmt

        shifted_vmt = multiplier * electric_vmt

        delta_gas  = -shifted_vmt * gas_intensity
        delta_elec = +shifted_vmt * elec_intensity

        # Savings = reduction in net emissions (positive = less CO2)
        charger_savings = -(delta_gas + delta_elec)

        rows.append({
            "year":                    yr,
            "multiplier":              multiplier,
            "shifted_vmt":             shifted_vmt,
            "delta_gasoline_mt_co2":   delta_gas,
            "delta_electricity_mt_co2": delta_elec,
            "charger_savings_mt_co2":  charger_savings,
        })

    return pd.DataFrame(rows)
