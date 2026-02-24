"""Add 'Transport (v2 — City-Specific)' and 'Transport (v3 — MPG Split)' tabs to IAM_model.xlsx.

v2 replicates the city-specific pipeline with hardcoded car/truck fractions (0.42/0.58),
same MPG for car and truck, SPPC->MISC fallback, first-match freight efficiency,
and freight_ehybrid allocated to diesel.

v3 uses the current codebase: dynamic car/truck fractions from AEO LDV sales shares,
separate car/truck MPG, SPPC carbon intensity available directly, last-match freight
efficiency (average across weight classes), and freight_ehybrid allocated to gasoline.

Usage:
    python scripts/build_transport_tabs.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

from iam.config import (
    CITIES, CITY_REGION_MAP, CITY_STATE_MAP,
    PROJECTION_YEARS, BASE_YEAR, CITY_AEO_SALES_REGION_MAP,
    LDV_SHARE, HDV_SHARE, KWH_PER_GALLON_GASOLINE,
    EMISSION_FACTORS_KG_CO2,
)
from iam.data_loader import load_all_data, get_carbon_intensity, get_ldv_sales_share
from iam.city import City
from iam.transport import (
    calculate_initial_vmt_by_fuel, project_vmt,
    calculate_fuel_consumption, calculate_transport_emissions,
)


# ============================================================
# Shared styles
# ============================================================
title_font = Font(bold=True, size=14)
section_font = Font(bold=True, size=12, color="1F4E79")
note_font = Font(italic=True, size=10, color="666666")
bold_font = Font(bold=True, size=10)
header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
header_font = Font(bold=True, size=10, color="FFFFFF")
change_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
change_font = Font(bold=True, size=10, color="BF8F00")
num_fmt = "#,##0.0"
year_col_start = 3  # Column C


# ============================================================
# Shared helper functions
# ============================================================

def _write_year_headers(ws, row: int, proj_years: list) -> None:
    """Write year column headers with formatting."""
    for i, yr in enumerate(proj_years):
        c = ws.cell(row=row, column=year_col_start + i, value=yr)
        c.font = header_font
        c.fill = header_fill
        c.alignment = Alignment(horizontal="center")


def _write_data_row(ws, row: int, label: str, values: list,
                    fmt: str = "#,##0.0", lfont: Font = None) -> None:
    """Write a label + data values row."""
    c = ws.cell(row=row, column=1, value=label)
    if lfont:
        c.font = lfont
    for i, v in enumerate(values):
        if v is not None:
            c = ws.cell(row=row, column=year_col_start + i, value=v)
            c.number_format = fmt


def _write_documentation_header(ws, r: int, title: str, description: str,
                                changes: list, proj_years: list) -> int:
    """Write the documentation header section. Returns next row."""
    last_col = get_column_letter(year_col_start + len(proj_years) - 1)
    ws.merge_cells(f"A{r}:{last_col}{r}")
    ws[f"A{r}"] = title
    ws[f"A{r}"].font = title_font
    r += 1

    ws.merge_cells(f"A{r}:{last_col}{r}")
    ws[f"A{r}"] = description
    ws[f"A{r}"].font = note_font
    r += 2

    ws[f"A{r}"] = "CHANGES / NOTES"
    ws[f"A{r}"].font = section_font
    r += 1

    for label, desc in changes:
        ws[f"A{r}"] = label
        ws[f"A{r}"].font = change_font
        ws[f"A{r}"].fill = change_fill
        ws[f"B{r}"] = desc
        ws[f"B{r}"].font = note_font
        r += 1

    r += 1
    return r


def _write_city_params_section(ws, r: int, city_results: dict,
                               ci_label: str = "CI Region Used") -> int:
    """Write the city input parameters table. Returns next row."""
    ws[f"A{r}"] = "CITY INPUT PARAMETERS"
    ws[f"A{r}"].font = section_font
    r += 1

    param_headers = ["City", "State", "Region", "FHWA Annual VMT (Base Year)", ci_label]
    for i, h in enumerate(param_headers):
        c = ws.cell(row=r, column=i + 1, value=h)
        c.font = header_font
        c.fill = header_fill
        c.alignment = Alignment(horizontal="center")
    r += 1

    for name in CITIES:
        cr = city_results[name]
        ws.cell(row=r, column=1, value=name)
        ws.cell(row=r, column=2, value=cr["state"])
        ws.cell(row=r, column=3, value=cr["region"])
        c = ws.cell(row=r, column=4, value=cr["total_vmt_base"])
        c.number_format = "#,##0"
        ws.cell(row=r, column=5, value=cr["ci_region"])
        r += 1

    r += 1
    return r


def _write_total_emissions_section(ws, r: int, city_results: dict,
                                   proj_years: list) -> int:
    """Write total transport emissions by city section. Returns next row."""
    ws[f"A{r}"] = "TOTAL TRANSPORT EMISSIONS BY CITY (MT CO2)"
    ws[f"A{r}"].font = section_font
    r += 1

    ws.cell(row=r, column=1, value="City").font = header_font
    ws.cell(row=r, column=1).fill = header_fill
    ws.cell(row=r, column=2, value="State").font = header_font
    ws.cell(row=r, column=2).fill = header_fill
    _write_year_headers(ws, r, proj_years)
    r += 1

    for name in CITIES:
        ws.cell(row=r, column=1, value=name)
        ws.cell(row=r, column=2, value=city_results[name]["state"])
        by_year = city_results[name]["by_year"]
        for i, yr in enumerate(proj_years):
            if yr in by_year:
                c = ws.cell(row=r, column=year_col_start + i,
                            value=by_year[yr]["emissions"]["total_mt_co2"])
                c.number_format = num_fmt
        r += 1

    r += 1
    return r


def _write_emissions_by_fuel_section(ws, r: int, city_results: dict,
                                     proj_years: list) -> int:
    """Write emissions by fuel type per city section. Returns next row."""
    ws[f"A{r}"] = "EMISSIONS BY FUEL TYPE PER CITY (MT CO2)"
    ws[f"A{r}"].font = section_font
    r += 1

    fuel_keys = [
        ("gasoline_mt_co2", "Gasoline"),
        ("diesel_mt_co2", "Diesel"),
        ("ethanol_mt_co2", "Ethanol"),
        ("electricity_mt_co2", "Electricity"),
    ]

    for name in CITIES:
        ws[f"A{r}"] = name
        ws[f"A{r}"].font = Font(bold=True, size=11, underline="single")
        r += 1
        ws.cell(row=r, column=1, value="Fuel Type").font = header_font
        ws.cell(row=r, column=1).fill = header_fill
        _write_year_headers(ws, r, proj_years)
        r += 1

        by_year = city_results[name]["by_year"]

        vals = [by_year[yr]["emissions"]["total_mt_co2"] if yr in by_year else None
                for yr in proj_years]
        _write_data_row(ws, r, "Total Emissions", vals, lfont=bold_font)
        r += 1

        for key, label in fuel_keys:
            vals = [by_year[yr]["emissions"][key] if yr in by_year else None
                    for yr in proj_years]
            _write_data_row(ws, r, f"   {label}", vals)
            r += 1

        r += 1

    return r


def _write_fuel_consumption_section(ws, r: int, city_results: dict,
                                    proj_years: list) -> int:
    """Write fuel consumption per city section. Returns next row."""
    ws[f"A{r}"] = "FUEL CONSUMPTION PER CITY"
    ws[f"A{r}"].font = section_font
    r += 1

    consumption_keys = [
        ("gasoline_gallons", "Gasoline (gallons)"),
        ("diesel_gallons", "Diesel (gallons)"),
        ("ethanol_gallons", "Ethanol (gallons)"),
        ("electricity_mwh", "Electricity (MWh)"),
    ]

    for name in CITIES:
        ws[f"A{r}"] = name
        ws[f"A{r}"].font = Font(bold=True, size=11, underline="single")
        r += 1
        ws.cell(row=r, column=1, value="Fuel Type").font = header_font
        ws.cell(row=r, column=1).fill = header_fill
        _write_year_headers(ws, r, proj_years)
        r += 1

        by_year = city_results[name]["by_year"]
        for key, label in consumption_keys:
            vals = [by_year[yr]["fuel"][key] if yr in by_year else None
                    for yr in proj_years]
            _write_data_row(ws, r, f"   {label}", vals)
            r += 1

        r += 1

    return r


def _write_vmt_by_fuel_section(ws, r: int, city_results: dict,
                               proj_years: list) -> int:
    """Write VMT by fuel type per city section. Returns next row."""
    ws[f"A{r}"] = "VMT BY FUEL TYPE PER CITY"
    ws[f"A{r}"].font = section_font
    r += 1

    vmt_keys = [
        ("conventional_gasoline", "Conventional Gasoline"),
        ("tdi_diesel", "TDI Diesel"),
        ("flex_fuel", "Flex-Fuel"),
        ("electric", "Electric"),
        ("plugin_hybrid", "Plug-in Hybrid"),
        ("electric_hybrid", "Electric Hybrid"),
    ]

    for name in CITIES:
        ws[f"A{r}"] = name
        ws[f"A{r}"].font = Font(bold=True, size=11, underline="single")
        r += 1
        ws.cell(row=r, column=1, value="Fuel Type").font = header_font
        ws.cell(row=r, column=1).fill = header_fill
        _write_year_headers(ws, r, proj_years)
        r += 1

        by_year = city_results[name]["by_year"]

        vals = [by_year[yr]["vmt_total"] if yr in by_year else None
                for yr in proj_years]
        _write_data_row(ws, r, "Total VMT", vals, fmt="#,##0", lfont=bold_font)
        r += 1

        for key, label in vmt_keys:
            vals = [by_year[yr]["vmt_by_fuel"][key] if yr in by_year else None
                    for yr in proj_years]
            _write_data_row(ws, r, f"   {label}", vals, fmt="#,##0")
            r += 1

        r += 1

    return r


def _set_column_widths(ws, proj_years: list) -> None:
    """Set standard column widths and freeze panes."""
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 20
    for i in range(len(proj_years)):
        ws.column_dimensions[get_column_letter(year_col_start + i)].width = 14
    ws.freeze_panes = "C1"


# ============================================================
# v2 compute function — replicates v2 logic inline
# ============================================================

def _v2_calculate_fuel_consumption(
    vmt_by_fuel: dict,
    year: int,
    aeo_mpg,
    aeo_freight,
) -> dict:
    """v2 fuel consumption: hardcoded 0.42/0.58 car/truck fraction, same MPG
    for car and truck (no vehicle_class filter), first-match freight efficiency,
    and freight_ehybrid allocated to diesel.

    Differences from v3:
    - car_fraction = 0.42, truck_fraction = 0.58 (hardcoded)
    - MPG lookup uses vehicle_type only (no vehicle_class), takes first match (.iloc[0])
    - Freight efficiency uses first match (.iloc[0]) instead of last
    - freight_ehybrid goes to diesel (v2 bug), not gasoline
    """
    car_fraction = 0.42
    truck_fraction = 0.58
    yr_col = f"y{year}"

    def _get_mpg_v2(vehicle_type: str) -> float:
        """v2 MPG: no vehicle_class filter, first match."""
        row = aeo_mpg[aeo_mpg["vehicle_type"] == vehicle_type]
        if row.empty:
            raise ValueError(f"MPG not found for '{vehicle_type}'")
        val = row[yr_col].iloc[0]
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return np.inf
        return float(val)

    def _get_freight_eff_v2(category: str) -> float:
        """v2 freight efficiency: first match (.iloc[0])."""
        if aeo_freight is None:
            return np.inf
        row = aeo_freight[aeo_freight["category"] == category]
        if row.empty:
            return np.inf
        val = row[yr_col].iloc[0]  # FIRST match, not last
        if val is None or val == 0 or (isinstance(val, float) and np.isnan(val)):
            return np.inf
        return float(val)

    # ---- Gasoline consumption (gallons) ----
    car_gas_mpg = _get_mpg_v2("Gasoline ICE Vehicles")
    car_gas = vmt_by_fuel.get("conventional_gasoline", 0) * LDV_SHARE * car_fraction / car_gas_mpg

    # v2: same MPG for truck (no vehicle_class distinction), same first match
    truck_gas_mpg = _get_mpg_v2("Gasoline ICE Vehicles")
    truck_gas = vmt_by_fuel.get("conventional_gasoline", 0) * LDV_SHARE * truck_fraction / truck_gas_mpg

    freight_gas_mpg = _get_freight_eff_v2("Conventional Gasoline")
    freight_gas = vmt_by_fuel.get("conventional_gasoline", 0) * HDV_SHARE / freight_gas_mpg

    total_gasoline = car_gas + truck_gas + freight_gas

    # ---- Diesel consumption (gallons) ----
    truck_diesel_mpg = _get_mpg_v2("TDI Diesel ICE")
    truck_diesel = vmt_by_fuel.get("tdi_diesel", 0) * LDV_SHARE / truck_diesel_mpg

    freight_diesel_mpg = _get_freight_eff_v2("TDI Diesel")
    freight_diesel = vmt_by_fuel.get("tdi_diesel", 0) * HDV_SHARE / freight_diesel_mpg

    total_diesel = truck_diesel + freight_diesel

    # ---- Ethanol consumption (gallons) ----
    car_flex_mpg = _get_mpg_v2("Ethanol-Flex Fuel ICE")
    car_ethanol = vmt_by_fuel.get("flex_fuel", 0) * LDV_SHARE * car_fraction / car_flex_mpg

    truck_flex_mpg = _get_mpg_v2("Ethanol-Flex Fuel ICE")
    truck_ethanol = vmt_by_fuel.get("flex_fuel", 0) * LDV_SHARE * truck_fraction / truck_flex_mpg

    freight_flex_mpg = _get_freight_eff_v2("Flex-Fuel")
    freight_ethanol = vmt_by_fuel.get("flex_fuel", 0) * HDV_SHARE / freight_flex_mpg

    total_ethanol = car_ethanol + truck_ethanol + freight_ethanol

    # ---- Electricity consumption (MWh) ----
    car_ev_mpge = _get_mpg_v2("Average EV")
    car_ev_mwh = (vmt_by_fuel.get("electric", 0) * LDV_SHARE * car_fraction
                  / car_ev_mpge * KWH_PER_GALLON_GASOLINE / 1000)

    truck_ev_mpge = _get_mpg_v2("Average EV")
    truck_ev_mwh = (vmt_by_fuel.get("electric", 0) * LDV_SHARE * truck_fraction
                    / truck_ev_mpge * KWH_PER_GALLON_GASOLINE / 1000)

    freight_ev_mpge = _get_freight_eff_v2("Electric")
    freight_ev_mwh = (vmt_by_fuel.get("electric", 0) * HDV_SHARE
                      / freight_ev_mpge * KWH_PER_GALLON_GASOLINE / 1000)

    # Plugin hybrid
    car_phev_mpg = _get_mpg_v2("Average Plug In Hybrid")
    car_phev = vmt_by_fuel.get("plugin_hybrid", 0) * LDV_SHARE * car_fraction / car_phev_mpg

    truck_phev_mpg = _get_mpg_v2("Average Plug In Hybrid")
    truck_phev = vmt_by_fuel.get("plugin_hybrid", 0) * LDV_SHARE * truck_fraction / truck_phev_mpg

    freight_phev_mpg = _get_freight_eff_v2("Plug-in Diesel Hybrid")
    freight_phev = vmt_by_fuel.get("plugin_hybrid", 0) * HDV_SHARE / freight_phev_mpg

    # Electric hybrid (gasoline equivalent)
    car_ehybrid_mpg = _get_mpg_v2("Electric-Gasoline Hybrid")
    car_ehybrid = vmt_by_fuel.get("electric_hybrid", 0) * LDV_SHARE * car_fraction / car_ehybrid_mpg

    truck_ehybrid_mpg = _get_mpg_v2("Electric-Gasoline Hybrid")
    truck_ehybrid = vmt_by_fuel.get("electric_hybrid", 0) * LDV_SHARE * truck_fraction / truck_ehybrid_mpg

    freight_ehybrid_mpg = _get_freight_eff_v2("Electric Hybrid")
    freight_ehybrid = vmt_by_fuel.get("electric_hybrid", 0) * HDV_SHARE / freight_ehybrid_mpg

    # v2 allocation:
    # Gasoline: car_phev + truck_phev + car_ehybrid + truck_ehybrid (NOT freight_ehybrid)
    # Diesel: freight_phev + freight_ehybrid (freight_ehybrid goes to diesel in v2)
    total_gasoline += car_phev + truck_phev + car_ehybrid + truck_ehybrid
    total_diesel += freight_phev + freight_ehybrid

    total_electricity_mwh = car_ev_mwh + truck_ev_mwh + freight_ev_mwh

    return {
        "gasoline_gallons": total_gasoline,
        "diesel_gallons": total_diesel,
        "ethanol_gallons": total_ethanol,
        "electricity_mwh": total_electricity_mwh,
    }


def _v2_get_carbon_intensity(region: str, year: int, ci_df) -> float:
    """v2 carbon intensity lookup: SPPC falls back to MISC."""
    lookup_region = region
    if region == "SPPC":
        lookup_region = "MISC"
    return get_carbon_intensity(lookup_region, year, ci_df)


def compute_all_cities_v2(all_data: dict) -> dict:
    """Run the v2 transport pipeline for all 25 cities.

    v2 differences from v3:
    - Car/truck fraction hardcoded at 0.42/0.58
    - Same MPG value used for both car and truck (no vehicle_class distinction)
    - SPPC region falls back to MISC for carbon intensity lookup
    - Freight efficiency uses FIRST match in CSV (.iloc[0])
    - freight_ehybrid allocated to DIESEL (not gasoline)
    """
    city_results = {}
    for name in CITIES:
        city = City(name=name, all_data=all_data)
        by_year = {}
        vmt_df = city._get_projected_vmt()
        total_vmt = city._get_city_vmt()

        # v2: SPPC falls back to MISC
        ci_region = city.region
        if ci_region == "SPPC":
            ci_region = "MISC"

        for yr in PROJECTION_YEARS:
            year_row = vmt_df[vmt_df["year"] == yr]
            if year_row.empty:
                continue
            year_row = year_row.iloc[0]
            vmt_by_fuel = {
                "conventional_gasoline": year_row["vmt_conventional_gasoline"],
                "tdi_diesel": year_row["vmt_tdi_diesel"],
                "flex_fuel": year_row["vmt_flex_fuel"],
                "electric": year_row["vmt_electric"],
                "plugin_hybrid": year_row["vmt_plugin_hybrid"],
                "electric_hybrid": year_row["vmt_electric_hybrid"],
            }

            # v2: uses inline fuel consumption with hardcoded fractions
            fuel = _v2_calculate_fuel_consumption(
                vmt_by_fuel, yr, all_data["aeo_mpg"], all_data["aeo_freight"],
            )

            # v2: SPPC -> MISC fallback for carbon intensity
            ci = _v2_get_carbon_intensity(city.region, yr, all_data["aeo_ci"])
            emissions = calculate_transport_emissions(fuel, ci)

            by_year[yr] = {
                "vmt_by_fuel": vmt_by_fuel,
                "vmt_total": sum(vmt_by_fuel.values()),
                "fuel": fuel,
                "emissions": emissions,
                "ci": ci,
            }

        city_results[name] = {
            "total_vmt_base": total_vmt,
            "region": CITY_REGION_MAP[name],
            "state": CITY_STATE_MAP[name],
            "ci_region": ci_region,
            "by_year": by_year,
        }
    return city_results


# ============================================================
# v3 compute function — uses current v3 functions directly
# ============================================================

def compute_all_cities_v3(all_data: dict) -> dict:
    """Run the v3 transport pipeline for all 25 cities.

    v3 uses:
    - Dynamic car/truck fractions from AEO LDV sales shares
    - Separate car/truck MPG (vehicle_class="car" vs "truck")
    - SPPC carbon intensity directly available (no fallback)
    - Freight efficiency uses last match (.iloc[-1] = average across weight classes)
    - freight_ehybrid allocated to gasoline (correct per Excel R13)
    """
    city_results = {}
    for name in CITIES:
        city = City(name=name, all_data=all_data)
        by_year = {}
        vmt_df = city._get_projected_vmt()
        total_vmt = city._get_city_vmt()

        for yr in PROJECTION_YEARS:
            year_row = vmt_df[vmt_df["year"] == yr]
            if year_row.empty:
                continue
            year_row = year_row.iloc[0]
            vmt_by_fuel = {
                "conventional_gasoline": year_row["vmt_conventional_gasoline"],
                "tdi_diesel": year_row["vmt_tdi_diesel"],
                "flex_fuel": year_row["vmt_flex_fuel"],
                "electric": year_row["vmt_electric"],
                "plugin_hybrid": year_row["vmt_plugin_hybrid"],
                "electric_hybrid": year_row["vmt_electric_hybrid"],
            }

            # v3: dynamic car/truck fractions from AEO LDV sales shares
            sales_region = CITY_AEO_SALES_REGION_MAP.get(name, "South Atlantic")
            car_fraction = get_ldv_sales_share(
                sales_region, "Cars", yr, all_data["aeo_ldv_sales"]
            )
            truck_fraction = get_ldv_sales_share(
                sales_region, "Pick Up Trucks", yr, all_data["aeo_ldv_sales"]
            )

            # v3: uses current calculate_fuel_consumption with separate car/truck MPG
            fuel = calculate_fuel_consumption(
                vmt_by_fuel, yr, all_data["aeo_mpg"],
                car_fraction=car_fraction,
                truck_fraction=truck_fraction,
                aeo_freight=all_data["aeo_freight"],
            )

            # v3: SPPC carbon intensity available directly (no fallback)
            ci = get_carbon_intensity(city.region, yr, all_data["aeo_ci"])
            emissions = calculate_transport_emissions(fuel, ci)

            by_year[yr] = {
                "vmt_by_fuel": vmt_by_fuel,
                "vmt_total": sum(vmt_by_fuel.values()),
                "fuel": fuel,
                "emissions": emissions,
                "ci": ci,
            }

        city_results[name] = {
            "total_vmt_base": total_vmt,
            "region": CITY_REGION_MAP[name],
            "state": CITY_STATE_MAP[name],
            "ci_region": CITY_REGION_MAP[name],
            "by_year": by_year,
        }
    return city_results


# ============================================================
# v2 tab builder
# ============================================================

def build_v2_tab(wb: openpyxl.Workbook, city_results: dict) -> None:
    """Add the 'Transport (v2 — City-Specific)' sheet to the workbook."""
    tab_name = "Transport (v2 — City-Specific)"
    if tab_name in wb.sheetnames:
        del wb[tab_name]
    ws = wb.create_sheet(tab_name)

    proj_years = PROJECTION_YEARS

    # ---- Documentation Header ----
    changes = [
        ("CHANGE 1 — City-specific VMT",
         "Old: Single reference city VMT (Atlanta). "
         "New: Each city uses own FHWA VMT."),
        ("CHANGE 2 — State-specific fuel mix",
         "Old: Georgia AFDC shares. "
         "New: Each city uses own state's shares."),
        ("CHANGE 3 — Region-specific carbon intensity",
         "Old: SRSE only. "
         "New: City's own AEO region (SPPC->MISC fallback)."),
        ("KNOWN APPROXIMATION",
         "Car/truck MPG uses same value; hardcoded 0.42/0.58 fraction."),
    ]

    r = _write_documentation_header(
        ws, 1,
        title="Transportation — v2 City-Specific Emissions",
        description=(
            "This tab uses city-specific VMT, state fuel mix, and regional carbon intensity, "
            "but retains v2 approximations: hardcoded car/truck fractions (0.42/0.58), "
            "same MPG for cars and trucks, SPPC->MISC CI fallback, first-match freight "
            "efficiency, and freight_ehybrid allocated to diesel."
        ),
        changes=changes,
        proj_years=proj_years,
    )

    # ---- City Input Parameters ----
    r = _write_city_params_section(ws, r, city_results, ci_label="CI Region Used (SPPC->MISC)")

    # ---- Total Emissions by City ----
    r = _write_total_emissions_section(ws, r, city_results, proj_years)

    # ---- Emissions by Fuel Type per City ----
    r = _write_emissions_by_fuel_section(ws, r, city_results, proj_years)

    # ---- Fuel Consumption per City ----
    r = _write_fuel_consumption_section(ws, r, city_results, proj_years)

    # ---- VMT by Fuel Type per City ----
    r = _write_vmt_by_fuel_section(ws, r, city_results, proj_years)

    # ---- Column widths ----
    _set_column_widths(ws, proj_years)


# ============================================================
# v3 tab builder
# ============================================================

def build_v3_tab(wb: openpyxl.Workbook, city_results: dict) -> None:
    """Add the 'Transport (v3 — MPG Split)' sheet to the workbook."""
    tab_name = "Transport (v3 — MPG Split)"
    if tab_name in wb.sheetnames:
        del wb[tab_name]
    ws = wb.create_sheet(tab_name)

    proj_years = PROJECTION_YEARS

    # ---- Documentation Header ----
    changes = [
        ("CHANGE 4 — Car/truck MPG split",
         "Car MPG from AEO R9, truck from AEO R24. "
         "Dynamic car/truck fractions from AEO LDV sales."),
        ("CHANGE 5 — Dynamic car/truck fractions",
         "From AEO LDV sales shares (R103-R107) by region and year."),
        ("CHANGE 6 — SPPC carbon intensity",
         "Now available directly from AEO (no MISC fallback)."),
        ("CHANGE 7 — Freight efficiency fix",
         "Uses average across weight classes (AEO R155-R160, last match in CSV)."),
        ("CHANGE 8 — freight_ehybrid allocation",
         "Corrected to gasoline (was diesel in v2)."),
        ("KNOWN DIVERGENCE",
         "Excel R21 formula bug — uses diesel VMT for car flex-fuel "
         "instead of flex VMT."),
    ]

    r = _write_documentation_header(
        ws, 1,
        title="Transportation — v3 MPG Split Emissions",
        description=(
            "This tab uses the full v3 pipeline: dynamic car/truck fractions from "
            "AEO LDV sales shares, separate car/truck MPG values, SPPC carbon intensity "
            "available directly, last-match freight efficiency (average across weight classes), "
            "and corrected freight_ehybrid allocation to gasoline."
        ),
        changes=changes,
        proj_years=proj_years,
    )

    # ---- City Input Parameters ----
    r = _write_city_params_section(ws, r, city_results, ci_label="CI Region Used")

    # ---- Total Emissions by City ----
    r = _write_total_emissions_section(ws, r, city_results, proj_years)

    # ---- Emissions by Fuel Type per City ----
    r = _write_emissions_by_fuel_section(ws, r, city_results, proj_years)

    # ---- Fuel Consumption per City ----
    r = _write_fuel_consumption_section(ws, r, city_results, proj_years)

    # ---- VMT by Fuel Type per City ----
    r = _write_vmt_by_fuel_section(ws, r, city_results, proj_years)

    # ---- Python Module Documentation ----
    r = _write_python_module_docs(ws, r, proj_years)

    # ---- Column widths ----
    _set_column_widths(ws, proj_years)


def _write_python_module_docs(ws, r: int, proj_years: list) -> int:
    """Write Python module documentation section for v3 tab. Returns next row."""
    last_col = get_column_letter(year_col_start + len(proj_years) - 1)

    ws[f"A{r}"] = "PYTHON MODULE DOCUMENTATION"
    ws[f"A{r}"].font = section_font
    r += 1

    # --- transport.py ---
    ws[f"A{r}"] = "transport.py"
    ws[f"A{r}"].font = Font(bold=True, size=11, underline="single")
    r += 1
    transport_docs = [
        ("calculate_initial_vmt_by_fuel(total_vmt, state, afdc_shares)",
         "Allocate total VMT across fuel types using AFDC state shares. "
         "Maps to Excel Transport R45-R50."),
        ("project_vmt(initial_vmt_by_fuel, years)",
         "Project VMT forward using AEO growth rates. "
         "Maps to Excel Transport R45-R50 columns E+. "
         "Formula: VMT(yr) = VMT(yr-1) * (1 + rate)."),
        ("calculate_fuel_consumption(vmt_by_fuel, year, aeo_mpg, car_fraction, truck_fraction, aeo_freight)",
         "Convert VMT to fuel consumption. Car/truck MPG split via vehicle_class column. "
         "Freight uses last-match efficiency. "
         "Maps to Excel Transport R13-R16, R19-R38."),
        ("calculate_transport_emissions(fuel_consumption, carbon_intensity)",
         "Convert fuel to CO2 using EPA factors + regional CI. "
         "Maps to Excel Transport R7-R10."),
    ]
    for func, desc in transport_docs:
        ws[f"A{r}"] = func
        ws[f"A{r}"].font = Font(bold=True, size=9)
        ws[f"B{r}"] = desc
        ws[f"B{r}"].font = note_font
        r += 1
    r += 1

    # --- city.py ---
    ws[f"A{r}"] = "city.py"
    ws[f"A{r}"].font = Font(bold=True, size=11, underline="single")
    r += 1
    city_docs = [
        ("City.__init__(name, fixed_data, city_data, all_data)",
         "Initialize with region/state from config. Lazy-loads data if not provided."),
        ("City.transport_emissions(year)",
         "Full pipeline: FHWA VMT -> AFDC fuel split -> AEO growth -> "
         "fuel consumption (car/truck MPG split) -> emissions. "
         "Caches VMT projections in _transport_vmt_cache."),
        ("City._get_city_vmt()",
         "Lookup from FHWA data, multiplied by 1000. Maps to Excel Transport R44."),
        ("City._get_projected_vmt()",
         "Cached VMT projections for all years. Uses calculate_initial_vmt_by_fuel + project_vmt."),
    ]
    for func, desc in city_docs:
        ws[f"A{r}"] = func
        ws[f"A{r}"].font = Font(bold=True, size=9)
        ws[f"B{r}"] = desc
        ws[f"B{r}"].font = note_font
        r += 1
    r += 1

    # --- config.py ---
    ws[f"A{r}"] = "config.py"
    ws[f"A{r}"].font = Font(bold=True, size=11, underline="single")
    r += 1
    config_docs = [
        ("LDV_SHARE = 0.9, HDV_SHARE = 0.1",
         "Light/heavy duty vehicle share of VMT (Transport R53-R54)."),
        ("KWH_PER_GALLON_GASOLINE = 33.7",
         "Energy content conversion for EV MPGe (Transport R57)."),
        ("EMISSION_FACTORS_KG_CO2",
         "EPA emission factors: motor_gasoline=8.78, diesel=10.21, ethanol_100=5.75 (Transport R52-R63)."),
        ("VMT_GROWTH_RATES",
         "AEO 2025 Table 41 annual growth rates by fuel type (Transport R70-R86)."),
        ("CITY_REGION_MAP",
         "25 cities -> AEO electricity market regions."),
        ("CITY_STATE_MAP",
         "25 cities -> states (for AFDC lookups)."),
        ("CITY_AEO_SALES_REGION_MAP",
         "25 cities -> AEO census divisions (South Atlantic / Middle Atlantic) for LDV sales shares."),
    ]
    for const, desc in config_docs:
        ws[f"A{r}"] = const
        ws[f"A{r}"].font = Font(bold=True, size=9)
        ws[f"B{r}"] = desc
        ws[f"B{r}"].font = note_font
        r += 1
    r += 1

    # --- data_loader.py ---
    ws[f"A{r}"] = "data_loader.py"
    ws[f"A{r}"].font = Font(bold=True, size=11, underline="single")
    r += 1
    loader_docs = [
        ("load_all_data()",
         "Loads all CSVs into a single dict: fixed, aeo_ci, aeo_mpg, aeo_freight, "
         "aeo_ldv_sales, fhwa_vmt, afdc_shares, buildings_emissions, etc."),
        ("get_carbon_intensity(region, year, ci_df)",
         "Lookup MT CO2/MWh for a region and year from AEO carbon intensity table."),
        ("get_ldv_sales_share(region, vehicle_type, year, sales_df)",
         "Lookup car/truck fraction from AEO LDV sales shares table. "
         "Returns 0-1 fraction for 'Cars' or 'Pick Up Trucks'."),
        ("load_aeo_mpg()",
         "AEO MPG projections with vehicle_class column ('car'/'truck') to disambiguate."),
        ("load_aeo_freight_efficiency()",
         "AEO freight efficiency by weight class and fuel type. "
         "Average values are last rows in CSV (R155-R160)."),
    ]
    for func, desc in loader_docs:
        ws[f"A{r}"] = func
        ws[f"A{r}"].font = Font(bold=True, size=9)
        ws[f"B{r}"] = desc
        ws[f"B{r}"].font = note_font
        r += 1
    r += 1

    return r


# ============================================================
# Main
# ============================================================

def main():
    print("Loading data...")
    all_data = load_all_data()

    print("Computing v2 (city-specific, hardcoded fractions)...")
    v2_results = compute_all_cities_v2(all_data)

    print("Computing v3 (MPG split, dynamic fractions)...")
    v3_results = compute_all_cities_v3(all_data)

    print("Building Excel tabs...")
    xlsx_path = Path("IAM_model.xlsx")
    wb = openpyxl.load_workbook(xlsx_path)
    build_v2_tab(wb, v2_results)
    build_v3_tab(wb, v3_results)
    wb.save(xlsx_path)

    # Print verification values
    for name in ["Atlanta"]:
        for yr in [2027]:
            v2_val = v2_results[name]["by_year"][yr]["emissions"]["total_mt_co2"]
            v3_val = v3_results[name]["by_year"][yr]["emissions"]["total_mt_co2"]
            print(f"\n{name} {yr}:")
            print(f"  v2: {v2_val:,.0f} MT CO2")
            print(f"  v3: {v3_val:,.0f} MT CO2")

    print(f"\nDone. Added v2 and v3 tabs to {xlsx_path}")


if __name__ == "__main__":
    main()
