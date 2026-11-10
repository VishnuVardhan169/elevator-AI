---
name: eda-report
description: Full exploratory data analysis of elevator data answering maintenance questions - failure/outage patterns by component, age, model, site, time of day/week/season, usage and load, entrapments - with plotly charts and a written report.
argument-hint: "<dataset_id> [specific questions]"
agent: data-analyst
---

Run an exploratory analysis of the dataset (and any specific questions) in the user's request.

1. Read `data/catalog.yaml` for the dataset's authenticity and canonical tables. Prefer `data/curated/<id>/`
   if present, else `data/raw/<id>/`. Put a synthetic/unknown warning at the top of the report if applicable.
2. Write the analysis as `scripts/analysis/<id>/eda.py` (re-runnable) and save charts to
   `reports/<id>/eda_*.html`.
3. Cover whatever the data supports from this list, skipping what it cannot answer (say so):
   - **Volume & coverage**: units, time window, events per unit, missing periods.
   - **Failure / outage profile**: counts and rates by component, code, reason; Pareto (top 20% of causes).
   - **Unit heterogeneity**: distribution of failures per unit; worst 10 units; repeat failures within 30 days.
   - **Time patterns**: hour-of-day, day-of-week, month/season, trend over years.
   - **Drivers**: age, model/manufacturer, drive type, site type, traffic/usage, load %, overloads.
   - **Downtime**: duration distribution (median, p90), scheduled vs unscheduled, longest outages.
   - **Safety**: entrapments and emergency events, separately, with rates.
   - **Sensor behaviour** (telemetry): distributions, drift over time, behaviour in the window before failures.
4. For every relationship you claim, give the effect size and sample size; use a simple test (chi-square,
   Mann-Whitney, Spearman) where it helps, and note confounders (e.g. age vs model).
5. Write `reports/<id>/eda.md` in the report format from your instructions. Return the path and key findings.
