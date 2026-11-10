"""Map MTA NYCT elevator/escalator availability onto the canonical schema.

raw:     data/raw/mta_nyct_ee_availability/mta_nyct_elevator_escalator_availability.csv
outputs: data/curated/mta_nyct_ee_availability/units.parquet, aggregates.parquet
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/mta_nyct_ee_availability/mta_nyct_elevator_escalator_availability.csv"
OUT = ROOT / "data/curated/mta_nyct_ee_availability"

df = pd.read_csv(RAW)
df["Month"] = pd.to_datetime(df["Month"], format="%m/%d/%Y")
df = df.sort_values(["Equipment Code", "Month"])

last = df.groupby("Equipment Code").tail(1)
units = pd.DataFrame({
    "unit_id": last["Equipment Code"],
    "unit_type": last["Equipment Type"].str.lower(),
    "operator": last["Equipment Code"].str.endswith("X").map({True: "third_party", False: "MTA"}),
    "site_id": last["Station MRN"].astype(str),
    "station_name": last["Station Name"],
    "station_complex_id": last["Station Complex MRN"].astype(str),
    "station_complex_name": last["Station Complex Name"],
    "borough": last["Borough"],
}).merge(df.groupby("Equipment Code").Month.agg(first_month="min", last_month="max")
         .rename_axis("unit_id").reset_index(), on="unit_id")

aggregates = pd.DataFrame({
    "unit_id": df["Equipment Code"],
    "period_start": df["Month"],
    "period": "month",
    "outages_total": df["Total Outages"],
    "outages_scheduled": df["Scheduled Outages"],
    "outages_unscheduled": df["Unscheduled Outages"],
    "entrapments": df["Entrapments"],
    "months_since_major_improvement": df["Time Since Major Improvement"],
    "availability_am_pct": df["AM Peak Availability"] * 100,
    "availability_pm_pct": df["PM Peak Availability"] * 100,
    "availability_24h_pct": df["24-Hour Availability"] * 100,
    "hours_available_am": df["AM Peak Hours Available"],
    "hours_total_am": df["AM Peak Total Hours"],
    "hours_available_pm": df["PM Peak Hours Available"],
    "hours_total_pm": df["PM Peak Total Hours"],
    "hours_available_24h": df["24-Hour Hours Available"],
    "hours_total_24h": df["24-Hour Total Hours"],
})
aggregates["downtime_24h_h"] = aggregates.hours_total_24h - aggregates.hours_available_24h

OUT.mkdir(parents=True, exist_ok=True)
units.to_parquet(OUT / "units.parquet", index=False)
aggregates.to_parquet(OUT / "aggregates.parquet", index=False)
print(f"units: {len(units)} rows, aggregates: {len(aggregates)} rows -> {OUT}")
