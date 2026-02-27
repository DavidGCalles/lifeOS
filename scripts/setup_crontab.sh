#!/bin/sh
# Generic script to translate crons.yaml into a native crontab and start crond.
# Assumes yq and curl are installed in the container.

CONFIG=src/config/crons.yaml
CRONTAB_FILE="/etc/crontabs/root"

if [ ! -f "$CONFIG" ]; then
    echo "Configuration file not found: $CONFIG" >&2
    exit 1
fi

# Start with an empty crontab
> "$CRONTAB_FILE"

# For busybox crond (used in Alpine), we must set the TZ environment variable.
# We'll use the first timezone found in any enabled job as the global TZ.
CRON_TZ=$(yq e '.crons.*.timezone | select(. != null) | first' "$CONFIG")
if [ -n "$CRON_TZ" ] && [ "$CRON_TZ" != "null" ]; then
    echo "Found timezone '$CRON_TZ', will apply to crond environment."
else
    echo "No timezone specified in YAML, using system default (UTC)."
    CRON_TZ=""
fi

echo "" >> "$CRONTAB_FILE"

# Loop through all cron jobs and add them to the crontab
yq e '.crons | keys | .[]' "$CONFIG" | while read -r job_key; do
    # Check if job is enabled (defaults to true if missing)
    ENABLED=$(yq e ".crons.$job_key.enabled // true" "$CONFIG")

    if [ "$ENABLED" = "true" ]; then
        SCHEDULE=$(yq e ".crons.$job_key.schedule" "$CONFIG")
        ENDPOINT=$(yq e ".crons.$job_key.target.endpoint" "$CONFIG")
        METHOD=$(yq e ".crons.$job_key.target.method // \"POST\"" "$CONFIG")
        DESCRIPTION=$(yq e ".crons.$job_key.description" "$CONFIG")

        if [ -z "$SCHEDULE" ] || [ "$SCHEDULE" = "null" ] || [ -z "$ENDPOINT" ] || [ "$ENDPOINT" = "null" ]; then
            echo "Skipping job '$job_key': missing schedule or endpoint." >&2
            continue
        fi

        # Write job entry to crontab
        echo "# $DESCRIPTION" >> "$CRONTAB_FILE"
        cat <<EOF >> "$CRONTAB_FILE"
$SCHEDULE curl -s -X $METHOD http://lifeos_worker:8080$ENDPOINT \
  -H "X-Cron-Token:\$SYSTEM_CRON_TOKEN"
EOF
        echo "" >> "$CRONTAB_FILE"
        echo "Added job: $job_key"
    else
        echo "Skipping disabled job: $job_key"
    fi
done

# Ensure correct permissions on crontab file
chmod 600 "$CRONTAB_FILE"

echo "--- Generated Crontab ---"
cat "$CRONTAB_FILE"
echo "-------------------------"

# Start cron daemon in foreground, setting TZ if it was found
echo "Starting crond..."
if [ -n "$CRON_TZ" ]; then
    exec env TZ="$CRON_TZ" crond -f -l 2
else
    exec crond -f -l 2
fi
