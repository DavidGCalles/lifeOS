#!/usr/bin/env python3
"""
Google Cloud Scheduler deployment and management script for LifeOS.

This script reads cron configuration from crons.yaml and programmatically creates,
updates, or deletes Google Cloud Scheduler jobs targeting the deployed Worker service.

It ensures consistent scheduling between local (Docker) and cloud (GCP) environments.

Usage:
  python scripts/deploy_schedulers.py --action deploy [--worker-url URL]
  python scripts/deploy_schedulers.py --action destroy
  python scripts/deploy_schedulers.py --action list
  python scripts/deploy_schedulers.py --action validate
"""

import os
import sys
import argparse
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

import yaml
from google.cloud import scheduler_v1
from google.api_core.exceptions import AlreadyExists, NotFound
import google.auth

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GCPSchedulerManager:
    """
    Manages Google Cloud Scheduler jobs based on crons.yaml configuration.
    """

    def __init__(self, config_path: str = "src/config/crons.yaml"):
        """Initialize the GCP scheduler manager."""
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.cron_jobs: Dict[str, Dict[str, Any]] = {}
        self.client = None
        self.project_id = None
        self.location = None
        
        self._initialize()

    def _initialize(self) -> None:
        """Initialize GCP client and load configuration."""
        # Load configuration
        self.load_config()
        
        # Get GCP project and credentials
        try:
            _, self.project_id = google.auth.default()
        except google.auth.exceptions.DefaultCredentialsError:
            logger.error(
                "Google Cloud credentials not configured. "
                "Set GOOGLE_APPLICATION_CREDENTIALS or run 'gcloud auth application-default login'"
            )
            sys.exit(1)

        # Get location from config or environment
        global_config = self.config.get('global', {})
        cloud_config = global_config.get('cloud', {})
        self.location = cloud_config.get('location', 'us-central1')

        # Initialize Cloud Scheduler client
        self.client = scheduler_v1.CloudSchedulerClient()

        logger.info(f"Initialized GCP Scheduler Manager for project: {self.project_id}")
        logger.info(f"Location: {self.location}")

    def load_config(self) -> None:
        """Load cron configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                data = yaml.safe_load(f)
                self.config = data
                self.cron_jobs = data.get('crons', {})
                logger.info(f"Loaded {len(self.cron_jobs)} cron jobs from {self.config_path}")
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {self.config_path}")
            sys.exit(1)
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML configuration: {e}")
            sys.exit(1)

    def _resolve_env_variables(self, value: str) -> str:
        """Resolve environment variable placeholders in config values."""
        if not isinstance(value, str):
            return value
        
        if value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            resolved = os.getenv(env_var)
            if resolved is None:
                logger.warning(f"Environment variable {env_var} not set")
                return value
            return resolved
        return value

    def _build_job_name(self, job_key: str) -> str:
        """Build the full Google Cloud Scheduler job name."""
        parent = self.client.common_location_path(self.project_id, self.location)
        return f"{parent}/jobs/lifeos-{job_key}"

    def _get_auth_token(self) -> str:
        """Get the authentication token from environment."""
        global_config = self.config.get('global', {})
        auth_token_env = global_config.get('auth_token_env', 'SYSTEM_CRON_TOKEN')
        token = os.getenv(auth_token_env)
        
        if not token:
            logger.warning(
                f"Authentication token {auth_token_env} not configured. "
                "Schedulers will execute without token validation."
            )
            return ""
        return token

    def deploy_job(
        self,
        job_key: str,
        job_config: Dict[str, Any],
        worker_url: str
    ) -> bool:
        """
        Create or update a Cloud Scheduler job.
        
        Args:
            job_key: Unique identifier for the job (used in crons.yaml)
            job_config: Job configuration from crons.yaml
            worker_url: Base URL of the deployed worker service
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not job_config.get('enabled', True):
                logger.info(f"Skipping disabled job: {job_key}")
                return True

            target = job_config.get('target', {})
            endpoint = target.get('endpoint', '')
            method = target.get('method', 'POST').upper()
            headers = target.get('headers', {}).copy()
            payload = job_config.get('payload')
            schedule = job_config.get('schedule')
            description = job_config.get('description', '')

            if not schedule:
                logger.error(f"Job {job_key} has no schedule defined")
                return False

            # Build full URL
            full_url = f"{worker_url}{endpoint}"

            # Add authentication token
            auth_token = self._get_auth_token()
            if auth_token:
                global_config = self.config.get('global', {})
                auth_header = global_config.get('auth_header', 'X-Cron-Token')
                headers[auth_header] = auth_token

            # Build HTTP request body for Cloud Scheduler
            http_body = scheduler_v1.HttpTarget(
                uri=full_url,
                http_method=scheduler_v1.HttpMethod[method],
                headers=headers,
            )

            # Set request body if payload exists
            if payload:
                http_body.body = json.dumps(payload).encode()

            # Build HTTP target with OAuth token for authentication
            # Note: This uses the service account email for authentication
            service_account_email = self._resolve_env_variables(
                self.config.get('global', {})
                .get('cloud', {})
                .get('service_account_email', '')
            )
            
            if service_account_email:
                http_body.oauth_token = scheduler_v1.OAuthToken(
                    service_account_email=service_account_email
                )

            # Create the job object
            tz = job_config.get('timezone', 'UTC')
            job = scheduler_v1.Job(
                name=self._build_job_name(job_key),
                description=description,
                schedule=schedule,
                timezone=tz,
                http_target=http_body,
            )

            # Try to create or update the job
            parent = self.client.common_location_path(self.project_id, self.location)
            
            try:
                # Try to get existing job first
                existing = self.client.get_job(name=job.name)
                # Update existing job
                logger.info(f"Updating Cloud Scheduler job: {job_key}")
                self.client.update_job(job=job)
                logger.info(f"Successfully updated job: {job_key}")
            except NotFound:
                # Create new job
                logger.info(f"Creating Cloud Scheduler job: {job_key}")
                self.client.create_job(request={"parent": parent, "job": job})
                logger.info(f"Successfully created job: {job_key}")

            return True

        except Exception as e:
            logger.error(f"Error deploying job {job_key}: {e}")
            return False

    def delete_job(self, job_key: str) -> bool:
        """
        Delete a Cloud Scheduler job.
        
        Args:
            job_key: Unique identifier for the job
            
        Returns:
            True if successful, False otherwise
        """
        try:
            job_name = self._build_job_name(job_key)
            logger.info(f"Deleting Cloud Scheduler job: {job_key}")
            self.client.delete_job(name=job_name)
            logger.info(f"Successfully deleted job: {job_key}")
            return True
        except NotFound:
            logger.warning(f"Job not found: {job_key}")
            return True
        except Exception as e:
            logger.error(f"Error deleting job {job_key}: {e}")
            return False

    def list_jobs(self) -> List[Dict[str, Any]]:
        """
        List all LifeOS Cloud Scheduler jobs in the configured location.
        
        Returns:
            List of job information dictionaries
        """
        try:
            parent = self.client.common_location_path(self.project_id, self.location)
            jobs = self.client.list_jobs(request={"parent": parent})
            
            lifeos_jobs = []
            for job in jobs:
                if "lifeos-" in job.name:
                    job_key = job.name.split("lifeos-")[-1]
                    lifeos_jobs.append({
                        "name": job_key,
                        "schedule": job.schedule,
                        "description": job.description,
                        "last_execution_time": job.last_execution_time,
                        "state": job.state.name if hasattr(job, 'state') else "UNKNOWN",
                    })
            
            return lifeos_jobs
        except Exception as e:
            logger.error(f"Error listing jobs: {e}")
            return []

    def deploy_all(self, worker_url: str) -> bool:
        """
        Deploy all enabled cron jobs to Cloud Scheduler.
        
        Args:
            worker_url: Base URL of the deployed worker service
            
        Returns:
            True if all jobs deployed successfully, False otherwise
        """
        logger.info(f"Deploying jobs to Cloud Scheduler (project: {self.project_id})")
        
        success_count = 0
        failed_count = 0
        
        for job_key, job_config in self.cron_jobs.items():
            if self.deploy_job(job_key, job_config, worker_url):
                success_count += 1
            else:
                failed_count += 1

        logger.info(
            f"Deployment complete: {success_count} successful, {failed_count} failed"
        )
        return failed_count == 0

    def destroy_all(self) -> bool:
        """
        Delete all LifeOS Cloud Scheduler jobs.
        
        Returns:
            True if all jobs deleted successfully, False otherwise
        """
        logger.info(f"Destroying all Cloud Scheduler jobs for LifeOS")
        
        success_count = 0
        failed_count = 0
        
        for job_key in self.cron_jobs.keys():
            if self.delete_job(job_key):
                success_count += 1
            else:
                failed_count += 1

        logger.info(
            f"Destruction complete: {success_count} successful, {failed_count} failed"
        )
        return failed_count == 0

    def validate_config(self) -> bool:
        """
        Validate the cron configuration without making changes.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        logger.info("Validating cron configuration...")
        
        is_valid = True
        for job_key, job_config in self.cron_jobs.items():
            # Check required fields
            if 'schedule' not in job_config:
                logger.error(f"Job {job_key} missing 'schedule'")
                is_valid = False
            
            if 'target' not in job_config:
                logger.error(f"Job {job_key} missing 'target'")
                is_valid = False
            else:
                target = job_config['target']
                if 'endpoint' not in target:
                    logger.error(f"Job {job_key} target missing 'endpoint'")
                    is_valid = False

            # Validate cron expression
            try:
                from croniter import croniter
                if 'schedule' in job_config:
                    croniter(job_config['schedule'])
            except Exception as e:
                logger.error(f"Job {job_key} has invalid cron expression: {e}")
                is_valid = False

        if is_valid:
            logger.info("Configuration is valid")
        else:
            logger.error("Configuration has errors")

        return is_valid


def main():
    """Entry point for the deployment script."""
    parser = argparse.ArgumentParser(
        description="Deploy and manage LifeOS Cloud Scheduler jobs"
    )
    parser.add_argument(
        "--action",
        choices=["deploy", "destroy", "list", "validate"],
        default="deploy",
        help="Action to perform"
    )
    parser.add_argument(
        "--worker-url",
        default=os.getenv("WORKER_URL", "https://worker.lifeos.dev"),
        help="Base URL of the deployed worker service"
    )

    args = parser.parse_args()

    manager = GCPSchedulerManager()

    if args.action == "deploy":
        logger.info(f"Deploying jobs to worker URL: {args.worker_url}")
        success = manager.deploy_all(args.worker_url)
        sys.exit(0 if success else 1)

    elif args.action == "destroy":
        logger.warning("Destroying all LifeOS Cloud Scheduler jobs")
        success = manager.destroy_all()
        sys.exit(0 if success else 1)

    elif args.action == "list":
        jobs = manager.list_jobs()
        if jobs:
            logger.info(f"Found {len(jobs)} LifeOS jobs:")
            for job in jobs:
                logger.info(f"  - {job['name']}: {job['schedule']}")
        else:
            logger.info("No LifeOS jobs found")
        sys.exit(0)

    elif args.action == "validate":
        success = manager.validate_config()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
