"""
VDAM KC — Vector Surveillance Dashboard

Turns trap/species count data and insecticide-resistance bioassay data into a
site map, trend charts, WHO resistance status and a ranked site risk table,
linked to the Mosquito Atlas (species reference) and Anopheles Behaviour
(resistance mechanisms).

Run locally:
    pip install -r requirements.txt
    streamlit run app.py

Logic lives in the ``vdamkc`` package (data loading/validation, analysis,
reference links, theme); this file is the Streamlit UI only.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from vdamkc import __version__, analysis, data, reference, theme

st.set_page_config(
    page_title="VDAM KC · Vector Surveillance",
    page_icon="🦟",
    layout="wide",
    initial_sidebar_state="expanded",
)
theme.register_plotly_template()
st.markdown(theme.PAGE_CSS, unsafe_allow_html=True)

PLOT_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]}
ATLAS_URL = reference.setting("ATLAS_URL")
BEHAVIOUR_URL = reference.setting("BEHAVIOUR_URL")


# ---------- Loading (cached on file contents) ----------

@st.cache_data(show_spinner=False)
def _load_trap(raw: bytes | str) -> data.LoadResult:
    return data.load_trap_data(raw)


@st.cache_data(show_spinner=False)
def _load_resistance(raw: bytes | str) -> data.LoadResult:
    return data.load_resistance_data(raw)


def _tint(value: str) -> str:
    color = theme.TINTS.get(value)
    return f"background-color: {color}; color: {theme.INK}" if color else ""


def _label(value: str) -> str:
    return f"{theme.STATUS_ICONS.get(value, '')} {value}".strip() if value else ""


def _empty_state(message: str) -> None:
    st.info(message, icon="ℹ️")


# ---------- Sidebar ----------

with st.sidebar:
    st.markdown(
        '<div class="vk-brand-card"><div class="vk-brand">VDAM KC</div>'
        '<div class="vk-brand-sub">Vector Dynamics &amp; Malaria Knowledge for Control</div></div>',
        unsafe_allow_html=True,
    )
    st.divider()
    st.subheader("Data source")
    trap_upload = st.file_uploader("Trap data (CSV)", type="csv", key="trap_upload")
    resistance_upload = st.file_uploader("Resistance bioassays (CSV)", type="csv", key="resistance_upload")

    using_sample = trap_upload is None and resistance_upload is None
    if using_sample:
        st.caption("No files uploaded — showing **sample data** from Maiduguri.")
    with st.expander("Blank templates"):
        st.download_button("Trap data template", data.blank_template(data.TRAP_COLUMNS),
                           "trap_data_template.csv", "text/csv", width="stretch")
        st.download_button(
            "Resistance template",
            data.blank_template(data.RESISTANCE_COLUMNS + data.RESISTANCE_OPTIONAL_COLUMNS),
            "resistance_data_template.csv", "text/csv", width="stretch",
        )

# Sample data is used only when nothing is uploaded. Uploading one file never
# pads the other with sample records — that would mix real and fake data.
if using_sample:
    trap_result = _load_trap(data.DEFAULT_TRAP_PATH)
    res_result = _load_resistance(data.DEFAULT_RESISTANCE_PATH)
else:
    trap_result = _load_trap(trap_upload.getvalue()) if trap_upload else data.LoadResult(
        pd.DataFrame(columns=data.TRAP_COLUMNS))
    res_result = _load_resistance(resistance_upload.getvalue()) if resistance_upload else data.LoadResult(
        pd.DataFrame(columns=data.RESISTANCE_COLUMNS + data.RESISTANCE_OPTIONAL_COLUMNS))

trap_all = trap_result.df
res_all = res_result.df
issues = trap_result.issues + res_result.issues + data.cross_check(trap_all, res_all)
unknown_species = reference.unrecognised_species(trap_all["species"].tolist())
if unknown_species:
    issues.append(data.Issue(
        "warning", "Trap data",
        f"Species not found in the Mosquito Atlas taxon list: {', '.join(unknown_species)}. "
        "Check the spelling — a variant name is counted as a separate species.",
    ))

# ---------- Filters ----------

all_dates = pd.concat([trap_all["date"], res_all["date"]]).dropna()
all_sites = sorted(set(trap_all["site_name"]) | set(res_all["site_name"]))
all_methods = sorted(trap_all["collection_method"].unique())

with st.sidebar:
    st.divider()
    st.subheader("Filters")
    if all_dates.empty:
        start, end = date.today(), date.today()
    else:
        lo, hi = all_dates.min().date(), all_dates.max().date()
        picked = st.date_input("Period", value=(lo, hi), min_value=lo, max_value=hi, format="YYYY-MM-DD")
        start, end = picked if isinstance(picked, tuple) and len(picked) == 2 else (lo, hi)
    sites = st.multiselect("Sites", all_sites, placeholder="All sites")
    methods = st.multiselect("Collection methods", all_methods, placeholder="All methods")

    if ATLAS_URL or BEHAVIOUR_URL:
        st.divider()
        st.subheader("VDAM KC tools")
        if ATLAS_URL:
            st.link_button("Mosquito Atlas", ATLAS_URL, width="stretch")
        if BEHAVIOUR_URL:
            st.link_button("Anopheles Behaviour", BEHAVIOUR_URL, width="stretch")


def _filter(df: pd.DataFrame, with_method: bool = False) -> pd.DataFrame:
    if df.empty:
        return df
    mask = df["date"].dt.date.between(start, end)
    if sites:
        mask &= df["site_name"].isin(sites)
    if with_method and methods:
        mask &= df["collection_method"].isin(methods)
    return df[mask]


trap = _filter(trap_all, with_method=True)
resistance = _filter(res_all)

summary = analysis.site_summary(trap)
bioassays = analysis.interpret_bioassays(resistance)
latest = analysis.latest_bioassays(bioassays) if not bioassays.empty else bioassays
flags = analysis.resistance_flags(latest) if not latest.empty else {}
risk = analysis.risk_table(summary, flags)

# ---------- Header ----------

source_chip = (
    '<span class="vk-chip sample">Sample data</span>' if using_sample
    else '<span class="vk-chip live">Your uploaded data</span>'
)
through = all_dates.max().strftime("%d %b %Y") if not all_dates.empty else "—"
st.markdown(
    f"""
    <div class="vk-header">
      <div>
        <div class="vk-eyebrow">Malaria vector surveillance</div>
        <h1 class="vk-title">Surveillance Dashboard</h1>
      </div>
      <div class="vk-meta">
        {source_chip}
        <span class="vk-chip">Period {start:%d %b %Y} – {end:%d %b %Y}</span>
        <span class="vk-chip">Data through {through}</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

for issue in issues:
    if issue.level == "error":
        st.error(f"**{issue.dataset}:** {issue.message}")
if not using_sample and (trap_upload is None or resistance_upload is None):
    missing = "resistance bioassay" if trap_upload else "trap"
    st.info(f"Only one file uploaded — upload the {missing} CSV to complete the picture. "
            "Sample data is not mixed with your records.")

n_confirmed = sum(1 for s in flags.values() if s == analysis.CONFIRMED)
n_rising = int((summary["trend"] == "Rising").sum())
n_high = int((risk["risk"] == analysis.HIGH).sum()) if not risk.empty else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Sites monitored", len(sites) if sites else len(all_sites), border=True,
          help="Sites with trap or bioassay records in the current filter.")
k2.metric("Specimens collected", f"{int(trap['count'].sum()):,}" if not trap.empty else "—", border=True,
          help="All specimens in the selected period, sites and methods.")
k3.metric("Confirmed resistance", n_confirmed, border=True,
          help="Sites whose latest valid bioassay for any insecticide is < 90% mortality with n ≥ 100.")
k4.metric("Rising density", n_rising, border=True,
          help=f"Latest collection > {analysis.RISING_PCT:.0f}% and ≥ {analysis.RISING_MIN_ABS} specimens above "
               "the previous one by the same method.")
k5.metric("High-risk sites", n_high, border=True, help="Rising density and confirmed resistance together.")

# ---------- Tabs ----------

n_warn = sum(1 for i in issues if i.level in ("error", "warning"))
tab_overview, tab_species, tab_res, tab_quality, tab_data, tab_method = st.tabs([
    "Overview", "Species & density", "Insecticide resistance",
    f"Data quality ({n_warn})" if n_warn else "Data quality",
    "Data & export", "Methodology",
])

# Overview: map + risk table
with tab_overview:
    mapped = risk.dropna(subset=["latitude", "longitude"]) if not risk.empty else risk
    if mapped.empty:
        _empty_state("No trap records in the current filter — nothing to map.")
    else:
        st.subheader("Trap network")
        map_df = mapped.assign(
            size=mapped["latest_count"].fillna(0).clip(lower=1),
            change=mapped["change_pct"].map(lambda v: f"{v:+.0f}%" if pd.notna(v) else "—"),
        )
        span = max(map_df["latitude"].max() - map_df["latitude"].min(),
                   map_df["longitude"].max() - map_df["longitude"].min())
        zoom = 12 if span < 0.05 else 11 if span < 0.15 else 9 if span < 0.6 else 7 if span < 3 else 5
        fig = px.scatter_map(
            map_df, lat="latitude", lon="longitude", size="size", size_max=30,
            color="risk",
            color_discrete_map=theme.RISK_COLORS,
            category_orders={"risk": analysis.RISK_ORDER},
            hover_name="site_name",
            hover_data={"size": False, "latitude": False, "longitude": False, "risk": False,
                        "latest_count": True, "latest_date": True, "latest_method": True,
                        "change": True, "reason": True},
            labels={"latest_count": "Latest count", "latest_date": "Collected", "latest_method": "Method",
                    "change": "Change", "reason": "Why", "risk": "Risk"},
            zoom=zoom, height=500,
        )
        fig.update_traces(marker=dict(opacity=0.85))
        fig.update_layout(map_style="carto-positron", margin=dict(l=0, r=0, t=0, b=0),
                          legend=dict(y=0.98, x=0.01, yanchor="top", bgcolor="rgba(255,255,255,.9)"))
        st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)
        st.caption("Bubble size = specimens in the latest collection. Colour = site risk level (see Methodology).")

    st.subheader("Where to look first")
    if risk.empty:
        _empty_state("No sites to rank yet.")
    else:
        view = risk.assign(risk=risk["risk"].map(_label))[
            ["site_name", "risk", "reason", "resistance", "latest_count", "previous_count", "change_pct",
             "latest_date", "latest_method", "collections"]
        ]
        st.dataframe(
            view.style.map(lambda v: _tint(v.split(" ", 1)[-1]) if isinstance(v, str) else "", subset=["risk"]),
            width="stretch", hide_index=True,
            column_config={
                "site_name": st.column_config.TextColumn("Site", width="medium"),
                "risk": st.column_config.TextColumn("Risk"),
                "reason": st.column_config.TextColumn("Why", width="large"),
                "latest_count": st.column_config.NumberColumn("Latest count", format="%d"),
                "previous_count": st.column_config.NumberColumn("Previous", format="%d"),
                "change_pct": st.column_config.NumberColumn("Change", format="%+.0f%%"),
                "latest_date": st.column_config.DateColumn("Last collected", format="DD MMM YYYY"),
                "latest_method": st.column_config.TextColumn("Method"),
                "resistance": st.column_config.TextColumn("Resistance status"),
                "collections": st.column_config.NumberColumn("Collections", format="%d"),
            },
        )

# Species & density
with tab_species:
    if trap.empty:
        _empty_state("No trap records in the current filter.")
    else:
        species_colors = theme.series_colors(analysis.species_order(trap_all))
        left, right = st.columns([3, 1])
        left.subheader("Species composition by collection date")
        mode = right.segmented_control("Show", ["Counts", "Share %"], default="Counts",
                                       label_visibility="collapsed") or "Counts"
        comp = analysis.species_by_collection(trap)
        fig = px.bar(
            comp, x="date", y="count", color="species",
            color_discrete_map=species_colors,
            category_orders={"species": list(species_colors)},
            labels={"count": "Specimens" if mode == "Counts" else "Share of catch (%)",
                    "date": "Collection date", "species": "Species"},
            height=380,
        )
        fig.update_traces(marker_line_color=theme.SURFACE, marker_line_width=1.5,
                          hovertemplate="%{x|%d %b %Y}<br>%{fullData.name}: %{y:,}<extra></extra>")
        if mode == "Share %":
            fig.update_layout(barnorm="percent")
            fig.update_traces(hovertemplate="%{x|%d %b %Y}<br>%{fullData.name}: %{y:.0f}%<extra></extra>")
        st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)

        st.subheader("Species reference")
        ref = reference.species_reference(trap["species"].tolist())
        totals = trap.groupby("species")["count"].sum()
        ref = ref.assign(specimens=ref["species"].map(totals)).sort_values("specimens", ascending=False)
        columns = ["species", "specimens", "atlas_name", "complex_or_group", "id_note"]
        if ATLAS_URL:
            columns.append("atlas_link")
        st.dataframe(
            ref[columns], width="stretch", hide_index=True,
            column_config={
                "species": "Recorded as",
                "specimens": st.column_config.NumberColumn("Specimens", format="%d"),
                "atlas_name": "Atlas taxon",
                "complex_or_group": "Complex / group",
                "id_note": st.column_config.TextColumn("Identification note", width="large"),
                "atlas_link": st.column_config.LinkColumn("Atlas", display_text="Open ↗", width="small"),
            },
        )
        st.caption(
            "Taxonomy and identification notes come from the VDAM KC Mosquito Atlas "
            f"(snapshot {reference.atlas_taxa()['synced']}). Members of a cryptic complex can't be told apart "
            "by morphology, so species-level counts are only as reliable as the molecular (PCR) "
            "identification behind them."
        )

        st.subheader("Density over time by site")
        coll = analysis.collection_totals(trap)
        site_colors = theme.series_colors(sorted(trap_all["site_name"].unique()))
        fig = px.line(
            coll, x="date", y="count", color="site_name", symbol="collection_method",
            markers=True, color_discrete_map=site_colors,
            labels={"count": "Specimens per collection", "date": "Collection date",
                    "site_name": "Site", "collection_method": "Method"},
            height=380,
        )
        fig.update_traces(line_width=2, marker_size=9)
        fig.update_layout(hovermode="x unified")
        st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)
        st.caption("Marker shape = collection method. Counts from different methods aren't directly comparable.")

# Insecticide resistance
with tab_res:
    if bioassays.empty:
        _empty_state("No bioassay records in the current filter.")
    else:
        st.subheader("Current status — latest valid test per site and insecticide")
        if latest.empty:
            _empty_state("Every test in the filter is invalid (control mortality > 20%).")
        else:
            cell = latest.assign(
                cell=[f"{theme.STATUS_ICONS[s]} {m:.0f}%" for s, m in zip(latest["status"], latest["corrected_mortality"], strict=False)]
            )
            values = cell.pivot(index="site_name", columns="insecticide", values="cell").fillna("").rename_axis("Site")
            states = cell.pivot(index="site_name", columns="insecticide", values="status").fillna("")
            styled = values.style.apply(lambda col: [_tint(s) for s in states[col.name]], axis=0)
            styled.columns.name = None
            st.dataframe(styled, width="stretch")
            st.caption(
                f"{theme.STATUS_ICONS[analysis.SUSCEPTIBLE]} Susceptible (≥ 98%)  ·  "
                f"{theme.STATUS_ICONS[analysis.POSSIBLE]} Possible resistance (90–97%, or < 90% with n < 100)  ·  "
                f"{theme.STATUS_ICONS[analysis.CONFIRMED]} Confirmed resistance (< 90%, n ≥ 100)"
            )

            pyrethroid_hits = latest[
                latest["insecticide"].map(reference.is_pyrethroid)
                & latest["status"].isin([analysis.CONFIRMED, analysis.POSSIBLE])
            ]
            if not pyrethroid_hits.empty:
                with st.container(border=True):
                    st.markdown("**Recommended follow-up for pyrethroid resistance**")
                    confirmed = sorted(pyrethroid_hits.loc[pyrethroid_hits["status"] == analysis.CONFIRMED, "site_name"].unique())
                    possible = sorted(set(pyrethroid_hits["site_name"]) - set(confirmed))
                    lines = []
                    if possible:
                        lines.append(f"- **Repeat the test** at {', '.join(possible)} to confirm (WHO: a second "
                                     "result below 98% confirms resistance).")
                    if confirmed:
                        lines.append(f"- **PBO synergist assay** at {', '.join(confirmed)}: restored mortality "
                                     "after PBO points to P450 metabolic resistance — relevant to choosing "
                                     "PBO nets.")
                        lines.append(f"- **Intensity assay (5× and 10×)** at {', '.join(confirmed)} to judge "
                                     "whether resistance is strong enough to undermine control.")
                        lines.append("- **kdr genotyping** (L995F/S in *An. gambiae* s.l.) on a subsample to "
                                     "separate target-site from metabolic resistance.")
                    st.markdown("\n".join(lines))
                    if BEHAVIOUR_URL:
                        st.markdown(
                            f"To see how kdr and P450 mechanisms change a tube-test outcome, explore the "
                            f"[Anopheles Behaviour model]({BEHAVIOUR_URL}). It is a research model for "
                            "understanding mechanisms — not a forecast for these sites."
                        )

        st.subheader("Mortality over time")
        insecticides = sorted(bioassays["insecticide"].unique())
        # Open on the insecticide with the weakest current result — the one worth looking at.
        worst = latest.sort_values("corrected_mortality").iloc[0]["insecticide"] if not latest.empty else insecticides[0]
        chosen = st.selectbox("Insecticide", insecticides, index=insecticides.index(worst))
        series = bioassays[(bioassays["insecticide"] == chosen) & (bioassays["status"] != analysis.INVALID)]
        site_colors = theme.series_colors(sorted(res_all["site_name"].unique()))
        fig = px.line(
            series.sort_values("date"), x="date", y="corrected_mortality", color="site_name",
            markers=True, color_discrete_map=site_colors,
            hover_data={"sample_size": True, "status": True},
            labels={"corrected_mortality": "Mortality (%)", "date": "Test date", "site_name": "Site",
                    "sample_size": "n", "status": "Status"},
            height=400,
        )
        for y0, y1, color, text in [
            (analysis.SUSCEPTIBLE_MIN, 101, theme.GOOD, "Susceptible"),
            (analysis.RESISTANT_BELOW, analysis.SUSCEPTIBLE_MIN, theme.WARNING, "Possible"),
            (0, analysis.RESISTANT_BELOW, theme.CRITICAL, "Resistant"),
        ]:
            fig.add_hrect(y0=y0, y1=y1, fillcolor=color, opacity=0.08, line_width=0,
                          annotation_text=text, annotation_position="right",
                          annotation_font=dict(size=11, color=theme.MUTED))
        low = series["corrected_mortality"].min() if not series.empty else 80
        fig.update_yaxes(range=[max(0, min(low, 85) - 5), 101])
        fig.update_traces(line_width=2, marker_size=9)
        fig.update_layout(hovermode="x unified", margin=dict(r=90))
        st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)

        with st.expander("All bioassay results"):
            st.dataframe(
                bioassays.sort_values(["date", "site_name"], ascending=[False, True])[
                    ["date", "site_name", "insecticide", "sample_size", "mortality_percent",
                     "control_mortality_percent", "corrected_mortality", "status", "note"]
                ].style.map(_tint, subset=["status"]),
                width="stretch", hide_index=True,
                column_config={
                    "date": st.column_config.DateColumn("Date", format="DD MMM YYYY"),
                    "site_name": "Site", "insecticide": "Insecticide",
                    "sample_size": st.column_config.NumberColumn("n", format="%d"),
                    "mortality_percent": st.column_config.NumberColumn("Observed %", format="%.1f"),
                    "control_mortality_percent": st.column_config.NumberColumn("Control %", format="%.1f"),
                    "corrected_mortality": st.column_config.NumberColumn("Corrected %", format="%.1f"),
                    "status": "Status", "note": st.column_config.TextColumn("Note", width="large"),
                },
            )

# Data quality
with tab_quality:
    st.subheader("Data quality checks")
    st.caption("Every row that was excluded or adjusted is listed here — nothing is dropped silently.")
    if not issues:
        st.success("All checks passed — no problems found in the loaded data.", icon="✅")
    for issue in issues:
        render = {"error": st.error, "warning": st.warning, "info": st.info}[issue.level]
        render(f"**{issue.dataset}** — {issue.message}")

# Data & export
with tab_data:
    stamp = date.today().isoformat()
    st.subheader("Site risk table")
    st.download_button("Download risk table (CSV)", data.safe_csv_bytes(risk),
                       f"vdamkc_site_risk_{stamp}.csv", "text/csv", disabled=risk.empty)
    st.subheader("Trap data")
    st.caption(f"{len(trap):,} rows in the current filter (of {len(trap_all):,} loaded).")
    st.dataframe(trap, width="stretch", hide_index=True,
                 column_config={"date": st.column_config.DateColumn("date", format="YYYY-MM-DD")})
    st.download_button("Download trap data (CSV)", data.safe_csv_bytes(trap),
                       f"vdamkc_trap_data_{stamp}.csv", "text/csv", disabled=trap.empty)
    st.subheader("Resistance data")
    st.caption(f"{len(bioassays):,} rows in the current filter (of {len(res_all):,} loaded), "
               "with corrected mortality and WHO status.")
    st.dataframe(bioassays, width="stretch", hide_index=True,
                 column_config={"date": st.column_config.DateColumn("date", format="YYYY-MM-DD")})
    st.download_button("Download resistance data (CSV)", data.safe_csv_bytes(bioassays),
                       f"vdamkc_resistance_data_{stamp}.csv", "text/csv", disabled=bioassays.empty)

# Methodology
with tab_method:
    st.subheader("How the numbers are calculated")
    st.markdown(f"""
**Insecticide resistance** follows the WHO tube-test interpretation criteria
(*Test procedures for insecticide resistance monitoring in malaria vector mosquitoes*, 2nd ed., 2016):

| Mortality (24 h) | Status |
|---|---|
| ≥ {analysis.SUSCEPTIBLE_MIN:.0f}% | Susceptible |
| {analysis.RESISTANT_BELOW:.0f}–{analysis.SUSCEPTIBLE_MIN:.0f}% | Possible resistance — confirm with further testing |
| < {analysis.RESISTANT_BELOW:.0f}% | Confirmed resistance, **if at least {analysis.MIN_SAMPLE_FOR_CONFIRMATION} mosquitoes were tested**; otherwise reported as possible resistance |

If a `control_mortality_percent` column is supplied: control mortality below {analysis.CONTROL_CORRECT_ABOVE:.0f}% is
ignored, {analysis.CONTROL_CORRECT_ABOVE:.0f}–{analysis.CONTROL_INVALID_ABOVE:.0f}% is corrected with **Abbott's formula**
(corrected = (observed − control) ÷ (100 − control) × 100), and above {analysis.CONTROL_INVALID_ABOVE:.0f}% the test is
**invalid** and excluded. A site's status uses its most recent valid test for each insecticide.

**Density trend** compares a site's latest collection with its previous collection *by the same method*
(a larval dip and a light trap catch are not comparable). It is **Rising** when the count is more than
{analysis.RISING_PCT:.0f}% higher *and* at least {analysis.RISING_MIN_ABS} specimens higher — so small catches don't trigger
alerts from noise. Sites with a single collection, or whose method changed, have no trend.

**Site risk**

| Level | Rule |
|---|---|
| High | Rising density **and** confirmed resistance |
| Watch | Rising density, or any resistance flag |
| Low | Trend measured, not rising, no resistance flag |
| Insufficient data | No measurable trend and no resistance flag |

These rules are a prioritisation aid for field teams — not an epidemiological risk model. They do not
account for case data, rainfall, or biting behaviour.

**Species** names are matched against the taxon list of the VDAM KC **Mosquito Atlas** (83 Afrotropical
*Anopheles*, *Culex* and *Aedes* taxa, keyed from Coetzee 2020, Simsaa et al. 2021 and Mohamed et al. 2017).
Unrecognised names are flagged in Data quality. Complex and group notes are the Atlas's own.
""")

st.markdown(
    f'<div class="vk-footer"><span>VDAM KC — Vector Dynamics &amp; Malaria Knowledge for Control</span>'
    f'<span>Dashboard v{__version__} · Decision-support tool; verify findings before acting.</span></div>',
    unsafe_allow_html=True,
)
