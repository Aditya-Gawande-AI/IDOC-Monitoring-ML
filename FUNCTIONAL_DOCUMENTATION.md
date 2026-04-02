# Functional Documentation - IDoc ML Insight Service

## 1. Purpose
This service helps operations teams monitor SAP IDoc failures, identify error patterns, forecast upcoming workload, and take proactive actions.

It provides:
- Near real-time ingestion (every 15 minutes)
- Insight APIs for monitoring and decisions
- Monthly model refresh based on collected history

## 2. Business Users
- IDoc support analysts
- SAP operations teams
- Integration support leads
- Capacity and planning teams

## 3. How to Use This API Functionally
1. Confirm service availability.
2. Run or verify ingestion.
3. Use insight endpoints to answer operational questions.
4. Trigger training when needed (or rely on monthly auto-training).
5. Track model updates in training registry.

## 4. Operational Endpoints

### 4.1 Health Check
Business intent: verify the service is reachable.

Request:
```http
GET /health
```

Sample response:
```json
{
  "status": "ok"
}
```

### 4.2 Run Ingestion Once
Business intent: pull latest IDoc data immediately (instead of waiting for the next 15-minute cycle).

Request:
```http
GET /jobs/ingest
```

Sample response:
```json
{
  "fetched_records": 991,
  "inserted_records": 991,
  "processed_rows": 26757,
  "updated_at": "2026-04-02T11:13:20.354878"
}
```

### 4.3 Run Training Once
Business intent: force immediate retraining after enough new data is available.

Request:
```http
GET /jobs/train
```

Sample response:
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

### 4.4 Training Registry
Business intent: audit historical training runs and model versions.

Request:
```http
GET /jobs/training-registry
```

Sample response:
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

## 5. Insight Endpoints (Business Scenarios)

### 5.1 Anomaly Detection
Business question: Are current error patterns behaving abnormally?

Request:
```http
GET /insights/anomaly-detection
```

Sample response:
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

Action guidance:
- If `anomaly_ratio_overall` spikes, review recent transport/config changes.
- Prioritize error types with high `anomaly_ratio` and high `total_records`.

### 5.2 Root Cause Clustering
Business question: How are error events grouped into major issue buckets?

Request:
```http
GET /insights/root-cause-clustering
```

Sample response:
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

Action guidance:
- Focus on the largest clusters first.
- Map each cluster to operational runbooks.

### 5.3 Volume Forecast
Business question: What incoming IDoc error volume should we expect in a target period?

Inputs:
- `period`: `hour`, `day`, `week`, `month`
- `target_datetime` (optional, ISO datetime)

Sample requests:
```http
GET /insights/volume-forecast?period=hour
GET /insights/volume-forecast?period=week&target_datetime=2026-04-10T00:00:00Z
```

Sample response (`period=hour`):
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

Action guidance:
- Plan staffing from `predicted_volume`.
- Pre-assign owners for top `forecast_by_error_type` categories.

### 5.4 Partner Health
Business question: Which partner systems are currently high risk?

Request:
```http
GET /insights/partner-health
```

Sample response:
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

Action guidance:
- Prioritize partners with lower `health_score` and high `volume`.

### 5.5 Dynamic Error Clustering
Business question: What exact error types are active right now, and how frequent are they?

Request:
```http
GET /insights/dynamic-error-clustering
```

Sample response:
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

Action guidance:
- Use `error_clusters` as the primary backlog for triage and assignment.

### 5.6 Adaptive Thresholding
Business question: Is current failure behavior above normal tolerance?

Request:
```http
GET /insights/adaptive-thresholding
```

Sample response:
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

Action guidance:
- If `breach=true`, start incident escalation and high-frequency monitoring.

### 5.7 Partner Behavior
Business question: How do partner traffic and failure characteristics differ?

Request:
```http
GET /insights/partner-behavior
```

Sample response:
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

Action guidance:
- Detect outlier partners and apply partner-specific controls.

### 5.8 Capacity Planning
Business question: How much next-day processing capacity is required?

Request:
```http
GET /insights/capacity-planning
```

Sample response:
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

Action guidance:
- Use `next_day_capacity` to size queue workers, batch windows, and support shifts.

## 6. Functional Status Meanings
- `ok`: full model-based output available.
- `cold_start`: model/scaler not ready yet; fallback logic used.
- `no_data`: not enough source data in storage.
- `invalid_input`: request inputs are syntactically valid but operationally not acceptable (for example, past target datetime).
- `success`/`skipped` (training endpoints): training completed or intentionally skipped.

## 7. Recommended Daily Operating Flow
1. Call `/health`.
2. Check `/jobs/training-registry` for latest successful run.
3. Use `/insights/dynamic-error-clustering` and `/insights/anomaly-detection` for immediate triage.
4. Use `/insights/volume-forecast` and `/insights/capacity-planning` for planning.
5. Use partner endpoints (`/insights/partner-health`, `/insights/partner-behavior`) for owner-specific actions.
