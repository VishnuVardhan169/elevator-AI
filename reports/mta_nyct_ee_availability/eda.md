# EDA: MTA NYCT subway elevators & escalators (2015-01 → 2026-09)

**Real data** (MTA official open data, audit: approved with caveats — [audit.md](audit.md)).
Code: `scripts/analysis/mta_nyct_ee_availability/eda.py` · numbers: [eda_results.json](eda_results.json) ·
charts: `eda_*.html` in this folder.

## Summary
1. **Elevators are far more reliable than escalators**: MTA elevators run 97.0% 24 h availability with
   1.81 unscheduled outages per unit-month; MTA escalators 93.8% and 6.63 (3.7× more breakdowns).
2. **Entrapments are frequent**: 35.5 per 100 elevator-months — 23.7% of MTA elevator-months have at least one
   (≈ 107 entrapments per month across the fleet in 2023-26).
3. **Problems concentrate in a minority of units**: the worst 10% of MTA elevators produce 26.4% of
   unscheduled outages and 29.8% of entrapments; the top 20% produce 44.3% of outages.
4. **History predicts the future**: an elevator with an entrapment this month has a 40.0% chance of another
   next month vs 18.6% otherwise (2.1×); units in the top outage quintile have 36.4% vs 17.1% in the lowest.
5. **Older installations break more**: 20+ years since last major improvement → 2.13 unscheduled outages and
   43.9 entrapments per 100 unit-months vs 1.44 and 28.2 for 0-2 years (+47% / +56%); availability 96.3% vs 98.2%.
6. **Fleet is improving**: elevator availability rose from 96.0-96.6% (2015-19) to 97.7-98.2% (2023-25);
   entrapments fell from a 2017-18 peak of ~51 to ~30-31 per 100 elevator-months since 2020.

## Data used
- `data/curated/mta_nyct_ee_availability/aggregates.parquet` (83,776 unit-months) + `units.parquet` (701 units).
- Availability is hours-weighted (Σ hours available / Σ counted hours); unit-months with 0 counted hours excluded.
- **Outage and entrapment analyses use MTA-operated units only** (368 elevators, 234 escalators). The 99
  third-party units report essentially no outages (0.0022 unscheduled per elevator-month), consistent with MTA's
  note that they are not on LiftNet — their counts are unusable, though their availability is reported.

## Findings

### 1. Fleet overview
| Segment | Unit-months | 24 h avail. | AM peak | PM peak | Unscheduled / unit-month | Scheduled / unit-month | Entrapments / 100 unit-months |
|---|---|---|---|---|---|---|---|
| Elevator — MTA | 39,744 | 97.02% | 97.73% | 97.58% | 1.81 | 1.95 | 35.5 |
| Elevator — third party | 6,236 | 92.67% | 92.59% | 92.71% | (0.002, not recorded) | (0.001) | (0.13) |
| Escalator — MTA | 31,383 | 93.79% | 95.12% | 93.89% | 6.63 | 3.30 | — |
| Escalator — third party | 6,413 | 88.58% | 88.32% | 88.67% | (0.0) | (0.0) | — |

- Third-party units have **4-5 pp lower availability** than MTA units of the same type.
- Peak availability is slightly higher than 24 h (elevators +0.7 pp AM, +0.6 pp PM), suggesting planned work is
  pushed off-peak. Escalators: +1.3 pp AM but only +0.1 pp PM.
- Charts: `eda_coverage.html` (units reported per month: 485 → 697 as new units were commissioned).

### 2. Trends 2015-2026 (MTA units) — `eda_trend_*.html`
| Year | Elevator avail. | Elevator unscheduled / unit-month | Entrapments / 100 elevator-months | Escalator avail. | Escalator unscheduled |
|---|---|---|---|---|---|
| 2015 | 96.56% | 1.89 | 33.8 | 94.41% | 6.18 |
| 2017 | 96.05% | 2.33 | **51.9** | 94.68% | 5.62 |
| 2019 | 96.34% | 2.02 | 45.1 | **89.38%** | **9.93** |
| 2020 | 96.91% | 1.42 | 28.6 | 92.89% | 5.56 |
| 2023 | 97.71% | 1.60 | 31.4 | 95.41% | 6.93 |
| 2025 | **98.17%** | 1.72 | 30.7 | **96.12%** | 6.05 |
| 2026 (Jan-Sep) | 97.67% | 1.78 | 34.6 | 96.33% | 5.15 |

- Elevator unscheduled outages trend down over the years but not significantly (Spearman ρ = -0.54, p = 0.07,
  12 yearly points). The 2020-21 drop coincides with the pandemic ridership collapse — usage matters.
- 2019 was an escalator outlier year (89.4% availability, 9.9 unscheduled outages per unit-month).
- 2026 shows a small uptick in elevator entrapments (34.6) — worth watching.

### 3. Seasonality (MTA elevators) — `eda_seasonality.html`
- Unscheduled outages differ by calendar month (Kruskal-Wallis p = 7.6e-16): highest in **January (2.10)** and
  December (1.94), lowest in April (1.63) — about +29% in winter vs spring. Entrapments follow the same pattern
  (0.42 per unit-month in January vs 0.32 in April). Availability is lowest in Jan/Feb/Aug (96.75-96.73%).
- Interpretation (not proven by this data): cold, wet weather and holiday crowds; summer heat in August.

### 4. Unit heterogeneity — `eda_unit_distribution.html`, `eda_unit_scatter.html`
| | Elevators (368) | Escalators (234) |
|---|---|---|
| Unscheduled / month per unit: p10 / median / p90 | 0.74 / 1.51 / 3.22 | 3.25 / 6.22 / 11.02 |
| Availability per unit: p10 / median / p90 | 95.3% / 97.6% / 99.1% | 90.0% / 94.6% / 96.7% |
| Share of unscheduled outages from worst 10% / 20% of units | 26.4% / 44.3% | 20.8% / 35.7% |
| Share of entrapments from worst 10% of units | 29.8% | — |
| Units with zero entrapments over their history | 7 | — |

Worst MTA elevators (≥ 24 months of data), unscheduled outages per month: EL710 Manhattan 5.33 · EL601 Manhattan
5.18 · EL108 Manhattan 4.98 (9.9 entrapments/yr) · EL509 Bronx 4.88 · EL113 Manhattan 4.79 · EL405 Queens 4.77
(10.2 entrapments/yr) · EL117 · EL109 · EL281 · EL277 Manhattan (12.4 entrapments/yr). Full list in the JSON.
8 of the top 10 are in Manhattan.

### 5. Drivers (MTA elevators)
**Years since last major improvement** — `eda_age_bands.html` (39,583 unit-months with age known)

| Band | Unit-months | Avail. | Unscheduled / unit-month | Entrapments / 100 | % months with entrapment |
|---|---|---|---|---|---|
| 0-2 y | 3,179 | 98.21% | 1.44 | 28.2 | 20.0% |
| 2-5 y | 3,902 | 97.76% | 1.67 | 23.5 | 17.9% |
| 5-10 y | 6,446 | 97.25% | 1.82 | 27.5 | 20.1% |
| 10-20 y | 14,518 | 96.97% | 1.67 | 37.1 | 24.9% |
| 20 y+ | 11,538 | 96.30% | 2.13 | 43.9 | 27.1% |

Availability falls steadily with age; entrapments rise sharply after 10 years. The month-level correlation is
weak (Spearman ρ = 0.055, p < 1e-27) — age shifts the average but explains little of the month-to-month
variation. Possible confounder: older units are concentrated in busier Manhattan stations.

**Borough** (χ² on entrapment months p = 5e-14)

| Borough | Unit-months | Avail. | Unscheduled | Entrapments / 100 |
|---|---|---|---|---|
| Bronx | 5,321 | 96.74% | 1.77 | **40.2** |
| Manhattan | 19,463 | 96.77% | **2.01** | 37.2 |
| Brooklyn | 9,592 | 97.36% | 1.50 | 32.2 |
| Queens | 5,368 | 97.59% | 1.66 | 30.6 |

### 6. Downtime
| | Monthly downtime h — p50 / p90 / p99 | Unit-months fully down | Unit-months < 90% available |
|---|---|---|---|
| MTA elevators | 11.2 / 44.9 / 179.6 | 19 | 1,855 (4.8%) |
| MTA escalators | 24.6 / 88.1 / 412.1 | 107 | 3,994 (13.2%) |

Downtime is heavy-tailed: the typical elevator loses ~11 h a month, but 1% of unit-months lose more than a week.

### 7. Safety & predictability (MTA elevators) — `eda_entrapment_lift.html`
| Condition this month | P(entrapment next month) |
|---|---|
| Any unit (base rate) | 23.7% |
| No entrapment this month | 18.6% |
| ≥ 1 entrapment this month | **40.0%** |
| ≥ 2 entrapments in the last 3 months | 40.9% |
| Lowest unscheduled-outage quintile | 17.1% |
| Highest unscheduled-outage quintile | **36.4%** |

- Same-month correlation between unscheduled outages and entrapments: r = 0.49; month-to-month autocorrelation
  of unscheduled outages: r = 0.44. Unit history carries real signal for next-month risk.
- Alert thresholds derived from this: [experiments/thresholds_mta_nyct_ee_availability/README.md](../../experiments/thresholds_mta_nyct_ee_availability/README.md).

## Data quality issues and handling
| Issue | Handling |
|---|---|
| Third-party units record ~0 outages | Excluded from outage/entrapment analysis; availability reported separately |
| 2,573 unit-months with 0 counted hours (capital rehab / out of scope) | Excluded from availability |
| 3,493 partial months | Hours-weighted availability |
| Age (months since improvement) missing 15.4% | Age analysis on 39,583 unit-months with values |
| Monthly granularity | No event timing/cause analysis possible |

## Open questions / next steps
1. **Modelling**: next-month entrapment risk per elevator using history (entrapments, outages, availability
   lags), age, borough and season — the persistence numbers above suggest a model can beat the 23.7% base rate
   comfortably (`/model-experiment mta_nyct_ee_availability "entrapment next month"`).
2. **Usage**: join station ridership (MTA open data) to test whether traffic explains the Manhattan / winter /
   2020 effects.
3. **Causes**: the live MTA outage feed (api.mta.info) has per-outage reasons — collecting it going forward
   would enable cause-level analysis that monthly data cannot provide.
4. Ask MTA why third-party outage counts are empty while their availability is lower.
