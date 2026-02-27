# Configuration-Driven Scheduling Infrastructure (ADR-014-005)

## Overview

This document describes the configuration-driven scheduling infrastructure that provides environment-agnostic recurring trigger mechanisms for LifeOS. The system reads from a single source of truth (`crons.yaml`) and guarantees execution parity between Local (Docker) and Cloud (GCP) environments.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Single Source of Truth                   │
│              src/config/crons.yaml (Configuration)          │
└──────────────────┬──────────────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
   LOCAL ENVIRONMENT     CLOUD ENVIRONMENT
   ┌──────────────┐      ┌────────────────┐
   │   Docker     │      │  Google Cloud  │
   │ Compose      │      │  Scheduler     │
   │              │      │                │
   │  scheduler   │      │  deploy_      │
   │  service     │      │  schedulers.py │
   │  (crond)     │      │                │
   └──────┬───────┘      └────────┬───────┘
          │                       │
          │ (HTTP POST)           │ (HTTP POST)
          ▼                       ▼
   ┌──────────────────────────────────────┐
   │      lifeos_worker service           │
   │   /system/cron/{endpoint}            │
   │   (Protected by SYSTEM_CRON_TOKEN)   │
   └──────────────────────────────────────┘
```

## Components

### 1. Source Configuration: `src/config/crons.yaml`

A minimal YAML that serves as the single source of truth for scheduled tasks. It
contains only enabled jobs, schedules, timezones and the target endpoint; all
other logic is left to the native cron daemon or the worker service.

**Example minimal structure:**
```yaml
crons:
  consolidate_memory:
    description: "Consolidate and deduplicate episodic memories"
    enabled: true
    timezone: "Europe/Madrid"
    schedule: "0 2 * * *"
    target:
      endpoint: "/system/cron/consolidate"
      method: "POST"
```

The scheduler itself does not interpret headers, payloads, timeouts, or retry
settings; the worker API handles any additional requirements.


### 2. Local Scheduler: native `crond` with helper script

In keeping with minimalism, the local scheduler service simply uses Alpine's
built‑in `crond` daemon. A small shell helper (`scripts/setup_crontab.sh`) parses
the YAML once (using `yq`) and writes an entry to `/etc/crontabs/root`.

**Features:**
- No Python runtime or third‑party packages at container start
- The job is a single `curl` command to the worker endpoint
- Timezone support via `CRON_TZ` environment variable in crontab
- Uses standard, battle‑tested cron behavior for scheduling

**Docker Service:**
``` yaml
lifeos_scheduler:
  image: alpine:latest
  depends_on:
    - lifeos_worker
  entrypoint: >
    sh -c "
      apk add --no-cache curl yq &&
      chmod +x /app/scripts/setup_crontab.sh &&
      /app/scripts/setup_crontab.sh
    "
```

### 3. Cloud Deployment: `scripts/deploy_schedulers.py`

Python script that parses `crons.yaml` and manages Google Cloud Scheduler jobs.

**Capabilities:**
- **Deploy**: Create or update Cloud Scheduler jobs
- **Destroy**: Delete all LifeOS Cloud Scheduler jobs
- **List**: Show all deployed Cloud Scheduler jobs
- **Validate**: Check configuration syntax and cron expressions

## Usage

### Local Environment (Docker)

1. **Start the scheduler with Docker Compose:**
```bash
docker-compose up -d --build
```

The `lifeos_scheduler` service automatically starts and:
- Reads `crons.yaml`
- Monitors configured schedules
- Makes HTTP requests to `http://lifeos_worker:8080` destinations
- Includes `X-Cron-Token` header from `SYSTEM_CRON_TOKEN` environment variable

2. **Monitor logs:**
```bash
docker-compose logs -f lifeos_scheduler
```

3. **Add new jobs:**
- Edit `src/config/crons.yaml`
- Restart the scheduler container: `docker-compose restart lifeos_scheduler`

### Cloud Environment (GCP)

1. **Set up authentication:**
```bash
# Using application default credentials
gcloud auth application-default login

# Or provide service account file
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

2. **Set environment variables:**
```bash
export GCP_PROJECT_ID="your-gcp-project"
export GCP_SERVICE_ACCOUNT_EMAIL="scheduler@your-project.iam.gserviceaccount.com"
export SYSTEM_CRON_TOKEN="your-secret-token"
export WORKER_URL="https://worker.lifeos.dev"  # Your deployed worker URL
```

3. **Deploy Cloud Scheduler jobs:**
```bash
python scripts/deploy_schedulers.py --action deploy --worker-url https://worker.lifeos.dev
```

4. **List deployed jobs:**
```bash
python scripts/deploy_schedulers.py --action list
```

5. **Destroy all Cloud Scheduler jobs:**
```bash
python scripts/deploy_schedulers.py --action destroy
```

6. **Validate configuration:**
```bash
python scripts/deploy_schedulers.py --action validate
```

## Security

### Authentication

All cron requests include a bearer token in the `X-Cron-Token` header:

```
X-Cron-Token: {SYSTEM_CRON_TOKEN}
```

**Local Environment:**
- Token sourced from `.env` file via Docker
- Validated in `main_worker.py` by `verify_cron_token()` dependency

**Cloud Environment:**
- Token passed via Cloud Scheduler HTTP headers
- Can optionally use OAuth service account authentication

### Token Management

1. **Generate secure token:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

2. **Set in environment:**
```bash
# .env file (local)
SYSTEM_CRON_TOKEN=your-generated-token

# GCP Secret Manager (cloud)
gcloud secrets create SYSTEM_CRON_TOKEN --data-file=- <<< "your-token"
```

3. **Use in worker service:**
The token is validated in `main_worker.py`:
```python
async def verify_cron_token(request: Request):
    token = request.headers.get("X-Cron-Token")
    if token != SYSTEM_CRON_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid cron token")
```

## Predefined Jobs

### consolidate_memory
- **Schedule:** Daily at 2 AM UTC
- **Endpoint:** `/system/cron/consolidate`
- **Description:** Consolidate and deduplicate episodic memories with semantic analysis

(Other jobs were removed to keep the YAML minimal and avoid endpoints that do not exist.)
## Adding New Cron Jobs

1. **Edit `src/config/crons.yaml`:**
```yaml
crons:
  my_custom_job:
    description: "My custom scheduled task"
    enabled: true
    schedule: "0 12 * * *"  # Noon daily
    target:
      endpoint: "/system/cron/my-endpoint"
      method: "POST"
```

2. **Implement the endpoint in `main_worker.py`:**
```python
@app.post("/system/cron/my-endpoint", dependencies=[Depends(verify_cron_token)])
async def my_cron_endpoint(request: Request):
    logger.info("Executing my custom job")
    # Your implementation here
    return {"status": "success"}
```

3. **For local testing:**
```bash
docker-compose restart lifeos_scheduler
```

4. **For cloud deployment:**
```bash
python scripts/deploy_schedulers.py --action deploy
```

## Cron Expression Reference

LifeOS uses standard Unix cron expressions with five fields:

```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (Sunday to Saturday)
│ │ │ │ │
│ │ │ │ │
* * * * *
```

**Examples:**
- `0 2 * * *` — Every day at 2:00 AM
- `0 3 * * 0` — Every Sunday at 3:00 AM
- `*/30 * * * *` — Every 30 minutes
- `0 */4 * * *` — Every 4 hours
- `0 12 * * 1-5` — Weekdays at noon
- `0 0 1 * *` — First day of month at midnight

See [crontab.guru](https://crontab.guru) for interactive expression builder.

## Troubleshooting

### Local Scheduler Not Executing Jobs

1. **Check scheduler logs:**
```bash
docker-compose logs lifeos_scheduler
```

2. **Verify worker service is running:**
```bash
curl http://localhost:8081/docs
```

3. **Test cron expression:**
```bash
python -c "from croniter import croniter; from datetime import datetime; c = croniter('0 2 * * *', datetime.now()); print(c.get_next(datetime))"
```

4. **Verify token is set:**
```bash
docker-compose exec lifeos_scheduler printenv SYSTEM_CRON_TOKEN
```

### Cloud Scheduler Jobs Not Executing

1. **Check GCP Cloud Scheduler logs:**
```bash
gcloud logging read "resource.type=cloud_scheduler_job AND resource.labels.job_id=lifeos-*" --limit 50
```

2. **Verify worker URL is accessible:**
```bash

```

3. **Check Cloud Scheduler job status:**
```bash
python scripts/deploy_schedulers.py --action list
```

4. **Validate configuration:**
```bash
python scripts/deploy_schedulers.py --action validate
```

## Environment Variables

### Required for Cloud Deployment

```bash
GOOGLE_APPLICATION_CREDENTIALS    # Path to GCP service account JSON
GCP_PROJECT_ID                     # GCP project ID
GCP_SERVICE_ACCOUNT_EMAIL         # Service account email
SYSTEM_CRON_TOKEN                 # Authentication token for cron requests
WORKER_URL                        # Base URL of deployed worker service
```

### Optional

```bash
QDRANT_API_KEY                    # Qdrant vector database API key
LITELLM_API_KEY                   # LiteLLM proxy API key
```

## Migration Guide

### From APScheduler to Configuration-Driven Scheduling

If migrating from in-app APScheduler jobs:

1. **Map existing jobs to `crons.yaml`:**
   - Convert APScheduler schedules to cron expressions
   - Create corresponding worker endpoints
   - Remove in-app scheduler initialization

2. **Deploy to local environment:**
   ```bash
   docker-compose up -d --build
   ```

3. **Test execution and logging:**
   ```bash
   docker-compose logs -f lifeos_scheduler
   ```

4. **Deploy to cloud:**
   ```bash
   python scripts/deploy_schedulers.py --action deploy
   ```

## Performance Considerations

### Local Environment
- **Memory:** ~50MB for scheduler container
- **CPU:** Minimal (~1% idle)
- **Overhead:** Check every 30 seconds for due jobs
- **Scaling:** Single scheduler handles hundreds of jobs

### Cloud Environment
- **Cost:** ~$0.10 per job per month
- **Reliability:** 99.9% SLA from Google Cloud
- **Limits:** 1000 jobs per Cloud Scheduler region
- **Latency:** Typically <1s execution time

## Best Practices

1. **Use UTC timezone consistently** — All timestamps in `crons.yaml` are UTC
2. **Set appropriate timeouts** — Account for external API latencies
3. **Implement idempotent endpoints** — Allow safe job retries
4. **Monitor job execution** — Check logs regularly for failures
5. **Version control configuration** — Track `crons.yaml` changes in git
6. **Test before deploying** — Use `--action validate` before changes
7. **Document custom jobs** — Include purpose and expected behavior
8. **Set secure tokens** — Use strong, randomly generated tokens

## Related Documentation

- [ADR-014: Workers and Orchestration](../docs/adr/014-workers.md)
- [System Status Management](../docs/adr/008-two-speed-architecture.md)
- [Memory Consolidation Strategy](../docs/adr/005-session-memory.md)

## Version History

- **v1.0** (2026-02-27) — Initial implementation with local and cloud support
