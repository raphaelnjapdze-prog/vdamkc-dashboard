# VDAM KC Dashboard — Product Scope

## Why start here

Right now, the only data you can access without needing anyone else's permission is your own field data. So v1 is built around **one real user: you, as a field entomologist**, turning raw trap/resistance records into something you can actually see and act on. This isn't a toy — it's the same core engine a ministry would use later, just with one user and one data source for now. When a real NMP or research partner comes on board, this becomes the demo you show them, not a throwaway.

## v1 — What it does (buildable now, with your own data)

A single-user Streamlit dashboard that takes two CSV files — trap/species counts and insecticide-resistance bioassay results — and turns them into:

1. **Trap network map** — every site plotted, color-coded by recent mosquito density.
2. **Species composition over time** — which Anopheles species are showing up, and how that mix shifts.
3. **Insecticide resistance tracking** — mortality % per insecticide per site, checked against WHO susceptibility thresholds (≥98% susceptible, 90–97% possible resistance, <90% confirmed resistant).
4. **Site risk table** — a simple ranked list of which sites are trending up in density or showing resistance warnings, so you know where to look first.
5. **Data table + CSV export** — the underlying numbers, always visible and downloadable.

This works today with the sample data included, and works with your real data as soon as you drop it into the same two-file format (template included, explained below).

## v2 — Once there's a real pilot partner (NMP, research institution, funder)

- Multiple users with different views: field agent (data entry), supervisor (site oversight), ministry viewer (read-only reports)
- Offline field data capture — rather than building a mobile app from scratch, the practical path is a tool built for this already (e.g. KoboToolbox or ODK, both free and widely used in African public health field work) feeding data into this dashboard, instead of reinventing offline sync
- Automated report export formatted for national malaria programme / WHO reporting cycles
- Alerting when a site crosses a risk threshold

## v3 — Growth

- Multi-region, multi-country deployment
- Integration with DHIS2 (the health information system many African ministries already run) rather than asking them to adopt a second, disconnected tool
- Predictive risk modeling combining trap trends, rainfall, and case data

## v1 data schema

**`trap_data.csv`** — one row per species count per collection

| Column | Example | Notes |
|---|---|---|
| trap_id | MDG-001 | Unique ID per trap/site |
| site_name | Bulabulin Ward | Human-readable location name |
| latitude | 11.8333 | Decimal degrees |
| longitude | 13.1500 | Decimal degrees |
| date | 2026-06-14 | YYYY-MM-DD |
| collection_method | CDC Light Trap | Or Pyrethrum Spray Catch, Larval Dip, etc. |
| species | Anopheles gambiae | Full species name |
| sex | Female | Female / Male |
| count | 14 | Number collected |

**`resistance_data.csv`** — one row per bioassay result

| Column | Example | Notes |
|---|---|---|
| site_name | Bulabulin Ward | Matches trap_data site names |
| date | 2026-06-14 | YYYY-MM-DD |
| insecticide | Deltamethrin | Insecticide tested |
| exposure_time_min | 60 | WHO tube test standard exposure |
| sample_size | 100 | Mosquitoes tested |
| mortality_percent | 92.0 | % mortality — the app classifies this automatically |

## Tech choices, and why

- **Streamlit** — you already know it, free to run locally, free to deploy (Streamlit Community Cloud) when you want a shareable link
- **Pandas** — for all the data wrangling, also your existing skill
- **Plotly** — for the map and charts, no paid API key required
- **CSV for now, database later** — CSVs are enough for one user; move to SQLite once you have real field agents entering data concurrently

## What "done" looks like for v1

You can drop your own (currently unorganized) field notes into the two-CSV format and get a working dashboard reflecting your actual surveillance work in Borno State — something real to iterate on and eventually demo.
