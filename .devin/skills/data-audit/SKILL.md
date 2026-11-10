---
name: data-audit
description: Independent audit of an elevator dataset or analysis artifact - provenance, licence, real-vs-synthetic verdict, data quality and fitness for the canonical schema (or leakage/overclaiming review of a report or model).
argument-hint: "<dataset_id | file path | report/model path>"
agent: data-auditor
---

Audit the dataset or artifact named in the user's request.

1. Resolve it: if it is a dataset id, read its entry in `data/catalog.yaml` and list the files in `data/raw/<id>/`.
   If it is a report or model card, read it and the code it references.
2. For datasets, run on each main table (sample with `--nrows 200000` if large):
   - `.venv/bin/python -m analytics.synthetic_check <file> [--label <rare label cols>] [--time-col C] [--id-col C]`
   - `.venv/bin/python -m analytics.profile <file> --json --nrows 200000`
   Then check provenance and licence on the web (original publisher, paper/DOI, whether it is a re-upload or a
   remix of AI4I 2020 / Azure PdM / Huawei door data).
3. For reports/models, apply the review checklist in your instructions (denominators, leakage, baselines,
   metric choice, AUC > 0.98, synthetic caveats, conclusions vs numbers).
4. Return the structured verdict block, including the recommended `data/catalog.yaml` update.
