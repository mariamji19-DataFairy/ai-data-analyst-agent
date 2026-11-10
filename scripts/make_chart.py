"""README chart: national median asking price per m², from the statistics agent's own tool results (no new numbers)."""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

run = Path(sys.argv[1])  # e.g. runs/20261107-211726
out = Path(sys.argv[2])  # e.g. docs/images/price_per_m2.png
calls = json.loads((run / "4_statistics.json").read_text())["facts"]["tool_calls"]
trend = next(json.loads(c["result"]) for c in calls
             if c["tool"] == "trend" and c["input"] == {"metric": "avg_price_per_m2_eur", "commune": None})
years = [r["year"] for r in trend["by_year"]]
median = [r["median"] for r in trend["by_year"]]

SURFACE, INK, MUTED, GRID, SERIES = "#fcfcfb", "#0b0b0b", "#52514e", "#e7e6e2", "#2a78d6"
fig, ax = plt.subplots(figsize=(9, 4.2), dpi=150, facecolor=SURFACE)
ax.set_facecolor(SURFACE)
ax.plot(years, median, color=SERIES, linewidth=2, solid_capstyle="round", solid_joinstyle="round")
peak = median.index(max(median))
for i in (0, peak, len(years) - 1):  # selective direct labels: start, peak, latest
    ax.scatter([years[i]], [median[i]], s=40, color=SERIES, edgecolor=SURFACE, linewidth=2, zorder=3)
    ax.annotate(f"€{median[i]:,.0f}", (years[i], median[i]), textcoords="offset points",
                xytext=(0, 10), ha="center", fontsize=10, color=INK, fontweight="bold")
ax.set_title("Luxembourg apartments: median asking price per m² across communes, 2010–2025",
             loc="left", fontsize=12, color=INK, pad=14)
ax.text(0, -0.16, "Source: Ministère du Logement – Observatoire de l'Habitat (CC0). Communes with fewer than 30 listings are not published.",
        transform=ax.transAxes, fontsize=8, color=MUTED)
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"€{v/1000:.0f}K"))
ax.set_ylim(0, max(median) * 1.18)
ax.set_xticks(years[::3] + ([years[-1]] if (len(years) - 1) % 3 else []))
ax.grid(axis="y", color=GRID, linewidth=1)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color(GRID)
ax.tick_params(colors=MUTED, labelsize=9, length=0)
fig.tight_layout()
out.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out, facecolor=SURFACE)
print("wrote", out)
