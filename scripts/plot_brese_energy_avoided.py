"""Plot BRESE cumulative energy avoided by state (2026-2040).

Two panels: electricity (MWh) and natural gas (MMBtu).
"""
import sys
sys.path.insert(0, ".")

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# --- Load data ---
elec = pd.read_csv("data/inputs/brese/electricity_avoided.csv")
ng = pd.read_csv("data/inputs/brese/ng_avoided.csv")

# Sort states by 2040 cumulative electricity (largest first)
elec_2040 = elec[elec["year"] == 2040].set_index("state")["cumulative_mwh_avoided"]
state_order = elec_2040.sort_values(ascending=False).index.tolist()

# Color palette for 11 states
cmap = plt.cm.tab20
colors = {state: cmap(i / len(state_order)) for i, state in enumerate(state_order)}

# --- Figure ---
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
fig.suptitle("BRESE: Cumulative Energy Avoided by State (2026–2040)",
             fontsize=14, fontweight="bold", y=1.02)

# Panel 1: Cumulative Electricity Avoided
for state in state_order:
    sdf = elec[elec["state"] == state].sort_values("year")
    ax1.plot(sdf["year"], sdf["cumulative_mwh_avoided"] / 1e6,
             color=colors[state], linewidth=2, marker="o", markersize=3, label=state)

ax1.set_xlabel("Year")
ax1.set_ylabel("Cumulative MWh Avoided (Millions)")
ax1.set_title("Electricity")
ax1.legend(fontsize=8, loc="upper left", ncol=2)
ax1.grid(True, alpha=0.2)
ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.1f}"))

# Panel 2: Cumulative NG Avoided
ng_2040 = ng[ng["year"] == 2040].set_index("state")["cumulative_mmbtu_avoided"]
ng_order = ng_2040.sort_values(ascending=False).index.tolist()

for state in ng_order:
    sdf = ng[ng["state"] == state].sort_values("year")
    ax2.plot(sdf["year"], sdf["cumulative_mmbtu_avoided"] / 1e6,
             color=colors[state], linewidth=2, marker="s", markersize=3, label=state)

ax2.set_xlabel("Year")
ax2.set_ylabel("Cumulative MMBtu Avoided (Millions)")
ax2.set_title("Natural Gas")
ax2.legend(fontsize=8, loc="upper left", ncol=2)
ax2.grid(True, alpha=0.2)
ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.1f}"))

plt.tight_layout()
plt.savefig("outputs/brese_cumulative_energy_avoided.png", dpi=150, bbox_inches="tight")
print("Saved: outputs/brese_cumulative_energy_avoided.png")
plt.close()
