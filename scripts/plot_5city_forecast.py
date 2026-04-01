"""Plot 5-city forecast comparison: emissions, carbon intensity, and sector breakdown.

Generates 3-panel figure showing key trends from 2027-2035 for
Atlanta, Charlotte, Nashville, Cleveland, and Philadelphia.
"""
import sys
sys.path.insert(0, ".")

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from iam.data_loader import load_all_data, get_carbon_intensity
from iam.config import CITY_REGION_MAP

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

# Load carbon intensity data
data = load_all_data()
ci_df = data["aeo_ci"]
years = list(range(2026, 2036))

# --- Figure Setup ---
fig, axes = plt.subplots(1, 3, figsize=(18, 6))
fig.suptitle("5-City Emissions Forecast: 2027–2035", fontsize=15, fontweight="bold", y=1.02)

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
ax1.axhline(y=70, color="gray", linestyle=":", alpha=0.3)
ax1.set_xlabel("Year")
ax1.set_ylabel("Total Emissions (2027 = 100%)")
ax1.set_title("Total Emissions Decline")
ax1.legend(fontsize=8, loc="lower left")
ax1.set_ylim(55, 105)
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
# Plot 2: Carbon Intensity Decline by Region
# ============================================================
ax2 = axes[1]
for city in cities:
    region = CITY_REGION_MAP[city]
    ci_vals = [get_carbon_intensity(region, y, ci_df) for y in years]
    ci_base = ci_vals[0]
    ci_indexed = [v / ci_base * 100 for v in ci_vals]
    ax2.plot(years, ci_indexed, color=colors[city], linewidth=2,
             label=f"{city} ({region})", marker="s", markersize=4)

ax2.axhline(y=100, color="gray", linestyle="--", alpha=0.3)
ax2.axhline(y=40, color="gray", linestyle=":", alpha=0.3)
ax2.set_xlabel("Year")
ax2.set_ylabel("Carbon Intensity (2027 = 100%)")
ax2.set_title("Grid Carbon Intensity Decline")
ax2.legend(fontsize=7, loc="upper right")
ax2.set_ylim(15, 110)
ax2.yaxis.set_major_formatter(mticker.PercentFormatter(100, decimals=0))
ax2.grid(True, alpha=0.2)

# Add annotation for average CI decline
ci_declines = []
for city in cities:
    region = CITY_REGION_MAP[city]
    ci_27 = get_carbon_intensity(region, 2027, ci_df)
    ci_35 = get_carbon_intensity(region, 2035, ci_df)
    ci_declines.append((ci_35 / ci_27 - 1) * 100)
avg_ci = np.mean(ci_declines)
ax2.annotate(f"Avg: {avg_ci:.0f}%", xy=(2035, 100 + avg_ci),
             fontsize=9, fontweight="bold", color="black",
             bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", edgecolor="gray"))

# ============================================================
# Plot 3: Stacked Bar — Sector contribution to emissions decline
# Shows buildings vs transport share of total decline, plus
# electricity emissions vs energy consumption decline comparison
# ============================================================
ax3 = axes[2]

# Compute buildings and transport contributions to total decline
bld_pcts = []
trans_pcts = []
elec_em_declines = []
ng_em_declines = []
city_labels = []

for city in cities:
    cdf = df[df["city"] == city].sort_values("year")
    r27 = cdf.iloc[0]
    r35 = cdf.iloc[-1]

    total_decline = r27["total_mt_co2e"] - r35["total_mt_co2e"]  # positive = reduction
    bld_decline = r27["buildings_total_mt_co2e"] - r35["buildings_total_mt_co2e"]
    trans_decline = r27["transport_mt_co2"] - r35["transport_mt_co2"]  # negative = increase

    # Share of total decline (transport is negative contribution)
    bld_pct = bld_decline / total_decline * 100 if total_decline > 0 else 0
    trans_pct = trans_decline / total_decline * 100 if total_decline > 0 else 0

    bld_pcts.append(bld_pct)
    trans_pcts.append(trans_pct)

    # Electricity emissions decline vs NG emissions decline
    elec_d = (r35["buildings_electricity_mt_co2"] / r27["buildings_electricity_mt_co2"] - 1) * 100
    ng_d = (r35["buildings_ng_mt_co2e"] / r27["buildings_ng_mt_co2e"] - 1) * 100
    elec_em_declines.append(elec_d)
    ng_em_declines.append(ng_d)
    city_labels.append(city)

x = np.arange(len(cities))
width = 0.35

# Left group: sector contribution to total decline
bars1 = ax3.bar(x - width/2, bld_pcts, width, label="Buildings", color="#4a90d9", edgecolor="white")
bars2 = ax3.bar(x - width/2, trans_pcts, width, bottom=bld_pcts, label="Transport", color="#e8a838", edgecolor="white")

# Right group: electricity vs NG emissions decline
bars3 = ax3.bar(x + width/2, elec_em_declines, width, label="Electricity CO₂", color="#5cb85c", edgecolor="white")
bars4 = ax3.bar(x + width/2, ng_em_declines, width * 0.6, label="NG CO₂", color="#c9302c", edgecolor="white", alpha=0.8)

ax3.set_xlabel("")
ax3.set_ylabel("% Change (2027→2035)")
ax3.set_title("Emissions Decline: Sector & Source")
ax3.set_xticks(x)
ax3.set_xticklabels(city_labels, fontsize=8)
ax3.legend(fontsize=7, loc="lower left", ncol=2)
ax3.axhline(y=0, color="black", linewidth=0.5)
ax3.grid(True, alpha=0.2, axis="y")

# Add percentage labels on the buildings bars
for i, (b, t) in enumerate(zip(bld_pcts, trans_pcts)):
    ax3.text(i - width/2, b/2, f"{b:.0f}%", ha="center", va="center", fontsize=7, fontweight="bold", color="white")

plt.tight_layout()
plt.savefig("outputs/5city_forecast_2027_2035.png", dpi=150, bbox_inches="tight")
print("Saved: outputs/5city_forecast_2027_2035.png")
plt.close()
