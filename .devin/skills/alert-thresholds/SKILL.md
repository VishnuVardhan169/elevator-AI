---
name: alert-thresholds
description: Derive data-driven alert thresholds (PRELIMINARY / WARNING / LEVEL_3 / EMERGENCY) for elevator sensors, KPIs or model scores, and estimate the resulting alert volume and how many historical failures each level would have caught.
argument-hint: "<dataset_id> <signal or score columns>"
agent: data-scientist
---

Derive alert thresholds for the signals in the user's request.

1. Use only a training period (chronologically first ~75%) to fit thresholds; evaluate on the rest.
2. For each signal compute candidate thresholds with three methods and compare:
   - percentiles: `analytics.validation.percentile_thresholds` (p95 / p99 / p99.9), direction-aware
   - robust z: `analytics.validation.robust_z_thresholds` (median + 3 / 4.5 / 6 MAD)
   - label-driven (if failure labels exist): the value at which precision of "failure within horizon" reaches
     e.g. 30% / 50% / 80%
   Consider per-unit or per-model baselines when units differ systematically (check variance between units).
3. Apply smoothing/persistence (rolling mean or "k of n readings") to avoid flapping, and merge consecutive
   breaches into episodes like `elevator_ai/alerts.py` does.
4. On the evaluation period report per level: alerts per unit per month, share of failures preceded by an alert
   within the horizon, median lead time, precision.
5. EMERGENCY is rule-based (entrapment, controller program malfunction, safety-circuit trips) — list which
   codes/events in this dataset should map to it.
6. Save `experiments/thresholds_<id>/thresholds.json` (values + method + direction) and a `README.md` with the
   comparison table and your recommendation. Return the recommended thresholds and expected alert volume.
