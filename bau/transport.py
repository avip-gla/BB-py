"""Transportation sector emissions calculation module.

Translates the Excel 'Transport' tab into Python.

The transport model works as follows:
1. Start with total VMT for each city (from FHWA data, 2024)
2. Allocate VMT by fuel type using AFDC state vehicle registration shares
3. Project total VMT forward using flat 0.6%/year national growth rate (FHWA)
4. Evolve fuel shares using AFDC growth deltas (2024-2023 change, applied once)
5. Convert VMT to fuel consumption using AEO MPG by vehicle type
6. Convert fuel consumption to emissions using EPA emission factors

VMT projection methodology (Baseline Module Documentation):
- Total VMT grows at flat 0.6%/year: total_vmt(Y) = total_vmt(2024) * (1.006)^(Y-2024)
- Year 1 (2024) fuel shares = AFDC 2024 registration shares
- Year 2+ fuel shares = 2024_share + growth_delta (FIXED, not cumulative)
- Shares clamped >= 0 and re-normalized to sum to 1.0
- fuel_vmt(Y) = total_vmt(Y) * fuel_share(Y)

Seven fuel types: gasoline, diesel, ethanol, electric, plugin_hybrid,
electric_hybrid, biodiesel. Biodiesel gallons use the diesel emission factor.

Key Excel formulas and their locations:
- Total VMT (R44): =XLOOKUP(city, FHWA!A9:A33, FHWA!AB9:AB33) * 1000
- VMT allocation (R45): =$B$44 * XLOOKUP($B$42, B$67:AZ$67, B68:AZ68)
- Fuel consumption: VMT * vehicle_share / MPG
  - Car gasoline (R20): =E45 * $F53 * AEO!E103 / AEO!E9
  - Truck gasoline (R26): =E45 * $F53 * AEO!E104 / AEO!E24
  - Freight gasoline (R33): =E45 * $F$54 / AEO!E155
- Emissions: consumption * emission_factor / 1000
  - Gasoline (R7): =E13 * $B62 / 1000
  - Diesel (R8): =E14 * $B57 / 1000
  - Ethanol (R9): =E15 * $B58 / 1000
  - Electricity (R10): =E16 * XLOOKUP(region, AEO CI)
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional

from bau.config import (
    LDV_SHARE, HDV_SHARE, KWH_PER_GALLON_GASOLINE,
    EMISSION_FACTORS_KG_CO2, NATIONAL_VMT_GROWTH_RATE,
    PROJECTION_YEARS, BASE_YEAR,
)


def calculate_initial_vmt_by_fuel(
    total_vmt: float,
    state: str,
    afdc_shares: pd.DataFrame,
) -> dict:
    """Allocate total VMT across fuel types using AFDC vehicle registration shares.

    Logic source: Excel 'Transport' tab R45-R51 (2024 column).
    Excel formula: =$B$44 * XLOOKUP($B$42, B$67:AZ$67, B68:AZ68)

    The AFDC shares represent the fraction of registered vehicles by fuel type
    in the city's state. This is used as a proxy for VMT allocation.
    Includes 7 fuel types: gasoline, diesel, ethanol, electric, plugin_hybrid,
    electric_hybrid, and biodiesel.

    Args:
        total_vmt: Total annual VMT for the city (from FHWA).
        state: State name for AFDC share lookup.
        afdc_shares: DataFrame with state-level vehicle registration shares.

    Returns:
        Dict mapping fuel type to allocated VMT.
    """
    # Filter to 2024 shares if year column present
    if "year" in afdc_shares.columns:
        state_row = afdc_shares[
            (afdc_shares["state"] == state) & (afdc_shares["year"] == 2024)
        ]
    else:
        state_row = afdc_shares[afdc_shares["state"] == state]

    if state_row.empty:
        raise ValueError(f"State '{state}' not found in AFDC vehicle shares data")

    state_data = state_row.iloc[0]

    # Map AFDC share columns to VMT fuel types
    # Source: Transport tab R68-R74
    vmt_by_fuel = {
        "conventional_gasoline": total_vmt * float(state_data.get("gasoline", 0)),
        "tdi_diesel": total_vmt * float(state_data.get("diesel", 0)),
        "flex_fuel": total_vmt * float(state_data.get("ethanol_flex_e85", state_data.get("ethanol/flex_e85", 0))),
        "electric": total_vmt * float(state_data.get("electric_ev", state_data.get("electric", 0))),
        "plugin_hybrid": total_vmt * float(state_data.get("plug-in_hybrid_electric_phev", state_data.get("plug_in_hybrid_electric_phev", 0))),
        "electric_hybrid": total_vmt * float(state_data.get("hybrid_electric_hev", state_data.get("hybrid_electric", 0))),
        "biodiesel": total_vmt * float(state_data.get("biodiesel", 0)),
    }

    return vmt_by_fuel


def project_vmt(
    total_vmt: float,
    afdc_shares: dict,
    afdc_deltas: dict,
    years: list,
) -> pd.DataFrame:
    """Project VMT forward using flat national growth + AFDC share evolution.

    Logic source: Baseline Module Documentation, Excel 'Transport' tab.

    Methodology:
    1. Total VMT grows at flat 0.6%/year (FHWA national trend):
       total_vmt(Y) = total_vmt(2024) * (1 + 0.006)^(Y - 2024)
    2. Year 1 (2024) fuel shares = AFDC 2024 registration shares
    3. Year 2+ fuel shares = 2024_share + growth_delta (FIXED, not cumulative)
       The delta is the 2024-2023 change, applied as a single step for all
       years beyond the base year.
    4. Shares are clamped >= 0 and re-normalized to sum to 1.0
    5. fuel_vmt(Y) = total_vmt(Y) * fuel_share(Y)

    Args:
        total_vmt: Total annual VMT for the city in the base year (from FHWA).
        afdc_shares: Dict mapping fuel type -> 2024 AFDC share (0-1).
        afdc_deltas: Dict mapping fuel type -> growth delta (2024 - 2023).
        years: List of projection years.

    Returns:
        DataFrame with year rows and fuel-type VMT columns.
    """
    fuel_types = list(afdc_shares.keys())
    all_years = list(range(BASE_YEAR, max(years) + 1))
    results = []

    for yr in all_years:
        years_from_base = yr - BASE_YEAR

        # Step 1: Total VMT grows at flat rate
        yr_total_vmt = total_vmt * (1 + NATIONAL_VMT_GROWTH_RATE) ** years_from_base

        # Step 2-3: Fuel shares
        if years_from_base == 0:
            # Base year: use 2024 shares directly
            shares = dict(afdc_shares)
        else:
            # Future years: 2024_share + delta (fixed, not cumulative)
            shares = {}
            for fuel in fuel_types:
                s = afdc_shares.get(fuel, 0) + afdc_deltas.get(fuel, 0)
                shares[fuel] = max(s, 0)  # Clamp >= 0

        # Step 4: Re-normalize shares to sum to 1.0
        total_share = sum(shares.values())
        if total_share > 0:
            shares = {k: v / total_share for k, v in shares.items()}

        # Step 5: Allocate VMT
        row = {"year": yr, "vmt_total": yr_total_vmt}
        for fuel in fuel_types:
            row[f"vmt_{fuel}"] = yr_total_vmt * shares.get(fuel, 0)
        results.append(row)

    df = pd.DataFrame(results)
    return df[df["year"].isin(years)].reset_index(drop=True)


def calculate_fuel_consumption(
    vmt_by_fuel: dict,
    year: int,
    aeo_mpg: pd.DataFrame,
    car_fraction: float,
    truck_fraction: float,
    aeo_freight: Optional[pd.DataFrame] = None,
) -> dict:
    """Convert VMT to fuel consumption (gallons or MWh) for each fuel type.

    Logic source: Excel 'Transport' tab R13-R16, R19-R38.

    The fuel consumption calculation splits each fuel type's VMT across three
    vehicle categories: Car, Pick Up Truck, and Freight Trucking.

    Excel formulas (using gasoline as example):
      Car gasoline (R20): =E45 * $F53 * AEO!E103 / AEO!E9
      Truck gasoline (R26): =E45 * $F53 * AEO!E104 / AEO!E24
      Freight gasoline (R33): =E45 * $F$54 / AEO!E155

    Where:
      - $F53 = LDV_share = 0.9 (Transport R53)
      - $F54 = HDV_share = 0.1 (Transport R54)
      - AEO!E103 = car sales share by region and year
      - AEO!E104 = truck sales share by region and year
      - AEO!E9 = car gasoline MPG (AEO R9)
      - AEO!E24 = truck gasoline MPG (AEO R24)
      - AEO!E155 = freight gasoline efficiency

    Total gasoline (R13) = car + truck + freight gasoline consumption

    Assumptions:
      - LDV/HDV split is fixed at 90/10 for all cities
      - Car/truck split within LDV uses AEO regional sales shares (dynamic by year)
      - Car and truck have separate MPG values from AEO table

    Args:
        vmt_by_fuel: Dict mapping fuel type -> VMT for this year.
        year: Target year for MPG lookups.
        aeo_mpg: AEO MPG DataFrame (with vehicle_class column).
        car_fraction: Car sales share for this region/year (from AEO LDV sales).
        truck_fraction: Truck sales share for this region/year (from AEO LDV sales).
        aeo_freight: Optional AEO freight efficiency DataFrame.

    Returns:
        Dict with fuel consumption: gasoline (gallons), diesel (gallons),
        ethanol (gallons), electricity (MWh).
    """
    yr_col = f"y{year}"

    def _get_mpg(vehicle_type: str, vehicle_class: str = "car") -> float:
        """Look up MPG by vehicle type and class (car or truck).

        Uses the vehicle_class column in aeo_mpg to disambiguate duplicate
        vehicle type names (e.g., 'Gasoline ICE Vehicles' for both car and truck).
        """
        if "vehicle_class" in aeo_mpg.columns:
            row = aeo_mpg[
                (aeo_mpg["vehicle_type"] == vehicle_type) &
                (aeo_mpg["vehicle_class"] == vehicle_class)
            ]
        else:
            row = aeo_mpg[aeo_mpg["vehicle_type"] == vehicle_type]
        if row.empty:
            raise ValueError(f"MPG not found for '{vehicle_type}' class='{vehicle_class}'")
        val = row[yr_col].iloc[0]
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return np.inf
        return float(val)

    def _get_freight_eff(category: str) -> float:
        """Look up freight efficiency by category.

        Uses the LAST match in the freight efficiency table, which corresponds
        to the "Average Fuel Efficiencies by Fuel Type" section (AEO R155-R160).
        Earlier rows contain weight-class-specific values (Light Medium, Medium,
        Heavy) which are not used in the Transport tab formulas.

        For categories that have zero efficiency in early years (Plug-in Diesel
        Hybrid, Electric Hybrid), falls back to the first non-zero year value.
        This matches Excel behavior where R39 uses AEO!D159 (2026) for 2024-2025
        and R40 uses AEO!C160 (2025) for 2024.
        """
        if aeo_freight is None:
            return np.inf
        row = aeo_freight[aeo_freight["category"] == category]
        if row.empty:
            return np.inf
        # Use last match = average across weight classes (AEO R155-R160)
        last_row = row.iloc[-1]
        val = last_row[yr_col]
        if val is not None and val != 0 and not (isinstance(val, float) and np.isnan(val)):
            return float(val)
        # Fallback: find first non-zero year value (Excel hardcodes future column refs)
        year_cols = sorted([c for c in last_row.index if c.startswith("y") and c[1:].isdigit()])
        for yc in year_cols:
            v = last_row[yc]
            if v is not None and v != 0 and not (isinstance(v, float) and np.isnan(v)):
                return float(v)
        return np.inf

    # ---- Gasoline consumption (gallons) ----
    # Car gasoline: Transport R20 = VMT_gas * LDV * car_frac / car_mpg
    # AEO!E9 = car gasoline MPG
    car_gas_mpg = _get_mpg("Gasoline ICE Vehicles", "car")
    car_gas = vmt_by_fuel.get("conventional_gasoline", 0) * LDV_SHARE * car_fraction / car_gas_mpg

    # Truck gasoline: Transport R26 = VMT_gas * LDV * truck_frac / truck_mpg
    # AEO!E24 = truck gasoline MPG (different from car MPG!)
    truck_gas_mpg = _get_mpg("Gasoline ICE Vehicles", "truck")
    truck_gas = vmt_by_fuel.get("conventional_gasoline", 0) * LDV_SHARE * truck_fraction / truck_gas_mpg

    # Freight gasoline: Transport R33 = VMT_gas * HDV / freight_gas_mpg
    freight_gas_mpg = _get_freight_eff("Conventional Gasoline")
    freight_gas = vmt_by_fuel.get("conventional_gasoline", 0) * HDV_SHARE / freight_gas_mpg

    total_gasoline = car_gas + truck_gas + freight_gas

    # ---- Diesel consumption (gallons) ----
    # Diesel only has truck (R27) and freight (R34), no car diesel row in Excel
    # Transport R27 (truck TDI): VMT_diesel * LDV * truck_frac / diesel_mpg
    # Note: Excel R27 = E46*$F53/AEO!E25 — no car_frac, uses full LDV share
    truck_diesel_mpg = _get_mpg("TDI Diesel ICE", "truck")
    truck_diesel = vmt_by_fuel.get("tdi_diesel", 0) * LDV_SHARE / truck_diesel_mpg

    # Transport R34 (freight TDI): VMT_diesel * HDV / freight_diesel_mpg
    freight_diesel_mpg = _get_freight_eff("TDI Diesel")
    freight_diesel = vmt_by_fuel.get("tdi_diesel", 0) * HDV_SHARE / freight_diesel_mpg

    total_diesel = truck_diesel + freight_diesel

    # ---- Ethanol consumption (gallons) ----
    # Car flex: Transport R21 = VMT_flex * LDV * car_frac / car_flex_mpg
    # NOTE: Excel R21 formula references E46 (diesel VMT) instead of E47 (flex VMT).
    # This appears to be a formula copy error in the Excel. Python uses the correct
    # flex-fuel VMT for this calculation. This causes a small divergence from Excel.
    car_flex_mpg = _get_mpg("Ethanol-Flex Fuel ICE", "car")
    car_ethanol = vmt_by_fuel.get("flex_fuel", 0) * LDV_SHARE * car_fraction / car_flex_mpg

    # Truck flex: Transport R28 = VMT_flex * LDV * truck_frac / truck_flex_mpg
    truck_flex_mpg = _get_mpg("Ethanol-Flex Fuel ICE", "truck")
    truck_ethanol = vmt_by_fuel.get("flex_fuel", 0) * LDV_SHARE * truck_fraction / truck_flex_mpg

    # Freight flex: Transport R35
    freight_flex_mpg = _get_freight_eff("Flex-Fuel")
    freight_ethanol = vmt_by_fuel.get("flex_fuel", 0) * HDV_SHARE / freight_flex_mpg

    total_ethanol = car_ethanol + truck_ethanol + freight_ethanol

    # ---- Electricity consumption (MWh) ----
    # Car EV: Transport R22 = VMT_ev * LDV * car_frac / car_ev_mpge * kWh_per_gal / 1000
    car_ev_mpge = _get_mpg("Average EV", "car")
    car_ev_mwh = (vmt_by_fuel.get("electric", 0) * LDV_SHARE * car_fraction
                  / car_ev_mpge * KWH_PER_GALLON_GASOLINE / 1000)

    # Truck EV: Transport R29 = VMT_ev * LDV * truck_frac / truck_ev_mpge * kWh_per_gal / 1000
    truck_ev_mpge = _get_mpg("Average EV", "truck")
    truck_ev_mwh = (vmt_by_fuel.get("electric", 0) * LDV_SHARE * truck_fraction
                    / truck_ev_mpge * KWH_PER_GALLON_GASOLINE / 1000)

    # Freight EV: Transport R36
    freight_ev_mpge = _get_freight_eff("Electric")
    freight_ev_mwh = (vmt_by_fuel.get("electric", 0) * HDV_SHARE
                      / freight_ev_mpge * KWH_PER_GALLON_GASOLINE / 1000)

    # Plugin hybrid
    # Car PHEV: Transport R23 = VMT_phev * LDV * car_frac / car_phev_mpg
    car_phev_mpg = _get_mpg("Average Plug In Hybrid", "car")
    car_phev = vmt_by_fuel.get("plugin_hybrid", 0) * LDV_SHARE * car_fraction / car_phev_mpg

    # Truck PHEV: Transport R30 = VMT_phev * LDV * truck_frac / truck_phev_mpg
    truck_phev_mpg = _get_mpg("Average Plug In Hybrid", "truck")
    truck_phev = vmt_by_fuel.get("plugin_hybrid", 0) * LDV_SHARE * truck_fraction / truck_phev_mpg

    # Freight plugin diesel hybrid
    freight_phev_mpg = _get_freight_eff("Plug-in Diesel Hybrid")
    freight_phev = vmt_by_fuel.get("plugin_hybrid", 0) * HDV_SHARE / freight_phev_mpg

    # Electric hybrid (gasoline equivalent)
    # Car hybrid: Transport R24 = VMT_hybrid * LDV * car_frac / car_hybrid_mpg
    car_ehybrid_mpg = _get_mpg("Electric-Gasoline Hybrid", "car")
    car_ehybrid = vmt_by_fuel.get("electric_hybrid", 0) * LDV_SHARE * car_fraction / car_ehybrid_mpg

    # Truck hybrid: Transport R31 = VMT_hybrid * LDV * truck_frac / truck_hybrid_mpg
    truck_ehybrid_mpg = _get_mpg("Electric-Gasoline Hybrid", "truck")
    truck_ehybrid = vmt_by_fuel.get("electric_hybrid", 0) * LDV_SHARE * truck_fraction / truck_ehybrid_mpg

    freight_ehybrid_mpg = _get_freight_eff("Electric Hybrid")
    freight_ehybrid = vmt_by_fuel.get("electric_hybrid", 0) * HDV_SHARE / freight_ehybrid_mpg

    # ---- Biodiesel consumption (gallons) ----
    # Biodiesel is a 7th fuel type using diesel MPG values.
    # Biodiesel gallons aggregate into the diesel emissions bucket (using diesel EF 10.21).
    # TODO: Excel R25 uses HDV_SHARE for car biodiesel, not LDV — replicating Excel behavior
    # Car biodiesel (R25): biodiesel_VMT * HDV_SHARE * car_frac / truck_diesel_MPG
    car_biodiesel = vmt_by_fuel.get("biodiesel", 0) * HDV_SHARE * car_fraction / truck_diesel_mpg

    # Truck biodiesel (R33): biodiesel_VMT * HDV_SHARE * truck_frac / truck_diesel_MPG
    truck_biodiesel = vmt_by_fuel.get("biodiesel", 0) * HDV_SHARE * truck_fraction / truck_diesel_mpg

    # Freight biodiesel (R41): biodiesel_VMT * HDV_SHARE / freight_diesel_MPG
    freight_biodiesel = vmt_by_fuel.get("biodiesel", 0) * HDV_SHARE / freight_diesel_mpg

    total_biodiesel = car_biodiesel + truck_biodiesel + freight_biodiesel

    # Allocation per Excel R13-R14:
    # Gasoline (R13) = car_gas + car_phev + car_hybrid + truck_gas + truck_phev
    #                 + truck_hybrid + freight_gas + freight_hybrid
    # Diesel (R14) = truck_diesel + freight_diesel + freight_phev + biodiesel
    # Note: freight_ehybrid goes to gasoline (R13 includes R38), NOT diesel
    # Note: freight_phev goes to diesel (R14 includes R37)
    # Note: biodiesel gallons use diesel emission factor (10.21 kg CO2/gal)
    total_gasoline += car_phev + truck_phev + car_ehybrid + truck_ehybrid + freight_ehybrid
    total_diesel += freight_phev + total_biodiesel

    total_electricity_mwh = car_ev_mwh + truck_ev_mwh + freight_ev_mwh

    return {
        "gasoline_gallons": total_gasoline,
        "diesel_gallons": total_diesel,
        "ethanol_gallons": total_ethanol,
        "electricity_mwh": total_electricity_mwh,
    }


def calculate_transport_emissions(
    fuel_consumption: dict,
    carbon_intensity: float,
) -> dict:
    """Convert fuel consumption to CO2 emissions.

    Logic source: Excel 'Transport' tab R7-R10.

    Formulas:
      Gasoline (R7): =consumption * 8.78 / 1000  (kg CO2/gal -> MT CO2)
      Diesel (R8): =consumption * 10.21 / 1000
      Ethanol (R9): =consumption * 5.75 / 1000
      Electricity (R10): =consumption_MWh * carbon_intensity(region)

    Note: Excel formula for electricity is:
      =E16 * XLOOKUP($B43, AEO!$A39:$A50, AEO!E39:E50)

    The Excel model correctly uses each city's AEO region via
    XLOOKUP($B43, AEO!$A39:$A50, ...) where $B43 = Findings!B5.
    The Python implementation replicates this using CITY_REGION_MAP.

    Args:
        fuel_consumption: Dict from calculate_fuel_consumption().
        carbon_intensity: Regional carbon intensity (MT CO2/MWh) for electricity.

    Returns:
        Dict with emissions by fuel type and total, all in MT CO2.
    """
    # Excel 'Transport' R62: Motor Gasoline = 8.78 kg CO2/gallon
    gasoline_mt = fuel_consumption["gasoline_gallons"] * EMISSION_FACTORS_KG_CO2["motor_gasoline"] / 1000

    # Excel 'Transport' R57: Diesel = 10.21 kg CO2/gallon
    diesel_mt = fuel_consumption["diesel_gallons"] * EMISSION_FACTORS_KG_CO2["diesel"] / 1000

    # Excel 'Transport' R58: Ethanol = 5.75 kg CO2/gallon
    ethanol_mt = fuel_consumption["ethanol_gallons"] * EMISSION_FACTORS_KG_CO2["ethanol_100"] / 1000

    # Excel 'Transport' R10: Electricity emissions = MWh * CI
    electricity_mt = fuel_consumption["electricity_mwh"] * carbon_intensity

    total = gasoline_mt + diesel_mt + ethanol_mt + electricity_mt

    return {
        "gasoline_mt_co2": gasoline_mt,
        "diesel_mt_co2": diesel_mt,
        "ethanol_mt_co2": ethanol_mt,
        "electricity_mt_co2": electricity_mt,
        "total_mt_co2": total,
    }


def calculate_transport_savings(
    emissions_base: dict,
    emissions_projected: dict,
) -> float:
    """Calculate total transport GHG savings between base and projected year.

    Logic source: Excel 'Findings' tab R12.
    Savings = baseline total - projected total.

    Args:
        emissions_base: Transport emissions dict for base year.
        emissions_projected: Transport emissions dict for target year.

    Returns:
        GHG savings in MT CO2 (positive = emissions reduction).
    """
    return emissions_base["total_mt_co2"] - emissions_projected["total_mt_co2"]
