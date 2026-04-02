# Standard Deployment-Ready Plan

## 1. Runtime Baseline
- Python 3.10+
- Service command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Process manager: NSSM/Task Scheduler/Windows Service wrapper for auto-restart

## 2. Environment and Secrets
- Keep API credentials only in environment variables (`IDOC_API_*` or `SAP_*`)
- Disable plaintext secrets in source files
- Rotate exposed credentials before go-live

## 3. Scheduling Model
- Ingestion runs every 15 minutes in app scheduler
- Monthly model training auto-triggers when a new month is detected and minimum data is available
- Manual overrides available via `/jobs/ingest` and `/jobs/train`

## 4. Data and Artifact Paths
- Raw events CSV: `data/raw/idoc_raw.csv`
- Processed feature CSV: `data/processed/idoc_processed.csv`
- Scalers: `artifacts/scalers/*.pkl`
- Models: `artifacts/models/*.pkl`
- Training registry: `artifacts/metadata/training_registry.json`

## 5. Reliability Controls
- API timeout enforced
- Upstream fetch failures are logged and retried on next scheduler run
- Ingestion uses deduplication by event hash
- Cold-start fallbacks when trained models are unavailable

## 6. Monitoring
- Track:
  - last successful ingestion time
  - rows ingested per cycle
  - last successful training run tag
  - endpoint latencies and error rate

## 7. Validation Checklist
- Verify ingestion happens every 15 minutes
- Verify monthly training writes scaler + model artifacts
- Verify training registry appends one run per completed training
- Verify all 8 insight endpoints return valid JSON responses

## 8. Production Hardening Next Steps
- Move CSV storage to PostgreSQL for scale and concurrency
- Add authentication for insight endpoints
- Add centralized logging and alerts
- Add unit/integration tests and CI pipeline
