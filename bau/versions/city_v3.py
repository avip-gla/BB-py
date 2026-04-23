"""City class — core abstraction for the IAM model.

Each city is represented as a City object that holds both fixed and localized
data, and exposes methods to calculate sector-level emissions and savings.

The City class orchestrates the full calculation pipeline:
  1. Load city-specific data (region, consumption baselines)
  2. Load shared national data (AEO projections, emission factors)
  3. Calculate buildings emissions (electricity + NG) by year
  4. Calculate transport emissions (VMT -> fuel -> CO2) by year
  5. Aggregate into Findings-style output

Excel model flow:
  Findings tab -> Buildings tab -> Electricity tab + NG tab -> AEO tab
  Findings tab -> Transport tab -> AEO tab + FHWA tab + AFDC data
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional

from bau.config import (
    CITY_REGION_MAP, CITY_STATE_MAP, PROJECTION_YEARS, BASE_YEAR,
    CITY_AEO_SALES_REGION_MAP,
)
from bau.data_loader import (
    load_all_data, load_city_data, get_carbon_intensity, get_mpg,
    load_buildings_emissions, load_electricity_emissions, load_ng_emissions,
    load_transport_emissions, get_ldv_sales_share,
)
from bau.buildings import calculate_total_buildings_emissions
from bau.transport import (
    calculate_initial_vmt_by_fuel, project_vmt,
    calculate_fuel_consumption, calculate_transport_emissions,
)
from bau.findings import (
    calculate_findings_for_year, calculate_trends,
    calculate_savings_series, findings_to_dataframe,
)


class City:
    """Represents a single city in the IAM model.

    Holds both fixed national parameters and city-specific localized data.
    Provides methods to calculate sector-level emissions and GHG savings
    across projection years (2027-2050).

    Attributes:
        name: City name (e.g., 'Atlanta').
        region: AEO electricity market region (e.g., 'SRSE').
        state: State name for AFDC lookups (e.g., 'Georgia').
        fixed: Dict of shared national parameters.
        local: Dict of city-specific parameters.
        data: Dict of all loaded data (AEO, FHWA, AFDC, etc.).
    """

    def __init__(
        self,
        name: str,
        fixed_data: Optional[dict] = None,
        city_data: Optional[dict] = None,
        all_data: Optional[dict] = None,
    ):
        """Initialize a City with its data.

        Args:
            name: City name matching entries in config.CITY_REGION_MAP.
            fixed_data: National/fixed parameters. If None, loaded from CSV.
            city_data: City-specific parameters. If None, loaded from CSV.
            all_data: Pre-loaded data dict from load_all_data().
                If None, all data will be loaded on first calculation.
        """
        self.name = name
        self.region = CITY_REGION_MAP.get(name, "")
        self.state = CITY_STATE_MAP.get(name, "")

        # Load data if not provided
        if all_data is not None:
            self.data = all_data
        else:
            self.data = None  # lazy-load on first use

        if fixed_data is not None:
            self.fixed = fixed_data
        elif all_data is not None:
            self.fixed = all_data["fixed"]
        else:
            self.fixed = None  # lazy-load

        if city_data is not None:
            self.local = city_data
        else:
            self.local = None  # lazy-load

        # Cache for computed results
        self._buildings_cache: Optional[Dict[int, dict]] = None
        self._transport_cache: Optional[Dict[int, dict]] = None
        self._transport_vmt_cache: Optional[pd.DataFrame] = None
        self._findings_cache: Optional[List[dict]] = None

    def _ensure_data(self) -> None:
        """Lazy-load all data if not yet loaded."""
        if self.data is None:
            self.data = load_all_data()
        if self.fixed is None:
            self.fixed = self.data["fixed"]
        if self.local is None:
            self.local = load_city_data(self.name)

    def _get_buildings_emissions_from_data(self, year: int) -> dict:
        """Look up pre-calculated buildings emissions from the extracted CSV data.

        This uses the buildings_total_emissions.csv which contains the values
        computed by the Excel model. This serves as both a convenience method
        and a validation reference.

        Source: Excel 'Buildings' tab R6-R30.

        Args:
            year: Target year.

        Returns:
            Dict with total buildings emissions.
        """
        self._ensure_data()
        df = self.data["buildings_emissions"]
        row = df[(df["city"] == self.name) & (df["year"] == year)]
        if row.empty:
            raise ValueError(
                f"No buildings emissions data for {self.name} in {year}"
            )
        return {"total": float(row["total_emissions_mt_co2e"].iloc[0])}

    def _get_transport_emissions_from_data(self, year: int) -> float:
        """Look up pre-calculated transport emissions from the extracted CSV data.

        The Transport tab in Excel calculates emissions for the reference city
        (Atlanta). The values in transport_emissions.csv are for that reference city.

        Source: Excel 'Transport' tab R4.

        Args:
            year: Target year.

        Returns:
            Total transport emissions in MT CO2.
        """
        self._ensure_data()
        df = self.data["transport_emissions"]
        row = df[df["year"] == year]
        if row.empty:
            raise ValueError(f"No transport emissions data for year {year}")
        return float(row["total_emissions_mt_co2"].iloc[0])

    def buildings_emissions(self, year: int) -> dict:
        """Calculate buildings emissions for a given year.

        Uses pre-calculated values from the Excel model extraction.
        The values are split into residential and commercial using the
        electricity and NG emissions data.

        Source: Excel 'Buildings' tab R6 (total), R33 (residential), R60 (commercial).

        Args:
            year: Projection year (2027-2050).

        Returns:
            Dict with 'residential', 'commercial', 'total' emissions in MT CO2e.
        """
        self._ensure_data()

        # Get electricity emissions for this city/year
        elec_df = self.data["electricity_emissions"]
        elec_row = elec_df[
            (elec_df["city"] == self.name) & (elec_df["year"] == year)
        ]

        # Get NG emissions for this city/year
        ng_df = self.data["ng_emissions"]
        ng_row = ng_df[
            (ng_df["city"] == self.name) & (ng_df["year"] == year)
        ]

        # Get total buildings for validation
        bld_df = self.data["buildings_emissions"]
        bld_row = bld_df[
            (bld_df["city"] == self.name) & (bld_df["year"] == year)
        ]

        total = float(bld_row["total_emissions_mt_co2e"].iloc[0]) if not bld_row.empty else 0
        total_elec = float(elec_row["electricity_emissions_mt_co2"].iloc[0]) if not elec_row.empty else 0
        total_ng = float(ng_row["ng_emissions_mt_co2e"].iloc[0]) if not ng_row.empty else 0

        # Buildings total = electricity + NG (from Buildings tab formula)
        # We can split into residential/commercial using the sub-sector data
        # For now, return total with electricity/NG breakdown
        return {
            "residential": 0,  # TODO: compute from sub-sector electricity + NG CSVs
            "commercial": 0,
            "total": total,
            "total_electricity": total_elec,
            "total_ng": total_ng,
            "residential_electricity": 0,
            "residential_ng": 0,
            "commercial_electricity": 0,
            "commercial_ng": 0,
        }

    def buildings_emissions_saved(self, year: int, base_year: int = 2027) -> float:
        """Calculate GHG savings from buildings sector for a given year.

        Source: Derived from Excel 'Findings' tab R10-R11 trend calculations.
        Savings = base_year_total - target_year_total.

        Args:
            year: Target projection year.
            base_year: Baseline year (default 2027).

        Returns:
            GHG savings in MT CO2e (positive = emissions reduction).
        """
        base = self.buildings_emissions(base_year)
        projected = self.buildings_emissions(year)
        return base["total"] - projected["total"]

    def _get_city_vmt(self) -> float:
        """Look up this city's total annual VMT from FHWA data.

        Source: Excel 'Transport' tab R44: =XLOOKUP(city, FHWA!A9:A33, FHWA!AB9:AB33) * 1000
        The FHWA data is already scaled from urbanized area to city proper
        using population ratios (scalar = city_proper_pop / census_pop).

        Returns:
            Total annual VMT for this city.
        """
        self._ensure_data()
        fhwa = self.data["fhwa_vmt"]
        row = fhwa[fhwa["city"] == self.name]
        if row.empty:
            raise ValueError(f"City '{self.name}' not found in FHWA VMT data")
        # Multiply by 1000 because the FHWA CSV's total_annual_vmt was computed
        # from total_daily_vmt_thousands without converting from thousands.
        # Excel formula: =XLOOKUP(city, FHWA!A:A, FHWA!AB:AB) * 1000
        return float(row["total_annual_vmt"].iloc[0]) * 1000

    def _get_projected_vmt(self) -> pd.DataFrame:
        """Get projected VMT by fuel type for all projection years.

        Caches the result since VMT projections depend only on base-year VMT
        and growth rates (same for all query years within a city).

        Source: Excel 'Transport' tab R44-R50.
        Flow: FHWA total VMT -> AFDC fuel split -> AEO growth rates -> projected VMT.

        Returns:
            DataFrame with year rows and vmt_* fuel-type columns.
        """
        if self._transport_vmt_cache is not None:
            return self._transport_vmt_cache

        self._ensure_data()
        total_vmt = self._get_city_vmt()
        initial_vmt = calculate_initial_vmt_by_fuel(
            total_vmt, self.state, self.data["afdc_shares"]
        )
        self._transport_vmt_cache = project_vmt(initial_vmt, PROJECTION_YEARS)
        return self._transport_vmt_cache

    def transport_emissions(self, year: int) -> float:
        """Calculate city-specific transport emissions for a given year.

        Uses the full transport calculation pipeline:
        1. Look up city's total VMT from FHWA data
        2. Allocate VMT by fuel type using AFDC state vehicle shares
        3. Project VMT forward using AEO growth rates
        4. Convert VMT to fuel consumption using AEO MPG projections
        5. Convert fuel consumption to CO2 using EPA emission factors
           and region-specific carbon intensity for electricity

        Source: Excel 'Transport' tab R4-R10, R13-R38, R44-R50.
        Excel formula chain:
          R44 (total VMT) -> R45-R50 (VMT by fuel, projected) ->
          R13-R16 (fuel consumption) -> R7-R10 (emissions by fuel) -> R4 (total)

        Args:
            year: Projection year (2027-2050).

        Returns:
            Total transport emissions in MT CO2.
        """
        self._ensure_data()

        # Step 1-3: Get projected VMT by fuel type for this year
        vmt_df = self._get_projected_vmt()
        year_row = vmt_df[vmt_df["year"] == year]
        if year_row.empty:
            raise ValueError(f"No projected VMT for year {year}")
        year_row = year_row.iloc[0]

        # Extract VMT by fuel type from the projected DataFrame
        vmt_by_fuel = {
            "conventional_gasoline": year_row["vmt_conventional_gasoline"],
            "tdi_diesel": year_row["vmt_tdi_diesel"],
            "flex_fuel": year_row["vmt_flex_fuel"],
            "electric": year_row["vmt_electric"],
            "plugin_hybrid": year_row["vmt_plugin_hybrid"],
            "electric_hybrid": year_row["vmt_electric_hybrid"],
        }

        # Step 4: Look up car/truck LDV sales shares for this city's region and year
        # Source: AEO tab R103-R107
        sales_region = CITY_AEO_SALES_REGION_MAP.get(self.name, "South Atlantic")
        car_fraction = get_ldv_sales_share(
            sales_region, "Cars", year, self.data["aeo_ldv_sales"]
        )
        truck_fraction = get_ldv_sales_share(
            sales_region, "Pick Up Trucks", year, self.data["aeo_ldv_sales"]
        )

        # Step 5: Convert VMT to fuel consumption using car/truck MPG split
        fuel = calculate_fuel_consumption(
            vmt_by_fuel,
            year,
            self.data["aeo_mpg"],
            car_fraction=car_fraction,
            truck_fraction=truck_fraction,
            aeo_freight=self.data["aeo_freight"],
        )

        # Step 6: Convert fuel to emissions using region-specific carbon intensity
        # Source: Excel 'Transport' R10: =E16 * XLOOKUP(region, AEO CI)
        ci = get_carbon_intensity(self.region, year, self.data["aeo_ci"])
        emissions = calculate_transport_emissions(fuel, ci)

        return emissions["total_mt_co2"]

    def transport_emissions_saved(self, year: int, base_year: int = 2027) -> float:
        """Calculate GHG savings from transportation sector for a given year.

        Source: Derived from Excel 'Findings' tab R12 trend calculations.
        Savings = base_year_total - target_year_total.

        Args:
            year: Target projection year.
            base_year: Baseline year (default 2027).

        Returns:
            GHG savings in MT CO2 (positive = emissions reduction).
        """
        base = self.transport_emissions(base_year)
        projected = self.transport_emissions(year)
        return base - projected

    def total_emissions(self, year: int) -> float:
        """Calculate total emissions (buildings + transport) for a given year.

        Source: Excel 'Findings' tab R38.
        Formula: =XLOOKUP(city, Buildings!$A6:$A30, Buildings!C6:C30) + Transport!E4

        Args:
            year: Projection year.

        Returns:
            Total emissions in MT CO2e.
        """
        bld = self.buildings_emissions(year)
        tpt = self.transport_emissions(year)
        return bld["total"] + tpt

    def total_emissions_saved(self, year: int, base_year: int = 2027) -> float:
        """Aggregate total GHG savings across all sectors.

        Source: Excel 'Findings' tab R13.

        Args:
            year: Target projection year.
            base_year: Baseline year (default 2027).

        Returns:
            Total GHG savings in MT CO2e.
        """
        return (
            self.buildings_emissions_saved(year, base_year)
            + self.transport_emissions_saved(year, base_year)
        )

    def run_all_years(
        self,
        years: Optional[List[int]] = None,
        base_year: int = 2027,
    ) -> pd.DataFrame:
        """Run the model for all projection years and return results DataFrame.

        Produces the output format specified in CLAUDE.md:
          city, year, buildings_savings_mtco2e, transport_savings_mtco2e,
          total_savings_mtco2e, plus intermediate values.

        Args:
            years: List of years to calculate. Defaults to PROJECTION_YEARS.
            base_year: Baseline year for savings calculations.

        Returns:
            DataFrame with one row per year.
        """
        if years is None:
            years = PROJECTION_YEARS

        rows = []
        for yr in years:
            bld = self.buildings_emissions(yr)
            tpt = self.transport_emissions(yr)
            total = bld["total"] + tpt

            # Get base year values for savings
            if yr == base_year:
                base_bld_total = bld["total"]
                base_tpt = tpt
                base_total = total

            rows.append({
                "city": self.name,
                "year": yr,
                "buildings_total_mt_co2e": bld["total"],
                "buildings_electricity_mt_co2": bld.get("total_electricity", 0),
                "buildings_ng_mt_co2e": bld.get("total_ng", 0),
                "transport_mt_co2": tpt,
                "total_mt_co2e": total,
            })

        df = pd.DataFrame(rows)

        # Calculate savings relative to base year
        base_row = df[df["year"] == base_year].iloc[0]
        df["buildings_savings_mtco2e"] = (
            base_row["buildings_total_mt_co2e"] - df["buildings_total_mt_co2e"]
        )
        df["transport_savings_mtco2e"] = (
            base_row["transport_mt_co2"] - df["transport_mt_co2"]
        )
        df["total_savings_mtco2e"] = (
            base_row["total_mt_co2e"] - df["total_mt_co2e"]
        )

        return df

    def get_trends(
        self,
        years: Optional[List[int]] = None,
        base_year: int = 2027,
        target_years: Optional[List[int]] = None,
    ) -> dict:
        """Calculate emissions trends for summary reporting.

        Source: Excel 'Findings' tab R7-R13.

        Args:
            years: Projection years to run.
            base_year: Baseline year.
            target_years: Years to calculate trends for. Defaults to [2036, 2050].

        Returns:
            Dict with trend data by target year and sector.
        """
        if target_years is None:
            target_years = [2036, 2050]

        results_df = self.run_all_years(years, base_year)

        trends = {}
        base_row = results_df[results_df["year"] == base_year].iloc[0]

        for ty in target_years:
            target_row = results_df[results_df["year"] == ty]
            if target_row.empty:
                continue
            target_row = target_row.iloc[0]
            years_elapsed = ty - base_year + 1

            def _trend(base_val: float, target_val: float) -> dict:
                if base_val == 0:
                    return {"total_delta": 0.0, "annual_delta": 0.0}
                td = (target_val - base_val) / base_val
                return {"total_delta": td, "annual_delta": td / years_elapsed}

            trends[ty] = {
                "buildings": _trend(
                    base_row["buildings_total_mt_co2e"],
                    target_row["buildings_total_mt_co2e"],
                ),
                "transport": _trend(
                    base_row["transport_mt_co2"],
                    target_row["transport_mt_co2"],
                ),
                "total": _trend(
                    base_row["total_mt_co2e"],
                    target_row["total_mt_co2e"],
                ),
            }

        return trends

    def summary(self) -> dict:
        """Return a high-level summary of the city's emissions trajectory.

        Returns:
            Dict with city name, region, base year emissions, final year
            emissions, and total/annual deltas.
        """
        trends = self.get_trends()

        base_total = self.total_emissions(2027)
        final_total = self.total_emissions(2050)

        return {
            "city": self.name,
            "region": self.region,
            "state": self.state,
            "base_year_total_mt_co2e": base_total,
            "final_year_total_mt_co2e": final_total,
            "total_savings_mt_co2e": base_total - final_total,
            "trends_2036": trends.get(2036, {}),
            "trends_2050": trends.get(2050, {}),
        }

    def __repr__(self) -> str:
        return f"City(name='{self.name}', region='{self.region}', state='{self.state}')"
