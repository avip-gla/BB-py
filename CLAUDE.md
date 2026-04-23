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
│   │   ├── afdc_vehicle_shares.csv # State AFDC registration shares (2023 & 2024, normalized)
│   │   ├── afdc_growth_deltas.csv # AFDC share deltas (2024 − 2023) by state
│   │   ├── emission_factors.csv   # EPA emission factors
│   │   ├── cities/                # Per-city parameter CSVs
│   │   ├── electricity/           # Electricity consumption/emissions
│   │   └── ng/                    # Natural gas consumption/emissions
│   └── aeo/                   # Annual Energy Outlook tables
│       ├── aeo_carbon_intensity.csv   # Regional grid CI (MT CO2/MWh)
│       ├── aeo_mpg.csv               # Vehicle MPG with vehicle_class column
│       ├── aeo_freight_efficiency.csv # Freight MPG by weight class and fuel type
│       └── aeo_ldv_sales_shares.csv   # Car/truck LDV sales fractions by census division
├── docs/
│   └── transport_refactoring.md  # Comprehensive transport refactoring document
├── outputs/                   # GHG results as CSV and Excel
│   ├── csv/
│   └── xlsx/
├── bau/                       # Main Python package
│   ├── __init__.py
│   ├── config.py              # Global constants, city mappings, VMT growth rate
│   ├── data_loader.py         # Load fixed, city, AEO, AFDC data
│   ├── buildings.py           # Buildings emissions module
│   ├── transport.py           # Transportation emissions module
│   ├── findings.py            # Top-level GHG aggregation (mirrors Findings tab)
│   ├── emissions.py           # Shared emissions calculation logic
│   ├── city.py                # City class: holds all city-level data and runs calcs
│   ├── output.py              # CSV and Excel export utilities
│   └── versions/              # Snapshot copies for audit trail (pre-AFDC/biodiesel refactor)
│       ├── transport_v3.py    # v3: car/truck MPG split, before flat VMT growth + AFDC shares
│       ├── city_v3.py
│       ├── config_v3.py
│       └── data_loader_v3.py
├── scripts/
│   ├── run_model.py           # CLI entry point: run for one or many cities
│   ├── compare_versions.py    # Compare Excel vs Python transport emissions
│   ├── compare_transport.py   # Compare Excel vs current transport
│   ├── compare_cities.py      # Compare emissions across cities
│   ├── build_transport_tab.py # Generate "Transport (City-Specific)" Excel tab
│   └── build_transport_tabs.py # Generate transport Excel tab
├── tests/
│   └── test_findings.py       # Emission factors, buildings, transport integration tests
└── IAM_model.xlsx             # Excel workbook with generated tabs
```

---

## Excel Model Mapping

| Excel Tab       | Python Module / File         | Role |
|----------------|------------------------------|------|
| `Findings`      | `bau/findings.py`            | Top-level GHG savings aggregation by city and year |
| `Buildings`     | `bau/buildings.py`           | Residential & commercial building emissions lookups and calcs |
| `Transport`     | `bau/transport.py`           | Transportation sector emissions lookups and calcs |
| `Transport (City-Specific)` | `scripts/build_transport_tabs.py` | Generated tab: city-specific transport emissions |
| `Electricity`   | `data/inputs/electricity/`   | City-level electricity usage data |
| `NG`            | `data/inputs/ng/`            | City-level natural gas usage data |
| `AEO`           | `data/aeo/`                  | Annual Energy Outlook tables and projections |

---

## Architecture & Design Principles

### 1. City Class (core abstraction)
Each city is represented as a `City` object that holds both fixed and localized data, and exposes methods to calculate sector-level emissions.

```python
# bau/city.py
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
# bau/buildings.py
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
from bau.buildings import calculate_residential_savings   # swap this line to change logic
```

### 4. Data Loader
Separates data loading from calculation logic. Supports loading:
- Fixed/national data (shared across all cities)
- Individual city data (from CSV or Excel)
- AEO tables

```python
# bau/data_loader.py
def load_fixed_data(path: str) -> dict: ...
def load_city_data(city_name: str, data_dir: str) -> dict: ...
def load_aeo(path: str) -> dict: ...
```

### 5. Output Layer
All output formatting lives in `bau/output.py`. Supports:
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

See `docs/transport_refactoring.md` for full details on Excel-to-Python translation.

### Excel vs Python comparison
```bash
python scripts/compare_versions.py                                 # Summary for 2027/2036/2050
python scripts/compare_versions.py --detail Atlanta                # + fuel-type breakdown
python scripts/compare_versions.py --detail Atlanta --notes        # + difference notes
python scripts/compare_versions.py --years 2027 2030 2040 2050     # Custom years
python scripts/compare_versions.py --output outputs/csv/version_comparison.csv  # Export CSV
```

### Alternate comparison script
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

## Generating Excel Tab

```bash
python scripts/build_transport_tabs.py
```
Adds "Transport (City-Specific)" tab to `IAM_model.xlsx` with: documentation header, city parameters, total emissions (25 cities × 24 years), emissions by fuel type, fuel consumption, VMT by fuel type, Python module documentation.

### Alternate single-tab script
```bash
python scripts/build_transport_tab.py
```

---

## Testing

### Run all tests
```bash
pytest tests/test_findings.py -v
```

17 tests covering:
- Emission factor constants (NG, MWh/MMBtu conversions)
- Buildings emissions (electricity, NG) for specific cities/years
- Transport emissions (Atlanta 2027, car/truck MPG split validation)
- VMT projection (flat 0.6% growth, AFDC share evolution, biodiesel in diesel bucket)
- SPPC carbon intensity (direct lookup, no fallback)
- All 25 cities load successfully

---

## Documentation

| Document | Purpose |
|----------|---------|
| `CLAUDE.md` | Developer guide for Claude Code (this file) |
| `README.md` | User-facing usage guide |
| `docs/transport_refactoring.md` | Transport refactoring document (client-readable) |
| Excel transport tab | In-workbook documentation with data and change lists |

---

## Coding Standards

- **Type hints** on all function signatures
- **Docstrings** on every function — include the Excel tab/row reference where the logic originates
- **No hardcoded values** inside functions — all constants go in `bau/config.py`
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
