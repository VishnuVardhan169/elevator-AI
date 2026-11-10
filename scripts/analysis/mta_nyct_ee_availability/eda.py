"""EDA for MTA NYCT elevator/escalator availability (/eda-report).

Reads data/curated/mta_nyct_ee_availability/*.parquet, writes charts reports/mta_nyct_ee_availability/eda_*.html
and numeric results eda_results.json.
Rules: availability is always hours-weighted (sum available / sum total), unit-months with 0 total hours are
excluded from availability; rates are per unit-month.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
from scipy import stats

ROOT = Path(__file__).resolve().parents[3]
CUR = ROOT / "data/curated/mta_nyct_ee_availability"
OUT = ROOT / "reports/mta_nyct_ee_availability"
OUT.mkdir(parents=True, exist_ok=True)

units = pd.read_parquet(CUR / "units.parquet")
a = pd.read_parquet(CUR / "aggregates.parquet").merge(units[["unit_id", "unit_type", "operator", "borough",
                                                             "station_complex_id"]], on="unit_id")
a["year"] = a.period_start.dt.year
a["month"] = a.period_start.dt.month
a["in_scope"] = a.hours_total_24h > 0
R = {}


def avail(df, p="24h"):
    d = df[df[f"hours_total_{p}"] > 0]
    return round(100 * d[f"hours_available_{p}"].sum() / d[f"hours_total_{p}"].sum(), 2)


def save(fig, name):
    fig.write_html(OUT / f"eda_{name}.html", include_plotlyjs="cdn")


def summary(df):
    return {
        "unit_months": int(len(df)),
        "availability_24h_pct": avail(df), "availability_am_pct": avail(df, "am"), "availability_pm_pct": avail(df, "pm"),
        "unscheduled_per_unit_month": round(df.outages_unscheduled.mean(), 3),
        "scheduled_per_unit_month": round(df.outages_scheduled.mean(), 3),
        "entrapments_per_100_unit_months": round(df.entrapments.mean() * 100, 2),
        "share_unit_months_with_entrapment_pct": round((df.entrapments > 0).mean() * 100, 2),
    }


# ---------- 1. coverage & headline ----------
R["coverage"] = {"window": [str(a.period_start.min().date()), str(a.period_start.max().date())],
                 "units": units.groupby(["unit_type", "operator"]).size().unstack(fill_value=0).to_dict()}
R["by_type"] = {t: summary(g) for t, g in a.groupby("unit_type")}
R["by_type_operator"] = {f"{t}/{o}": summary(g) for (t, o), g in a.groupby(["unit_type", "operator"])}
cov = a.groupby(["period_start", "unit_type"]).unit_id.nunique().reset_index(name="units")
save(px.line(cov, x="period_start", y="units", color="unit_type", title="Units reported per month"), "coverage")

# Third-party units record ~0 outages/entrapments (not on LiftNet), so every outage/entrapment analysis below
# uses MTA-operated units only. Availability for third-party units is reported in by_type_operator above.
R["third_party_outage_check"] = {f"{t}": round(g.outages_unscheduled.mean(), 4)
                                 for t, g in a[a.operator == "third_party"].groupby("unit_type")}
a = a[a.operator == "MTA"].copy()
R["analysis_scope"] = "MTA-operated units only from here on"

# ---------- 2. trend by year ----------
yr = []
for (y, t), g in a.groupby(["year", "unit_type"]):
    yr.append({"year": y, "unit_type": t, **summary(g)})
yr = pd.DataFrame(yr)
R["by_year"] = yr.to_dict("records")
save(px.line(yr, x="year", y="availability_24h_pct", color="unit_type", markers=True,
             title="24h availability by year (hours-weighted)"), "trend_availability")
save(px.line(yr, x="year", y="unscheduled_per_unit_month", color="unit_type", markers=True,
             title="Unscheduled outages per unit-month by year"), "trend_unscheduled")
el = a[a.unit_type == "elevator"]
yr_el = yr[yr.unit_type == "elevator"]
save(px.bar(yr_el, x="year", y="entrapments_per_100_unit_months",
            title="Elevator entrapments per 100 elevator-months"), "trend_entrapments")
rho, p = stats.spearmanr(yr_el.year, yr_el.unscheduled_per_unit_month)
R["elevator_trend_unscheduled_spearman"] = {"rho": round(rho, 3), "p": float(p)}

# ---------- 3. seasonality ----------
mo = el.groupby("month").agg(unscheduled=("outages_unscheduled", "mean"), entrapments=("entrapments", "mean"),
                             avail_av=("hours_available_24h", "sum"), avail_tot=("hours_total_24h", "sum")).reset_index()
mo["availability_24h_pct"] = 100 * mo.avail_av / mo.avail_tot
R["elevator_by_month_of_year"] = mo[["month", "unscheduled", "entrapments", "availability_24h_pct"]].round(3).to_dict("records")
kw = stats.kruskal(*[g.outages_unscheduled for _, g in el.groupby("month")])
R["elevator_month_of_year_kruskal_p"] = float(kw.pvalue)
save(px.bar(mo, x="month", y="unscheduled", title="Elevators: unscheduled outages per unit-month by calendar month"),
     "seasonality")

# ---------- 4. unit heterogeneity / Pareto ----------
per_unit = (a[a.in_scope].groupby(["unit_id", "unit_type", "operator", "borough"])
            .agg(months=("period_start", "size"), unscheduled=("outages_unscheduled", "sum"),
                 entrapments=("entrapments", "sum"), h_av=("hours_available_24h", "sum"),
                 h_tot=("hours_total_24h", "sum")).reset_index())
per_unit["unscheduled_per_month"] = per_unit.unscheduled / per_unit.months
per_unit["entrapments_per_year"] = per_unit.entrapments / per_unit.months * 12
per_unit["availability_24h_pct"] = 100 * per_unit.h_av / per_unit.h_tot
pareto = {}
for t, g in per_unit.groupby("unit_type"):
    s = g.sort_values("unscheduled", ascending=False).unscheduled
    cum = s.cumsum() / s.sum()
    n = len(s)
    pareto[t] = {"units": n,
                 "share_of_unscheduled_from_top10pct_units": round(float(cum.iloc[int(np.ceil(n * .1)) - 1]) * 100, 1),
                 "share_of_unscheduled_from_top20pct_units": round(float(cum.iloc[int(np.ceil(n * .2)) - 1]) * 100, 1),
                 "unscheduled_per_month_p10_p50_p90": g.unscheduled_per_month.quantile([.1, .5, .9]).round(2).tolist(),
                 "availability_p10_p50_p90": g.availability_24h_pct.quantile([.1, .5, .9]).round(2).tolist()}
    if t == "elevator":
        e = g.sort_values("entrapments", ascending=False).entrapments
        ce = e.cumsum() / e.sum()
        pareto[t]["share_of_entrapments_from_top10pct_units"] = round(float(ce.iloc[int(np.ceil(n * .1)) - 1]) * 100, 1)
        pareto[t]["units_with_zero_entrapments"] = int((g.entrapments == 0).sum())
R["pareto"] = pareto
worst = (per_unit[(per_unit.unit_type == "elevator") & (per_unit.months >= 24)]
         .sort_values("unscheduled_per_month", ascending=False).head(15))
R["worst_elevators"] = worst[["unit_id", "borough", "operator", "months", "unscheduled_per_month",
                              "entrapments_per_year", "availability_24h_pct"]].round(2).to_dict("records")
save(px.histogram(per_unit, x="unscheduled_per_month", color="unit_type", nbins=60, barmode="overlay",
                  title="Per-unit unscheduled outages per month (distribution)"), "unit_distribution")
save(px.scatter(per_unit[per_unit.unit_type == "elevator"], x="unscheduled_per_month", y="availability_24h_pct",
                size="entrapments_per_year", color="operator", hover_data=["unit_id", "borough"],
                title="Elevators: outages vs availability (bubble = entrapments/yr)"), "unit_scatter")

# ---------- 5. drivers: operator, borough, age since improvement ----------
R["by_borough_elevator"] = {b: summary(g) for b, g in el.groupby("borough")}
ct = pd.crosstab(el.borough, el.entrapments > 0)
R["elevator_entrapment_by_borough_chi2_p"] = float(stats.chi2_contingency(ct)[1])

el_age = el.dropna(subset=["months_since_major_improvement"]).copy()
el_age["years_since_improvement"] = el_age.months_since_major_improvement / 12
el_age["age_band"] = pd.cut(el_age.years_since_improvement, [0, 2, 5, 10, 20, 200],
                            labels=["0-2y", "2-5y", "5-10y", "10-20y", "20y+"], include_lowest=True)
age = []
for b, g in el_age.groupby("age_band", observed=True):
    age.append({"band": str(b), **summary(g)})
R["elevator_by_years_since_major_improvement"] = age
rho, p = stats.spearmanr(el_age.months_since_major_improvement, el_age.outages_unscheduled)
R["elevator_age_vs_unscheduled_spearman"] = {"rho": round(rho, 3), "p": float(p), "n": int(len(el_age))}
save(px.bar(pd.DataFrame(age), x="band", y=["unscheduled_per_unit_month", "entrapments_per_100_unit_months"],
            barmode="group", title="Elevators by years since last major improvement"), "age_bands")

# ---------- 6. downtime & peaks ----------
ins = a[a.in_scope].copy()
ins["downtime_share_pct"] = 100 * ins.downtime_24h_h / ins.hours_total_24h
R["downtime"] = {t: {"monthly_downtime_h_p50_p90_p99": g.downtime_24h_h.quantile([.5, .9, .99]).round(1).tolist(),
                     "unit_months_fully_down": int((g.hours_available_24h == 0).sum()),
                     "unit_months_below_90pct": int((g.downtime_share_pct > 10).sum()),
                     "share_unit_months_below_90pct": round((g.downtime_share_pct > 10).mean() * 100, 2)}
                 for t, g in ins.groupby("unit_type")}
R["peak_vs_24h"] = {t: {"am_minus_24h_pp": round(avail(g, "am") - avail(g), 2),
                        "pm_minus_24h_pp": round(avail(g, "pm") - avail(g), 2)} for t, g in a.groupby("unit_type")}

# ---------- 7. safety & persistence (predictability) ----------
el_s = el.sort_values(["unit_id", "period_start"]).copy()
grp = el_s.groupby("unit_id")
el_s["entrap_next"] = grp.entrapments.shift(-1)
el_s["unsched_next"] = grp.outages_unscheduled.shift(-1)
el_s["entrap_prev3"] = grp.entrapments.transform(lambda s: s.rolling(3, min_periods=1).sum())
nx = el_s.dropna(subset=["entrap_next"])
base = (nx.entrap_next > 0).mean()
R["elevator_entrapment_persistence"] = {
    "P(entrapment next month)": round(base * 100, 2),
    "P(next | entrapment this month)": round((nx[nx.entrapments > 0].entrap_next > 0).mean() * 100, 2),
    "P(next | none this month)": round((nx[nx.entrapments == 0].entrap_next > 0).mean() * 100, 2),
    "P(next | >=2 in last 3 months)": round((nx[nx.entrap_prev3 >= 2].entrap_next > 0).mean() * 100, 2),
    "corr(unscheduled, entrapments) same month": round(el.outages_unscheduled.corr(el.entrapments), 3),
    "lag1 autocorr unscheduled (pooled)": round(nx.outages_unscheduled.corr(nx.unsched_next), 3),
}
q = pd.qcut(nx.outages_unscheduled.rank(method="first"), 5, labels=["Q1 low", "Q2", "Q3", "Q4", "Q5 high"])
lift = nx.groupby(q, observed=True).apply(lambda g: (g.entrap_next > 0).mean() * 100).round(2)
R["elevator_P(entrapment next month) by unscheduled-outage quintile this month"] = lift.to_dict()
save(px.bar(lift.reset_index(name="pct"), x="outages_unscheduled", y="pct",
            title="Elevators: % with an entrapment next month, by this month's unscheduled-outage quintile"),
     "entrapment_lift")

(OUT / "eda_results.json").write_text(json.dumps(R, indent=2, default=str))
print(json.dumps(R, indent=2, default=str))
