"""Reusable analysis toolkit used by the data-analyst / data-scientist / data-auditor agents."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def load_table(path: str | Path, nrows: int | None = None, **kw) -> pd.DataFrame:
    """Load csv / parquet / xlsx / json by extension."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".parquet":
        df = pd.read_parquet(p, **kw)
        return df.head(nrows) if nrows else df
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(p, nrows=nrows, **kw)
    if ext == ".json":
        return pd.read_json(p, **kw).head(nrows) if nrows else pd.read_json(p, **kw)
    return pd.read_csv(p, nrows=nrows, encoding_errors="replace", **kw)
