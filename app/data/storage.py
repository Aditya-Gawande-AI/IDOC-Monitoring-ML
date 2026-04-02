from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import pandas as pd

from app.core.config import settings


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def append_records(csv_path: Path, records: List[Dict[str, object]], unique_key: str = "event_hash") -> int:
    if not records:
        return 0

    _ensure_parent(csv_path)
    new_df = pd.DataFrame(records)

    if csv_path.exists():
        old_df = pd.read_csv(csv_path)
        combined = pd.concat([old_df, new_df], ignore_index=True)
        before = len(combined)
        combined = combined.drop_duplicates(subset=[unique_key], keep="first")
        inserted = len(combined) - len(old_df)
        if inserted <= 0:
            return 0
        combined.to_csv(csv_path, index=False)
        return inserted

    new_df = new_df.drop_duplicates(subset=[unique_key], keep="first")
    new_df.to_csv(csv_path, index=False)
    return len(new_df)


def load_dataframe(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        return pd.DataFrame()
    return pd.read_csv(csv_path)


def append_training_registry(record: Dict[str, object]) -> None:
    path = settings.training_registry_json
    _ensure_parent(path)

    if not path.exists():
        with path.open("w", encoding="utf-8") as fp:
            json.dump({"runs": [record]}, fp, indent=2)
        return

    with path.open("r", encoding="utf-8") as fp:
        current = json.load(fp)

    current.setdefault("runs", []).append(record)

    with path.open("w", encoding="utf-8") as fp:
        json.dump(current, fp, indent=2)


def load_training_registry() -> Dict[str, object]:
    path = settings.training_registry_json
    if not path.exists():
        return {"runs": []}
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)
