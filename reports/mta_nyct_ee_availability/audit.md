# Data audit: mta_nyct_ee_availability

```
DATASET / ARTIFACT: mta_nyct_ee_availability
VERDICT: APPROVED WITH CAVEATS
AUTHENTICITY: real — published by MTA New York City Transit on data.ny.gov (rc78-7x78); outages come from
              LiftNet remote monitoring -> EAM maintenance system; official methodology PDF in data/raw/.
LICENCE: NY Open Data — "There are no limitations on the data at this time" (overview PDF) — commercial use: yes
FINDINGS:
  [MEDIUM] Monthly aggregates only: no outage start/end times, durations or outage codes per event. Supports
           monthly KPIs and "next-month" prediction, not hour-level failure prediction.
  [MEDIUM] 99 of 701 units are third-party operated ("X" suffix). Most are not on LiftNet, so MTA itself flags
           their outage codes and availability as less reliable -> analyse separately / flag.
  [MEDIUM] Units in capital rehabilitation are excluded from availability; 2,573 unit-months have
           24h total hours = 0 (availability null) and 3,493 are partial months (< 90% of hours counted).
           Survivorship: availability is only measured while a unit is "in scope".
  [LOW]    Entrapments are a subset of unscheduled outages (verified: never exceed them) — don't add them.
  [LOW]    History restated in Aug 2023 (1-2% of equipment-months changed); the file is updated monthly,
           so results depend on download date (downloaded 2026-10-30, data through 2026-09).
  [LOW]    Time Since Major Improvement is null in 15.4% of rows (13.9% elevators, 17.1% escalators).
  [INFO]   synthetic_check: only a "fixed clock" flag, which is expected for monthly period data (false
           positive); no seeded-RNG, white-noise or exact-rule signatures. Internal consistency is perfect:
           availability = hours_available / total_hours in 100% of rows; total = scheduled + unscheduled in
           100% of rows; no duplicate unit-months; no gaps inside any unit's history.
RECOMMENDED CATALOG UPDATE:
  authenticity: real
  evidence: "MTA NYCT official open data (LiftNet/EAM); internally consistent; methodology PDF"
  license: NY Open Data (no limitations)
  granularity: monthly per asset, 83,776 rows, 701 assets (419 elevators, 282 escalators), 2015-01..2026-09
  status: profiled
```
