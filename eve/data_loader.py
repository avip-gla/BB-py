"""EVE data loader.

Loads city-specific EV electrification inputs from CSV and retrieves
BAU transport baseline data (VMT by fuel, emissions by fuel) from the
bau module.
"""
from pathlib import Path
from typing import Dict, List

import pandas as pd

from eve.config import EVE_DATA_DIR, EVE_YEARS


def load_eve_inputs(city_name: str) -> Dict:
    """Load city-specific EVE parameters from data/inputs/eve/<city>.csv.

    The CSV has columns: parameter, value, notes.
    Returns a dict keyed by parameter name with float values.

    Args:
        city_name: City name matching the CSV filename (e.g. "Atlanta").

    Returns:
        Dict of parameter name → value (numeric).
    """
    csv_path = EVE_DATA_DIR / f"{city_name.lower()}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(
            f"EVE inputs not found for {city_name!r}. "
            f"Expected: {csv_path}"
        )
    df = pd.read_csv(csv_path)
    return {row["parameter"]: float(row["value"]) for _, row in df.iterrows()}


def load_bau_transport_series(city_name: str, all_data: dict, years: List[int] = None) -> pd.DataFrame:
    """Compute BAU transport emissions and VMT by fuel for one city.

    Replicates the per-fuel breakdown from the bau transport pipeline
    (project_vmt → calculate_fuel_consumption → calculate_transport_emissions)
    for every year requested.

    Args:
        city_name: City name (must exist in CITY_STATE_MAP).
        all_data: Output of bau.data_loader.load_all_data().
        years: List of years to compute. Defaults to EVE_YEARS.

    Returns:
        DataFrame with columns:
            year, total_vmt,
            vmt_electric, vmt_conventional_gasoline,
            gasoline_mt_co2, diesel_mt_co2, ethanol_mt_co2,
            electricity_mt_co2, total_mt_co2
    """
    from bau.config import CITY_STATE_MAP, CITY_REGION_MAP, CITY_AEO_SALES_REGION_MAP
    from bau.data_loader import get_carbon_intensity, get_ldv_sales_share
    from bau.transport import project_vmt, calculate_fuel_consumption, calculate_transport_emissions

    if years is None:
        years = EVE_YEARS

    state = CITY_STATE_MAP[city_name]
    region = CITY_REGION_MAP[city_name]
    sales_region = CITY_AEO_SALES_REGION_MAP.get(city_name, "South Atlantic")

    # Base VMT from FHWA
    fhwa = all_data["fhwa_vmt"]
    row = fhwa[fhwa["city"] == city_name].iloc[0]
    total_vmt_base = float(row["total_annual_vmt"]) * 1000

    # AFDC fuel shares for base year and delta
    col_map = {
        "gasoline": "conventional_gasoline",
        "diesel": "tdi_diesel",
        "ethanol_flex_e85": "flex_fuel",
        "electric_ev": "electric",
        "plug-in_hybrid_electric_phev": "plugin_hybrid",
        "hybrid_electric_hev": "electric_hybrid",
        "biodiesel": "biodiesel",
    }
    shares_df = all_data["afdc_shares"]
    state_row = shares_df[
        (shares_df["state"] == state) & (shares_df["year"] == 2024)
    ].iloc[0]
    afdc_shares = {v: float(state_row.get(k, 0)) for k, v in col_map.items()}

    deltas_df = all_data["afdc_growth_deltas"]
    delta_row = deltas_df[deltas_df["state"] == state].iloc[0]
    afdc_deltas = {v: float(delta_row.get(k, 0)) for k, v in col_map.items()}

    vmt_df = project_vmt(total_vmt_base, afdc_shares, afdc_deltas, years)

    rows = []
    for yr in years:
        yr_row = vmt_df[vmt_df["year"] == yr].iloc[0]
        vmt_by_fuel = {
            "conventional_gasoline": yr_row["vmt_conventional_gasoline"],
            "tdi_diesel":            yr_row["vmt_tdi_diesel"],
            "flex_fuel":             yr_row["vmt_flex_fuel"],
            "electric":              yr_row["vmt_electric"],
            "plugin_hybrid":         yr_row["vmt_plugin_hybrid"],
            "electric_hybrid":       yr_row["vmt_electric_hybrid"],
            "biodiesel":             yr_row.get("vmt_biodiesel", 0),
        }
        car_frac = get_ldv_sales_share(sales_region, "Cars", yr, all_data["aeo_ldv_sales"])
        truck_frac = get_ldv_sales_share(sales_region, "Pick Up Trucks", yr, all_data["aeo_ldv_sales"])

        fuel = calculate_fuel_consumption(
            vmt_by_fuel, yr, all_data["aeo_mpg"],
            car_fraction=car_frac, truck_fraction=truck_frac,
            aeo_freight=all_data["aeo_freight"],
        )
        ci = get_carbon_intensity(region, yr, all_data["aeo_ci"])
        em = calculate_transport_emissions(fuel, ci)

        rows.append({
            "year":                       yr,
            "total_vmt":                  yr_row["vmt_total"],
            "vmt_electric":               yr_row["vmt_electric"],
            "vmt_conventional_gasoline":  yr_row["vmt_conventional_gasoline"],
            "gasoline_mt_co2":            em["gasoline_mt_co2"],
            "diesel_mt_co2":              em["diesel_mt_co2"],
            "ethanol_mt_co2":             em["ethanol_mt_co2"],
            "electricity_mt_co2":         em["electricity_mt_co2"],
            "total_mt_co2":               em["total_mt_co2"],
        })

    return pd.DataFrame(rows)
