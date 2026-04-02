from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "idoc-ml-insights")
    app_env: str = os.getenv("APP_ENV", "dev")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    idoc_api_url: str = os.getenv("IDOC_API_URL", os.getenv("SAP_URL", ""))
    idoc_api_username: str = os.getenv("IDOC_API_USERNAME", os.getenv("SAP_USER", ""))
    idoc_api_password: str = os.getenv("IDOC_API_PASSWORD", os.getenv("SAP_PASS", ""))
    idoc_origin_header: str = os.getenv("IDOC_ORIGIN_HEADER", os.getenv("SAP_ORIGIN", "*"))
    verify_tls: bool = _env_bool("VERIFY_TLS", _env_bool("SAP_VERIFY_TLS", True))
    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))

    fetch_interval_minutes: int = int(os.getenv("FETCH_INTERVAL_MINUTES", "15"))
    min_training_rows: int = int(os.getenv("MIN_TRAINING_ROWS", "300"))

    base_dir: Path = Path(os.getenv("BASE_DIR", Path.cwd()))

    @property
    def raw_data_csv(self) -> Path:
        return self.base_dir / "data" / "raw" / "idoc_raw.csv"

    @property
    def processed_data_csv(self) -> Path:
        return self.base_dir / "data" / "processed" / "idoc_processed.csv"

    @property
    def training_registry_json(self) -> Path:
        return self.base_dir / "artifacts" / "metadata" / "training_registry.json"

    @property
    def model_dir(self) -> Path:
        return self.base_dir / "artifacts" / "models"

    @property
    def scaler_dir(self) -> Path:
        return self.base_dir / "artifacts" / "scalers"


settings = Settings()
