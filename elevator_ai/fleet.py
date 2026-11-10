"""Combine the Kaggle datasets into one synthetic 100-elevator fleet.

Backbone: Azure PdM (100 machines, hourly telemetry, errors, maintenance, failures for 2015).
Each other dataset has no machine IDs or time axis, so it is split into 100 contiguous chunks,
one per elevator, and spread evenly over the same 2015 timeline:
  * Elevator PdM (shivamb)  -> door mechanism sensor stream (revolutions, humidity, vibration)
  * AI4I 2020               -> drive/load cycles (temperatures, rpm, torque -> passengers, wear, faults)
  * MIMII pump sounds       -> machine-room sound clips (assigned in sound.py)
"""
import numpy as np
import pandas as pd

from . import config as C


def _elevator_id(machine_id: pd.Series) -> pd.Series:
    return "ELV-" + machine_id.astype(int).astype(str).str.zfill(3)


def _spread_over_year(n_per_unit: int, start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    return pd.date_range(start, end, periods=n_per_unit)


def build_elevators() -> pd.DataFrame:
    m = pd.read_csv(C.RAW / "azure" / "PdM_machines.csv")
    rng = np.random.default_rng(C.SEED)
    return pd.DataFrame({
        "elevator_id": _elevator_id(m.machineID),
        "site": rng.choice(C.SITES, len(m)),
        "model_code": m.model,
        "model": m.model.map(C.ELEVATOR_MODELS),
        "capacity_persons": m.model.map(C.MODEL_CAPACITY),
        "age_years": m.age,
    })


def _load_azure(name: str) -> pd.DataFrame:
    df = pd.read_csv(C.RAW / "azure" / f"PdM_{name}.csv", parse_dates=["datetime"])
    df.insert(0, "elevator_id", _elevator_id(df.pop("machineID")))
    return df.rename(columns={"datetime": "timestamp"})


def build_telemetry() -> pd.DataFrame:
    t = _load_azure("telemetry").rename(columns=C.SENSOR_MAP)
    return t.sort_values(["elevator_id", "timestamp"]).reset_index(drop=True)


def build_events() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    errors = _load_azure("errors")
    errors["code"] = errors.pop("errorID").map(C.ERROR_MAP)

    maint = _load_azure("maint")
    maint["component"] = maint.pop("comp").map(C.COMPONENT_MAP)

    failures = _load_azure("failures")
    failures["component"] = failures.pop("failure").map(C.COMPONENT_MAP)
    failures["code"] = "F-" + failures.component

    # A maintenance record on the same hour as a failure is the corrective repair.
    key = ["elevator_id", "timestamp", "component"]
    maint = maint.merge(failures[key].assign(_f=1), on=key, how="left")
    maint["type"] = np.where(maint.pop("_f").eq(1), "Corrective (failure repair)", "Scheduled replacement")
    return errors, maint, failures


def _chunk_to_fleet(df: pd.DataFrame, elevator_ids: list[str], start, end) -> pd.DataFrame:
    n = len(elevator_ids)
    per = len(df) // n
    df = df.iloc[: per * n].copy()
    df["elevator_id"] = np.repeat(elevator_ids, per)
    df["timestamp"] = np.tile(_spread_over_year(per, start, end), n)
    return df


def build_door_sensor(elevator_ids: list[str], start, end) -> pd.DataFrame:
    d = pd.read_csv(C.RAW / "elevator" / "predictive-maintenance-dataset.csv")
    d = d[["revolutions", "humidity", "vibration"]].rename(columns={
        "revolutions": "door_revolutions", "humidity": "humidity_pct", "vibration": "door_vibration"})
    d["door_vibration"] = d.door_vibration.interpolate(limit_direction="both")
    d = _chunk_to_fleet(d, elevator_ids, start, end)
    return d[["elevator_id", "timestamp", "door_revolutions", "humidity_pct", "door_vibration"]]


def build_drive_cycles(elevators: pd.DataFrame, start, end) -> pd.DataFrame:
    a = pd.read_csv(C.RAW / "ai4i" / "ai4i2020.csv", encoding="utf-8-sig")
    a = a.sample(frac=1, random_state=C.SEED).reset_index(drop=True)
    torque = a["Torque [Nm]"]
    df = pd.DataFrame({
        "usage_class": a.Type.map(C.AI4I_USAGE),
        "machine_room_temp_c": a["Air temperature [K]"] - 273.15,
        "motor_temp_c": a["Process temperature [K]"] - 273.15,
        "motor_rpm": a["Rotational speed [rpm]"],
        "torque_nm": torque,
        "wear_minutes": a["Tool wear [min]"],
        "failure": a["Machine failure"],
    })
    for col, code in C.AI4I_FAILURE_MAP.items():
        df[code] = a[col]
    df = _chunk_to_fleet(df, elevators.elevator_id.tolist(), start, end)
    df = df.merge(elevators[["elevator_id", "capacity_persons"]], on="elevator_id")
    scale = df.torque_nm / df.torque_nm.max() * C.OVERLOAD_FACTOR
    df["passengers"] = np.round(scale * df.capacity_persons).astype(int)
    df["load_pct"] = (df.passengers / df.capacity_persons * 100).round(1)
    df["overloaded"] = df.passengers > df.capacity_persons
    return df


def build_downtime(failures: pd.DataFrame, maint: pd.DataFrame, lookup: pd.DataFrame) -> pd.DataFrame:
    repair_hours = lookup.set_index("code").est_repair_hours
    f = failures.assign(kind="Unplanned (failure)", hours=failures.code.map(repair_hours))
    s = maint[maint.type.eq("Scheduled replacement")]
    s = s.assign(kind="Planned (maintenance)", hours=C.SCHEDULED_MAINT_HOURS, code="MAINT-" + s.component)
    cols = ["elevator_id", "timestamp", "component", "code", "kind", "hours"]
    return pd.concat([f[cols], s[cols]], ignore_index=True).sort_values("timestamp")
