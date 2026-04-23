# Transport Module: Excel to Python Translation

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Original Excel Model](#2-original-excel-model)
3. [Python Implementation](#3-python-implementation)
4. [Python Module Reference](#4-python-module-reference)
5. [Data Files Reference](#5-data-files-reference)
6. [Excel Formula to Python Mapping](#6-excel-formula-to-python-mapping)
7. [Validation Results](#7-validation-results)

---

## 1. Executive Summary

baseline-builder-py is a Python-based Integrated Assessment Model that calculates greenhouse gas (GHG) emissions savings for 25 US cities across projection years 2027 through 2050. The model covers two sectors: **Buildings** (residential and commercial) and **Transportation**. It was refactored from an Excel-based model into a Python/conda application to improve transparency, reproducibility, and city-level accuracy.

The Python implementation improves on the Excel model in several ways:

- **City-specific data pipeline:** Each city uses its own FHWA VMT, state-level AFDC fuel shares, and regional carbon intensity — the Excel model used Atlanta as a reference city for all 25 cities.
- **Flat VMT growth with AFDC share evolution:** Total VMT grows at a flat 0.6%/year (FHWA national trend). Fuel shares evolve using AFDC 2024 shares plus a fixed growth delta (2024 − 2023), replacing per-technology AEO Table 41 compound growth rates.
- **Biodiesel as 7th fuel type:** Biodiesel is included as a distinct fuel type throughout the pipeline (VMT allocation, fuel consumption, emissions). Biodiesel gallons are aggregated into the diesel emissions bucket using the diesel emission factor (10.21 kg CO2/gal).
- **Separate car/truck MPG:** Cars use AEO Row 9 MPG values and trucks use AEO Row 24, rather than a single MPG for both.
- **Dynamic car/truck fractions:** Light-duty vehicle car/truck fractions come from AEO LDV sales shares by census division and year, replacing hardcoded 0.42/0.58 values.
- **Corrected freight efficiency:** Uses the average across weight classes (AEO R155-R160) rather than a specific weight class. Freight efficiency for Plug-in Diesel Hybrid and Electric Hybrid now has non-zero values for 2024-2025 (see Change Log below).
- **SPPC carbon intensity:** Available directly in the dataset, eliminating any fallback.
- **AFDC shares normalized:** The 7 fuel types used in the model (gasoline, diesel, ethanol, electric, PHEV, hybrid, biodiesel) are normalized to sum to 1.0, excluding minor fuel types (CNG, propane, hydrogen, methanol) that collectively represent <0.006% of registrations.

---

## 2. Original Excel Model

### Overview

The original Transport tab in the Excel model calculates emissions for whichever city is selected in the Findings tab. The Transport tab uses dynamic cell references (B41=city from Findings!B3, B42=state from Findings!B4, B43=region from Findings!B5) so that when the Findings tab is switched to a different city, all transport lookups (VMT, AFDC shares, carbon intensity) update accordingly.

### Formula Chain

The Excel calculation proceeds through the following steps:

**Step 1: Total VMT (Row 44)**

The model looks up the selected city's total vehicle miles traveled from FHWA data:

- `R44 = XLOOKUP(B41, FHWA!A9:A33, FHWA!AB9:AB33) * 1000`
- Where B41 = Findings!B3 (the city name)

The raw FHWA value is in thousands, so it is multiplied by 1,000 to obtain actual annual VMT. For Atlanta, this yields 5,598,764,246.

**Step 2: VMT by Fuel Type (Rows 45-50)**

Total VMT is split across fuel types using the city's state AFDC vehicle registration shares:

- `R45-R50 = $B$44 * XLOOKUP($B$42, B$67:AZ$67, B68:AZ68)`
- Where $B$42 = Findings!B4 (the city's state)

This produces VMT for seven fuel types: gasoline, diesel, flex-fuel (ethanol), electric, plug-in hybrid, hybrid, and biodiesel.

**Step 3: VMT Growth Projections**

Total VMT grows at a flat 0.6%/year national growth rate (FHWA):

- `total_vmt(Y) = total_vmt(2024) * (1.006)^(Y − 2024)`

Fuel type shares evolve using AFDC growth deltas (Transport R88-R94):

- Year 1 (2024): shares = AFDC 2024 registration shares (R72-R78)
- Year 2+ (2025-2050): shares = 2024_share + growth_delta (fixed, not cumulative)
- Shares are clamped ≥ 0 and re-normalized to sum to 1.0
- `fuel_vmt(Y) = total_vmt(Y) * fuel_share(Y)`

The growth delta is the difference between 2024 and 2023 AFDC shares (R88-R94), applied as a single step for all future years.

**Step 4: Fuel Consumption (Rows 13-16)**

VMT is converted to fuel consumption using MPG values and vehicle category fractions. The four fuel categories are:

- **Gasoline (R13):** Sum of car gasoline (R20) + car PHEV (R23) + car hybrid (R24) + truck gasoline (R26) + truck PHEV (R30) + truck hybrid (R31) + freight gasoline (R33) + freight hybrid (R38)
- **Diesel (R14):** Truck diesel (R27) + freight diesel (R34) + freight PHEV (R37)
- **Ethanol (R15):** Car flex-fuel (R21) + truck flex-fuel (R28) + freight flex-fuel (R35)
- **Electricity (R16):** Car EV (R22) + truck EV (R29) + freight EV (R36)

**Step 5: Emissions (Rows 7-10)**

Fuel consumption is multiplied by EPA emission factors and divided by 1,000 to convert from kilograms to metric tons of CO2:

- Gasoline emissions: `fuel_gallons * 8.78 / 1000`
- Diesel emissions: `fuel_gallons * 10.21 / 1000`
- Ethanol emissions: `fuel_gallons * 5.75 / 1000`
- Electricity emissions: `electricity_MWh * carbon_intensity(region, year)`

**Step 6: Total Emissions (Row 4)**

- `R4 = sum(R7:R10)`

### Key Characteristics

- The Transport tab is a single-city worksheet that recalculates for whichever city is selected in the Findings tab.
- Per-city VMT, state-level fuel mix, and regional carbon intensity are all handled via dynamic cell references (B41, B42, B43).
- Car/truck MPG uses a single value (not split by vehicle class).
- Car/truck LDV fractions are fixed at 0.42/0.58 rather than varying by region and year.

---

## 3. Python Implementation

### Improvements Over Excel

The Python implementation addresses all limitations of the Excel model:

1. **City-specific VMT from FHWA.** Each of the 25 cities uses its own total VMT from the FHWA dataset. City-level total VMT ranges from approximately 0.8 billion (smaller cities like Lansing) to over 10 billion (larger metros like Philadelphia). `fhwa_vmt.csv` and `CITY_STATE_MAP` drive per-city lookups.

2. **State-specific AFDC fuel shares.** State-level vehicle fleet composition varies significantly. For example, California (Oakland) has much higher EV registration shares than Georgia (Atlanta) or Mississippi (Jackson). `afdc_vehicle_shares.csv` and `CITY_STATE_MAP` drive per-state lookups.

3. **Region-specific carbon intensity.** Regional grid cleanliness varies by AEO electricity market region. The Pacific Northwest (hydro-heavy) has much lower carbon intensity than the Southeast (coal/gas-heavy). `aeo_carbon_intensity.csv` and `CITY_REGION_MAP` drive per-region lookups.

4. **Car/truck MPG split.** Cars now use the MPG value from AEO Row 9, and trucks use the separate value from AEO Row 24. The `aeo_mpg.csv` file includes a `vehicle_class` column containing "car" or "truck" to disambiguate vehicle types.

5. **Dynamic car/truck fractions.** Instead of hardcoded 0.42/0.58 values, car and truck fractions are drawn from AEO LDV sales shares (AEO Rows 103-107), which vary by census division (South Atlantic, Middle Atlantic) and projection year. A `CITY_AEO_SALES_REGION_MAP` in `config.py` maps each of the 25 cities to its appropriate AEO sales region.

6. **SPPC carbon intensity available directly.** The SPPC electricity market region is included in `aeo_carbon_intensity.csv`, eliminating any need for fallback lookups.

7. **Freight efficiency fix.** The freight efficiency lookup uses the last matching row in the CSV, which corresponds to the average across all weight classes (AEO Rows 155-160).

8. **freight_ehybrid allocation corrected.** Electric hybrid freight vehicles are correctly allocated to the gasoline fuel category (R13), matching the original Excel model.

9. **Known Excel bug documented.** Transport Row 21 (car flex-fuel consumption) references cell E46 (diesel VMT) instead of E47 (flex VMT). This is a confirmed error in the original Excel model. The Python implementation uses the correct flex VMT value.

### Python Modules

Four core Python modules implement the transport pipeline:

- **`bau/transport.py`** -- Core transport calculation functions: VMT allocation by fuel type, year-over-year projection, fuel consumption calculation, and emissions estimation.
- **`bau/city.py`** -- The City class that orchestrates the full calculation pipeline from data loading through emissions output.
- **`bau/config.py`** -- All constants, city-to-region mappings, city-to-state mappings, VMT growth rates, and emission factors.
- **`bau/data_loader.py`** -- CSV loading and lookup functions that separate data access from calculation logic.

### Data Files Extracted from Excel

| File | Description |
|---|---|
| `data/inputs/fhwa_vmt.csv` | FHWA VMT per city (daily VMT in thousands, population ratio, total annual VMT) |
| `data/inputs/afdc_vehicle_shares.csv` | State-level AFDC vehicle registration shares by fuel type |
| `data/aeo/aeo_carbon_intensity.csv` | Regional electricity grid carbon intensity by year (MT CO2/MWh) |
| `data/aeo/aeo_mpg.csv` | Vehicle type MPG projections by year, with `vehicle_class` column |
| `data/aeo/aeo_freight_efficiency.csv` | Freight truck fuel efficiency by weight class, fuel type, and year |
| `data/aeo/aeo_ldv_sales_shares.csv` | Car vs. truck LDV sales fractions by census division and year |
| `data/inputs/emission_factors.csv` | EPA emission factors (kg CO2 per unit fuel) |

### Configuration

| Item | Detail |
|---|---|
| `CITY_REGION_MAP` | Maps 25 cities to their AEO electricity market region (12 regions total) |
| `CITY_STATE_MAP` | Maps 25 cities to their state (for AFDC fuel share lookups) |
| `CITY_AEO_SALES_REGION_MAP` | Maps 25 cities to their AEO LDV sales region |

---

## 4. Python Module Reference

### bau/transport.py -- Core Transport Calculations

This module contains the pure calculation functions that form the transport emissions pipeline:

- **`calculate_initial_vmt_by_fuel(total_vmt, state, afdc_shares)`** -- Takes a city's total annual VMT, its state, and the AFDC vehicle registration shares DataFrame. Returns a dictionary of VMT allocated by fuel type (gasoline, diesel, flex/ethanol, electric, PHEV, hybrid, biodiesel). Filters to 2024 shares if a `year` column is present.

- **`project_vmt(total_vmt, afdc_shares, afdc_deltas, years)`** -- Projects VMT forward using flat 0.6%/year national growth with AFDC share evolution. Takes the base year total VMT, AFDC 2024 shares dict, growth deltas dict, and list of projection years. Returns a DataFrame of projected VMT by fuel type and year.

- **`calculate_fuel_consumption(vmt_by_fuel, year, aeo_mpg, car_fraction, truck_fraction, aeo_freight)`** -- Converts projected VMT into fuel consumption (gallons or MWh) using vehicle-class-specific MPG values, car/truck fractions, and freight efficiency data. Returns a dictionary of fuel consumption by fuel category (gasoline, diesel, ethanol, electricity).

- **`calculate_transport_emissions(fuel_consumption, carbon_intensity)`** -- Multiplies fuel consumption by emission factors to produce emissions in metric tons of CO2. Returns a dictionary of emissions by fuel type.

- **`calculate_transport_savings(emissions_base, emissions_projected)`** -- Calculates the difference between baseline and projected emissions to determine GHG savings.

### bau/city.py -- City Class

The City class is the central abstraction that ties together data and calculations:

- **`City(name, all_data=...)`** -- Initialize with a city name and a pre-loaded data dictionary containing all datasets (FHWA, AFDC, AEO, emission factors).

- **`City.transport_emissions(year)`** -- Runs the full pipeline for a given projection year: VMT lookup, fuel split, growth projection, fuel consumption, and emissions calculation.

- **`City._get_city_vmt()`** -- Looks up the city's total annual VMT from the FHWA dataset. Applies the * 1000 scaling factor (FHWA reports daily VMT in thousands).

- **`City._get_projected_vmt()`** -- Returns cached VMT projections. The `_transport_vmt_cache` attribute avoids redundant recomputation when emissions are calculated for multiple years.

### bau/config.py -- Configuration and Constants

All constants and mapping tables are centralized here:

- **`CITY_REGION_MAP`** -- Maps 25 cities to their AEO electricity market region (12 regions total).
- **`CITY_STATE_MAP`** -- Maps 25 cities to their state (for AFDC fuel share lookups).
- **`CITY_AEO_SALES_REGION_MAP`** -- Maps 25 cities to their AEO LDV sales region (South Atlantic or Middle Atlantic).
- **`NATIONAL_VMT_GROWTH_RATE`** (0.006) -- Flat 0.6%/year national VMT growth rate from FHWA.
- **`VMT_GROWTH_RATES`** -- AEO 2025 Table 41 growth rates per fuel technology (deprecated; retained as backward-compat alias for `VMT_GROWTH_RATES_AEO_TABLE41`).
- **`EMISSION_FACTORS_KG_CO2`** -- EPA emission factors in kilograms of CO2 per unit of fuel.
- **`LDV_SHARE`** (0.9) and **`HDV_SHARE`** (0.1) -- Light-duty and heavy-duty vehicle VMT split.

### bau/data_loader.py -- Data Loading

All file I/O is isolated in this module:

- **`load_all_data()`** -- Loads all datasets from disk and returns a single dictionary containing all DataFrames needed for calculations.
- **`get_carbon_intensity(region, year, ci_df)`** -- Looks up the electricity carbon intensity (MT CO2/MWh) for a given AEO region and year.
- **`get_mpg(vehicle_type, year, mpg_df, vehicle_class)`** -- Looks up the MPG for a given vehicle type, year, and vehicle class ("car" or "truck").
- **`get_ldv_sales_share(region, vehicle_type, year, sales_df)`** -- Looks up the LDV sales fraction for a given region, vehicle type, and year.

---

## 5. Data Files Reference

| File | Source | Contents |
|---|---|---|
| `data/inputs/fhwa_vmt.csv` | FHWA; Excel Transport R44 | City name, daily VMT (in thousands), population ratio, total annual VMT |
| `data/inputs/afdc_vehicle_shares.csv` | AFDC; Excel Transport R72-R78 (2024), R80-R86 (2023) | State-level vehicle registration shares by fuel type (7 types, normalized to sum to 1.0), with `year` column for 2023 and 2024 |
| `data/inputs/afdc_growth_deltas.csv` | Excel Transport R88-R94 | Pre-computed share deltas (2024 − 2023) by state and fuel type |
| `data/inputs/emission_factors.csv` | EPA; Excel Transport R52-R63 | Emission factors in kg CO2 per unit of fuel (gallon or MWh) |
| `data/aeo/aeo_carbon_intensity.csv` | AEO 2025; Excel AEO R39-R50 | Regional electricity grid carbon intensity (MT CO2/MWh) by region and year |
| `data/aeo/aeo_mpg.csv` | AEO 2025; Excel AEO R9, R24 | Vehicle type MPG projections by year, with `vehicle_class` column ("car" or "truck") |
| `data/aeo/aeo_freight_efficiency.csv` | AEO 2025; Excel AEO R155-R160 | Freight truck fuel efficiency (MPG) by weight class, fuel type, and year |
| `data/aeo/aeo_ldv_sales_shares.csv` | AEO 2025; Excel AEO R103-R107 | Car vs. truck LDV sales fractions by census division and year |

All data files are stored as CSV and were extracted from the original Excel model (`data/raw/IAM_model.xlsx`). They are treated as read-only inputs to the Python pipeline.

---

## 6. Excel Formula to Python Mapping

The following table maps the most important Excel formulas to their Python implementations:

| Excel Reference | Excel Formula Description | Python Implementation |
|---|---|---|
| Transport R44 | Total VMT = XLOOKUP(city, FHWA) * 1000 | `City._get_city_vmt()` -- looks up city in `fhwa_vmt.csv`, multiplies by 1000 |
| Transport R45-R50 | VMT by fuel type = Total VMT * AFDC share | `calculate_initial_vmt_by_fuel()` -- total_vmt * state-specific AFDC share |
| Transport R45 col E+ | VMT(year) = total_vmt * (1.006)^(Y-2024) * share(Y) | `project_vmt()` -- flat 0.6% growth with AFDC share evolution |
| Transport R20 | Car gasoline consumption = VMT_gas * LDV * car_frac / car_mpg | `calculate_fuel_consumption()` -- uses AEO R9 car MPG |
| Transport R21 | Car flex-fuel consumption (Excel uses diesel VMT -- bug) | `calculate_fuel_consumption()` -- uses correct flex VMT |
| Transport R22 | Car EV consumption = VMT_ev * LDV * car_frac / car_mpg | `calculate_fuel_consumption()` -- EV consumption in MWh |
| Transport R26 | Truck gasoline consumption = VMT_gas * LDV * truck_frac / truck_mpg | `calculate_fuel_consumption()` -- uses AEO R24 truck MPG |
| Transport R33 | Freight gasoline consumption = VMT_gas * HDV / freight_mpg | `calculate_fuel_consumption()` -- uses last CSV match for average freight efficiency |
| Transport R38 | Freight hybrid consumption (allocated to gasoline) | `calculate_fuel_consumption()` -- correctly allocated to gasoline (R13) |
| Transport R37 | Freight PHEV consumption (allocated to diesel) | `calculate_fuel_consumption()` -- allocated to diesel (R14) |
| Transport R13 | Total gasoline = car_gas + car_phev + car_hybrid + truck_gas + truck_phev + truck_hybrid + freight_gas + freight_hybrid | Sum of all gasoline-category consumption components |
| Transport R14 | Total diesel = truck_diesel + freight_diesel + freight_phev | Sum of all diesel-category consumption components |
| Transport R15 | Total ethanol = car_flex + truck_flex + freight_flex | Sum of all ethanol-category consumption components |
| Transport R16 | Total electricity = car_ev + truck_ev + freight_ev | Sum of all electricity-category consumption components |
| Transport R7 | Gasoline emissions = gallons * 8.78 / 1000 | `calculate_transport_emissions()` -- applies EPA gasoline emission factor |
| Transport R8 | Diesel emissions = gallons * 10.21 / 1000 | `calculate_transport_emissions()` -- applies EPA diesel emission factor |
| Transport R9 | Ethanol emissions = gallons * 5.75 / 1000 | `calculate_transport_emissions()` -- applies EPA ethanol emission factor |
| Transport R10 | Electricity emissions = MWh * CI(region, year) | `calculate_transport_emissions()` -- applies region- and year-specific carbon intensity |
| Transport R4 | Total emissions = sum(R7:R10) | Sum of all four fuel-type emissions |
| AEO R9 | Car MPG by vehicle type and year | `get_mpg(vehicle_type, year, mpg_df, vehicle_class="car")` |
| AEO R24 | Truck MPG by vehicle type and year | `get_mpg(vehicle_type, year, mpg_df, vehicle_class="truck")` |
| AEO R39-R50 | Carbon intensity by region and year | `get_carbon_intensity(region, year, ci_df)` |
| AEO R103-R107 | LDV sales shares (car/truck) by region and year | `get_ldv_sales_share(region, vehicle_type, year, sales_df)` |
| AEO R155-R160 | Freight efficiency by weight class and fuel type | `get_mpg()` for freight -- uses last CSV match for average |

---

## 7. Validation Results

### Atlanta: Excel vs Python (Baseline Module.xlsx)

After correcting the Excel R21 bug and aligning AFDC shares and AEO freight data, Python matches the Excel model to floating-point precision for all projection years (2027–2050):

| Year | Total Match | Gasoline | Diesel | Ethanol | Electricity |
|---|---|---|---|---|---|
| 2024 | +0.004% | +0.002% | +0.06% | 0.000% | 0.000% |
| **2027–2050** | **0.000000%** | **0.000000%** | **0.000000%** | **0.000000%** | **0.000000%** |

The 2024 residual (+0.004%) is caused by Excel Transport R39/R40 using hardcoded future-year AEO column references for freight PHEV/hybrid efficiency instead of the matching 2024 column. This does not affect projection years.

### Atlanta 2027 Reference Values

| Metric | Excel (MT CO2) | Python (MT CO2) |
|---|---|---|
| Total | 1,829,547.14 | 1,829,547.14 |
| Gasoline | 1,626,389.46 | 1,626,389.46 |
| Diesel | 57,896.68 | 57,896.68 |
| Ethanol | 134,626.66 | 134,626.66 |
| Electricity | 10,634.35 | 10,634.35 |

### Multi-City Validation

Cities validated against `Baseline Module.xlsx` (city switched in Findings tab):

| City | State | AEO Sales Region | 2027–2050 Match | Notes |
|---|---|---|---|---|
| Atlanta | Georgia | South Atlantic | **0.000000%** | Reference city |
| Charlotte | North Carolina | South Atlantic | **0.000000%** | |
| Nashville | Tennessee | South Atlantic | **0.000000%** | |
| Cleveland | Ohio | Middle Atlantic | ~0.08–0.12% | Dynamic region difference (see below) |
| Philadelphia | Pennsylvania | Middle Atlantic | ~0.08–0.13% | Dynamic region difference (see below) |

**AEO Sales Region Note:** Excel Transport tab hardcodes AEO R103/R104 (South Atlantic) for car/truck LDV sales fractions for all cities. Python intentionally uses region-appropriate AEO sales data via `CITY_AEO_SALES_REGION_MAP` (South Atlantic or Middle Atlantic). This produces ~0.1% differences for non-South-Atlantic cities. This is a deliberate improvement — the dynamic mapping can be reverted to match Excel if needed.

### Full City Coverage

All 25 cities run successfully through the Python pipeline. The automated test suite (17 tests) confirms correct behavior across diverse geographies, vehicle fleets, and electricity grid regions.

---

## 8. Change Log

### Excel Corrections

The following corrections were made to `Baseline Module.xlsx` during Python-Excel reconciliation:

**1. Transport R21 — Car flex-fuel VMT reference (all year columns)**

- **Before:** `=E49*$F57*AEO!E103/AEO!E11` — referenced R49 (TDI Diesel VMT)
- **After:** `=E50*$F57*AEO!E103/AEO!E11` — references R50 (Flex-Fuel VMT)
- **Impact:** Car flex-fuel consumption was underestimated by ~70% because diesel VMT (~121M) is much smaller than flex-fuel VMT (~407M for Atlanta). This caused total transport emissions to be ~1.7% low.
- **Scope:** Fixed across all year columns (B through AB, 2024–2050).

**2. AEO R159 — Plug-in Diesel Hybrid freight efficiency (2024–2025)**

- **Before:** 0.0 MPG for 2024 (col B) and 2025 (col C); first non-zero value at 2026 (col D) = 9.4955
- **After:** 2024 = 9.3000, 2025 = 9.3900 (extrapolated from the 2026–2050 trend)
- **Impact:** With zero efficiency, Transport R39 (freight PHEV consumption) divided by zero for 2024–2025. Excel R39 worked around this by hardcoding `AEO!D159` (the 2026 value) for the 2024–2026 columns. With non-zero values populated, the correct year-matched column can be used.
- **Effect on projection years (2027–2050):** None — these already had non-zero values.

**3. AEO R160 — Electric Hybrid freight efficiency (2024)**

- **Before:** 0.0 MPG for 2024 (col B); first non-zero value at 2025 (col C) = 12.0398
- **After:** 2024 = 11.9900 (extrapolated from the 2025–2050 trend)
- **Impact:** With zero efficiency, Transport R40 (freight hybrid consumption) divided by zero for 2024. Excel R40 worked around this by hardcoding `AEO!C160` (the 2025 value) for the 2024 column. With the non-zero value populated, the correct year-matched column can be used.
- **Effect on projection years (2027–2050):** None — these already had non-zero values.

### Python-Side Data Corrections

**4. AFDC vehicle shares — normalized to 7 fuel types**

- **Before:** CSV included all 11 AFDC fuel types (including CNG, propane, hydrogen, methanol). The 7 fuel types used in the model summed to ~0.99995 instead of 1.0.
- **After:** CSV re-extracted from Excel Transport R72-R78, which normalizes shares to the 7 fuel types used (gasoline, diesel, ethanol, electric, PHEV, hybrid, biodiesel), summing to exactly 1.0.
- **Impact:** Eliminated a systematic -0.005% VMT allocation error across all fuel types and all cities.

**5. AFDC growth deltas — re-extracted from Excel**

- **Before:** Deltas computed from raw (un-normalized) 2024 and 2023 shares.
- **After:** Re-extracted from Excel Transport R88-R94, which uses the normalized shares.
- **Impact:** Consistent with the normalized shares; eliminates ~10⁻⁸ level differences in share evolution.

**6. AEO freight efficiency CSV — updated with new non-zero values**

- **Before:** `aeo_freight_efficiency.csv` had 0.0 for Plug-in Diesel Hybrid (2024–2025) and Electric Hybrid (2024).
- **After:** Updated to match the corrected Excel AEO R159-R160 values.
- **Impact:** Python freight PHEV/hybrid consumption now uses correct year-matched efficiency values instead of falling back to the first non-zero year.

### Intentional Python–Excel Differences

**7. AEO LDV sales region — dynamic vs hardcoded**

- **Excel:** Transport R20/R27 formulas hardcode `AEO!E103/AEO!E104` (South Atlantic car/truck fractions) for all cities.
- **Python:** Uses `CITY_AEO_SALES_REGION_MAP` to assign each city to its geographically correct AEO census division (South Atlantic or Middle Atlantic).
- **Impact:** Non-South-Atlantic cities (Cleveland, Philadelphia, Pittsburgh, etc.) show ~0.08–0.13% difference vs Excel. South Atlantic cities (Atlanta, Charlotte, Nashville, etc.) match exactly.
- **Rationale:** Using region-appropriate car/truck fractions is more accurate. The Excel hardcoding appears to be an oversight rather than intentional.
- **Reversibility:** Can be switched to match Excel by changing all entries in `CITY_AEO_SALES_REGION_MAP` to "South Atlantic".
