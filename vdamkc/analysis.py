"""Surveillance analysis: WHO bioassay interpretation, site trends, risk ranking.

Pure functions over DataFrames — no Streamlit — so they can be unit-tested.
"""

from __future__ import annotations

import math

import pandas as pd

# ---------- WHO tube-test interpretation ----------
# WHO (2016, rev. 2022) Test procedures for insecticide resistance monitoring
# in malaria vector mosquitoes.

SUSCEPTIBLE = "Susceptible"
POSSIBLE = "Possible resistance"
CONFIRMED = "Confirmed resistance"
INVALID = "Invalid test"
STATUS_ORDER = [CONFIRMED, POSSIBLE, SUSCEPTIBLE, INVALID]

SUSCEPTIBLE_MIN = 98.0
RESISTANT_BELOW = 90.0
MIN_SAMPLE_FOR_CONFIRMATION = 100
CONTROL_CORRECT_ABOVE = 5.0   # Abbott's correction applies for 5–20% control mortality
CONTROL_INVALID_ABOVE = 20.0  # test must be discarded and repeated


def abbott_corrected(mortality: float, control: float | None) -> float | None:
    """Abbott's formula. Returns None when the test is invalid (control > 20%)."""
    if control is None or (isinstance(control, float) and math.isnan(control)):
        return mortality
    if control > CONTROL_INVALID_ABOVE:
        return None
    if control < CONTROL_CORRECT_ABOVE:
        return mortality
    corrected = (mortality - control) / (100 - control) * 100
    return round(max(corrected, 0.0), 1)


def classify_resistance(mortality: float | None, sample_size: int | None = None) -> str:
    """WHO thresholds: ≥98 susceptible, 90–<98 possible, <90 confirmed.

    Below-90% mortality only counts as *confirmed* when enough mosquitoes were
    tested; a small test is reported as possible resistance pending a repeat.
    """
    if mortality is None or (isinstance(mortality, float) and math.isnan(mortality)):
        return INVALID
    if mortality >= SUSCEPTIBLE_MIN:
        return SUSCEPTIBLE
    if mortality >= RESISTANT_BELOW:
        return POSSIBLE
    if sample_size is not None and sample_size < MIN_SAMPLE_FOR_CONFIRMATION:
        return POSSIBLE
    return CONFIRMED


def _status_note(row) -> str:
    if row["status"] == INVALID:
        return f"Control mortality {row['control_mortality_percent']:.0f}% > 20% — repeat test"
    notes = []
    if row["corrected_mortality"] != row["mortality_percent"]:
        notes.append("Abbott-corrected")
    if row["sample_size"] < MIN_SAMPLE_FOR_CONFIRMATION:
        if row["corrected_mortality"] < RESISTANT_BELOW:
            notes.append(f"<90% but n={row['sample_size']} — repeat with ≥100 to confirm")
        else:
            notes.append(f"n={row['sample_size']} (<100)")
    return "; ".join(notes)


def interpret_bioassays(resistance: pd.DataFrame) -> pd.DataFrame:
    """Add corrected_mortality, status and note columns."""
    df = resistance.copy()
    if df.empty:
        return df.assign(corrected_mortality=pd.Series(dtype=float),
                         status=pd.Series(dtype=str), note=pd.Series(dtype=str))
    df["corrected_mortality"] = [
        abbott_corrected(m, c) for m, c in zip(df["mortality_percent"], df["control_mortality_percent"], strict=False)
    ]
    df["status"] = [classify_resistance(m, n) for m, n in zip(df["corrected_mortality"], df["sample_size"], strict=False)]
    df["note"] = df.apply(_status_note, axis=1)
    return df


def latest_bioassays(interpreted: pd.DataFrame) -> pd.DataFrame:
    """Most recent *valid* test per site × insecticide."""
    valid = interpreted[interpreted["status"] != INVALID]
    return (
        valid.sort_values("date")
        .groupby(["site_name", "insecticide"], as_index=False)
        .tail(1)
        .sort_values(["site_name", "insecticide"])
        .reset_index(drop=True)
    )


def resistance_flags(latest: pd.DataFrame) -> dict[str, str]:
    """Worst current status per site, among non-susceptible results."""
    flags: dict[str, str] = {}
    for site, group in latest.groupby("site_name"):
        statuses = set(group["status"])
        if CONFIRMED in statuses:
            flags[site] = CONFIRMED
        elif POSSIBLE in statuses:
            flags[site] = POSSIBLE
    return flags


# ---------- Density trends ----------

RISING_PCT = 25.0       # % increase on the previous collection
RISING_MIN_ABS = 5      # …and at least this many more specimens, so 2→3 isn't "rising"


def collection_totals(trap: pd.DataFrame) -> pd.DataFrame:
    """Specimens per site per collection event (date + method)."""
    return (
        trap.groupby(["site_name", "date", "collection_method"], as_index=False)["count"]
        .sum()
        .sort_values(["site_name", "date"])
    )


def site_summary(trap: pd.DataFrame) -> pd.DataFrame:
    """One row per site with its latest collection and trend vs the previous one.

    A trend is only computed when the two collections used the same method:
    a larval dip and a light-trap catch are not comparable densities.
    """
    cols = ["site_name", "latitude", "longitude", "collections", "latest_date",
            "latest_method", "latest_count", "previous_count", "change_pct", "trend"]
    if trap.empty:
        return pd.DataFrame(columns=cols)

    coords = trap.groupby("site_name")[["latitude", "longitude"]].last()
    rows = []
    for site, group in collection_totals(trap).groupby("site_name"):
        latest = group.iloc[-1]
        prior_same = group.iloc[:-1][group.iloc[:-1]["collection_method"] == latest["collection_method"]]
        previous_count = change_pct = None
        if len(group) == 1:
            trend = "Single collection"
        elif prior_same.empty:
            trend = "Method changed"
        else:
            previous_count = int(prior_same.iloc[-1]["count"])
            diff = latest["count"] - previous_count
            change_pct = round(diff / previous_count * 100, 1) if previous_count else None
            if diff >= RISING_MIN_ABS and (change_pct is None or change_pct > RISING_PCT):
                trend = "Rising"
            elif diff <= -RISING_MIN_ABS and change_pct is not None and change_pct < -RISING_PCT:
                trend = "Falling"
            else:
                trend = "Stable"
        rows.append({
            "site_name": site,
            "latitude": coords.loc[site, "latitude"],
            "longitude": coords.loc[site, "longitude"],
            "collections": len(group),
            "latest_date": latest["date"].date(),
            "latest_method": latest["collection_method"],
            "latest_count": int(latest["count"]),
            "previous_count": previous_count,
            "change_pct": change_pct,
            "trend": trend,
        })
    return pd.DataFrame(rows, columns=cols)


# ---------- Risk ranking ----------

HIGH = "High"
WATCH = "Watch"
LOW = "Low"
INSUFFICIENT = "Insufficient data"
RISK_ORDER = [HIGH, WATCH, LOW, INSUFFICIENT]


def risk_table(summary: pd.DataFrame, flags: dict[str, str]) -> pd.DataFrame:
    """Rank sites by where to look first.

    High  — density rising AND confirmed resistance
    Watch — any one of: rising density, confirmed or possible resistance
    Low   — trend measured, not rising, no resistance flag
    Insufficient data — no measurable trend and no bioassay flag
    """
    table = summary.copy()
    # Sites that only appear in bioassays still belong on the list.
    for site in sorted(set(flags) - set(table["site_name"])):
        table.loc[len(table)] = {"site_name": site, "trend": "No trap data", "collections": 0}

    def assess(row):
        flag = flags.get(row["site_name"])
        rising = row["trend"] == "Rising"
        reasons = []
        if rising:
            reasons.append(f"density up {row['change_pct']:+.0f}%" if pd.notna(row["change_pct"]) else "density up")
        if flag:
            reasons.append(flag.lower())
        if rising and flag == CONFIRMED:
            level = HIGH
        elif rising or flag:
            level = WATCH
        elif row["trend"] in ("Stable", "Falling"):
            level = LOW
        else:
            level = INSUFFICIENT
            reasons.append(row["trend"].lower())
        return level, "; ".join(reasons)

    if table.empty:
        return table.assign(risk=pd.Series(dtype=str), reason=pd.Series(dtype=str))
    table[["risk", "reason"]] = table.apply(lambda r: pd.Series(assess(r)), axis=1)
    table["resistance"] = table["site_name"].map(flags).fillna("")
    table["_rank"] = table["risk"].map({r: i for i, r in enumerate(RISK_ORDER)})
    return (
        table.sort_values(["_rank", "latest_count"], ascending=[True, False], na_position="last")
        .drop(columns="_rank")
        .reset_index(drop=True)
    )


# ---------- Species composition ----------

MAX_SPECIES_SERIES = 7  # beyond this, the rest fold into "Other" (8 colours max)


def species_by_collection(trap: pd.DataFrame) -> pd.DataFrame:
    if trap.empty:
        return pd.DataFrame(columns=["date", "species", "count"])
    totals = trap.groupby("species")["count"].sum().sort_values(ascending=False)
    keep = set(totals.index[:MAX_SPECIES_SERIES]) if len(totals) > MAX_SPECIES_SERIES + 1 else set(totals.index)
    labelled = trap.assign(species=trap["species"].where(trap["species"].isin(keep), "Other"))
    return labelled.groupby(["date", "species"], as_index=False)["count"].sum()


def species_order(trap: pd.DataFrame) -> list[str]:
    """Stable species order (by total catch) so colours follow the species, not the filter."""
    if trap.empty:
        return []
    order = trap.groupby("species")["count"].sum().sort_values(ascending=False).index.tolist()
    if len(order) > MAX_SPECIES_SERIES + 1:
        order = order[:MAX_SPECIES_SERIES] + ["Other"]
    return order
