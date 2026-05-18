# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Utility functions for logging."""

import json
import logging
import os
import sys

from google.cloud.logging.handlers import StructuredLogHandler


def log_struct(level: str, message: str, labels: dict):
    """Logs a structured message. In GCP Log Explorer, the labels will appear under `jsonPayload`.
    
    Args:
        level: Log level (e.g., "INFO", "WARNING", "ERROR").
        message: Log message.
        labels: Additional labels to include in the log.
    """
    # With Python logging lib, json is interpreted as text (populates textPayload field).
    # Using print to populate json as structured logs (populate jsonPayload field).
    # Ref: https://cloud.google.com/functions/docs/monitoring/logging#writing_structured_logs
    print(json.dumps({"message": message, "severity": level, **labels}))


def configure_cloud_logging():
    """Configure a structured log handler to send logs to stdout.

    This is the standard way to get structured logs with correct severity
    in Google Cloud environments like Cloud Run, Cloud Functions, and Batch.
    The logs are captured from stdout by the environment's logging agent.

    It also removes any existing handlers to prevent log duplication.
    """
    # Remove all existing handlers from the root logger.
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            root.removeHandler(handler)

    # Add a handler that formats logs as JSON and sends them to stdout.
    handler = StructuredLogHandler(stream=sys.stdout)

    root.addHandler(handler)
    root.setLevel(logging.INFO)  # Set root logger level


def running_on_cloud() -> bool:
    """Check if running on Cloud.
    
    Returns:
        bool: True if running on Cloud services or jobs, False otherwise.
    """
    return bool(os.getenv('K_SERVICE')) or bool(
        os.getenv('CLOUD_RUN_JOB')) or bool(os.getenv('BATCH_JOB_UID'))


