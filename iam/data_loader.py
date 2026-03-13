"""Data loading functions for the IAM model.

Separates data loading from calculation logic. Loads:
- Fixed/national data (shared across all cities)
- Individual city data (from CSV)
- AEO tables (carbon intensity, MPG, freight efficiency)
- Electricity consumption and emissions data
- Natural gas consumption and emissions data
- Transportation VMT and FHWA data
- AFDC vehicle registration shares by state
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional

from iam.config import (
    INPUTS_DIR, AEO_DIR, CITIES_DIR, ELECTRICITY_DIR, NG_DIR,
    CITY_REGION_MAP, CITY_STATE_MAP, PROJECTION_YEARS,
    CITY_AEO_SALES_REGION_MAP,
)


def load_fixed_data(path: Optional[str] = None) -> dict:
    """Load national/fixed parameters shared across all cities.

    Source: Excel model various tabs — emission factors, conversion constants.
    Data file: data/inputs/fixed_data.csv

    Args:
        path: Optional path override. Defaults to data/inputs/fixed_data.csv.

    Returns:
        Dict with keys like 'ng_emission_factor_mt_co2_per_mmbtu', etc.
    """
    if path is None:
        path = INPUTS_DIR / "fixed_data.csv"
    df = pd.read_csv(path)
    return df.iloc[0].to_dict()


def load_emission_factors(path: Optional[str] = None) -> pd.DataFrame:
    """Load EPA emission factors for transportation fuels.

    Source: Excel 'Transport' tab R52-R63 (EPA 2025 Emissions Factor Hub).

    Args:
        path: Optional path override. Defaults to data/inputs/emission_factors.csv.

    Returns:
        DataFrame with columns: fuel_type, kg_co2_per_unit, unit.
    """
    if path is None:
        path = INPUTS_DIR / "emission_factors.csv"
    return pd.read_csv(path)


def load_city_data(city_name: str, data_dir: Optional[str] = None) -> dict:
    """Load city-specific parameters from its CSV file.

    Source: Compiled from Excel 'Buildings', 'Electricity', 'NG', 'Sense Check' tabs.
    Each city CSV contains: region, building emissions baselines, electricity/NG
    consumption in MWh and MMBtu, and inventory data.

    Args:
        city_name: City name (e.g., 'Atlanta', 'Boston').
        data_dir: Optional directory override. Defaults to data/inputs/cities/.

    Returns:
        Dict with city-specific parameters.
    """
    if data_dir is None:
        data_dir = CITIES_DIR
    else:
        data_dir = Path(data_dir)

    fname = city_name.lower().replace(" ", "_").replace(".", "") + ".csv"
    filepath = data_dir / fname
    df = pd.read_csv(filepath)
    return df.iloc[0].to_dict()


def load_aeo_carbon_intensity(path: Optional[str] = None) -> pd.DataFrame:
    """Load AEO regional carbon intensity projections (MT CO2/MWh).

    Source: Excel 'AEO' tab R39-R49.
    These are year-by-year carbon intensity forecasts by electricity market region,
    derived from AEO Table 54.15 and related tables.

    The carbon intensity for a region determines how much CO2 is emitted per MWh
    of electricity consumed. This is the key driver of electricity emissions trends.

    Args:
        path: Optional path override. Defaults to data/aeo/aeo_carbon_intensity.csv.

    Returns:
        DataFrame with 'region' column and year columns (y2024, y2025, ..., y2050).
    """
    if path is None:
        path = AEO_DIR / "aeo_carbon_intensity.csv"
    return pd.read_csv(path)


def load_aeo_mpg(path: Optional[str] = None) -> pd.DataFrame:
    """Load AEO miles-per-gallon projections by vehicle/fuel type.

    Source: Excel 'AEO' tab R5-R36.
    Includes stock average MPG for cars and light trucks, and new vehicle MPG
    by technology type (gasoline, EV, hybrid, flex-fuel, etc.).

    Used in transport emissions calculations to convert VMT to fuel consumption.

    Args:
        path: Optional path override. Defaults to data/aeo/aeo_mpg.csv.

    Returns:
        DataFrame with 'vehicle_type' column and year columns (y2024-y2050).
    """
    if path is None:
        path = AEO_DIR / "aeo_mpg.csv"
    return pd.read_csv(path)


def load_aeo_freight_efficiency(path: Optional[str] = None) -> pd.DataFrame:
    """Load AEO freight transportation fuel efficiency projections.

    Source: Excel 'AEO' tab R109-R160 (Table 49).
    Includes fuel efficiency (MPG) by weight class and fuel type for freight trucks.

    Args:
        path: Optional path override. Defaults to data/aeo/aeo_freight_efficiency.csv.

    Returns:
        DataFrame with 'category' column and year columns.
    """
    if path is None:
        path = AEO_DIR / "aeo_freight_efficiency.csv"
    return pd.read_csv(path)


def load_electricity_emissions(path: Optional[str] = None) -> pd.DataFrame:
    """Load pre-calculated electricity emissions by city and year.

    Source: Excel 'Electricity' tab R5-R29.
    These are the total electricity-related CO2 emissions for each city,
    calculated as: MWh_consumed * carbon_intensity(region, year).

    Args:
        path: Optional path override.

    Returns:
        DataFrame with columns: city, year, electricity_emissions_mt_co2.
    """
    if path is None:
        path = ELECTRICITY_DIR / "electricity_emissions.csv"
    return pd.read_csv(path)


def load_ng_emissions(path: Optional[str] = None) -> pd.DataFrame:
    """Load pre-calculated natural gas emissions by city and year.

    Source: Excel 'NG' tab R6-R30.
    Total NG emissions = residential + commercial NG emissions.
    Each calculated as: NG_consumption_MMBtu * 0.05306 MT_CO2/MMBtu.

    Args:
        path: Optional path override.

    Returns:
        DataFrame with columns: city, year, ng_emissions_mt_co2e.
    """
    if path is None:
        path = NG_DIR / "ng_emissions.csv"
    return pd.read_csv(path)


def load_ng_consumption(sector: str = "residential",
                        path: Optional[str] = None) -> pd.DataFrame:
    """Load natural gas consumption data (MMBtu) by city and year.

    Source: Excel 'NG' tab R90-R114 (residential), R117-R141 (commercial).
    Raw input data sourced from SLOPE (National Lab of the Rockies).

    Args:
        sector: 'residential' or 'commercial'.
        path: Optional path override.

    Returns:
        DataFrame with columns: city, year, ng_{sector}_mmbtu.
    """
    if path is None:
        path = NG_DIR / f"ng_{sector}_consumption.csv"
    return pd.read_csv(path)


def load_electricity_consumption_mmbtu(path: Optional[str] = None) -> pd.DataFrame:
    """Load electricity consumption in MMBtu by city and sector.

    Source: Excel 'Electricity' tab R143-R167 (residential), R170-R194 (commercial).
    Raw input data sourced from SLOPE.

    Note: MWh = MMBtu * 0.3 (MWh/MMBtu conversion factor from Electricity tab R1).

    Args:
        path: Not used; data loaded from city CSVs containing mmbtu fields.

    Returns:
        Dict mapping city -> {residential_mmbtu, commercial_mmbtu} for base year.
    """
    # This data is embedded in individual city CSVs
    result = {}
    for city in CITY_REGION_MAP:
        city_data = load_city_data(city)
        result[city] = {
            "residential_mmbtu": city_data.get("electricity_residential_mmbtu"),
            "commercial_mmbtu": city_data.get("electricity_commercial_mmbtu"),
        }
    return result


def load_fhwa_vmt(path: Optional[str] = None) -> pd.DataFrame:
    """Load FHWA Vehicle Miles Traveled data by city.

    Source: Excel 'FHWA' tab R9-R33.
    Federal Highway Administration data for 2024, scaled from urbanized area
    totals to city proper using population ratios.

    The Excel model looks up per-city VMT via XLOOKUP(B41, FHWA!A9:A33, ...).
    This CSV provides the same per-city VMT baselines for the Python implementation,
    ranging from ~0.8B to ~10B across the 25 cities.

    Args:
        path: Optional path override.

    Returns:
        DataFrame with columns: city, census_population, total_daily_vmt_thousands,
        city_proper_population, scalar, total_annual_vmt.
    """
    if path is None:
        path = INPUTS_DIR / "fhwa_vmt.csv"
    return pd.read_csv(path)


def load_afdc_vehicle_shares(path: Optional[str] = None, year: Optional[int] = None) -> pd.DataFrame:
    """Load AFDC vehicle registration shares by state.

    Source: Excel 'Transport' tab R68-R74 (2024), R76-R82 (2023).
    Light-Duty Vehicle Registration data from the Alternative Fuels Data Center.
    Shows the fraction of registered vehicles by fuel type for each state.

    Used to allocate total VMT among fuel types for the initial year (2024).
    The CSV includes both 2023 and 2024 rows (distinguished by 'year' column).

    Args:
        path: Optional path override.
        year: If provided, filter to this year only. If None, return all years.

    Returns:
        DataFrame with 'state', 'year' columns and fuel-type share columns.
    """
    if path is None:
        path = INPUTS_DIR / "afdc_vehicle_shares.csv"
    df = pd.read_csv(path)
    if year is not None and "year" in df.columns:
        df = df[df["year"] == year].reset_index(drop=True)
    return df


def load_afdc_growth_deltas(path: Optional[str] = None) -> pd.DataFrame:
    """Load AFDC vehicle share growth deltas by state (2024 - 2023).

    Source: Excel 'Transport' tab R85-R91.
    Pre-computed deltas: 2024_share - 2023_share for each fuel type.
    Used to project fuel shares beyond the base year: share(Y) = 2024_share + delta.

    Args:
        path: Optional path override.

    Returns:
        DataFrame with 'state' column and fuel-type delta columns.
    """
    if path is None:
        path = INPUTS_DIR / "afdc_growth_deltas.csv"
    return pd.read_csv(path)


def load_transport_emissions(path: Optional[str] = None) -> pd.DataFrame:
    """Load pre-calculated transport emissions by year and fuel type.

    Source: Excel 'Transport' tab R4-R10.
    Total and per-fuel-type CO2 emissions from transportation.

    Note: The Transport tab recalculates for whichever city is selected in
    the Findings tab. These pre-calculated values serve as validation references.

    Args:
        path: Optional path override.

    Returns:
        DataFrame with columns: year, total_emissions_mt_co2,
        gasoline/diesel/ethanol/electricity_emissions_mt_co2.
    """
    if path is None:
        path = INPUTS_DIR / "transport_emissions.csv"
    return pd.read_csv(path)


def load_transport_vmt(path: Optional[str] = None) -> pd.DataFrame:
    """Load VMT projections by fuel type.

    Source: Excel 'Transport' tab R44-R50.
    VMT grows/declines annually by the AEO growth rates (Transport tab R70-R86).

    Formula pattern: VMT(year) = VMT(year-1) * (1 + annual_growth_rate)

    Args:
        path: Optional path override.

    Returns:
        DataFrame with columns: year, vmt_conventional_gasoline, vmt_tdi_diesel, etc.
    """
    if path is None:
        path = INPUTS_DIR / "transport_vmt_by_fuel.csv"
    return pd.read_csv(path)


def load_buildings_emissions(path: Optional[str] = None) -> pd.DataFrame:
    """Load pre-calculated total building emissions by city and year.

    Source: Excel 'Buildings' tab R6-R30.
    Total = Residential + Commercial.
    Each sector = Electricity_emissions + NG_emissions.

    Formula chain:
      Buildings total = Electricity_emissions + NG_emissions
      Electricity_emissions = MWh * carbon_intensity(region, year)
      NG_emissions = NG_consumption_MMBtu * 0.05306

    Args:
        path: Optional path override.

    Returns:
        DataFrame with columns: city, year, total_emissions_mt_co2e.
    """
    if path is None:
        path = INPUTS_DIR / "buildings_total_emissions.csv"
    return pd.read_csv(path)


def get_carbon_intensity(region: str, year: int,
                         ci_df: Optional[pd.DataFrame] = None) -> float:
    """Look up carbon intensity for a region and year.

    Source: Excel 'AEO' tab R39-R49 via XLOOKUP in Electricity tab.
    Excel formula: =XLOOKUP($B32, AEO!$A$39:$A$50, AEO!E$39:E$50)

    The Excel model looks up per-city carbon intensity via
    XLOOKUP($B43, AEO!$A39:$A50, ...) where $B43 = Findings!B5 (the city's
    AEO region). The Python implementation replicates this using CITY_REGION_MAP.

    Args:
        region: AEO electricity market region code (e.g., 'SRSE', 'PJMW').
        year: Target year (2024-2050).
        ci_df: Optional pre-loaded carbon intensity DataFrame.

    Returns:
        Carbon intensity in MT CO2/MWh.
    """
    if ci_df is None:
        ci_df = load_aeo_carbon_intensity()

    row = ci_df[ci_df["region"] == region]
    if row.empty:
        raise ValueError(f"Region '{region}' not found in AEO carbon intensity data")

    col = f"y{year}"
    if col not in row.columns:
        raise ValueError(f"Year {year} not found in AEO carbon intensity data")

    return float(row[col].iloc[0])


def get_mpg(vehicle_type: str, year: int,
            mpg_df: Optional[pd.DataFrame] = None,
            vehicle_class: Optional[str] = None) -> float:
    """Look up MPG for a vehicle type and year.

    Source: Excel 'AEO' tab R5-R36.
    Excel formula references: AEO!E9 (Gasoline ICE Cars), AEO!E24 (Gasoline ICE Trucks).

    The AEO MPG table has duplicate vehicle_type names for car and truck rows
    (e.g., "Gasoline ICE Vehicles" appears for both cars and light trucks).
    Use the vehicle_class parameter to disambiguate.

    Args:
        vehicle_type: AEO vehicle type label (e.g., 'Gasoline ICE Vehicles').
        year: Target year.
        mpg_df: Optional pre-loaded MPG DataFrame.
        vehicle_class: 'car' or 'truck' to disambiguate duplicate vehicle_type names.
            If None, returns the first match (car by default).

    Returns:
        Miles per gallon (or MPGe for electric vehicles).
    """
    if mpg_df is None:
        mpg_df = load_aeo_mpg()

    if vehicle_class is not None and "vehicle_class" in mpg_df.columns:
        row = mpg_df[
            (mpg_df["vehicle_type"] == vehicle_type) &
            (mpg_df["vehicle_class"] == vehicle_class)
        ]
    else:
        row = mpg_df[mpg_df["vehicle_type"] == vehicle_type]

    if row.empty:
        raise ValueError(
            f"Vehicle type '{vehicle_type}' (class={vehicle_class}) not found in AEO MPG data"
        )

    col = f"y{year}"
    if col not in row.columns:
        raise ValueError(f"Year {year} not found in AEO MPG data")

    return float(row[col].iloc[0])


def load_aeo_ldv_sales_shares(path: Optional[str] = None) -> pd.DataFrame:
    """Load AEO Light-Duty Vehicle sales shares (car vs. truck fraction).

    Source: Excel 'AEO' tab R101-R107.
    Provides the fraction of LDV sales that are cars vs. pick-up trucks,
    by AEO census division (South Atlantic, Middle Atlantic) and year.

    Used in transport fuel consumption to split LDV VMT between car and truck
    categories, which have different MPG values.

    Args:
        path: Optional path override. Defaults to data/aeo/aeo_ldv_sales_shares.csv.

    Returns:
        DataFrame with columns: region, vehicle_type, y2024, y2025, ..., y2050.
    """
    if path is None:
        path = AEO_DIR / "aeo_ldv_sales_shares.csv"
    return pd.read_csv(path)


def get_ldv_sales_share(
    region: str,
    vehicle_type: str,
    year: int,
    sales_df: Optional[pd.DataFrame] = None,
) -> float:
    """Look up car or truck LDV sales share for a region and year.

    Source: Excel 'AEO' tab R103 (South Atlantic Cars), R104 (SA Trucks),
    R106 (Middle Atlantic Cars), R107 (MA Trucks).

    Args:
        region: AEO sales region ('South Atlantic' or 'Middle Atlantic').
        vehicle_type: 'Cars' or 'Pick Up Trucks'.
        year: Target year.
        sales_df: Optional pre-loaded sales shares DataFrame.

    Returns:
        Fraction (0-1) of LDV sales for this vehicle type in this region/year.
    """
    if sales_df is None:
        sales_df = load_aeo_ldv_sales_shares()

    row = sales_df[
        (sales_df["region"] == region) & (sales_df["vehicle_type"] == vehicle_type)
    ]
    if row.empty:
        raise ValueError(
            f"LDV sales share not found for region='{region}', type='{vehicle_type}'"
        )

    col = f"y{year}"
    if col not in row.columns:
        raise ValueError(f"Year {year} not found in LDV sales shares data")

    return float(row[col].iloc[0])


def load_all_data() -> dict:
    """Load all data needed for the model into a single dict.

    Convenience function that loads everything at once for use by City objects.

    Returns:
        Dict with keys: 'fixed', 'aeo_ci', 'aeo_mpg', 'aeo_freight',
        'fhwa_vmt', 'afdc_shares', 'buildings_emissions',
        'electricity_emissions', 'ng_emissions'.
    """
    return {
        "fixed": load_fixed_data(),
        "aeo_ci": load_aeo_carbon_intensity(),
        "aeo_mpg": load_aeo_mpg(),
        "aeo_freight": load_aeo_freight_efficiency(),
        "aeo_ldv_sales": load_aeo_ldv_sales_shares(),
        "fhwa_vmt": load_fhwa_vmt(),
        "afdc_shares": load_afdc_vehicle_shares(),
        "afdc_growth_deltas": load_afdc_growth_deltas(),
        "buildings_emissions": load_buildings_emissions(),
        "electricity_emissions": load_electricity_emissions(),
        "ng_emissions": load_ng_emissions(),
        "transport_emissions": load_transport_emissions(),
        "transport_vmt": load_transport_vmt(),
        "emission_factors": load_emission_factors(),
    }
