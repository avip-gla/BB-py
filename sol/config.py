"""SOL module configuration.

Solar policy module constants and city group definitions.
"""
import os

# --- Paths ---
SOL_INPUTS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "data", "inputs", "sol"
)
AEO_CARBON_INTENSITY_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "aeo", "aeo_carbon_intensity.csv"
)

# --- Default parameters ---
DEGRADATION_RATE = 0.005          # 0.5%/yr panel efficiency loss (PVWatts standard)
BASELINE_SYSTEM_KW = 5.0          # PVWatts baseline system size (kW)
DEFAULT_START_YEAR = 2026
DEFAULT_END_YEAR = 2035            # 10-year horizon matching the Excel analysis

# --- City groups ---
# Each group defines a cohort of cities sharing a program (same scale factor and
# total HH count). The calculator averages per-5kW-system metrics across all
# cities in the group, then scales by scale_factor × num_households.
#
# To model a standalone city (not averaged with others), define a single-city group.

CITY_GROUPS = {
    "oh": {
        "cities": ["akron", "dayton", "columbus", "cincinnati", "cleveland", "pittsburgh"],
        "num_households": 5500,
        "system_kw": 16.3,         # 90 MW total ÷ 5500 HH = 16.3 kW/home
        "label": "OH + Pittsburgh PA",
    },
    "va": {
        "cities": ["hampton"],
        "num_households": 52,
        "system_kw": 5.0,          # Standard 5 kW residential
        "label": "Hampton and Newport News, VA",
    },
}

# Map city name → group name (auto-derived from CITY_GROUPS)
CITY_TO_GROUP = {
    city: group
    for group, cfg in CITY_GROUPS.items()
    for city in cfg["cities"]
}
