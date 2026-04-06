# baseline-builder-py

A Python model for calculating GHG emissions baselines and savings across 25 US cities, covering the **Buildings** and **Transportation** sectors from 2027 to 2050.

This is a Python refactor of an Excel-based Integrated Assessment Model (IAM). The Python version adds city-specific transport calculations validated against the original Excel formulas, and includes two supplementary policy modules (BPS and BRESE).

For setup, installation, and usage instructions see **[USAGE_GUIDE.md](USAGE_GUIDE.md)**.

---

## What This Model Does

For each city, the model calculates annual GHG emissions and savings across two sectors:

**Buildings** — Emissions from electricity and natural gas consumption in residential and commercial buildings. Electricity emissions use AEO regional carbon intensity projections (declining over time as the grid decarbonizes). Natural gas emissions use a fixed EPA emission factor.

**Transportation** — Emissions from on-road vehicle travel. The model starts from each city's total VMT (from FHWA), grows it at a flat 0.6%/year national rate, allocates VMT across seven fuel types (gasoline, diesel, ethanol, EV, plug-in hybrid, hybrid, biodiesel) using AFDC state vehicle registration shares, converts VMT to fuel consumption using AEO MPG projections, and converts fuel to CO₂ using EPA emission factors and regional carbon intensity for electric vehicles.

**Savings** — Computed as the difference between each year's emissions and the 2027 baseline, by sector and in total.

---

## Repository Contents

```
baseline-builder-py/
├── iam/          # Core IAM model (buildings + transport calculations)
├── bps/          # Building Performance Standards policy module
├── brese/        # Building Energy Code Savings (DOE BRESE) module
├── scripts/      # Command-line tools: run, compare, plot
├── tests/        # Test suite (17 tests)
├── data/
│   ├── inputs/   # City CSVs, FHWA VMT, AFDC shares, emission factors
│   └── aeo/      # Annual Energy Outlook tables (MPG, carbon intensity, LDV sales)
└── docs/         # Supplementary technical documentation
```

---

## Module Overview

### `iam/` — Core IAM Model

The main calculation package. Each module has a single responsibility:

| Module | Role |
|--------|------|
| `city.py` | The `City` class — the top-level entry point. Orchestrates all calculations for a given city across projection years and produces the output DataFrame. |
| `buildings.py` | Buildings sector: converts electricity and NG consumption (MMBtu) to MT CO₂e. Mirrors the Excel "Buildings" tab. |
| `transport.py` | Transportation sector: four-step pipeline from VMT allocation → VMT projection → fuel consumption → MT CO₂. Mirrors the Excel "Transport" tab. |
| `findings.py` | Aggregation: combines buildings + transport into city-level totals. Mirrors the Excel "Findings" tab. |
| `emissions.py` | Shared unit conversion helpers (MMBtu → MWh, MWh → MT CO₂, gallons → MT CO₂). |
| `data_loader.py` | Loads all input CSVs and AEO tables. Provides lookup helpers for carbon intensity, MPG, and LDV sales shares. |
| `config.py` | All constants and city mappings: emission factors, VMT growth rate, LDV/HDV shares, AEO region assignments, projection year range. |
| `output.py` | CSV and Excel export. |
| `versions/` | Snapshot of modules before the AFDC/biodiesel refactor, kept for audit trail. |

**Calculation flow:**

```
City.run_all_years()
  ├── buildings_emissions(year)
  │     ├── Electricity: MMBtu × 0.3 → MWh × regional CI → MT CO₂
  │     └── Natural Gas: MMBtu × 0.05306 → MT CO₂e
  └── transport_emissions(year)
        ├── FHWA VMT × (1.006)^(year−2024) → projected total VMT
        ├── total VMT × AFDC fuel share → VMT by fuel type
        ├── VMT / AEO MPG (car/truck + freight) → fuel consumption
        └── fuel consumption × EPA emission factor → MT CO₂
```

---

### `bps/` — Building Performance Standards

Calculates GHG savings from building performance standard policies. Supports two policy types modeled from real city programs:

- **Retrocommissioning** (Philadelphia BEPP): staggered efficiency bins with a two-cycle renewal. Buildings in each bin achieve a savings rate in their first cycle, then again at renewal. Savings compound across cycles.
- **Benchmarking** (Kansas City Energy Empowerment Ordinance): year-over-year consumption reduction from a single policy bin with no renewal. Carbon intensity uses the prior year's value.

| Module | Role |
|--------|------|
| `config.py` | BPS constants and policy parameters. |
| `data_loader.py` | Loads city building stock areas, baseline consumption, and AEO carbon intensity. |
| `calculator.py` | Core logic for both policy types: baselines → reductions → annual energy and GHG savings by bin. |

---

### `brese/` — Building Energy Code Savings

Implements the DOE Building Energy Code Emissions Calculator logic, estimating GHG and cost savings from building energy code adoption (IECC 2024 / ASHRAE 90.1-2025) across 11 SEEA states. All states modeled adopt the new code in 2026; projections run through 2040.

| Module | Role |
|--------|------|
| `config.py` | BRESE constants: discount rate (5%), compliance rate (75%), NPV horizon, eGrid vintage, GWP values. |
| `data_loader.py` | Loads pre-computed cost-benefit, electricity avoided, and NG avoided CSVs from the DOE calculator. |
| `calculator_logic.py` | Documents the full DOE SEEA calculation chain, verified across all 11 states (SC, NC, GA, AL, FL, VA, LA, KY, TN, AR, MS). |

---

### `scripts/` — Command-Line Tools

| Script | What it does |
|--------|-------------|
| `run_model.py` | Run the IAM for one city, a subset, or all 25. |
| `run_bps.py` | Run the BPS module for Philadelphia or Kansas City. |
| `compare_versions.py` | Compare Excel vs. Python transport emissions across cities and years. |
| `compare_transport.py` | Alternate Excel vs. Python transport comparison. |
| `compare_cities.py` | Side-by-side emissions, savings rankings, and trajectories across cities. |
| `build_transport_tabs.py` | Generate a "Transport (City-Specific)" Excel tab for all 25 cities. |
| `plot_5city_forecast.py` | 3-panel figure: emissions decline, grid CI decline, sector contribution (2027–2035). |
| `plot_5city_forecast_normalized.py` | Normalized version of the 5-city forecast. |
| `plot_transport_fuel_mix.py` | Fuel mix trend over time and per-city comparison (2027 vs. 2050). |
| `plot_brese_takeaways.py` | BRESE key takeaways across SEEA states. |
| `plot_brese_energy_avoided.py` | BRESE electricity and NG avoided by state. |

---

## Further Reading

| Document | Description |
|----------|-------------|
| `USAGE_GUIDE.md` | Setup, running the model, output format, data inputs, customization, adding a new city |
| `docs/transport_refactoring.md` | Full Excel-to-Python translation: formula chain, data files, validation, change log |
