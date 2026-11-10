# Profile: data/raw/mta_nyct_ee_availability/mta_nyct_elevator_escalator_availability.csv

- Rows: **83,776**, columns: **22**, duplicate rows: 0, memory: 20.6 MB
- Time column `Month`: 2015-01-01 00:00:00 -> 2026-09-01 00:00:00; most common intervals {'31 days 00:00:00': 48703, '30 days 00:00:00': 27266, '28 days 00:00:00': 5383}
- Units (`Equipment Code`): 701, rows/unit {'count': 701.0, 'mean': 119.5, 'std': 39.6, 'min': 1.0, '25%': 117.0, '50%': 141.0, '75%': 141.0, 'max': 141.0}
- Max |corr| between numeric columns: 0.9999

## Columns

| column | dtype | null % | unique | mean | std | min | median | max | skew | outlier % |
|---|---|---|---|---|---|---|---|---|---|---|
| Month | datetime64[us] | 0.0 | 141 |  |  |  |  |  |  |  |
| Borough | str | 0.0 | 4 |  |  |  |  |  |  |  |
| Equipment Type | str | 0.0 | 2 |  |  |  |  |  |  |  |
| Equipment Code | str | 0.0 | 701 |  |  |  |  |  |  |  |
| Total Outages | int64 | 0.0 | 71 | 5.5048 | 6.356 | 0.0 | 4.0 | 91.0 | 2.332 | 1.04 |
| Scheduled Outages | int64 | 0.0 | 36 | 2.1621 | 2.5429 | 0.0 | 2.0 | 35.0 | 3.444 | 1.756 |
| Unscheduled Outages | int64 | 0.0 | 62 | 3.3428 | 5.1181 | 0.0 | 1.0 | 86.0 | 3.02 | 3.065 |
| Entrapments | int64 | 0.0 | 12 | 0.1684 | 0.5754 | 0.0 | 0.0 | 12.0 | 5.215 | 11.241 |
| Time Since Major Improvement | float64 | 15.35 | 1455 | 343.3939 | 323.898 | 1.0 | 227.0 | 1455.0 | 1.269 | 0.072 |
| AM Peak Availability | float64 | 3.11 | 6539 | 0.9562 | 0.1152 | 0.0 | 0.9919 | 1.0 | -5.6 | 6.379 |
| AM Peak Hours Available | float64 | 0.0 | 5866 | 112.1383 | 25.408 | 0.0 | 120.0 | 124.0 | -3.619 | 6.75 |
| AM Peak Total Hours | float64 | 0.0 | 541 | 117.2802 | 22.3524 | 0.0 | 124.0 | 124.0 | -4.812 | 4.193 |
| PM Peak Availability | float64 | 3.09 | 6796 | 0.9513 | 0.1165 | 0.0 | 0.9872 | 1.0 | -5.339 | 5.455 |
| PM Peak Hours Available | float64 | 0.0 | 6195 | 111.5653 | 25.3923 | 0.0 | 120.0 | 124.0 | -3.563 | 6.409 |
| PM Peak Total Hours | float64 | 0.0 | 476 | 117.2855 | 22.3411 | 0.0 | 124.0 | 124.0 | -4.814 | 4.186 |
| 24-Hour Availability | float64 | 3.07 | 19398 | 0.9482 | 0.1133 | 0.0 | 0.9792 | 1.0 | -5.669 | 5.947 |
| 24-Hour Hours Available | float64 | 0.0 | 12774 | 667.1611 | 150.794 | 0.0 | 711.95 | 744.0 | -3.635 | 6.947 |
| 24-Hour Total Hours | float64 | 0.0 | 1890 | 703.6427 | 134.0695 | 0.0 | 744.0 | 744.0 | -4.813 | 4.152 |
| Station Name | str | 0.0 | 185 |  |  |  |  |  |  |  |
| Station MRN | int64 | 0.0 | 185 | 272.3742 | 133.1718 | 2.0 | 275.0 | 477.0 | -0.164 | 0.0 |
| Station Complex Name | str | 0.0 | 139 |  |  |  |  |  |  |  |
| Station Complex MRN | int64 | 0.0 | 152 | 416.5377 | 189.6306 | 2.0 | 438.0 | 636.0 | -0.314 | 0.0 |

## Redundant (derived) columns |r| >= 0.999

- `AM Peak Total Hours` ~ `PM Peak Total Hours` (r=0.99985)
- `AM Peak Total Hours` ~ `24-Hour Total Hours` (r=0.99993)
- `PM Peak Total Hours` ~ `24-Hour Total Hours` (r=0.99993)

## Strong correlations

- `Total Outages` ~ `Unscheduled Outages` (r=0.924)
- `AM Peak Availability` ~ `AM Peak Hours Available` (r=0.878)
- `AM Peak Availability` ~ `PM Peak Availability` (r=0.957)
- `AM Peak Availability` ~ `PM Peak Hours Available` (r=0.844)
- `AM Peak Availability` ~ `24-Hour Availability` (r=0.985)
- `AM Peak Availability` ~ `24-Hour Hours Available` (r=0.864)
- `AM Peak Hours Available` ~ `AM Peak Total Hours` (r=0.841)
- `AM Peak Hours Available` ~ `PM Peak Availability` (r=0.835)
- `AM Peak Hours Available` ~ `PM Peak Hours Available` (r=0.987)
- `AM Peak Hours Available` ~ `PM Peak Total Hours` (r=0.841)
- `AM Peak Hours Available` ~ `24-Hour Availability` (r=0.856)
- `AM Peak Hours Available` ~ `24-Hour Hours Available` (r=0.996)
- `AM Peak Hours Available` ~ `24-Hour Total Hours` (r=0.841)
- `AM Peak Total Hours` ~ `PM Peak Hours Available` (r=0.836)
- `AM Peak Total Hours` ~ `24-Hour Hours Available` (r=0.842)
- `PM Peak Availability` ~ `PM Peak Hours Available` (r=0.877)
- `PM Peak Availability` ~ `24-Hour Availability` (r=0.982)
- `PM Peak Availability` ~ `24-Hour Hours Available` (r=0.855)
- `PM Peak Hours Available` ~ `PM Peak Total Hours` (r=0.836)
- `PM Peak Hours Available` ~ `24-Hour Availability` (r=0.858)
- `PM Peak Hours Available` ~ `24-Hour Hours Available` (r=0.995)
- `PM Peak Hours Available` ~ `24-Hour Total Hours` (r=0.836)
- `PM Peak Total Hours` ~ `24-Hour Hours Available` (r=0.843)
- `24-Hour Availability` ~ `24-Hour Hours Available` (r=0.868)
- `24-Hour Hours Available` ~ `24-Hour Total Hours` (r=0.843)
