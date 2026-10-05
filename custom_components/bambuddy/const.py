"""Constants for the Bambuddy integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "bambuddy"

CONF_API_KEY: Final = "api_key"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 10
MAX_SCAN_INTERVAL: Final = 600

API_PREFIX: Final = "/api/v1"
REQUEST_TIMEOUT: Final = timedelta(seconds=15)

# Queue item statuses that are still "in the queue" (not finished history).
QUEUE_ACTIVE_STATUSES: Final = ("pending", "printing")

# Upper bound for job lists exposed as state attributes. Home Assistant warns
# when an entity's attributes exceed 16 KB, and a long queue gets there fast.
MAX_JOBS_IN_ATTRIBUTES: Final = 50

# gcode_state values reported by Bambu printers while a print is in progress.
ACTIVE_PRINT_STATES: Final = frozenset({"PREPARE", "SLICING", "RUNNING", "PAUSE"})
