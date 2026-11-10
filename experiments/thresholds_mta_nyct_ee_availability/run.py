"""Alert thresholds for MTA-operated subway ELEVATORS from monthly KPIs (/alert-thresholds).

Decision time: end of each month. Signals known then: this month's unscheduled outages, 24h availability,
3-month rolling unscheduled outages. Evaluation targets (next month): >=1 entrapment; 24h availability < 90%.
Fit thresholds on months < CUTOFF (~first 75%), evaluate on months >= CUTOFF.
EMERGENCY is rule-based (any entrapment = passenger trapped), not threshold-based.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from analytics.validation import percentile_thresholds, robust_z_thresholds  # noqa: E402

OUT = Path(__file__).parent
CUTOFF = pd.Timestamp("2023-10-01")
LEVELS = ["PRELIMINARY", "WARNING", "LEVEL_3"]

a = pd.read_parquet(ROOT / "data/curated/mta_nyct_ee_availability/aggregates.parquet")
u = pd.read_parquet(ROOT / "data/curated/mta_nyct_ee_availability/units.parquet")
a = a.merge(u[["unit_id", "unit_type", "operator"]], on="unit_id")
a = a[(a.unit_type == "elevator") & (a.operator == "MTA") & (a.hours_total_24h > 0)].sort_values(["unit_id", "period_start"])
g = a.groupby("unit_id")
a["unsched_3m"] = g.outages_unscheduled.transform(lambda s: s.rolling(3, min_periods=3).sum())
a["y_entrap_next"] = (g.entrapments.shift(-1) > 0).astype(float).where(g.entrapments.shift(-1).notna())
a["y_lowavail_next"] = (g.availability_24h_pct.shift(-1) < 90).astype(float).where(g.availability_24h_pct.shift(-1).notna())
a = a.dropna(subset=["y_entrap_next", "y_lowavail_next"])
train, test = a[a.period_start < CUTOFF], a[a.period_start >= CUTOFF]

SIGNALS = {"outages_unscheduled": "high", "unsched_3m": "high", "availability_24h_pct": "low"}
TARGET = {"outages_unscheduled": "y_entrap_next", "unsched_3m": "y_entrap_next", "availability_24h_pct": "y_lowavail_next"}


def label_driven(df, col, direction, target, precisions=(0.30, 0.45, 0.60)):
    """Smallest (high) / largest (low) threshold whose precision on train reaches each target."""
    d = df.dropna(subset=[col])
    vals = np.unique(d[col].quantile(np.linspace(0.5, 0.999, 300)))
    out = {}
    for lvl, ptarget in zip(LEVELS, precisions):
        best = None
        for v in (vals if direction == "high" else vals[::-1]):
            hit = d[col] >= v if direction == "high" else d[col] <= v
            if hit.sum() >= 30 and d.loc[hit, target].mean() >= ptarget:
                best = float(v)
                break
        out[lvl] = best
    return out


def evaluate(df, col, direction, th, target):
    d = df.dropna(subset=[col])
    rows, n_months = [], d.period_start.nunique()
    base = d[target].mean()
    for lvl in LEVELS:
        t = th.get(lvl)
        if t is None:
            rows.append({"level": lvl, "threshold": None})
            continue
        hit = d[col] >= t if direction == "high" else d[col] <= t
        rows.append({
            "level": lvl, "threshold": round(t, 2),
            "share_unit_months_flagged_pct": round(hit.mean() * 100, 2),
            "alerts_per_month_fleet": round(hit.sum() / n_months, 1),
            "precision_pct": round(d.loc[hit, target].mean() * 100, 1) if hit.any() else None,
            "lift_vs_base": round(d.loc[hit, target].mean() / base, 2) if hit.any() else None,
            "recall_pct": round(d.loc[hit, target].sum() / d[target].sum() * 100, 1),
        })
    return {"base_rate_pct": round(base * 100, 2), "levels": rows}


results = {"scope": "MTA-operated elevators, unit-months with >0 counted hours",
           "train": [str(train.period_start.min().date()), str(train.period_start.max().date()), len(train)],
           "test": [str(test.period_start.min().date()), str(test.period_start.max().date()), len(test)],
           "signals": {}}
for col, direction in SIGNALS.items():
    tgt = TARGET[col]
    methods = {
        "percentile": percentile_thresholds(train[col], direction),
        "robust_z": robust_z_thresholds(train[col], direction),
        "label_driven": label_driven(train, col, direction, tgt),
    }
    results["signals"][col] = {"direction": direction, "eval_target": tgt,
                               "methods": {m: {"thresholds": th, "test": evaluate(test, col, direction, th, tgt)}
                                           for m, th in methods.items()}}

results["emergency_rule"] = ("Any entrapment (outage codes ENT passenger trapped, ENV vandalism entrapment; "
                             "EUF operator-error entrapment as LEVEL_3) -> EMERGENCY immediately; "
                             "MTA counts entrapments monthly, so in this dataset: entrapments > 0 in a month.")
ent_test = test[test.entrapments > 0]
results["emergency_volume_test"] = {"unit_months_with_entrapment_pct": round(len(ent_test) / len(test) * 100, 2),
                                    "entrapment_events_per_month_fleet": round(test.entrapments.sum() / test.period_start.nunique(), 1)}

(OUT / "results.json").write_text(json.dumps(results, indent=2, default=str))
for col, r in results["signals"].items():
    print(f"\n=== {col} ({r['direction']}) -> {r['eval_target']}")
    for m, x in r["methods"].items():
        print(f"  {m}: base {x['test']['base_rate_pct']}%")
        for row in x["test"]["levels"]:
            print("    ", row)
print("\nEMERGENCY:", results["emergency_volume_test"])
