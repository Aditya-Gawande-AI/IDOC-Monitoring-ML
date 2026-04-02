# IDoc ML Insight Service

FastAPI service for SAP IDoc monitoring with:
- Data ingestion from SAP OData API every 15 minutes
- CSV-based historical storage for ML training
- Monthly model training with pickle artifacts
- JSON training registry tracking run metadata
- Separate endpoint per feasible insight

## Implemented Insights (8)
1. Anomaly Detection
2. Root Cause Clustering
3. Volume Forecast
4. Partner Health Score
5. Dynamic Error Clustering
6. Adaptive Thresholding
7. Partner Behavior Analytics
8. Predictive Capacity Planning

## Project Structure

```text
app/
  api/routes.py
  core/config.py
  data/storage.py
  jobs/scheduler.py
  ml/features.py
  ml/training.py
  ml/inference.py
  services/api_client.py
  services/parser.py
  services/ingestion.py
  main.py
artifacts/
  models/
  scalers/
  metadata/training_registry.json
data/
  raw/idoc_raw.csv
  processed/idoc_processed.csv
```

## Setup

```powershell
pip install -r requirements.txt
copy .env.example .env
```

You can also keep using your existing `.env` with `SAP_URL`, `SAP_USER`, `SAP_PASS`, `SAP_ORIGIN`, `SAP_VERIFY_TLS`.

## Run

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## API Endpoints

### Operational
- `GET /health`
- `GET /jobs/ingest` - force one ingestion cycle
- `GET /jobs/train` - force one monthly training cycle
- `GET /jobs/training-registry` - view training history

### Insights
- `GET /insights/anomaly-detection`
- `GET /insights/root-cause-clustering`
- `GET /insights/volume-forecast`
- `GET /insights/partner-health`
- `GET /insights/dynamic-error-clustering`
- `GET /insights/adaptive-thresholding`
- `GET /insights/partner-behavior`
- `GET /insights/capacity-planning`

## Training and Artifacts
- Training cadence: monthly (auto-checked after each ingestion)
- Scaler artifact: `artifacts/scalers/preprocessor_YYYYMM.pkl`
- Model artifacts: `artifacts/models/<insight>_YYYYMM.pkl`
- Registry: `artifacts/metadata/training_registry.json`

## Cold Start Behavior
Before enough data is collected (`MIN_TRAINING_ROWS`), endpoints return `status=cold_start` with heuristic outputs.
