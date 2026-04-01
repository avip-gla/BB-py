"""BPS calculation engine.

Supports two policy types:

1. Retrocommissioning (Philadelphia BEPP):
   Staggered bin reductions with renewal cycle.
   Source: Philly BEPP.xlsx 'BPS' tab.
   Key formulas:
     Baselines:     Row 81 = Row 93 * $P19  (total elec * area_pct)
     1st reduction: Row 69 = Row 81 * $B$3  (baseline * savings_rate)
     After 1st:     Row 57 = Row 81 - Row 69
     2nd reduction: Row 45 = Row 57 * $B$3  (new_baseline * savings_rate)
     After 2nd:     Row 33 = Row 57 - Row 45
     Savings:       Row 21 = Row 81 - Row 33 (baseline - final consumption)
     MWh savings:   Row 16 = Row 21 * 0.3
     GHG:           Row 8  = Row 16 * CI + Row 26 * NG_EF

2. Benchmarking (Kansas City Energy Empowerment Ordinance):
   Year-over-year savings with single bin, no renewal.
   Source: KC Benchmarking Analysis.xlsx 'BPS' tab.
   Key formulas:
     Baselines:     Row 23 = Row 33 * $Q$19  (total elec * area_pct)
     Reduction:     Row 19 = Row 23 * $B$3   (baseline * 3%)
     New cons:      Row 15 = Row 23 - Row 19
     Savings:       Row 11 = baseline(yr) - new_cons(yr-1)
     MWh savings:   Row 10 = Row 11 * 0.3
     GHG:           Row 7  = Row 10 * CI(yr-1) + Row 12 * NG_EF
   Note: CI uses previous year's value (ci_lag=True).
"""
from typing import Dict, List, Optional, Tuple

from bps.config import MWH_CONV, NG_EF


def calculate_baselines(
    total_consumption: Dict[int, float],
    area_pcts: Dict[str, float],
    years: List[int],
) -> Dict[str, Dict[int, float]]:
    """Calculate consumption baselines by bin for each year.

    Each bin's baseline = total commercial consumption * bin's area percentage.

    Source: Excel BPS! rows 81-84 (electricity), 86-89 (gas).
    Formula: B81 = B$93 * $P19

    Args:
        total_consumption: Dict mapping year -> total commercial consumption (MMBtu).
        area_pcts: Dict mapping bin label -> fraction of total area.
        years: List of projection years.

    Returns:
        Dict mapping bin_label -> {year -> baseline consumption MMBtu}.
    """
    result = {}
    for label, pct in area_pcts.items():
        result[label] = {yr: total_consumption[yr] * pct for yr in years
                         if yr in total_consumption}
    return result


def apply_staggered_reduction(
    baselines: Dict[str, Dict[int, float]],
    savings_rate: float,
    implementation_years: Dict[str, int],
    years: List[int],
) -> Tuple[Dict[str, Dict[int, float]], Dict[str, Dict[int, float]]]:
    """Apply a staggered percentage reduction to baselines.

    Each bin begins its reduction the year AFTER its implementation year.
    The reduction = baseline * savings_rate for years at or after the start.

    Source: Excel BPS! rows 69-72 (1st elec reduction), rows 74-77 (1st gas).
    Formula: C69 = C81 * $B$3 (starting at stagger year)

    Args:
        baselines: Dict from calculate_baselines().
        savings_rate: Fractional reduction (e.g., 0.15 for 15%).
        implementation_years: Dict mapping bin label -> implementation year.
            Energy savings begin the year after this.
        years: List of projection years.

    Returns:
        Tuple of:
          - reductions: {bin_label -> {year -> reduction amount}}
          - new_baselines: {bin_label -> {year -> baseline after reduction}}
    """
    reductions = {}
    new_baselines = {}

    for label, baseline_series in baselines.items():
        impl_year = implementation_years[label]
        savings_start = impl_year + 1  # savings begin year after implementation

        reductions[label] = {}
        new_baselines[label] = {}

        for yr in years:
            base = baseline_series.get(yr, 0)
            if yr >= savings_start:
                red = base * savings_rate
            else:
                red = 0.0
            reductions[label][yr] = red
            new_baselines[label][yr] = base - red

    return reductions, new_baselines


def calculate_bps_reductions(
    elec_consumption: Dict[int, float],
    ng_consumption: Dict[int, float],
    carbon_intensity: Dict[int, float],
    area_pcts: Dict[str, float],
    savings_rate: float,
    implementation_years: Dict[str, int],
    renewal_year: int,
    years: List[int],
) -> dict:
    """Run the full BPS reduction calculation for a city.

    Two-round process:
      Round 1: Apply savings_rate reduction starting at each bin's
               implementation year + 1.
      Round 2: Apply savings_rate reduction to the new baselines (after round 1),
               starting at renewal_year + 1 + bin offset.

    The renewal implementation follows the same stagger pattern as the original,
    offset from renewal_year + 1 (Excel interprets "renews in 2030" as renewal
    announced in 2030, implementation begins 2031, savings begin 2032).

    Source: Excel BPS! tab full calculation chain.

    Args:
        elec_consumption: {year -> total commercial electricity MMBtu}.
        ng_consumption: {year -> total commercial NG MMBtu}.
        carbon_intensity: {year -> regional CI in MT CO2/MWh}.
        area_pcts: {bin_label -> fraction of total commercial area}.
        savings_rate: Fractional reduction (e.g., 0.15).
        implementation_years: {bin_label -> first round implementation year}.
        renewal_year: Year the policy cycle renews.
        years: List of projection years.

    Returns:
        Dict with keys:
          - years: list of years
          - bins: list of bin labels
          - elec_baselines: {bin -> {year -> MMBtu}}
          - ng_baselines: {bin -> {year -> MMBtu}}
          - elec_savings: {bin -> {year -> MMBtu saved}}
          - ng_savings: {bin -> {year -> MMBtu saved}}
          - elec_savings_mwh: {bin -> {year -> MWh saved}}
          - ghg_reduction: {bin -> {year -> MT CO2 reduced}}
          - total_ghg_by_year: {year -> total MT CO2 reduced}
          - total_ghg: grand total MT CO2 reduced across all years
    """
    bins = list(area_pcts.keys())

    # ---- Electricity ----
    elec_baselines = calculate_baselines(elec_consumption, area_pcts, years)

    # Round 1
    elec_red1, elec_after1 = apply_staggered_reduction(
        elec_baselines, savings_rate, implementation_years, years
    )

    # Round 2: renewal stagger is offset from renewal_year + 1
    # Excel: 200k+ renewal impl 2031, savings 2032 (= renewal_year + 1 + 0 + 1)
    # The offset for each bin relative to the first bin is preserved.
    first_impl = min(implementation_years.values())
    renewal_impl_years = {
        label: renewal_year + 1 + (impl_yr - first_impl)
        for label, impl_yr in implementation_years.items()
    }
    elec_red2, elec_after2 = apply_staggered_reduction(
        elec_after1, savings_rate, renewal_impl_years, years
    )

    # Total electricity savings = baseline - after_both_rounds
    elec_savings = {}
    for label in bins:
        elec_savings[label] = {
            yr: elec_baselines[label].get(yr, 0) - elec_after2[label].get(yr, 0)
            for yr in years
        }

    # ---- Natural Gas ----
    ng_baselines = calculate_baselines(ng_consumption, area_pcts, years)

    ng_red1, ng_after1 = apply_staggered_reduction(
        ng_baselines, savings_rate, implementation_years, years
    )
    ng_red2, ng_after2 = apply_staggered_reduction(
        ng_after1, savings_rate, renewal_impl_years, years
    )

    ng_savings = {}
    for label in bins:
        ng_savings[label] = {
            yr: ng_baselines[label].get(yr, 0) - ng_after2[label].get(yr, 0)
            for yr in years
        }

    # ---- Convert to MWh and GHG ----
    # Excel: Row 16 = Row 21 * 0.3 (MMBtu -> MWh)
    # Excel: Row 8 = (Row 16 * CI) + (Row 26 * NG_EF)
    elec_savings_mwh = {}
    ghg_reduction = {}
    for label in bins:
        elec_savings_mwh[label] = {
            yr: elec_savings[label][yr] * MWH_CONV
            for yr in years
        }
        ghg_reduction[label] = {
            yr: (elec_savings_mwh[label][yr] * carbon_intensity.get(yr, 0)
                 + ng_savings[label][yr] * NG_EF)
            for yr in years
        }

    # ---- Totals ----
    total_ghg_by_year = {
        yr: sum(ghg_reduction[label][yr] for label in bins)
        for yr in years
    }
    total_ghg = sum(total_ghg_by_year.values())

    return {
        "years": years,
        "bins": bins,
        "elec_baselines": elec_baselines,
        "ng_baselines": ng_baselines,
        "elec_savings": elec_savings,
        "ng_savings": ng_savings,
        "elec_savings_mwh": elec_savings_mwh,
        "ghg_reduction": ghg_reduction,
        "total_ghg_by_year": total_ghg_by_year,
        "total_ghg": total_ghg,
    }


def calculate_benchmarking_reductions(
    elec_consumption: Dict[int, float],
    ng_consumption: Dict[int, float],
    carbon_intensity: Dict[int, float],
    area_pcts: Dict[str, float],
    savings_rate: float,
    years: List[int],
    ci_lag: bool = True,
) -> dict:
    """Run benchmarking-style BPS calculation (Kansas City model).

    Year-over-year savings with a single bin, no stagger or renewal.
    The reduction is applied as a flat percentage of the baseline each year.
    Savings are measured as baseline(yr) - new_consumption(yr-1), capturing
    both the policy reduction and natural baseline trajectory changes.

    Source: KC Benchmarking Analysis.xlsx 'BPS' tab.

    Key formulas:
      Row 23: baseline(yr) = total_consumption(yr) * area_pct
      Row 19: reduction(yr) = baseline(yr) * savings_rate
      Row 15: new_cons(yr) = baseline(yr) - reduction(yr)
      Row 11: savings(yr) = baseline(yr) - new_cons(yr-1)
      Row 10: savings_mwh(yr) = savings_mmbtu(yr) * 0.3
      Row  7: ghg(yr) = savings_mwh(yr) * CI(yr-1) + gas_savings(yr) * NG_EF

    Args:
        elec_consumption: {year -> total commercial electricity MMBtu}.
        ng_consumption: {year -> total commercial NG MMBtu}.
        carbon_intensity: {year -> regional CI in MT CO2/MWh}.
        area_pcts: {bin_label -> fraction of total commercial area}.
        savings_rate: Fractional reduction (e.g., 0.03 for 3%).
        years: List of projection years (first year is lead-in for reductions).
        ci_lag: If True, GHG uses previous year's CI (Excel behavior).

    Returns:
        Dict with same structure as calculate_bps_reductions().
    """
    bins = list(area_pcts.keys())

    # ---- Baselines ----
    elec_baselines = calculate_baselines(elec_consumption, area_pcts, years)
    ng_baselines = calculate_baselines(ng_consumption, area_pcts, years)

    elec_savings = {}
    ng_savings = {}
    elec_savings_mwh = {}
    ghg_reduction = {}

    for label in bins:
        elec_bl = elec_baselines[label]
        ng_bl = ng_baselines[label]

        # New consumption after reduction each year
        # Excel Row 19: reduction = baseline * savings_rate
        # Excel Row 15: new_cons = baseline - reduction
        elec_new_cons = {yr: elec_bl[yr] * (1 - savings_rate) for yr in years}
        ng_new_cons = {yr: ng_bl[yr] * (1 - savings_rate) for yr in years}

        # Savings = baseline(yr) - new_cons(yr-1)
        # Excel Row 11: C11 = C23 - B15
        # First year has no savings (no prior year new_cons to compare against)
        e_savings = {}
        n_savings = {}
        e_savings_mwh = {}
        ghg = {}

        for i, yr in enumerate(years):
            if i == 0:
                # Lead-in year: reduction is applied but savings not yet measured
                e_savings[yr] = 0.0
                n_savings[yr] = 0.0
            else:
                prev_yr = years[i - 1]
                # Excel: savings = baseline(yr) - new_consumption(yr-1)
                e_savings[yr] = elec_bl[yr] - elec_new_cons[prev_yr]
                n_savings[yr] = ng_bl[yr] - ng_new_cons[prev_yr]

            e_savings_mwh[yr] = e_savings[yr] * MWH_CONV

            # GHG: use previous year CI if ci_lag, else current year
            if ci_lag and i > 0:
                ci_yr = years[i - 1]
            else:
                ci_yr = yr
            ci_val = carbon_intensity.get(ci_yr, 0)

            ghg[yr] = e_savings_mwh[yr] * ci_val + n_savings[yr] * NG_EF

        elec_savings[label] = e_savings
        ng_savings[label] = n_savings
        elec_savings_mwh[label] = e_savings_mwh
        ghg_reduction[label] = ghg

    # ---- Totals ----
    total_ghg_by_year = {
        yr: sum(ghg_reduction[label][yr] for label in bins)
        for yr in years
    }
    total_ghg = sum(total_ghg_by_year.values())

    return {
        "years": years,
        "bins": bins,
        "elec_baselines": elec_baselines,
        "ng_baselines": ng_baselines,
        "elec_savings": elec_savings,
        "ng_savings": ng_savings,
        "elec_savings_mwh": elec_savings_mwh,
        "ghg_reduction": ghg_reduction,
        "total_ghg_by_year": total_ghg_by_year,
        "total_ghg": total_ghg,
    }


def run_bps(city: str, data: dict, policy: dict) -> dict:
    """Convenience wrapper: run BPS calculation for a city.

    Dispatches to the appropriate calculator based on policy_type.

    Args:
        city: City name.
        data: Dict from load_all_bps_data().
        policy: Policy dict from CITY_BPS_POLICIES.

    Returns:
        Full results dict from the appropriate calculator.
    """
    policy_type = policy.get("policy_type", "retrocommissioning")

    if policy_type == "benchmarking":
        return calculate_benchmarking_reductions(
            elec_consumption=data["elec_consumption"],
            ng_consumption=data["ng_consumption"],
            carbon_intensity=data["carbon_intensity"],
            area_pcts=data["area_pcts"],
            savings_rate=policy["savings_rate"],
            years=policy["projection_years"],
            ci_lag=policy.get("ci_lag", True),
        )
    else:
        return calculate_bps_reductions(
            elec_consumption=data["elec_consumption"],
            ng_consumption=data["ng_consumption"],
            carbon_intensity=data["carbon_intensity"],
            area_pcts=data["area_pcts"],
            savings_rate=policy["savings_rate"],
            implementation_years=policy["implementation_years"],
            renewal_year=policy["renewal_year"],
            years=policy["projection_years"],
        )
