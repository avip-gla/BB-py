# CLAUDE.md — baseline-builder-py Project Guide

## Project Overview

**baseline-builder-py** is a Python/conda refactor of an Excel-based Integrated Assessment Model (IAM) that calculates **GHG emissions savings** in US cities across future years. Emissions reductions come from two sectors:
- **Buildings** (Residential & Commercial)
- **Transportation**

The model uses city-level and fixed national data, drawing from energy data sources including Annual Energy Outlook (AEO), and produces outputs suitable for plotting and comparison across cities.

---

## Conda Environment

- **Environment name:** `baseline-builder-py`
- **Python version:** 3.11 (recommended for scientific stack compatibility)
- **Create with:**
  ```bash
  conda create -n baseline-builder-py python=3.11
  conda activate baseline-builder-py
  pip install -r requirements.txt
  ```

### Core dependencies (`requirements.txt`)
```
pandas
numpy
openpyxl
matplotlib
scipy
pyyaml
pytest
```

---

## Project Structure

```
baseline-builder-py/
├── CLAUDE.md                  # This file (dev guide for Claude Code)
├── README.md                  # User-facing usage guide
├── environment.yml            # Conda environment spec
├── requirements.txt
├── data/
│   ├── raw/                   # Original Excel model and source data
│   │   └── IAM_model.xlsx
│   ├── inputs/                # City-specific and fixed input CSVs
│   │   ├── fixed_data.csv         # National/fixed parameters (all cities)
│   │   ├── fhwa_vmt.csv          # FHWA VMT per city
│   │   ├── afdc_vehicle_shares.csv # State AFDC registration shares
│   │   ├── emission_factors.csv   # EPA emission factors
│   │   ├── cities/                # Per-city parameter CSVs
│   │   ├── electricity/           # Electricity consumption/emissions
│   │   └── ng/                    # Natural gas consumption/emissions
│   └── aeo/                   # Annual Energy Outlook tables
│       ├── aeo_carbon_intensity.csv   # Regional grid CI (MT CO2/MWh)
│       ├── aeo_mpg.csv               # Vehicle MPG with vehicle_class column
│       ├── aeo_freight_efficiency.csv # Freight MPG by weight class
│       └── aeo_ldv_sales_shares.csv   # Car/truck LDV sales fractions
├── docs/
│   └── transport_refactoring.md  # Comprehensive transport refactoring document
├── outputs/                   # GHG results as CSV and Excel
│   ├── csv/
│   └── xlsx/
├── iam/                       # Main Python package
│   ├── __init__.py
│   ├── config.py              # Global constants and configuration
│   ├── data_loader.py         # Load fixed, city, AEO data
│   ├── buildings.py           # Buildings emissions module
│   ├── transport.py           # Transportation emissions module (v3 — current)
│   ├── findings.py            # Top-level GHG aggregation (mirrors Findings tab)
│   ├── emissions.py           # Shared emissions calculation logic
│   ├── city.py                # City class: holds all city-level data and runs calcs
│   ├── output.py              # CSV and Excel export utilities
│   └── versions/              # Versioned copies of refactored modules
│       ├── transport_v2.py / transport_v3.py
│       ├── city_v2.py / city_v3.py
│       ├── config_v2.py / config_v3.py
│       └── data_loader_v2.py / data_loader_v3.py
├── scripts/
│   ├── run_model.py           # CLI entry point: run for one or many cities
│   ├── compare_versions.py    # Compare v1/v2/v3 transport emissions
│   ├── compare_transport.py   # Compare v1 (Excel) vs current transport
│   ├── compare_cities.py      # Compare emissions across cities
│   ├── build_transport_tab.py # Generate "Transport (City-Specific)" Excel tab
│   └── build_transport_tabs.py # Generate v2 and v3 Excel tabs
├── tests/
│   └── test_findings.py       # 21 tests: emission factors, buildings, transport, v1/v2 versions
└── IAM_model.xlsx             # Excel workbook with generated tabs
```

---

## Excel Model Mapping

| Excel Tab       | Python Module / File         | Role |
|----------------|------------------------------|------|
| `Findings`      | `iam/findings.py`            | Top-level GHG savings aggregation by city and year |
| `Buildings`     | `iam/buildings.py`           | Residential & commercial building emissions lookups and calcs |
| `Transport`     | `iam/transport.py`           | Transportation sector emissions lookups and calcs (v3 — current) |
| `Transport (v2)`| `scripts/build_transport_tabs.py` | Generated tab: city-specific with v2 approximations |
| `Transport (v3)`| `scripts/build_transport_tabs.py` | Generated tab: MPG split with v3 corrections |
| `Electricity`   | `data/inputs/electricity/`   | City-level electricity usage data |
| `NG`            | `data/inputs/ng/`            | City-level natural gas usage data |
| `AEO`           | `data/aeo/`                  | Annual Energy Outlook tables and projections |

---

## Architecture & Design Principles

### 1. City Class (core abstraction)
Each city is represented as a `City` object that holds both fixed and localized data, and exposes methods to calculate sector-level emissions.

```python
# iam/city.py
class City:
    def __init__(self, name: str, fixed_data: dict, city_data: dict):
        self.name = name
        self.fixed = fixed_data      # shared national parameters
        self.local = city_data       # city-specific parameters

    def buildings_emissions_saved(self, year: int) -> float:
        """Calculate GHG savings from buildings sector for a given year."""
        ...

    def transport_emissions_saved(self, year: int) -> float:
        """Calculate GHG savings from transportation sector for a given year."""
        ...

    def total_emissions_saved(self, year: int) -> float:
        """Aggregate total GHG savings across all sectors."""
        return self.buildings_emissions_saved(year) + self.transport_emissions_saved(year)
```

### 2. Sector Modules (Buildings & Transport)
Each sector module contains the calculation logic extracted from the Excel model. Logic should be:
- **Clearly documented** with docstrings explaining what the formula does and its Excel origin
- **Parameterized** so the calculation approach can be swapped without changing the City class
- **Pure functions where possible** — take inputs, return outputs, no hidden state

```python
# iam/buildings.py
def calculate_residential_savings(city_data: dict, fixed_data: dict, aeo: dict, year: int) -> float:
    """
    Calculate GHG savings from residential buildings for a given city and year.
    
    Logic source: Excel 'Buildings' tab, rows 12-45.
    Formula: [describe the formula here once extracted from Excel]
    
    Args:
        city_data: Localized building stock and energy data for the city.
        fixed_data: National emission factors and efficiency parameters.
        aeo: AEO projections for the target year.
        year: Target future year for projection.
    
    Returns:
        GHG savings in metric tons CO2e.
    """
    ...
```

### 3. Calculation Logic is Swappable
All core calculation functions should be imported into `findings.py` via a **strategy pattern** or simple function references. This means you can swap calculation logic by changing one import or parameter — without touching the City class or output layer.

```python
# findings.py example
from iam.buildings import calculate_residential_savings   # swap this line to change logic
```

### 4. Data Loader
Separates data loading from calculation logic. Supports loading:
- Fixed/national data (shared across all cities)
- Individual city data (from CSV or Excel)
- AEO tables

```python
# iam/data_loader.py
def load_fixed_data(path: str) -> dict: ...
def load_city_data(city_name: str, data_dir: str) -> dict: ...
def load_aeo(path: str) -> dict: ...
```

### 5. Output Layer
All output formatting lives in `iam/output.py`. Supports:
- Single city CSV export
- Multi-city comparison CSV (cities as columns or rows)
- Excel `.xlsx` export with formatted sheets
- Data structures ready for `matplotlib` plotting

---

## Running the Model

### Single city
```bash
python scripts/run_model.py --cities Atlanta
```

### Multiple cities (comparison)
```bash
python scripts/run_model.py --cities Atlanta Charlotte Nashville --output csv
```

### Output to Excel
```bash
python scripts/run_model.py --cities Atlanta Charlotte --output xlsx
```

### All 25 cities with summary
```bash
python scripts/run_model.py --all --summary --output both
```

---

## Comparing Versions

The transport module has 3 versions: v1 (Excel), v2 (city-specific), v3 (MPG split).
See `docs/transport_refactoring.md` for full details.

### 3-version comparison (v1 vs v2 vs v3)
```bash
python scripts/compare_versions.py                                 # Summary for 2027/2036/2050
python scripts/compare_versions.py --detail Atlanta                # + fuel-type breakdown
python scripts/compare_versions.py --detail Atlanta --notes        # + version differences
python scripts/compare_versions.py --years 2027 2030 2040 2050     # Custom years
python scripts/compare_versions.py --output outputs/csv/version_comparison.csv  # Export CSV
```

### v1 (Excel) vs current transport
```bash
python scripts/compare_transport.py                                # Terminal summary
python scripts/compare_transport.py --output outputs/csv/transport_comparison.csv
python scripts/compare_transport.py --cities Atlanta Charlotte     # Specific cities
```

### Cross-city comparison
```bash
python scripts/compare_cities.py --all                             # All 25 cities
python scripts/compare_cities.py --all --top 10                    # Top 10 by savings
python scripts/compare_cities.py --cities Atlanta Charlotte Nashville --plot
```

---

## Generating Excel Tabs

### v2 and v3 transport tabs
```bash
python scripts/build_transport_tabs.py
```
Adds two tabs to `IAM_model.xlsx`:
- **"Transport (v2 — City-Specific)"** — hardcoded 0.42/0.58 fractions, same car/truck MPG
- **"Transport (v3 — MPG Split)"** — dynamic fractions, separate car/truck MPG

Each tab includes: documentation header, city parameters, total emissions (25 cities × 24 years), emissions by fuel type, fuel consumption, VMT by fuel type.

### Single transport tab (current version)
```bash
python scripts/build_transport_tab.py
```

---

## Testing

### Run all tests
```bash
pytest tests/test_findings.py -v
```

21 tests covering:
- Emission factor constants (NG, MWh/MMBtu conversions)
- Buildings emissions (electricity, NG) for specific cities/years
- Transport emissions (Atlanta 2027, car/truck MPG split validation)
- SPPC carbon intensity (direct lookup, no fallback)
- All 25 cities load successfully
- v1/v2 transport version validation (reference values, hardcoded fractions, SPPC fallback, cross-version deltas)

---

## Versioned Transport Modules

Versioned copies of the 4 core transport modules are in `iam/versions/`:

| Version | Commit | Key characteristics |
|---------|--------|---------------------|
| v2 | `0ddac27` | City-specific VMT/fuel/CI; hardcoded 0.42/0.58 car/truck; same MPG; SPPC→MISC |
| v3 | working tree | Dynamic car/truck fractions; separate MPG; SPPC direct; freight fix |

To revert to v2 for testing:
```bash
cp iam/versions/transport_v2.py iam/transport.py
cp iam/versions/city_v2.py iam/city.py
cp iam/versions/config_v2.py iam/config.py
cp iam/versions/data_loader_v2.py iam/data_loader.py
```

---

## Documentation

| Document | Purpose |
|----------|---------|
| `CLAUDE.md` | Developer guide for Claude Code (this file) |
| `README.md` | User-facing usage guide |
| `docs/transport_refactoring.md` | Comprehensive transport refactoring document (client-readable) |
| Excel v2/v3 tabs | In-workbook documentation with data and change lists |

---

## Coding Standards

- **Type hints** on all function signatures
- **Docstrings** on every function — include the Excel tab/row reference where the logic originates
- **No hardcoded values** inside functions — all constants go in `iam/config.py`
- **pandas DataFrames** for tabular data (city energy usage, AEO projections)
- **dicts** for city parameters and fixed data
- **numpy** for any matrix or vectorized numerical operations
- File names and functions use `snake_case`; classes use `PascalCase`

---

## Documentation Requirements

When Claude builds or refactors a calculation function, it must:
1. Reference the **source Excel tab and approximate row/column** in the docstring
2. Write out the **calculation logic in plain English** before the code
3. Note any **assumptions or approximations** made during the Excel → Python translation
4. Flag any Excel features (e.g. VLOOKUP, iterative calculations) with a comment explaining how they were handled

---

## Key Data Concepts

- **Fixed data:** National emission factors, efficiency standards, technology adoption curves — same for all cities
- **Localized data:** City-specific building stock, vehicle fleet, utility mix, climate zone
- **AEO data:** Year-by-year energy projections used to scale future emissions
- **GHG savings:** Calculated as the **delta** between a baseline scenario and an improved scenario, expressed in metric tons CO2e per year

---

## Output Format

All outputs should include:
- `city` — city name
- `year` — projection year
- `buildings_savings_mtco2e` — GHG savings from buildings (MT CO2e)
- `transport_savings_mtco2e` — GHG savings from transportation (MT CO2e)
- `total_savings_mtco2e` — total GHG savings
- Any intermediate values useful for debugging or plotting

---

## Notes for Claude Code

- Always read this file at the start of a session before writing any code
- When translating Excel formulas, show the original formula logic in a comment before the Python implementation
- Prefer creating new modules over adding to existing ones if a new calculation domain emerges
- When in doubt about Excel → Python translation fidelity, add a `# TODO: verify against Excel` comment
- Do not add dependencies beyond those in `requirements.txt` without asking first
