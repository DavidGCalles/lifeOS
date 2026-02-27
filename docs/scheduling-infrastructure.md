# Configuration-Driven Scheduling Infrastructure (ADR-014-005)

This document describes the environment-agnostic recurring trigger mechanisms for LifeOS. The system reads from a single source of truth (`crons.yaml`) and guarantees execution parity between Local (Docker) and Cloud (GCP) environments.

## 🚀 Quick Start: Adding a New Cron Job

All background tasks are defined in a single file. You do not need to touch the scheduler code to add a new task.

### 1. Edit the Configuration
Open `src/config/crons.yaml` and add your new job:
```yaml
crons:
  my_custom_job:
    description: "Brief description of what this does"
    enabled: true
    timezone: "Europe/Madrid"     # Ensures the cron respects daylight saving time
    schedule: "0 14 * * *"        # Standard cron expression (e.g., 2:00 PM daily)
    target:
      endpoint: "/system/cron/my-endpoint"
      method: "POST"              # Defaults to POST if omitted
```
### 2. Implement the Endpoint
In main_worker.py, create the endpoint matching the YAML and protect it with the security dependency:

```python
@app.post("/system/cron/my-endpoint", dependencies=[Depends(verify_cron_token)])
async def my_custom_cron():
    logger.info("Executing custom background task")
    # Implementation logic here
    return {"status": "success"}
```
### 3. Apply Changes
#### Local Environment (Docker):

Restart the lightweight scheduler container to parse the new YAML:

```bash
docker-compose restart lifeos_scheduler
```

#### Cloud Environment (GCP):
Deploy the updated configuration to Google Cloud Scheduler:

```bash
python scripts/deploy_schedulers.py --action deploy --worker-url "https://worker.lifeos.dev"
```
## 🏗️ Architecture
```text
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
   │  lifeos_     │      │  deploy_       │
   │  scheduler   │      │  schedulers.py │
   │  (Alpine)    │      │                │
   └──────┬───────┘      └────────┬───────┘
          │ (HTTP POST)           │ (HTTP POST)
          ▼                       ▼
   ┌──────────────────────────────────────┐
   │         lifeos_worker service        │
   │      (Protected by X-Cron-Token)     │
   └──────────────────────────────────────┘
```

#### Local Scheduler (Minimalist)
The local service uses Alpine's built‑in crond daemon. A shell helper (scripts/setup_crontab.sh) parses the YAML once using yq and writes standard Linux cron entries.

_Overhead_: Minimal (~50MB RAM, ~1% CPU).

_Timezone Support_: Achieved by injecting the TZ environment variable directly into the crond process.

_Cloud Deployment_: The Python script deploy_schedulers.py translates the YAML into native GCP Cloud Scheduler jobs, applying the required OIDC/Service Account headers automatically.

## 🔒 Security & Authentication
All automated requests from both local and cloud schedulers are authenticated via a Bearer token in the headers:

X-Cron-Token: {SYSTEM_CRON_TOKEN}

The token is loaded from your .env file (Local) or Secret Manager (GCP) and is validated natively in FastAPI using the verify_cron_token dependency.

## ⏱️ Cron Expression Reference
LifeOS uses standard Unix cron expressions (5 fields):

```text
* * * * *
│ │ │ │ │
│ │ │ │ └───── day of week (0 - 6) (Sunday=0)
│ │ │ └──────── month (1 - 12)
│ │ └────────── day of month (1 - 31)
│ └──────────── hour (0 - 23)
└────────────── minute (0 - 59)
```
Daily at 2:00 AM: 0 2 * * *

Every 30 minutes: */30 * * * *

Weekdays at noon: 0 12 * * 1-5

(Tip: Use crontab.guru to validate complex expressions).

## 🛠️ Troubleshooting
1. "No timezone specified in YAML" (Local)
Ensure timezone: "Europe/Madrid" exists in at least one enabled job in crons.yaml. Also verify that the tzdata package is installed in the lifeos_scheduler Docker configuration.

2. Job not executing locally
Check the crontab compilation and the live daemon logs:

```Bash
docker-compose logs -f lifeos_scheduler
```

3. 403 Forbidden Error in Worker
The scheduler is failing to pass the correct token. Verify that SYSTEM_CRON_TOKEN is correctly set in your .env file and that the worker and scheduler share the same value.