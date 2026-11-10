"""Elevator AI alerting dashboard (POC).

Run:  .venv/bin/streamlit run app/dashboard.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from scipy.io import wavfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from elevator_ai import config as C  # noqa: E402

st.set_page_config(page_title="Elevator AI - Alerts & Prediction", layout="wide")
LEVEL_ORDER = C.ALERT_LEVELS[1:]
COLOR_MAP = C.LEVEL_COLORS


@st.cache_data
def load(name: str) -> pd.DataFrame:
    return pd.read_parquet(C.PROCESSED / f"{name}.parquet")


@st.cache_data
def load_meta() -> dict:
    return json.loads((C.PROCESSED / "meta.json").read_text())


@st.cache_data
def load_lookup() -> pd.DataFrame:
    return pd.read_csv(C.LOOKUP_CSV)


if not (C.PROCESSED / "meta.json").exists():
    st.error("No processed data found. Run `python -m elevator_ai.pipeline` first.")
    st.stop()

meta = load_meta()
elevators, alerts, lookup = load("elevators"), load("alerts"), load_lookup()
failures, downtime = load("failures"), load("downtime")
period_start, period_end = (pd.Timestamp(x) for x in meta["period"])


def fault_card(code: str) -> None:
    row = lookup[lookup.code.eq(code)]
    if row.empty:
        st.info(f"No lookup entry for `{code}`.")
        return
    r = row.iloc[0]
    st.markdown(f"#### {r.code} - {r.title}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Default level", r.default_level)
    c2.metric("Component", r.component)
    c3.metric("Est. repair", f"{r.est_repair_hours:g} h")
    c4.metric("Skill", r.technician_skill)
    st.markdown(f"**Symptoms:** {r.symptoms}  \n**Probable causes:** {r.probable_causes}  \n**Parts:** {r.parts}")
    st.markdown("**Fix steps:**\n" + "\n".join(f"{i}. {s.strip()}" for i, s in enumerate(r.fix_steps.split("|"), 1)))


def level_badge(level: str) -> str:
    return f"<span style='background:{COLOR_MAP[level]};color:white;padding:2px 8px;border-radius:4px'>{level}</span>"


def color_level(v):
    return f"background-color:{COLOR_MAP.get(v, '')};color:white" if v in COLOR_MAP else ""


# ---------------- Sidebar ----------------
st.sidebar.title("Elevator AI")
st.sidebar.caption("POC: historical replay of a 100-elevator fleet built from Kaggle data")
asof = pd.Timestamp(st.sidebar.slider(
    "As-of date (replay)", min_value=period_start.date(), max_value=period_end.date(),
    value=pd.Timestamp("2015-11-15").date(), format="YYYY-MM-DD")) + pd.Timedelta(hours=23)
sites = st.sidebar.multiselect("Sites", sorted(elevators.site.unique()))
active_window_h = st.sidebar.number_input("Active alert window (hours)", 1, 168, 24)
if asof < pd.Timestamp(C.TRAIN_END):
    st.sidebar.info(f"AI predictions are only available from {C.TRAIN_END} (model test period).")

fleet = elevators[elevators.site.isin(sites)] if sites else elevators
ids = set(fleet.elevator_id)
hist = alerts[alerts.elevator_id.isin(ids) & (alerts.start <= asof)]
active = hist[hist.end >= asof - pd.Timedelta(hours=active_window_h)]

status = (active.sort_values("level_rank").groupby("elevator_id").tail(1)
          .set_index("elevator_id")[["level", "code", "message", "start"]])
fleet_status = fleet.set_index("elevator_id").join(status)
fleet_status["level"] = fleet_status.level.fillna("NORMAL")
fleet_status["level_rank"] = fleet_status.level.map(C.LEVEL_RANK)

tabs = st.tabs(["Fleet overview", "Alerts", "Elevator detail", "Failure prediction",
                "Downtime & usage", "Fault-to-fix lookup", "About the data"])

# ---------------- Fleet overview ----------------
with tabs[0]:
    st.subheader(f"Fleet status as of {asof:%Y-%m-%d}")
    f_ytd = failures[failures.elevator_id.isin(ids) & (failures.timestamp <= asof)]
    d_ytd = downtime[downtime.elevator_id.isin(ids) & (downtime.timestamp <= asof)]
    hours_elapsed = (asof - period_start).total_seconds() / 3600 * len(ids)
    cols = st.columns(7)
    cols[0].metric("Elevators", len(ids))
    for col, lvl in zip(cols[1:5], LEVEL_ORDER):
        col.metric(lvl.replace("_", " ").title(), int(fleet_status.level.eq(lvl).sum()))
    cols[5].metric("Failures to date", len(f_ytd))
    cols[6].metric("Fleet availability", f"{100 * (1 - d_ytd.hours.sum() / max(hours_elapsed, 1)):.2f}%")

    c1, c2 = st.columns([3, 2])
    with c1:
        grid = fleet_status.reset_index().sort_values("elevator_id")
        grid["row"], grid["col"] = np.arange(len(grid)) // 10, np.arange(len(grid)) % 10
        fig = px.scatter(grid, x="col", y="row", color="level", color_discrete_map=COLOR_MAP,
                         category_orders={"level": C.ALERT_LEVELS}, text=grid.elevator_id.str[-3:],
                         hover_data={"elevator_id": True, "site": True, "code": True, "message": True,
                                     "row": False, "col": False})
        fig.update_traces(marker=dict(size=38, symbol="square"), textfont=dict(color="white", size=10))
        fig.update_layout(height=430, xaxis_visible=False, yaxis_visible=False, yaxis_autorange="reversed",
                          title="Elevator health grid (worst active alert)", margin=dict(t=40, b=0))
        st.plotly_chart(fig, width="stretch")
    with c2:
        by_site = fleet_status.groupby(["site", "level"]).size().reset_index(name="elevators")
        fig = px.bar(by_site, x="elevators", y="site", color="level", orientation="h",
                     color_discrete_map=COLOR_MAP, category_orders={"level": C.ALERT_LEVELS},
                     title="Status by site")
        fig.update_layout(height=430, margin=dict(t=40, b=0))
        st.plotly_chart(fig, width="stretch")

    weekly = hist.assign(week=hist.start.dt.to_period("W").dt.start_time).groupby(["week", "level"]).size()
    fig = px.bar(weekly.reset_index(name="alerts"), x="week", y="alerts", color="level",
                 color_discrete_map=COLOR_MAP, category_orders={"level": LEVEL_ORDER}, title="Alerts per week")
    st.plotly_chart(fig, width="stretch")

    st.markdown("**Elevators needing attention**")
    attention = fleet_status[fleet_status.level_rank > 0].sort_values("level_rank", ascending=False)
    st.dataframe(attention[["site", "model", "level", "code", "message", "start"]].style.map(color_level, subset=["level"]),
                 width="stretch")

# ---------------- Alerts ----------------
with tabs[1]:
    st.subheader("Alert log")
    c1, c2, c3 = st.columns(3)
    lv = c1.multiselect("Levels", LEVEL_ORDER, default=["WARNING", "LEVEL_3", "EMERGENCY"])
    src = c2.multiselect("Sources", sorted(alerts.source.unique()))
    days = c3.slider("Look-back (days)", 1, 365, 14)
    view = hist[hist.level.isin(lv) & (hist.start >= asof - pd.Timedelta(days=days))]
    if src:
        view = view[view.source.isin(src)]
    view = view.sort_values(["start", "level_rank"], ascending=False)
    st.caption(f"{len(view)} alerts. Select a row to see the recommended fix.")
    shown = view[["alert_id", "start", "elevator_id", "level", "code", "source", "component", "message"]]
    sel = st.dataframe(shown.style.map(color_level, subset=["level"]), width="stretch", height=380,
                       hide_index=True, on_select="rerun", selection_mode="single-row")
    if sel.selection.rows:
        a = shown.iloc[sel.selection.rows[0]]
        st.markdown(f"**{a.alert_id}** on **{a.elevator_id}** at {a.start:%Y-%m-%d %H:%M} &nbsp; {level_badge(a.level)}",
                    unsafe_allow_html=True)
        fault_card(a.code)

# ---------------- Elevator detail ----------------
with tabs[2]:
    eid = st.selectbox("Elevator", sorted(ids), index=0)
    info = fleet_status.loc[eid]
    st.markdown(f"### {eid} &nbsp; {level_badge(info.level)}", unsafe_allow_html=True)
    st.caption(f"{info.site} · {info.model} · {info.age_years} years old · capacity {info.capacity_persons} persons")
    window_days = st.slider("Window (days before as-of)", 3, 120, 30)
    w0 = asof - pd.Timedelta(days=window_days)

    tel = load("telemetry")
    tel = tel[(tel.elevator_id == eid) & tel.timestamp.between(w0, asof)].set_index("timestamp")
    sensor = st.radio("Sensor", list(C.SENSOR_MAP.values()), horizontal=True)
    th = meta["thresholds"][sensor]
    fig = go.Figure()
    fig.add_scatter(x=tel.index, y=tel[sensor], name="hourly", line=dict(color="#bbb", width=1))
    fig.add_scatter(x=tel.index, y=tel[sensor].rolling(24, min_periods=6).mean(), name="24h avg",
                    line=dict(color="#1f77b4", width=2))
    for lvl in ["PRELIMINARY", "WARNING", "LEVEL_3"]:
        fig.add_hline(y=th[lvl], line_dash="dash", line_color=COLOR_MAP[lvl], annotation_text=lvl)
    ev = pd.concat([
        load("errors").assign(kind="error"), failures.assign(kind="failure"),
        load("maintenance").assign(kind="maintenance", code=lambda d: "MAINT-" + d.component),
    ])
    ev = ev[(ev.elevator_id == eid) & ev.timestamp.between(w0, asof)]
    sym = {"error": "x", "failure": "star", "maintenance": "triangle-up"}
    for kind, g in ev.groupby("kind"):
        fig.add_scatter(x=g.timestamp, y=[tel[sensor].max() * 1.02] * len(g), mode="markers", name=kind,
                        marker=dict(symbol=sym[kind], size=12), text=g.code, hovertemplate="%{text}<br>%{x}")
    fig.update_layout(height=380, title=f"{sensor} ({th['direction']} = bad)", margin=dict(t=40, b=0))
    st.plotly_chart(fig, width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        preds = load("predictions")
        p = preds[(preds.elevator_id == eid) & preds.timestamp.between(w0, asof)]
        if p.empty:
            st.info("No AI predictions in this window (predictions cover the test period only).")
        else:
            fig = px.line(p.melt("timestamp", [f"prob_{c}" for c in C.COMPONENTS], var_name="component",
                                 value_name="probability"), x="timestamp", y="probability", color="component",
                          title="Predicted failure probability (next 24h)")
            for lvl, v in C.PROB_LEVELS.items():
                fig.add_hline(y=v, line_dash="dot", line_color=COLOR_MAP[lvl])
            fig.update_layout(height=320, yaxis_range=[0, 1], margin=dict(t=40, b=0))
            st.plotly_chart(fig, width="stretch")
    with c2:
        door = load("door_sensor")
        d = door[(door.elevator_id == eid) & door.timestamp.between(w0, asof)]
        fig = px.line(d, x="timestamp", y="door_vibration", title="Door mechanism vibration")
        for lvl in ["PRELIMINARY", "WARNING", "LEVEL_3"]:
            fig.add_hline(y=meta["thresholds"]["door_vibration"][lvl], line_dash="dash", line_color=COLOR_MAP[lvl])
        fig.update_layout(height=320, margin=dict(t=40, b=0))
        st.plotly_chart(fig, width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        drive = load("drive_cycles")
        dr = drive[(drive.elevator_id == eid) & drive.timestamp.between(w0, asof)]
        fig = px.bar(dr, x="timestamp", y="load_pct", color="overloaded", title="Car load per sampled run (% of capacity)",
                     color_discrete_map={True: "#e74c3c", False: "#3498db"})
        fig.add_hline(y=100, line_dash="dash")
        fig.update_layout(height=300, margin=dict(t=40, b=0))
        st.plotly_chart(fig, width="stretch")
    with c2:
        clips = load("sound_clips")
        cl = clips[(clips.elevator_id == eid) & (clips.timestamp <= asof)].sort_values("timestamp", ascending=False)
        st.markdown("**Machine-room sound recordings**")
        if cl.empty:
            st.info("No recordings for this elevator yet.")
        else:
            sth = meta["thresholds"]["sound_anomaly_score"]
            cl = cl.assign(level=[next((l for l in ["LEVEL_3", "WARNING", "PRELIMINARY"] if s >= sth[l]), "NORMAL")
                                  for s in cl.anomaly_score])
            st.dataframe(cl[["timestamp", "anomaly_score", "level", "spectral_centroid_hz", "rms"]]
                         .style.map(color_level, subset=["level"]), hide_index=True, width="stretch")
            pick = st.selectbox("Play recording", cl.timestamp.astype(str).tolist())
            sr, x = wavfile.read(C.ROOT / cl[cl.timestamp.astype(str) == pick].iloc[0].file)
            st.audio((x[:, 0] if x.ndim > 1 else x).astype(np.float32) / 32768.0, sample_rate=sr)

    st.markdown("**Alert history**")
    eh = hist[hist.elevator_id == eid].sort_values("start", ascending=False)
    st.dataframe(eh[["start", "end", "level", "code", "source", "message"]].style.map(color_level, subset=["level"]),
                 hide_index=True, width="stretch", height=250)

# ---------------- Failure prediction ----------------
with tabs[3]:
    st.subheader("AI failure prediction (component fails within next 24h)")
    m = meta["model"]
    st.caption(f"Gradient-boosted classifiers trained on data before {C.TRAIN_END}, evaluated on "
               f"{m['_meta']['n_test']:,} unseen 3-hourly snapshots after it.")
    perf = pd.DataFrame({c: {**m[c], **m["_event_recall"][c]} for c in C.COMPONENTS}).T
    st.dataframe(perf[["roc_auc", "pr_auc", "precision_at_warning", "recall_at_warning", "failures", "caught",
                       "event_recall"]].astype(float).round(3), width="stretch")
    st.warning("Scores are near-perfect because the Azure PdM data is synthetic with strong pre-failure "
               "sensor signatures. Expect lower accuracy on real elevator data.")

    c1, c2 = st.columns(2)
    with c1:
        fi = load("feature_importance")
        comp = st.selectbox("Component", C.COMPONENTS)
        top = fi[fi.component == comp].nlargest(12, "importance")
        fig = px.bar(top, x="importance", y="feature", orientation="h", title=f"Top drivers - {comp}")
        fig.update_layout(height=420, yaxis_autorange="reversed", margin=dict(t=40, b=0))
        st.plotly_chart(fig, width="stretch")
    with c2:
        preds = load("predictions")
        recent = preds[preds.elevator_id.isin(ids) & preds.timestamp.between(asof - pd.Timedelta(hours=24), asof)]
        if recent.empty:
            st.info("Move the as-of date into the test period to see at-risk elevators.")
        else:
            risk = recent.groupby("elevator_id")[[f"prob_{c}" for c in C.COMPONENTS]].max()
            risk["max_risk"] = risk.max(axis=1)
            risk["component"] = risk.drop(columns="max_risk").idxmax(axis=1).str.replace("prob_", "")
            st.markdown(f"**Top at-risk elevators (last 24h to {asof:%Y-%m-%d})**")
            st.dataframe(risk.sort_values("max_risk", ascending=False).head(15).round(3), width="stretch",
                         column_config={"max_risk": st.column_config.ProgressColumn(
                             "max_risk", min_value=0.0, max_value=1.0, format="%.2f")})

# ---------------- Downtime & usage ----------------
with tabs[4]:
    st.subheader("Downtime, operating hours and load analysis")
    dt = downtime[downtime.elevator_id.isin(ids) & (downtime.timestamp <= asof)].merge(elevators, on="elevator_id")
    c1, c2, c3 = st.columns(3)
    c1.metric("Unplanned downtime", f"{dt[dt.kind.str.startswith('Unplanned')].hours.sum():,.0f} h")
    c2.metric("Planned downtime", f"{dt[dt.kind.str.startswith('Planned')].hours.sum():,.0f} h")
    c3.metric("Mean time between failures",
              f"{(asof - period_start).total_seconds() / 3600 * len(ids) / max(len(f_ytd), 1):,.0f} h")

    c1, c2 = st.columns(2)
    fig = px.bar(dt.groupby(["component", "kind"]).hours.sum().reset_index(), x="component", y="hours",
                 color="kind", title="Downtime hours by component")
    c1.plotly_chart(fig, width="stretch")
    dt["age_band"] = pd.cut(dt.age_years, [-1, 5, 10, 15, 25], labels=["0-5y", "6-10y", "11-15y", "16-20y"])
    per_unit = dt[dt.kind.str.startswith("Unplanned")].groupby("age_band", observed=False).hours.sum() / \
        elevators[elevators.elevator_id.isin(ids)].assign(age_band=lambda d: pd.cut(
            d.age_years, [-1, 5, 10, 15, 25], labels=["0-5y", "6-10y", "11-15y", "16-20y"])
        ).groupby("age_band", observed=False).size()
    fig = px.bar(per_unit.reset_index(name="hours"), x="age_band", y="hours",
                 title="Unplanned downtime per elevator by age")
    c2.plotly_chart(fig, width="stretch")

    worst = dt.groupby("elevator_id").hours.sum().nlargest(15).reset_index()
    fig = px.bar(worst, x="elevator_id", y="hours", title="Top 15 elevators by downtime hours")
    st.plotly_chart(fig, width="stretch")

    st.markdown("#### How load and operating time affect failures")
    drive = load("drive_cycles")
    drive = drive[drive.elevator_id.isin(ids)]
    c1, c2, c3 = st.columns(3)
    lb = drive.assign(load_band=pd.cut(drive.load_pct, [0, 50, 75, 90, 100, 200],
                                       labels=["<50%", "50-75%", "75-90%", "90-100%", ">100% (overload)"]))
    fr = lb.groupby("load_band", observed=False).failure.mean().mul(100).reset_index(name="failure_rate_pct")
    c1.plotly_chart(px.bar(fr, x="load_band", y="failure_rate_pct", title="Failure rate vs car load"), width="stretch")
    wb = drive.assign(op_band=pd.cut(drive.wear_minutes, [-1, 50, 100, 150, 200, 260]))
    fr = wb.groupby("op_band", observed=False).failure.mean().mul(100).reset_index(name="failure_rate_pct")
    fr["op_band"] = fr.op_band.astype(str)
    c2.plotly_chart(px.bar(fr, x="op_band", y="failure_rate_pct",
                           title="Failure rate vs operating minutes since service"), width="stretch")
    fr = drive.groupby("usage_class").failure.mean().mul(100).reset_index(name="failure_rate_pct")
    c3.plotly_chart(px.bar(fr, x="usage_class", y="failure_rate_pct", title="Failure rate by traffic class"),
                    width="stretch")
    fm = drive[list(C.AI4I_FAILURE_MAP.values())].sum().rename(lookup.set_index("code").title).reset_index()
    fm.columns = ["fault", "count"]
    st.plotly_chart(px.bar(fm, x="count", y="fault", orientation="h", title="Drive fault types"), width="stretch")

# ---------------- Fault-to-fix lookup ----------------
with tabs[5]:
    st.subheader("Fault-to-fix lookup")
    q = st.text_input("Search code, component or symptom")
    lk = lookup
    if q:
        lk = lk[lk.apply(lambda r: q.lower() in " ".join(map(str, r.values)).lower(), axis=1)]
    st.dataframe(lk[["code", "title", "category", "component", "default_level", "est_repair_hours"]]
                 .style.map(color_level, subset=["default_level"]), hide_index=True, width="stretch")
    code = st.selectbox("Show fix for", lk.code.tolist())
    if code:
        fault_card(code)
        n = hist[hist.code == code]
        st.caption(f"{len(n)} occurrences in the fleet up to {asof:%Y-%m-%d}, on {n.elevator_id.nunique()} elevators.")

# ---------------- About ----------------
with tabs[6]:
    st.subheader("How this POC combines the data")
    st.markdown(f"""
| Source (Kaggle) | Used as | Notes |
|---|---|---|
| `arnabbiswas1/microsoft-azure-predictive-maintenance` | **Fleet backbone**: 100 elevators, hourly telemetry, error codes, maintenance, failures for 2015 | volt → motor voltage, rotate → motor RPM, pressure → brake pressure, vibration → car vibration; comp1-4 → DOOR / MOTOR / BRAKE / CONTROLLER |
| `shivamb/elevator-predictive-maintenance-dataset` | Door mechanism sensor (revolutions, humidity, vibration) | No IDs/timestamps: split into 100 chunks spread over 2015 |
| `stephanmatzka/predictive-maintenance-dataset-ai4i-2020` | Drive & load cycles: temperatures, torque → passengers, wear → operating time, failure modes | Same chunking; torque scaled to 0-125% of car capacity |
| `giacomoveneri1/mimii-dataset-sound-data-for-malfunctioning-pump` | Machine-room sound clips (normal / abnormal) | Clips randomly assigned to elevators and dates |

**Alert levels**: Preliminary / Warning / Level 3 thresholds = {', '.join(f'p{int(q * 1000) / 10:g}' for q in C.PERCENTILE_LEVELS.values())}
of the pre-{C.TRAIN_END} data for each sensor (direction-aware). Failures → Level 3; controller program malfunction (E105) → Emergency.
AI predictions: probability ≥ {C.PROB_LEVELS['PRELIMINARY']} / {C.PROB_LEVELS['WARNING']} / {C.PROB_LEVELS['LEVEL_3']}.

The datasets come from different machines, so links between them (e.g. a sound clip and a failure on the same elevator) are **synthetic**.
Treat cross-source patterns as a demo of the system, not as findings.
""")
    st.markdown("**Computed thresholds**")
    st.json(meta["thresholds"], expanded=False)
    st.markdown(f"**Sound anomaly detector**: IsolationForest on spectral features, hold-out ROC AUC "
                f"{meta['sound']['holdout_roc_auc']:.3f} ({meta['sound']['n_clips']} clips).")
