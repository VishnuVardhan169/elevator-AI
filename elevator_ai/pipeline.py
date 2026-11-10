"""End-to-end pipeline: raw Kaggle data -> processed fleet tables, model, alerts.

Run:  .venv/bin/python -m elevator_ai.pipeline
"""
import json
import time

import pandas as pd

from . import alerts as A
from . import config as C
from . import fleet, model, sound


def _step(msg: str, t0: float) -> float:
    print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)
    return time.time()


def run() -> None:
    t0 = time.time()
    C.PROCESSED.mkdir(parents=True, exist_ok=True)
    lookup = pd.read_csv(C.LOOKUP_CSV)

    elevators = fleet.build_elevators()
    telemetry = fleet.build_telemetry()
    errors, maint, failures = fleet.build_events()
    start, end = telemetry.timestamp.min(), telemetry.timestamp.max()
    ids = elevators.elevator_id.tolist()
    door = fleet.build_door_sensor(ids, start, end)
    drive = fleet.build_drive_cycles(elevators, start, end)
    downtime = fleet.build_downtime(failures, maint, lookup)
    _step("fleet tables built", t0)

    clips, sound_info = sound.build_sound_clips(ids, start, end)
    _step(f"sound features: {len(clips)} clips, holdout AUC {sound_info['holdout_roc_auc']:.3f}", t0)

    feats = model.build_features(telemetry, errors, maint, failures, elevators)
    preds, metrics, importance = model.train_and_predict(feats)
    metrics["_event_recall"] = model.event_recall(preds, failures)
    _step("failure models trained: " + ", ".join(
        f"{c} AUC={metrics[c]['roc_auc']:.3f}" for c in C.COMPONENTS), t0)

    s_alerts, s_th = A.sensor_alerts(telemetry, lookup)
    d_alerts, d_th = A.door_alerts(door)
    alerts = A.combine(
        s_alerts, d_alerts,
        A.sound_alerts(clips, sound_info["thresholds"]),
        A.prediction_alerts(preds),
        A.event_alerts(errors, failures, drive, lookup),
    )
    _step(f"alerts: {len(alerts)} total\n{alerts.level.value_counts().to_string()}", t0)

    tables = {"elevators": elevators, "telemetry": telemetry, "errors": errors, "maintenance": maint,
              "failures": failures, "door_sensor": door, "drive_cycles": drive, "downtime": downtime,
              "sound_clips": clips, "predictions": preds, "feature_importance": importance, "alerts": alerts}
    for name, df in tables.items():
        df.to_parquet(C.PROCESSED / f"{name}.parquet", index=False)
    meta = {
        "period": [str(start), str(end)],
        "thresholds": {**s_th, **d_th, "sound_anomaly_score": sound_info["thresholds"],
                       "failure_probability": C.PROB_LEVELS},
        "sound": {k: v for k, v in sound_info.items() if k != "thresholds"},
        "model": metrics,
    }
    (C.PROCESSED / "meta.json").write_text(json.dumps(meta, indent=2, default=float))
    _step(f"saved to {C.PROCESSED}", t0)


if __name__ == "__main__":
    run()
