"""Shared emissions calculation logic used across sectors.

Provides common utility functions for unit conversions and emissions
calculations that are shared between buildings and transport modules.

Source: Various tabs in the Excel model — consolidates repeated patterns.
"""
from typing import Dict


def mmbtu_to_mwh(mmbtu: float, conversion_factor: float = 0.3) -> float:
    """Convert energy from MMBtu to MWh.

    Source: Excel 'Electricity' tab R1, cell G1 (MWh/MMBtu = 0.3).
    Used in Electricity tab formula: R87 = R143 * $G$1

    Args:
        mmbtu: Energy in million BTU.
        conversion_factor: MWh per MMBtu (default 0.3).

    Returns:
        Energy in megawatt-hours.
    """
    return mmbtu * conversion_factor


def mwh_to_mt_co2(mwh: float, carbon_intensity: float) -> float:
    """Convert electricity consumption to CO2 emissions.

    Source: Excel 'Electricity' tab R32 formula:
        =C87 * XLOOKUP($B32, AEO!$A$39:$A$50, AEO!E$39:E$50)

    Args:
        mwh: Electricity consumption in MWh.
        carbon_intensity: Regional carbon intensity in MT CO2/MWh.

    Returns:
        CO2 emissions in metric tons.
    """
    return mwh * carbon_intensity


def ng_mmbtu_to_mt_co2e(
    mmbtu: float,
    emission_factor: float = 0.05306,
) -> float:
    """Convert natural gas consumption to CO2e emissions.

    Source: Excel 'NG' tab R2, cell G2 (=53.06/1000 = 0.05306 MT CO2/MMBtu).
    Used in NG tab formula: R33 = B90 * $G$2

    Args:
        mmbtu: Natural gas consumption in MMBtu.
        emission_factor: MT CO2 per MMBtu (default 0.05306).

    Returns:
        CO2e emissions in metric tons.
    """
    return mmbtu * emission_factor


def gallons_to_mt_co2(
    gallons: float,
    kg_co2_per_gallon: float,
) -> float:
    """Convert fuel consumption in gallons to CO2 emissions.

    Source: Excel 'Transport' tab R7-R9 formulas:
        Gasoline: =E13 * $B62 / 1000  (8.78 kg CO2/gal)
        Diesel:   =E14 * $B57 / 1000  (10.21 kg CO2/gal)
        Ethanol:  =E15 * $B58 / 1000  (5.75 kg CO2/gal)

    Args:
        gallons: Fuel consumed in gallons.
        kg_co2_per_gallon: Emission factor in kg CO2 per gallon.

    Returns:
        CO2 emissions in metric tons.
    """
    return gallons * kg_co2_per_gallon / 1000.0


def calculate_trend(
    base_value: float,
    projected_value: float,
    years_elapsed: int,
) -> Dict[str, float]:
    """Calculate total and annual delta trends between base and projected values.

    Source: Excel 'Findings' tab R10-R13.
    Excel formula: Total Delta = (projected - base) / base
                   Annual Delta = total_delta / years

    Args:
        base_value: Emissions in the base year.
        projected_value: Emissions in the target year.
        years_elapsed: Number of years between base and target.

    Returns:
        Dict with 'total_delta' (fractional change) and 'annual_delta'.
    """
    if base_value == 0:
        return {"total_delta": 0.0, "annual_delta": 0.0}

    total_delta = (projected_value - base_value) / base_value
    annual_delta = total_delta / years_elapsed if years_elapsed > 0 else 0.0

    return {
        "total_delta": total_delta,
        "annual_delta": annual_delta,
    }
