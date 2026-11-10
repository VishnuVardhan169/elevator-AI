"""Alert engine: turns sensor readings, events and predictions into leveled alerts.

Levels: PRELIMINARY < WARNING < LEVEL_3 < EMERGENCY.
Sensor thresholds are percentiles of the training-period data (see config.PERCENTILE_LEVELS).
Consecutive out-of-limit readings are merged into one alert "episode".
"""
import numpy as np
import pandas as pd

from . import config as C

ALERT_COLS = ["elevator_id", "start", "end", "level", "code", "source", "component", "value", "threshold", "message"]
LEVELS_ASC = ["PRELIMINARY", "WARNING", "LEVEL_3"]


def percentile_thresholds(values: pd.Series, direction: str = "high") -> dict:
    return {lvl: float(values.quantile(q if direction == "high" else 1 - q))
            for lvl, q in C.PERCENTILE_LEVELS.items()}


def level_rank(values: pd.Series, thresholds: dict, direction: str = "high") -> np.ndarray:
    rank = np.zeros(len(values), dtype=int)
    for lvl in LEVELS_ASC:
        hit = values >= thresholds[lvl] if direction == "high" else values <= thresholds[lvl]
        rank = np.where(hit, C.LEVEL_RANK[lvl], rank)
    return rank


def _episodes(df: pd.DataFrame, keys: list[str], value_col: str, direction: str, gap: str) -> pd.DataFrame:
    df = df[df["rank"] > 0].sort_values(keys + ["timestamp"])
    if df.empty:
        return pd.DataFrame(columns=keys + ["start", "end", "rank", "value"])
    grp = df.groupby(keys)
    new = grp.timestamp.diff().gt(pd.Timedelta(gap)) | grp.cumcount().eq(0)
    df = df.assign(episode=new.cumsum())
    return df.groupby(keys + ["episode"], as_index=False).agg(
        start=("timestamp", "min"), end=("timestamp", "max"), rank=("rank", "max"),
        value=(value_col, "max" if direction == "high" else "min"))


def _finish(ep: pd.DataFrame, code: str, source: str, component: str, thresholds: dict, label: str) -> pd.DataFrame:
    ep = ep.copy()
    ep["level"] = ep["rank"].map(dict(enumerate(C.ALERT_LEVELS)))
    ep["threshold"] = ep.level.map(thresholds)
    ep["code"], ep["source"], ep["component"] = code, source, component
    ep["message"] = [f"{label} reached {v:.2f} (limit {t:.2f})" for v, t in zip(ep.value, ep.threshold)]
    return ep[ALERT_COLS]


def sensor_alerts(telemetry: pd.DataFrame, lookup: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    sensors = list(C.SENSOR_MAP.values())
    roll = telemetry.groupby("elevator_id")[sensors].rolling(24, min_periods=6).mean().reset_index(level=0, drop=True)
    roll = pd.concat([telemetry[["elevator_id", "timestamp"]], roll], axis=1)
    train = roll[roll.timestamp < C.TRAIN_END]
    out, thresholds = [], {}
    comp = lookup.set_index("code").component
    for s in sensors:
        d = C.SENSOR_DIRECTION[s]
        th = percentile_thresholds(train[s].dropna(), d)
        thresholds[s] = {"direction": d, "basis": "24h rolling mean", **th}
        df = roll[["elevator_id", "timestamp", s]].assign(rank=level_rank(roll[s], th, d))
        ep = _episodes(df, ["elevator_id"], s, d, "1h")
        out.append(_finish(ep, C.SENSOR_CODE[s], "Telemetry", comp[C.SENSOR_CODE[s]], th, f"{s} (24h avg)"))
    return pd.concat(out, ignore_index=True), thresholds


def door_alerts(door: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    th = percentile_thresholds(door.loc[door.timestamp < C.TRAIN_END, "door_vibration"])
    df = door.assign(rank=level_rank(door.door_vibration, th))
    ep = _episodes(df, ["elevator_id"], "door_vibration", "high", "12h")
    return _finish(ep, "S-DOOR-VIB", "Door sensor", "DOOR", th, "door_vibration"), {"door_vibration": th}


def sound_alerts(clips: pd.DataFrame, thresholds: dict) -> pd.DataFrame:
    df = clips.assign(rank=level_rank(clips.anomaly_score, thresholds))
    ep = _episodes(df, ["elevator_id"], "anomaly_score", "high", "0h")
    return _finish(ep, "S-SOUND", "Acoustic", "MOTOR", thresholds, "sound anomaly score")


def prediction_alerts(preds: pd.DataFrame) -> pd.DataFrame:
    out = []
    for comp in C.COMPONENTS:
        col = f"prob_{comp}"
        df = preds[["elevator_id", "timestamp", col]].assign(rank=level_rank(preds[col], C.PROB_LEVELS))
        ep = _episodes(df, ["elevator_id"], col, "high", "3h")
        out.append(_finish(ep, f"PRED-{comp}", "AI prediction", comp, C.PROB_LEVELS, f"{comp} failure probability (24h)"))
    return pd.concat(out, ignore_index=True)


def event_alerts(errors, failures, drive, lookup) -> pd.DataFrame:
    lk = lookup.set_index("code")
    ev = pd.concat([
        errors.assign(source="Controller error"),
        failures[["elevator_id", "timestamp", "code"]].assign(source="Failure / out of service"),
    ], ignore_index=True)

    drive_codes = list(C.AI4I_FAILURE_MAP.values())
    flt = drive.melt(id_vars=["elevator_id", "timestamp"], value_vars=drive_codes, var_name="code")
    flt = flt[flt.value.eq(1)].drop(columns="value").assign(source="Drive monitor")
    ovl = drive[drive.overloaded & drive.failure.eq(0)]
    ovl = ovl[["elevator_id", "timestamp", "load_pct"]].assign(code="O501", source="Drive monitor")

    ev = pd.concat([ev, flt], ignore_index=True)
    ev["level"] = ev.code.map(lk.default_level)
    ev["value"] = np.nan
    ev["message"] = ev.code.map(lk.title)
    ovl["level"] = "PRELIMINARY"
    ovl["value"] = ovl.pop("load_pct")
    ovl["message"] = [f"Overloaded run at {v:.0f}% of rated capacity" for v in ovl.value]
    ev = pd.concat([ev, ovl], ignore_index=True)
    ev["start"] = ev["end"] = ev.pop("timestamp")
    ev["component"] = ev.code.map(lk.component)
    ev["threshold"] = np.where(ev.code.eq("O501") & ev.value.notna(), 100.0, np.nan)
    return ev[ALERT_COLS]


def combine(*frames: pd.DataFrame) -> pd.DataFrame:
    a = pd.concat(frames, ignore_index=True).sort_values(["start", "elevator_id"]).reset_index(drop=True)
    a["level_rank"] = a.level.map(C.LEVEL_RANK)
    a.insert(0, "alert_id", [f"AL-{i:06d}" for i in range(1, len(a) + 1)])
    return a
