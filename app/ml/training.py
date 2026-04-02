from __future__ import annotations

import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression

from app.core.config import settings
from app.data.storage import append_training_registry, load_dataframe, load_training_registry
from app.ml.features import fit_transform_features, save_scaler


class TrainingService:
    def __init__(self) -> None:
        settings.model_dir.mkdir(parents=True, exist_ok=True)

    def train_monthly(self) -> Dict[str, Any]:
        df = load_dataframe(settings.processed_data_csv)
        if df.empty or len(df) < settings.min_training_rows:
            return {
                "status": "skipped",
                "reason": f"Not enough data. Need >= {settings.min_training_rows} rows",
                "rows": len(df),
            }

        run_id = str(uuid4())
        run_tag = datetime.now(timezone.utc).strftime("%Y%m")
        started = datetime.now(timezone.utc)

        preprocessor, x = fit_transform_features(df)
        scaler_path = save_scaler(preprocessor, run_tag)

        model_paths: Dict[str, str] = {}
        metrics: Dict[str, float] = {}

        anomaly = IsolationForest(random_state=42, contamination=0.05)
        anomaly.fit(x)
        anomaly_path = self._save_model("anomaly_detection", anomaly, run_tag)
        model_paths["anomaly_detection"] = str(anomaly_path)
        metrics["anomaly_samples"] = float(len(df))

        root_cause = KMeans(n_clusters=min(8, max(2, len(df) // 50)), random_state=42, n_init=10)
        root_cause.fit(x)
        root_cause_path = self._save_model("root_cause_clustering", root_cause, run_tag)
        model_paths["root_cause_clustering"] = str(root_cause_path)
        metrics["root_cause_inertia"] = float(root_cause.inertia_)

        volume_model, volume_score = self._train_volume_model(df)
        volume_path = self._save_model("volume_forecast", volume_model, run_tag)
        model_paths["volume_forecast"] = str(volume_path)
        metrics["volume_r2"] = volume_score

        partner_health = self._train_partner_health(df)
        partner_health_path = self._save_model("partner_health", partner_health, run_tag)
        model_paths["partner_health"] = str(partner_health_path)

        dynamic_error = KMeans(n_clusters=min(6, max(2, len(df) // 70)), random_state=42, n_init=10)
        dynamic_error.fit(x)
        dynamic_error_path = self._save_model("dynamic_error_clustering", dynamic_error, run_tag)
        model_paths["dynamic_error_clustering"] = str(dynamic_error_path)

        threshold_model = self._train_adaptive_threshold(df)
        threshold_path = self._save_model("adaptive_thresholding", threshold_model, run_tag)
        model_paths["adaptive_thresholding"] = str(threshold_path)

        partner_behavior = self._train_partner_behavior(df)
        partner_behavior_path = self._save_model("partner_behavior", partner_behavior, run_tag)
        model_paths["partner_behavior"] = str(partner_behavior_path)

        capacity_model, capacity_score = self._train_capacity_model(df)
        capacity_path = self._save_model("capacity_planning", capacity_model, run_tag)
        model_paths["capacity_planning"] = str(capacity_path)
        metrics["capacity_r2"] = capacity_score

        finished = datetime.now(timezone.utc)
        duration_seconds = (finished - started).total_seconds()

        run_record = {
            "run_id": run_id,
            "run_tag": run_tag,
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "duration_seconds": duration_seconds,
            "status": "success",
            "dataset_rows": int(len(df)),
            "scaler_path": str(scaler_path),
            "model_paths": model_paths,
            "metrics": metrics,
        }
        append_training_registry(run_record)
        return run_record

    def latest_training_month(self) -> str | None:
        registry = load_training_registry().get("runs", [])
        successful = [r for r in registry if r.get("status") == "success"]
        if not successful:
            return None
        successful = sorted(successful, key=lambda r: r.get("finished_at", ""), reverse=True)
        return successful[0].get("run_tag")

    def _save_model(self, model_name: str, model: Any, run_tag: str) -> Path:
        path = settings.model_dir / f"{model_name}_{run_tag}.pkl"
        with path.open("wb") as fp:
            pickle.dump(model, fp)
        return path

    def _train_volume_model(self, df: pd.DataFrame) -> tuple[LinearRegression, float]:
        hourly = (
            pd.to_datetime(df["event_ts"], errors="coerce", utc=True)
            .dt.floor("h")
            .value_counts()
            .rename_axis("bucket")
            .reset_index(name="volume")
            .sort_values("bucket")
        )
        hourly["t"] = np.arange(len(hourly))

        model = LinearRegression()
        model.fit(hourly[["t"]], hourly["volume"])
        score = model.score(hourly[["t"]], hourly["volume"])
        return model, float(score)

    def _train_partner_health(self, df: pd.DataFrame) -> Dict[str, Any]:
        grouped = (
            df.groupby("receiver")
            .agg(
                failure_rate=("is_failure", "mean"),
                avg_process_time=("process_time", "mean"),
                volume=("idoc_no", "count"),
            )
            .reset_index()
        )
        grouped["health_score"] = (
            100
            - (grouped["failure_rate"] * 50)
            - (grouped["avg_process_time"] * 10)
            - (grouped["volume"] / max(grouped["volume"].max(), 1) * 5)
        ).clip(lower=0, upper=100)
        return {"rows": grouped.to_dict(orient="records")}

    def _train_adaptive_threshold(self, df: pd.DataFrame) -> Dict[str, Any]:
        hourly = (
            df.assign(bucket=pd.to_datetime(df["event_ts"], errors="coerce", utc=True).dt.floor("h"))
            .groupby("bucket")
            .agg(failure_rate=("is_failure", "mean"), volume=("idoc_no", "count"))
            .reset_index()
        )
        return {
            "failure_rate_mean": float(hourly["failure_rate"].mean()),
            "failure_rate_std": float(hourly["failure_rate"].std(ddof=0) if len(hourly) > 1 else 0.0),
            "volume_mean": float(hourly["volume"].mean()),
            "volume_std": float(hourly["volume"].std(ddof=0) if len(hourly) > 1 else 0.0),
        }

    def _train_partner_behavior(self, df: pd.DataFrame) -> Dict[str, Any]:
        profile = (
            df.groupby("receiver")
            .agg(
                avg_hourly_volume=("idoc_no", "count"),
                failure_rate=("is_failure", "mean"),
                avg_process_time=("process_time", "mean"),
            )
            .reset_index()
        )
        return {"rows": profile.to_dict(orient="records")}

    def _train_capacity_model(self, df: pd.DataFrame) -> tuple[LinearRegression, float]:
        daily = (
            pd.to_datetime(df["event_ts"], errors="coerce", utc=True)
            .dt.date
            .value_counts()
            .rename_axis("date")
            .reset_index(name="volume")
            .sort_values("date")
        )
        daily["t"] = np.arange(len(daily))

        model = LinearRegression()
        model.fit(daily[["t"]], daily["volume"])
        score = model.score(daily[["t"]], daily["volume"])
        return model, float(score)
