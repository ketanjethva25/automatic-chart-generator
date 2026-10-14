"""
app.py
======
Automatic Chart Generator & Data Explorer
An automated exploratory data analysis (EDA) and interactive visualization platform.

Run locally:
    python app.py
"""
from __future__ import annotations

import csv
import logging
import os
import re
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import gradio as gr
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --------------------------------------------------------------------------- #
# Logging & Paths
# --------------------------------------------------------------------------- #
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("app")
BASE_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()

# =========================================================================== #
# Data Profiling & Type Detection Engine
# =========================================================================== #

# Column "kinds" (semantic types, not raw pandas dtypes)
NUMERIC = "numeric"          # continuous / high-cardinality numbers
CATEGORICAL = "categorical"  # few distinct values (labels, flags, small ints)
DATETIME = "datetime"        # dates / timestamps
TEXT = "text"                # free text or very high-cardinality strings
IDENTIFIER = "identifier"    # row ids, keys, running index
CONSTANT = "constant"        # a single unique value
EMPTY = "empty"              # (almost) no data

# Tunable thresholds
MAX_CATEGORIES = 30           # <= this many distinct strings => categorical
MAX_CATEGORIES_RATIO = 0.05   # ...or up to 100 distinct if ratio <= 5 %
LOW_CARD_INT_MAX = 10         # integer columns with <= 10 values => categorical
LOW_CARD_INT_RATIO = 0.2      # ...if that is also <= 20 % of the rows
NUMERIC_PARSE_THRESHOLD = 0.95   # share of strings that must parse as numbers
DATETIME_PARSE_THRESHOLD = 0.90  # share of strings that must parse as dates
MAX_MISSING_RATIO = 0.70      # columns with more missing data are skipped
ID_NAME_PATTERN = re.compile(r"(^|[^a-z])(id|uuid|guid|idx|index)$", re.IGNORECASE)


class DataLoadError(Exception):
    """Raised when a CSV cannot be read or contains no usable data."""


@dataclass
class ColumnProfile:
    """Everything the chart generator needs to know about one column."""
    name: str
    kind: str                   # one of the kind constants above
    pandas_dtype: str           # dtype of the *original* column
    n_unique: int
    n_missing: int
    pct_missing: float
    usable: bool                # eligible for *automatic* charts
    note: str = ""              # human-readable reason if not usable
    is_numeric_dtype: bool = False  # True if the cleaned column holds numbers


@dataclass
class DatasetProfile:
    """Profile of a whole dataset (one ``ColumnProfile`` per column)."""
    n_rows: int
    n_cols: int
    columns: Dict[str, ColumnProfile] = field(default_factory=dict)

    def names(self, *kinds: str, usable_only: bool = True) -> List[str]:
        """Column names of the given kinds, in original column order."""
        return [
            c.name for c in self.columns.values()
            if c.kind in kinds and (c.usable or not usable_only)
        ]

    @property
    def numeric(self) -> List[str]:
        return self.names(NUMERIC)

    @property
    def categorical(self) -> List[str]:
        return self.names(CATEGORICAL)

    @property
    def datetime(self) -> List[str]:
        return self.names(DATETIME)

    @property
    def text(self) -> List[str]:
        return self.names(TEXT, usable_only=False)


def load_csv(path: str) -> pd.DataFrame:
    """Read a CSV file robustly.

    * Detects the delimiter (comma, semicolon, tab, pipe).
    * Tries several text encodings.
    * Rejects binary files, empty files and files without data rows.
    """
    if not path or not os.path.exists(path):
        raise DataLoadError("The uploaded file could not be found. Please upload it again.")
    if os.path.getsize(path) == 0:
        raise DataLoadError("The uploaded file is empty.")

    with open(path, "rb") as fh:
        head = fh.read(8192)
    if b"\x00" in head:
        raise DataLoadError("This does not look like a text CSV file (binary content detected).")

    last_error: Optional[Exception] = None
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            sample = head.decode(encoding, errors="strict")
        except UnicodeDecodeError:
            try:
                sample = head[:-4].decode(encoding, errors="strict")
            except UnicodeDecodeError as exc:
                last_error = exc
                continue
        sep = _sniff_delimiter(sample)
        try:
            df = pd.read_csv(path, sep=sep, encoding=encoding, low_memory=False)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
        except pd.errors.EmptyDataError:
            raise DataLoadError("The CSV file is empty (no columns found).")
        except pd.errors.ParserError as exc:
            raise DataLoadError(f"The file is not a valid CSV and could not be parsed: {exc}")
        except Exception as exc:
            raise DataLoadError(f"Unexpected error while reading the CSV: {exc}")
        return _validate_loaded(df)

    raise DataLoadError(f"Could not decode the file with a supported encoding ({last_error}).")


def _sniff_delimiter(sample: str) -> str:
    """Guess the delimiter from a text sample; default to a comma."""
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def _validate_loaded(df: pd.DataFrame) -> pd.DataFrame:
    """Drop fully empty rows/columns and make sure something is left."""
    df = df.copy()
    df.columns = [str(c).strip() or f"column_{i}" for i, c in enumerate(df.columns)]
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    if df.shape[1] == 0 or df.shape[0] == 0:
        raise DataLoadError("The dataset is empty: it has no rows or no non-empty columns.")
    return df.reset_index(drop=True)


def prepare_dataframe(df: pd.DataFrame) -> Tuple[pd.DataFrame, DatasetProfile]:
    """Clean a raw dataframe and profile every column."""
    if df is None or df.empty:
        raise DataLoadError("The dataset is empty.")

    clean = df.copy()
    profile = DatasetProfile(n_rows=len(clean), n_cols=clean.shape[1])

    for col in list(clean.columns):
        original_dtype = str(clean[col].dtype)
        series, kind, note = _detect_and_convert(clean[col], col)
        clean[col] = series

        n_missing = int(series.isna().sum())
        n_nonnull = len(series) - n_missing
        n_unique = int(series.nunique(dropna=True))
        pct_missing = n_missing / len(series) if len(series) else 1.0

        usable = kind in (NUMERIC, CATEGORICAL, DATETIME)
        if n_nonnull == 0 or pct_missing > MAX_MISSING_RATIO:
            kind = EMPTY if n_nonnull == 0 else kind
            usable = False
            note = note or f"{pct_missing:.0%} of the values are missing"
        elif kind == CONSTANT:
            note = note or "only one unique value"
        elif kind == IDENTIFIER:
            note = note or "looks like an identifier"
        elif kind == TEXT:
            note = note or "free text / too many distinct values"

        profile.columns[col] = ColumnProfile(
            name=col,
            kind=kind,
            pandas_dtype=original_dtype,
            n_unique=n_unique,
            n_missing=n_missing,
            pct_missing=pct_missing,
            usable=usable,
            note=note,
            is_numeric_dtype=bool(pd.api.types.is_numeric_dtype(series)
                                  and not pd.api.types.is_bool_dtype(series)),
        )
    return clean, profile


def _detect_and_convert(s: pd.Series, name: str) -> Tuple[pd.Series, str, str]:
    """Return ``(converted_series, kind, note)`` for one column."""
    if pd.api.types.is_bool_dtype(s):
        s = s.map({True: "True", False: "False"}).astype(object)

    if pd.api.types.is_datetime64_any_dtype(s):
        return _strip_timezone(s), DATETIME, ""

    if pd.api.types.is_numeric_dtype(s):
        return s, _classify_numeric(s, name), ""

    s = _clean_strings(s)
    non_null = s.dropna()
    if non_null.empty:
        return s, EMPTY, "no values"

    as_num = _try_numeric(s)
    if as_num is not None:
        return as_num, _classify_numeric(as_num, name), ""

    as_dt = _try_datetime(s)
    if as_dt is not None:
        return as_dt, DATETIME, ""

    return s, _classify_string(s), ""


def _clean_strings(s: pd.Series) -> pd.Series:
    """Strip whitespace, turn blanks into NaN; always returns object dtype."""
    def _fix(v):
        if isinstance(v, str):
            v = v.strip()
            return np.nan if v == "" else v
        return v
    return s.astype(object).map(_fix)


def _strip_timezone(s: pd.Series) -> pd.Series:
    """Drop tz info so all downstream period/resample logic is uniform."""
    try:
        if getattr(s.dt, "tz", None) is not None:
            return s.dt.tz_localize(None)
    except (AttributeError, TypeError):
        pass
    return s


def _try_numeric(s: pd.Series) -> Optional[pd.Series]:
    """Convert strings such as ``"1,234.5"``, ``"$12"`` or ``"45%"`` to numbers."""
    non_null = s.dropna().astype(str)
    cleaned = non_null.str.replace(r"[,$€£%\s]", "", regex=True)
    parsed = pd.to_numeric(cleaned, errors="coerce")
    if parsed.notna().mean() < NUMERIC_PARSE_THRESHOLD:
        return None
    full = s.astype(str).str.replace(r"[,$€£%\s]", "", regex=True)
    out = pd.to_numeric(full.where(s.notna()), errors="coerce")
    return out.astype("float64")


def _try_datetime(s: pd.Series) -> Optional[pd.Series]:
    """Parse strings as dates when (nearly) all of them look like dates."""
    non_null = s.dropna().astype(str)
    if non_null.empty:
        return None
    sample = non_null.sample(min(200, len(non_null)), random_state=0)
    looks_datey = sample.str.contains(r"\d") & (sample.str.len() >= 6)
    if looks_datey.mean() < DATETIME_PARSE_THRESHOLD:
        return None
    parsed_sample = _to_datetime(sample)
    if parsed_sample.notna().mean() < DATETIME_PARSE_THRESHOLD:
        return None
    parsed = _to_datetime(s.where(s.notna()).astype(object))
    if parsed[s.notna()].notna().mean() < DATETIME_PARSE_THRESHOLD:
        return None
    return _strip_timezone(parsed)


def _to_datetime(s: pd.Series) -> pd.Series:
    """``pd.to_datetime`` that never raises and never spams warnings."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            return pd.to_datetime(s, errors="coerce", format="mixed")
        except (TypeError, ValueError):
            try:
                return pd.to_datetime(s, errors="coerce")
            except Exception:
                return pd.Series(pd.NaT, index=s.index)


def _classify_numeric(s: pd.Series, name: str) -> str:
    """Decide between numeric / categorical / identifier / constant for numbers."""
    non_null = s.dropna()
    n = len(non_null)
    n_unique = non_null.nunique()
    if n_unique <= 1:
        return CONSTANT
    is_int_like = bool((np.isclose(non_null % 1, 0)).all()) if n else False
    if is_int_like and n_unique == n and n >= 2:
        sorted_vals = np.sort(non_null.to_numpy(dtype="float64"))
        consecutive = bool(np.all(np.diff(sorted_vals) == 1))
        if consecutive or ID_NAME_PATTERN.search(name):
            return IDENTIFIER
    if is_int_like and n_unique <= LOW_CARD_INT_MAX and n_unique <= LOW_CARD_INT_RATIO * n:
        return CATEGORICAL
    return NUMERIC


def _classify_string(s: pd.Series) -> str:
    """Decide between categorical / identifier / text / constant for strings."""
    non_null = s.dropna().astype(str)
    n = len(non_null)
    n_unique = non_null.nunique()
    if n_unique <= 1:
        return CONSTANT
    ratio = n_unique / n
    if n >= 10 and ratio > 0.9:
        avg_len = non_null.str.len().mean()
        has_spaces = non_null.str.contains(" ").mean() > 0.5
        return IDENTIFIER if (avg_len <= 20 and not has_spaces) else TEXT
    if n_unique <= MAX_CATEGORIES or (n_unique <= 100 and ratio <= MAX_CATEGORIES_RATIO):
        return CATEGORICAL
    return TEXT


def column_info_table(profile: DatasetProfile) -> pd.DataFrame:
    """One row per column: detected type, missing values, uniqueness, usability."""
    rows = []
    for c in profile.columns.values():
        rows.append({
            "Column": c.name,
            "Detected type": c.kind,
            "Original dtype": c.pandas_dtype,
            "Missing": c.n_missing,
            "Missing %": round(c.pct_missing * 100, 1),
            "Unique values": c.n_unique,
            "Used in auto charts": "Yes" if c.usable else f"No - {c.note}",
        })
    return pd.DataFrame(rows)


def summary_statistics(df: pd.DataFrame, profile: DatasetProfile) -> pd.DataFrame:
    """Descriptive statistics tailored to each column's kind."""
    rows = []
    for name, c in profile.columns.items():
        s = df[name]
        row: Dict[str, object] = {"Column": name, "Type": c.kind, "Non-null": int(s.notna().sum()),
                                  "Unique": c.n_unique}
        if c.is_numeric_dtype:
            finite = s.replace([np.inf, -np.inf], np.nan).dropna()
            if not finite.empty:
                row.update({
                    "Mean": round(float(finite.mean()), 4),
                    "Std": round(float(finite.std()), 4) if len(finite) > 1 else np.nan,
                    "Min": round(float(finite.min()), 4),
                    "Median": round(float(finite.median()), 4),
                    "Max": round(float(finite.max()), 4),
                })
        elif c.kind == DATETIME:
            valid = s.dropna()
            if not valid.empty:
                row.update({"Min": str(valid.min()), "Max": str(valid.max())})
        else:
            vc = s.dropna().astype(str).value_counts()
            if not vc.empty:
                row.update({"Top value": vc.index[0], "Top count": int(vc.iloc[0])})
        rows.append(row)
    out = pd.DataFrame(rows)
    return out.astype(object).where(out.notna(), "")


def rank_columns_by_completeness(df: pd.DataFrame, cols: List[str]) -> List[str]:
    """Order columns: fewest missing values first, then most distinct values."""
    return sorted(cols, key=lambda c: (df[c].isna().mean(), -df[c].nunique()))


def strong_correlations(df: pd.DataFrame, profile: DatasetProfile,
                        min_abs: float = 0.3, top_n: int = 5) -> List[Tuple[str, str, float]]:
    """Numeric column pairs with ``|Pearson r| >= min_abs`` (strongest first)."""
    cols = profile.numeric
    if len(cols) < 2:
        return []
    data = df[cols].replace([np.inf, -np.inf], np.nan)
    corr = data.corr(min_periods=10)
    pairs: List[Tuple[str, str, float]] = []
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            r = corr.loc[a, b]
            if pd.notna(r) and abs(r) >= min_abs:
                pairs.append((a, b, float(r)))
    pairs.sort(key=lambda t: abs(t[2]), reverse=True)
    return pairs[:top_n]


def suggest_default_axes(profile: DatasetProfile) -> Tuple[Optional[str], Optional[str]]:
    """Sensible initial X / Y for the custom-chart dropdowns."""
    x = next(iter(profile.datetime or profile.categorical or profile.numeric), None)
    if x is None and profile.columns:
        x = next(iter(profile.columns))
    y = next((c for c in profile.numeric if c != x), None)
    return x, y


# =========================================================================== #
# Plotly Chart Generation & Visualization Builders
# =========================================================================== #

# Public constants
AGGREGATIONS = ["mean", "sum", "count", "min", "max", "median"]
CHART_TYPES = ["Auto", "Scatter", "Line", "Bar", "Pie", "Histogram", "Box", "Correlation Heatmap"]
MAX_AUTO_CHARTS = 12

# Styling constants
PALETTE = px.colors.qualitative.Set2
PRIMARY = "#4C78A8"
TEMPLATE = "plotly_white"
CHART_HEIGHT = 460
MAX_SCATTER_POINTS = 5000     # larger data is sampled to keep the browser fast
MAX_BAR_CATEGORIES = 30
MAX_PIE_SLICES = 8
MAX_TIME_POINTS = 200         # time series are re-binned above this


class ChartError(Exception):
    """Raised when a requested chart is impossible; message is user-facing."""


@dataclass
class ChartResult:
    """A rendered chart plus the reasoning that produced it."""
    figure: go.Figure
    title: str
    description: str
    group: str = "custom"


@dataclass
class Candidate:
    """A lazily-built auto chart (so we only pay for charts we keep)."""
    group: str
    build: Callable[[], ChartResult]


def _style(fig: go.Figure, title: str, xlabel: Optional[str] = None,
           ylabel: Optional[str] = None, legend: Optional[bool] = None) -> go.Figure:
    """Apply the shared look: title, axis labels, responsive sizing, legend."""
    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor="center"),
        template=TEMPLATE,
        autosize=True,
        height=CHART_HEIGHT,
        margin=dict(l=60, r=30, t=70, b=60),
        hoverlabel=dict(font_size=13),
    )
    if legend is not None:
        fig.update_layout(showlegend=legend)
    if xlabel is not None:
        fig.update_xaxes(title_text=xlabel)
    if ylabel is not None:
        fig.update_yaxes(title_text=ylabel)
    return fig


def _kind(profile: DatasetProfile, col: str) -> str:
    return profile.columns[col].kind


def _is_numeric(profile: DatasetProfile, col: str) -> bool:
    """True if the (cleaned) column stores numbers, regardless of its kind."""
    return profile.columns[col].is_numeric_dtype


def _finite(s: pd.Series) -> pd.Series:
    """Series with +/-inf replaced by NaN (charts cannot draw them)."""
    return s.replace([np.inf, -np.inf], np.nan) if pd.api.types.is_numeric_dtype(s) else s


def _as_labels(s: pd.Series) -> pd.Series:
    """Categorical values as strings; whole floats lose their '.0'."""
    if pd.api.types.is_float_dtype(s):
        s = s.map(lambda v: (str(int(v)) if float(v).is_integer() else str(v)) if pd.notna(v) else np.nan)
    return s.astype(object).where(s.notna(), np.nan).map(lambda v: str(v) if pd.notna(v) else v)


def _time_bin(s: pd.Series) -> pd.Series:
    """Round a datetime series to a coarser period when it has too many points."""
    valid = s.dropna()
    if valid.nunique() <= MAX_TIME_POINTS:
        return s
    days = (valid.max() - valid.min()).days
    if days < 1:
        return s.dt.floor("min")
    if days <= 14:
        return s.dt.floor("60min")
    for limit, alias in ((MAX_TIME_POINTS, "D"), (MAX_TIME_POINTS * 7, "W"),
                         (MAX_TIME_POINTS * 30, "M"), (MAX_TIME_POINTS * 91, "Q")):
        if days <= limit:
            return s.dt.to_period(alias).dt.to_timestamp()
    return s.dt.to_period("Y").dt.to_timestamp()


def _aggregate(df: pd.DataFrame, x: str, y: Optional[str], agg: str,
               x_is_datetime: bool = False) -> pd.DataFrame:
    """Group ``df`` by ``x`` and aggregate ``y`` -> columns ``[x, value]``."""
    if agg not in AGGREGATIONS:
        raise ChartError(f"Unknown aggregation '{agg}'. Choose one of: {', '.join(AGGREGATIONS)}.")
    d = df[[x] + ([y] if y else [])].copy()
    d = d.dropna(subset=[x])
    if x_is_datetime:
        d[x] = _time_bin(d[x])
    elif not pd.api.types.is_numeric_dtype(d[x]):
        d[x] = _as_labels(d[x])
    if y is None:
        return d.groupby(x, observed=True).size().rename("count").reset_index()
    d[y] = _finite(d[y])
    if agg == "count":
        out = d.groupby(x, observed=True)[y].count()
        label = f"count of {y}"
    else:
        if not pd.api.types.is_numeric_dtype(d[y]):
            raise ChartError(f"Aggregation '{agg}' needs a numeric Y column, but '{y}' is not numeric. "
                             f"Use 'count' or pick a numeric column.")
        out = d.groupby(x, observed=True)[y].agg(agg)
        label = f"{agg} of {y}"
    out = out.rename(label).reset_index()
    return out.dropna(subset=[label])


def _value_col(agg_df: pd.DataFrame, x: str) -> str:
    """Name of the aggregated value column produced by ``_aggregate``."""
    return [c for c in agg_df.columns if c != x][0]


def _need_rows(d: pd.DataFrame, minimum: int = 2, what: str = "data points") -> None:
    if len(d) < minimum:
        raise ChartError(f"Not enough {what} to draw this chart after removing missing values "
                         f"(found {len(d)}, need at least {minimum}).")


def _cap_categories(agg_df: pd.DataFrame, x: str, value: str, agg: str,
                    limit: int, add_other: bool = False):
    """Keep the top ``limit`` categories by value; optionally fold the rest into 'Other'."""
    if len(agg_df) <= limit:
        return agg_df, ""
    ordered = agg_df.sort_values(value, ascending=False)
    top, rest = ordered.head(limit), ordered.iloc[limit:]
    note = f" Showing the top {limit} of {len(agg_df)} categories."
    if add_other and agg in ("sum", "count"):
        other = pd.DataFrame({x: ["Other"], value: [rest[value].sum()]})
        top = pd.concat([top, other], ignore_index=True)
        note = f" The {len(rest)} smallest categories are grouped as 'Other'."
    return top, note


# Figure builders
def _fig_scatter(df: pd.DataFrame, x: str, y: str, color: Optional[str] = None,
                 title: Optional[str] = None) -> go.Figure:
    cols = [x, y] + ([color] if color else [])
    d = df[cols].copy()
    d[x], d[y] = _finite(d[x]), _finite(d[y])
    d = d.dropna(subset=[x, y])
    _need_rows(d, 2)
    sampled = ""
    if len(d) > MAX_SCATTER_POINTS:
        d = d.sample(MAX_SCATTER_POINTS, random_state=0)
        sampled = f" (random sample of {MAX_SCATTER_POINTS:,} points)"
    if color:
        d[color] = _as_labels(d[color]).fillna("(missing)")
    fig = px.scatter(d, x=x, y=y, color=color, opacity=0.7,
                     color_discrete_sequence=PALETTE if color else [PRIMARY])
    if pd.api.types.is_numeric_dtype(d[x]) and d[x].nunique() > 1 and d[y].nunique() > 1:
        slope, intercept = np.polyfit(d[x].astype(float), d[y].astype(float), 1)
        r = float(np.corrcoef(d[x].astype(float), d[y].astype(float))[0, 1])
        xs = np.array([d[x].min(), d[x].max()], dtype=float)
        fig.add_trace(go.Scatter(x=xs, y=slope * xs + intercept, mode="lines",
                                 name=f"Linear trend (r = {r:.2f})",
                                 line=dict(color="#E45756", dash="dash", width=2)))
    return _style(fig, (title or f"{y} vs {x}") + sampled, x, y, legend=True)


def _fig_line(agg_df: pd.DataFrame, x: str, title: str, xlabel: str) -> go.Figure:
    value = _value_col(agg_df, x)
    d = agg_df.sort_values(x)
    _need_rows(d, 2, "points on the X axis")
    fig = px.line(d, x=x, y=value, markers=len(d) <= 60, color_discrete_sequence=[PRIMARY])
    return _style(fig, title, xlabel, value)


def _fig_bar(agg_df: pd.DataFrame, x: str, title: str, xlabel: str,
             sort: bool = True) -> go.Figure:
    value = _value_col(agg_df, x)
    d = agg_df.sort_values(value, ascending=False) if sort else agg_df.sort_values(x)
    _need_rows(d, 1, "categories")
    horizontal = len(d) > 12 or d[x].astype(str).str.len().max() > 14
    if horizontal:
        fig = px.bar(d, x=value, y=x, orientation="h", color_discrete_sequence=[PRIMARY])
        fig.update_yaxes(autorange="reversed", type="category")
        return _style(fig, title, value, xlabel, legend=False)
    fig = px.bar(d, x=x, y=value, color_discrete_sequence=[PRIMARY])
    fig.update_xaxes(type="category")
    return _style(fig, title, xlabel, value, legend=False)


def _fig_pie(agg_df: pd.DataFrame, x: str, title: str) -> go.Figure:
    value = _value_col(agg_df, x)
    d = agg_df[agg_df[value] > 0]
    _need_rows(d, 2, "categories with positive values")
    fig = px.pie(d, names=x, values=value, hole=0.35, color_discrete_sequence=PALETTE)
    fig.update_traces(textposition="inside", textinfo="percent+label",
                      hovertemplate="%{label}<br>%{value:,.4g} (%{percent})<extra></extra>")
    return _style(fig, title, legend=True)


def _fig_hist(df: pd.DataFrame, x: str) -> go.Figure:
    d = df[[x]].copy()
    d[x] = _finite(d[x])
    d = d.dropna()
    _need_rows(d, 2)
    fig = px.histogram(d, x=x, nbins=30, marginal="box", color_discrete_sequence=[PRIMARY])
    return _style(fig, f"Distribution of {x}", x, "Number of rows", legend=False)


def _fig_box(df: pd.DataFrame, y: str, x: Optional[str] = None) -> go.Figure:
    cols = [y] + ([x] if x else [])
    d = df[cols].copy()
    d[y] = _finite(d[y])
    d = d.dropna(subset=[y])
    if x:
        d = d.dropna(subset=[x])
        d[x] = _as_labels(d[x])
        keep = d[x].value_counts().head(15).index
        d = d[d[x].isin(keep)]
    _need_rows(d, 2)
    fig = px.box(d, x=x, y=y, color=x, color_discrete_sequence=PALETTE, points="outliers")
    title = f"{y} by {x}" if x else f"Spread of {y}"
    return _style(fig, title, x, y, legend=False)


def _fig_heatmap(df: pd.DataFrame, cols: List[str]) -> go.Figure:
    if len(cols) < 2:
        raise ChartError("A correlation heatmap needs at least two numeric columns.")
    cols = rank_columns_by_completeness(df, cols)[:20]
    corr = df[cols].replace([np.inf, -np.inf], np.nan).corr(min_periods=3)
    corr = corr.dropna(how="all").dropna(axis=1, how="all")
    if corr.shape[0] < 2:
        raise ChartError("Not enough overlapping numeric values to compute correlations.")
    fig = px.imshow(corr, text_auto=".2f" if len(corr) <= 12 else False, zmin=-1, zmax=1,
                    color_continuous_scale="RdBu_r", aspect="auto")
    fig.update_traces(hovertemplate="%{y} vs %{x}<br>r = %{z:.3f}<extra></extra>")
    fig.update_layout(coloraxis_colorbar=dict(title="Pearson r"))
    return _style(fig, "Correlation heatmap of numeric columns", legend=None)


def _fig_grouped_counts(df: pd.DataFrame, x: str, y: str) -> go.Figure:
    """Category x category -> stacked bar of row counts."""
    d = df[[x, y]].dropna().copy()
    d[x], d[y] = _as_labels(d[x]), _as_labels(d[y])
    d = d[d[x].isin(d[x].value_counts().head(15).index) & d[y].isin(d[y].value_counts().head(10).index)]
    _need_rows(d, 2)
    counts = d.groupby([x, y]).size().rename("count").reset_index()
    fig = px.bar(counts, x=x, y="count", color=y, barmode="stack", color_discrete_sequence=PALETTE)
    fig.update_xaxes(type="category")
    return _style(fig, f"Number of rows by {x} and {y}", x, "count", legend=True)


# Automatic chart generation & candidates
def _numeric_measures(df: pd.DataFrame, profile: DatasetProfile) -> List[str]:
    return rank_columns_by_completeness(df, profile.numeric)


def _candidates_timeseries(df, profile) -> List[Candidate]:
    """Datetime x numeric -> line chart (or row count over time)."""
    out: List[Candidate] = []
    dts = rank_columns_by_completeness(df, profile.datetime)[:2]
    nums = _numeric_measures(df, profile)
    for dt in dts:
        if df[dt].nunique() < 3:
            continue
        for num in nums[:3]:
            out.append(Candidate("Time series", lambda dt=dt, num=num: _auto_line(df, dt, num)))
        if not nums:
            out.append(Candidate("Time series", lambda dt=dt: _auto_line(df, dt, None)))
    return out


def _auto_line(df, dt, num) -> ChartResult:
    agg = "mean" if num else "count"
    agg_df = _aggregate(df, dt, num, agg, x_is_datetime=True)
    value = _value_col(agg_df, dt)
    title = f"{value} over {dt}"
    fig = _fig_line(agg_df, dt, title, dt)
    return ChartResult(fig, title, f"Datetime x numeric -> line chart. Values with the same "
                       f"(or binned) date are combined using '{agg}'.", "Time series")


def _candidates_category_distribution(df, profile) -> List[Candidate]:
    """One categorical column -> pie (few values) or bar (many values)."""
    cats = [c for c in profile.categorical if profile.columns[c].n_unique >= 2]
    cats.sort(key=lambda c: (profile.columns[c].n_unique > 20, df[c].isna().mean(),
                             profile.columns[c].n_unique))
    return [Candidate("Category distribution", lambda c=c: _auto_distribution(df, profile, c))
            for c in cats[:4]]


def _auto_distribution(df, profile, col) -> ChartResult:
    counts = _aggregate(df, col, None, "count")
    n_unique = len(counts)
    if n_unique <= 6:
        fig = _fig_pie(counts, col, f"Share of rows by {col}")
        desc = "Categorical distribution (6 or fewer values) -> pie chart."
    else:
        capped, note = _cap_categories(counts, col, "count", "count", MAX_BAR_CATEGORIES)
        fig = _fig_bar(capped, col, f"Row count by {col}", col)
        desc = "Categorical distribution (many values) -> bar chart." + note
    return ChartResult(fig, fig.layout.title.text, desc, "Category distribution")


def _candidates_category_vs_numeric(df, profile) -> List[Candidate]:
    """Category x numeric -> bar chart of the mean."""
    cats = [c for c in profile.categorical if 2 <= profile.columns[c].n_unique <= 25]
    cats.sort(key=lambda c: (df[c].isna().mean(), profile.columns[c].n_unique))
    nums = _numeric_measures(df, profile)
    pairs = [(i + j, i, j) for i, _ in enumerate(cats[:3]) for j, _ in enumerate(nums[:3])]
    pairs.sort()
    return [Candidate("Category vs numeric",
                      lambda c=cats[i], n=nums[j]: _auto_cat_num(df, c, n)) for _, i, j in pairs]


def _auto_cat_num(df, cat, num) -> ChartResult:
    agg_df = _aggregate(df, cat, num, "mean")
    capped, note = _cap_categories(agg_df, cat, _value_col(agg_df, cat), "mean", MAX_BAR_CATEGORIES)
    value = _value_col(capped, cat)
    title = f"{value} by {cat}"
    fig = _fig_bar(capped, cat, title, cat)
    return ChartResult(fig, title, "Categorical x numeric -> bar chart of the mean." + note,
                       "Category vs numeric")


def _candidates_scatter(df, profile) -> List[Candidate]:
    """Numeric x numeric -> scatter for the most correlated pairs."""
    pairs = strong_correlations(df, profile, min_abs=0.3, top_n=4)
    if not pairs and len(profile.numeric) >= 2:
        a, b = _numeric_measures(df, profile)[:2]
        pairs = [(a, b, float(df[[a, b]].corr().iloc[0, 1]))]
    color = next((c for c in profile.categorical if 2 <= profile.columns[c].n_unique <= 8), None)
    return [Candidate("Numeric vs numeric", lambda a=a, b=b, r=r: _auto_scatter(df, a, b, r, color))
            for a, b, r in pairs]


def _auto_scatter(df, a, b, r, color) -> ChartResult:
    strength = "strong" if abs(r) >= 0.7 else "moderate" if abs(r) >= 0.3 else "weak"
    title = f"{b} vs {a}"
    fig = _fig_scatter(df, a, b, color=color, title=title)
    desc = f"Numeric x numeric -> scatter plot ({strength} correlation, r = {r:.2f})."
    if color:
        desc += f" Points are coloured by '{color}'."
    return ChartResult(fig, title, desc, "Numeric vs numeric")


def _candidates_heatmap(df, profile) -> List[Candidate]:
    if len(profile.numeric) < 2:
        return []
    return [Candidate("Correlation", lambda: ChartResult(
        _fig_heatmap(df, profile.numeric), "Correlation heatmap",
        "Several numeric columns -> correlation heatmap (Pearson r, -1 to +1).", "Correlation"))]


def _candidates_histograms(df, profile) -> List[Candidate]:
    return [Candidate("Numeric distribution", lambda n=n: ChartResult(
        _fig_hist(df, n), f"Distribution of {n}",
        "Single numeric column -> histogram with a box plot on top.", "Numeric distribution"))
        for n in _numeric_measures(df, profile)[:3]]


# (group name, budget in the first pass, candidate factory) - display order too.
AUTO_GROUPS = [
    ("Time series", 3, _candidates_timeseries),
    ("Category distribution", 2, _candidates_category_distribution),
    ("Category vs numeric", 3, _candidates_category_vs_numeric),
    ("Numeric vs numeric", 2, _candidates_scatter),
    ("Correlation", 1, _candidates_heatmap),
    ("Numeric distribution", 1, _candidates_histograms),
]


def generate_auto_charts(df: pd.DataFrame, profile: DatasetProfile,
                         max_charts: int = MAX_AUTO_CHARTS) -> List[ChartResult]:
    """Pick and render the most useful charts for this dataset."""
    candidates: Dict[str, List[Candidate]] = {}
    for name, budget, factory in AUTO_GROUPS:
        try:
            candidates[name] = factory(df, profile)
        except Exception:
            logger.exception("Candidate generation failed for group %s", name)
            candidates[name] = []

    chosen: List[Candidate] = []
    remaining: List[Candidate] = []
    for name, budget, _ in AUTO_GROUPS:
        chosen.extend(candidates[name][:budget])
        remaining.extend(candidates[name][budget:])
    for cand in remaining:
        if len(chosen) >= max_charts:
            break
        chosen.append(cand)
    chosen = chosen[:max_charts]

    group_order = {name: i for i, (name, _, _) in enumerate(AUTO_GROUPS)}
    chosen.sort(key=lambda c: group_order[c.group])

    results: List[ChartResult] = []
    for cand in chosen:
        try:
            results.append(cand.build())
        except ChartError as exc:
            logger.info("Skipped %s chart: %s", cand.group, exc)
        except Exception:
            logger.exception("Unexpected failure building a %s chart", cand.group)
    return results


# Custom chart builders
def _check_usable(profile: DatasetProfile, col: str, axis: str) -> None:
    """Reject columns that can never make a meaningful chart."""
    p = profile.columns[col]
    if p.kind == EMPTY:
        raise ChartError(f"{axis} column '{col}' has no usable values ({p.note}).")
    if p.kind == CONSTANT:
        raise ChartError(f"{axis} column '{col}' has only one unique value, so it cannot be charted.")
    if p.kind == TEXT:
        raise ChartError(f"{axis} column '{col}' is free text / has too many distinct values "
                         f"({p.n_unique:,}). Pick a numeric, date or category column.")
    if p.kind == IDENTIFIER and not p.is_numeric_dtype:
        raise ChartError(f"{axis} column '{col}' looks like an identifier (every value is unique).")


def _suggest_type(profile: DatasetProfile, x: str, y: Optional[str]) -> str:
    """The 'Auto' rule table for the custom chart."""
    xk = _kind(profile, x)
    y_num = y is not None and _is_numeric(profile, y)
    x_num = _is_numeric(profile, x) and xk in (NUMERIC, IDENTIFIER)
    if y is None:
        if xk == DATETIME:
            return "Line"
        if x_num:
            return "Histogram"
        return "Pie" if profile.columns[x].n_unique <= 6 else "Bar"
    if xk == DATETIME:
        if y_num:
            return "Line"
        raise ChartError(f"Cannot combine date column '{x}' with non-numeric '{y}'. Choose a numeric Y.")
    if x_num and y_num:
        return "Scatter"
    if not x_num and y_num:
        return "Bar"
    if x_num and not y_num:
        raise ChartError(f"'{x}' is numeric and '{y}' is not. Swap the axes (category on X, number on Y) "
                         f"or choose a chart type manually.")
    return "Bar"


def _custom_scatter(df, profile, x, y, agg) -> ChartResult:
    if y is None:
        raise ChartError("A scatter plot needs both X and Y. Select a numeric Y column.")
    x_ok = _is_numeric(profile, x) or _kind(profile, x) == DATETIME
    if not x_ok or not _is_numeric(profile, y):
        raise ChartError(f"A scatter plot needs a numeric (or date) X and a numeric Y. "
                         f"'{x}' is {_kind(profile, x)} and '{y}' is {_kind(profile, y)}. "
                         f"Try a Bar or Box chart instead.")
    color = next((c for c in profile.categorical if c not in (x, y)
                  and 2 <= profile.columns[c].n_unique <= 8), None)
    fig = _fig_scatter(df, x, y, color=color)
    desc = "Scatter plot of raw rows (aggregation is not applied)."
    if color:
        desc += f" Coloured by '{color}'."
    return ChartResult(fig, fig.layout.title.text, desc)


def _custom_line(df, profile, x, y, agg) -> ChartResult:
    if y is not None and not _is_numeric(profile, y) and agg != "count":
        raise ChartError(f"A line chart needs a numeric Y (or aggregation 'count'). '{y}' is not numeric.")
    xk = _kind(profile, x)
    is_dt = xk == DATETIME
    if not is_dt and not _is_numeric(profile, x):
        raise ChartError(f"A line chart needs a date or numeric X column; '{x}' is {xk}. "
                         f"Use a Bar chart for categories.")
    agg_df = _aggregate(df, x, y, agg if y else "count", x_is_datetime=is_dt)
    value = _value_col(agg_df, x)
    title = f"{value} by {x}"
    fig = _fig_line(agg_df, x, title, x)
    return ChartResult(fig, title, f"Line chart: '{agg if y else 'count'}' per {x} value, sorted by {x}.")


def _custom_bar(df, profile, x, y, agg) -> ChartResult:
    xk = _kind(profile, x)
    if y is not None and not _is_numeric(profile, y):
        if xk in (CATEGORICAL,) and _kind(profile, y) == CATEGORICAL:
            fig = _fig_grouped_counts(df, x, y)
            return ChartResult(fig, fig.layout.title.text, "Two categories -> stacked bar of row counts.")
        if agg != "count":
            raise ChartError(f"Y column '{y}' is not numeric, so '{agg}' cannot be computed. "
                             f"Choose aggregation 'count' or a numeric Y.")
    is_dt = xk == DATETIME
    if _is_numeric(profile, x) and xk in (NUMERIC, IDENTIFIER) and df[x].nunique() > MAX_BAR_CATEGORIES:
        raise ChartError(f"'{x}' is numeric with {df[x].nunique():,} distinct values, which would create "
                         f"too many bars. Use a Histogram, or pick a category column as X.")
    effective_agg = agg if y else "count"
    agg_df = _aggregate(df, x, y, effective_agg, x_is_datetime=is_dt)
    value = _value_col(agg_df, x)
    if is_dt:
        agg_df[x] = agg_df[x].astype(str)
    capped, note = _cap_categories(agg_df, x, value, effective_agg, MAX_BAR_CATEGORIES)
    title = f"{value} by {x}"
    sort_by_value = xk == CATEGORICAL and not _is_numeric(profile, x)
    fig = _fig_bar(capped, x, title, x, sort=sort_by_value)
    return ChartResult(fig, title, f"Bar chart: '{effective_agg}' per {x} value." + note)


def _custom_pie(df, profile, x, y, agg) -> ChartResult:
    if _kind(profile, x) == DATETIME or (_is_numeric(profile, x) and _kind(profile, x) != CATEGORICAL):
        raise ChartError(f"A pie chart needs a category column as X; '{x}' is {_kind(profile, x)}.")
    if y is not None and not _is_numeric(profile, y) and agg != "count":
        raise ChartError(f"A pie chart needs a numeric Y (or aggregation 'count'); '{y}' is not numeric.")
    if y is not None and agg in ("mean", "min", "max", "median"):
        raise ChartError(f"Pie slices are shares of a whole, so '{agg}' is not meaningful. "
                         f"Use 'sum' or 'count' (or a bar chart).")
    effective_agg = agg if y else "count"
    agg_df = _aggregate(df, x, y, effective_agg)
    value = _value_col(agg_df, x)
    if (agg_df[value] < 0).any():
        raise ChartError(f"'{value}' contains negative values, which cannot be shown as pie slices. "
                         f"Try a Bar chart.")
    capped, note = _cap_categories(agg_df, x, value, effective_agg, MAX_PIE_SLICES, add_other=True)
    title = f"{value} by {x}"
    fig = _fig_pie(capped, x, title)
    return ChartResult(fig, title, f"Pie chart of '{effective_agg}' per {x} value." + note)


def _custom_hist(df, profile, x, y, agg) -> ChartResult:
    if not _is_numeric(profile, x):
        raise ChartError(f"A histogram needs a numeric X column; '{x}' is {_kind(profile, x)}. "
                         f"Use a Bar chart to count categories.")
    fig = _fig_hist(df, x)
    note = " (Y is ignored for histograms.)" if y else ""
    return ChartResult(fig, fig.layout.title.text, "Histogram of a single numeric column." + note)


def _custom_box(df, profile, x, y, agg) -> ChartResult:
    if y is None:
        if not _is_numeric(profile, x):
            raise ChartError("A box plot needs a numeric column. Select a numeric X (or a numeric Y).")
        fig = _fig_box(df, y=x)
        return ChartResult(fig, fig.layout.title.text, "Box plot of one numeric column.")
    if not _is_numeric(profile, y):
        raise ChartError(f"A box plot needs a numeric Y; '{y}' is {_kind(profile, y)}.")
    if _kind(profile, x) == DATETIME or (_is_numeric(profile, x) and profile.columns[x].n_unique > 30):
        raise ChartError(f"A box plot groups Y by a category; '{x}' has too many distinct values or is a date.")
    fig = _fig_box(df, y=y, x=x)
    return ChartResult(fig, fig.layout.title.text, f"Box plot of '{y}' for each '{x}' group (top 15 groups).")


_CUSTOM_BUILDERS: Dict[str, Callable[..., ChartResult]] = {
    "Scatter": _custom_scatter,
    "Line": _custom_line,
    "Bar": _custom_bar,
    "Pie": _custom_pie,
    "Histogram": _custom_hist,
    "Box": _custom_box,
}


def build_custom_chart(df: pd.DataFrame, profile: DatasetProfile, x: Optional[str],
                       y: Optional[str] = None, chart_type: str = "Auto",
                       aggregation: str = "mean") -> ChartResult:
    """Render the chart requested by the user."""
    if chart_type not in CHART_TYPES:
        raise ChartError(f"Unknown chart type '{chart_type}'.")
    if aggregation not in AGGREGATIONS:
        raise ChartError(f"Unknown aggregation '{aggregation}'.")

    if chart_type == "Correlation Heatmap":
        cols = [c for c in profile.columns if _is_numeric(profile, c)
                and _kind(profile, c) not in (CONSTANT, EMPTY, IDENTIFIER)]
        fig = _fig_heatmap(df, cols)
        return ChartResult(fig, "Correlation heatmap", "Uses every numeric column (X/Y ignored).")

    y = None if (y in (None, "", "(none)")) else y
    if not x or x not in profile.columns:
        raise ChartError("Please select a valid X-axis column.")
    if y is not None and y not in profile.columns:
        raise ChartError(f"Y column '{y}' does not exist in this dataset.")
    if y is not None and y == x:
        raise ChartError("X and Y are the same column. Choose two different columns, or set Y to '(none)'.")
    _check_usable(profile, x, "X")
    if y is not None:
        _check_usable(profile, y, "Y")

    if chart_type == "Auto":
        chart_type = _suggest_type(profile, x, y)

    builder = _CUSTOM_BUILDERS[chart_type]
    return builder(df, profile, x, y, aggregation)


# =========================================================================== #
# Gradio Web Interface & Dashboard Layout
# =========================================================================== #

NONE_CHOICE = "(none)"          # dropdown entry meaning "no Y column"
PREVIEW_ROWS = 10
Session = Tuple[pd.DataFrame, DatasetProfile]   # what we keep in gr.State


def _display_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Make a dataframe safe/pretty for gr.Dataframe (dates -> text, NaN -> blank)."""
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d %H:%M:%S").str.replace(" 00:00:00", "", regex=False)
    return out.astype(object).where(out.notna(), "")


def _overview_markdown(df: pd.DataFrame, profile: DatasetProfile, filename: str) -> str:
    total_missing = int(sum(c.n_missing for c in profile.columns.values()))
    kinds = {}
    for c in profile.columns.values():
        kinds.setdefault(c.kind, []).append(c.name)
    lines = [
        f"### {filename}",
        f"**{profile.n_rows:,} rows x {profile.n_cols} columns** · {total_missing:,} missing cells",
        "",
    ]
    for kind in (NUMERIC, CATEGORICAL, DATETIME, TEXT, IDENTIFIER, CONSTANT, EMPTY):
        if kind in kinds:
            lines.append(f"- **{kind.capitalize()}** ({len(kinds[kind])}): " + ", ".join(f"`{n}`" for n in kinds[kind]))
    return "\n".join(lines)


def _status(message: str, ok: bool = True) -> str:
    return f"{'✅' if ok else '❌'} {message}"


def _uploaded_path(file_value) -> Optional[str]:
    """Gradio returns a path string (or an object with .name, depending on version)."""
    if file_value is None:
        return None
    return file_value if isinstance(file_value, str) else getattr(file_value, "name", None)


# --------------------------------------------------------------------------- #
# UI
# --------------------------------------------------------------------------- #
with gr.Blocks(title="Automatic Chart Generator") as demo:
    gr.Markdown(
        "# 📊 Automatic Chart Generator\n"
        "Upload any CSV file. The app detects column types and builds suitable charts automatically. "
        "You can then design your own chart in the **Custom chart** tab."
    )
    session = gr.State(None)  # (clean_df, profile) for the current upload

    # ---- 1. Upload ---------------------------------------------------------
    file_input = gr.File(label="Upload a CSV file", file_types=[".csv"], type="filepath")
    status_md = gr.Markdown("Waiting for a CSV file…")

    with gr.Tabs():
        # ---- 2. Dataset preview ---------------------------------------------
        with gr.Tab("1 · Dataset preview"):
            overview_md = gr.Markdown()
            preview_df = gr.Dataframe(label=f"First {PREVIEW_ROWS} rows", interactive=False, wrap=True)
            info_df = gr.Dataframe(label="Columns: detected types and missing values", interactive=False, wrap=True)

        # ---- 3. Statistics ----------------------------------------------------
        with gr.Tab("2 · Dataset statistics"):
            stats_df = gr.Dataframe(label="Descriptive statistics per column", interactive=False, wrap=True)

        # ---- 4. Automatic charts ------------------------------------------
        with gr.Tab("3 · Automatic charts"):
            auto_md = gr.Markdown()
            auto_plots = []
            for _ in range(0, MAX_AUTO_CHARTS, 2):        # two charts per row
                with gr.Row():
                    for _ in range(2):
                        auto_plots.append(gr.Plot(visible=False, show_label=True))

        # ---- 5. Custom chart ----------------------------------------------
        with gr.Tab("4 · Custom chart"):
            with gr.Row():
                x_dd = gr.Dropdown(label="X-axis column", choices=[], interactive=True)
                y_dd = gr.Dropdown(label="Y-axis column (optional)", choices=[NONE_CHOICE],
                                   value=NONE_CHOICE, interactive=True)
                type_dd = gr.Dropdown(label="Chart type", choices=CHART_TYPES, value="Auto")
                agg_dd = gr.Dropdown(label="Aggregation", choices=AGGREGATIONS, value="mean")
            gr.Markdown(
                "*Auto* picks the chart from the column types. Aggregation is used by Bar, Line and Pie charts "
                "(with no Y column, rows are counted). Scatter, Histogram, Box and the heatmap use raw values."
            )
            custom_btn = gr.Button("Generate custom chart", variant="primary")
            custom_msg = gr.Markdown()
            custom_plot = gr.Plot(label="Custom chart")

    # ------------------------------------------------------------------ #
    # Event handlers
    # ------------------------------------------------------------------ #
    def _reset_outputs(message: str) -> dict:
        """Blank everything (used on clear / on error)."""
        out = {
            status_md: message, overview_md: "", preview_df: None, info_df: None, stats_df: None,
            auto_md: "", x_dd: gr.update(choices=[], value=None),
            y_dd: gr.update(choices=[NONE_CHOICE], value=NONE_CHOICE),
            session: None, custom_plot: None, custom_msg: "",
        }
        for plot in auto_plots:
            out[plot] = gr.update(value=None, visible=False)
        return out

    ALL_OUTPUTS = [status_md, overview_md, preview_df, info_df, stats_df, auto_md, x_dd, y_dd,
                   session, custom_plot, custom_msg, *auto_plots]

    def process_upload(file_value) -> dict:
        """Load the CSV, profile it, and generate every automatic chart."""
        path = _uploaded_path(file_value)
        if path is None:
            return _reset_outputs("Waiting for a CSV file…")
        if not path.lower().endswith(".csv"):
            return _reset_outputs(_status("Please upload a file with the .csv extension.", ok=False))
        try:
            raw = load_csv(path)
            df, profile = prepare_dataframe(raw)
        except DataLoadError as exc:
            return _reset_outputs(_status(str(exc), ok=False))
        except Exception as exc:
            logger.exception("Unexpected error while loading CSV")
            return _reset_outputs(_status(f"Unexpected error while reading the file: {exc}", ok=False))

        # Charts are best-effort: a failure here must not hide the dataset info.
        try:
            charts = generate_auto_charts(df, profile)
        except Exception:
            logger.exception("Automatic chart generation failed")
            charts = []

        filename = os.path.basename(path)
        out = {
            status_md: _status(f"Loaded **{filename}**: {profile.n_rows:,} rows, {profile.n_cols} columns."),
            overview_md: _overview_markdown(df, profile, filename),
            preview_df: _display_frame(df.head(PREVIEW_ROWS)),
            info_df: column_info_table(profile),
            stats_df: summary_statistics(df, profile),
            session: (df, profile),
            custom_plot: None,
            custom_msg: "",
        }

        if charts:
            out[auto_md] = (f"**{len(charts)} chart(s)** generated automatically. Hover over a chart for "
                            "tooltips; each chart's caption explains why it was chosen.")
        else:
            usable = [c.name for c in profile.columns.values() if c.usable]
            reason = ("no columns look suitable for charting (they may be identifiers, free text, constant or "
                      "mostly empty)" if not usable else "the columns do not combine into meaningful charts")
            out[auto_md] = (f"⚠️ No automatic charts could be generated: {reason}. "
                            "Try the **Custom chart** tab.")
        for i, plot in enumerate(auto_plots):
            if i < len(charts):
                out[plot] = gr.update(value=charts[i].figure, visible=True,
                                      label=f"{charts[i].group}: {charts[i].description}")
            else:
                out[plot] = gr.update(value=None, visible=False)

        names = list(profile.columns)
        x_default, y_default = suggest_default_axes(profile)
        out[x_dd] = gr.update(choices=names, value=x_default)
        out[y_dd] = gr.update(choices=[NONE_CHOICE] + names, value=y_default or NONE_CHOICE)
        return out

    def build_custom(x, y, chart_type, aggregation, sess: Optional[Session]) -> dict:
        """Render the user-configured chart; show errors instead of crashing."""
        if not sess:
            return {custom_plot: None, custom_msg: "⚠️ Please upload a CSV file first."}
        df, profile = sess
        try:
            result = build_custom_chart(df, profile, x, y, chart_type, aggregation)
        except ChartError as exc:
            return {custom_plot: None, custom_msg: f"⚠️ {exc}"}
        except Exception as exc:
            logger.exception("Custom chart failed")
            return {custom_plot: None,
                    custom_msg: f"⚠️ Could not draw this chart ({type(exc).__name__}: {exc}). "
                                "Try a different column or chart type."}
        return {custom_plot: result.figure, custom_msg: f"✅ {result.description}"}

    file_input.change(process_upload, inputs=file_input, outputs=ALL_OUTPUTS, show_progress="minimal")
    custom_btn.click(build_custom, inputs=[x_dd, y_dd, type_dd, agg_dd, session],
                     outputs=[custom_plot, custom_msg])


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    host = os.environ.get("GRADIO_SERVER_NAME", "0.0.0.0")
    demo.queue().launch(
        server_name=host,
        server_port=port,
        allowed_paths=[str(BASE_DIR)]
    )
