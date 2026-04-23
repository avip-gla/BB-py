"""BRESE module configuration and state definitions.

State-level policy parameters for building energy code adoption analysis.
Sources:
  - BRESE-cost-benefit-analysis.xlsx (SEEA summary, 11 state tabs)
  - DOE Building Energy Code Savings Calculator (.xlsm, upstream model)
See calculator_logic.py for full calculation chain documentation.
"""
from pathlib import Path
from typing import Dict

from bau.config import PROJECT_ROOT, INPUTS_DIR

# ============================================================
# Paths
# ============================================================
BRESE_DATA_DIR = INPUTS_DIR / "ecu"
BRESE_SOURCE_XLSX = Path(
    "/Users/apurkayastha/GLA/projects/brese/SEEA/BRESE-cost-benefit-analysis.xlsx"
)
BRESE_SEEA_DIR = Path("/Users/apurkayastha/GLA/projects/brese/SEEA")

# DOE Calculator scenarios (one per state, different baseline codes)
# Note: the two .xlsm files are reused for different states. The mapping below
# reflects the CURRENT state loaded in each file. Previous states verified:
#   SC (seea.xlsm), NC (seea (1).xlsm) — verified 2026-2040
#   Arkansas (seea.xlsm), Georgia (seea (1).xlsm) — verified 2026-2040
#   Florida (seea.xlsm), Alabama (seea (1).xlsm) — verified 2026-2040
#   Virginia (seea.xlsm), Louisiana (seea (1).xlsm) — verified 2026-2040
#   Tennessee (seea.xlsm), Kentucky (seea (1).xlsm) — verified 2026-2040
#   Mississippi (seea.xlsm) — verified 2026-2040
CALCULATOR_SCENARIOS = {
    "Mississippi": BRESE_SEEA_DIR / "Building-Energy-Code-Emissions-Calculator-seea.xlsm",
    "Kentucky": BRESE_SEEA_DIR / "Building-Energy-Code-Emissions-Calculator-seea (1).xlsm",
}

# ============================================================
# State tab names in the Excel workbook
# ============================================================
STATE_TABS = [
    "SC", "Georgia", "NC", "AL", "Florida",
    "VA", "LA", "KY", "TN", "Arkansas", "MS",
]

# ============================================================
# State metadata extracted from Excel headers
# ============================================================
STATE_INFO: Dict[str, dict] = {
    "SC": {
        "full_name": "South Carolina",
        "tab_name": "SC",
        "current_code": "2009 IECC & ASHRAE 90.1 2007",
        "proposed_code": "2024 IECC & 2025 ASHRAE",
        "energy_index_gain": {"ashrae": 0.32, "iecc": 0.40},
        "energy_savings_pct": {"ashrae": 0.09, "iecc": 0.06},
    },
    "Georgia": {
        "full_name": "Georgia",
        "tab_name": "Georgia",
        "current_code": "2015 IECC & ASHRAE 90.1 2013",
        "proposed_code": "2024 IECC & 2025 ASHRAE",
        "energy_index_gain": {"ashrae": 0.13, "iecc": 0.12},
        "energy_savings_pct": {"ashrae": 0.037, "iecc": 0.041},
    },
    "NC": {
        "full_name": "North Carolina",
        "tab_name": "NC",
        "current_code": "2015 IECC & ASHRAE 90.1 2013",
        "proposed_code": "2024 IECC & 2025 ASHRAE",
        "energy_index_gain": {"ashrae": 0.13, "iecc": 0.12},
        "energy_savings_pct": {"ashrae": 0.037, "iecc": 0.041},
    },
    "AL": {
        "full_name": "Alabama",
        "tab_name": "AL",
        "current_code": "2015 IECC & ASHRAE 90.1 2013",
        "proposed_code": "2024 IECC & 2025 ASHRAE",
        "energy_index_gain": {"ashrae": 0.13, "iecc": 0.12},
        "energy_savings_pct": {"ashrae": 0.037, "iecc": 0.041},
    },
    "Florida": {
        "full_name": "Florida",
        "tab_name": "Florida",
        "current_code": "2021 IECC & ASHRAE 90.1 2019",
        "proposed_code": "2024 IECC & 2025 ASHRAE",
        "energy_index_gain": {"ashrae": 0.10, "iecc": 0.03},
        "energy_savings_pct": {"ashrae": 0.0, "iecc": 0.029},
    },
    "VA": {
        "full_name": "Virginia",
        "tab_name": "VA",
        "current_code": "2021 IECC & ASHRAE 90.1 2019",
        "proposed_code": "2024 IECC & 2025 ASHRAE",
        "energy_index_gain": {"ashrae": 0.10, "iecc": 0.03},
        "energy_savings_pct": {"ashrae": 0.0, "iecc": 0.029},
    },
    "LA": {
        "full_name": "Louisiana",
        "tab_name": "LA",
        "current_code": "2021 IECC & ASHRAE 90.1 2019",
        "proposed_code": "2024 IECC & 2025 ASHRAE",
        "energy_index_gain": {"ashrae": 0.10, "iecc": 0.03},
        "energy_savings_pct": {"ashrae": 0.0, "iecc": 0.029},
    },
    "KY": {
        "full_name": "Kentucky",
        "tab_name": "KY",
        "current_code": "2012 IECC & ASHRAE 90.1 2010",
        "proposed_code": "2024 IECC & 2025 ASHRAE",
        "energy_index_gain": {"ashrae": 0.40, "iecc": 0.16},
        "energy_savings_pct": {"ashrae": 0.10, "iecc": 0.06},
    },
    "TN": {
        "full_name": "Tennessee",
        "tab_name": "TN",
        "current_code": "2021 IECC",
        "proposed_code": "2024 IECC & 2025 ASHRAE",
        "energy_index_gain": {"ashrae": 0.70, "iecc": 0.04},
        "energy_savings_pct": {"ashrae": 0.10, "iecc": 0.029},
        "notes": "No commercial savings",
    },
    "Arkansas": {
        "full_name": "Arkansas",
        "tab_name": "Arkansas",
        "current_code": "2009 IECC & ASHRAE 90.1 2007",
        "proposed_code": "2024 IECC & 2025 ASHRAE",
        "energy_index_gain": {"ashrae": 0.32, "iecc": 0.40},
        "energy_savings_pct": {"ashrae": 0.09, "iecc": 0.06},
    },
    "MS": {
        "full_name": "Mississippi",
        "tab_name": "MS",
        "current_code": "2006 IECC & ASHRAE 90.1 2004",
        "proposed_code": "2024 IECC & 2025 ASHRAE",
        "energy_index_gain": {"ashrae": 0.32, "iecc": 0.40},
        "energy_savings_pct": {"ashrae": 0.09, "iecc": 0.06},
        "notes": "Home rule state, assumed oldest code",
    },
}
