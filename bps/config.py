"""BPS module configuration and policy parameters.

Contains city-specific policy definitions and constants that are unique
to BPS calculations. Shared constants (emission factors, conversion factors)
are imported from bau.config.
"""
from pathlib import Path
from typing import Dict, List, Tuple

from bau.config import (
    PROJECT_ROOT,
    INPUTS_DIR,
    NG_EMISSION_FACTOR_MT_CO2_PER_MMBTU,
    MWH_PER_MMBTU,
)

# ============================================================
# BPS data paths
# ============================================================
BPS_DATA_DIR = INPUTS_DIR / "bps"

# ============================================================
# Re-export shared constants for convenience
# ============================================================
NG_EF = NG_EMISSION_FACTOR_MT_CO2_PER_MMBTU  # 0.05306 MT CO2/MMBtu
MWH_CONV = MWH_PER_MMBTU                      # 0.3 MWh/MMBtu

# ============================================================
# SLOPE area projection
# ============================================================
# Building area thresholds from SLOPE that are directly available (sq ft bins).
# Areas above 50k are projected using the ratio between the last two known bins
# (barea_gt_45k → barea_gt_50k). This ratio is applied repeatedly in 5k
# increments up to 200k.
SLOPE_PROJECTION_STEP_SQFT: int = 5_000
SLOPE_MAX_KNOWN_THRESHOLD: int = 50_000
SLOPE_PROJECTION_TARGET: int = 200_000

# ============================================================
# City-specific BPS policy definitions
# ============================================================
# Each city's BPS policy is defined by:
#   - policy_type: "retrocommissioning" (Philly-style staggered reductions)
#                  or "benchmarking" (KC-style year-over-year)
#   - region: AEO electricity market region for carbon intensity lookup
#   - savings_rate: fractional energy reduction
#   - bins: list of (label, lower_bound_sqft, upper_bound_sqft or None for open)
#
# Retrocommissioning-specific:
#   - implementation_years: {bin_label: year implementation starts}
#     Energy savings begin the year AFTER implementation.
#   - renewal_year: year the policy cycle renews
#
# Benchmarking-specific:
#   - ci_lag: if True, GHG uses previous year's carbon intensity (Excel behavior)
#   - projection_years includes a lead-in year (e.g., 2026) where consumption is
#     reduced but savings are measured starting the following year

CITY_BPS_POLICIES: Dict[str, dict] = {
    "Philadelphia": {
        "policy_type": "retrocommissioning",
        "region": "PJME",
        "savings_rate": 0.15,
        "bins": [
            ("200k+", 200_000, None),
            ("100-200k", 100_000, 200_000),
            ("70-100k", 70_000, 100_000),
            ("50-70k", 50_000, 70_000),
        ],
        "implementation_years": {
            "200k+": 2026,
            "100-200k": 2027,
            "70-100k": 2028,
            "50-70k": 2029,
        },
        "renewal_year": 2030,
        "projection_years": list(range(2026, 2036)),
    },
    "Kansas City": {
        "policy_type": "benchmarking",
        "region": "SPPC",
        "savings_rate": 0.03,
        "bins": [
            ("50k+", 50_000, None),
        ],
        "ci_lag": True,
        "projection_years": list(range(2026, 2037)),
    },
}
