"""EVE fleet electrification calculator.

Estimates GHG savings from electrifying city and airport vehicle fleets
(light-duty, medium-duty, heavy-duty) along a linear ramp schedule.

All inputs are city-specific and loaded from data/inputs/eve/<city>.csv.
No VMT data is used here — fleet savings depend only on vehicle counts
and per-vehicle annual savings rates.

Calculation chain (logic verified against Atlanta - Electrification Coalition
Analysis.xlsx "Fleet" sheet; same formula applies to any city):

  Fleet totals:
    total_ldv = fleet_ldv_city + fleet_ldv_airport
    total_mdv = fleet_mdv_city + fleet_mdv_airport
    total_hdv = fleet_hdv_city + fleet_hdv_airport

  Targets (from pct_zev parameters):
    target_ldv_2035 = total_ldv × pct_zev_2035   (e.g. 50%)
    target_ldv_2040 = total_ldv × pct_zev_2040   (e.g. 100%)
    (same for MDV and HDV)

  Linear ramp (Phase 1: base_year → 2035, 9 steps):
    step_ldv = (target_ldv_2035 - init_ldv_2026) / (2035 - base_year)
    step_mdv = (target_mdv_2035 - init_mdv_2026) / (2035 - base_year)
    step_hdv = (target_hdv_2035 - init_hdv_2026) / (2035 - base_year)

    cumulative_ldv(year) = init_ldv + step_ldv × (year - base_year)  [if year ≤ 2035]

  Linear ramp (Phase 2: 2035 → 2040, 5 steps):
    step2_ldv = (target_ldv_2040 - target_ldv_2035) / (2040 - 2035)
    cumulative_ldv(year) = target_ldv_2035 + step2_ldv × (year - 2035)  [if year > 2035]

  Hold at 100% after 2040.

  Annual savings:
    savings = cumulative_ldv × savings_ldv + cumulative_mdv × savings_mdv
              + cumulative_hdv × savings_hdv    [MT CO2/yr]

Source: Atlanta - Electrification Coalition Analysis.xlsx.
Verified:
  2026: 50×2.73 + 0×12.18 + 12×21.13 = 390.06 MT CO2 ✓
  2027: 207.72×2.73 + 43.44×12.18 + 35.61×21.13 ≈ 1,856 MT CO2 ✓
  (cumulative includes init + one step)
"""
from typing import Dict, List

import pandas as pd


def _ramp(init: float, target1: float, target2: float,
          base_year: int, mid_year: int, end_year: int,
          year: int) -> float:
    """Linear two-phase ramp for a single vehicle class.

    Phase 1: base_year → mid_year (linear from init → target1).
    Phase 2: mid_year → end_year (linear from target1 → target2).
    Held at target2 after end_year.
    """
    if year <= base_year:
        return init
    elif year <= mid_year:
        steps = mid_year - base_year
        progress = year - base_year
        return init + (target1 - init) * progress / steps
    elif year <= end_year:
        steps = end_year - mid_year
        progress = year - mid_year
        return target1 + (target2 - target1) * progress / steps
    else:
        return target2


def compute_fleet_savings(
    eve_inputs: Dict,
    years: List[int],
) -> pd.DataFrame:
    """Compute annual GHG savings from fleet electrification.

    Computes the cumulative number of electrified vehicles per class
    for each year, then multiplies by class-specific savings factors.

    Args:
        eve_inputs: Dict of city EVE parameters from eve.data_loader.load_eve_inputs().
        years: List of projection years.

    Returns:
        DataFrame with columns:
            year,
            cumulative_ldv, cumulative_mdv, cumulative_hdv,
            fleet_savings_mt_co2
    """
    base_year  = int(eve_inputs["base_year"])
    mid_year   = 2035
    end_year   = 2040

    total_ldv = eve_inputs["fleet_ldv_city"] + eve_inputs["fleet_ldv_airport"]
    total_mdv = eve_inputs["fleet_mdv_city"] + eve_inputs["fleet_mdv_airport"]
    total_hdv = eve_inputs["fleet_hdv_city"] + eve_inputs["fleet_hdv_airport"]

    pct_mid = eve_inputs["pct_zev_2035"]
    pct_end = eve_inputs["pct_zev_2040"]

    target_ldv_mid = total_ldv * pct_mid
    target_mdv_mid = total_mdv * pct_mid
    target_hdv_mid = total_hdv * pct_mid

    target_ldv_end = total_ldv * pct_end
    target_mdv_end = total_mdv * pct_end
    target_hdv_end = total_hdv * pct_end

    init_ldv = eve_inputs["fleet_ldv_init_2026"]
    init_mdv = eve_inputs["fleet_mdv_init_2026"]
    init_hdv = eve_inputs["fleet_hdv_init_2026"]

    sv_ldv = eve_inputs["savings_ldv_mt_co2"]
    sv_mdv = eve_inputs["savings_mdv_mt_co2"]
    sv_hdv = eve_inputs["savings_hdv_mt_co2"]

    # Compute the ramp step size (Phase 1: base_year+1 → mid_year, 9 steps).
    # The step excludes the init vehicles so the ramp count starts from 0 in
    # base_year+1, matching the Excel formula =($C14+prev) in the Fleet sheet.
    step_ldv = (target_ldv_mid - init_ldv) / (mid_year - base_year)
    step_mdv = (target_mdv_mid - init_mdv) / (mid_year - base_year)
    step_hdv = (target_hdv_mid - init_hdv) / (mid_year - base_year)

    step2_ldv = (target_ldv_end - target_ldv_mid) / (end_year - mid_year)
    step2_mdv = (target_mdv_end - target_mdv_mid) / (end_year - mid_year)
    step2_hdv = (target_hdv_end - target_hdv_mid) / (end_year - mid_year)

    def ramp_vehicles(yr: int) -> tuple:
        """Return (ramp_ldv, ramp_mdv, ramp_hdv) — cumulative ramp count,
        EXCLUDING init vehicles. Matches Excel rows 14-16.

        Phase 1 (base_year+1 → mid_year): grows by step each year.
        Phase 2 (mid_year+1 → end_year): grows by step2 each year (on top of Phase 1).
        Held at full target after end_year.
        """
        if yr <= base_year:
            return 0.0, 0.0, 0.0
        elif yr <= mid_year:
            n = yr - base_year
            return n * step_ldv, n * step_mdv, n * step_hdv
        elif yr <= end_year:
            n1 = mid_year - base_year
            n2 = yr - mid_year
            return (n1 * step_ldv + n2 * step2_ldv,
                    n1 * step_mdv + n2 * step2_mdv,
                    n1 * step_hdv + n2 * step2_hdv)
        else:
            # Full electrification achieved; hold at total fleet (excluding init)
            return (total_ldv - init_ldv, total_mdv - init_mdv, total_hdv - init_hdv)

    rows = []
    for yr in years:
        r_ldv, r_mdv, r_hdv = ramp_vehicles(yr)

        # Annual savings = (init vehicles + cumulative ramp vehicles) × per-vehicle rate.
        # Init vehicles are counted every year from base_year onwards — they remain
        # electrified and save emissions continuously.
        # Ramp vehicles accumulate over time (0 in base_year, growing thereafter).
        savings = (
            (init_ldv + r_ldv) * sv_ldv
            + (init_mdv + r_mdv) * sv_mdv
            + (init_hdv + r_hdv) * sv_hdv
        )

        rows.append({
            "year":                 yr,
            "ramp_ldv":             r_ldv,
            "ramp_mdv":             r_mdv,
            "ramp_hdv":             r_hdv,
            "fleet_savings_mt_co2": savings,
        })

    return pd.DataFrame(rows)
