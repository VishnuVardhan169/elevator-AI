---
name: elevator-data-intake
description: Onboard a newly procured elevator dataset (Kaggle ref, URL, open-data API or local file) - register in the catalog, download to data/raw, audit authenticity/licence, profile it and map it to the canonical elevator schema.
argument-hint: "<kaggle ref | URL | local path> [dataset_id]"
allowed-tools:
  - read
  - grep
  - glob
---

Onboard the dataset the user specified with this command. Work through these steps in order and keep the user
informed after each one.

## 1. Identify and register
- Choose a short snake_case `dataset_id` (or use the one given).
- Read `data/catalog.yaml`. If the dataset is already listed, update that entry instead of adding a duplicate.
- Add/update the entry with: id, title, source, license (unknown until verified), authenticity: unknown,
  status: candidate.

## 2. Download (never overwrite existing raw data)
- Target folder: `data/raw/<dataset_id>/`. If it already contains files, stop and ask before replacing.
- Kaggle: `export KAGGLE_API_TOKEN="$(grep -i '^kaggle=' .env | cut -d= -f2- | tr -d '\r')" && .venv/bin/kaggle datasets download -d <ref> -p data/raw/<dataset_id> --unzip -q`
  (never print the token).
- Socrata open data (data.ny.gov, data.cityofnewyork.us): `curl -L "<domain>/api/views/<4x4>/rows.csv?accessType=DOWNLOAD" -o data/raw/<id>/<name>.csv`.
  Note: the shell tool strips `$` — URL-encode SoQL params (`%24limit`).
- Direct URLs (figshare/zenodo): `curl -L <url> -o data/raw/<id>/<file>`.
- Warn the user and confirm before downloads larger than ~2 GB. Record file names and sizes.
- Set catalog status: downloaded.

## 3. Audit (delegate)
Run the `/data-audit` skill on the new files. Copy its authenticity, licence and evidence into the catalog entry.
If the verdict is REJECTED, set status: rejected, tell the user why, and stop.

## 4. Profile (delegate)
Run the `/data-profile` skill. It writes `reports/<dataset_id>/profile.md`. Set catalog status: profiled.

## 5. Map to the canonical schema
- Read `.devin/skills/elevator-data-intake/canonical_schema.md`.
- Propose a column mapping table (source column -> canonical table.column, unit conversion) and show it to the
  user for confirmation.
- Write `scripts/curate/<dataset_id>.py` that reads `data/raw/<dataset_id>/`, applies the mapping and writes
  `data/curated/<dataset_id>/<table>.parquet`. Run it and report row counts per table.
- Set catalog `canonical_tables` and status: curated.

## 6. Summarise
Tell the user: what the dataset is, authenticity + licence, which canonical tables it fills, join keys to other
datasets in the catalog, the 3 most important data-quality issues, and which questions it can answer
(suggest `/eda-report`, `/reliability-kpis`, `/model-experiment` as next steps).
