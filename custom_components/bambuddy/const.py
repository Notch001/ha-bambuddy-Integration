"""Constants for the Bambuddy integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "bambuddy"

CONF_API_KEY: Final = "api_key"
CONF_BACKEND: Final = "backend"
BACKEND_BAMBUDDY: Final = "bambuddy"
BACKEND_PRINTDOG: Final = "printdog"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 10
MAX_SCAN_INTERVAL: Final = 600

API_PREFIX: Final = "/api/v1"
REQUEST_TIMEOUT: Final = timedelta(seconds=15)
# X1/H2/P2 snapshots go through ffmpeg on the Bambuddy side and can be slow.
CAMERA_TIMEOUT: Final = timedelta(seconds=30)
CAMERA_TOKEN_LIFETIME: Final = timedelta(minutes=50)
COLOR_MAP_REFRESH: Final = timedelta(hours=1)
STATS_INTERVAL: Final = timedelta(minutes=10)
CONF_ENABLE_COSTS: Final = "enable_costs"
CONF_NOTIFY_TARGETS: Final = "notify_targets"
# Warn when an AMS spool has this many percent left or less (0 = never).
CONF_LOW_SPOOL: Final = "low_spool_threshold"
DEFAULT_LOW_SPOOL: Final = 10

# Bambu print speed levels as Bambuddy reports and accepts them.
SPEED_LEVELS: Final = {1: "silent", 2: "standard", 3: "sport", 4: "ludicrous"}

# Queue item statuses that are still "in the queue" (not finished history).
QUEUE_ACTIVE_STATUSES: Final = ("pending", "printing")

# Upper bound for job lists exposed as state attributes. Home Assistant warns
# when an entity's attributes exceed 16 KB, and a long queue gets there fast.
MAX_JOBS_IN_ATTRIBUTES: Final = 50

# gcode_state values reported by Bambu printers while a print is in progress.
ACTIVE_PRINT_STATES: Final = frozenset({"PREPARE", "SLICING", "RUNNING", "PAUSE"})
