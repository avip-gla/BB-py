"""Plot 5-city forecast comparison with normalized 0-100% y-axis.

Same 3-panel layout as plot_5city_forecast.py but with:
- Total emissions y-axis: 0-100% (2027-2035)
- Grid carbon intensity y-axis: 0-100% (2026-2035, CI data available from 2026)
"""
import sys
sys.path.insert(0, ".")

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from bau.data_loader import load_all_data, get_carbon_intensity
from bau.config import CITY_REGION_MAP

# --- Data Setup ---
cities = ["Atlanta", "Charlotte", "Nashville", "Cleveland", "Philadelphia"]
colors = {"Atlanta": "#1f77b4", "Charlotte": "#ff7f0e", "Nashville": "#2ca02c",
          "Cleveland": "#d62728", "Philadelphia": "#9467bd"}

# Load city results
dfs = []
for c in cities:
    df = pd.read_csv(f"outputs/csv/{c.lower()}_results.csv")
    dfs.append(df)
all_df = pd.concat(dfs)

# Filter to 2026-2035
mask = (all_df["year"] >= 2026) & (all_df["year"] <= 2035)
df = all_df[mask].copy()

# Load carbon intensity data (available from 2026)
data = load_all_data()
ci_df = data["aeo_ci"]
ci_years = list(range(2026, 2036))

# --- Figure Setup (2-panel: emissions + carbon intensity) ---
fig, axes = plt.subplots(1, 2, figsize=(14, 6))
fig.suptitle("5-City Emissions Forecast: 2026–2035 (Normalized)", fontsize=15, fontweight="bold", y=1.02)

# ============================================================
# Plot 1: Total Emissions Decline (indexed to 2027 = 100%)
# ============================================================
ax1 = axes[0]
for city in cities:
    cdf = df[df["city"] == city].sort_values("year")
    base = cdf["total_mt_co2e"].iloc[0]
    indexed = cdf["total_mt_co2e"] / base * 100
    ax1.plot(cdf["year"], indexed, color=colors[city], linewidth=2, label=city, marker="o", markersize=4)

ax1.axhline(y=100, color="gray", linestyle="--", alpha=0.3)
ax1.set_xlabel("Year")
ax1.set_ylabel("Total Emissions (2026 = 100%)")
ax1.set_title("Total Emissions Decline")
ax1.legend(fontsize=8, loc="upper right")
ax1.set_ylim(0, 105)
ax1.yaxis.set_major_formatter(mticker.PercentFormatter(100, decimals=0))
ax1.grid(True, alpha=0.2)

# Add annotation for average decline
declines = []
for city in cities:
    cdf = df[df["city"] == city].sort_values("year")
    d = (cdf["total_mt_co2e"].iloc[-1] / cdf["total_mt_co2e"].iloc[0] - 1) * 100
    declines.append(d)
avg_decline = np.mean(declines)
ax1.annotate(f"Avg: {avg_decline:.0f}%", xy=(2035, 100 + avg_decline),
             fontsize=9, fontweight="bold", color="black",
             bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", edgecolor="gray"))

# ============================================================
# Plot 2: Carbon Intensity Decline by Region (2026-2035)
# ============================================================
ax2 = axes[1]
for city in cities:
    region = CITY_REGION_MAP[city]
    ci_vals = [get_carbon_intensity(region, y, ci_df) for y in ci_years]
    ci_base = ci_vals[0]
    ci_indexed = [v / ci_base * 100 for v in ci_vals]
    ax2.plot(ci_years, ci_indexed, color=colors[city], linewidth=2,
             label=f"{city} ({region})", marker="s", markersize=4)

ax2.axhline(y=100, color="gray", linestyle="--", alpha=0.3)
ax2.set_xlabel("Year")
ax2.set_ylabel("Carbon Intensity (2026 = 100%)")
ax2.set_title("Grid Carbon Intensity Decline")
ax2.legend(fontsize=7, loc="upper right")
ax2.set_ylim(0, 105)
ax2.yaxis.set_major_formatter(mticker.PercentFormatter(100, decimals=0))
ax2.grid(True, alpha=0.2)

# Add annotation for average CI decline
ci_declines = []
for city in cities:
    region = CITY_REGION_MAP[city]
    ci_26 = get_carbon_intensity(region, 2026, ci_df)
    ci_35 = get_carbon_intensity(region, 2035, ci_df)
    ci_declines.append((ci_35 / ci_26 - 1) * 100)
avg_ci = np.mean(ci_declines)
ax2.annotate(f"Avg: {avg_ci:.0f}%", xy=(2035, 100 + avg_ci),
             fontsize=9, fontweight="bold", color="black",
             bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", edgecolor="gray"))

plt.tight_layout()
plt.savefig("outputs/5city_forecast_normalized.png", dpi=150, bbox_inches="tight")
print("Saved: outputs/5city_forecast_normalized.png")
plt.close()

# ============================================================
# Separate figure: Sector & fuel evolution over time (5-city avg)
# ============================================================
fig3, (ax3a, ax3b) = plt.subplots(1, 2, figsize=(14, 6))
fig3.suptitle("5-City Average: Sector & Fuel Mix (2026–2035)", fontsize=14, fontweight="bold", y=1.02)

plot_years = sorted(df["year"].unique())

# Aggregate 5-city averages by year
avg_bld = []
avg_trans = []
avg_elec = []
avg_ng = []

for yr in plot_years:
    ydf = df[df["year"] == yr]
    avg_bld.append(ydf["buildings_total_mt_co2e"].mean())
    avg_trans.append(ydf["transport_mt_co2"].mean())
    avg_elec.append(ydf["buildings_electricity_mt_co2"].mean())
    avg_ng.append(ydf["buildings_ng_mt_co2e"].mean())

avg_bld = np.array(avg_bld)
avg_trans = np.array(avg_trans)
avg_elec = np.array(avg_elec)
avg_ng = np.array(avg_ng)

# Panel 1: Sector — Buildings vs Transport (line chart)
ax3a.plot(plot_years, avg_bld / 1e6, color="#4a90d9", linewidth=2.5,
          marker="o", markersize=5, label="Buildings")
ax3a.plot(plot_years, avg_trans / 1e6, color="#e8a838", linewidth=2.5,
          marker="s", markersize=5, label="Transport")
ax3a.fill_between(plot_years, avg_bld / 1e6, alpha=0.1, color="#4a90d9")
ax3a.fill_between(plot_years, avg_trans / 1e6, alpha=0.1, color="#e8a838")
ax3a.set_xlabel("Year")
ax3a.set_ylabel("Avg Emissions (M MT CO₂e)")
ax3a.set_title("Sector Emissions")
ax3a.legend(fontsize=9, loc="upper right")
ax3a.set_ylim(0, ax3a.get_ylim()[1] * 1.05)
ax3a.grid(True, alpha=0.2)

# Annotate % change
bld_chg = (avg_bld[-1] / avg_bld[0] - 1) * 100
trans_chg = (avg_trans[-1] / avg_trans[0] - 1) * 100
ax3a.annotate(f"{bld_chg:+.0f}%", xy=(plot_years[-1], avg_bld[-1] / 1e6),
              xytext=(5, 5), textcoords="offset points",
              fontsize=9, fontweight="bold", color="#4a90d9")
ax3a.annotate(f"{trans_chg:+.0f}%", xy=(plot_years[-1], avg_trans[-1] / 1e6),
              xytext=(5, -12), textcoords="offset points",
              fontsize=9, fontweight="bold", color="#e8a838")

# Panel 2: Buildings fuel — Electricity vs NG (line chart)
ax3b.plot(plot_years, avg_elec / 1e6, color="#5cb85c", linewidth=2.5,
          marker="o", markersize=5, label="Electricity CO₂")
ax3b.plot(plot_years, avg_ng / 1e6, color="#c9302c", linewidth=2.5,
          marker="s", markersize=5, label="Natural Gas CO₂")
ax3b.fill_between(plot_years, avg_elec / 1e6, alpha=0.1, color="#5cb85c")
ax3b.fill_between(plot_years, avg_ng / 1e6, alpha=0.1, color="#c9302c")
ax3b.set_xlabel("Year")
ax3b.set_ylabel("Avg Buildings Emissions (M MT CO₂e)")
ax3b.set_title("Buildings Fuel Mix")
ax3b.legend(fontsize=9, loc="upper right")
ax3b.set_ylim(0, ax3b.get_ylim()[1] * 1.05)
ax3b.grid(True, alpha=0.2)

# Annotate % change
elec_chg = (avg_elec[-1] / avg_elec[0] - 1) * 100
ng_chg = (avg_ng[-1] / avg_ng[0] - 1) * 100
ax3b.annotate(f"{elec_chg:+.0f}%", xy=(plot_years[-1], avg_elec[-1] / 1e6),
              xytext=(5, 5), textcoords="offset points",
              fontsize=9, fontweight="bold", color="#5cb85c")
ax3b.annotate(f"{ng_chg:+.0f}%", xy=(plot_years[-1], avg_ng[-1] / 1e6),
              xytext=(5, -12), textcoords="offset points",
              fontsize=9, fontweight="bold", color="#c9302c")

plt.tight_layout()
plt.savefig("outputs/5city_sector_source.png", dpi=150, bbox_inches="tight")
print("Saved: outputs/5city_sector_source.png")
plt.close()
