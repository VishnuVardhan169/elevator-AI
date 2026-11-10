"""Acoustic anomaly detection on MIMII pump clips (stand-in for elevator machine-room sound)."""
import numpy as np
import pandas as pd
from scipy.io import wavfile
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import config as C

N_BANDS = 16


def clip_features(path) -> dict:
    sr, x = wavfile.read(path)
    x = (x[:, 0] if x.ndim > 1 else x).astype(np.float32) / 32768.0
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    freqs = np.fft.rfftfreq(len(x), 1 / sr)
    power = spec**2
    total = power.sum() + 1e-12
    centroid = (freqs * power).sum() / total
    cum = np.cumsum(power) / total
    rms = float(np.sqrt(np.mean(x**2)))
    feats = {
        "rms": rms,
        "crest_factor": float(np.max(np.abs(x)) / (rms + 1e-12)),
        "zero_cross_rate": float(np.mean(np.abs(np.diff(np.sign(x))) > 0)),
        "spectral_centroid_hz": float(centroid),
        "spectral_bandwidth_hz": float(np.sqrt(((freqs - centroid) ** 2 * power).sum() / total)),
        "spectral_rolloff_hz": float(freqs[np.searchsorted(cum, 0.85)]),
    }
    edges = np.logspace(np.log10(20), np.log10(sr / 2), N_BANDS + 1)
    for i in range(N_BANDS):
        band = power[(freqs >= edges[i]) & (freqs < edges[i + 1])].sum()
        feats[f"band_{i:02d}_db"] = float(10 * np.log10(band / total + 1e-12))
    return feats


def build_sound_clips(elevator_ids: list[str], start, end) -> tuple[pd.DataFrame, dict]:
    rows = []
    for label in ("normal", "abnormal"):
        for p in sorted((C.RAW / "mimii" / label).glob("*.wav")):
            rows.append({"file": str(p.relative_to(C.ROOT)).replace("\\", "/"), "true_label": label, **clip_features(p)})
    clips = pd.DataFrame(rows)
    feat_cols = [c for c in clips.columns if c not in ("file", "true_label")]

    normal_idx = clips.index[clips.true_label.eq("normal")]
    train_idx, _ = train_test_split(normal_idx, test_size=0.3, random_state=C.SEED)
    model = make_pipeline(StandardScaler(), IsolationForest(n_estimators=300, random_state=C.SEED))
    model.fit(clips.loc[train_idx, feat_cols])
    clips["anomaly_score"] = -model.score_samples(clips[feat_cols])
    clips["in_training"] = clips.index.isin(train_idx)

    # Thresholds = percentiles of the anomaly score on healthy training clips.
    train_scores = clips.loc[train_idx, "anomaly_score"]
    thresholds = {lvl: float(train_scores.quantile(q)) for lvl, q in C.PERCENTILE_LEVELS.items()}
    holdout = clips[~clips.in_training]
    metrics = {
        "holdout_roc_auc": float(roc_auc_score(holdout.true_label.eq("abnormal"), holdout.anomaly_score)),
        "n_clips": len(clips),
        "n_abnormal": int(clips.true_label.eq("abnormal").sum()),
    }

    rng = np.random.default_rng(C.SEED)
    clips["elevator_id"] = rng.choice(elevator_ids, len(clips))
    span = (pd.Timestamp(end) - pd.Timestamp(start)).total_seconds()
    clips["timestamp"] = pd.Timestamp(start) + pd.to_timedelta(rng.uniform(0, span, len(clips)), unit="s")
    clips["timestamp"] = clips.timestamp.dt.floor("h")
    return clips.sort_values("timestamp").reset_index(drop=True), {"thresholds": thresholds, **metrics}
