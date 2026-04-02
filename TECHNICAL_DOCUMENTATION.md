# Technical Documentation - IDoc ML Insight Service

## 1. System Overview
This is a FastAPI service that:
- Pulls SAP OData Atom XML payloads on schedule
- Parses and stores historical records into CSV layers
- Trains scikit-learn models monthly
- Serves inference outputs across 8 insight endpoints

## 2. Runtime and Entry Point
- Framework: FastAPI
- ASGI server: Uvicorn
- App module: `app.main:app`
- Scheduler lifecycle: started and stopped via FastAPI lifespan hooks

Run command:
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 3. Architecture Components
- `app/main.py`: app bootstrap and scheduler lifecycle
- `app/api/routes.py`: all route contracts
- `app/services/api_client.py`: SAP API fetch with credentials and timeout
- `app/services/parser.py`: Atom XML to normalized record fields
- `app/services/ingestion.py`: raw append + processed feature dataset build
- `app/data/storage.py`: CSV and training registry JSON persistence
- `app/ml/features.py`: preprocessing/scaler fit and transform
- `app/ml/training.py`: monthly training and artifact writing
- `app/ml/inference.py`: model loading, response shaping, fallback logic
- `app/jobs/scheduler.py`: 15-minute ingestion loop + monthly training check

## 4. Data Flow
1. Scheduler triggers ingestion every `FETCH_INTERVAL_MINUTES`.
2. Ingestion fetches SAP payload and parses records.
3. Raw records append into `data/raw/idoc_raw.csv` with event-hash dedupe.
4. Processed dataset rebuilds into `data/processed/idoc_processed.csv`.
5. Monthly training generates:
   - scaler artifact in `artifacts/scalers`
   - model artifacts in `artifacts/models`
   - run metadata in `artifacts/metadata/training_registry.json`
6. Inference endpoints load latest successful model artifacts and return insight payloads.

## 5. Configuration (Environment Variables)
From `app/core/config.py`:

- `APP_NAME` (default: `idoc-ml-insights`)
- `APP_ENV` (default: `dev`)
- `LOG_LEVEL` (default: `INFO`)
- `IDOC_API_URL` or fallback `SAP_URL`
- `IDOC_API_USERNAME` or fallback `SAP_USER`
- `IDOC_API_PASSWORD` or fallback `SAP_PASS`
- `IDOC_ORIGIN_HEADER` or fallback `SAP_ORIGIN`
- `VERIFY_TLS` or fallback `SAP_VERIFY_TLS` (boolean)
- `REQUEST_TIMEOUT_SECONDS` (default: `30`)
- `FETCH_INTERVAL_MINUTES` (default: `15`)
- `MIN_TRAINING_ROWS` (default: `300`)
- `BASE_DIR` (default: current working directory)

Derived paths:
- raw CSV: `data/raw/idoc_raw.csv`
- processed CSV: `data/processed/idoc_processed.csv`
- training registry: `artifacts/metadata/training_registry.json`
- models: `artifacts/models`
- scalers: `artifacts/scalers`

## 6. Scheduler and Training Behavior
- Ingestion loop interval: `max(60, FETCH_INTERVAL_MINUTES * 60)` seconds
- Monthly retrain trigger: compares latest successful `run_tag` with current UTC month (`YYYYMM`)
- Manual routes:
  - `GET /jobs/ingest`
  - `GET /jobs/train`

Training outcome status:
- `success`: artifacts and registry updated
- `skipped`: insufficient rows (`len(df) < MIN_TRAINING_ROWS`)

## 7. API Contracts

### 7.1 Operational Endpoints

#### `GET /health`
Request:
```http
GET /health
```
Response example:
```json
{
  "status": "ok"
}
```

#### `GET /jobs/ingest`
Request:
```http
GET /jobs/ingest
```
Response example:
```json
{
  "fetched_records": 991,
  "inserted_records": 991,
  "processed_rows": 26757,
  "updated_at": "2026-04-02T11:13:20.354878"
}
```

#### `GET /jobs/train`
Request:
```http
GET /jobs/train
```
Response example:
```json
{
  "run_id": "e394f58b-08b0-4cfe-8fff-655d5fe52a9b",
  "run_tag": "202604",
  "started_at": "2026-04-02T11:13:20.732749+00:00",
  "finished_at": "2026-04-02T11:13:31.341348+00:00",
  "duration_seconds": 10.608599,
  "status": "success",
  "dataset_rows": 26757,
  "scaler_path": ".../artifacts/scalers/preprocessor_202604.pkl",
  "model_paths": {
    "anomaly_detection": ".../artifacts/models/anomaly_detection_202604.pkl",
    "root_cause_clustering": ".../artifacts/models/root_cause_clustering_202604.pkl",
    "volume_forecast": ".../artifacts/models/volume_forecast_202604.pkl",
    "partner_health": ".../artifacts/models/partner_health_202604.pkl",
    "dynamic_error_clustering": ".../artifacts/models/dynamic_error_clustering_202604.pkl",
    "adaptive_thresholding": ".../artifacts/models/adaptive_thresholding_202604.pkl",
    "partner_behavior": ".../artifacts/models/partner_behavior_202604.pkl",
    "capacity_planning": ".../artifacts/models/capacity_planning_202604.pkl"
  },
  "metrics": {
    "anomaly_samples": 26757.0,
    "root_cause_inertia": 24363.12728597285,
    "volume_r2": 0.014705882352941346,
    "capacity_r2": null
  }
}
```

#### `GET /jobs/training-registry`
Request:
```http
GET /jobs/training-registry
```
Response example:
```json
{
  "runs": [
    {
      "run_id": "4bcf1d18-7a04-43d5-86e8-440e830feefb",
      "run_tag": "202604",
      "status": "success"
    },
    {
      "run_id": "e394f58b-08b0-4cfe-8fff-655d5fe52a9b",
      "run_tag": "202604",
      "status": "success"
    }
  ]
}
```

### 7.2 Insight Endpoints

All insight endpoints return common metadata keys:
- `insight`
- `generated_at`
- `model_ready`
- `model_version`
- `status`

#### `GET /insights/anomaly-detection`
Request:
```http
GET /insights/anomaly-detection
```
Response example:
```json
{
  "insight": "anomaly_detection",
  "generated_at": "2026-04-02T11:13:31.421973+00:00",
  "model_ready": true,
  "model_version": "202604",
  "status": "ok",
  "anomaly_ratio": 0.05953582240161453,
  "anomaly_ratio_overall": 0.05953582240161453,
  "anomaly_by_error_type": [
    {
      "error_name": "ISO unit of measure ...",
      "total_records": 567,
      "anomaly_count": 567,
      "anomaly_ratio": 1.0
    },
    {
      "error_name": "Could not find code page ...",
      "total_records": 810,
      "anomaly_count": 135,
      "anomaly_ratio": 0.16666666666666666
    }
  ]
}
```

#### `GET /insights/root-cause-clustering`
Request:
```http
GET /insights/root-cause-clustering
```
Response example:
```json
{
  "insight": "root_cause_clustering",
  "generated_at": "2026-04-02T11:13:33.233367+00:00",
  "model_ready": true,
  "model_version": "202604",
  "status": "ok",
  "clusters": {
    "0": 9855,
    "3": 7587,
    "2": 2592,
    "1": 1971,
    "4": 1620,
    "6": 1161,
    "5": 1134,
    "7": 837
  }
}
```

#### `GET /insights/volume-forecast`
Query params:
- `period` (required enum): `hour | day | week | month`
- `target_datetime` (optional ISO datetime string)

Requests:
```http
GET /insights/volume-forecast?period=hour
GET /insights/volume-forecast?period=week&target_datetime=2026-04-10T00:00:00Z
```

Response example (`period=hour`):
```json
{
  "insight": "volume_forecast",
  "generated_at": "2026-04-02T11:13:35.289499+00:00",
  "model_ready": true,
  "model_version": "202604",
  "status": "ok",
  "requested_period": "hour",
  "forecast_start": "2026-04-02T12:00:00+00:00",
  "forecast_end": "2026-04-02T13:00:00+00:00",
  "predicted_volume": 991.0,
  "forecast_by_error_type": [
    {
      "error_name": "Make an entry in field ...",
      "historical_count": 9477,
      "historical_share": 0.35418768920282545,
      "predicted_volume": 351.0
    },
    {
      "error_name": "Account category ...",
      "historical_count": 7533,
      "historical_share": 0.2815338042381433,
      "predicted_volume": 279.0
    }
  ],
  "next_hour_volume": 991.0
}
```

Response example (`period=week`):
```json
{
  "insight": "volume_forecast",
  "generated_at": "2026-04-02T11:13:35.982007+00:00",
  "model_ready": true,
  "model_version": "202604",
  "status": "ok",
  "requested_period": "week",
  "forecast_start": "2026-04-10T00:00:00+00:00",
  "forecast_end": "2026-04-17T00:00:00+00:00",
  "predicted_volume": 166488.0,
  "forecast_by_error_type": [
    {
      "error_name": "Make an entry in field ...",
      "historical_count": 9477,
      "historical_share": 0.35418768920282545,
      "predicted_volume": 58968.00000000001
    },
    {
      "error_name": "Account category ...",
      "historical_count": 7533,
      "historical_share": 0.2815338042381433,
      "predicted_volume": 46872.0
    }
  ]
}
```

#### `GET /insights/partner-health`
Request:
```http
GET /insights/partner-health
```
Response example:
```json
{
  "insight": "partner_health",
  "generated_at": "2026-04-02T11:13:36.761943+00:00",
  "model_ready": true,
  "model_version": "202604",
  "status": "ok",
  "partners": [
    {
      "receiver": "S89_200",
      "failure_rate": 1.0,
      "avg_process_time": 0.0,
      "volume": 724,
      "health_score": 45.0
    }
  ]
}
```

#### `GET /insights/dynamic-error-clustering`
Request:
```http
GET /insights/dynamic-error-clustering
```
Response example:
```json
{
  "insight": "dynamic_error_clustering",
  "generated_at": "2026-04-02T11:13:36.806061+00:00",
  "model_ready": true,
  "model_version": "202604",
  "status": "ok",
  "cluster_strategy": "one_cluster_per_unique_error",
  "total_error_types": 36,
  "error_clusters": [
    {
      "error_name": "Make an entry in field ...",
      "count": 9477
    },
    {
      "error_name": "Account category ...",
      "count": 7533
    }
  ]
}
```

#### `GET /insights/adaptive-thresholding`
Request:
```http
GET /insights/adaptive-thresholding
```
Response example:
```json
{
  "insight": "adaptive_thresholding",
  "generated_at": "2026-04-02T11:13:37.537042+00:00",
  "model_ready": true,
  "model_version": "202604",
  "status": "ok",
  "current_failure_rate": 1.0,
  "adaptive_threshold": 1.0,
  "breach": false
}
```

#### `GET /insights/partner-behavior`
Request:
```http
GET /insights/partner-behavior
```
Response example:
```json
{
  "insight": "partner_behavior",
  "generated_at": "2026-04-02T11:13:38.185639+00:00",
  "model_ready": true,
  "model_version": "202604",
  "status": "ok",
  "partner_behavior": [
    {
      "receiver": "S89_200",
      "avg_hourly_volume": 724,
      "failure_rate": 1.0,
      "avg_process_time": 0.0
    }
  ]
}
```

#### `GET /insights/capacity-planning`
Request:
```http
GET /insights/capacity-planning
```
Response example:
```json
{
  "insight": "capacity_planning",
  "generated_at": "2026-04-02T11:13:38.203373+00:00",
  "model_ready": true,
  "model_version": "202604",
  "status": "ok",
  "next_day_capacity": 991.0
}
```

## 8. Status Semantics
Inference statuses:
- `ok`: model and scaler available, normal inference path
- `cold_start`: model/scaler unavailable, fallback outputs used
- `no_data`: source dataset empty
- `invalid_input`: invalid query value or target datetime not in valid future range

Training statuses:
- `success`: training complete, artifacts and metadata persisted
- `skipped`: training intentionally skipped due to insufficient data rows

## 9. Model and Artifact Details
Training service saves the following model families each monthly run:
- `anomaly_detection` -> IsolationForest
- `root_cause_clustering` -> KMeans
- `volume_forecast` -> LinearRegression
- `partner_health` -> tabular summary model object
- `dynamic_error_clustering` -> KMeans
- `adaptive_thresholding` -> statistical threshold object
- `partner_behavior` -> tabular summary model object
- `capacity_planning` -> LinearRegression

Scaler artifact:
- `artifacts/scalers/preprocessor_YYYYMM.pkl`

Model artifacts:
- `artifacts/models/<model_name>_YYYYMM.pkl`

Registry:
- `artifacts/metadata/training_registry.json`

## 10. Cold Start and Fallback Behaviors
- If model/scaler missing, endpoint returns `cold_start` and a computed heuristic payload.
- `volume_forecast` computes fallback as historical mean times requested horizon.
- `anomaly_detection` and `dynamic_error_clustering` still provide useful summaries from current data.

## 11. Validation Commands
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" | ConvertTo-Json -Depth 8
Invoke-RestMethod -Uri "http://127.0.0.1:8000/jobs/training-registry" | ConvertTo-Json -Depth 8
Invoke-RestMethod -Uri "http://127.0.0.1:8000/insights/volume-forecast?period=week&target_datetime=2026-04-10T00:00:00Z" | ConvertTo-Json -Depth 12
```

## 12. Notes on Compatibility
- `period=hour` includes `next_hour_volume` in addition to `predicted_volume`.
- `forecast_by_error_type` is returned for all forecast periods.
- All timestamps in samples are UTC.
