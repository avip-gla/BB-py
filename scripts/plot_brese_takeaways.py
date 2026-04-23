"""BRESE takeaway plots: cost-benefit, sector BCR, and CO2 impact.

Three figures:
  1. Net benefit by state (ranked bar chart)
  2. Residential vs Commercial BCR (grouped bars)
  3. Cumulative CO2 avoided with cost per MT overlay
"""
import sys
sys.path.insert(0, ".")

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# --- Load data ---
cb = pd.read_csv("data/inputs/ecu/cost_benefit_summary.csv")
elec = pd.read_csv("data/inputs/ecu/electricity_avoided.csv")

# Derived columns
cb["net_benefit"] = cb["savings_total"] - cb["costs_total"]
cb["bcr_res_calc"] = cb["savings_res"] / cb["costs_res"]
cb["bcr_com_calc"] = cb["savings_com"] / cb["costs_com"]
cb["bcr_total_calc"] = cb["savings_total"] / cb["costs_total"]

# CO2 at 2030
co2 = elec[elec["annual_mt_co2_avoided"].notna()][["state", "cumulative_mt_co2_avoided"]].copy()
co2 = co2.rename(columns={"cumulative_mt_co2_avoided": "cum_co2_mt"})
cb = cb.merge(co2, on="state", how="left")

# ============================================================
# Figure 1: Net Benefit by State
# ============================================================
fig1, ax1 = plt.subplots(figsize=(10, 6))

df1 = cb.sort_values("net_benefit", ascending=True)
bar_colors = ["#2ca02c" if v >= 0 else "#d62728" for v in df1["net_benefit"]]

bars = ax1.barh(df1["state"], df1["net_benefit"], color=bar_colors, edgecolor="white")
ax1.axvline(x=0, color="black", linewidth=0.8)
ax1.set_xlabel("Net Benefit (Millions $ NPV)")
ax1.set_title("BRESE: Net Benefit of Code Adoption by State\n(Energy Cost Savings minus Implementation Costs, NPV through 2040)",
              fontsize=12, fontweight="bold")
ax1.grid(True, alpha=0.2, axis="x")

# Add value labels
for bar, val in zip(bars, df1["net_benefit"]):
    x_pos = bar.get_width()
    ha = "left" if x_pos >= 0 else "right"
    offset = 15 if x_pos >= 0 else -15
    ax1.annotate(f"${val:+,.0f}M", xy=(x_pos, bar.get_y() + bar.get_height() / 2),
                 xytext=(offset, 0), textcoords="offset points",
                 ha=ha, va="center", fontsize=9, fontweight="bold")

ax1.set_xlim(ax1.get_xlim()[0] * 1.15, ax1.get_xlim()[1] * 1.3)

plt.tight_layout()
plt.savefig("outputs/brese_net_benefit.png", dpi=150, bbox_inches="tight")
print("Saved: outputs/brese_net_benefit.png")
plt.close()

# ============================================================
# Figure 2: Residential vs Commercial BCR
# ============================================================
fig2, ax2 = plt.subplots(figsize=(10, 6))

df2 = cb.sort_values("bcr_total_calc", ascending=False)
x = np.arange(len(df2))
width = 0.3

# Replace NaN/inf for commercial (TN has 0 costs)
bcr_com = df2["bcr_com_calc"].fillna(0).replace([np.inf, -np.inf], 0)

bars_res = ax2.bar(x - width/2, df2["bcr_res_calc"], width,
                   label="Residential", color="#4a90d9", edgecolor="white")
bars_com = ax2.bar(x + width/2, bcr_com, width,
                   label="Commercial", color="#e8a838", edgecolor="white")

ax2.axhline(y=1.0, color="black", linewidth=1.2, linestyle="--", label="Break-even (BCR = 1.0)")
ax2.set_xticks(x)
ax2.set_xticklabels(df2["state"], fontsize=9)
ax2.set_ylabel("Benefit-Cost Ratio")
ax2.set_title("BRESE: Residential vs Commercial Benefit-Cost Ratio\n(Energy Savings / Implementation Costs, NPV through 2040)",
              fontsize=12, fontweight="bold")
ax2.legend(fontsize=9, loc="upper right")
ax2.grid(True, alpha=0.2, axis="y")

# Add value labels on residential bars
for i, (bar, val) in enumerate(zip(bars_res, df2["bcr_res_calc"])):
    ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.03,
             f"{val:.2f}", ha="center", va="bottom", fontsize=7, fontweight="bold")

# Add value labels on commercial bars (skip TN which has 0)
for i, (bar, val) in enumerate(zip(bars_com, bcr_com)):
    if val > 0:
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.03,
                 f"{val:.2f}", ha="center", va="bottom", fontsize=7, fontweight="bold")
    else:
        ax2.text(bar.get_x() + bar.get_width() / 2, 0.05,
                 "N/A", ha="center", va="bottom", fontsize=7, color="gray")

plt.tight_layout()
plt.savefig("outputs/brese_bcr_res_vs_com.png", dpi=150, bbox_inches="tight")
print("Saved: outputs/brese_bcr_res_vs_com.png")
plt.close()

# ============================================================
# Figure 3: Cumulative CO2 Avoided with Cost Overlay
# ============================================================
fig3, ax3 = plt.subplots(figsize=(10, 6))

df3 = cb.dropna(subset=["cum_co2_mt"]).sort_values("cum_co2_mt", ascending=True)

bars_co2 = ax3.barh(df3["state"], df3["cum_co2_mt"] / 1e6,
                     color="#5cb85c", edgecolor="white", label="Cumulative CO₂ Avoided")
ax3.set_xlabel("Cumulative MT CO₂ Avoided by 2030 (Millions)")
ax3.set_title("BRESE: Cumulative CO₂ Avoided by 2030 & Cost per MT\n(Code adoption impact through 2030)",
              fontsize=12, fontweight="bold")
ax3.grid(True, alpha=0.2, axis="x")

# Add cost per MT CO2 as text labels
for bar, (_, row) in zip(bars_co2, df3.iterrows()):
    co2_val = row["cum_co2_mt"]
    cost_val = row["costs_total"] * 1e6  # convert to $
    cost_per_mt = cost_val / co2_val if co2_val > 0 else 0
    net = row["net_benefit"]
    net_color = "#2ca02c" if net >= 0 else "#d62728"

    x_pos = bar.get_width()
    ax3.annotate(f"${cost_per_mt:,.0f}/MT  (net: ${net:+,.0f}M)",
                 xy=(x_pos, bar.get_y() + bar.get_height() / 2),
                 xytext=(8, 0), textcoords="offset points",
                 ha="left", va="center", fontsize=8, color=net_color)

ax3.set_xlim(0, ax3.get_xlim()[1] * 1.55)

plt.tight_layout()
plt.savefig("outputs/brese_co2_avoided.png", dpi=150, bbox_inches="tight")
print("Saved: outputs/brese_co2_avoided.png")
plt.close()
