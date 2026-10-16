# VDAM KC — Vector Surveillance Dashboard

**Live:** https://vdamkc-dashboard-ksz8kh3ciazdw3cie6v3jw.streamlit.app/

A Streamlit dashboard that turns trap/species count data and insecticide-resistance
bioassay data into a site map, species and density trends, WHO resistance status and
a ranked "where to look first" site table. It is linked to the other VDAM KC tools:
the **Mosquito Atlas** (species reference) and **Anopheles Behaviour** (resistance mechanisms).

See `PRODUCT_SCOPE.md` for the product plan (v1 → v2 → v3).

## Run it locally

```bash
python -m venv venv
venv\Scripts\activate              # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

It opens at `http://localhost:8501`. With no uploads it runs on the sample data in
`sample_data/` (clearly labelled as sample). Once you upload a file, sample data is
never mixed with your records.

## Your data

Two CSV files — download blank templates from the sidebar.

**Trap data**: `trap_id, site_name, latitude, longitude, date, collection_method, species, sex, count`

**Resistance data**: `site_name, date, insecticide, exposure_time_min, sample_size, mortality_percent`,
plus optional `control_mortality_percent` (enables Abbott's correction and rejects tests with
control mortality > 20%).

Headers are case- and space-insensitive, and files exported from Excel (UTF-8 BOM or Windows-1252)
are read correctly. Invalid rows (bad dates, out-of-range coordinates or mortality, negative counts,
exact duplicates) are excluded **and listed by CSV row number** in the *Data quality* tab, so nothing
disappears silently.

## What it calculates

All rules are written out in the app's *Methodology* tab. In short:

- **WHO tube-test status**: ≥ 98% susceptible, 90–97% possible resistance, < 90% confirmed resistance.
  Confirmation requires n ≥ 100; smaller tests are reported as possible resistance.
- **Density trend**: latest collection against the previous one **by the same method**. "Rising" needs
  more than 25% *and* at least 5 more specimens, so small catches don't raise noisy alerts.
- **Site risk**: High = rising density plus confirmed resistance; Watch = either one; Low = measured and
  quiet; Insufficient data = no measurable trend yet.

## Links to the Atlas and Behaviour apps

- Species names are matched against the Mosquito Atlas taxon list (83 Afrotropical taxa). Names the Atlas
  doesn't know are flagged as possible typos, and each species shows its complex/group and the Atlas's
  identification note (for example, that *An. gambiae* complex members need PCR).
- Where pyrethroid resistance is found, the resistance tab lists the standard follow-up tests (repeat,
  PBO synergist, intensity, kdr genotyping) and links to the Behaviour model **as a way to understand the
  mechanisms**. It is not presented as a forecast, since that model's validity domain is still being
  established.

The taxon list is a snapshot at `vdamkc/reference/atlas_taxa.json`. Refresh it when the Atlas changes:

```bash
python scripts/sync_atlas_taxa.py ../Anopheles_Atlas
```

Set the public addresses of the two apps to show the links (`.streamlit/secrets.toml`, Streamlit Cloud
secrets, or environment variables — see `.streamlit/secrets.toml.example`):

```toml
ATLAS_URL = "https://…"
BEHAVIOUR_URL = "https://…"
```

When unset, the links are hidden. The species matching works either way.

## Development

```bash
pip install -r requirements-dev.txt
pytest            # tests for validation, WHO thresholds, Abbott, trends, risk, Atlas matching
ruff check .
```

Layout:

```
app.py                  Streamlit UI only
vdamkc/data.py          CSV loading, validation, safe CSV export
vdamkc/analysis.py      WHO interpretation, trends, risk ranking (pure functions)
vdamkc/reference.py     Atlas taxon matching, links to Atlas / Behaviour
vdamkc/theme.py         brand palette, chart template, page CSS
scripts/sync_atlas_taxa.py
tests/
```

## Deploy (free)

1. Push this folder to its own GitHub repository.
2. On [share.streamlit.io](https://share.streamlit.io), point it at the repo and `app.py`.
3. Add `ATLAS_URL` / `BEHAVIOUR_URL` under the app's *Secrets* once those apps are online.
