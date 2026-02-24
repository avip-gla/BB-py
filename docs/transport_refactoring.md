# Transport Module Refactoring: From Excel to City-Specific Python

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Version Comparison](#2-version-comparison)
3. [v1: Original Excel Model](#3-v1-original-excel-model)
4. [v2: City-Specific Refactor](#4-v2-city-specific-refactor)
5. [v3: Car/Truck MPG Split and Data Corrections](#5-v3-cartruck-mpg-split-and-data-corrections)
6. [Python Module Reference](#6-python-module-reference)
7. [Data Files Reference](#7-data-files-reference)
8. [Excel Formula to Python Mapping](#8-excel-formula-to-python-mapping)
9. [Validation Results](#9-validation-results)
10. [Versioned Files](#10-versioned-files)

---

## 1. Executive Summary

baseline-builder-py is a Python-based Integrated Assessment Model that calculates greenhouse gas (GHG) emissions savings for 25 US cities across projection years 2027 through 2050. The model covers two sectors: **Buildings** (residential and commercial) and **Transportation**. It was refactored from an Excel-based model into a Python/conda application to improve transparency, reproducibility, and city-level accuracy.

The transportation module underwent two major refactoring phases:

- **v2 (City-Specific Refactor):** Replaced the single reference city approach (Atlanta) with city-specific data pipelines. Each of the 25 cities now uses its own vehicle miles traveled (VMT), state-level fuel mix, and regional electricity carbon intensity. This was the foundational shift from a one-size-fits-all calculation to a geographically differentiated model.

- **v3 (MPG Split and Data Corrections):** Added car/truck MPG differentiation using separate AEO fuel economy values, introduced dynamic light-duty vehicle (LDV) sales fractions by census division and year, corrected freight efficiency lookups, fixed a fuel allocation error for electric hybrid freight vehicles, and added the SPPC electricity market region directly to the carbon intensity dataset.

Together, these refactoring phases transformed a static, single-city Excel spreadsheet into a modular, testable, and extensible Python application that produces city-specific GHG emissions projections validated against the original Excel model.

---

## 2. Version Comparison

The following table summarizes the key differences across all three versions of the transport module:

| Feature | v1 (Excel Original) | v2 (City-Specific) | v3 (MPG Split) |
|---|---|---|---|
| **VMT source** | Atlanta only (5,598,764,246 annual VMT) | FHWA data per city (25 unique baselines) | FHWA data per city (25 unique baselines) |
| **Fuel mix** | Georgia AFDC registration shares | State-specific AFDC shares (per city's state) | State-specific AFDC shares (per city's state) |
| **Carbon intensity** | SRSE (Atlanta's region) only | City's AEO region; SPPC falls back to MISC | City's AEO region; SPPC available directly |
| **Car/truck MPG** | Same MPG value for both | Same MPG value for both | Separate car (AEO R9) and truck (AEO R24) |
| **Car/truck fraction** | Hardcoded 0.42 / 0.58 | Hardcoded 0.42 / 0.58 | Dynamic from AEO LDV sales shares by region and year |
| **Freight efficiency** | First CSV match (weight-class-specific) | First CSV match (weight-class-specific) | Last CSV match (average across weight classes, AEO R155-R160) |
| **freight_ehybrid allocation** | To gasoline (R13) | To diesel (R14) -- bug introduced | To gasoline (R13) -- corrected to match Excel |
| **SPPC region** | N/A (SRSE only) | Falls back to MISC region | Available directly in carbon intensity data |
| **Python modules** | N/A (Excel only) | transport.py, city.py, config.py, data_loader.py | Same modules, updated with corrections |

---

## 3. v1: Original Excel Model

### Overview

The original Transport tab in the Excel model calculates emissions for a single reference city -- Atlanta -- and applies those values to all 25 cities in the Findings tab. This means that every city receives the same transportation emissions estimate regardless of its actual vehicle fleet, travel patterns, state fuel mix, or regional electricity grid.

### Formula Chain

The Excel calculation proceeds through the following steps:

**Step 1: Total VMT (Row 44)**

The model looks up Atlanta's total vehicle miles traveled from FHWA data:

- `R44 = XLOOKUP(city, FHWA) * 1000 = 5,598,764,246`

The raw FHWA value is in thousands, so it is multiplied by 1,000 to obtain actual annual VMT.

**Step 2: VMT by Fuel Type (Rows 45-50)**

Total VMT is split across fuel types using Georgia's AFDC vehicle registration shares:

- `R45-R50 = Total VMT * AFDC share (Georgia)`

This produces VMT for gasoline, diesel, flex-fuel (ethanol), electric, plug-in hybrid, and hybrid vehicles.

**Step 3: VMT Growth Projections (Rows 70-86)**

VMT growth rates are drawn from AEO 2025 Table 41, differentiated by vehicle technology:

- `R70-R86 = growth rates by fuel technology`
- `R45 col E+ = VMT(year-1) * (1 + growth_rate)`

Each subsequent year's VMT is calculated by compounding the prior year's value.

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

### Key Limitations

- All 25 cities receive Atlanta's transport emissions, regardless of geography.
- No variation by city VMT levels (cities range from under 1 billion to over 10 billion annual VMT).
- No variation by state fuel mix (e.g., California has very different EV adoption than Georgia).
- No variation by regional grid carbon intensity (e.g., the Pacific Northwest has much cleaner electricity than the Southeast).

---

## 4. v2: City-Specific Refactor

### Changes Introduced

The v2 refactor replaced the single-city approach with a fully city-specific data pipeline:

1. **City-specific VMT from FHWA data.** Each of the 25 cities now uses its own baseline VMT from the Federal Highway Administration, producing 25 different starting points for the projection.

2. **State-specific AFDC fuel shares.** Vehicle registration data from the Alternative Fuels Data Center is now looked up by each city's state, reflecting differences in vehicle fleet composition (e.g., higher EV shares in California vs. lower shares in Texas).

3. **Region-specific carbon intensity.** Each city is mapped to one of 12 AEO electricity market regions, so electricity emissions reflect the actual grid mix. Cities served by cleaner grids (e.g., Pacific Northwest hydro) produce lower electricity-related transport emissions than those on coal-heavy grids.

### What Replaced What: Excel Cell-Level Mapping

The v2 refactor replaced five specific hardcoded values from the Excel Transport tab with city-specific lookups:

| Excel Cell | v1 (All Cities = Atlanta) | v2 (Per City) | Data Source |
|---|---|---|---|
| R42 (City) | "Atlanta" hardcoded | Each of 25 cities | `config.CITY_REGION_MAP` keys |
| R43 (Region) | "SRSE" | Per-city AEO region | `config.CITY_REGION_MAP[city]` |
| R44 (Total VMT) | 5,598,764,246 (Atlanta) | FHWA lookup per city | `fhwa_vmt.csv` |
| R45-R50 (VMT by fuel) | R44 x Georgia AFDC shares | R44 x city's state AFDC shares | `afdc_vehicle_shares.csv` |
| R10 (Electricity CI) | XLOOKUP("SRSE", AEO CI) | XLOOKUP(city_region, AEO CI) | `aeo_carbon_intensity.csv` |

These replacements are driven by three new mapping tables and three new CSV data files, none of which existed in v1:

1. **FHWA VMT (R44)** -- City-level total VMT ranges from approximately 0.8 billion (smaller cities like Lansing) to over 10 billion (larger metros like Philadelphia). In v1, all 25 cities used Atlanta's 5.6 billion VMT. The new `fhwa_vmt.csv` and `CITY_STATE_MAP` enable per-city lookups.

2. **AFDC Fuel Shares (R45-R50)** -- State-level vehicle fleet composition varies significantly. For example, California (Oakland) has much higher EV registration shares than Georgia (Atlanta) or Mississippi (Jackson). The new `afdc_vehicle_shares.csv` and `CITY_STATE_MAP` enable per-state lookups.

3. **Carbon Intensity (R10)** -- Regional grid cleanliness varies by AEO electricity market region. The Pacific Northwest (hydro-heavy) has much lower carbon intensity than the Southeast (coal/gas-heavy). The new `aeo_carbon_intensity.csv` (with all 12 regions) and `CITY_REGION_MAP` enable per-region lookups.

### Items Still Approximated in v2

- **Car/truck MPG:** A single MPG value was used for both cars and trucks because the `aeo_mpg.csv` file did not yet include a `vehicle_class` column to distinguish them.
- **Car/truck fraction:** Hardcoded at 0.42 (cars) and 0.58 (trucks) for all cities and years.
- **SPPC electricity market region:** The SPPC region was not yet in the carbon intensity dataset, so cities in that region fell back to the MISC (miscellaneous) region.
- **Freight efficiency:** Used the first matching row in the CSV, which corresponds to a specific weight class rather than the average across all weight classes.
- **freight_ehybrid allocation:** Electric hybrid freight vehicles were incorrectly allocated to the diesel fuel category instead of gasoline.

### Python Modules Created

Four core Python modules were created during the v2 refactor:

- **`iam/transport.py`** -- Core transport calculation functions: VMT allocation by fuel type, year-over-year projection, fuel consumption calculation, and emissions estimation.
- **`iam/city.py`** -- The City class that orchestrates the full calculation pipeline from data loading through emissions output.
- **`iam/config.py`** -- All constants, city-to-region mappings, city-to-state mappings, VMT growth rates, and emission factors.
- **`iam/data_loader.py`** -- CSV loading and lookup functions that separate data access from calculation logic.

### Data Files Extracted from Excel

| File | Description |
|---|---|
| `data/inputs/fhwa_vmt.csv` | FHWA VMT per city (daily VMT in thousands, population ratio, total annual VMT) |
| `data/inputs/afdc_vehicle_shares.csv` | State-level AFDC vehicle registration shares by fuel type |
| `data/aeo/aeo_carbon_intensity.csv` | Regional electricity grid carbon intensity by year (MT CO2/MWh) |
| `data/aeo/aeo_mpg.csv` | Vehicle type MPG projections by year |
| `data/aeo/aeo_freight_efficiency.csv` | Freight truck fuel efficiency by weight class, fuel type, and year |
| `data/inputs/emission_factors.csv` | EPA emission factors (kg CO2 per unit fuel) |

### Numerical Impact

For Atlanta in projection year 2027:

- **v1 (Excel):** 1,603,108 MT CO2
- **v2 (Python):** approximately 1,475,530 MT CO2

The difference reflects the combined effect of the v2 approximations (single MPG, hardcoded car/truck fractions, freight efficiency lookup method, and the freight_ehybrid misallocation).

---

## 5. v3: Car/Truck MPG Split and Data Corrections

### Changes from v2

The v3 refactor addressed all remaining approximations and data corrections:

1. **Car/truck MPG split.** Cars now use the MPG value from AEO Row 9, and trucks use the separate value from AEO Row 24. The `aeo_mpg.csv` file was updated with a `vehicle_class` column containing "car" or "truck" to disambiguate vehicle types that previously had duplicate names.

2. **Dynamic car/truck fractions.** Instead of hardcoded 0.42/0.58 values, car and truck fractions are now drawn from AEO LDV sales shares (AEO Rows 103-107), which vary by census division (South Atlantic, Middle Atlantic) and projection year. A new `CITY_AEO_SALES_REGION_MAP` in `config.py` maps each of the 25 cities to its appropriate AEO sales region.

3. **SPPC carbon intensity available directly.** The SPPC electricity market region is now included in `aeo_carbon_intensity.csv`, eliminating the need for the MISC fallback. The `TRANSPORT_CI_REGION_FALLBACK` configuration was removed.

4. **Freight efficiency fix.** The freight efficiency lookup now uses the last matching row in the CSV, which corresponds to the average across all weight classes (AEO Rows 155-160). Previously, the first match was used, which corresponded to a specific weight class.

5. **freight_ehybrid allocation corrected.** Electric hybrid freight vehicles are now correctly allocated to the gasoline fuel category (R13), matching the original Excel model. In v2, they had been incorrectly placed in diesel (R14).

6. **Known Excel bug documented.** Transport Row 21 (car flex-fuel consumption) references cell E46 (diesel VMT) instead of E47 (flex VMT). This is a confirmed error in the original Excel model. The Python implementation uses the correct flex VMT value.

### New and Updated Data Files

| File | Change |
|---|---|
| `data/aeo/aeo_ldv_sales_shares.csv` | **New.** Car vs. truck LDV sales fractions by census division and year. |
| `data/aeo/aeo_mpg.csv` | **Updated.** Added `vehicle_class` column ("car" or "truck") to distinguish vehicle types. |
| `data/aeo/aeo_carbon_intensity.csv` | **Updated.** Added SPPC region data directly. |

### Configuration Changes

| Change | Detail |
|---|---|
| **Added:** `CITY_AEO_SALES_REGION_MAP` | Maps 25 cities to their AEO LDV sales region (South Atlantic or Middle Atlantic). |
| **Removed:** `TRANSPORT_CI_REGION_FALLBACK` | No longer needed since SPPC is available in the carbon intensity data. |

### Numerical Impact

For Atlanta in projection year 2027:

- **v2 (Python):** approximately 1,475,530 MT CO2
- **v3 (Python):** approximately 1,626,675 MT CO2
- **v1 (Excel):** 1,603,108 MT CO2
- **Difference (v3 vs. Excel):** approximately 23,567 MT CO2 (1.47%)

The 23,567 MT CO2 difference between v3 and Excel is exactly explained by the Excel Row 21 bug: Python correctly uses flex VMT for car flex-fuel consumption, while Excel incorrectly uses diesel VMT. The additional ethanol consumption from the correct flex VMT accounts for the entire discrepancy.

---

## 6. Python Module Reference

### iam/transport.py -- Core Transport Calculations

This module contains the pure calculation functions that form the transport emissions pipeline:

- **`calculate_initial_vmt_by_fuel(total_vmt, state, afdc_shares)`** -- Takes a city's total annual VMT, its state, and the AFDC vehicle registration shares DataFrame. Returns a dictionary of VMT allocated by fuel type (gasoline, diesel, flex/ethanol, electric, PHEV, hybrid).

- **`project_vmt(initial_vmt_by_fuel, years)`** -- Takes the initial VMT-by-fuel dictionary and projects it forward across the specified years using AEO growth rates. Returns a DataFrame of projected VMT by fuel type and year.

- **`calculate_fuel_consumption(vmt_by_fuel, year, aeo_mpg, car_fraction, truck_fraction, aeo_freight)`** -- Converts projected VMT into fuel consumption (gallons or MWh) using vehicle-class-specific MPG values, car/truck fractions, and freight efficiency data. Returns a dictionary of fuel consumption by fuel category (gasoline, diesel, ethanol, electricity).

- **`calculate_transport_emissions(fuel_consumption, carbon_intensity)`** -- Multiplies fuel consumption by emission factors to produce emissions in metric tons of CO2. Returns a dictionary of emissions by fuel type.

- **`calculate_transport_savings(emissions_base, emissions_projected)`** -- Calculates the difference between baseline and projected emissions to determine GHG savings.

### iam/city.py -- City Class

The City class is the central abstraction that ties together data and calculations:

- **`City(name, all_data=...)`** -- Initialize with a city name and a pre-loaded data dictionary containing all datasets (FHWA, AFDC, AEO, emission factors).

- **`City.transport_emissions(year)`** -- Runs the full pipeline for a given projection year: VMT lookup, fuel split, growth projection, fuel consumption, and emissions calculation.

- **`City._get_city_vmt()`** -- Looks up the city's total annual VMT from the FHWA dataset. Applies the * 1000 scaling factor (FHWA reports daily VMT in thousands).

- **`City._get_projected_vmt()`** -- Returns cached VMT projections. The `_transport_vmt_cache` attribute avoids redundant recomputation when emissions are calculated for multiple years.

### iam/config.py -- Configuration and Constants

All constants and mapping tables are centralized here:

- **`CITY_REGION_MAP`** -- Maps 25 cities to their AEO electricity market region (12 regions total).
- **`CITY_STATE_MAP`** -- Maps 25 cities to their state (for AFDC fuel share lookups).
- **`CITY_AEO_SALES_REGION_MAP`** -- Maps 25 cities to their AEO LDV sales region (South Atlantic or Middle Atlantic).
- **`VMT_GROWTH_RATES`** -- AEO 2025 Table 41 growth rates per fuel technology and year.
- **`EMISSION_FACTORS_KG_CO2`** -- EPA emission factors in kilograms of CO2 per unit of fuel.
- **`LDV_SHARE`** (0.9) and **`HDV_SHARE`** (0.1) -- Light-duty and heavy-duty vehicle VMT split.

### iam/data_loader.py -- Data Loading

All file I/O is isolated in this module:

- **`load_all_data()`** -- Loads all datasets from disk and returns a single dictionary containing all DataFrames needed for calculations.
- **`get_carbon_intensity(region, year, ci_df)`** -- Looks up the electricity carbon intensity (MT CO2/MWh) for a given AEO region and year.
- **`get_mpg(vehicle_type, year, mpg_df, vehicle_class)`** -- Looks up the MPG for a given vehicle type, year, and vehicle class ("car" or "truck").
- **`get_ldv_sales_share(region, vehicle_type, year, sales_df)`** -- Looks up the LDV sales fraction for a given region, vehicle type, and year.

---

## 7. Data Files Reference

| File | Source | Contents |
|---|---|---|
| `data/inputs/fhwa_vmt.csv` | FHWA; Excel Transport R44 | City name, daily VMT (in thousands), population ratio, total annual VMT |
| `data/inputs/afdc_vehicle_shares.csv` | AFDC; Excel Transport R90-R96 | State-level vehicle registration shares by fuel type (gasoline, diesel, flex, EV, PHEV, hybrid) |
| `data/inputs/emission_factors.csv` | EPA; Excel Transport R52-R63 | Emission factors in kg CO2 per unit of fuel (gallon or MWh) |
| `data/aeo/aeo_carbon_intensity.csv` | AEO 2025; Excel AEO R39-R50 | Regional electricity grid carbon intensity (MT CO2/MWh) by region and year |
| `data/aeo/aeo_mpg.csv` | AEO 2025; Excel AEO R9, R24 | Vehicle type MPG projections by year, with `vehicle_class` column ("car" or "truck") |
| `data/aeo/aeo_freight_efficiency.csv` | AEO 2025; Excel AEO R155-R160 | Freight truck fuel efficiency (MPG) by weight class, fuel type, and year |
| `data/aeo/aeo_ldv_sales_shares.csv` | AEO 2025; Excel AEO R103-R107 | Car vs. truck LDV sales fractions by census division and year |

All data files are stored as CSV and were extracted from the original Excel model (`data/raw/IAM_model.xlsx`). They are treated as read-only inputs to the Python pipeline.

---

## 8. Excel Formula to Python Mapping

The following table maps the most important Excel formulas to their Python implementations:

| Excel Reference | Excel Formula Description | Python Implementation |
|---|---|---|
| Transport R44 | Total VMT = XLOOKUP(city, FHWA) * 1000 | `City._get_city_vmt()` -- looks up city in `fhwa_vmt.csv`, multiplies by 1000 |
| Transport R45-R50 | VMT by fuel type = Total VMT * AFDC share | `calculate_initial_vmt_by_fuel()` -- total_vmt * state-specific AFDC share |
| Transport R45 col E+ | VMT(year) = VMT(year-1) * (1 + growth_rate) | `project_vmt()` -- compounds VMT forward using AEO Table 41 growth rates |
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

**Known Excel Bug:** Transport R21 references cell E46 (diesel VMT) instead of E47 (flex VMT) for car flex-fuel consumption. The Python implementation uses the correct flex VMT. This is the sole source of the 1.47% difference between v3 and the Excel model for Atlanta 2027.

---

## 9. Validation Results

### Atlanta 2027: Cross-Version Comparison

| Version | Total Emissions (MT CO2) | Notes |
|---|---|---|
| v1 (Excel) | 1,603,108 | Reference city calculation; applied uniformly to all 25 cities |
| v2 (Python) | ~1,475,530 | City-specific VMT and fuel mix, but with single MPG and other approximations |
| v3 (Python) | ~1,626,675 | Corrected MPG split, dynamic fractions, freight fix; +1.47% vs. Excel |

### Explanation of the v3 vs. Excel Difference

The 23,567 MT CO2 difference between v3 (1,626,675) and the Excel model (1,603,108) is fully accounted for by a confirmed bug in the Excel model:

- Excel Transport Row 21 (car flex-fuel consumption) references cell E46, which contains **diesel VMT**, instead of E47, which contains the correct **flex-fuel VMT**.
- Because flex-fuel VMT differs from diesel VMT, the Python model (which uses the correct flex VMT) calculates a different ethanol consumption value.
- The additional ethanol consumption produces exactly the observed 23,567 MT CO2 difference.

This has been verified by manually substituting the Excel's incorrect VMT reference into the Python model and confirming that the outputs then match exactly.

### Full City Coverage

All 25 cities run successfully through both the v2 and v3 pipelines. The automated test suite includes 21 tests, all of which pass. Cities span diverse geographies, vehicle fleets, and electricity grid regions, confirming that the city-specific data pipeline handles the full range of input variations.

---

## 10. Versioned Files

Versioned copies of the four core modules are preserved in the `iam/versions/` directory to support comparison and rollback:

| v2 File | v3 File | Module Purpose |
|---|---|---|
| `transport_v2.py` | `transport_v3.py` | Core transport calculation functions |
| `city_v2.py` | `city_v3.py` | City class orchestrating the full pipeline |
| `config_v2.py` | `config_v3.py` | Constants, mappings, and configuration |
| `data_loader_v2.py` | `data_loader_v3.py` | CSV loading and data lookup functions |

The v2 files correspond to git commit `0ddac27`. The v3 files represent the current working tree.

To switch between versions for testing or comparison, the versioned files can be copied over the active modules in `iam/`. For example, to revert to v2 behavior:

```
cp iam/versions/transport_v2.py iam/transport.py
cp iam/versions/city_v2.py iam/city.py
cp iam/versions/config_v2.py iam/config.py
cp iam/versions/data_loader_v2.py iam/data_loader.py
```

This approach preserves a complete audit trail of the refactoring process and allows side-by-side numerical validation between versions.
