"""Render a static reference figure from the uploaded CSV, without DB or Google.

Optional dependency: python -m pip install matplotlib
Run from any directory: python scripts/render_reference.py
The resulting PNG is a design reference, not the required live Data Studio report.
"""

from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import FuncFormatter, MaxNLocator

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))
from ingest import read_source
from transform import transform_dataframe

NAVY = "#18354D"
TEAL = "#00847F"
BRICK = "#B9463A"
INK = "#263B4C"
MUTED = "#657686"
BG = "#F3F7FA"
GRID = "#E4EBF1"


def panel(fig, bounds, title, inset_left=0.038):
    x, y, width, height = bounds
    fig.add_artist(FancyBboxPatch(
        (x, y), width, height, boxstyle="round,pad=0.006,rounding_size=0.008",
        transform=fig.transFigure, facecolor="white", edgecolor="#DCE6ED",
        linewidth=0.8, zorder=-1,
    ))
    fig.text(x + 0.016, y + height - 0.029, title,
             fontsize=11.5, weight="bold", color=NAVY, va="center")
    ax = fig.add_axes([x + inset_left, y + 0.060, width - inset_left - 0.022, height - 0.112])
    ax.set_facecolor("white")
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=9, length=0, pad=5)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)
    return ax


def render(output: Path | None = None) -> Path:
    tables, quality = transform_dataframe(read_source(PROJECT_DIR / "data/raw/superstore.csv"))
    output = output or PROJECT_DIR / "docs/dashboard_reference.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    fig = plt.figure(figsize=(18, 11.5), facecolor=BG)
    fig.text(0.04, 0.961, "Superstore | Dashboard reference", fontsize=25,
             color=NAVY, weight="bold", va="top")
    fig.text(0.04, 0.918,
             "Offline reference from uploaded CSV; recreate in Data Studio",
             fontsize=11.5, color=MUTED, va="top")
    fig.text(0.96, 0.949, "ORDER DATES  /  03 JAN 2014 - 30 DEC 2017",
             fontsize=10, color=MUTED, ha="right")
    cards = [
        ("TOTAL SALES", f"{quality['sales']:,.2f}", "Source units"),
        ("TOTAL PROFIT", f"{quality['profit']:,.2f}", "Source units"),
        ("PROFIT MARGIN", f"{quality['profit_margin']:.2%}", "Sum of profit / sum of sales"),
        ("DISTINCT ORDERS", f"{quality['orders']:,}", f"{quality['output_rows']:,} order lines | {quality['customers']:,} customers"),
    ]
    card_width, card_gap = 0.215, 0.020
    for index, (label, value, note) in enumerate(cards):
        x, y = 0.04 + index * (card_width + card_gap), 0.802
        fig.add_artist(FancyBboxPatch((x, y), card_width, 0.095,
            boxstyle="round,pad=0.006,rounding_size=0.008", transform=fig.transFigure,
            facecolor="white", edgecolor="#DCE6ED", linewidth=0.8, zorder=-1))
        fig.text(x + 0.015, y + 0.073, label, fontsize=9, color=MUTED, weight="bold")
        fig.text(x + 0.015, y + 0.035, value, fontsize=23, color=TEAL if index == 2 else NAVY, weight="bold")
        fig.text(x + 0.015, y + 0.010, note, fontsize=9, color=MUTED)

    # 1. Same unit and same scale for the two monthly amount series.
    ax = panel(fig, [0.04, 0.437, 0.535, 0.325], "01  Monthly sales and profit")
    monthly = tables["monthly_summary"]
    ax.plot(monthly.order_month, monthly.sales / 1000, color=TEAL, linewidth=2, label="Sales")
    ax.plot(monthly.order_month, monthly.profit / 1000, color=NAVY, linewidth=2, label="Profit")
    ax.axhline(0, color=MUTED, linewidth=0.8)
    ax.set_ylim(-8, 137)
    ax.set_ylabel("Source units (thousands)", fontsize=9)
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.legend(loc="upper left", frameon=False, ncol=2, fontsize=9)
    peak = monthly.loc[monthly.sales.idxmax()]
    ax.annotate("Nov 2017: 118.4k", (peak.order_month, peak.sales / 1000),
                xytext=(-9, 11), textcoords="offset points", ha="right",
                fontsize=9, color=TEAL)

    # 2. All 17 subcategories; label the three loss-making categories explicitly.
    ax = panel(fig, [0.595, 0.437, 0.365, 0.325], "02  Sales and profit by subcategory", inset_left=0.045)
    sub = tables["subcategory_summary"]
    ax.scatter(sub.sales / 1000, sub.profit / 1000, s=58,
               c=[TEAL if value >= 0 else BRICK for value in sub.profit],
               edgecolors="white", linewidths=0.8, alpha=0.95, zorder=3)
    ax.axhline(0, color=NAVY, linewidth=1)
    offsets = {"Supplies": (5, -17), "Bookcases": (5, -17), "Tables": (5, -17),
               "Copiers": (5, 9), "Phones": (-5, 9), "Paper": (5, 9)}
    for row in sub.itertuples(index=False):
        if row.sub_category in offsets:
            offset = offsets[row.sub_category]
            ax.annotate(row.sub_category, (row.sales / 1000, row.profit / 1000),
                        xytext=offset, textcoords="offset points", fontsize=8.5,
                        ha="right" if row.sub_category == "Phones" else "left",
                        color=BRICK if row.profit < 0 else NAVY)
    ax.set_xlim(0, 370)
    ax.set_ylim(-32, 68)
    ax.set_xlabel("Sales (thousands)", fontsize=9)
    ax.set_ylabel("Profit (thousands)", fontsize=9)

    # 3. Region profit, plotted from zero with the largest region at the top.
    ax = panel(fig, [0.04, 0.094, 0.280, 0.304], "03  Profit by region", inset_left=0.050)
    region = tables["region_summary"].sort_values("profit")
    bars = ax.barh(region.region, region.profit / 1000, height=0.58,
                   color=[TEAL if name == "West" else NAVY for name in region.region], zorder=3)
    ax.grid(False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_xlim(0, 137)
    ax.set_xlabel("Profit (source units, thousands)", fontsize=9)
    ax.xaxis.set_major_locator(MaxNLocator(4))
    for bar in bars:
        ax.text(bar.get_width() + 3, bar.get_y() + bar.get_height() / 2,
                f"{bar.get_width():.1f}k", va="center", fontsize=9, color=INK)

    # 4. Total contribution by customer segment, not averages per customer.
    ax = panel(fig, [0.340, 0.094, 0.300, 0.304], "04  Sales and profit by segment", inset_left=0.044)
    segment = tables["segment_summary"].sort_values("sales", ascending=False)
    positions = list(range(len(segment)))
    width = 0.34
    sales_bars = ax.bar([p - width / 2 for p in positions], segment.sales / 1000,
                       width, color=TEAL, label="Sales", zorder=3)
    profit_bars = ax.bar([p + width / 2 for p in positions], segment.profit / 1000,
                        width, color=NAVY, label="Profit", zorder=3)
    ax.set_xticks(positions, [name.replace(" ", "\n") for name in segment.segment])
    ax.set_ylim(0, 1410)
    ax.set_ylabel("Source units (thousands)", fontsize=9)
    ax.legend(loc="upper right", frameon=False, fontsize=8.5)
    for bar in [*sales_bars, *profit_bars]:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 30,
                f"{bar.get_height():,.0f}", ha="center", fontsize=8.5, color=INK)

    # 5. Weighted margin; the negative baseline is never truncated.
    ax = panel(fig, [0.660, 0.094, 0.300, 0.304], "05  Margin by discount band", inset_left=0.042)
    bands = tables["discount_summary"].sort_values("discount_band_sort")
    margins = bands.profit_margin * 100
    bars = ax.bar(list(range(len(bands))), margins, width=0.58,
                  color=[TEAL if value >= 0 else BRICK for value in margins], zorder=3)
    ax.axhline(0, color=NAVY, linewidth=1)
    ax.set_xticks(list(range(len(bands))), ["0%", "(0%,20%]", "(20%,40%]", ">40%"])
    ax.tick_params(axis="x", labelsize=8.5)
    ax.set_ylim(-100, 52)
    ax.set_ylabel("Sum(profit) / sum(sales)", fontsize=9)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:.0f}%"))
    for bar, value in zip(bars, margins):
        ax.text(bar.get_x() + bar.get_width() / 2, value + (4 if value >= 0 else -5),
                f"{value:.1f}%", ha="center", va="bottom" if value >= 0 else "top",
                fontsize=9, color=TEAL if value >= 0 else BRICK, weight="bold")

    fig.text(0.04, 0.048,
             "Source: uploaded Sample - Superstore.csv | All 9,994 order lines retained | No dashboard filters applied",
             fontsize=9.5, color=MUTED)
    fig.text(0.04, 0.026,
             "Sales and profit use source units; currency is not specified. Discount comparisons describe association, not causation.",
             fontsize=9.5, color=MUTED)
    fig.savefig(output, dpi=170, facecolor=BG)
    plt.close(fig)
    return output


if __name__ == "__main__":
    print(render())
