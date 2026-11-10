---
name: analyze-dataset
description: End-to-end analysis of a procured elevator dataset - audit, profile, EDA, reliability KPIs and (if labels exist) a first model and alert thresholds - coordinated across the data-auditor, data-analyst and data-scientist agents, ending with a consolidated brief.
argument-hint: "<dataset_id | kaggle ref | URL>"
---

Run the full analysis workflow for the dataset in the user's request. You are the coordinator: delegate each step
to the skill named, wait for it, check its output, and only then continue.

1. **Intake** — if the dataset is not in `data/catalog.yaml` with status >= profiled, run `/elevator-data-intake`
   first. Otherwise read its catalog entry.
2. **Audit** — run `/data-audit <id>` unless the catalog already has an audit verdict. If REJECTED, stop and report.
3. **EDA** — run `/eda-report <id>`.
4. **Reliability** — if the data has failures/outages/availability, run `/reliability-kpis <id>`.
5. **Modelling** — if there is a usable label (failures, faults, outages) with enough positive examples
   (roughly >= 50) and a time axis, run `/model-experiment <id> <goal>` choosing the most valuable goal for an
   elevator maintenance team, then `/alert-thresholds` on the model score. Otherwise run `/alert-thresholds` on
   the key raw signals/KPIs.
6. **Review** — run `/data-audit` on the EDA report and the model card to catch leakage or overclaiming.
   Fix or caveat anything rated HIGH by re-delegating to the responsible skill.
7. **Brief** — write `reports/<id>/BRIEF.md` (max ~1 page): what the data is (authenticity, licence), 5 key
   findings with numbers, model performance vs baseline, recommended alert thresholds, limitations, and
   recommended next data to procure. Update the dataset's catalog status to `in_use` or `profiled`.
   Present the brief to the user.
