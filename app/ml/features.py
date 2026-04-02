from __future__ import annotations

from pathlib import Path
from typing import List, Tuple
import pickle

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.core.config import settings

NUMERIC_COLS = ["process_time", "total_count", "success_count", "failure_count", "event_hour", "event_day", "event_weekday"]
CATEGORICAL_COLS = ["message_type", "idoc_type", "sender", "receiver", "status_code", "direction"]
TEXT_COL = "status_text_clean"


def _build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_COLS),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_COLS),
            ("txt", TfidfVectorizer(max_features=200), TEXT_COL),
        ]
    )


def fit_transform_features(df: pd.DataFrame) -> Tuple[ColumnTransformer, object]:
    feature_df = df[NUMERIC_COLS + CATEGORICAL_COLS + [TEXT_COL]].fillna("")
    preprocessor = _build_preprocessor()
    x = preprocessor.fit_transform(feature_df)
    return preprocessor, x


def transform_features(preprocessor: ColumnTransformer, df: pd.DataFrame) -> object:
    feature_df = df[NUMERIC_COLS + CATEGORICAL_COLS + [TEXT_COL]].fillna("")
    return preprocessor.transform(feature_df)


def save_scaler(preprocessor: ColumnTransformer, run_tag: str) -> Path:
    settings.scaler_dir.mkdir(parents=True, exist_ok=True)
    path = settings.scaler_dir / f"preprocessor_{run_tag}.pkl"
    with path.open("wb") as fp:
        pickle.dump(preprocessor, fp)
    return path


def load_latest_scaler() -> ColumnTransformer | None:
    settings.scaler_dir.mkdir(parents=True, exist_ok=True)
    candidates: List[Path] = sorted(settings.scaler_dir.glob("preprocessor_*.pkl"), reverse=True)
    if not candidates:
        return None

    with candidates[0].open("rb") as fp:
        return pickle.load(fp)
