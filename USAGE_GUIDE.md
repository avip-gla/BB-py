# baseline-builder-py Usage Guide

A step-by-step guide for running the IAM (Integrated Assessment Model) to calculate GHG emissions savings across US cities.

---

## 1. Quick Start

### Prerequisites
- [Anaconda](https://www.anaconda.com/) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html) installed
- macOS, Linux, or Windows with a terminal

### Environment Setup

```bash
# Create and activate the conda environment
conda create -n baseline-builder-py python=3.11 -y
conda activate baseline-builder-py

# Install dependencies
pip install -r requirements.txt
```

Or use the environment file:

```bash
conda env create -f environment.yml
conda activate baseline-builder-py
```

### Verify Installation

```bash
# Run the test suite to confirm everything works
pytest tests/ -v
```

You should see all 17 tests pass:

```
tests/test_findings.py::TestEmissionFactors::test_ng_emission_factor PASSED
tests/test_findings.py::TestEmissionFactors::test_mwh_per_mmbtu PASSED
...
17 passed
```

---

## 2. Running Single-City Scenarios

The simplest way to use the model is to run it for one city:

```bash
python scripts/run_model.py --cities atlanta
```

This will:
1. Load all input data (fixed national parameters, city data, AEO projections)
2. Calculate buildings and transportation emissions for every year from 2027 to 2050
3. Save results as a CSV file in `outputs/csv/`

**Output file:** `outputs/csv/atlanta_results.csv`

### Adding a Summary

Use `--summary` to print trend information to the terminal:

```bash
python scripts/run_model.py --cities atlanta --summary
```

This shows the total and annual deltas for buildings, transport, and total emissions.

### Choosing Output Format

```bash
# CSV output (default)
python scripts/run_model.py --cities atlanta --output csv

# Excel output
python scripts/run_model.py --cities atlanta --output xlsx

# Both CSV and Excel
python scripts/run_model.py --cities atlanta --output both
```

**Output locations:**
- CSV: `outputs/csv/atlanta_results.csv`
- Excel: `outputs/xlsx/`

---

## 3. Running Multi-City Comparisons

### Running the Model for Multiple Cities

```bash
python scripts/run_model.py --cities atlanta charlotte nashville memphis
```

This produces:
- Individual CSV files for each city in `outputs/csv/`
- A combined CSV with all cities in one file: `outputs/csv/multi_city_results.csv`

### Comparison Tables

For a formatted side-by-side analysis, use `compare_cities.py`:

```bash
python scripts/compare_cities.py --cities atlanta charlotte nashville memphis
```

This prints four tables to the terminal:
1. **Emissions Summary** -- 2027 and 2050 emissions by sector with percent change
2. **Savings Rankings** -- Cities ranked by total GHG savings
3. **Year-by-Year Trajectory** -- Total emissions at milestone years (2027, 2030, 2035, 2040, 2045, 2050)
4. **Sector Breakdown** -- Buildings vs. transport share of 2027 emissions

---

## 4. Generating Plots

Add `--plot` to the comparison script to generate a 4-panel chart:

```bash
python scripts/compare_cities.py --cities atlanta charlotte nashville memphis --plot
```

**Output file:** `outputs/comparison_plot.png`

The plot includes:
- Total emissions over time (line chart)
- Buildings emissions over time (line chart)
- Cumulative GHG savings vs. 2027 baseline (line chart)
- 2050 GHG savings by sector (bar chart)

---

## 5. Running All 25 Cities

### Full Batch Run

```bash
python scripts/run_model.py --all --output csv
```

This runs all 25 cities and produces individual CSVs plus a combined file.

### Full Comparison

```bash
python scripts/compare_cities.py --all
```

### Top-N Filtering

Show only the top cities by total GHG savings:

```bash
# Top 10 cities by savings
python scripts/compare_cities.py --all --top 10

# Top 5 with plots
python scripts/compare_cities.py --all --top 5 --plot
```

---

## 6. Output Files Reference

### CSV Output Columns

| Column | Description |
|--------|-------------|
| `city` | City name |
| `year` | Projection year (2027-2050) |
| `buildings_total_mt_co2e` | Total buildings emissions (MT CO2e) |
| `buildings_electricity_mt_co2e` | Electricity-related buildings emissions |
| `buildings_ng_mt_co2e` | Natural gas-related buildings emissions |
| `transport_mt_co2e` | Transportation sector emissions (MT CO2e) |
| `total_mt_co2e` | Total emissions across all sectors |
| `buildings_savings_mtco2e` | Buildings GHG savings vs. 2027 baseline |
| `transport_savings_mtco2e` | Transport GHG savings vs. 2027 baseline |
| `total_savings_mtco2e` | Total GHG savings vs. 2027 baseline |

### Output Directory Structure

```
outputs/
├── csv/
│   ├── atlanta_results.csv          # Single-city results
│   ├── charlotte_results.csv
│   ├── multi_city_results.csv       # Combined multi-city file
│   └── ...
├── xlsx/                            # Excel workbooks
└── comparison_plot.png              # Generated plots
```

### Units

- **MT CO2e** -- Metric tons of CO2 equivalent
- **Savings** -- Positive values indicate emissions reductions relative to the 2027 baseline

---

## 7. Running Tests

```bash
# Run all tests with verbose output
pytest tests/ -v

# Run a specific test class
pytest tests/test_findings.py::TestEmissionFactors -v

# Run a single test
pytest tests/test_findings.py::TestCityIntegration::test_atlanta_buildings_2027 -v
```

The test suite (17 tests) validates:
- Emission factor constants match the Excel model
- NG and electricity emissions formulas produce correct values
- City-level integration (Atlanta buildings and transport for 2027 and 2050)
- VMT projection: flat 0.6% growth rate, AFDC share evolution, biodiesel in diesel bucket
- SPPC carbon intensity (Kansas City uses SPPC directly)
- All 25 cities load and produce non-zero emissions

---

## 8. Troubleshooting

### "ModuleNotFoundError: No module named 'iam'"
Make sure you are running scripts from the project root directory:
```bash
cd /path/to/baseline-builder-py
python scripts/run_model.py --cities atlanta
```

### "conda: command not found"
Anaconda/Miniconda is not installed or not in your PATH. Install from https://docs.conda.io/en/latest/miniconda.html.

### "Warning: City 'xxx' not found"
City names are case-insensitive but must match a valid city. Run the command without arguments to see available cities:
```bash
python scripts/run_model.py
```
Multi-word cities should be entered as separate words:
```bash
python scripts/run_model.py --cities "kansas city"
python scripts/run_model.py --cities "st. louis"
python scripts/run_model.py --cities "newport news"
```

### "No such file or directory: data/inputs/..."
The data files may not have been extracted yet. Ensure the `data/` directory contains the required input CSVs. See the project README for data setup instructions.

### Conda environment not activated
If you see import errors for pandas, numpy, etc.:
```bash
conda activate baseline-builder-py
```

### Plot not displaying
The `--plot` flag saves to `outputs/comparison_plot.png` rather than displaying interactively. Open the file with your system image viewer after generation.

---

## 9. Customizing GHG Calculation Logic

The model's emissions calculations are organized as pure functions in separate modules. This section explains where each calculation lives and how to modify it.

### Architecture Overview

```
City.run_all_years()                   # iam/city.py — orchestrates everything
  ├── City.buildings_emissions(year)   # calls into iam/buildings.py
  │     ├── Electricity: MMBtu → MWh → MT CO2 (using regional carbon intensity)
  │     └── Natural Gas: MMBtu → MT CO2e (using fixed emission factor)
  └── City.transport_emissions(year)   # calls into iam/transport.py
        ├── VMT allocation by fuel type (AFDC state shares)
        ├── VMT projection (AEO growth rates)
        ├── Fuel consumption (VMT / MPG)
        └── Emissions (fuel × emission factor)
```

### Buildings Sector

**File:** `iam/buildings.py`

Buildings emissions are the sum of electricity emissions and natural gas emissions, calculated separately for residential and commercial sectors.

#### Key Functions

| Function | Location | What it does |
|----------|----------|-------------|
| `calculate_electricity_emissions()` | `iam/buildings.py:34` | Converts electricity MMBtu → MWh → MT CO2 using carbon intensity |
| `calculate_ng_emissions()` | `iam/buildings.py:63` | Converts NG MMBtu → MT CO2e using fixed emission factor |
| `calculate_total_buildings_emissions()` | `iam/buildings.py:186` | Combines res + com electricity + NG into total |
| `calculate_residential_savings()` | `iam/buildings.py:87` | Savings = base year emissions - projected year emissions |
| `calculate_commercial_savings()` | `iam/buildings.py:141` | Same as residential but for commercial sector |

#### How to Change Buildings Logic

**Change the electricity emission factor (carbon intensity):**
Carbon intensity comes from AEO projections by region. To use a different source, modify the data in `data/aeo/` or change the lookup in `iam/data_loader.py` (`get_carbon_intensity()`).

**Change the natural gas emission factor:**
Edit `NG_EMISSION_FACTOR_MT_CO2_PER_MMBTU` in `iam/config.py` (currently `0.05306`).

**Change the MMBtu-to-MWh conversion:**
Edit `MWH_PER_MMBTU` in `iam/config.py` (currently `0.3`).

**Add a new buildings sub-sector (e.g., industrial):**
1. Add consumption data CSV under `data/inputs/`
2. Create a new calculation function in `iam/buildings.py` following the pattern of `calculate_residential_savings()`
3. Update `calculate_total_buildings_emissions()` to include the new sub-sector
4. Update `City.buildings_emissions()` in `iam/city.py` to incorporate the new data

**Change the electricity emissions formula:**
Edit `calculate_electricity_emissions()` in `iam/buildings.py`. The current formula is:
```python
# Current: emissions = MMBtu * 0.3 (MWh/MMBtu) * carbon_intensity (MT CO2/MWh)
mwh = electricity_mmbtu * MWH_PER_MMBTU
emissions_mt_co2 = mwh * carbon_intensity
```

### Transportation Sector

**File:** `iam/transport.py`

Transportation emissions follow a 4-step pipeline: VMT allocation → VMT projection → fuel consumption → emissions.

#### Key Functions

| Function | Location | What it does |
|----------|----------|-------------|
| `calculate_initial_vmt_by_fuel()` | `iam/transport.py:37` | Splits total VMT by fuel type using AFDC state shares |
| `project_vmt()` | `iam/transport.py:78` | Projects VMT forward using AEO annual growth rates |
| `calculate_fuel_consumption()` | `iam/transport.py:142` | Converts VMT → gallons/MWh using AEO MPG tables |
| `calculate_transport_emissions()` | `iam/transport.py:306` | Converts fuel consumption → MT CO2 using EPA emission factors |
| `calculate_transport_savings()` | `iam/transport.py:354` | Savings = base year - projected year |

#### How to Change Transportation Logic

**Change VMT growth rate:**
Edit `NATIONAL_VMT_GROWTH_RATE` in `iam/config.py` (currently `0.006`, i.e., 0.6%/year flat national growth from FHWA). Total VMT grows at this flat rate; fuel-type allocation evolves using AFDC share deltas.

**Change AFDC fuel share evolution:**
Edit `data/inputs/afdc_growth_deltas.csv` to change how fuel shares evolve over time. Each row is a state, each column is a fuel type. The delta is applied as a fixed step for all future years (not cumulative).

**Change EPA emission factors:**
Edit `EMISSION_FACTORS_KG_CO2` in `iam/config.py`. Current values (kg CO2 per gallon):
- Motor gasoline: 8.78
- Diesel: 10.21
- Ethanol: 5.75

**Change the LDV/HDV split:**
Edit `LDV_SHARE` and `HDV_SHARE` in `iam/config.py` (currently 0.9 / 0.1).

**Change the car/truck fraction within LDV:**
The `car_fraction` and `truck_fraction` parameters in `calculate_fuel_consumption()` (`iam/transport.py`) are dynamically sourced from AEO LDV sales shares by region and year. To use different values, modify the lookup in `City.transport_emissions()` (`iam/city.py`) or the data in `data/aeo/aeo_ldv_sales_shares.csv`.

**Add a new fuel type (e.g., hydrogen):**
1. Add the fuel's VMT growth rate to `VMT_GROWTH_RATES` in `iam/config.py`
2. Add the fuel's emission factor to `EMISSION_FACTORS_KG_CO2` in `iam/config.py`
3. Add AFDC share mapping in `calculate_initial_vmt_by_fuel()` (`iam/transport.py`)
4. Add fuel consumption calculation in `calculate_fuel_consumption()` (`iam/transport.py`)
5. Add emissions calculation in `calculate_transport_emissions()` (`iam/transport.py`)

**Change how VMT is projected:**
Edit `project_vmt()` in `iam/transport.py`. The current formula is flat growth with AFDC share evolution:
```python
# Current: total_vmt(Y) = total_vmt(2024) * (1.006)^(Y - 2024)
# fuel_share(Y) = clamp(2024_share + growth_delta, min=0), re-normalized to sum to 1.0
# fuel_vmt(Y) = total_vmt(Y) * fuel_share(Y)
```

### Shared Utilities

**File:** `iam/emissions.py`

Contains unit conversion helpers used by both sectors:

| Function | What it does |
|----------|-------------|
| `mmbtu_to_mwh()` | Energy conversion: MMBtu × 0.3 = MWh |
| `mwh_to_mt_co2()` | MWh × carbon intensity = MT CO2 |
| `ng_mmbtu_to_mt_co2e()` | NG MMBtu × 0.05306 = MT CO2e |
| `gallons_to_mt_co2()` | Gallons × emission factor / 1000 = MT CO2 |
| `calculate_trend()` | Computes total and annual delta between base and target values |

### Constants and Configuration

**File:** `iam/config.py`

All hardcoded values are centralized here. Key constants you might want to change:

| Constant | Current Value | Description |
|----------|---------------|-------------|
| `PROJECTION_YEARS` | 2027-2050 | Range of years the model projects |
| `BASE_YEAR` | 2024 | Starting year for VMT compound growth |
| `NG_EMISSION_FACTOR_MT_CO2_PER_MMBTU` | 0.05306 | NG emission factor |
| `MWH_PER_MMBTU` | 0.3 | Electricity unit conversion |
| `LDV_SHARE` / `HDV_SHARE` | 0.9 / 0.1 | Light-duty vs heavy-duty VMT split |
| `NATIONAL_VMT_GROWTH_RATE` | 0.006 | Flat 0.6%/year national VMT growth (FHWA) |
| `EMISSION_FACTORS_KG_CO2` | (see file) | EPA emission factors by fuel |
| `CITY_REGION_MAP` | (see file) | Maps each city to its AEO electricity region |
| `CITY_AEO_SALES_REGION_MAP` | (see file) | Maps each city to its AEO LDV sales region |

### Aggregation Layer

**File:** `iam/findings.py`

This module mirrors the Excel "Findings" tab and pulls buildings + transport together. If you add a new sector (e.g., waste, industrial), update `calculate_findings_for_year()` to include it in the totals.

### Swapping Calculation Logic (Strategy Pattern)

The architecture is designed so calculation logic can be swapped without touching the City class. For example, to use a different buildings formula:

1. Write your new function in `iam/buildings.py` (or a new module) with the same signature as the existing one
2. Change the import in `iam/findings.py` or `iam/city.py` to point to your new function

```python
# In iam/city.py — swap this import to change buildings calculation
from iam.buildings import calculate_total_buildings_emissions  # original
# from iam.buildings_alt import calculate_total_buildings_emissions  # your new version
```

---

## 10. Data Inputs Reference

All input data lives under `data/`. The model loads these files automatically via `iam/data_loader.py`.

### Directory Layout

```
data/
├── raw/
│   └── IAM_model.xlsx                    # Original Excel model (source of truth)
├── inputs/
│   ├── fixed_data.csv                    # National constants (emission factors, conversions)
│   ├── fhwa_vmt.csv                      # FHWA Vehicle Miles Traveled by city
│   ├── afdc_vehicle_shares.csv           # Vehicle registration shares by state/fuel type (2023 & 2024)
│   ├── afdc_growth_deltas.csv            # AFDC share deltas (2024 − 2023) by state
│   ├── emission_factors.csv              # EPA emission factors (kg CO2 per unit by fuel)
│   ├── buildings_total_emissions.csv     # Pre-calculated buildings emissions (city × year)
│   ├── transport_emissions.csv           # Pre-calculated transport emissions (year only)
│   ├── transport_vmt_by_fuel.csv         # VMT projections by fuel type (year only)
│   ├── transport_fuel_consumption.csv    # Fuel consumption projections (year only)
│   ├── cities/                           # One CSV per city
│   │   ├── atlanta.csv
│   │   ├── akron.csv
│   │   └── ... (25 files)
│   ├── electricity/
│   │   └── electricity_emissions.csv     # Electricity emissions (city × year)
│   └── ng/
│       ├── ng_emissions.csv              # Total NG emissions (city × year)
│       ├── ng_residential_consumption.csv  # Residential NG MMBtu (city × year)
│       ├── ng_residential_emissions.csv
│       ├── ng_commercial_consumption.csv   # Commercial NG MMBtu (city × year)
│       └── ng_commercial_emissions.csv
└── aeo/
    ├── aeo_carbon_intensity.csv          # Grid carbon intensity by region × year
    ├── aeo_mpg.csv                       # Vehicle MPG by type × year
    ├── aeo_freight_efficiency.csv        # Freight truck MPG by category × year
    ├── aeo_ldv_sales_shares.csv          # Car/truck LDV sales fractions by region × year
    └── aeo_regional_electricity.csv      # Regional electricity sales & CO2 (source table)
```

### Data Sources

| File | Source | Description |
|------|--------|-------------|
| `fixed_data.csv` | Excel model | NG emission factor (53.06 kg CO2/MMBtu), MWh/MMBtu (0.3), LDV/HDV shares |
| `cities/*.csv` | SLOPE (NREL) | City-level electricity and NG consumption (MMBtu), inventory totals |
| `fhwa_vmt.csv` | FHWA HM-71 | Annual VMT per city, scaled from urbanized area to city proper by population |
| `afdc_vehicle_shares.csv` | AFDC (DOE) | 2023 and 2024 Light-Duty Vehicle registration shares by fuel type per state (7 types, normalized) |
| `afdc_growth_deltas.csv` | AFDC (DOE) | Pre-computed share deltas (2024 − 2023) by state and fuel type |
| `emission_factors.csv` | EPA 2025 Hub | kg CO2 per gallon/unit for each fuel type |
| `aeo_carbon_intensity.csv` | AEO 2025 Table 54 | MT CO2/MWh by electricity market region, 2024-2050 |
| `aeo_mpg.csv` | AEO 2025 | Miles per gallon by vehicle/fuel type, 2024-2050 |
| `aeo_freight_efficiency.csv` | AEO 2025 Table 49 | Freight truck MPG by fuel type, 2024-2050 |
| `aeo_ldv_sales_shares.csv` | AEO 2025 Table 38 | Car vs. truck LDV sales fractions by census division and year |
| `buildings_total_emissions.csv` | Derived from Excel | Total buildings emissions (electricity + NG) per city per year |
| `electricity_emissions.csv` | Derived from Excel | Electricity-related CO2 emissions per city per year |
| `ng_*.csv` | Derived from Excel | NG consumption (MMBtu) and emissions (MT CO2e) per city per year |
| `transport_emissions.csv` | Derived from Excel | Transport emissions by fuel type (reference city only) |
| `transport_vmt_by_fuel.csv` | Derived from Excel | VMT projections by fuel type (reference city only) |

### CSV Format Conventions

- Year columns in AEO files use the prefix `y` (e.g., `y2027`, `y2050`)
- City × year files use long format with columns: `city`, `year`, `<value>`
- City names use title case with spaces/periods (e.g., `Kansas City`, `St. Louis`)
- City CSV filenames use lowercase with underscores (e.g., `kansas_city.csv`, `st_louis.csv`)

### City CSV Columns

Each file in `data/inputs/cities/` contains one row with these fields:

| Column | Description |
|--------|-------------|
| `name` | City name |
| `region` | AEO electricity market region code |
| `buildings_residential_2027` | Residential buildings emissions baseline (MT CO2e) |
| `buildings_commercial_2027` | Commercial buildings emissions baseline (MT CO2e) |
| `electricity_residential_mwh` | Residential electricity consumption (MWh) |
| `electricity_commercial_mwh` | Commercial electricity consumption (MWh) |
| `electricity_residential_mmbtu` | Residential electricity consumption (MMBtu) |
| `electricity_commercial_mmbtu` | Commercial electricity consumption (MMBtu) |
| `inventory_total` | City GHG inventory total (for validation) |
| `eie_total` | EIE total (for validation) |
| `inventory_residential` | Inventory residential emissions |
| `inventory_commercial` | Inventory commercial emissions |
| `inventory_transport` | Inventory transport emissions |

---

## 11. How to Add a New City

To add a 26th (or Nth) city to the model:

### Step 1: Gather Required Data

You need the following for your new city:
- **Electricity and NG consumption** (MMBtu) from SLOPE or utility data
- **AEO electricity market region** (which of the 11 regions the city falls in)
- **State** (for AFDC vehicle registration share lookup)
- **FHWA VMT** (from HM-71 tables, scaled to city proper population)
- **Inventory/EIE totals** (optional, for validation)

### Step 2: Create the City CSV

Create a new file `data/inputs/cities/<city_name>.csv` following the existing format. Use an existing city as a template:

```bash
# Copy a template
cp data/inputs/cities/atlanta.csv data/inputs/cities/new_city.csv
# Edit with your city's data
```

The file must have one row with all the columns listed in the City CSV Columns table above.

### Step 3: Add to Config Maps

Edit `iam/config.py` and add entries to both maps:

```python
# In CITY_REGION_MAP — maps city to its AEO electricity market region
CITY_REGION_MAP: dict = {
    ...
    "New City": "SRSE",   # <-- add your city and its region
}

# In CITY_STATE_MAP — maps city to its state (for AFDC lookups)
CITY_STATE_MAP: dict = {
    ...
    "New City": "Georgia",  # <-- add your city and its state
}
```

The `CITIES` list is auto-generated from `CITY_REGION_MAP`, so no separate update is needed.

### Step 4: Add Buildings Emissions Data

Add rows for your city to these files (one row per year from 2027-2050):

- `data/inputs/buildings_total_emissions.csv` -- columns: `city`, `year`, `total_emissions_mt_co2e`
- `data/inputs/electricity/electricity_emissions.csv` -- columns: `city`, `year`, `electricity_emissions_mt_co2`
- `data/inputs/ng/ng_emissions.csv` -- columns: `city`, `year`, `ng_emissions_mt_co2e`
- `data/inputs/ng/ng_residential_consumption.csv` -- columns: `city`, `year`, `ng_residential_mmbtu`
- `data/inputs/ng/ng_commercial_consumption.csv` -- columns: `city`, `year`, `ng_commercial_mmbtu`

### Step 5: Add FHWA VMT Data

Add a row for your city to `data/inputs/fhwa_vmt.csv`:

```
city,census_population,total_daily_vmt_thousands,city_proper_population,scalar,total_annual_vmt
New City,500000,12000,200000,0.4,1752000
```

The `scalar` is `city_proper_population / census_population` and `total_annual_vmt` is `total_daily_vmt_thousands * scalar * 365`.

### Step 6: Verify

```bash
# Confirm the city loads and runs
python scripts/run_model.py --cities "new city"

# Run tests to make sure nothing else broke
pytest tests/ -v
```

### Step 7: Add AFDC Data (if needed)

If the city is in a state not already in `data/inputs/afdc_vehicle_shares.csv`, add a row for that state with vehicle registration fractions by fuel type. All existing states are already covered.

---

