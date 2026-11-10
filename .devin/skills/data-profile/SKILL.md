---
name: data-profile
description: Profile an elevator dataset - schema, nulls, duplicates, distributions, outliers, redundant columns, time coverage and per-unit structure - and write reports/<dataset_id>/profile.md with interpretation.
argument-hint: "<dataset_id | file path>"
agent: data-analyst
---

Profile the dataset named in the user's request.

1. Resolve files: a dataset id maps to `data/raw/<id>/` (and `data/curated/<id>/` if present). Identify the main
   tables; skip images/audio (just count files, sizes, formats, sample rates).
2. For each table run:
   `.venv/bin/python -m analytics.profile <file> [--time-col C] [--id-col C] --out reports/<id>/profile_<table>.md`
   Detect the time and unit-id columns yourself and pass them. Use `--nrows` only if the file is > 2 GB, and say so.
3. Go beyond the tool output with targeted checks you script yourself:
   - per-unit time coverage and gaps; sampling frequency consistency
   - value ranges vs physical plausibility (e.g. elevator speed 0-10 m/s, availability 0-100%, temps -20-80 C)
   - categorical code inventories (error codes, components, outage reasons) with counts
   - label balance for any failure / fault / outage columns
4. Write `reports/<id>/profile.md`: a short interpreted summary on top (what the data is, how clean it is,
   what it can support), then links to the per-table profiles, then a list of data-quality issues with severity
   and a suggested fix for each.
5. Return the report path and the top issues.
