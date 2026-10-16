"""Brand palette, chart styling and page CSS.

Brand colours match the VDAM KC website (vdamkc.netlify.app). Chart series
colours are a colour-blind-validated categorical order; status colours are
reserved for WHO status / risk and always appear with a text label.
"""

import plotly.graph_objects as go
import plotly.io as pio

from vdamkc import analysis

BRAND_TEAL = "#0B3D3A"
BRAND_BLUE = "#0EA5E9"
INK = "#0F211D"
INK_SOFT = "#4B5D58"
MUTED = "#898781"
GRID = "#E1E0D9"
LINE = "#DCE6E2"
SURFACE = "#FFFFFF"
PAGE = "#F7FAF9"

# Categorical order — validated for colour-vision deficiency on adjacent pairs.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
OTHER = "#9C9A92"

GOOD, WARNING, SERIOUS, CRITICAL, NEUTRAL = "#0ca30c", "#fab219", "#ec835a", "#d03b3b", "#9C9A92"

STATUS_COLORS = {
    analysis.SUSCEPTIBLE: GOOD,
    analysis.POSSIBLE: WARNING,
    analysis.CONFIRMED: CRITICAL,
    analysis.INVALID: NEUTRAL,
}
RISK_COLORS = {
    analysis.HIGH: CRITICAL,
    analysis.WATCH: WARNING,
    analysis.LOW: GOOD,
    analysis.INSUFFICIENT: NEUTRAL,
}
# Light tints for table cells: ink text stays readable, the tint carries state.
TINTS = {
    analysis.SUSCEPTIBLE: "#E3F5E3", analysis.POSSIBLE: "#FEF1D2",
    analysis.CONFIRMED: "#F9DEDE", analysis.INVALID: "#F0EFEC",
    analysis.HIGH: "#F9DEDE", analysis.WATCH: "#FEF1D2",
    analysis.LOW: "#E3F5E3", analysis.INSUFFICIENT: "#F0EFEC",
}
# Paired with every status colour so meaning never rests on colour alone.
STATUS_ICONS = {
    analysis.SUSCEPTIBLE: "●", analysis.POSSIBLE: "▲", analysis.CONFIRMED: "■", analysis.INVALID: "○",
    analysis.HIGH: "■", analysis.WATCH: "▲", analysis.LOW: "●", analysis.INSUFFICIENT: "○",
}

FONT = "IBM Plex Sans, system-ui, -apple-system, Segoe UI, sans-serif"


def series_colors(names: list[str]) -> dict[str, str]:
    """Map entities to colours in fixed order — pass the *unfiltered* list so a
    filter never repaints the survivors."""
    mapping = {}
    palette = iter(SERIES)
    for name in names:
        mapping[name] = OTHER if name == "Other" else next(palette, OTHER)
    return mapping


def register_plotly_template() -> None:
    template = go.layout.Template()
    template.layout = go.Layout(
        font=dict(family=FONT, size=13, color=INK_SOFT),
        title=dict(font=dict(size=15, color=INK)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=SERIES,
        xaxis=dict(showgrid=False, linecolor="#C3C2B7", ticks="outside", tickcolor="#C3C2B7",
                   title=dict(font=dict(color=MUTED, size=12))),
        yaxis=dict(gridcolor=GRID, zeroline=False, linecolor="rgba(0,0,0,0)",
                   title=dict(font=dict(color=MUTED, size=12))),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    title=dict(text=""), font=dict(color=INK_SOFT)),
        hoverlabel=dict(bgcolor=SURFACE, bordercolor=LINE, font=dict(family=FONT, color=INK)),
        margin=dict(l=8, r=8, t=48, b=8),
        bargap=0.25,
    )
    pio.templates["vdamkc"] = template
    pio.templates.default = "vdamkc"


PAGE_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

.stApp, [data-testid="stMarkdownContainer"] {{ font-family: {FONT}; }}
h1, h2, h3, h4 {{ font-family: 'Space Grotesk', {FONT}; letter-spacing: -0.01em; color: {INK}; }}
.block-container {{ padding-top: 2rem; max-width: 1320px; }}

.vk-header {{
  display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: 12px;
  border-bottom: 1px solid {LINE}; padding-bottom: 14px; margin-bottom: 18px;
}}
.vk-eyebrow {{ font: 600 12px/1 'IBM Plex Sans', sans-serif; letter-spacing: .12em;
  text-transform: uppercase; color: {BRAND_BLUE}; margin-bottom: 6px; }}
.vk-title {{ font: 700 28px/1.15 'Space Grotesk', sans-serif; color: {INK}; margin: 0; }}
.vk-meta {{ display: flex; gap: 8px; flex-wrap: wrap; }}
.vk-chip {{ font: 500 12px/1 'IBM Plex Sans', sans-serif; padding: 6px 10px; border-radius: 999px;
  border: 1px solid {LINE}; background: {SURFACE}; color: {INK_SOFT}; white-space: nowrap; }}
.vk-chip.sample {{ border-color: #F5C26B; background: #FFF8E8; color: #8A5A00; }}
.vk-chip.live {{ border-color: #A7DDB8; background: #EEFAF2; color: #1D6B37; }}

[data-testid="stMetric"] {{ background: {SURFACE}; }}
[data-testid="stMetricValue"] {{ font-family: 'Space Grotesk', sans-serif; color: {INK}; }}
[data-testid="stMetricLabel"] p {{ color: {INK_SOFT}; font-size: 13px; }}

.vk-brand-card {{ background: {BRAND_TEAL}; border-radius: 10px; padding: 16px 16px 14px; }}
.vk-brand {{ font: 700 22px/1 'Space Grotesk', sans-serif; color: #FFFFFF; letter-spacing: .02em; }}
.vk-brand-sub {{ font-size: 12px; line-height: 1.4; color: #A9C4BF; margin-top: 6px; }}

.vk-footer {{ margin-top: 40px; padding-top: 14px; border-top: 1px solid {LINE};
  font-size: 12px; color: {MUTED}; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; }}
</style>
"""
