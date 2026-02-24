# IAM-py

Python/conda refactor of an Excel-based Integrated Assessment Model (IAM) that calculates GHG emissions savings for 25 US cities across projection years 2027-2050. Covers two sectors: **Buildings** (residential and commercial) and **Transportation**.

## Setup

```bash
conda create -n IAM-py python=3.11
conda activate IAM-py
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

### Compare Transport Versions (v1 / v2 / v3)

The transport module has been refactored twice from the original Excel model. All 3 versions can be compared side-by-side:

- **v1 (Excel):** Single reference city (Atlanta) applied to all 25 cities.
- **v2 (City-Specific):** City-specific VMT, state fuel mix, regional carbon intensity. Hardcoded 0.42/0.58 car/truck fractions, same MPG for both.
- **v3 (MPG Split):** Dynamic car/truck fractions from AEO LDV sales shares, separate car/truck MPG, SPPC carbon intensity, freight efficiency fix.

```bash
# 3-version comparison table (v1 vs v2 vs v3) for all 25 cities
python scripts/compare_versions.py

# With fuel-type breakdown for a specific city
python scripts/compare_versions.py --detail Atlanta

# With version difference notes
python scripts/compare_versions.py --detail Atlanta --notes

# Custom summary years
python scripts/compare_versions.py --years 2027 2030 2040 2050

# Export full comparison to CSV (25 cities x 24 years, fuel-type detail)
python scripts/compare_versions.py --output outputs/csv/version_comparison.csv
```

### Compare v1 (Excel) vs Current

```bash
# Reference city (old) vs city-specific (current)
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

### Generate Excel Tabs

```bash
# Add v2 and v3 transport tabs to IAM_model.xlsx
python scripts/build_transport_tabs.py

# Add single "Transport (City-Specific)" tab (current version)
python scripts/build_transport_tab.py
```

The v2/v3 tabs include:
- Documentation header with version description and change list
- City input parameters (state, region, FHWA VMT, CI region)
- Total transport emissions by city (25 cities x 24 years)
- Emissions by fuel type per city (gasoline, diesel, ethanol, electricity)
- Fuel consumption per city
- VMT by fuel type per city
- Python module documentation (v3 tab only)

## Testing

```bash
# Run all 14 tests
pytest tests/test_findings.py -v
```

Tests cover:
- Emission factor constants (NG, MWh/MMBtu conversions)
- Buildings emissions (electricity for Akron 2027, Atlanta 2027/2050, savings)
- Transport emissions (Atlanta 2027, car/truck MPG split validation)
- SPPC carbon intensity (Kansas City uses SPPC directly, no fallback)
- All 25 cities load and run successfully

## Documentation

| Document | Audience | Description |
|----------|----------|-------------|
| [Transport Refactoring](docs/transport_refactoring.md) | Client / technical | Full story: v1 -> v2 -> v3, formula mappings, validation, data files |
| [CLAUDE.md](CLAUDE.md) | Developer (Claude Code) | Architecture, coding standards, project structure |
| Excel v2/v3 tabs | Client | In-workbook documentation with data and in-tab change lists |

### Transport Refactoring Document

`docs/transport_refactoring.md` covers:
1. Executive Summary
2. Version Comparison Table (v1/v2/v3 feature matrix)
3. v1: Original Excel Model (formula chain, limitations)
4. v2: City-Specific Refactor (changes, data files, numerical impact)
5. v3: MPG Split & Data Corrections (6 changes, Excel bug, numerical impact)
6. Python Module Reference (transport.py, city.py, config.py, data_loader.py)
7. Data Files Reference (7 CSVs with sources)
8. Excel Formula to Python Mapping (20+ formulas)
9. Validation Results (Atlanta 2027 across all versions, Excel bug explanation)
10. Versioned Files (where to find v2/v3 copies, how to switch)

## Versioned Transport Modules

Versioned copies of the 4 core modules are in `iam/versions/`:

| File | Version | Source |
|------|---------|--------|
| `transport_v2.py` | v2 | Git commit `0ddac27` |
| `transport_v3.py` | v3 | Current working tree |
| `city_v2.py` / `city_v3.py` | v2 / v3 | Same |
| `config_v2.py` / `config_v3.py` | v2 / v3 | Same |
| `data_loader_v2.py` / `data_loader_v3.py` | v2 / v3 | Same |

To revert to v2 for testing:
```bash
cp iam/versions/transport_v2.py iam/transport.py
cp iam/versions/city_v2.py iam/city.py
cp iam/versions/config_v2.py iam/config.py
cp iam/versions/data_loader_v2.py iam/data_loader.py
```

## Validation Reference

Atlanta 2027 transport emissions across all 3 versions:

| Version | MT CO2 | vs Excel |
|---------|--------|----------|
| v1 (Excel) | 1,603,108 | -- |
| v2 (Python) | 1,475,530 | -8.0% |
| v3 (Python) | 1,626,675 | +1.5% |

The 1.5% v3-vs-Excel difference (23,567 MT CO2) is fully explained by a confirmed Excel bug: Transport R21 references diesel VMT (E46) instead of flex VMT (E47) for car flex-fuel consumption.

## Project Structure

```
IAM-py/
├── iam/                       # Main Python package
│   ├── config.py              # Constants, city mappings, growth rates
│   ├── data_loader.py         # CSV loading and lookups
│   ├── transport.py           # Transport emissions (v3 — current)
│   ├── buildings.py           # Buildings emissions
│   ├── city.py                # City class orchestrating all calculations
│   ├── findings.py            # Top-level GHG aggregation
│   ├── emissions.py           # Shared emissions logic
│   ├── output.py              # CSV/Excel export
│   └── versions/              # v2 and v3 module snapshots
├── scripts/                   # CLI tools
│   ├── run_model.py           # Run model for cities
│   ├── compare_versions.py    # Compare v1/v2/v3 transport
│   ├── compare_transport.py   # Compare v1 vs current
│   ├── compare_cities.py      # Compare across cities
│   ├── build_transport_tab.py # Generate single Excel tab
│   └── build_transport_tabs.py # Generate v2 + v3 Excel tabs
├── tests/
│   └── test_findings.py       # 14 tests
├── data/                      # Input data (CSVs extracted from Excel)
├── docs/                      # Documentation
├── outputs/                   # Generated CSV/Excel outputs
└── IAM_model.xlsx             # Excel workbook with generated tabs
```
