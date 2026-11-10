"""Targeted data-quality checks for the MTA NYCT elevator/escalator availability dataset (/data-profile step 3)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data/raw/mta_nyct_ee_availability/mta_nyct_elevator_escalator_availability.csv"
OUT = ROOT / "reports/mta_nyct_ee_availability"

df = pd.read_csv(RAW)
df["Month"] = pd.to_datetime(df["Month"], format="%m/%d/%Y")
res = {}

res["rows"] = len(df)
res["window"] = [str(df.Month.min().date()), str(df.Month.max().date())]
res["months"] = int(df.Month.nunique())
res["units_by_type"] = df.groupby("Equipment Type")["Equipment Code"].nunique().to_dict()
res["dup_unit_month"] = int(df.duplicated(["Equipment Code", "Month"]).sum())
res["third_party_units_X"] = int(df.loc[df["Equipment Code"].str.endswith("X"), "Equipment Code"].nunique())

# coverage per unit: months present vs span first..last
g = df.groupby("Equipment Code").Month
span = ((g.max().dt.year - g.min().dt.year) * 12 + g.max().dt.month - g.min().dt.month + 1)
present = g.nunique()
gaps = (span - present)
res["units_with_gaps"] = int((gaps > 0).sum())
res["missing_unit_months_inside_span"] = int(gaps.sum())
res["units_full_history"] = int((present == res["months"]).sum())
res["units_starting_after_2015"] = int((g.min() > df.Month.min()).sum())
res["units_ending_before_last_month"] = int((g.max() < df.Month.max()).sum())

# consistency
for p in ("AM Peak", "PM Peak", "24-Hour"):
    av, ha, th = df[f"{p} Availability"], df[f"{p} Hours Available"], df[f"{p} Total Hours"]
    calc = ha / th.replace(0, np.nan)
    res[f"{p}: |availability - hours_avail/total| > 0.005"] = int(((av - calc).abs() > 0.005).sum())
    res[f"{p}: hours_available > total_hours"] = int((ha > th + 1e-6).sum())
    res[f"{p}: total_hours == 0"] = int((th == 0).sum())
    res[f"{p}: availability null"] = int(av.isna().sum())
    res[f"{p}: availability null AND total_hours>0"] = int((av.isna() & (th > 0)).sum())
res["total != scheduled + unscheduled"] = int((df["Total Outages"] != df["Scheduled Outages"] + df["Unscheduled Outages"]).sum())
res["entrapments > unscheduled"] = int((df.Entrapments > df["Unscheduled Outages"]).sum())
res["24h total hours > hours in month"] = int((df["24-Hour Total Hours"] > df.Month.dt.days_in_month * 24 + 1).sum())
res["partial months (24h total < 90% of month)"] = int((df["24-Hour Total Hours"] < 0.9 * df.Month.dt.days_in_month * 24).sum())
res["time_since_improvement null %"] = round(df["Time Since Major Improvement"].isna().mean() * 100, 2)
res["time_since_improvement null % by type"] = (df.groupby("Equipment Type")["Time Since Major Improvement"]
                                                 .apply(lambda s: round(s.isna().mean() * 100, 1)).to_dict())
res["units in >1 borough"] = int((df.groupby("Equipment Code").Borough.nunique() > 1).sum())
res["units in >1 station"] = int((df.groupby("Equipment Code")["Station MRN"].nunique() > 1).sum())
res["months with zero availability (24h)"] = int((df["24-Hour Availability"] == 0).sum())
res["label balance: unit-months with >=1 entrapment %"] = round((df.Entrapments > 0).mean() * 100, 2)
res["label balance: elevator unit-months with >=1 entrapment %"] = round(
    (df.loc[df["Equipment Type"] == "Elevator", "Entrapments"] > 0).mean() * 100, 2)
res["units per month (min/median/max)"] = df.groupby("Month")["Equipment Code"].nunique().describe()[["min", "50%", "max"]].tolist()

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "quality.json").write_text(json.dumps(res, indent=2, default=str))
print(json.dumps(res, indent=2, default=str))
