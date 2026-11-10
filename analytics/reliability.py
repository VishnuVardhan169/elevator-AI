"""Reliability KPIs for elevator fleets: MTBF, MTTR, availability, failure rate, Weibull.

Input: an events table with one row per failure/outage:
    unit_id, start (timestamp), [end (timestamp) | duration_h], [component]
Observation window defaults to min(start)..max(end or start).

Usage:  .venv/bin/python -m analytics.reliability <events_file> --unit COL --start COL [--end COL | --duration COL]
                                                   [--component COL] [--n-units N] [--out reports/x.md]
"""
import argparse

import numpy as np
import pandas as pd
from scipy import stats

from . import REPORTS, load_table


def prepare(df, unit, start, end=None, duration=None, component=None) -> pd.DataFrame:
    e = pd.DataFrame({"unit_id": df[unit].astype(str), "start": pd.to_datetime(df[start], errors="coerce")})
    if end:
        e["end"] = pd.to_datetime(df[end], errors="coerce")
    elif duration:
        e["end"] = e.start + pd.to_timedelta(pd.to_numeric(df[duration], errors="coerce"), unit="h")
    else:
        e["end"] = pd.NaT
    e["repair_h"] = (e.end - e.start).dt.total_seconds() / 3600
    e["component"] = df[component].astype(str) if component else "ALL"
    return e.dropna(subset=["start"]).sort_values(["unit_id", "start"])


def kpis(e: pd.DataFrame, n_units: int | None = None, window=None) -> dict:
    w0, w1 = window or (e.start.min(), e[["start", "end"]].max().max())
    hours = (w1 - w0).total_seconds() / 3600
    n_units = n_units or e.unit_id.nunique()
    unit_hours = hours * n_units
    downtime = e.repair_h.clip(lower=0).sum(min_count=1)
    n = len(e)
    return {
        "window": [str(w0), str(w1)], "units": n_units, "failures": n,
        "failures_per_unit_year": round(n / unit_hours * 8760, 3) if unit_hours else None,
        "MTBF_h": round((unit_hours - (downtime or 0)) / n, 1) if n else None,
        "MTTR_h": round(float(e.repair_h.mean()), 2) if e.repair_h.notna().any() else None,
        "MTTR_median_h": round(float(e.repair_h.median()), 2) if e.repair_h.notna().any() else None,
        "availability_pct": round(100 * (1 - downtime / unit_hours), 3) if pd.notna(downtime) and unit_hours else None,
    }


def weibull(e: pd.DataFrame) -> dict:
    """Fit Weibull to time-between-failures per unit. beta<1 infant mortality, ~1 random, >1 wear-out."""
    tbf = e.groupby(["unit_id", "component"]).start.diff().dt.total_seconds().dropna() / 3600
    tbf = tbf[tbf > 0]
    if len(tbf) < 10:
        return {"n_intervals": int(len(tbf)), "note": "too few intervals for a Weibull fit"}
    beta, _, eta = stats.weibull_min.fit(tbf, floc=0)
    regime = "infant mortality / early failures" if beta < 0.9 else "random failures" if beta < 1.1 else "wear-out"
    return {"n_intervals": int(len(tbf)), "beta_shape": round(beta, 3), "eta_scale_h": round(eta, 1),
            "regime": regime, "B10_life_h": round(eta * (-np.log(0.9)) ** (1 / beta), 1),
            "median_tbf_h": round(float(tbf.median()), 1)}


def by_group(e: pd.DataFrame, col: str, n_units_map: dict | None = None) -> pd.DataFrame:
    rows = []
    for g, sub in e.groupby(col):
        rows.append({col: g, **kpis(sub, n_units=(n_units_map or {}).get(g))})
    return pd.DataFrame(rows).sort_values("failures", ascending=False)


def worst_units(e: pd.DataFrame, top: int = 15) -> pd.DataFrame:
    return (e.groupby("unit_id").agg(failures=("start", "size"), downtime_h=("repair_h", "sum"),
                                     last_failure=("start", "max"))
            .sort_values(["failures", "downtime_h"], ascending=False).head(top))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--unit", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end")
    ap.add_argument("--duration")
    ap.add_argument("--component")
    ap.add_argument("--n-units", type=int)
    ap.add_argument("--out")
    a = ap.parse_args()
    e = prepare(load_table(a.file), a.unit, a.start, a.end, a.duration, a.component)
    md = ["# Reliability KPIs", "", "## Fleet", ""]
    md += [f"- **{k}**: {v}" for k, v in kpis(e, a.n_units).items()]
    md += ["", "## Weibull (time between failures)", ""] + [f"- **{k}**: {v}" for k, v in weibull(e).items()]
    if a.component:
        md += ["", "## By component", "", by_group(e, "component").to_markdown(index=False)]
    md += ["", "## Worst units", "", worst_units(e).to_markdown()]
    text = "\n".join(md) + "\n"
    if a.out:
        REPORTS.mkdir(exist_ok=True)
        open(a.out, "w", encoding="utf-8").write(text)
    print(text)


if __name__ == "__main__":
    main()
