"""Model-validation helpers: time/group splits, leakage scan, threshold derivation.

Usage (leakage scan):
  .venv/bin/python -m analytics.validation <file> --target COL [--time-col COL] [--group-col COL]
"""
import argparse

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from . import load_table


def time_split(df: pd.DataFrame, time_col: str, cutoff=None, test_frac: float = 0.25, gap: str | None = None):
    """Chronological split. `gap` (e.g. '24h') drops rows just before the cutoff to stop label-window bleed."""
    t = pd.to_datetime(df[time_col])
    cutoff = pd.Timestamp(cutoff) if cutoff else t.quantile(1 - test_frac)
    train_end = cutoff - pd.Timedelta(gap) if gap else cutoff
    return df[t < train_end], df[t >= cutoff]


def group_split(df: pd.DataFrame, group_col: str, test_frac: float = 0.25, seed: int = 42):
    """Hold out whole units (elevators) to test generalisation to unseen equipment."""
    groups = df[group_col].drop_duplicates().sample(frac=1, random_state=seed)
    test = set(groups.iloc[: max(1, int(len(groups) * test_frac))])
    return df[~df[group_col].isin(test)], df[df[group_col].isin(test)]


def leakage_scan(df: pd.DataFrame, target: str, time_col: str | None = None, group_col: str | None = None) -> list[dict]:
    """Flag features that alone almost perfectly predict the target, identifiers, and future-dated columns."""
    y = df[target]
    findings = []
    binary = y.nunique() == 2
    for c in df.columns.drop([target]):
        s = df[c]
        if c in (time_col, group_col):
            continue
        if s.nunique() == len(s):
            findings.append({"feature": c, "issue": "unique per row (identifier) - drop before modelling"})
            continue
        if not pd.api.types.is_numeric_dtype(s) or not binary:
            continue
        ok = s.notna()
        if ok.sum() < 20 or y[ok].nunique() < 2:
            continue
        auc = roc_auc_score(y[ok], s[ok])
        auc = max(auc, 1 - auc)
        if auc > 0.98:
            findings.append({"feature": c, "issue": f"single-feature AUC {auc:.4f} - check it is known BEFORE the label time"})
        name = c.lower()
        if any(k in name for k in ("repair", "fixed", "resolved", "after", "next", "outcome", "closed", "rul")):
            findings.append({"feature": c, "issue": "name suggests post-event information"})
    if group_col and time_col:
        t = pd.to_datetime(df[time_col])
        dup = df.assign(_t=t).duplicated([group_col, "_t"]).sum()
        if dup:
            findings.append({"feature": f"{group_col}+{time_col}", "issue": f"{dup} duplicate unit-timestamps (random splits will leak)"})
    return findings


def percentile_thresholds(values: pd.Series, direction: str = "high",
                          levels=(("PRELIMINARY", 0.95), ("WARNING", 0.99), ("LEVEL_3", 0.999))) -> dict:
    v = pd.Series(values).dropna()
    return {lvl: float(v.quantile(q if direction == "high" else 1 - q)) for lvl, q in levels}


def robust_z_thresholds(values: pd.Series, direction: str = "high", z=(3, 4.5, 6)) -> dict:
    """Median +/- k * 1.4826 * MAD; resistant to the very anomalies we want to catch."""
    v = pd.Series(values).dropna()
    med, mad = v.median(), 1.4826 * (v - v.median()).abs().median()
    sign = 1 if direction == "high" else -1
    return {lvl: float(med + sign * k * mad) for lvl, k in zip(("PRELIMINARY", "WARNING", "LEVEL_3"), z)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--target", required=True)
    ap.add_argument("--time-col")
    ap.add_argument("--group-col")
    ap.add_argument("--nrows", type=int)
    a = ap.parse_args()
    df = load_table(a.file, nrows=a.nrows)
    f = leakage_scan(df, a.target, a.time_col, a.group_col)
    print("No leakage signals found." if not f else "\n".join(f"- {x['feature']}: {x['issue']}" for x in f))


if __name__ == "__main__":
    main()
