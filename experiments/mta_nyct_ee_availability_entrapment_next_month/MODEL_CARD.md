# Model card — MTA elevator entrapment, next month

Experiment: `mta_nyct_ee_availability_entrapment_next_month`
Reproduce: `.venv/bin/python experiments/mta_nyct_ee_availability_entrapment_next_month/run.py`
(seed 42; writes metrics.json, predictions.parquet, feature_importances.csv,
calibration.html, precision_at_k.html)

## Target & framing
- Decision time: end of month t, after month-t KPIs are published.
- Target: `y = 1` if the unit records >= 1 entrapment in month t+1 (horizon 1 month).
- Scope: MTA-operated subway ELEVATORS (368 units; third-party units excluded —
  not on LiftNet, ~0 recorded outages). Decision rows: unit-months where month t
  is in scope (`hours_total_24h > 0`) AND month t+1 is a consecutive in-scope
  month — the label is always a monitored month.
- Base rate (test, 2023-10 .. 2026-08): 22.9% of unit-months; ~315 elevators/month.

## Data & authenticity
`data/curated/mta_nyct_ee_availability/{aggregates,units}.parquet`, real MTA
NYCT data (audit: `reports/mta_nyct_ee_availability/audit.md`), 2015-01..2026-09.
Leakage scan on the feature table: **no findings** (no single feature > 0.98 AUC,
no post-event columns). Model AUCs are far below the leakage-suspicion range.

## Splits
- Chronological: train decision months t < 2023-09 (1-month gap >= horizon),
  test t in [2023-10, 2026-08] — train 26,531 / test 11,032 unit-months.
- Unit hold-out: 25% of units (91, seed 42) held out entirely; trained on the
  other 277 units in the train period, tested on held-out units in the test
  period — train 20,005 / test 2,770.

## Features (all from months <= t, or known in advance)
- Rolling sums of entrapments / unscheduled / scheduled outages / downtime over
  the past 1, 3, 6, 12 **in-scope** months (out-of-scope months masked to NaN,
  not counted as zeros); rolling mean 24h availability (1/3/6m).
- `ent_lag1`, `ent_flag_lag1`; expanding historical entrapment-month rate over
  in-scope months only (`hist_ent_rate`, min 3) + `hist_n_months` (in-scope
  months observed so far).
- `months_since_major_improvement` (lagged) + missing indicator; `unit_age_months`.
- `gap_lag1` (previous month out of scope), `gap_in_prev12` (any gap in prior
  12 months — used for sensitivity, not a model feature), `target_month`,
  `complex_size`, borough (one-hot).

## Results (chronological test; base rate 22.9%)

| Model | PR-AUC | ROC-AUC | Brier | Prec@5% | Prec@10% | Prec@20% | Recall@20% (months) | Events caught @20% |
|---|---|---|---|---|---|---|---|---|
| Base rate | 0.229 | 0.500 | 0.177 | 23.2% | 26.3% | 24.8% | 21.7% | 22.2% |
| "Entrapment this month" rule | 0.276 | 0.585 | 0.172 | 25.8% | 31.8% | 35.9% | 31.4% | 37.1% |
| Unit historical rate | 0.352 | 0.663 | 0.168 | 45.4% | 42.9% | 38.9% | 34.0% | 38.3% |
| Logistic reg. (4 lags) | 0.376 | 0.637 | 0.167 | 56.1% | 47.4% | 40.2% | 35.1% | 41.6% |
| **HistGradientBoosting** | **0.400** | **0.679** | **0.163** | **55.0%** | **52.1%** | **43.8%** | **38.3%** | **45.5%** |
| HGB, sensitivity: no out-of-scope month in prior 12 (n=10,292) | 0.385 | 0.675 | 0.157 | 53.5% | 50.4% | 42.3% | 39.0% | 45.8% |

"Events caught" = share of next-month entrapment *events* (sum of entrapment
counts) inside flagged units; "recall" = share of entrapment *unit-months*.

Unit hold-out test (91 unseen elevators; base 22.1%): HGB PR-AUC 0.359 / ROC 0.659 /
Brier 0.162, Prec@10% 46.9%, Prec@20% 40.8% — a modest drop vs chronological
(0.400/0.679) and still above every baseline (best baseline: hist rate 0.336 /
logreg 0.347).

### Same-volume comparison vs the existing threshold rules
The outage-count rules (`experiments/thresholds_mta_nyct_ee_availability`) flag
~15.5 units/month (PRELIMINARY union) at 41–52% precision and <=9% recall, and
~3.6/month at WARNING-level thresholds (44–52% precision, ~1–2% recall).
Model top-N per month at the same volumes (chronological test):

| Operating point | Flags/mo | Precision | Recall (months) | Events caught |
|---|---|---|---|---|
| Rules PRELIMINARY union | 15.5 | 41–52% | <=9% | — |
| **Model top-16/mo** | 16.0 | **54.6%** | **12.1%** | **15.2%** |
| Rules WARNING band | ~3.6 | 44–52% | ~1–2% | — |
| **Model top-4/mo** | 4.0 | **57.1%** | **3.2%** | **3.8%** |

At matched alert volume the model is ~3–13 points more precise and catches
~1.5–3x more entrapment months/events.

## Top features (permutation importance on the TEST set, PR-AUC drop)
`ent_sum12` (0.056), `hist_ent_rate` (0.026), `msmi` (0.009), `ent_sum3` (0.008),
`ent_sum6` (0.007), `ent_lag1` (0.005), `avail_mean6`, `sched_sum3`,
`downtime_sum3`. Zero/negative importance: `msmi_missing`, `gap_lag1`,
`ent_flag_lag1`, `borough_Brooklyn`, `borough_Manhattan`, `avail_mean1`,
`sched_sum1`, `downtime_sum1` — engineering-sensible overall: long-run
entrapment history and time since major improvement dominate.

## Alert-level mapping (HGB score; thresholds = TRAIN quantiles, evaluated on test)
Because test-period scores drift downward, a train-quantile threshold flags a
smaller share of the fleet in test — the "top ~X%" label refers to the train
score distribution, not the realised test volume.

| Level | Train quantile | Prob ≥ | Flags/mo in test | % of fleet/mo | Precision | Recall | Events caught |
|---|---|---|---|---|---|---|---|
| PRELIMINARY | 80th | 0.353 | 37.4 | ~11.9% | 50.1% | 26.0% | 32.4% |
| WARNING | 95th | 0.501 | 3.7 | ~1.2% | 56.6% | 2.9% | 3.6% |
| LEVEL_3 | 99th | 0.592 | 0.5 | ~0.2% | 83.3% | 0.6% | 0.9% |

EMERGENCY stays rule-based: any entrapment occurring now triggers it.

Calibration (see calibration.html): roughly calibrated to mildly over-confident
above p≈0.5 — treat probabilities primarily as a ranking score; Brier 0.163 vs
0.177 base-rate baseline.

## Recommended thresholds
- PRELIMINARY at score ≥ 0.353: ~37 flags/month (~12% of fleet), 50% precision,
  catches ~1/3 of next-month entrapment events — the monthly inspection work-list.
- WARNING at score ≥ 0.501: ~4 flags/month, 57% precision — priority inspections.
- LEVEL_3 at score ≥ 0.592: only ~0.5 flags/month but 83% precision (18 flagged
  unit-months, 15 hits) — **kept**, as it now clearly out-precisions WARNING;
  volumes are small so interpret individually rather than as a fleet KPI.
- Alternative framing if stable volumes are preferred: per-month top-N (top 16
  ≈ 55% precision, top 4 ≈ 57%), which auto-adapts to score drift.

## Failure modes / limitations
- Monthly grain: an entrapment early in t+1 may occur before the flag is acted
  on; the score ranks *which* elevators to inspect, not *when* within the month.
- Recall ceiling is low: top ~20% of fleet catches ~38% of entrapment-months /
  ~46% of entrapment events; many entrapments are unpredictable from monthly KPIs.
- Thresholds fit on train quantiles drift under test-period score shifts
  (~20% train quantile → ~12% of test fleet flagged); per-month top-N or
  periodic re-fitting is safer for stable alert budgets.
- Units returning from capital rehab (long out-of-scope runs) have sparse
  feature history; `hist_n_months`/`gap_lag1` partially capture this.
- Permutation importance is computed on the test set (standard caveat: reflects
  what the model uses on this period, not causal drivers).
- Third-party elevators are out of scope entirely — no coverage.

## Changelog (post-audit fixes)
- Decision rows now require month t+1 in scope (previously 79 test rows had an
  unmonitored label month scored as y=0).
- Rolling sums and `hist_ent_rate` now count in-scope months only (out-of-scope
  months masked to NaN instead of zero-filled); added `gap_in_prev12` and a
  no-gap sensitivity eval (PR-AUC 0.385 vs 0.400 full — robust).
- Alert table reworded to train-quantile thresholds with realised test volumes;
  LEVEL_3 kept (83% precision at ~0.5 flags/mo).
- Added same-volume operating points vs the threshold rules.
- Removed dead code; permutation importance noted as test-set, with the
  zero/negative-importance feature list.

## Reproduce
`.venv/bin/python experiments/mta_nyct_ee_availability_entrapment_next_month/run.py`
→ metrics.json, predictions.parquet, feature_importances.csv,
calibration.html, precision_at_k.html, run.log
