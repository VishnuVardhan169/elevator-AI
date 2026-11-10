# Profile: mta_nyct_ee_availability

**Real data** — MTA NYCT subway elevator & escalator availability, official open data. Audit: approved with caveats
([audit.md](audit.md)).

## What it is
- One row per **unit per month**: 83,776 rows, 141 months (2015-01 → 2026-09), 701 units
  (419 elevators, 282 escalators) in 185 stations across 4 boroughs. 99 units are third-party operated (`X` suffix).
- Per unit-month: total / scheduled / unscheduled outages, entrapments, months since last major improvement,
  availability and hours available/total for the AM peak (6–10), PM peak (15–19) and 24 h.
- 485–697 units are reported per month (median 602): 216 units were commissioned after Jan 2015, 4 left before the
  last month. No unit has gaps inside its active period.

## How clean it is
Very clean and internally consistent (checks in `scripts/analysis/mta_nyct_ee_availability/quality.py`,
results in `quality.json`):

| Check | Result |
|---|---|
| Duplicate unit-months | 0 |
| availability == hours_available / total_hours (all 3 periods) | 100% of rows |
| hours_available > total_hours | 0 |
| total_outages == scheduled + unscheduled | 100% of rows |
| entrapments > unscheduled outages | 0 |
| Units changing borough/station | 0 |

Column-level statistics: [profile_table.md](profile_table.md).

## Data-quality issues
| Severity | Issue | Suggested handling |
|---|---|---|
| MEDIUM | 2,573 unit-months with 24 h total hours = 0 → availability null (unit out of scope, e.g. capital rehab) | Exclude from availability KPIs; keep for outage counts only if hours > 0 |
| MEDIUM | 3,493 partial months (< 90% of hours counted) | Weight availability by total hours (sum hours_available / sum total_hours), never average percentages |
| MEDIUM | Third-party units (99) have less reliable outage data (MTA note) | Report MTA vs third-party separately |
| LOW | 399 unit-months with 0% 24 h availability (out all month while in scope) | Keep — real long outages; examine as "long-term repair" cases |
| LOW | Time Since Major Improvement null in 15.4% | Use as feature with a missing indicator |
| LOW | AM/PM/24 h total-hours columns are near-duplicates (r ≥ 0.9998) | Use 24 h hours as the exposure; peak columns for peak-specific availability |
| INFO | Heavy-tailed outage counts: unscheduled outages median 1, mean 3.3, max 86 per month | Use medians / rates per unit-month; log scale in charts |

## What it can support
- Fleet / station / borough availability and outage KPIs, elevator vs escalator, MTA vs third-party.
- Entrapment rates (safety), 20.5% of elevator unit-months have ≥ 1 entrapment.
- Trends 2015–2026, seasonality, effect of asset age since major improvement.
- Next-month prediction (e.g. "≥ 1 entrapment" or "availability < 90%") — ample positives.
- Not supported: event timing, outage causes per event, component-level failure analysis.
