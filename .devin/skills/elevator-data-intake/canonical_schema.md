# Canonical elevator data schema

Every procured dataset is mapped onto these tables (as far as its content allows) and written to
`data/curated/<dataset_id>/<table>.parquet`. Keep the original columns in `data/raw/<dataset_id>/` untouched.

Column names are snake_case. Timestamps are timezone-naive UTC unless `tz` is recorded in the catalog.
Units go in the column name suffix (`_v`, `_a`, `_rpm`, `_mm_s`, `_g`, `_c`, `_kg`, `_h`, `_pct`).

## units  (one row per elevator / escalator)
| column | type | required | notes |
|---|---|---|---|
| unit_id | str | yes | stable ID; prefix with dataset if not globally unique |
| unit_type | str | yes | elevator / escalator / dumbwaiter |
| site_id | str | no | building / station |
| manufacturer, model | str | no | |
| drive_type | str | no | traction / MRL / hydraulic |
| capacity_kg, capacity_persons | num | no | |
| floors_served | int | no | |
| install_date / age_years | date / num | no | |
| lat, lon | num | no | |

## telemetry  (time series, one row per unit per timestamp)
| column | type | required | notes |
|---|---|---|---|
| unit_id | str | yes | |
| ts | datetime | yes | |
| <signal>_<unit> | num | - | e.g. motor_current_a, car_accel_z_g, door_vibration_mm_s, motor_temp_c, load_kg |
Record sampling rate and aggregation (raw / 1-min mean / hourly) in the catalog.

## events  (faults, error codes, alarms, entrapments)
| column | type | required | notes |
|---|---|---|---|
| unit_id | str | yes | |
| ts | datetime | yes | event start |
| event_type | str | yes | error_code / failure / alarm / entrapment / complaint / outage |
| code | str | no | controller code, mapped via `data/fault_fix_lookup.csv` when possible |
| component | str | no | DOOR / MOTOR / BRAKE / CONTROLLER / ROPE / GUIDE / SAFETY / OTHER |
| severity | str | no | PRELIMINARY / WARNING / LEVEL_3 / EMERGENCY |
| description | str | no | free text |

## outages  (downtime intervals)
| column | type | required | notes |
|---|---|---|---|
| unit_id | str | yes | |
| start, end | datetime | yes | `end` may be null if still out |
| scheduled | bool | no | planned maintenance vs unplanned |
| reason | str | no | |
| duration_h | num | derived | |

## maintenance  (work orders / technician visits)
| column | type | required | notes |
|---|---|---|---|
| unit_id | str | yes | |
| ts | datetime | yes | |
| work_type | str | yes | routine / corrective / callout / inspection / modernisation |
| component | str | no | |
| finding, action | str | no | what was found / what was done (needed for fault-to-fix learning) |
| hours_on_site | num | no | |

## aggregates  (pre-aggregated KPIs, e.g. monthly availability)
| column | type | required | notes |
|---|---|---|---|
| unit_id | str | yes | |
| period_start | datetime | yes | |
| period | str | yes | day / week / month |
| <kpi> | num | - | availability_pct, outages, entrapments, trips, ... |

## Label definitions (for modelling)
- **failure**: event_type in (failure, outage with scheduled = false) — state the exact rule per dataset.
- **horizon**: always explicit, e.g. "failure within next 24 h" or "> N unscheduled outages next month".
- Never derive labels from columns recorded after the prediction time (repair notes, closing dates).
