"""EVE module configuration.

Sources:
  - Atlanta - Electrification Coalition Analysis.xlsx
  - City-specific inputs in data/inputs/eve/<city>.csv
"""
from pathlib import Path

from bau.config import INPUTS_DIR

# ============================================================
# Paths
# ============================================================
EVE_DATA_DIR = INPUTS_DIR / "eve"

# ============================================================
# Projection years for EVE module
# ============================================================
EVE_START_YEAR: int = 2026
EVE_END_YEAR: int = 2050
EVE_YEARS = list(range(EVE_START_YEAR, EVE_END_YEAR + 1))
