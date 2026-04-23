"""Buildings sector emissions calculation module.

Translates the Excel 'Buildings', 'Electricity', and 'NG' tabs into Python.
Buildings emissions = Electricity emissions + Natural Gas emissions,
calculated separately for Residential and Commercial sectors.

Formula chain (Excel source references):
  1. Electricity consumption (MMBtu) -> loaded from SLOPE data
     Source: Electricity tab R143-R167 (res), R170-R194 (com)
  2. MMBtu -> MWh: MWh = MMBtu * 0.3
     Source: Electricity tab R1 (MWh/MMBtu = 0.3), formula in R87
  3. MWh -> MT CO2: emissions = MWh * carbon_intensity(region, year)
     Source: Electricity tab R32 formula: =C87*XLOOKUP($B32,AEO!$A$39:$A$50,AEO!E$39:E$50)
  4. NG consumption (MMBtu) -> loaded from SLOPE data
     Source: NG tab R90-R114 (res), R117-R141 (com)
  5. MMBtu -> MT CO2e: emissions = MMBtu * 0.05306
     Source: NG tab R2 (MT CO2/MMBtu = 53.06/1000), formula in R33: =B90*$G$2

Buildings total (Buildings tab R6): =C33+C60 (residential + commercial)
Buildings residential (Buildings tab R33): =Electricity!C32+NG!B33
Buildings commercial (Buildings tab R60): =Electricity!C59+NG!B60
"""
import pandas as pd
import numpy as np
from typing import Optional

from bau.config import (
    NG_EMISSION_FACTOR_MT_CO2_PER_MMBTU,
    MWH_PER_MMBTU,
    PROJECTION_YEARS,
)


def calculate_electricity_emissions(
    electricity_mmbtu: float,
    carbon_intensity: float,
) -> float:
    """Calculate CO2 emissions from electricity consumption for one city/sector/year.

    Logic source: Excel 'Electricity' tab R32-R56 (residential), R59-R83 (commercial).

    Formula (plain English):
      1. Convert electricity consumption from MMBtu to MWh: MWh = MMBtu * 0.3
      2. Multiply MWh by regional carbon intensity: MT_CO2 = MWh * CI

    Excel formula: =C87 * XLOOKUP($B32, AEO!$A$39:$A$50, AEO!E$39:E$50)
    Where C87 = C143 * $G$1  (i.e., MMBtu * MWh_per_MMBtu)

    Args:
        electricity_mmbtu: Electricity consumption in MMBtu for this city/sector/year.
        carbon_intensity: Regional carbon intensity in MT CO2/MWh for this year.

    Returns:
        Electricity-related CO2 emissions in MT CO2.
    """
    # Excel: Electricity!R87 = R143 * $G$1 (MWh/MMBtu = 0.3)
    mwh = electricity_mmbtu * MWH_PER_MMBTU
    # Excel: Electricity!R32 = R87 * XLOOKUP(region, AEO CI)
    emissions_mt_co2 = mwh * carbon_intensity
    return emissions_mt_co2


def calculate_ng_emissions(ng_consumption_mmbtu: float) -> float:
    """Calculate CO2e emissions from natural gas consumption for one city/sector/year.

    Logic source: Excel 'NG' tab R33-R57 (residential), R60-R84 (commercial).

    Formula (plain English):
      Emissions (MT CO2e) = NG consumption (MMBtu) * emission factor (0.05306 MT CO2/MMBtu)

    Excel formula: =B90 * $G$2
    Where $G$2 = 53.06/1000 = 0.05306 MT CO2/MMBtu

    Assumptions:
      - Emission factor is constant across all years (no change in NG composition).
      - 53.06 kg CO2/MMBtu is the EPA standard for natural gas stationary combustion.

    Args:
        ng_consumption_mmbtu: Natural gas consumption in MMBtu for this city/sector/year.

    Returns:
        NG-related CO2e emissions in MT CO2e.
    """
    return ng_consumption_mmbtu * NG_EMISSION_FACTOR_MT_CO2_PER_MMBTU


def calculate_residential_savings(
    city_data: dict,
    fixed_data: dict,
    carbon_intensity_series: dict,
    ng_consumption_series: dict,
    elec_consumption_series: dict,
    year: int,
    base_year: int = 2027,
) -> float:
    """Calculate GHG savings from residential buildings for a given city and year.

    Logic source: Excel 'Buildings' tab R33-R57.
    Savings = baseline emissions (base_year) - projected emissions (target year).

    The projected emissions decline because:
      - Carbon intensity of electricity grid decreases over time (AEO projections)
      - NG consumption may change based on SLOPE projections

    Formula: Buildings!R33 = Electricity!R32 + NG!R33
    Where:
      Electricity!R32 = MWh(year) * CI(region, year)
      NG!R33 = NG_MMBtu(year) * 0.05306

    Args:
        city_data: Dict with city-specific data including 'region'.
        fixed_data: Dict with national parameters.
        carbon_intensity_series: Dict mapping year -> carbon intensity for this city's region.
        ng_consumption_series: Dict mapping year -> residential NG consumption MMBtu.
        elec_consumption_series: Dict mapping year -> residential electricity consumption MMBtu.
        year: Target future year for projection.
        base_year: Baseline year for comparison (default 2027, first projection year).

    Returns:
        GHG savings in MT CO2e (positive = emissions reduction).
    """
    # Calculate baseline emissions
    base_elec = calculate_electricity_emissions(
        elec_consumption_series[base_year],
        carbon_intensity_series[base_year],
    )
    base_ng = calculate_ng_emissions(ng_consumption_series[base_year])
    baseline = base_elec + base_ng

    # Calculate projected emissions
    proj_elec = calculate_electricity_emissions(
        elec_consumption_series[year],
        carbon_intensity_series[year],
    )
    proj_ng = calculate_ng_emissions(ng_consumption_series[year])
    projected = proj_elec + proj_ng

    return baseline - projected


def calculate_commercial_savings(
    city_data: dict,
    fixed_data: dict,
    carbon_intensity_series: dict,
    ng_consumption_series: dict,
    elec_consumption_series: dict,
    year: int,
    base_year: int = 2027,
) -> float:
    """Calculate GHG savings from commercial buildings for a given city and year.

    Logic source: Excel 'Buildings' tab R60-R84.
    Same formula structure as residential but uses commercial sector data.

    Formula: Buildings!R60 = Electricity!R59 + NG!R60

    Args:
        city_data: Dict with city-specific data including 'region'.
        fixed_data: Dict with national parameters.
        carbon_intensity_series: Dict mapping year -> carbon intensity.
        ng_consumption_series: Dict mapping year -> commercial NG consumption MMBtu.
        elec_consumption_series: Dict mapping year -> commercial electricity consumption MMBtu.
        year: Target future year.
        base_year: Baseline year (default 2027).

    Returns:
        GHG savings in MT CO2e (positive = emissions reduction).
    """
    base_elec = calculate_electricity_emissions(
        elec_consumption_series[base_year],
        carbon_intensity_series[base_year],
    )
    base_ng = calculate_ng_emissions(ng_consumption_series[base_year])
    baseline = base_elec + base_ng

    proj_elec = calculate_electricity_emissions(
        elec_consumption_series[year],
        carbon_intensity_series[year],
    )
    proj_ng = calculate_ng_emissions(ng_consumption_series[year])
    projected = proj_elec + proj_ng

    return baseline - projected


def calculate_total_buildings_emissions(
    elec_res_mmbtu: float,
    elec_com_mmbtu: float,
    ng_res_mmbtu: float,
    ng_com_mmbtu: float,
    carbon_intensity: float,
) -> dict:
    """Calculate total building emissions for a city in a given year.

    Logic source: Excel 'Buildings' tab R6: =C33+C60

    This is the absolute emissions calculation (not savings).
    Used to produce the buildings emissions time series.

    Args:
        elec_res_mmbtu: Residential electricity consumption (MMBtu).
        elec_com_mmbtu: Commercial electricity consumption (MMBtu).
        ng_res_mmbtu: Residential NG consumption (MMBtu).
        ng_com_mmbtu: Commercial NG consumption (MMBtu).
        carbon_intensity: Regional carbon intensity (MT CO2/MWh).

    Returns:
        Dict with 'residential', 'commercial', 'total' emissions in MT CO2e.
    """
    res_elec = calculate_electricity_emissions(elec_res_mmbtu, carbon_intensity)
    res_ng = calculate_ng_emissions(ng_res_mmbtu)
    residential = res_elec + res_ng

    com_elec = calculate_electricity_emissions(elec_com_mmbtu, carbon_intensity)
    com_ng = calculate_ng_emissions(ng_com_mmbtu)
    commercial = com_elec + com_ng

    return {
        "residential": residential,
        "commercial": commercial,
        "total": residential + commercial,
        "residential_electricity": res_elec,
        "residential_ng": res_ng,
        "commercial_electricity": com_elec,
        "commercial_ng": com_ng,
    }
