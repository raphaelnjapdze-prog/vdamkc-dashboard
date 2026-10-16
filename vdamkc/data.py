"""Loading and validating the two input CSVs.

Every loader returns a ``LoadResult``: the cleaned DataFrame plus a list of
``Issue`` objects describing what was fixed, dropped, or looks suspicious.
Nothing is dropped silently — if a row is excluded, an issue says which one
and why, so the Data Quality tab can show it.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

TRAP_COLUMNS = [
    "trap_id", "site_name", "latitude", "longitude",
    "date", "collection_method", "species", "sex", "count",
]
RESISTANCE_COLUMNS = [
    "site_name", "date", "insecticide",
    "exposure_time_min", "sample_size", "mortality_percent",
]
# Optional: enables Abbott's correction when present.
RESISTANCE_OPTIONAL_COLUMNS = ["control_mortality_percent"]

DEFAULT_TRAP_PATH = "sample_data/trap_data_template.csv"
DEFAULT_RESISTANCE_PATH = "sample_data/resistance_data_template.csv"

# Characters that make spreadsheet apps evaluate a cell as a formula.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


@dataclass(frozen=True)
class Issue:
    level: str  # "error" | "warning" | "info"
    dataset: str  # "Trap data" | "Resistance data"
    message: str


@dataclass
class LoadResult:
    df: pd.DataFrame
    issues: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.level == "error" for i in self.issues)


# ---------- helpers ----------

def _read_csv(source, dataset: str) -> tuple[pd.DataFrame | None, list[Issue]]:
    """Read a path or uploaded file, tolerating BOMs and non-UTF-8 exports
    (Excel on Windows commonly writes cp1252)."""
    raw = source if isinstance(source, (str, bytes)) else source.getvalue()
    if isinstance(raw, str):
        with open(raw, "rb") as fh:
            raw = fh.read()

    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        return None, [Issue("error", dataset, "File is not readable text (unknown encoding).")]

    if not text.strip():
        return None, [Issue("error", dataset, "File is empty.")]
    try:
        df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    except pd.errors.ParserError as exc:
        return None, [Issue("error", dataset, f"Could not parse CSV: {exc}")]
    return df, []


def _normalise_headers(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _strip_strings(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
    return df


def _csv_row_numbers(index: pd.Index) -> str:
    """Spreadsheet row numbers (header is row 1) for a set of DataFrame rows."""
    rows = [str(i + 2) for i in index[:10]]
    more = f" (+{len(index) - 10} more)" if len(index) > 10 else ""
    return ", ".join(rows) + more


def _drop_invalid(df, mask, dataset, reason, issues) -> pd.DataFrame:
    if mask.any():
        issues.append(Issue(
            "warning", dataset,
            f"{int(mask.sum())} row(s) excluded — {reason}. CSV rows: {_csv_row_numbers(df.index[mask])}.",
        ))
    return df[~mask]


def _check_required(df, required, dataset) -> list[Issue]:
    missing = [c for c in required if c not in df.columns]
    if missing:
        return [Issue(
            "error", dataset,
            f"Missing required column(s): {', '.join(missing)}. "
            f"Expected: {', '.join(required)}.",
        )]
    return []


def _parse_dates(df, dataset, issues) -> pd.DataFrame:
    df["date"] = pd.to_datetime(df["date"], errors="coerce", format="mixed", dayfirst=False)
    df = _drop_invalid(df, df["date"].isna(), dataset, "date missing or not YYYY-MM-DD", issues)
    future = df["date"].dt.date > date.today()
    if future.any():
        issues.append(Issue(
            "warning", dataset,
            f"{int(future.sum())} row(s) are dated in the future — check for typos. "
            f"CSV rows: {_csv_row_numbers(df.index[future])}.",
        ))
    return df


def _to_numeric(df, cols) -> pd.DataFrame:
    for col in cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ---------- trap data ----------

def load_trap_data(source) -> LoadResult:
    dataset = "Trap data"
    df, issues = _read_csv(source, dataset)
    if df is None:
        return LoadResult(pd.DataFrame(columns=TRAP_COLUMNS), issues)

    df = _normalise_headers(df)
    issues += _check_required(df, TRAP_COLUMNS, dataset)
    if issues:
        return LoadResult(pd.DataFrame(columns=TRAP_COLUMNS), issues)

    df = _strip_strings(df)
    df = _drop_invalid(df, df["site_name"] == "", dataset, "site_name is blank", issues)
    df = _drop_invalid(df, df["species"] == "", dataset, "species is blank", issues)
    df = _parse_dates(df, dataset, issues)

    df = _to_numeric(df, ["latitude", "longitude", "count"])
    bad_coords = (
        df["latitude"].isna() | df["longitude"].isna()
        | ~df["latitude"].between(-90, 90) | ~df["longitude"].between(-180, 180)
    )
    df = _drop_invalid(df, bad_coords, dataset, "latitude/longitude missing or out of range", issues)
    bad_count = df["count"].isna() | (df["count"] < 0) | (df["count"] % 1 != 0)
    df = _drop_invalid(df, bad_count, dataset, "count is not a whole number ≥ 0", issues)
    df["count"] = df["count"].astype(int)

    df["sex"] = df["sex"].str.capitalize()
    unknown_sex = ~df["sex"].isin(["Female", "Male", "Unknown", ""])
    if unknown_sex.any():
        values = ", ".join(sorted(df.loc[unknown_sex, "sex"].unique())[:5])
        issues.append(Issue("info", dataset, f"Unrecognised sex values kept as-is: {values}."))

    # The schema is one row per species/sex per collection, so an exact
    # duplicate is a double entry; keeping it would double-count specimens.
    key = ["trap_id", "site_name", "date", "collection_method", "species", "sex"]
    dupes = df.duplicated(subset=key + ["count"], keep="first")
    df = _drop_invalid(df, dupes, dataset, "exact duplicate of an earlier row (double entry)", issues)
    conflicting = df.duplicated(subset=key, keep=False)
    if conflicting.any():
        issues.append(Issue(
            "warning", dataset,
            "Same trap, date, method, species and sex recorded more than once with "
            "different counts — counts were summed. CSV rows: "
            f"{_csv_row_numbers(df.index[conflicting])}.",
        ))

    # A site should sit in one place. If its coordinates vary, map it at its
    # most recent position and say so.
    coord_variants = df.groupby("site_name")[["latitude", "longitude"]].nunique().max(axis=1)
    for site in coord_variants[coord_variants > 1].index:
        latest = df[df["site_name"] == site].sort_values("date").iloc[-1]
        df.loc[df["site_name"] == site, ["latitude", "longitude"]] = [latest["latitude"], latest["longitude"]]
        issues.append(Issue(
            "warning", dataset,
            f"'{site}' has more than one set of coordinates; using the most recent "
            f"({latest['latitude']:.4f}, {latest['longitude']:.4f}).",
        ))

    return LoadResult(df[TRAP_COLUMNS].reset_index(drop=True), issues)


# ---------- resistance data ----------

def load_resistance_data(source) -> LoadResult:
    dataset = "Resistance data"
    cols = RESISTANCE_COLUMNS + RESISTANCE_OPTIONAL_COLUMNS
    df, issues = _read_csv(source, dataset)
    if df is None:
        return LoadResult(pd.DataFrame(columns=cols), issues)

    df = _normalise_headers(df)
    issues += _check_required(df, RESISTANCE_COLUMNS, dataset)
    if issues:
        return LoadResult(pd.DataFrame(columns=cols), issues)
    if "control_mortality_percent" not in df.columns:
        df["control_mortality_percent"] = ""
        issues.append(Issue(
            "info", dataset,
            "No control_mortality_percent column — mortality is used uncorrected. "
            "Add it to apply Abbott's correction and reject invalid tests (control > 20%).",
        ))

    df = _strip_strings(df)
    df = _drop_invalid(df, df["site_name"] == "", dataset, "site_name is blank", issues)
    df = _drop_invalid(df, df["insecticide"] == "", dataset, "insecticide is blank", issues)
    df = _parse_dates(df, dataset, issues)

    df = _to_numeric(df, ["exposure_time_min", "sample_size", "mortality_percent", "control_mortality_percent"])
    bad_mort = df["mortality_percent"].isna() | ~df["mortality_percent"].between(0, 100)
    df = _drop_invalid(df, bad_mort, dataset, "mortality_percent missing or outside 0–100", issues)
    bad_n = df["sample_size"].isna() | (df["sample_size"] <= 0)
    df = _drop_invalid(df, bad_n, dataset, "sample_size missing or not positive", issues)
    df["sample_size"] = df["sample_size"].astype(int)
    bad_ctrl = df["control_mortality_percent"].notna() & ~df["control_mortality_percent"].between(0, 100)
    if bad_ctrl.any():
        issues.append(Issue(
            "warning", dataset,
            f"{int(bad_ctrl.sum())} control mortality value(s) outside 0–100 ignored. "
            f"CSV rows: {_csv_row_numbers(df.index[bad_ctrl])}.",
        ))
        df.loc[bad_ctrl, "control_mortality_percent"] = float("nan")

    non_standard = df["exposure_time_min"].notna() & (df["exposure_time_min"] != 60)
    if non_standard.any():
        issues.append(Issue(
            "info", dataset,
            f"{int(non_standard.sum())} test(s) use a non-standard exposure time (WHO tube test is 60 min); "
            "thresholds may not apply to intensity assays.",
        ))

    dupes = df.duplicated(keep="first")
    df = _drop_invalid(df, dupes, dataset, "exact duplicate of an earlier row (double entry)", issues)

    return LoadResult(df[cols].reset_index(drop=True), issues)


def cross_check(trap: pd.DataFrame, resistance: pd.DataFrame) -> list[Issue]:
    """Site names should match across the two files; a typo silently splits a site."""
    if trap.empty or resistance.empty:
        return []
    orphans = sorted(set(resistance["site_name"]) - set(trap["site_name"]))
    if not orphans:
        return []
    return [Issue(
        "warning", "Resistance data",
        f"Site(s) with bioassays but no trap records: {', '.join(orphans)}. "
        "Check spelling against trap data — these sites can't be mapped.",
    )]


def safe_csv_bytes(df: pd.DataFrame) -> bytes:
    """CSV export that neutralises spreadsheet formula injection."""
    out = df.copy()
    for col in out.select_dtypes(include=["object", "string"]).columns:
        out[col] = out[col].map(
            lambda v: "'" + v if isinstance(v, str) and v.startswith(_FORMULA_PREFIXES) else v
        )
    return out.to_csv(index=False).encode("utf-8")


def blank_template(columns: list[str]) -> bytes:
    return (",".join(columns) + "\n").encode("utf-8")
