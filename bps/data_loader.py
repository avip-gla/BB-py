"""BPS data loading module.

Loads BPS-specific data (SLOPE building area thresholds) and pulls shared
consumption baselines from the same SLOPE source files used by bau/.

Data sources:
  BPS-specific:
    - data/inputs/bps/<city>.csv — SLOPE building area thresholds
  Shared with bau/ (same underlying SLOPE extractions):
    - data/inputs/electricity/electricity_commercial_consumption.csv
    - data/inputs/ng/ng_commercial_consumption.csv
    - data/aeo/aeo_carbon_intensity.csv
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from bps.config import (
    BPS_DATA_DIR,
    SLOPE_PROJECTION_STEP_SQFT,
    SLOPE_MAX_KNOWN_THRESHOLD,
    SLOPE_PROJECTION_TARGET,
)
from bau.config import INPUTS_DIR, AEO_DIR


def load_slope_areas(city: str, path: Optional[str] = None) -> pd.DataFrame:
    """Load SLOPE building area thresholds for a city.

    Source: SLOPE tool via Philly BEPP Excel R6-R16.
    Contains total commercial building area and areas for buildings
    exceeding each threshold (5k, 10k, ... 50k sq ft).

    Args:
        city: City name (lowercase used for filename).
        path: Optional path override.

    Returns:
        DataFrame with columns: threshold, area_sqft, building_count.
    """
    if path is None:
        path = BPS_DATA_DIR / f"{city.lower().replace(' ', '_')}.csv"
    return pd.read_csv(path)


def project_area_bins(
    slope_df: pd.DataFrame,
    bins: List[Tuple[str, int, Optional[int]]],
) -> Dict[str, float]:
    """Project building area for BPS bins beyond the SLOPE 50k threshold.

    Uses the rate of change between the last two known SLOPE thresholds
    (barea_gt_45k / barea_gt_50k) to extrapolate areas at higher thresholds
    in 5k increments up to 200k+.

    Source: Excel BPS!R17-R46 projection logic.
    Excel formula: S17 = U17 * S16, where U17 = U16 = S16/S15 (constant ratio).

    Args:
        slope_df: SLOPE area thresholds from load_slope_areas().
        bins: List of (label, lower_sqft, upper_sqft_or_None) bin definitions.

    Returns:
        Dict mapping bin label -> area in sq ft.
        Also includes 'total' key for total commercial area.
    """
    # Build lookup: threshold_sqft -> area
    threshold_areas = {}
    total_area = None
    for _, row in slope_df.iterrows():
        thresh = row["threshold"]
        area = row["area_sqft"]
        if thresh == "full_summary":
            total_area = area
        elif thresh.startswith("barea_gt_"):
            sqft = int(thresh.replace("barea_gt_", "").replace("k", "")) * 1000
            threshold_areas[sqft] = area

    # Calculate projection ratio from last two known thresholds
    # Excel: U16 = S16/S15 (barea_gt_50k / barea_gt_45k)
    ratio = threshold_areas[SLOPE_MAX_KNOWN_THRESHOLD] / threshold_areas[45_000]

    # Project areas beyond 50k in 5k increments up to target
    current_sqft = SLOPE_MAX_KNOWN_THRESHOLD
    while current_sqft < SLOPE_PROJECTION_TARGET:
        next_sqft = current_sqft + SLOPE_PROJECTION_STEP_SQFT
        threshold_areas[next_sqft] = threshold_areas[current_sqft] * ratio
        current_sqft = next_sqft

    # Calculate bin areas as differences between thresholds
    result = {"total": total_area}
    for label, lower, upper in bins:
        if upper is None:
            # Open-ended bin (e.g., 200k+): area at the lower threshold
            result[label] = threshold_areas[lower]
        else:
            # Bounded bin: area at lower threshold minus area at upper threshold
            result[label] = threshold_areas[lower] - threshold_areas[upper]

    return result


def calculate_area_percentages(
    bin_areas: Dict[str, float],
) -> Dict[str, float]:
    """Convert bin areas to percentages of total commercial area.

    Source: Excel BPS!P19-P22.
    Excel formula: P19 = O19 / S$6 (bin area / total area).

    Args:
        bin_areas: Dict from project_area_bins() with bin areas and 'total'.

    Returns:
        Dict mapping bin label -> fraction of total area (0 to 1).
    """
    total = bin_areas["total"]
    return {
        label: area / total
        for label, area in bin_areas.items()
        if label != "total"
    }


def load_commercial_electricity_consumption(
    city: str,
    years: List[int],
    path: Optional[str] = None,
) -> Dict[int, float]:
    """Load commercial electricity consumption (MMBtu) by year for a city.

    Source: Excel 'Electricity' tab R168-R192 (commercial MMBtu).
    Same SLOPE data used by bau/buildings.py.

    Args:
        city: City name.
        years: List of years to load.
        path: Optional path override.

    Returns:
        Dict mapping year -> commercial electricity consumption in MMBtu.
    """
    if path is None:
        path = INPUTS_DIR / "electricity" / "electricity_commercial_consumption.csv"
    df = pd.read_csv(path)
    row = df[df["city"] == city]
    if row.empty:
        raise ValueError(f"City '{city}' not found in commercial electricity data")
    row = row.iloc[0]
    return {yr: float(row[f"y{yr}"]) for yr in years if f"y{yr}" in row.index}


def load_commercial_ng_consumption(
    city: str,
    years: List[int],
    path: Optional[str] = None,
) -> Dict[int, float]:
    """Load commercial NG consumption (MMBtu) by year for a city.

    Source: Excel 'NG' tab R115-R140 (commercial MMBtu).
    Uses the wide-format CSV with columns y2024-y2050 for full year coverage.
    Same SLOPE data used by bau/buildings.py.

    Args:
        city: City name.
        years: List of years to load.
        path: Optional path override.

    Returns:
        Dict mapping year -> commercial NG consumption in MMBtu.
    """
    if path is None:
        path = INPUTS_DIR / "ng" / "ng_commercial_consumption_full.csv"
    df = pd.read_csv(path)
    row = df[df["city"] == city]
    if row.empty:
        raise ValueError(f"City '{city}' not found in commercial NG data")
    row = row.iloc[0]
    return {yr: float(row[f"y{yr}"]) for yr in years if f"y{yr}" in row.index}


def load_carbon_intensity(
    region: str,
    years: List[int],
    path: Optional[str] = None,
) -> Dict[int, float]:
    """Load AEO regional carbon intensity (MT CO2/MWh) by year.

    Source: AEO Table 54 via data/aeo/aeo_carbon_intensity.csv.
    Same data used by bau/buildings.py.

    Args:
        region: AEO electricity market region code (e.g., 'PJME').
        years: List of years to load.
        path: Optional path override.

    Returns:
        Dict mapping year -> carbon intensity in MT CO2/MWh.
    """
    if path is None:
        path = AEO_DIR / "aeo_carbon_intensity.csv"
    df = pd.read_csv(path)
    row = df[df["region"] == region]
    if row.empty:
        raise ValueError(f"Region '{region}' not found in AEO carbon intensity data")
    row = row.iloc[0]
    return {yr: float(row[f"y{yr}"]) for yr in years if f"y{yr}" in row.index}


def load_all_bps_data(city: str, policy: dict) -> dict:
    """Load all data needed for a BPS calculation.

    Combines BPS-specific SLOPE area data with shared consumption baselines
    and AEO carbon intensity data.

    Args:
        city: City name.
        policy: Policy dict from CITY_BPS_POLICIES.

    Returns:
        Dict with keys: slope_areas, bin_areas, area_pcts,
        elec_consumption, ng_consumption, carbon_intensity.
    """
    years = policy["projection_years"]
    region = policy["region"]
    bins = policy["bins"]

    slope_df = load_slope_areas(city)
    bin_areas = project_area_bins(slope_df, bins)
    area_pcts = calculate_area_percentages(bin_areas)

    elec = load_commercial_electricity_consumption(city, years)
    ng = load_commercial_ng_consumption(city, years)
    ci = load_carbon_intensity(region, years)

    return {
        "slope_areas": slope_df,
        "bin_areas": bin_areas,
        "area_pcts": area_pcts,
        "elec_consumption": elec,
        "ng_consumption": ng,
        "carbon_intensity": ci,
    }
