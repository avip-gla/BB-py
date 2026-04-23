"""EVE — EV Electrification policy module.

Estimates GHG savings from two interventions:
  1. Charger deployment: shifts VMT from gasoline to electric vehicles
     by increasing the effective electric VMT share.
  2. Fleet electrification: replaces city/airport fleet vehicles with
     EVs, saving a fixed MT CO2 per vehicle per year by class.

All city-specific inputs are loaded from data/inputs/eve/<city>.csv.
BAU transport data (VMT by fuel, emissions by fuel) is pulled from the
bau module so charger savings are always computed relative to the
baseline trajectory.
"""
