"""Deterministic checks. Every number the LLM sees comes from here, never from the LLM itself."""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

PLACEHOLDERS = {"*", "-", "--", "n/a", "na", "nan", "null", "none", "?", ""}


def _py(v: Any) -> Any:
    """numpy/pandas scalars -> plain Python, so results serialise to JSON."""
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return None if np.isnan(v) else round(float(v), 4)
    if isinstance(v, (pd.Timestamp,)):
        return v.isoformat()
    if v is pd.NA or (isinstance(v, float) and np.isnan(v)):
        return None
    return v


def numeric(series: pd.Series) -> pd.Series:
    """Values that parse as numbers; placeholders and text become NaN."""
    return pd.to_numeric(series.astype(str).str.strip().str.replace(",", ".", regex=False), errors="coerce")


def is_placeholder(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(PLACEHOLDERS) | series.isna()


# --------------------------------------------------------------------------- 1 profile

def profile(df: pd.DataFrame) -> dict:
    cols = []
    for c in df.columns:
        s = df[c]
        num = numeric(s)
        cols.append({
            "column": c,
            "dtype": str(s.dtype),
            "non_null": int(s.notna().sum()),
            "distinct": int(s.nunique(dropna=True)),
            "numeric_share": round(float(num.notna().mean()), 3),
            "examples": [_py(v) for v in s.dropna().astype(str).unique()[:6]],
        })
    return {"rows": int(len(df)), "columns": len(df.columns), "column_profiles": cols,
            "head": df.head(5).astype(str).to_dict(orient="records")}


# --------------------------------------------------------------------------- 2 quality

def quality(df: pd.DataFrame, key: list[str]) -> dict:
    out: dict[str, Any] = {"rows": int(len(df))}
    out["duplicate_rows"] = int(df.duplicated().sum())
    out["duplicate_keys"] = {
        "key": key,
        "count": int(df.duplicated(subset=key).sum()),
        "examples": df[df.duplicated(subset=key, keep=False)].head(6).astype(str).to_dict(orient="records"),
    }
    cols = {}
    for c in df.columns:
        s = df[c]
        text = s.astype(str)
        num = numeric(s)
        info: dict[str, Any] = {
            "missing": int(s.isna().sum()),
            "placeholders": {k: int(v) for k, v in text.str.strip().str.lower()[text.str.strip().str.lower().isin(PLACEHOLDERS)].value_counts().items()},
            "leading_trailing_spaces": int((text != text.str.strip()).sum()),
            "numeric_share": round(float(num.notna().mean()), 3),
        }
        if info["numeric_share"] > 0.5:
            v = num.dropna()
            q1, q3 = v.quantile(0.25), v.quantile(0.75)
            iqr = q3 - q1
            lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            outl = df.loc[(num < lo) | (num > hi)]
            info.update(min=_py(v.min()), max=_py(v.max()), negatives=int((v < 0).sum()), zeros=int((v == 0).sum()),
                        iqr_outliers={"count": int(len(outl)), "low_fence": _py(lo), "high_fence": _py(hi),
                                      "examples": outl.head(5).astype(str).to_dict(orient="records")})
        else:
            near = _near_duplicates(s.dropna().astype(str).unique())
            if near:
                info["similar_spellings"] = near[:10]
        cols[c] = info
    out["columns"] = cols
    if "year" in df.columns:
        per_year = df.groupby("year").size()
        out["rows_per_year"] = {str(k): int(v) for k, v in per_year.items()}
    return out


def _near_duplicates(values) -> list[list[str]]:
    """Values that differ only by case, accents-free spacing or punctuation ("Esch-sur-Alzette" / "Esch sur Alzette")."""
    groups: dict[str, set[str]] = {}
    for v in values:
        k = re.sub(r"[^a-z0-9]", "", str(v).lower())
        groups.setdefault(k, set()).add(str(v))
    return [sorted(g) for g in groups.values() if len(g) > 1]


# --------------------------------------------------------------------------- 3 integrity

RULE_TYPES = ["not_null", "unique", "range", "allowed_values", "numeric", "ratio_range"]


def check_rule(df: pd.DataFrame, rule: dict) -> dict:
    """Run one validation rule. Rules come from the profile step's LLM (or the defaults), as data, never code."""
    t = rule.get("type")
    col = rule.get("column")
    try:
        if t == "not_null":
            bad = df[is_placeholder(df[col])]
        elif t == "unique":
            cols = rule.get("columns") or [col]
            bad = df[df.duplicated(subset=cols, keep=False)]
        elif t == "numeric":
            s = df[col]
            allowed = set(rule.get("values") or [])
            bad = df[numeric(s).isna() & ~s.astype(str).str.strip().isin(allowed)]
        elif t == "range":
            v = numeric(df[col])
            lo, hi = rule.get("min"), rule.get("max")
            mask = pd.Series(False, index=df.index)
            if lo is not None:
                mask |= v < lo
            if hi is not None:
                mask |= v > hi
            bad = df[mask]
        elif t == "allowed_values":
            bad = df[~df[col].astype(str).isin([str(x) for x in rule.get("values") or []])]
        elif t == "ratio_range":
            ratio = numeric(df[rule["numerator"]]) / numeric(df[rule["denominator"]])
            lo, hi = rule.get("min"), rule.get("max")
            mask = pd.Series(False, index=df.index)
            if lo is not None:
                mask |= ratio < lo
            if hi is not None:
                mask |= ratio > hi
            bad = df[mask]
        else:
            return {"rule": rule, "status": "skipped", "reason": f"unknown rule type {t!r} (known: {RULE_TYPES})"}
    except KeyError as e:
        return {"rule": rule, "status": "skipped", "reason": f"column not found: {e}"}
    return {"rule": rule, "status": "pass" if bad.empty else "fail", "violations": int(len(bad)),
            "examples": bad.head(5).astype(str).to_dict(orient="records")}


def default_rules(key: list[str]) -> list[dict]:
    return [{"type": "unique", "columns": key, "reason": "one row per key"}]


# --------------------------------------------------------------------------- data for the statistics tools

def analysis_frame(df: pd.DataFrame, numeric_cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in numeric_cols:
        if c in out.columns:
            out[c] = numeric(out[c])
    if "year" in out.columns:
        out["year"] = numeric(out["year"]).astype("Int64")
    return out
