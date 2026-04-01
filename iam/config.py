"""Global constants and configuration for the IAM model.

All hardcoded values from the Excel model are centralized here.
Source references are noted for each constant.
"""
from pathlib import Path
from typing import List

# ============================================================
# Project paths
# ============================================================
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INPUTS_DIR = DATA_DIR / "inputs"
CITIES_DIR = INPUTS_DIR / "cities"
ELECTRICITY_DIR = INPUTS_DIR / "electricity"
NG_DIR = INPUTS_DIR / "ng"
AEO_DIR = DATA_DIR / "aeo"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# ============================================================
# Projection years
# ============================================================
PROJECTION_YEARS: List[int] = list(range(2026, 2051))
BASE_YEAR: int = 2024

# ============================================================
# Natural Gas emission factors
# Source: Excel 'Buildings' tab R3 (kg CO2/MMBtu = 53.06)
# Source: Excel 'NG' tab R2 (MT CO2/MMBtu = 53.06/1000 = 0.05306)
# ============================================================
NG_EMISSION_FACTOR_KG_CO2_PER_MMBTU: float = 53.06
NG_EMISSION_FACTOR_MT_CO2_PER_MMBTU: float = 0.05306

# ============================================================
# Electricity unit conversion
# Source: Excel 'Electricity' tab R1 (MWh/MMBtu = 0.3)
# ============================================================
MWH_PER_MMBTU: float = 0.3

# ============================================================
# Transportation constants
# Source: Excel 'Transport' tab
# ============================================================
# Vehicle type shares (R53-R54)
LDV_SHARE: float = 0.9   # Light-Duty Vehicle share of VMT
HDV_SHARE: float = 0.1   # Heavy-Duty Vehicle share of VMT

# Energy content (R57)
KWH_PER_GALLON_GASOLINE: float = 33.7

# MMBtu per gallon conversion factors (Findings tab R54-R57)
GASOLINE_MMBTU_PER_GALLON: float = 0.120214
DIESEL_MMBTU_PER_GALLON: float = 0.137381
ETHANOL_MMBTU_PER_GALLON: float = 0.08043
ELECTRICITY_MMBTU_PER_MWH: float = 3.412

# ============================================================
# EPA Emission Factors (kg CO2 per unit)
# Source: Excel 'Transport' tab R52-R63
# Source: EPA 2025 Emissions Factor Hub
# ============================================================
EMISSION_FACTORS_KG_CO2: dict = {
    "aviation_gasoline": 8.31,       # per gallon
    "biodiesel_100": 9.45,           # per gallon
    "cng": 0.05444,                  # per scf
    "diesel": 10.21,                 # per gallon
    "ethanol_100": 5.75,             # per gallon
    "jet_fuel": 9.75,               # per gallon
    "lng": 4.5,                      # per gallon
    "lpg": 5.68,                     # per gallon
    "motor_gasoline": 8.78,          # per gallon
    "residual_fuel_oil": 11.27,      # per gallon
}

# ============================================================
# National VMT growth rate (flat annual rate)
# Source: FHWA national VMT trend, Baseline Module Documentation
# Used to project total VMT forward from the base year.
# ============================================================
NATIONAL_VMT_GROWTH_RATE: float = 0.006  # 0.6% per year

# ============================================================
# VMT annual growth rates by technology type (DEPRECATED)
# Source: Excel 'Transport' tab R70-R86 (AEO 2025 Table 41)
# Average annual change 2024-2050
# Retained for backward compatibility with versioned modules.
# Current transport module uses flat NATIONAL_VMT_GROWTH_RATE + AFDC shares.
# ============================================================
VMT_GROWTH_RATES_AEO_TABLE41: dict = {
    "conventional_gasoline": -0.0326834237020539,
    "tdi_diesel": -0.01919978730308591,
    "ethanol_flex_fuel": -0.07232033885114875,
    "electric_100mi": 0.04273140391373276,
    "electric_200mi": 0.1802779176703697,
    "electric_300mi": 0.1511194448887787,
    "plugin_hybrid_20": 0.07336435372534322,
    "plugin_hybrid_50": 0.1453399405705382,
    "electric_gasoline_hybrid": 0.05032024312070926,
    "natural_gas_ice": -0.08074706678822707,
    "natural_gas_bifuel": -0.06163777509733337,
    "propane_ice": -0.06370986666023104,
    "propane_bifuel": -0.06326627020310216,
    "fuel_cell_hydrogen": -0.05573080622906224,
}

# Backward compatibility alias for versioned modules
VMT_GROWTH_RATES: dict = VMT_GROWTH_RATES_AEO_TABLE41

# ============================================================
# City-to-region mapping
# Source: Excel 'Buildings' tab R33-R57, 'Electricity' tab R32-R56
# Regions correspond to AEO electricity market modules
# Maps each city to its AEO electricity market region. Drives per-city carbon
# intensity lookups in Transport R10 and Electricity emissions.
# The Excel model does this via Findings!B5 -> Transport B43.
# ============================================================
CITY_REGION_MAP: dict = {
    "Akron": "PJMW",
    "Atlanta": "SRSE",
    "Birmingham": "SRSE",
    "Buffalo": "NYUP",
    "Charlotte": "SRCA",
    "Chattanooga": "SRCE",
    "Cincinnati": "PJMW",
    "Cleveland": "PJMW",
    "Columbus": "PJMW",
    "Dayton": "PJMW",
    "Hampton": "PJMD",
    "Jackson": "MISS",
    "Kansas City": "SPPC",
    "Lansing": "MISE",
    "Memphis": "SRCE",
    "Montgomery": "SRSE",
    "Nashville": "SRCE",
    "Newport News": "SRCA",
    "Oakland": "CANO",
    "Philadelphia": "PJME",
    "Pittsburgh": "PJMW",
    "Raleigh": "SRCA",
    "Rochester": "NYUP",
    "Savannah": "SRSE",
    "St. Louis": "MISC",
}

# City-to-state mapping (for AFDC vehicle share lookups)
# Source: Excel 'Findings' tab R4 (State), 'Transport' tab R42
# Maps each city to its state for AFDC vehicle share lookups in Transport R45-R50.
# The Excel model does this via Findings!B4 -> Transport B42.
CITY_STATE_MAP: dict = {
    "Akron": "Ohio",
    "Atlanta": "Georgia",
    "Birmingham": "Alabama",
    "Buffalo": "New York",
    "Charlotte": "North Carolina",
    "Chattanooga": "Tennessee",
    "Cincinnati": "Ohio",
    "Cleveland": "Ohio",
    "Columbus": "Ohio",
    "Dayton": "Ohio",
    "Hampton": "Virginia",
    "Jackson": "Mississippi",
    "Kansas City": "Missouri",
    "Lansing": "Michigan",
    "Memphis": "Tennessee",
    "Montgomery": "Alabama",
    "Nashville": "Tennessee",
    "Newport News": "Virginia",
    "Oakland": "California",
    "Philadelphia": "Pennsylvania",
    "Pittsburgh": "Pennsylvania",
    "Raleigh": "North Carolina",
    "Rochester": "New York",
    "Savannah": "Georgia",
    "St. Louis": "Missouri",
}

# City-to-AEO LDV sales region mapping
# Source: Excel 'AEO' tab R101-R107.
# The AEO provides car/truck LDV sales shares by census division.
# Cities are mapped to either "South Atlantic" or "Middle Atlantic" based on
# their geographic location. Used in transport fuel consumption to determine
# the car vs. truck fraction within LDV VMT.
# NOTE: Excel Transport tab hardcodes AEO R103/R104 (South Atlantic) for car/truck
# LDV sales fractions for ALL cities. The formula references are:
#   R20: =E48*$F57*AEO!E103/AEO!E9   (Cars, South Atlantic)
#   R27: =E48*$F57*AEO!E104/AEO!E24   (Trucks, South Atlantic)
# Python intentionally uses region-appropriate AEO sales data instead.
# This produces ~0.1-0.15% differences vs Excel for non-South-Atlantic cities.
# TODO: Revisit — may switch to match Excel hardcoding if needed.
CITY_AEO_SALES_REGION_MAP: dict = {
    "Akron": "Middle Atlantic",
    "Atlanta": "South Atlantic",
    "Birmingham": "South Atlantic",
    "Buffalo": "Middle Atlantic",
    "Charlotte": "South Atlantic",
    "Chattanooga": "South Atlantic",
    "Cincinnati": "Middle Atlantic",
    "Cleveland": "Middle Atlantic",
    "Columbus": "Middle Atlantic",
    "Dayton": "Middle Atlantic",
    "Hampton": "South Atlantic",
    "Jackson": "South Atlantic",
    "Kansas City": "Middle Atlantic",
    "Lansing": "Middle Atlantic",
    "Memphis": "South Atlantic",
    "Montgomery": "South Atlantic",
    "Nashville": "South Atlantic",
    "Newport News": "South Atlantic",
    "Oakland": "Middle Atlantic",
    "Philadelphia": "Middle Atlantic",
    "Pittsburgh": "Middle Atlantic",
    "Raleigh": "South Atlantic",
    "Rochester": "Middle Atlantic",
    "Savannah": "South Atlantic",
    "St. Louis": "Middle Atlantic",
}

# All 25 city names
CITIES: List[str] = sorted(CITY_REGION_MAP.keys())
