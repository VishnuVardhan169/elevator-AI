"""
FRAMING
-------
Decision time : end of month t (all of month t's KPIs are published).
Target        : y = 1 if the unit records >= 1 entrapment in month t+1.
Horizon       : 1 calendar month ahead.
Scope         : MTA-operated subway ELEVATORS only (third-party units are not on
                LiftNet and report ~0 outages -> excluded). Decision rows are
                unit-months with hours_total_24h > 0 (in scope, monitored).
Available at decision time: all monthly aggregates for months <= t, static unit
attributes (borough, station complex, first month), and the calendar month of
t+1 (known in advance). Months where the unit was out of scope
(hours_total_24h == 0) are masked to NaN so rolling windows and the expanding
historical rate count only monitored months; `gap_lag1` and `gap_in_prev12`
indicators are kept as features. Decision rows additionally require month t+1
to be in scope so the label is a monitored month.

Splits
------
Chronological: train decision months t < 2023-09 (1-month gap before the test
cutoff 2023-10, >= label horizon of 1 month). Test: t in [2023-10, 2026-08].
Unit hold-out: 25% of the 368 units held out (seed 42); model trained on the
remaining units in the train period and evaluated on held-out units in the test
period -> measures generalisation to unseen elevators.

Baselines: (a) base rate, (b) "entrapment this month" rule scored by its
conditional probability, (c) unit's expanding historical entrapment rate,
(d) logistic regression on a few lags. Model: HistGradientBoostingClassifier.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss,
                             roc_auc_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from analytics.validation import leakage_scan  # noqa: E402

SEED = 42
rng = np.random.RandomState(SEED)
OUT = Path(__file__).resolve().parent

# ------------------------------------------------------------------ load ----
agg = pd.read_parquet("data/curated/mta_nyct_ee_availability/aggregates.parquet")
units = pd.read_parquet("data/curated/mta_nyct_ee_availability/units.parquet")
df = agg.merge(units[["unit_id", "unit_type", "operator", "borough",
                      "station_complex_id", "first_month", "last_month"]],
               on="unit_id", how="left")
df = df[(df.unit_type == "elevator") & (df.operator == "MTA")].copy()
df["period_start"] = pd.to_datetime(df["period_start"])
df = df.sort_values(["unit_id", "period_start"]).reset_index(drop=True)

# ---- regular monthly grid per unit (keeps gap months explicit) --------------
frames = []
for uid, g in df.groupby("unit_id"):
    g = g.set_index("period_start").asfreq("MS")
    g["unit_id"] = uid
    frames.append(g.reset_index())
grid = pd.concat(frames, ignore_index=True)
meta = df[["unit_id", "borough", "station_complex_id", "first_month",
           "last_month"]].drop_duplicates("unit_id").set_index("unit_id")
for c in meta.columns:
    grid[c] = grid.unit_id.map(meta[c])
grid["in_scope"] = grid["hours_total_24h"].fillna(0) > 0

count_cols = ["outages_total", "outages_scheduled", "outages_unscheduled",
              "entrapments", "downtime_24h_h"]
# Out-of-scope months (hours_total_24h == 0 / absent) are NOT zero-count months:
# mask them to NaN so rolling windows and expanding stats skip them instead of
# diluting the signal.
grid[count_cols] = grid[count_cols].where(grid["in_scope"])

# ---------------------------------------------------------------- features --
g = grid.groupby("unit_id", group_keys=False)


def lag_sum(col, w):
    # sum over the last w calendar months, counting only in-scope months
    return g[col].apply(lambda s: s.shift(1).rolling(w, min_periods=1).sum())


def lag_mean(col, w):
    return g[col].apply(lambda s: s.shift(1).rolling(w, min_periods=1).mean())


grid["ent_lag1"] = g["entrapments"].shift(1)
grid["ent_flag_lag1"] = (grid["ent_lag1"] > 0).astype(float)
for w in (1, 3, 6, 12):
    grid[f"ent_sum{w}"] = lag_sum("entrapments", w)
    grid[f"unsched_sum{w}"] = lag_sum("outages_unscheduled", w)
    grid[f"sched_sum{w}"] = lag_sum("outages_scheduled", w)
    grid[f"downtime_sum{w}"] = lag_sum("downtime_24h_h", w)
    grid[f"avail_mean{w}"] = lag_mean("availability_24h_pct", w)

# expanding historical entrapment-month rate over IN-SCOPE months only
grid["hist_ent_rate"] = g.apply(
    lambda s: (s["entrapments"] > 0).where(s["in_scope"])
    .shift(1).expanding(min_periods=3).mean())
# number of in-scope months observed so far (denominator of hist_ent_rate)
grid["hist_n_months"] = g["in_scope"].apply(
    lambda s: s.shift(1).expanding(min_periods=0).sum())
grid["gap_lag1"] = (~g["in_scope"].shift(1).fillna(False)).astype(float)
# any out-of-scope month inside the previous 12 (sensitivity flag)
grid["gap_in_prev12"] = g["in_scope"].apply(
    lambda s: (~s).shift(1).rolling(12, min_periods=1).max()).fillna(0.0)
grid["msmi"] = g["months_since_major_improvement"].shift(1)
grid["msmi_missing"] = grid["msmi"].isna().astype(float)
grid["unit_age_months"] = (
    (grid["period_start"].dt.to_period("M")
     - pd.to_datetime(grid["first_month"]).dt.to_period("M")).apply(
        lambda p: p.n if pd.notna(p) else np.nan))
grid["target_month"] = (grid["period_start"] + pd.offsets.MonthBegin(1)).dt.month
complex_size = (units[(units.unit_type == "elevator") & (units.operator == "MTA")]
                .groupby("station_complex_id").size())
grid["complex_size"] = grid.station_complex_id.map(complex_size)

# target: entrapments in t+1, requiring the t+1 row to exist, be consecutive,
# AND be in scope (a monitored month with hours_total_24h > 0)
grid["next_period"] = g["period_start"].shift(-1)
grid["next_ent"] = g["entrapments"].shift(-1)
grid["next_in_scope"] = g["in_scope"].shift(-1)
consec = grid["next_period"] == grid["period_start"] + pd.offsets.MonthBegin(1)

# decision rows: in-scope month t with a consecutive in-scope month t+1
dec = grid[grid["in_scope"] & consec & grid["next_in_scope"].fillna(False)
           & grid["next_ent"].notna()].copy()
dec["y"] = (dec["next_ent"] >= 1).astype(int)
dec["y_events"] = dec["next_ent"]

NUM_FEATS = ["ent_lag1", "ent_flag_lag1",
             "ent_sum3", "ent_sum6", "ent_sum12",
             "unsched_sum1", "unsched_sum3", "unsched_sum6", "unsched_sum12",
             "sched_sum1", "sched_sum3", "downtime_sum1", "downtime_sum3",
             "avail_mean1", "avail_mean3", "avail_mean6",
             "hist_ent_rate", "hist_n_months", "gap_lag1",
             "msmi", "msmi_missing", "unit_age_months", "target_month",
             "complex_size"]
CAT_FEATS = ["borough"]
FEATS = NUM_FEATS + CAT_FEATS

# leakage scan
scan = leakage_scan(dec[["unit_id", "period_start"] + FEATS + ["y"]].assign(
    borough=pd.factorize(dec["borough"])[0]), target="y",
    time_col="period_start", group_col="unit_id")
print("leakage scan:", scan)

# ------------------------------------------------------------------ splits --
CUTOFF = pd.Timestamp("2023-10-01")
GAP = pd.Timestamp("2023-09-01")  # 1-month gap >= horizon
train = dec[dec.period_start < GAP]
test = dec[dec.period_start >= CUTOFF]

units_all = np.array(sorted(dec.unit_id.unique()))
held_out = set(rng.choice(units_all, size=int(0.25 * len(units_all)),
                          replace=False))
train_ho = train[~train.unit_id.isin(held_out)]
test_ho = test[test.unit_id.isin(held_out)]
print(f"chrono: train {len(train)} test {len(test)} | "
      f"unit-holdout: train {len(train_ho)} test {len(test_ho)} "
      f"({len(held_out)} units)")

Xtr = pd.get_dummies(train[FEATS], columns=CAT_FEATS)
Xte = pd.get_dummies(test[FEATS], columns=CAT_FEATS).reindex(
    columns=Xtr.columns, fill_value=0)
Xtr_ho = pd.get_dummies(train_ho[FEATS], columns=CAT_FEATS)
Xte_ho = pd.get_dummies(test_ho[FEATS], columns=CAT_FEATS).reindex(
    columns=Xtr_ho.columns, fill_value=0)


def evaluate(y, y_events, p, months):
    y = np.asarray(y); p = np.asarray(p)
    out = {"n": len(y), "months": int(months),
           "base_rate": float(y.mean()),
           "pr_auc": float(average_precision_score(y, p)),
           "roc_auc": float(roc_auc_score(y, p)),
           "brier": float(brier_score_loss(y, p))}
    order = np.argsort(-p)
    total_ev = y_events.sum()
    for k in (0.05, 0.10, 0.20):
        top = order[: max(1, int(k * len(y)))]
        prec = y[top].mean()
        out[f"prec_at_{int(k*100)}pct"] = float(prec)
        out[f"lift_at_{int(k*100)}pct"] = float(prec / y.mean())
        out[f"recall_at_{int(k*100)}pct"] = float(y[top].sum() / y.sum())
        out[f"events_caught_{int(k*100)}pct"] = float(
            y_events.iloc[top].sum() / total_ev)
    return out


results = {"leakage_scan": scan, "chrono": {}, "unit_holdout": {},
           "features": FEATS, "held_out_units": sorted(held_out)}

for name, tr, te, xa, xb in (("chrono", train, test, Xtr, Xte),
                             ("unit_holdout", train_ho, test_ho, Xtr_ho, Xte_ho)):
    ytr, yte = tr.y.values, te.y.values
    months = te.period_start.nunique()
    base = evaluate(yte, te.y_events, np.full(len(te), ytr.mean()), months)
    # baseline b: P(next | ent this month) as score
    p_flag = tr.loc[tr.ent_flag_lag1 == 1, "y"].mean()
    p_noflag = tr.loc[tr.ent_flag_lag1 == 0, "y"].mean()
    score_b = np.where(te.ent_flag_lag1 == 1, p_flag, p_noflag)
    bl_b = evaluate(yte, te.y_events, score_b, months)
    # baseline c: unit historical rate
    bl_c = evaluate(yte, te.y_events, te.hist_ent_rate.fillna(ytr.mean()), months)
    # baseline d: logistic on lags
    lr_feats = ["ent_lag1", "ent_sum3", "unsched_sum3", "avail_mean3"]
    lr = Pipeline([("imp", SimpleImputer(strategy="median")),
                   ("sc", StandardScaler()),
                   ("clf", LogisticRegression(max_iter=2000,
                                              random_state=SEED))])
    lr.fit(tr[lr_feats], ytr)
    bl_d = evaluate(yte, te.y_events, lr.predict_proba(te[lr_feats])[:, 1], months)
    # model
    hgb = HistGradientBoostingClassifier(
        max_iter=400, learning_rate=0.05, max_depth=None,
        min_samples_leaf=50, l2_regularization=1.0, random_state=SEED)
    hgb.fit(xa.fillna(xa.median()), ytr)
    p_hgb = hgb.predict_proba(xb.fillna(xa.median()))[:, 1]
    mdl = evaluate(yte, te.y_events, p_hgb, months)

    results[name] = {"baseline_base_rate": base,
                     "baseline_ent_this_month": bl_b,
                     "baseline_unit_hist_rate": bl_c,
                     "baseline_logreg_lags": bl_d,
                     "hgb": mdl}
    if name == "chrono":
        pred = te[["unit_id", "period_start", "y", "y_events"]].copy()
        pred["p_hgb"] = p_hgb
        pred["p_logreg"] = lr.predict_proba(te[lr_feats])[:, 1]
        pred["p_hist_rate"] = te.hist_ent_rate.values
        hgb_model, train_med = hgb, xa.median()
        train_p = hgb.predict_proba(xa.fillna(train_med))[:, 1]
        results["_train_p"] = train_p  # temp
        results["_train_y"] = ytr
        # sensitivity: only test rows with NO out-of-scope month in prior 12
        clean = te.gap_in_prev12 == 0
        results["chrono"]["hgb_no_gap_prev12"] = evaluate(
            yte[clean.values], te.y_events[clean.values],
            p_hgb[clean.values], months)

# ------------------------------------------------- thresholds & alert levels
train_p = results.pop("_train_p"); train_y = results.pop("_train_y")
qs = {"PRELIMINARY": 0.80, "WARNING": 0.95, "LEVEL_3": 0.99}  # top 20/5/1%
thr = {lvl: float(np.quantile(train_p, q)) for lvl, q in qs.items()}
alert_tbl = {}
te = test.assign(p=pred["p_hgb"].values)
for lvl, t in thr.items():
    flagged = te[te.p >= t]
    alert_tbl[lvl] = {
        "prob_threshold": t,
        "flagged_unit_months": int(len(flagged)),
        "alerts_per_month": float(len(flagged) / te.period_start.nunique()),
        "precision": float(flagged.y.mean()),
        "recall": float(flagged.y.sum() / te.y.sum()),
        "events_caught": float(flagged.y_events.sum() / te.y_events.sum()),
        "lift": float(flagged.y.mean() / te.y.mean()),
    }
results["alert_levels"] = alert_tbl
units_per_month = te.groupby("period_start").unit_id.nunique().mean()
for lvl in alert_tbl:
    alert_tbl[lvl]["pct_of_fleet_per_month"] = float(
        alert_tbl[lvl]["alerts_per_month"] / units_per_month)
    alert_tbl[lvl]["train_quantile"] = qs[lvl]
alert_tbl["_note"] = (
    "Thresholds are score quantiles fit on TRAIN; the flagged share in test "
    "differs because the test-period score distribution drifts.")

# same-volume operating points vs the threshold rules
# (rules: PRELIMINARY union ~15.5 flags/month, WARNING band ~3.6 flags/month)
def top_n_per_month(te_df, n):
    idx = (te_df.groupby("period_start")["p"]
           .nlargest(n).index.get_level_values(1))
    return te_df.loc[idx]

same_vol = {}
for label, n in (("match_rules_preliminary_union_~15.5_per_month", 16),
                 ("match_rules_warning_~3.6_per_month", 4)):
    fl = top_n_per_month(te, n)
    same_vol[label] = {
        "flags_per_month": float(len(fl) / te.period_start.nunique()),
        "precision": float(fl.y.mean()),
        "recall_months": float(fl.y.sum() / te.y.sum()),
        "events_caught": float(fl.y_events.sum() / te.y_events.sum()),
        "lift": float(fl.y.mean() / te.y.mean()),
    }
same_vol["_rules_reference"] = {
    "preliminary_union": {"alerts_per_month": 15.5, "precision": "~41-52%",
                          "recall": "<=9%"},
    "warning": {"alerts_per_month": 3.6, "precision": "~44-52%",
                "recall": "~1-2%"},
}
results["same_volume_vs_threshold_rules"] = same_vol

# ------------------------------------------------------------ persist ------
pred.to_parquet(OUT / "predictions.parquet", index=False)

# permutation importance (test set, PR-AUC drop)
from sklearn.inspection import permutation_importance  # noqa: E402
imp = permutation_importance(hgb_model, Xte.fillna(train_med), test.y.values,
                             scoring="average_precision", n_repeats=10,
                             random_state=SEED)
imp_df = (pd.DataFrame({"feature": Xte.columns,
                        "importance": imp.importances_mean})
          .sort_values("importance", ascending=False))
imp_df.to_csv(OUT / "feature_importances.csv", index=False)
results["perm_importance_note"] = (
    "Permutation importance computed on the CHRONOLOGICAL TEST set "
    "(average-precision drop, 10 repeats, seed 42).")
results["perm_importance_zero_or_negative"] = (
    imp_df.loc[imp_df.importance <= 0, "feature"].tolist())
print(imp_df.head(12).to_string(index=False))

import plotly.graph_objects as go  # noqa: E402
from sklearn.calibration import calibration_curve  # noqa: E402
fig = go.Figure()
frac, meanp = calibration_curve(test.y.values, pred.p_hgb, n_bins=10,
                                strategy="quantile")
fig.add_trace(go.Scatter(x=meanp, y=frac, mode="lines+markers",
                         name="HGB (test)"))
fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines",
                         line=dict(dash="dash"), name="perfect"))
fig.update_layout(title="Calibration — entrapment next month (chrono test)",
                  xaxis_title="predicted probability",
                  yaxis_title="observed frequency")
fig.write_html(OUT / "calibration.html")

ks = np.linspace(0.01, 0.5, 50)
order = np.argsort(-pred.p_hgb.values)
precs = [test.y.values[order[:max(1, int(k*len(order)))]].mean() for k in ks]
fig2 = go.Figure(go.Scatter(x=ks*100, y=precs, mode="lines"))
fig2.add_hline(y=test.y.mean(), line_dash="dash",
               annotation_text="base rate")
fig2.update_layout(title="Precision at top-k% of fleet (chrono test)",
                   xaxis_title="top % of unit-months flagged",
                   yaxis_title="precision")
fig2.write_html(OUT / "precision_at_k.html")

with open(OUT / "metrics.json", "w") as f:
    json.dump(results, f, indent=2, default=float)
print(json.dumps({k: v for k, v in results.items()
                  if k in ("chrono", "unit_holdout", "alert_levels")},
                 indent=2, default=float))
