from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

from app.core.config import settings
from app.data.storage import append_records, load_dataframe
from app.services.api_client import fetch_idoc_feed
from app.services.parser import parse_atom_xml

logger = logging.getLogger(__name__)


class IngestionService:
    async def pull_and_store(self) -> dict:
        payload = await fetch_idoc_feed()
        records = parse_atom_xml(payload)
        inserted = append_records(settings.raw_data_csv, records)

        raw_df = load_dataframe(settings.raw_data_csv)
        processed_df = self._build_processed(raw_df)
        processed_df.to_csv(settings.processed_data_csv, index=False)

        return {
            "fetched_records": len(records),
            "inserted_records": inserted,
            "processed_rows": len(processed_df),
            "updated_at": datetime.utcnow().isoformat(),
        }

    def _build_processed(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        if raw_df.empty:
            return raw_df

        df = raw_df.copy()
        df["entry_updated_at"] = pd.to_datetime(df["entry_updated_at"], errors="coerce", utc=True)
        df["ingested_at"] = pd.to_datetime(df["ingested_at"], errors="coerce", utc=True)

        df["event_ts"] = df["entry_updated_at"].fillna(df["ingested_at"])
        df["event_hour"] = df["event_ts"].dt.hour.fillna(0).astype(int)
        df["event_day"] = df["event_ts"].dt.day.fillna(1).astype(int)
        df["event_weekday"] = df["event_ts"].dt.weekday.fillna(0).astype(int)
        df["event_month"] = df["event_ts"].dt.month.fillna(1).astype(int)

        numeric_cols = ["process_time", "total_count", "success_count", "failure_count"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        df["is_failure"] = (df["status_code"].astype(str) != "53").astype(int)
        df["status_text_clean"] = (
            df["status_text"].fillna("").astype(str).str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
        )

        return df.sort_values("event_ts")
