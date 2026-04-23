"""DOE Building Energy Code Savings Calculator: logic and assumptions.

Documents the full calculation chain used by the upstream DOE calculator
(Building-Energy-Code-Emissions-Calculator-seea.xlsm) to produce the
cost-benefit results in BRESE-cost-benefit-analysis.xlsx.

Source: DOE Building Energy Code Savings Calculator
Location: /Users/apurkayastha/GLA/projects/brese/SEEA/
The two .xlsm files are reused across states by changing state inputs.
All 11 SEEA states verified (2026-2040, res+com, electricity+NG):
  SC, NC, Georgia, AL, Florida, VA, LA, KY, TN, Arkansas, MS

All states propose adoption of IECC 2024 / ASHRAE 90.1-2025 in 2026.

Tab structure (16 tabs):
  Cover Page, Step 1 - Location, Step 2 - Building Growth,
  Step 3 - Code Updates, Step 4 - Results, Step 4 - Results 2,
  Assumptions, Version Control, Energy+Emissions Calculation,
  Cost Calculation, PNNL Energy Code Savings, Energy Price Projections,
  eGrid Emissions, Building Growth Projections, CSA-level Data,
  Input Validations
"""

# ============================================================
# Calculator Assumptions (from Assumptions tab)
# ============================================================

DISCOUNT_RATE = 0.05  # 5% interest rate for NPV
COMPLIANCE_RATE = 0.75  # 75% of new construction meets code
NPV_YEAR_RANGE = (2013, 2040)  # NPV horizon (savings start at adoption year)
EGRID_YEAR = 2018  # eGrid emission factors vintage (static, not declining)
GWP_STANDARD = "SAR"  # IPCC Second Assessment Report (default)
GWP_CH4 = 21  # CH4 global warming potential (SAR)
GWP_N2O = 310  # N2O global warming potential (SAR)

# ============================================================
# Residential code savings (% over previous code, from PNNL)
# ============================================================
# Source: Assumptions tab, rows 6-12; PNNL Energy Code Savings tab row 7
# Each code version saves X% over the prior version.
# Savings chain: IECC 2006 -> 2009 -> 2012 -> 2015 -> 2018 -> 2021 -> 2024
# The first two steps (2006→2009 and 2009→2012) use state-specific
# percentages from PNNL rather than the standard values below.

RESIDENTIAL_CODE_SAVINGS_PCT = {
    "IECC 2015 over IECC 2012": 0.009,
    "IECC 2018 over IECC 2015": 0.005,
    "IECC 2021 over IECC 2018": 0.079,
    "IECC 2024 over IECC 2021": 0.05,
    "IECC 2027 over IECC 2024": 0.05,
    "PassiveHouse over IECC 2006": 0.50,
}

# ============================================================
# Commercial code savings
# ============================================================
# Source: Assumptions tab rows 7-12, cols 9-10
# ASHRAE 90.1-2013 over 2007 = 8.7%, 2016 over 2013 = 13.9%
# Later versions use flat 5% incremental.

COMMERCIAL_CODE_SAVINGS_PCT = {
    "ASHRAE 2013 over ASHRAE 2007": 0.087,
    "ASHRAE 2016 over ASHRAE 2013": 0.139,
    "ASHRAE 2019 over ASHRAE 2016": 0.05,
    "ASHRAE 2022 over ASHRAE 2019": 0.05,
    "ASHRAE 2025 over ASHRAE 2022": 0.05,
    "PassiveHouse over ASHRAE 2010": 0.40,
}


# ============================================================
# FULL CALCULATION CHAIN
# ============================================================
#
# ┌─────────────────────────────────────────────────────────────┐
# │  STEP 1: Per-Unit Energy Use by Code Version               │
# │  (PNNL Energy Code Savings tab)                            │
# └─────────────────────────────────────────────────────────────┘
#
# Each state has per-unit energy consumption for each code generation,
# computed by chaining incremental savings:
#
#   kWh(code_N) = kWh(code_N-1) × (1 - savings_pct)
#
# RESIDENTIAL (per household):
#   - PNNL tab row 8 headers: IECC 2006, 2009, 2012, 2015, 2018, 2021, 2024, 2027
#   - Row 9+ has state-specific kWh values for each code version
#   - Example MS: IECC 2006=12,141 kWh → IECC 2024=7,271 kWh (40% reduction)
#   - Example FL: IECC 2006=11,475 kWh → IECC 2024=7,416 kWh (35% reduction)
#   - Savings per home = baseline_kWh - upgrade_kWh
#     For MS (current=IECC 2006): 12,141 - 7,271 = 4,870 kWh/home
#     For FL (current=IECC 2021): 7,806 - 7,416 = 390 kWh/home
#
# COMMERCIAL (per square foot):
#   - PNNL tab row 8 cols 14+: ASHRAE 90.1-2004, 2007, 2010, 2013, etc.
#   - Row 9+ has state-specific kWh/sqft values
#   - Example MS: ASHRAE 2004=17.11 kWh/sf → ASHRAE 2025=? kWh/sf
#   - Savings per sqft = baseline_kWh/sf - upgrade_kWh/sf
#
# Key insight: The savings magnitude depends on how many code generations
# the state is jumping. States with older current codes (e.g., MS at IECC
# 2006, SC at IECC 2009) get much larger per-unit savings than states
# already at recent codes (e.g., FL/VA at IECC 2021).
#
#
# ┌─────────────────────────────────────────────────────────────┐
# │  STEP 2: New Construction Projection                       │
# │  (Building Growth Projections tab)                         │
# └─────────────────────────────────────────────────────────────┘
#
# Source: PNNL state-level housing unit projections (default option).
# User can override with manual annual growth rates (row 11).
#
# RESIDENTIAL (row 9 = PNNL default, row 14 = state-level):
#   - New housing units per year, 2013-2040
#   - Example MS: ~14,700/yr in 2017, declining to ~13,200/yr by 2040
#   - Values vary by state: FL has ~195,000/yr, MS has ~14,700/yr
#
# COMMERCIAL (separate block below residential):
#   - New floor area in square feet per year
#   - Example MS: ~16.6M sqft/yr in 2017, growing to ~20.5M sqft/yr by 2040
#
# Only NEW CONSTRUCTION after the code adoption year is affected.
# Existing building stock is NOT retrofitted.
#
#
# ┌─────────────────────────────────────────────────────────────┐
# │  STEP 3: Statewide Energy Savings                          │
# │  (Energy+Emissions Calculation tab)                        │
# └─────────────────────────────────────────────────────────────┘
#
# The Energy+Emissions Calculation tab has two parallel blocks:
#   - Residential: cols C-AD (3-30), year headers at row 7
#   - Commercial: cols AH-BL (34-64), year headers at row 7
# IMPORTANT: Residential and commercial year columns are offset
# by 32 columns, NOT 31 — must match by year header, not fixed offset.
#
# RESIDENTIAL ELECTRICITY (rows 5-22):
#   Row 8-10:  Baseline code, compliance rate, kWh consumption per home
#   Row 12-15: Upgrade code, compliance rate, kWh consumption per home
#   Row 16-17: Savings per home = baseline kWh - upgrade kWh
#   Row 19-20: Building projection (new homes/yr from Step 2)
#   Row 21:    Annual MWh Savings = new_homes × kWh_savings × compliance / 1000
#   Row 22:    Cumulative MWh Savings = running sum of row 21
#
# RESIDENTIAL GAS/OIL (rows 43-60):
#   Same structure but for MMBtu:
#   Row 46-49: Baseline code, compliance, MMBtu per home
#   Row 50-53: Upgrade code, compliance, MMBtu per home
#   Row 54-55: Savings per home (MMBtu)
#   Row 58:    Building projection
#   Row 59:    Annual MMBtu Savings
#   Row 60:    Cumulative MMBtu Savings
#
# COMMERCIAL (cols 34+): Same row layout, but:
#   - Energy use is per square foot (kWh/sf, MMBtu/sf)
#   - Building projection is in square feet
#   - Savings = new_sqft × savings_per_sf × compliance / 1000
#
# Savings are zero for all years before the code adoption date (2026).
#
#
# ┌─────────────────────────────────────────────────────────────┐
# │  STEP 4: Emissions Avoided                                 │
# │  (Energy+Emissions Calculation tab, rows 24-41 & 62-69)    │
# └─────────────────────────────────────────────────────────────┘
#
# ELECTRICITY EMISSIONS (rows 24-41):
#   Uses eGrid STATE-LEVEL emission factors (2018 vintage, static).
#   These do NOT decline over time (unlike AEO regional CI used in the
#   IAM baseline builder module).
#
#   eGrid factors per state (eGrid Emissions tab, row 9):
#     NOx (lb/MWh), SOx (lb/MWh), CH4 (lb/GWh), N2O (lb/GWh),
#     CO2 (lb/MWh), CO2e (lb/MWh)
#
#   Example eGrid factors by state:
#     MS:  CO2=1,057.5 lb/MWh, NOx=0.645, SOx=0.112, CH4=38 lb/GWh
#     FL:  CO2=  918.0 lb/MWh  (cleaner grid than MS)
#     KY:  CO2=1,971.0 lb/MWh  (coal-heavy, highest among SEEA states)
#     VA:  CO2=  790.8 lb/MWh  (relatively clean)
#
#   Row 27: Annual MWh savings (= row 21)
#   Row 28-33: Metric tons per year of NOx, SOx, CH4, N2O, CO2, CO2e
#   Row 35: Cumulative MWh savings
#   Row 36-41: Cumulative metric tons
#
#   Conversion: metric_tons = MWh_saved × lb/MWh / 2204.62
#
# GAS/OIL EMISSIONS (rows 62-69):
#   Standard combustion emission factors per MMBtu:
#     CH4:  ~1e-6 metric tons/MMBtu
#     N2O:  ~1e-7 metric tons/MMBtu
#     CO2:  ~53.06 kg/MMBtu (consistent with EPA EF Hub)
#
#   Row 65: Annual MMBtu savings
#   Row 66-69: Metric tons per year of CH4, N2O, CO2, CO2e
#
# GWP conversion for CO2e:
#   CO2e = CO2 + (CH4 × GWP_CH4) + (N2O × GWP_N2O)
#   Using SAR: GWP_CH4 = 21, GWP_N2O = 310
#
#
# ┌─────────────────────────────────────────────────────────────┐
# │  STEP 5: Cost-Benefit Analysis                             │
# │  (Cost Calculation tab)                                    │
# └─────────────────────────────────────────────────────────────┘
#
# The Cost Calculation tab mirrors the residential/commercial split:
#   - Residential costs & savings: cols B-AD (rows 5-24)
#   - Commercial costs & savings: cols AH+ (rows 5-24, offset right)
#
# ── SAVINGS CALCULATION (rows 8-14) ──
#
#   Row 8:  Cumulative MWh Savings (from Energy+Emissions Calc tab)
#   Row 9:  Cumulative MMBtu Savings
#   Row 10: $/kWh — state-specific electricity price by year
#   Row 11: $/MMBtu — state-specific gas price by year
#   Row 12: $ Electricity savings (millions) = cum_MWh × $/kWh / 1,000,000
#   Row 13: $ Gas/Oil savings (millions) = cum_MMBtu × $/MMBtu / 1,000,000
#   Row 14: Total Savings (millions $) = row 12 + row 13
#           NPV in col C = NPV(5%, annual_totals_2013:2040)
#
#   Energy prices source: Energy Price Projections tab
#     - AEO 2013 regional electricity prices (cents/kWh, 2011$)
#     - 25 eGrid regions mapped to states
#     - Residential and Commercial rates are separate
#     - Time-varying from 2011-2040 (30 years of projections)
#     - Natural gas prices: state-specific $/MMBtu from same source
#     - Prices generally rise over time → savings $ grow each year
#
# ── COST CALCULATION (rows 16-24) ──
#
#   Row 18: Base Code (current code for each year)
#   Row 19: Base Cost ($0 — current code is the no-cost baseline)
#   Row 20: Upgrade Code (proposed code after adoption year)
#   Row 21: Upgrade Cost per unit (PNNL state-level cost reports)
#   Row 22: Incremental Cost = Upgrade Cost - Base Cost
#           Residential: $/home (fixed for all years, no inflation)
#           Commercial: $/sqft (fixed for all years, no inflation)
#   Row 23: Building Projection (new homes/yr or new sqft/yr)
#   Row 24: Total Cost (millions $) = building_projection × incr_cost / 1,000,000
#           NPV in col C = NPV(5%, annual_costs_2013:2040)
#
#   Cost data source: PNNL state-level code cost reports
#     (http://www.energycodes.gov/development/residential/iecc_analysis)
#     - Row 30+: Per-state cost lookup table (all 50 states + DC)
#     - Columns: cost at each code version (IECC 2006 through PassiveHouse)
#     - Incremental cost = cost(upgrade_code) - cost(base_code)
#     - Also includes: % energy change 2006-2012, $/% energy change
#
#   Example residential incremental costs ($/home):
#     MS (IECC 2006→2024): $4,419/home
#     FL (IECC 2021→2024): $1,249/home (small jump = low cost)
#     SC (IECC 2009→2024): $3,357/home
#     KY (IECC 2012→2024): $2,679/home
#
#   Example commercial incremental costs ($/sqft):
#     MS (ASHRAE 2004→2025): $7.13/sqft
#     FL (ASHRAE 2019→2025): $3.05/sqft
#     SC (ASHRAE 2007→2025): $4.67/sqft
#
# ── NPV CALCULATION ──
#
#   NPV = Excel NPV(5%, annual_values_2013:2040)
#   The NPV function discounts each year's value back to the base year.
#   Since savings only begin in 2026, years 2013-2025 contribute $0.
#   Effective savings window: 2026-2040 = 15 years of discounted savings.
#
#   BCR (Benefit-Cost Ratio) = Savings NPV / Cost NPV
#   Net Benefit = Savings NPV - Cost NPV
#
# ── STEP 4 RESULTS (summary) ──
#
#   Step 4 - Results tab provides:
#     - 2030 and 2040 snapshot emissions (annual and cumulative)
#     - Residential vs Commercial split
#     - Cost & Savings summary:
#       Row 22: 'Projections Through 2040'
#       Row 23: Energy Cost Savings (Millions $ NPV) — Res, Com, Total
#       Row 24: Costs (Millions $ NPV) — Res, Com, Total
#       Row 25: Benefit-Cost Ratio — Res, Com, Total
#     - Emissions by pollutant: NOx, SOx, CH4, N2O, CO2, CO2e
#       (both through 2030 and through 2040)
#
#
# ============================================================
# Key Assumptions & Limitations
# ============================================================
#
# 1. STATIC EMISSION FACTORS: eGrid 2018 factors don't decline over
#    time. In reality, grid decarbonization would reduce the emission
#    savings from electricity efficiency. This overstates emission
#    reductions, especially for later years (2035-2040).
#
# 2. NEW CONSTRUCTION ONLY: no retrofit or existing building savings.
#    Total impact is proportional to new construction volume.
#    States with high growth (FL, GA, NC) get proportionally more
#    savings than slow-growth states (MS, KY).
#
# 3. COMPLIANCE at 75%: assumes 25% of new buildings don't meet code.
#    Actual compliance may vary by state/jurisdiction. This is a flat
#    rate applied equally to residential and commercial.
#
# 4. CONSTRUCTION COSTS are FIXED per unit regardless of year —
#    no inflation adjustment on the incremental cost.
#    This means costs stay constant in nominal terms while energy
#    prices (and thus savings) grow, biasing BCR upward over time.
#
# 5. ENERGY PRICES are time-varying (from AEO 2013 regional forecasts),
#    which means savings $ grow over time as energy prices rise.
#    Source vintage is AEO 2013 — actual prices may differ.
#
# 6. NPV WINDOW is 2013-2040 but savings only begin in 2026,
#    so the effective savings window is 15 years (2026-2040).
#    Costs also only begin in 2026 (zero before adoption year).
#
# 7. CODE SAVINGS CHAIN assumes each code version's savings are
#    independently multiplicative. PassiveHouse is modeled as a
#    single percentage over a base code (50% over IECC 2006 for
#    residential, 40% over ASHRAE 90.1-2010 for commercial).
#
# 8. BUILDING GROWTH uses PNNL default projections. These are
#    state-level estimates that may not reflect local conditions,
#    especially for metro areas. User can override with custom rates.
#
# 9. GWP VALUES use IPCC SAR (1995): CH4=21, N2O=310.
#    More recent AR5/AR6 values would give CH4≈28-30, N2O≈265.
#    This slightly underestimates CH4 contribution to CO2e.
#
# 10. COMMERCIAL COST DATA: incremental cost is per square foot,
#     which makes commercial costs very sensitive to new floor area
#     projections. Commercial costs tend to dominate total costs
#     because commercial $/sqft × sqft often exceeds residential
#     $/home × homes.
#
#
# ============================================================
# State-by-State Summary (all 11 SEEA states)
# ============================================================
#
# States grouped by current code vintage:
#
# OLDEST CODES (largest per-unit savings, highest per-unit costs):
#   MS:  IECC 2006 / ASHRAE 2004 → 2024/2025 (biggest jump)
#   SC:  IECC 2009 / ASHRAE 2007
#   AR:  IECC 2009 / ASHRAE 2007
#   KY:  IECC 2012 / ASHRAE 2010
#
# MIDDLE CODES:
#   GA:  IECC 2015 / ASHRAE 2013
#   NC:  IECC 2015 / ASHRAE 2013
#   AL:  IECC 2015 / ASHRAE 2013
#
# NEWEST CODES (smallest per-unit savings, lowest per-unit costs):
#   FL:  IECC 2021 / ASHRAE 2019
#   VA:  IECC 2021 / ASHRAE 2019
#   LA:  IECC 2021 / ASHRAE 2019
#   TN:  IECC 2021 (residential only; note: "no commercial savings")
#
# The cost-benefit outcome depends on the interplay of:
#   1. Code gap size (savings per unit)
#   2. Incremental cost per unit
#   3. New construction volume
#   4. Energy prices (state/region-specific)
#   5. Grid emission intensity (eGrid state factors)
#
# States with small code jumps and high construction volume (FL, VA)
# tend toward positive residential BCR because per-unit costs are low.
# States with large code jumps (MS, SC) have higher per-unit savings
# but also higher per-unit costs, which can push BCR below 1.0.
# Commercial almost always has BCR < 1.0 due to high $/sqft costs.
