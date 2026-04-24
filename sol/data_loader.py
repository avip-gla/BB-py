"""SOL data loader.

Loads city solar inputs from data/inputs/sol/<city>.csv and
AEO carbon intensity from data/aeo/aeo_carbon_intensity.csv.

City CSV format (parameter, value columns):
    base_kwh_5kw         Annual AC output of a 5 kW PVWatts system (kWh/yr)
    elec_rate_2026       Base residential electricity rate in 2026 ($/kWh)
    elec_rate_escalation Annual nominal rate escalation (e.g. 0.030 = 3%/yr)
    aeo_region           AEO carbon intensity region (e.g. PJMW, PJMD, SRSE)
    degradation_rate     Optional override; defaults to config.DEGRADATION_RATE

Data sources:
    Solar production     NREL PVWatts v8 (pvwatts.nrel.gov), 5 kW baseline,
                         south-facing, 20° tilt, 14% system losses.
    Electricity rates    EIA Electric Power Monthly (state/utility-specific).
                         Preferred over AEO Table 3 (national average) because
                         state and utility rates can deviate by ±20%.
    Carbon intensity     AEO 2025 Table 54 (same as BAU model).
"""
import os
from typing import Dict

import pandas as pd

from sol.config import SOL_INPUTS_DIR, AEO_CARBON_INTENSITY_PATH, DEGRADATION_RATE


def load_sol_inputs(city: str) -> Dict:
    """Load solar input parameters for a city.

    Args:
        city: City name (lowercase, underscores), e.g. 'akron', 'hampton'.

    Returns:
        Dict of parameter → value (numeric where applicable).

    Raises:
        FileNotFoundError: If no CSV exists for the city.
    """
    path = os.path.join(SOL_INPUTS_DIR, f"{city}.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Solar inputs not found for '{city}'. "
            f"Expected: {path}\n"
            f"Create a CSV with columns: parameter, value, notes."
        )
    df = pd.read_csv(path)
    inputs = dict(zip(df["parameter"], df["value"]))

    # Coerce numeric values
    numeric_keys = ["base_kwh_5kw", "elec_rate_2026", "elec_rate_escalation"]
    for k in numeric_keys:
        if k in inputs:
            inputs[k] = float(inputs[k])

    # Apply default degradation rate if not specified
    inputs.setdefault("degradation_rate", DEGRADATION_RATE)
    inputs["degradation_rate"] = float(inputs["degradation_rate"])

    return inputs


def load_carbon_intensity(region: str) -> Dict[int, float]:
    """Load AEO carbon intensity series for a given region.

    Args:
        region: AEO region code, e.g. 'PJMW', 'PJMD', 'SRSE'.

    Returns:
        Dict of year → carbon intensity (MT CO2/MWh).

    Raises:
        KeyError: If region is not found in the carbon intensity file.
    """
    df = pd.read_csv(AEO_CARBON_INTENSITY_PATH)
    df = df.set_index("region")

    if region not in df.index:
        available = ", ".join(df.index.tolist())
        raise KeyError(
            f"Region '{region}' not found. Available: {available}"
        )

    row = df.loc[region]
    # Columns are named y2024, y2025, ... y2050
    return {int(col[1:]): float(val) for col, val in row.items()}
