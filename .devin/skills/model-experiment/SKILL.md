---
name: model-experiment
description: Run a rigorous predictive-modelling experiment on elevator data (failure/outage prediction, remaining useful life, anomaly detection, fault classification) with baselines, chronological and unit hold-out validation, leakage checks and a model card.
argument-hint: "<dataset_id> <prediction goal, e.g. 'unscheduled outage next month'>"
agent: data-scientist
---

Run a modelling experiment for the dataset and goal in the user's request. Follow your modelling protocol
exactly (frame -> audit -> baselines -> splits -> features -> metrics -> thresholds -> sanity checks).

1. Name the experiment `<id>_<short_goal>` and work in `experiments/<name>/`.
2. Write the framing (target, horizon, decision time, available information) at the top of `run.py` as a
   docstring before writing any modelling code.
3. Start simple: baselines, then logistic regression / gradient boosting (`HistGradientBoostingClassifier` or
   `Regressor`). For unlabelled sensor data use IsolationForest / robust z-scores and validate on any known
   fault periods.
4. Evaluate with a chronological split (gap >= horizon) AND a unit hold-out. Report both.
5. Save `metrics.json`, `predictions.parquet`, feature importances, and plots (`*.html`).
6. Write `MODEL_CARD.md`. Return its path, the model-vs-baseline table, and the recommended alert thresholds.
