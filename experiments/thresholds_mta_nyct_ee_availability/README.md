# Alert thresholds — MTA subway elevators (monthly KPIs)

Reproduce: `.venv/bin/python experiments/thresholds_mta_nyct_ee_availability/run.py` → `results.json`

- Scope: MTA-operated elevators (368 units), unit-months with > 0 counted hours. Third-party units excluded
  (their outage counts are ~0 because they are not on LiftNet).
- Fit: 2015-01 → 2023-09 (26,906 unit-months). Evaluate: 2023-10 → 2026-08 (11,105 unit-months, ~319 elevators
  per month with a next month available).
- Targets evaluated next month: ≥ 1 entrapment (base rate 22.9%), 24 h availability < 90% (base rate 1.7%).

## Comparison on the evaluation period

**Signal: 3-month unscheduled outages → entrapment next month** (base 22.7%)

| Method | Level | Threshold | Flagged unit-months | Alerts / month (fleet) | Precision | Lift | Recall |
|---|---|---|---|---|---|---|---|
| percentile | PRELIMINARY | ≥ 17 | 4.9% | 15.3 | 41.2% | 1.81 | 8.9% |
| percentile | WARNING | ≥ 29 | 0.6% | 1.9 | 47.1% | 2.07 | 1.3% |
| percentile | LEVEL_3 | ≥ 49 | 0.08% | 0.3 | 88.9% | 3.91 | 0.3% |
| robust z | PRELIMINARY | ≥ 17.3 | 4.1% | 13.0 | 41.2% | 1.81 | 7.5% |
| robust z | WARNING | ≥ 24.0 | 1.1% | 3.6 | 44.8% | 1.97 | 2.2% |
| robust z | LEVEL_3 | ≥ 30.7 | 0.5% | 1.4 | 52.0% | 2.29 | 1.0% |

Single-month unscheduled outages perform slightly worse (precision 37.6–44.8% at the same alert volumes).
Label-driven thresholds collapse to the median (precision targets ≥ 45% are not reachable with enough
support), which itself shows that outage counts alone are a weak entrapment predictor.

**Signal: 24 h availability this month → availability < 90% next month** (base 1.7%)

| Method | Level | Threshold | Flagged | Alerts / month | Precision | Lift | Recall |
|---|---|---|---|---|---|---|---|
| robust z | PRELIMINARY | < 93.7% | 4.0% | 12.8 | 11.4% | 6.5 | 26.4% |
| percentile | WARNING | < 88.7% | 1.4% | 4.4 | 22.2% | 12.8 | 17.6% |
| percentile | LEVEL_3 | < 71.7% | 0.2% | 0.7 | 69.2% | 39.8 | 9.3% |

## Recommendation (MTA elevator fleet, monthly review)

| Level | Rule | Expected volume |
|---|---|---|
| PRELIMINARY | 24 h availability < 93.7% **or** 3-month unscheduled outages ≥ 17.3 | 15.5 units / month |
| WARNING | 24 h availability < 88.7% **or** 3-month unscheduled outages ≥ 24.0 | 5.3 units / month |
| LEVEL_3 | 24 h availability < 71.7% **or** 3-month unscheduled outages ≥ 30.7 | 2.3 units / month |

(Measured on the evaluation period with the combined rule, highest level wins: 23.2 of ~319 elevators flagged
per month, 7.3%.)
| EMERGENCY | any entrapment (codes ENT / ENV) — real-time rule, not a monthly threshold | ~107 entrapments / month fleet-wide (23% of unit-months) |

Thresholds live in `thresholds.json`.

## Caveats
- Monthly aggregates only: these are **chronic-problem flags for maintenance planning**, not real-time alarms.
- Outage-count thresholds have low recall (≤ 9%): most next-month entrapments happen on units that did not look
  unusual the month before. A multi-feature model (`/model-experiment`) is the next step to improve this.
- Availability persistence is strong (a unit far below 90% tends to stay there), partly because long repairs
  span month boundaries — LEVEL_3 availability alerts mostly identify ongoing long-term repairs.
