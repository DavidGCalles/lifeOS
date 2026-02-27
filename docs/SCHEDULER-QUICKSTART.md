# Quick Start: Configuration-Driven Scheduling

## Local Development (Docker)

### 1. Start Services
```bash
docker-compose up -d --build
```

### 2. Verify Scheduler Running
```bash
docker-compose ps  # Should show lifeos_scheduler running
docker-compose logs lifeos_scheduler --follow
```

### 3. Add a New Job
Edit `src/config/crons.yaml` with a minimal entry:
```yaml
  my_custom_job:
    description: "My scheduled task"
    enabled: true
    timezone: "Europe/Madrid"          # optional
    schedule: "0 14 * * *"  # 2 PM UTC daily
    target:
      endpoint: "/system/cron/my-endpoint"
      method: "POST"
```

Only the schedule and endpoint are required; extras such as headers or
payloads can be handled by the worker if needed.

Add endpoint to `main_worker.py`:
```python
@app.post("/system/cron/my-endpoint", dependencies=[Depends(verify_cron_token)])
async def my_endpoint():
    logger.info("My job executed")
    return {"status": "success"}
```

Restart scheduler:
```bash
docker-compose restart lifeos_scheduler
```

### 4. Monitor Execution
```bash
# Watch real-time logs
docker-compose logs -f lifeos_scheduler

# Test endpoint manually
curl -X POST http://localhost:8081/system/cron/my-endpoint \
  -H "X-Cron-Token: $(grep SYSTEM_CRON_TOKEN .env | cut -d= -f2)"
```

## Cloud Deployment (GCP)

### 1. Prerequisites
```bash
# Authenticate
gcloud auth application-default login

# Set environment variables
export GCP_PROJECT_ID="your-project"
export GCP_SERVICE_ACCOUNT_EMAIL="scheduler@your-project.iam.gserviceaccount.com"
export WORKER_URL="https://worker.lifeos.dev"
export SYSTEM_CRON_TOKEN="your-token"
```

### 2. Deploy Jobs
```bash
# Validate configuration
python scripts/deploy_schedulers.py --action validate

# Deploy to Cloud Scheduler
python scripts/deploy_schedulers.py --action deploy --worker-url "$WORKER_URL"

# List deployed jobs
python scripts/deploy_schedulers.py --action list
```

### 3. Monitor Execution
```bash
# View logs
gcloud logging read 'resource.type=cloud_scheduler_job AND resource.labels.job_id=lifeos-*' --limit 20

# Check Cloud Scheduler UI
gcloud scheduler jobs list
```

## Cron Expression Reference

| Expression | Meaning |
|-----------|---------|
| `0 2 * * *` | Every day at 2:00 AM |
| `0 2 * * 0` | Every Sunday at 2:00 AM |
| `*/30 * * * *` | Every 30 minutes |
| `0 */4 * * *` | Every 4 hours |
| `0 12 1 * *` | First day of month at noon |
| `0 0 1 1 *` | Every January 1st |

Use [crontab.guru](https://crontab.guru) for interactive expressions.

## Troubleshooting

### Scheduler Not Running
```bash
# Check if container exists
docker ps | grep scheduler

# Restart it
docker-compose up -d --build lifeos_scheduler

# Check for errors
docker-compose logs lifeos_scheduler
```

### Jobs Not Executing
```bash
# 1. Verify token is set
docker-compose exec lifeos_scheduler printenv SYSTEM_CRON_TOKEN

# 2. Test endpoint manually
curl -X POST http://localhost:8081/system/cron/consolidate \
  -H "X-Cron-Token: your-token" \
  -H "Content-Type: application/json"

# 3. Check iftrigger condition (not busy, LLM healthy)
docker-compose logs lifeos_worker | grep "consolidate"
```

### Cloud Scheduler Issues
```bash
# Check job status
gcloud scheduler jobs describe lifeos-consolidate_memory

# View execution logs
gcloud logging read 'resource.type=cloud_scheduler_job AND resource.labels.job_id=lifeos-consolidate_memory' --limit 10

# Test job execution
gcloud scheduler jobs run lifeos-consolidate_memory
```

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `SYSTEM_CRON_TOKEN` | Authentication token for scheduler | Yes |
| `GCP_PROJECT_ID` | Google Cloud project ID | Cloud only |
| `GCP_SERVICE_ACCOUNT_EMAIL` | GCP service account | Cloud only |
| `WORKER_URL` | Deployed worker service URL | Cloud only |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON | Cloud only |

## API Endpoints

Only two endpoints are relevant:

```
GET  /health
     └─ Basic health check (no token required)

POST /system/cron/consolidate
     └─ Trigger memory consolidation (requires `X-Cron-Token`)
```

## Common Tasks

### Update Cron Schedule
1. Edit `src/config/crons.yaml`
2. Local: `docker-compose restart lifeos_scheduler`
3. Cloud: `python scripts/deploy_schedulers.py --action deploy`

### Disable a Job Temporarily
```yaml
my_job:
  enabled: false  # Change this
  schedule: "0 2 * * *"
  ...
```



## More Information

- Architecture Decision: [docs/adr/014-workers.md](../docs/adr/014-workers.md)

---

**Questions?** Check the troubleshooting section or review the full documentation.
