
# baseline-builder-py

Python/conda refactor of an Excel-based Integrated Assessment Model (IAM) that calculates GHG emissions savings for 25 US cities across projection years 2027-2050. Covers two sectors: **Buildings** (residential and commercial) and **Transportation**.

## Setup

```bash
conda create -n baseline-builder-py python=3.11
conda activate baseline-builder-py
pip install -r requirements.txt
```

## Quick Start

```bash
# Run the model for a single city
python scripts/run_model.py --cities Atlanta

# Run all 25 cities with summary output
python scripts/run_model.py --all --summary --output csv

# Export to Excel
python scripts/run_model.py --cities Atlanta Charlotte Nashville --output xlsx
```

## Scripts

### Run the Model

| Command | Description |
|---------|-------------|
| `python scripts/run_model.py --cities Atlanta` | Single city, CSV output |
| `python scripts/run_model.py --cities Atlanta Charlotte --output xlsx` | Multiple cities, Excel output |
| `python scripts/run_model.py --all --summary --output both` | All 25 cities, CSV + Excel, print trends |

### Compare Excel vs Python Transport

Compare the original Excel model transport emissions against the current Python implementation for all 25 cities:

```bash
# Excel vs Python comparison for all 25 cities
python scripts/compare_versions.py

# With fuel-type breakdown for a specific city
python scripts/compare_versions.py --detail Atlanta

# With notes explaining differences
python scripts/compare_versions.py --detail Atlanta --notes

# Custom summary years
python scripts/compare_versions.py --years 2027 2030 2040 2050

# Export full comparison to CSV (25 cities x 24 years)
python scripts/compare_versions.py --output outputs/csv/version_comparison.csv
```

```bash
# Alternate comparison script (Excel vs current)
python scripts/compare_transport.py

# With CSV export
python scripts/compare_transport.py --output outputs/csv/transport_comparison.csv

# Specific cities only
python scripts/compare_transport.py --cities Atlanta Charlotte
```

### Compare Cities

```bash
# All 25 cities — emissions summary, savings rankings, trajectory, sector breakdown
python scripts/compare_cities.py --all

# Top 10 by total savings
python scripts/compare_cities.py --all --top 10

# Specific cities with matplotlib plots
python scripts/compare_cities.py --cities Atlanta Charlotte Nashville Memphis --plot
```

### Generate Excel Tab

```bash
# Add "Transport (City-Specific)" tab to IAM_model.xlsx
python scripts/build_transport_tabs.py

# Alternate single-tab script
python scripts/build_transport_tab.py
```

The generated tab includes:
- Documentation header with change list
- City input parameters (state, region, FHWA VMT, CI region)
- Total transport emissions by city (25 cities x 24 years)
- Emissions by fuel type per city (gasoline, diesel, ethanol, electricity)
- Fuel consumption per city
- VMT by fuel type per city
- Python module documentation

## Testing

```bash
pytest tests/test_findings.py -v
```

17 tests cover:
- Emission factor constants (NG, MWh/MMBtu conversions)
- Buildings emissions (electricity for Akron 2027, Atlanta 2027/2050, savings)
- Transport emissions (Atlanta 2027, car/truck MPG split validation)
- VMT projection (flat 0.6% growth, AFDC share evolution, biodiesel in diesel bucket)
- SPPC carbon intensity (Kansas City uses SPPC directly, no fallback)
- All 25 cities load and run successfully

## Documentation

| Document | Audience | Description |
|----------|----------|-------------|
| [Transport Refactoring](docs/transport_refactoring.md) | Client / technical | Excel-to-Python translation, formula mappings, validation, data files |
| [CLAUDE.md](CLAUDE.md) | Developer (Claude Code) | Architecture, coding standards, project structure |
| Excel transport tab | Client | In-workbook documentation with data and change lists |

### Transport Refactoring Document

`docs/transport_refactoring.md` covers:
1. Executive Summary
2. Original Excel Model (formula chain, characteristics)
3. Python Implementation (improvements, data files, numerical impact)
4. Python Module Reference (transport.py, city.py, config.py, data_loader.py)
5. Data Files Reference (8 CSVs with sources)
6. Excel Formula to Python Mapping (20+ formulas)
7. Validation Results (multi-city validation, Excel bug explanation)
8. Change Log (Excel corrections, Python-side data fixes, intentional differences)

## Validation Reference

Atlanta 2027 transport emissions (after Excel R21 bug fix):

| Version | MT CO2 | vs Excel |
|---------|--------|----------|
| Excel | 1,829,547.14 | -- |
| Python | 1,829,547.14 | **0.000000%** |

Multi-city validation (2027–2050):

| City | Match | Notes |
|------|-------|-------|
| Atlanta (GA) | 0.000000% | South Atlantic region |
| Charlotte (NC) | 0.000000% | South Atlantic region |
| Nashville (TN) | 0.000000% | South Atlantic region |
| Cleveland (OH) | ~0.1% | Middle Atlantic — intentional dynamic region mapping |
| Philadelphia (PA) | ~0.1% | Middle Atlantic — intentional dynamic region mapping |

Non-South-Atlantic cities show ~0.1% difference because Python uses region-appropriate AEO car/truck LDV sales fractions, while Excel hardcodes South Atlantic for all cities. See `docs/transport_refactoring.md` Section 8 for details.

## GitHub Setup

### 1. Install Homebrew (macOS package manager)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow the on-screen instructions (requires sudo password). After installation, add Homebrew to your PATH if prompted.

### 2. Install GitHub CLI

```bash
brew install gh
```

### 3. Authenticate with GitHub

```bash
gh auth login
```

Select **GitHub.com**, **HTTPS**, and follow the browser-based login flow.

### 4. Create the repository and push

```bash
gh repo create baseline-builder-py --private --source=. --push
```

This creates a private repo on GitHub, sets it as the remote, and pushes the current branch.

To push subsequent commits:

```bash
git push
```

## Project Structure

```
baseline-builder-py/
├── iam/                       # Main Python package
│   ├── config.py              # Constants, city mappings, VMT growth rate
│   ├── data_loader.py         # CSV loading and lookups
│   ├── transport.py           # Transport emissions (flat VMT growth + AFDC shares)
│   ├── buildings.py           # Buildings emissions
│   ├── city.py                # City class orchestrating all calculations
│   ├── findings.py            # Top-level GHG aggregation
│   ├── emissions.py           # Shared emissions logic
│   ├── output.py              # CSV/Excel export
│   └── versions/              # Module snapshots for audit trail
├── scripts/                   # CLI tools
│   ├── run_model.py           # Run model for cities
│   ├── compare_versions.py    # Compare Excel vs Python transport
│   ├── compare_transport.py   # Compare Excel vs current
│   ├── compare_cities.py      # Compare across cities
│   ├── build_transport_tab.py # Generate single Excel tab
│   └── build_transport_tabs.py # Generate transport Excel tab
├── tests/
│   └── test_findings.py       # Integration tests
├── data/                      # Input data (CSVs extracted from Excel)
├── docs/                      # Documentation
├── outputs/                   # Generated CSV/Excel outputs
└── IAM_model.xlsx             # Excel workbook with generated tabs
```
