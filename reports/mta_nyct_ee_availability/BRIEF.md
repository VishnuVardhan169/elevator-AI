# Brief: MTA NYCT subway elevator & escalator availability

**Data**: real, official MTA New York City Transit open data (data.ny.gov rc78-7x78), NY Open Data licence with no
use limitations. 83,776 unit-months, 701 units (419 elevators, 282 escalators), Jan 2015 → Sep 2026, monthly.
Audit: approved with caveats — monthly aggregates only; third-party units (99) have no usable outage counts.

## Key findings (MTA-operated units)
1. Elevators: **97.0%** availability, **1.81** unscheduled outages per unit-month. Escalators: 93.8% and 6.63.
2. **35.5 entrapments per 100 elevator-months** (≈ 107 per month fleet-wide recently); 23.7% of elevator-months
   have at least one.
3. The worst **10% of elevators cause 26% of breakdowns and 30% of entrapments**; 8 of the 10 worst are in Manhattan.
4. **Strong persistence**: after a month with an entrapment, the chance of another next month is **40%** vs 19%.
5. **Age matters**: 20+ years since last major improvement → +47% breakdowns, +56% entrapments, -1.9 pp availability
   vs units improved in the last 2 years. Winter (Jan) has ~29% more breakdowns than spring (Apr).
6. Fleet availability improved from ~96.3% (2015-19) to ~98% (2023-25).

## Alert thresholds (monthly maintenance-planning flags, MTA elevators)
| Level | Rule | Flags / month | Next-month outcome precision |
|---|---|---|---|
| PRELIMINARY | availability < 93.7% or 3-month unscheduled ≥ 17.3 | 15.5 | 41% entrapment (base 23%) |
| WARNING | availability < 88.7% or 3-month unscheduled ≥ 24.0 | 5.3 | 45% entrapment / 22% low availability (base 1.7%) |
| LEVEL_3 | availability < 71.7% or 3-month unscheduled ≥ 30.7 | 2.3 | 52% entrapment / 69% low availability |
| EMERGENCY | any entrapment — real-time rule | ~107 events | — |

Thresholds alone catch only ≤ 9% of next-month entrapments, hence the model below.

## Next-month entrapment risk model (MTA elevators)
Gradient boosting on monthly history (12-month entrapments, historical entrapment rate, months since major
improvement, outages, availability, season, borough). Train < 2023-09, test 2023-10 → 2026-08 (11,032 unit-months,
base rate 22.9%). Audit: **approved with caveats**, metrics independently recomputed.

| Model (chronological test) | PR-AUC | ROC-AUC | Precision top 10% | Entrapment events caught top 20% |
|---|---|---|---|---|
| Base rate | 0.229 | 0.500 | 26.3% | 22.2% |
| "Entrapment this month" rule | 0.276 | 0.585 | 31.8% | 37.1% |
| Unit historical rate | 0.352 | 0.663 | 42.9% | 38.3% |
| **Gradient boosting** | **0.400** | **0.679** | **52.1%** | **45.5%** |

On 91 elevators never seen in training: PR-AUC 0.359 (still above every baseline). At the same flag volume as the
threshold rules (~16/month) the model is more precise (54.6% vs 41-52%).

| Model alert level | Probability ≥ | Flags / month (of ~317) | Precision | Entrapment events caught |
|---|---|---|---|---|
| PRELIMINARY | 0.353 | 37 | 50% | 32% |
| WARNING | 0.501 | 3.7 | 57% | 3.6% |
| LEVEL_3 | 0.592 | 0.5 | 83% (only 18 flags in 35 months — low confidence) | 0.9% |

Predictability from monthly KPIs is moderate (ROC 0.68): use the score to **rank elevators for preventive
inspection**, not as a certainty. Thresholds were fit on train scores and drift; re-fit quarterly.
Model card: [MODEL_CARD.md](../../experiments/mta_nyct_ee_availability_entrapment_next_month/MODEL_CARD.md).

## Limitations
Monthly data — no outage timing, causes or durations per event; third-party units unusable for outage analysis;
history restated in 2023 and updated monthly (snapshot downloaded 2026-10-30).

## Recommended next
1. Feed the model's monthly risk ranking into the dashboard as a "preventive inspection list".
2. Join MTA station ridership to test the usage effect (likely the biggest missing driver).
3. Start archiving the live MTA outage feed (free API key) for per-outage causes and durations.

Details: [eda.md](eda.md) · [profile.md](profile.md) · [audit.md](audit.md) ·
[thresholds](../../experiments/thresholds_mta_nyct_ee_availability/README.md)
