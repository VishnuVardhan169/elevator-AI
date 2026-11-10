"""Failure prediction: probability that each component fails within the next 24 hours."""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import average_precision_score, precision_score, recall_score, roc_auc_score

from . import config as C

HORIZON_H = 24
STEP_H = 3


def build_features(telemetry, errors, maint, failures, elevators) -> pd.DataFrame:
    sensors = list(C.SENSOR_MAP.values())
    df = telemetry.copy()
    g = df.groupby("elevator_id")[sensors]
    for w in (3, 24):
        mean = g.rolling(w, min_periods=1).mean().reset_index(level=0, drop=True)
        std = g.rolling(w, min_periods=2).std().reset_index(level=0, drop=True)
        df[[f"{s}_mean_{w}h" for s in sensors]] = mean[sensors].to_numpy()
        df[[f"{s}_std_{w}h" for s in sensors]] = std[sensors].to_numpy()

    err = pd.crosstab([errors.elevator_id, errors.timestamp], errors.code).reset_index()
    df = df.merge(err, on=["elevator_id", "timestamp"], how="left")
    codes = sorted(C.ERROR_MAP.values())
    df[codes] = df[codes].fillna(0)
    err24 = df.groupby("elevator_id")[codes].rolling(24, min_periods=1).sum().reset_index(level=0, drop=True)
    df[[f"{c}_count_24h" for c in codes]] = err24[codes].to_numpy()
    df = df.drop(columns=codes)

    df = df.sort_values("timestamp")
    for comp in C.COMPONENTS:
        rep = maint.loc[maint.component.eq(comp), ["elevator_id", "timestamp"]].sort_values("timestamp")
        rep = rep.rename(columns={"timestamp": "_last"})
        df = pd.merge_asof(df, rep, left_on="timestamp", right_on="_last", by="elevator_id",
                           direction="backward", allow_exact_matches=False)
        df[f"hours_since_{comp}_service"] = (df.timestamp - df.pop("_last")).dt.total_seconds() / 3600
        df[f"hours_since_{comp}_service"] = df[f"hours_since_{comp}_service"].fillna(24 * 365)

        fail = failures.loc[failures.component.eq(comp), ["elevator_id", "timestamp"]].sort_values("timestamp")
        fail = fail.rename(columns={"timestamp": "_next"})
        df = pd.merge_asof(df, fail, left_on="timestamp", right_on="_next", by="elevator_id",
                           direction="forward", allow_exact_matches=False)
        hours_to = (df.pop("_next") - df.timestamp).dt.total_seconds() / 3600
        df[f"y_{comp}"] = hours_to.le(HORIZON_H).astype(int)

    df = df.merge(elevators[["elevator_id", "age_years", "model_code"]], on="elevator_id")
    df = pd.concat([df, pd.get_dummies(df.pop("model_code"), prefix="model", dtype=int)], axis=1)
    df = df[df.timestamp.dt.hour % STEP_H == 0]
    return df.sort_values(["elevator_id", "timestamp"]).reset_index(drop=True)


def feature_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in ("elevator_id", "timestamp") and not c.startswith("y_")]


def train_and_predict(features: pd.DataFrame) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    cols = feature_columns(features)
    train = features[features.timestamp < C.TRAIN_END]
    test = features[features.timestamp >= C.TRAIN_END]
    preds = test[["elevator_id", "timestamp"]].copy()
    metrics, importances = {}, []
    warn = C.PROB_LEVELS["WARNING"]

    for comp in C.COMPONENTS:
        y = f"y_{comp}"
        model = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31,
                                               l2_regularization=1.0, random_state=C.SEED)
        model.fit(train[cols], train[y])
        p = model.predict_proba(test[cols])[:, 1]
        preds[f"prob_{comp}"] = p
        metrics[comp] = {
            "roc_auc": float(roc_auc_score(test[y], p)),
            "pr_auc": float(average_precision_score(test[y], p)),
            "precision_at_warning": float(precision_score(test[y], p >= warn, zero_division=0)),
            "recall_at_warning": float(recall_score(test[y], p >= warn, zero_division=0)),
            "train_positives": int(train[y].sum()),
            "test_positives": int(test[y].sum()),
        }
        pos = test[test[y].eq(1)]
        neg = test[test[y].eq(0)].sample(min(20000, int(test[y].eq(0).sum())), random_state=C.SEED)
        sample = pd.concat([pos, neg])
        imp = permutation_importance(model, sample[cols], sample[y], scoring="roc_auc",
                                     n_repeats=3, random_state=C.SEED, n_jobs=-1)
        importances.append(pd.DataFrame({"component": comp, "feature": cols, "importance": imp.importances_mean}))

    metrics["_meta"] = {"train_end": C.TRAIN_END, "horizon_hours": HORIZON_H, "step_hours": STEP_H,
                        "n_train": len(train), "n_test": len(test)}
    return preds, metrics, pd.concat(importances, ignore_index=True)


def event_recall(preds: pd.DataFrame, failures: pd.DataFrame) -> dict:
    """Share of test-period failures preceded by a WARNING-or-higher prediction in the prior 24h."""
    out = {}
    test_fail = failures[failures.timestamp >= C.TRAIN_END]
    for comp in C.COMPONENTS:
        fc = test_fail[test_fail.component.eq(comp)]
        hits = 0
        for f in fc.itertuples():
            w = preds[(preds.elevator_id == f.elevator_id) & preds.timestamp.between(
                f.timestamp - pd.Timedelta(hours=HORIZON_H), f.timestamp)]
            hits += int((w[f"prob_{comp}"] >= C.PROB_LEVELS["WARNING"]).any())
        out[comp] = {"failures": len(fc), "caught": hits, "event_recall": hits / len(fc) if len(fc) else np.nan}
    return out
