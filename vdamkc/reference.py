"""Links to the sister VDAM KC tools: the Mosquito Atlas and Anopheles Behaviour.

Taxon names, complexes and identification notes come from the Atlas (via the
snapshot written by ``scripts/sync_atlas_taxa.py``) so the dashboard and the
Atlas never disagree on what a species is or which ones need PCR.

The apps' public URLs come from the ``ATLAS_URL`` and ``BEHAVIOUR_URL``
settings (environment variable or ``.streamlit/secrets.toml``). When a URL is
unset, links are simply omitted — the dashboard never points at a page that
doesn't exist.
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

TAXA_PATH = Path(__file__).parent / "reference" / "atlas_taxa.json"

_QUALIFIERS = re.compile(r"\b(s\.?\s?s\.?|s\.?\s?l\.?|sensu stricto|sensu lato|complex|group|spp?\.?)\s*$")
_GENUS_ABBREV = {"an.": "anopheles", "cx.": "culex", "ae.": "aedes"}


def setting(key: str) -> str | None:
    value = os.environ.get(key)
    if value:
        return value.strip()
    try:
        import streamlit as st
        value = st.secrets.get(key)
    except Exception:  # no secrets file — perfectly normal locally
        return None
    return str(value).strip() if value else None


@lru_cache(maxsize=1)
def atlas_taxa() -> dict:
    return json.loads(TAXA_PATH.read_text(encoding="utf-8"))


def _normalise(name: str) -> tuple[str, bool]:
    """Lower-case, expand 'An.' and strip s.s./s.l. Returns (key, was_sensu_lato)."""
    n = re.sub(r"\s+", " ", name.strip().lower())
    words = n.split(" ")
    if words and words[0] in _GENUS_ABBREV:
        words[0] = _GENUS_ABBREV[words[0]]
    n = " ".join(words)
    sensu_lato = bool(re.search(r"s\.?\s?l\.?$|sensu lato|complex$|group$", n))
    while True:
        stripped = _QUALIFIERS.sub("", n).strip()
        if stripped == n:
            break
        n = stripped
    return n, sensu_lato


@lru_cache(maxsize=1)
def _index() -> dict[str, dict]:
    return {t["name"].lower(): t for t in atlas_taxa()["taxa"]}


def match_species(name: str) -> dict | None:
    """The Atlas taxon a data-file species name refers to, or None."""
    key, _ = _normalise(name)
    return _index().get(key)


def species_reference(species: list[str]) -> pd.DataFrame:
    """One row per species name found in the data, resolved against the Atlas."""
    atlas_url = setting("ATLAS_URL")
    rows = []
    for name in sorted(set(species)):
        taxon = match_species(name)
        _, sensu_lato = _normalise(name)
        rows.append({
            "species": name,
            "in_atlas": taxon is not None,
            "atlas_name": taxon["display"] if taxon else "",
            "complex_or_group": (taxon or {}).get("group") or "",
            "id_note": (taxon or {}).get("group_note") or "",
            "recorded_as": "sensu lato" if sensu_lato else "species",
            "atlas_link": f"{atlas_url.rstrip('/')}/#taxon={taxon['id']}" if (atlas_url and taxon) else None,
        })
    return pd.DataFrame(rows)


def unrecognised_species(species: list[str]) -> list[str]:
    """Names that don't resolve to any Atlas taxon — often a typo that would
    otherwise split one species into two series."""
    return sorted({s for s in species if s and match_species(s) is None})


# Next-step guidance for a pyrethroid resistance signal. Standard WHO practice;
# the Behaviour model is offered for understanding mechanisms, not as a field
# prediction (see its docs/validity-domain.md).
PYRETHROIDS = {"deltamethrin", "permethrin", "alpha-cypermethrin", "alphacypermethrin",
               "lambda-cyhalothrin", "lambdacyhalothrin", "cyfluthrin", "etofenprox"}


def is_pyrethroid(insecticide: str) -> bool:
    return insecticide.strip().lower() in PYRETHROIDS
