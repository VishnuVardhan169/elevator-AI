# Elevator AI POC

AI alerting + failure prediction dashboard for an elevator fleet. Historical-data POC built on Kaggle datasets.

## Environment
- The agent shell is WSL bash (repo at `/mnt/d/Eleveator`). Use the venv: `.venv/bin/python`, `.venv/bin/streamlit`.
- `.env` holds `kaggle=<KGAT token>`; scripts export it as `KAGGLE_API_TOKEN`. Never print it.
- The agent shell tool strips `$var` inside inline `for` loops; put loops in a script file instead.

## Commands
- Setup: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
- Download data (~1.4 GB, into `data/raw/`): `bash scripts/download_data.sh`
- Build everything (≈2 min, writes `data/processed/`): `.venv/bin/python -m elevator_ai.pipeline`
- Dashboard: `.venv/bin/streamlit run app/dashboard.py` → http://localhost:8501
- Smoke test dashboard headless:
  `.venv/bin/python -c "from streamlit.testing.v1 import AppTest; at=AppTest.from_file('app/dashboard.py', default_timeout=300).run(); print(at.exception)"`

## Layout
- `elevator_ai/config.py` – paths, dataset→elevator mappings, alert percentiles/probability levels
- `elevator_ai/fleet.py` – merges Azure PdM (backbone), elevator PdM (door sensor), AI4I (drive/load), into a 100-elevator fleet
- `elevator_ai/sound.py` – MIMII spectral features + IsolationForest anomaly score
- `elevator_ai/model.py` – per-component 24h failure classifiers (train < 2015-09-01, test after)
- `elevator_ai/alerts.py` – leveled alerts (PRELIMINARY/WARNING/LEVEL_3/EMERGENCY)
- `data/fault_fix_lookup.csv` – fixed fault code → fix steps / parts / repair hours
- `app/dashboard.py` – Streamlit UI

## Data analysis team (agents + skills)
- Agents (`.devin/agents/`): `data-analyst` (EDA, cleaning, KPIs, reports), `data-scientist` (models, validation,
  thresholds, model cards), `data-auditor` (read-only: provenance, licence, real-vs-synthetic, leakage review).
- Skills (`.devin/skills/`): `/analyze-dataset` (end-to-end orchestrator), `/elevator-data-intake`,
  `/data-audit`, `/data-profile`, `/eda-report`, `/reliability-kpis`, `/alert-thresholds`, `/model-experiment`.
- Toolkit `analytics/`: `python -m analytics.profile|synthetic_check|reliability|validation <file> ...`
- Registry `data/catalog.yaml`; canonical schema `.devin/skills/elevator-data-intake/canonical_schema.md`.
- Folder conventions: raw (never edit) `data/raw/<id>/` → curated `data/curated/<id>/*.parquet`
  (via `scripts/curate/<id>.py`); analysis scripts `scripts/analysis/<id>/`; reports `reports/<id>/`;
  experiments `experiments/<name>/` (run.py, metrics.json, MODEL_CARD.md).
- The shell tool strips `$` — URL-encode SoQL params (`%24limit`) and avoid inline `for` loops.
