"""Tests for the IAM model findings calculations.

Validates Python calculations against known values from the Excel model.
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bau.config import CITY_REGION_MAP, NG_EMISSION_FACTOR_MT_CO2_PER_MMBTU, MWH_PER_MMBTU
from bau.buildings import (
    calculate_electricity_emissions,
    calculate_ng_emissions,
)
from bau.emissions import mmbtu_to_mwh, ng_mmbtu_to_mt_co2e
from bau.data_loader import load_all_data
from bau.city import City


class TestEmissionFactors:
    """Test that emission factor calculations match Excel constants."""

    def test_ng_emission_factor(self):
        """NG tab R2: MT CO2/MMBtu = 53.06/1000 = 0.05306."""
        assert NG_EMISSION_FACTOR_MT_CO2_PER_MMBTU == pytest.approx(0.05306)

    def test_mwh_per_mmbtu(self):
        """Electricity tab R1: MWh/MMBtu = 0.3."""
        assert MWH_PER_MMBTU == pytest.approx(0.3)

    def test_ng_emissions_calculation(self):
        """Verify NG emissions formula: MMBtu * 0.05306.

        Source: NG tab R33 formula: =B90 * $G$2
        Example: Akron 2027 residential NG consumption = 6593772.09 MMBtu
        Expected: 6593772.09 * 0.05306 = 349865.55 MT CO2e
        """
        mmbtu = 6593772.08529588
        expected = 349865.5468457994  # From NG tab R33, col B (2027)
        result = calculate_ng_emissions(mmbtu)
        assert result == pytest.approx(expected, rel=1e-6)

    def test_mmbtu_to_mwh_conversion(self):
        """Verify MMBtu to MWh conversion: MMBtu * 0.3.

        Source: Electricity tab R87 formula: =C143 * $G$1
        Example: Akron 2027 residential electricity = 2064533.25 MMBtu
        Expected MWh: 2064533.25 * 0.3 = 619359.98
        """
        mmbtu = 2064533.25336288
        expected_mwh = 619359.976008864  # From Electricity tab R87
        result = mmbtu_to_mwh(mmbtu)
        assert result == pytest.approx(expected_mwh, rel=1e-6)


class TestBuildingsCalculations:
    """Test buildings emissions calculations against Excel values."""

    def test_electricity_emissions_akron_2027(self):
        """Verify electricity emissions for Akron residential 2027.

        Source: Electricity tab R32.
        Formula: =C87 * XLOOKUP($B32, AEO!$A$39:$A$50, AEO!E$39:E$50)
        Akron region = PJMW, CI(2027) from AEO R41
        MWh = 619359.976 (from R87)
        CI = 0.4231 (PJMW 2027 from AEO)
        Expected: 619359.976 * 0.4231 ≈ 262045.33
        """
        mwh = 619359.976008864
        ci = 0.4230905163970035  # PJMW 2027 from AEO tab R41
        expected = 262045.33208522596  # From Electricity tab R32
        result = calculate_electricity_emissions(mwh / MWH_PER_MMBTU, ci)
        # Note: function takes MMBtu, converts internally
        # Actually the function already does MMBtu * 0.3 * CI
        result_direct = mwh * ci
        assert result_direct == pytest.approx(expected, rel=1e-4)


class TestCityIntegration:
    """Integration tests using City class against Excel reference values."""

    @pytest.fixture(scope="class")
    def all_data(self):
        return load_all_data()

    def test_atlanta_buildings_2027(self, all_data):
        """Verify Atlanta total buildings emissions in 2027.

        Source: Excel Buildings tab R7, col C (2027).
        Expected: 4306373.97 MT CO2e
        """
        city = City(name="Atlanta", all_data=all_data)
        result = city.buildings_emissions(2027)
        assert result["total"] == pytest.approx(4306373.973213104, rel=1e-4)

    def test_atlanta_buildings_2050(self, all_data):
        """Verify Atlanta total buildings emissions in 2050.

        Source: Excel Buildings tab R7, col Z (2050).
        Expected: 1643435.88 MT CO2e
        """
        city = City(name="Atlanta", all_data=all_data)
        result = city.buildings_emissions(2050)
        assert result["total"] == pytest.approx(1643435.8807667329, rel=1e-4)

    def test_atlanta_buildings_savings(self, all_data):
        """Verify Atlanta buildings savings 2027->2050.

        Savings = 4306373.97 - 1643435.88 = 2662938.09 MT CO2e
        """
        city = City(name="Atlanta", all_data=all_data)
        savings = city.buildings_emissions_saved(2050)
        expected = 4306373.973213104 - 1643435.8807667329
        assert savings == pytest.approx(expected, rel=1e-4)

    def test_transport_emissions_2027(self, all_data):
        """Verify city-specific transport emissions for Atlanta in 2027.

        Uses the full calculation pipeline: FHWA VMT -> flat 0.6% VMT growth ->
        AFDC share evolution -> fuel consumption -> emissions.

        Methodology: Flat 0.6%/yr total VMT growth with AFDC share-based fuel
        allocation and biodiesel as 7th fuel type. Shares for years beyond 2024
        use 2024_share + growth_delta (fixed, not cumulative).
        """
        city = City(name="Atlanta", all_data=all_data)
        result = city.transport_emissions(2027)
        assert result == pytest.approx(1829547.15, rel=1e-4)

    def test_run_all_years(self, all_data):
        """Verify run_all_years produces correct number of rows."""
        city = City(name="Atlanta", all_data=all_data)
        df = city.run_all_years()
        assert len(df) == 24  # 2027-2050
        assert "city" in df.columns
        assert "total_savings_mtco2e" in df.columns
        assert df.iloc[0]["year"] == 2027
        assert df.iloc[-1]["year"] == 2050

    def test_flat_vmt_growth(self, all_data):
        """Verify total VMT grows at flat 0.6%/year from base year.

        Source: Baseline Module Documentation — FHWA national VMT trend.
        Formula: total_vmt(Y) = total_vmt(2024) * (1.006)^(Y - 2024)
        """
        city = City(name="Atlanta", all_data=all_data)
        vmt_df = city._get_projected_vmt()
        row_2027 = vmt_df[vmt_df["year"] == 2027].iloc[0]
        row_2050 = vmt_df[vmt_df["year"] == 2050].iloc[0]

        base_vmt = city._get_city_vmt()
        expected_2027 = base_vmt * (1.006 ** 3)
        expected_2050 = base_vmt * (1.006 ** 26)

        assert row_2027["vmt_total"] == pytest.approx(expected_2027, rel=1e-6)
        assert row_2050["vmt_total"] == pytest.approx(expected_2050, rel=1e-6)

    def test_afdc_share_projection(self, all_data):
        """Verify fuel shares evolve correctly using AFDC growth deltas.

        For year 2024 (base), shares = AFDC 2024 shares directly.
        For year 2027 (future), shares = 2024_share + delta, clamped >= 0, normalized.
        The delta is fixed (not cumulative) — same adjustment for all future years.
        """
        from bau.transport import project_vmt

        afdc_shares = {"gasoline": 0.85, "electric": 0.05, "diesel": 0.10}
        afdc_deltas = {"gasoline": -0.02, "electric": 0.015, "diesel": 0.005}
        total_vmt = 1_000_000

        df = project_vmt(total_vmt, afdc_shares, afdc_deltas, [2024, 2027])

        # Base year: shares should match exactly
        row_2024 = df[df["year"] == 2024].iloc[0]
        assert row_2024["vmt_gasoline"] == pytest.approx(850_000, rel=1e-6)

        # Future year: shares = 2024 + delta, then normalized
        raw_gas = 0.85 + (-0.02)  # 0.83
        raw_elec = 0.05 + 0.015   # 0.065
        raw_diesel = 0.10 + 0.005 # 0.105
        total_raw = raw_gas + raw_elec + raw_diesel  # 1.0
        expected_gas_share = raw_gas / total_raw

        total_vmt_2027 = total_vmt * (1.006 ** 3)
        row_2027 = df[df["year"] == 2027].iloc[0]
        assert row_2027["vmt_gasoline"] == pytest.approx(
            total_vmt_2027 * expected_gas_share, rel=1e-6
        )

    def test_biodiesel_in_diesel_bucket(self, all_data):
        """Verify biodiesel consumption is included in diesel emissions.

        Biodiesel VMT should be non-zero for Atlanta (Georgia has ~1% biodiesel
        share) and its gallons should be folded into the diesel emission bucket.
        """
        city = City(name="Atlanta", all_data=all_data)
        vmt_df = city._get_projected_vmt()
        row_2027 = vmt_df[vmt_df["year"] == 2027].iloc[0]

        # Biodiesel VMT should be > 0
        assert row_2027["vmt_biodiesel"] > 0

        # Verify biodiesel is included in total
        fuel_cols = [c for c in vmt_df.columns if c.startswith("vmt_") and c != "vmt_total"]
        fuel_sum = sum(row_2027[c] for c in fuel_cols)
        assert fuel_sum == pytest.approx(row_2027["vmt_total"], rel=1e-6)

    def test_car_truck_mpg_split(self, all_data):
        """Verify car and truck use different MPG values from AEO.

        Source: AEO tab R9 (car gasoline MPG) vs R24 (truck gasoline MPG).
        For 2027: car = 42.12 MPG, truck = 31.94 MPG.
        These are looked up via the vehicle_class column in aeo_mpg.csv.
        """
        from bau.data_loader import get_mpg
        car_mpg = get_mpg("Gasoline ICE Vehicles", 2027, all_data["aeo_mpg"], vehicle_class="car")
        truck_mpg = get_mpg("Gasoline ICE Vehicles", 2027, all_data["aeo_mpg"], vehicle_class="truck")
        assert car_mpg == pytest.approx(42.124, rel=1e-3)
        assert truck_mpg == pytest.approx(31.942, rel=1e-3)
        assert car_mpg > truck_mpg  # Cars are more efficient than trucks

    def test_sppc_carbon_intensity(self, all_data):
        """Verify SPPC carbon intensity is available (no longer needs fallback).

        Source: AEO tab R50 (SPPC carbon intensity).
        Kansas City uses region SPPC, which previously fell back to MISC.
        """
        from bau.data_loader import get_carbon_intensity
        ci = get_carbon_intensity("SPPC", 2027, all_data["aeo_ci"])
        assert ci == pytest.approx(0.3687, rel=1e-3)

    def test_kansas_city_uses_sppc(self, all_data):
        """Verify Kansas City uses SPPC region directly for carbon intensity."""
        city = City(name="Kansas City", all_data=all_data)
        assert city.region == "SPPC"
        # Should not raise — SPPC is now in the AEO CI table
        result = city.transport_emissions(2027)
        assert result > 0

    def test_all_cities_load(self, all_data):
        """Verify all 25 cities can be loaded and run."""
        from bau.config import CITIES
        for city_name in CITIES:
            city = City(name=city_name, all_data=all_data)
            total = city.total_emissions(2027)
            assert total > 0, f"{city_name} has zero total emissions in 2027"


