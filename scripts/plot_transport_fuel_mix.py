"""Plot transportation fuel mix over time for 5 cities.

Two-panel figure:
  Left  — Stacked area: average emissions by fuel type across 5 cities (2027-2050)
  Right — Grouped bars: each city's fuel mix in 2027 vs 2050
"""
import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from bau.city import City
from bau.config import CITY_REGION_MAP, CITY_AEO_SALES_REGION_MAP
from bau.data_loader import load_all_data, get_carbon_intensity, get_ldv_sales_share
from bau.transport import project_vmt, calculate_fuel_consumption, calculate_transport_emissions

CITIES = ["Atlanta", "Charlotte", "Nashville", "Cleveland", "Philadelphia"]
YEARS = list(range(2027, 2051))

# Emission bucket colors
FUEL_COLORS = {
    "gasoline_mt_co2": "#e05c2a",
    "diesel_mt_co2":   "#8b5e3c",
    "ethanol_mt_co2":  "#5aaf5a",
    "electricity_mt_co2": "#4a90d9",
}
FUEL_LABELS = {
    "gasoline_mt_co2": "Gasoline",
    "diesel_mt_co2":   "Diesel",
    "ethanol_mt_co2":  "Ethanol",
    "electricity_mt_co2": "Electricity",
}


def get_fuel_emissions_series(city_name: str, all_data: dict) -> pd.DataFrame:
    """Compute annual transport emissions by fuel type for one city.

    Replicates city.transport_emissions() but captures the per-fuel breakdown
    from calculate_transport_emissions() before aggregation.

    Returns:
        DataFrame with columns [year, gasoline_mt_co2, diesel_mt_co2,
        ethanol_mt_co2, electricity_mt_co2, total_mt_co2].
    """
    from bau.config import CITY_STATE_MAP, CITY_REGION_MAP

    state = CITY_STATE_MAP[city_name]
    region = CITY_REGION_MAP[city_name]
    sales_region = CITY_AEO_SALES_REGION_MAP.get(city_name, "South Atlantic")

    # --- VMT projection ---
    fhwa = all_data["fhwa_vmt"]
    row = fhwa[fhwa["city"] == city_name].iloc[0]
    total_vmt = float(row["total_annual_vmt"]) * 1000

    # AFDC shares dict
    col_map = {
        "gasoline": "conventional_gasoline",
        "diesel": "tdi_diesel",
        "ethanol_flex_e85": "flex_fuel",
        "electric_ev": "electric",
        "plug-in_hybrid_electric_phev": "plugin_hybrid",
        "hybrid_electric_hev": "electric_hybrid",
        "biodiesel": "biodiesel",
    }
    shares_df = all_data["afdc_shares"]
    state_row = shares_df[
        (shares_df["state"] == state) & (shares_df["year"] == 2024)
    ].iloc[0]
    afdc_shares = {v: float(state_row.get(k, 0)) for k, v in col_map.items()}

    deltas_df = all_data["afdc_growth_deltas"]
    delta_row = deltas_df[deltas_df["state"] == state].iloc[0]
    afdc_deltas = {v: float(delta_row.get(k, 0)) for k, v in col_map.items()}

    vmt_df = project_vmt(total_vmt, afdc_shares, afdc_deltas, YEARS)

    # --- Per-year fuel consumption & emissions ---
    rows = []
    for yr in YEARS:
        yr_row = vmt_df[vmt_df["year"] == yr].iloc[0]
        vmt_by_fuel = {
            "conventional_gasoline": yr_row["vmt_conventional_gasoline"],
            "tdi_diesel":            yr_row["vmt_tdi_diesel"],
            "flex_fuel":             yr_row["vmt_flex_fuel"],
            "electric":              yr_row["vmt_electric"],
            "plugin_hybrid":         yr_row["vmt_plugin_hybrid"],
            "electric_hybrid":       yr_row["vmt_electric_hybrid"],
            "biodiesel":             yr_row.get("vmt_biodiesel", 0),
        }
        car_frac = get_ldv_sales_share(sales_region, "Cars", yr, all_data["aeo_ldv_sales"])
        truck_frac = get_ldv_sales_share(sales_region, "Pick Up Trucks", yr, all_data["aeo_ldv_sales"])

        fuel = calculate_fuel_consumption(
            vmt_by_fuel, yr, all_data["aeo_mpg"],
            car_fraction=car_frac, truck_fraction=truck_frac,
            aeo_freight=all_data["aeo_freight"],
        )
        ci = get_carbon_intensity(region, yr, all_data["aeo_ci"])
        em = calculate_transport_emissions(fuel, ci)

        rows.append({
            "year":               yr,
            "gasoline_mt_co2":    em["gasoline_mt_co2"],
            "diesel_mt_co2":      em["diesel_mt_co2"],
            "ethanol_mt_co2":     em["ethanol_mt_co2"],
            "electricity_mt_co2": em["electricity_mt_co2"],
            "total_mt_co2":       em["total_mt_co2"],
        })

    return pd.DataFrame(rows)


# ── Load data & compute ──────────────────────────────────────────────────────
print("Loading data and computing fuel mix series...")
all_data = load_all_data()

city_series = {}
for c in CITIES:
    print(f"  {c}...")
    city_series[c] = get_fuel_emissions_series(c, all_data)

fuel_cols = ["gasoline_mt_co2", "diesel_mt_co2", "ethanol_mt_co2", "electricity_mt_co2"]

# Average across cities for the stacked area
avg_df = pd.DataFrame({"year": YEARS})
for fc in fuel_cols:
    avg_df[fc] = np.mean([city_series[c][fc].values for c in CITIES], axis=0)

# ── Figure ───────────────────────────────────────────────────────────────────
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
fig.suptitle("5-City Transportation Fuel Mix", fontsize=14, fontweight="bold", y=1.01)

# ── Panel 1: Line chart — one line per fuel type (average emissions) ─────────
line_styles = {"gasoline_mt_co2": "-", "diesel_mt_co2": "--",
               "ethanol_mt_co2": "-.", "electricity_mt_co2": ":"}
for fc in fuel_cols:
    ax1.plot(YEARS, avg_df[fc].values / 1e6,
             label=FUEL_LABELS[fc],
             color=FUEL_COLORS[fc],
             linestyle=line_styles[fc],
             linewidth=2)

ax1.set_xlabel("Year")
ax1.set_ylabel("Average Transport Emissions (million MT CO₂)")
ax1.set_title("Average Fuel Mix Over Time\n(5-city average, 2027–2050)")
ax1.legend(loc="right", fontsize=9)
ax1.set_xlim(2027, 2050)
ax1.grid(True, alpha=0.2)

# ── Panel 2: Grouped bar — each city, 2027 vs 2050 ──────────────────────────
n_cities = len(CITIES)
x = np.arange(n_cities)
bar_w = 0.35
city_colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]

for i, yr in enumerate([2027, 2050]):
    bottoms = np.zeros(n_cities)
    for fc in fuel_cols:
        heights = np.array([
            city_series[c].loc[city_series[c]["year"] == yr, fc].iloc[0] / 1e6
            for c in CITIES
        ])
        offset = -bar_w / 2 if yr == 2027 else bar_w / 2
        ax2.bar(x + offset, heights, bar_w,
                bottom=bottoms,
                color=FUEL_COLORS[fc],
                alpha=0.9 if yr == 2027 else 0.55,
                edgecolor="white", linewidth=0.4)
        bottoms += heights

# Label total bar heights
for i, yr in enumerate([2027, 2050]):
    offset = -bar_w / 2 if yr == 2027 else bar_w / 2
    for j, c in enumerate(CITIES):
        total = sum(
            city_series[c].loc[city_series[c]["year"] == yr, fc].iloc[0]
            for fc in fuel_cols
        ) / 1e6
        ax2.text(j + offset, total + 0.005, f"{total:.2f}",
                 ha="center", va="bottom", fontsize=6.5, rotation=90)

ax2.set_xticks(x)
ax2.set_xticklabels(CITIES, fontsize=9)
ax2.set_xlabel("")
ax2.set_ylabel("Transport Emissions (million MT CO₂)")
ax2.set_title("Fuel Mix by City: 2027 vs 2050\n(dark = 2027, light = 2050)")
ax2.grid(True, alpha=0.2, axis="y")

# Combined legend for fuel types + year shade
legend_patches = [
    mpatches.Patch(color=FUEL_COLORS[fc], label=FUEL_LABELS[fc])
    for fc in fuel_cols
]
legend_patches += [
    mpatches.Patch(color="gray", alpha=0.9, label="2027"),
    mpatches.Patch(color="gray", alpha=0.55, label="2050"),
]
ax2.legend(handles=legend_patches, fontsize=8, loc="upper right", ncol=2)

plt.tight_layout()
out = "outputs/transport_fuel_mix_5city.png"
plt.savefig(out, dpi=150, bbox_inches="tight")
print(f"Saved: {out}")
plt.close()
