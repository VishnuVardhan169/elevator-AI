---
name: reliability-kpis
description: Compute elevator reliability KPIs - MTBF, MTTR, availability, failures per unit-year, Weibull shape/scale and B10 life - for the fleet and by component, model, age band and site, and write reports/<dataset_id>/reliability.md.
argument-hint: "<dataset_id> [group-by columns]"
agent: data-analyst
---

Compute reliability KPIs for the dataset in the user's request.

1. Build an events/outages table with columns unit_id, start, end (or duration_h), component — from
   `data/curated/<id>/outages.parquet` or `events.parquet` if curated, otherwise derive it in
   `scripts/analysis/<id>/reliability.py`. State the failure definition you used (e.g. unscheduled outages only).
2. Know the true fleet size and observation window (units with zero failures count!). Pass `--n-units`.
3. Run `.venv/bin/python -m analytics.reliability <events.parquet> --unit unit_id --start start --end end
   --component component --n-units N --out reports/<id>/reliability_fleet.md`, then use
   `analytics.reliability.by_group` for the group-bys requested (default: component, model, age band, site).
4. If the data is pre-aggregated (e.g. monthly availability per unit, like the MTA dataset), compute KPIs from
   the aggregates instead: availability = sum(hours_available) / sum(total_hours), outages per unit-month, etc.
5. Interpret: Weibull beta < 1 (infant mortality — check installation/repair quality), ~1 (random — condition
   monitoring helps), > 1 (wear-out — time-based replacement helps). Compare groups with confidence intervals
   (Poisson CI for failure rates).
6. Write `reports/<id>/reliability.md` with a KPI table, the group comparisons, the worst units, and
   maintenance implications. Return the path and headline KPIs.
