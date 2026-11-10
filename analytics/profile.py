"""Dataset profiler: schema, quality, distributions, redundancy, time structure.

Usage:  .venv/bin/python -m analytics.profile <file> [--time-col COL] [--id-col COL] [--nrows N] [--out reports/x.md]
"""
import argparse
import json

import numpy as np
import pandas as pd

from . import REPORTS, load_table


def _detect_time_col(df: pd.DataFrame) -> str | None:
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            return c
    for c in df.columns:
        if df[c].dtype == object and any(k in c.lower() for k in ("time", "date", "month", "day")):
            parsed = pd.to_datetime(df[c], errors="coerce")
            if parsed.notna().mean() > 0.9:
                df[c] = parsed
                return c
    return None


def profile(df: pd.DataFrame, time_col: str | None = None, id_col: str | None = None) -> dict:
    time_col = time_col or _detect_time_col(df)
    if time_col and not pd.api.types.is_datetime64_any_dtype(df[time_col]):
        df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    num = df.select_dtypes("number")
    cols = []
    for c in df.columns:
        s = df[c]
        info = {"column": c, "dtype": str(s.dtype), "null_pct": round(s.isna().mean() * 100, 2),
                "unique": int(s.nunique()), "constant": bool(s.nunique(dropna=True) <= 1)}
        if c in num:
            d = s.describe()
            info.update({k: round(float(d[k]), 4) for k in ("mean", "std", "min", "50%", "max") if k in d})
            info["skew"] = round(float(s.skew()), 3) if s.notna().sum() > 2 else None
            q1, q3 = s.quantile([0.25, 0.75])
            iqr = q3 - q1
            info["outlier_pct_iqr"] = round(float(((s < q1 - 3 * iqr) | (s > q3 + 3 * iqr)).mean() * 100), 3)
        else:
            info["top_values"] = s.astype(str).value_counts().head(5).to_dict()
        cols.append(info)

    corr = num.corr() if num.shape[1] > 1 else pd.DataFrame()
    redundant, strong = [], []
    for i, a in enumerate(corr.columns):
        for b in corr.columns[i + 1:]:
            r = corr.loc[a, b]
            if pd.notna(r) and abs(r) >= 0.999:
                redundant.append({"a": a, "b": b, "r": round(float(r), 5)})
            elif pd.notna(r) and abs(r) >= 0.7:
                strong.append({"a": a, "b": b, "r": round(float(r), 3)})

    out = {
        "rows": len(df), "columns": df.shape[1],
        "duplicate_rows": int(df.duplicated().sum()),
        "memory_mb": round(df.memory_usage(deep=True).sum() / 1e6, 1),
        "columns_detail": cols,
        "redundant_pairs_r>=0.999": redundant,
        "strong_pairs_r>=0.7": strong,
        "max_abs_offdiag_corr": round(float((corr.abs() - np.eye(len(corr))).max().max()), 4) if len(corr) else None,
    }
    if time_col:
        t = df[time_col].dropna()
        key = [id_col] if id_col else []
        g = df.sort_values(key + [time_col]).groupby(key)[time_col] if key else df.sort_values(time_col)[time_col]
        deltas = g.diff().dropna()
        out["time"] = {
            "column": time_col, "start": str(t.min()), "end": str(t.max()),
            "top_intervals": {str(k): int(v) for k, v in deltas.value_counts().head(3).items()},
            "hour_of_day_counts": t.dt.hour.value_counts().sort_index().to_dict() if t.dt.hour.nunique() > 1 else "single hour",
        }
    if id_col:
        per = df.groupby(id_col).size()
        out["units"] = {"column": id_col, "n_units": int(per.size), "rows_per_unit": per.describe().round(1).to_dict()}
    return out


def to_markdown(p: dict, title: str) -> str:
    lines = [f"# Profile: {title}", "", f"- Rows: **{p['rows']:,}**, columns: **{p['columns']}**, "
             f"duplicate rows: {p['duplicate_rows']}, memory: {p['memory_mb']} MB"]
    if "time" in p:
        t = p["time"]
        lines.append(f"- Time column `{t['column']}`: {t['start']} -> {t['end']}; most common intervals {t['top_intervals']}")
    if "units" in p:
        lines.append(f"- Units (`{p['units']['column']}`): {p['units']['n_units']}, rows/unit {p['units']['rows_per_unit']}")
    lines.append(f"- Max |corr| between numeric columns: {p['max_abs_offdiag_corr']}")
    lines += ["", "## Columns", "", "| column | dtype | null % | unique | mean | std | min | median | max | skew | outlier % |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in p["columns_detail"]:
        lines.append("| " + " | ".join(str(c.get(k, "")) for k in
                     ("column", "dtype", "null_pct", "unique", "mean", "std", "min", "50%", "max", "skew", "outlier_pct_iqr")) + " |")
    if p["redundant_pairs_r>=0.999"]:
        lines += ["", "## Redundant (derived) columns |r| >= 0.999", ""] + [
            f"- `{d['a']}` ~ `{d['b']}` (r={d['r']})" for d in p["redundant_pairs_r>=0.999"]]
    if p["strong_pairs_r>=0.7"]:
        lines += ["", "## Strong correlations", ""] + [f"- `{d['a']}` ~ `{d['b']}` (r={d['r']})" for d in p["strong_pairs_r>=0.7"]]
    const = [c["column"] for c in p["columns_detail"] if c["constant"]]
    if const:
        lines += ["", f"**Constant columns:** {const}"]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--time-col")
    ap.add_argument("--id-col")
    ap.add_argument("--nrows", type=int)
    ap.add_argument("--out")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    df = load_table(a.file, nrows=a.nrows)
    p = profile(df, a.time_col, a.id_col)
    if a.json:
        print(json.dumps(p, indent=2, default=str))
        return
    md = to_markdown(p, a.file)
    if a.out:
        REPORTS.mkdir(exist_ok=True)
        open(a.out, "w", encoding="utf-8").write(md)
        print(f"wrote {a.out}")
    print(md)


if __name__ == "__main__":
    main()
