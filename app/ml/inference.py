from __future__ import annotations

import pickle
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Literal

import numpy as np
import pandas as pd

from app.core.config import settings
from app.data.storage import load_dataframe, load_training_registry
from app.ml.features import load_latest_scaler, transform_features

INSIGHT_KEYS = [
    "anomaly_detection",
    "root_cause_clustering",
    "volume_forecast",
    "partner_health",
    "dynamic_error_clustering",
    "adaptive_thresholding",
    "partner_behavior",
    "capacity_planning",
]


class InferenceService:
    def __init__(self) -> None:
        self._cache: Dict[str, Any] = {}

    def _latest_model_path(self, model_name: str) -> Path | None:
        candidates = sorted(settings.model_dir.glob(f"{model_name}_*.pkl"), reverse=True)
        return candidates[0] if candidates else None

    def _load_model(self, model_name: str) -> Any | None:
        if model_name in self._cache:
            return self._cache[model_name]
        path = self._latest_model_path(model_name)
        if path is None:
            return None
        with path.open("rb") as fp:
            model = pickle.load(fp)
        self._cache[model_name] = model
        return model

    def _latest_metadata(self) -> Dict[str, Any]:
        runs = load_training_registry().get("runs", [])
        successful = [r for r in runs if r.get("status") == "success"]
        if not successful:
            return {"model_ready": False, "latest_run_tag": None}
        latest = sorted(successful, key=lambda x: x.get("finished_at", ""), reverse=True)[0]
        return {"model_ready": True, "latest_run_tag": latest.get("run_tag"), "latest_run": latest}

    def _base_response(self, insight: str) -> Dict[str, Any]:
        meta = self._latest_metadata()
        return {
            "insight": insight,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model_ready": meta["model_ready"],
            "model_version": meta.get("latest_run_tag"),
        }

    @staticmethod
    def _horizon_hours(period: Literal["hour", "day", "week", "month"]) -> int:
        if period == "hour":
            return 1
        if period == "day":
            return 24
        if period == "week":
            return 24 * 7
        return 24 * 30

    @staticmethod
    def _parse_target_datetime(target_datetime: str | None) -> datetime | None:
        if not target_datetime:
            return None
        parsed = pd.to_datetime(target_datetime, errors="coerce", utc=True)
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime()

    @staticmethod
    def _error_distribution(df: pd.DataFrame) -> pd.DataFrame:
        if "status_text" in df.columns:
            error_col = "status_text"
        elif "status_text_clean" in df.columns:
            error_col = "status_text_clean"
        else:
            return pd.DataFrame([{"error_name": "UNKNOWN_ERROR", "historical_count": len(df), "historical_share": 1.0}])

        errors = df[error_col].fillna("").astype(str).str.strip()
        errors = errors.where(errors != "", "UNKNOWN_ERROR")
        counts = errors.value_counts(dropna=False)
        total = max(int(counts.sum()), 1)

        return pd.DataFrame(
            {
                "error_name": counts.index,
                "historical_count": counts.values.astype(int),
                "historical_share": (counts.values / total).astype(float),
            }
        )

    @staticmethod
    def _forecast_by_error_type(distribution: pd.DataFrame, predicted_volume: float) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for row in distribution.itertuples(index=False):
            per_error_volume = float(max(predicted_volume, 0.0) * float(row.historical_share))
            output.append(
                {
                    "error_name": row.error_name,
                    "historical_count": int(row.historical_count),
                    "historical_share": float(row.historical_share),
                    "predicted_volume": per_error_volume,
                }
            )

        output.sort(key=lambda x: x["predicted_volume"], reverse=True)
        return output

    def anomaly_detection(self) -> Dict[str, Any]:
        base = self._base_response("anomaly_detection")
        df = load_dataframe(settings.processed_data_csv)
        if df.empty:
            return {**base, "status": "no_data"}

        model = self._load_model("anomaly_detection")
        scaler = load_latest_scaler()
        if model is None or scaler is None:
            return {
                **base,
                "status": "cold_start",
                "anomaly_ratio_overall": None,
                "anomaly_by_error_type": [],
                "message": "Model or scaler not available yet",
            }

        x = transform_features(scaler, df)
        preds = model.predict(x)
        is_anomaly = pd.Series(preds == -1)
        anomaly_ratio = float(is_anomaly.mean())

        error_col = "status_text" if "status_text" in df.columns else "status_text_clean"
        errors = df[error_col].fillna("").astype(str).str.strip()
        errors = errors.where(errors != "", "UNKNOWN_ERROR")

        anomaly_df = pd.DataFrame({"error_name": errors, "is_anomaly": is_anomaly.astype(int)})
        grouped = (
            anomaly_df.groupby("error_name", dropna=False)
            .agg(total_records=("is_anomaly", "count"), anomaly_count=("is_anomaly", "sum"))
            .reset_index()
        )
        grouped["anomaly_ratio"] = grouped["anomaly_count"] / grouped["total_records"]
        grouped = grouped.sort_values(["anomaly_ratio", "anomaly_count", "total_records"], ascending=False)

        return {
            **base,
            "status": "ok",
            "anomaly_ratio": anomaly_ratio,
            "anomaly_ratio_overall": anomaly_ratio,
            "anomaly_by_error_type": [
                {
                    "error_name": row.error_name,
                    "total_records": int(row.total_records),
                    "anomaly_count": int(row.anomaly_count),
                    "anomaly_ratio": float(row.anomaly_ratio),
                }
                for row in grouped.itertuples(index=False)
            ],
        }

    def root_cause_clustering(self) -> Dict[str, Any]:
        base = self._base_response("root_cause_clustering")
        df = load_dataframe(settings.processed_data_csv)
        if df.empty:
            return {**base, "status": "no_data"}

        model = self._load_model("root_cause_clustering")
        scaler = load_latest_scaler()
        if model is None or scaler is None:
            top_errors = df["status_text_clean"].fillna("").value_counts().head(5).to_dict()
            return {**base, "status": "cold_start", "top_error_patterns": top_errors}

        x = transform_features(scaler, df)
        labels = model.predict(x)
        label_counts = pd.Series(labels).value_counts().to_dict()
        return {**base, "status": "ok", "clusters": label_counts}

    def volume_forecast(
        self,
        period: Literal["hour", "day", "week", "month"] = "hour",
        target_datetime: str | None = None,
    ) -> Dict[str, Any]:
        base = self._base_response("volume_forecast")
        df = load_dataframe(settings.processed_data_csv)
        if df.empty:
            return {**base, "status": "no_data"}

        model = self._load_model("volume_forecast")
        hourly = (
            pd.to_datetime(df["event_ts"], errors="coerce", utc=True)
            .dt.floor("h")
            .value_counts()
            .sort_index()
        )
        if len(hourly) == 0:
            return {**base, "status": "no_data"}

        distribution = self._error_distribution(df)

        last_observed_hour_ts = pd.Timestamp(hourly.index.max())
        if last_observed_hour_ts.tzinfo is None:
            last_observed_hour_ts = last_observed_hour_ts.tz_localize("UTC")
        else:
            last_observed_hour_ts = last_observed_hour_ts.tz_convert("UTC")
        last_observed_hour = last_observed_hour_ts.to_pydatetime()
        target_dt = self._parse_target_datetime(target_datetime)
        if target_datetime and target_dt is None:
            return {
                **base,
                "status": "invalid_input",
                "message": "target_datetime must be a valid ISO datetime string",
            }

        if target_dt is None:
            forecast_start = last_observed_hour + timedelta(hours=1)
        else:
            forecast_start = target_dt.replace(minute=0, second=0, microsecond=0)

        delta_hours = int((forecast_start - last_observed_hour).total_seconds() // 3600)
        if delta_hours < 1:
            return {
                **base,
                "status": "invalid_input",
                "message": "target_datetime must be in the future relative to latest observed data",
                "latest_observed_hour": last_observed_hour.isoformat(),
            }

        horizon_hours = self._horizon_hours(period)
        forecast_end = forecast_start + timedelta(hours=horizon_hours)

        if model is None:
            predicted_volume = float(hourly.mean() * horizon_hours)
            return {
                **base,
                "status": "cold_start",
                "requested_period": period,
                "forecast_start": forecast_start.isoformat(),
                "forecast_end": forecast_end.isoformat(),
                "predicted_volume": predicted_volume,
                "forecast_by_error_type": self._forecast_by_error_type(distribution, predicted_volume),
            }

        start_index = (len(hourly) - 1) + delta_hours
        forecast_indices = np.arange(start_index, start_index + horizon_hours).reshape(-1, 1)
        predictions = model.predict(forecast_indices)
        predictions = np.maximum(predictions, 0.0)

        predicted_volume = float(np.sum(predictions))
        response = {
            **base,
            "status": "ok",
            "requested_period": period,
            "forecast_start": forecast_start.isoformat(),
            "forecast_end": forecast_end.isoformat(),
            "predicted_volume": predicted_volume,
            "forecast_by_error_type": self._forecast_by_error_type(distribution, predicted_volume),
        }

        if period == "hour":
            response["next_hour_volume"] = predicted_volume

        return response

    def partner_health(self) -> Dict[str, Any]:
        base = self._base_response("partner_health")
        model = self._load_model("partner_health")
        if model is None:
            df = load_dataframe(settings.processed_data_csv)
            if df.empty:
                return {**base, "status": "no_data"}
            grouped = (
                df.groupby("receiver")
                .agg(failure_rate=("is_failure", "mean"), avg_process_time=("process_time", "mean"), volume=("idoc_no", "count"))
                .reset_index()
            )
            return {**base, "status": "cold_start", "partners": grouped.to_dict(orient="records")}

        return {**base, "status": "ok", "partners": model.get("rows", [])}

    def dynamic_error_clustering(self) -> Dict[str, Any]:
        base = self._base_response("dynamic_error_clustering")
        df = load_dataframe(settings.processed_data_csv)
        if df.empty:
            return {**base, "status": "no_data"}

        error_col = "status_text" if "status_text" in df.columns else "status_text_clean"
        errors = df[error_col].fillna("").astype(str).str.strip()
        errors = errors.where(errors != "", "UNKNOWN_ERROR")

        counts = errors.value_counts(dropna=False)
        error_clusters = [
            {"error_name": error_name, "count": int(count)}
            for error_name, count in counts.items()
        ]

        return {
            **base,
            "status": "ok",
            "cluster_strategy": "one_cluster_per_unique_error",
            "total_error_types": int(len(error_clusters)),
            "error_clusters": error_clusters,
        }

    def adaptive_thresholding(self) -> Dict[str, Any]:
        base = self._base_response("adaptive_thresholding")
        model = self._load_model("adaptive_thresholding")
        df = load_dataframe(settings.processed_data_csv)
        if df.empty:
            return {**base, "status": "no_data"}

        current_failure_rate = float(df["is_failure"].mean())
        if model is None:
            return {**base, "status": "cold_start", "current_failure_rate": current_failure_rate}

        threshold = float(model["failure_rate_mean"] + 2 * model["failure_rate_std"])
        return {
            **base,
            "status": "ok",
            "current_failure_rate": current_failure_rate,
            "adaptive_threshold": threshold,
            "breach": current_failure_rate > threshold,
        }

    def partner_behavior(self) -> Dict[str, Any]:
        base = self._base_response("partner_behavior")
        model = self._load_model("partner_behavior")
        if model is None:
            df = load_dataframe(settings.processed_data_csv)
            if df.empty:
                return {**base, "status": "no_data"}
            return {**base, "status": "cold_start", "partner_behavior": []}
        return {**base, "status": "ok", "partner_behavior": model.get("rows", [])}

    def capacity_planning(self) -> Dict[str, Any]:
        base = self._base_response("capacity_planning")
        df = load_dataframe(settings.processed_data_csv)
        if df.empty:
            return {**base, "status": "no_data"}

        model = self._load_model("capacity_planning")
        daily = (
            pd.to_datetime(df["event_ts"], errors="coerce", utc=True)
            .dt.date
            .value_counts()
            .sort_index()
        )
        if len(daily) == 0:
            return {**base, "status": "no_data"}

        if model is None:
            return {**base, "status": "cold_start", "next_day_capacity": float(daily.mean())}

        t_next = np.array([[len(daily)]])
        pred = float(model.predict(t_next)[0])
        return {**base, "status": "ok", "next_day_capacity": max(0.0, pred)}
