"""BPS (Building Performance Standards) module.

Calculates GHG emissions reductions from city-level building performance
policies such as Philadelphia's Building Energy Performance Program (BEPP).

This module is separate from iam/buildings.py which models BAU baseline
emissions. BPS models the *additional* savings from policy interventions
(e.g., retrocommissioning tune-ups) applied to commercial building stock
segmented by building area bins.

Shared data sources with iam/:
  - AEO regional carbon intensity (data/aeo/aeo_carbon_intensity.csv)
  - SLOPE commercial consumption baselines (data/inputs/electricity/, data/inputs/ng/)
  - Emission factors (NG_EMISSION_FACTOR, MWH_PER_MMBTU from iam.config)

BPS-specific data:
  - SLOPE building area thresholds per city (data/inputs/bps/<city>.csv)
  - Policy parameters (savings rate, bin definitions, stagger schedule)
"""
