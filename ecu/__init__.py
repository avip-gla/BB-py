"""BRESE (Building Resilient and Energy-Saving Economies) module.

Calculates cost-benefit impacts of adopting updated building energy codes
across southeastern US states.

Data sources:
  - BRESE-cost-benefit-analysis.xlsx (SEEA summary workbook)
    11 state tabs: SC, Georgia, NC, AL, Florida, VA, LA, KY, TN, Arkansas, MS
  - DOE Building Energy Code Savings Calculator (upstream model)
    Building-Energy-Code-Emissions-Calculator-seea.xlsm

Each state tab in the summary workbook contains:
  - Energy avoided (electricity MWh, natural gas MMBtu) by year (2026-2040)
  - CO2 avoided (single-year snapshot, typically 2030)
  - Cost-benefit summary: energy cost savings vs implementation costs (NPV through 2040)
    split by residential and commercial sectors
"""
