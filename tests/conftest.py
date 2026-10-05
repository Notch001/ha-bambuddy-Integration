"""Shared fixtures: a fake Bambuddy server behind aioclient_mock."""

from __future__ import annotations

import copy
from typing import Any

import pytest

URL = "http://bambuddy.local:8000"
API = f"{URL}/api/v1"
API_KEY = "bb_testkey"

PRINTERS: list[dict[str, Any]] = [
    {"id": 1, "name": "X1C Werkstatt", "serial_number": "00M09A111111111", "model": "X1C", "is_active": True},
    {"id": 2, "name": "A1 Mini", "serial_number": "0300AA222222222", "model": "A1 Mini", "is_active": True},
]

STATUS: dict[int, dict[str, Any]] = {
    1: {
        "id": 1,
        "name": "X1C Werkstatt",
        "connected": True,
        "state": "RUNNING",
        "subtask_name": "Benchy",
        "current_print": "Benchy.gcode.3mf",
        "progress": 42.0,
        "remaining_time": 83,
        "layer_num": 50,
        "total_layers": 120,
        "temperatures": {"nozzle": 220.0, "nozzle_target": 220.0, "bed": 60.0, "bed_target": 60.0, "chamber": 35.0},
        "hms_errors": [],
        "wifi_signal": -55,
        "door_open": False,
        "awaiting_plate_clear": False,
        "firmware_version": "01.08.00.00",
    },
    2: {
        "id": 2,
        "name": "A1 Mini",
        "connected": False,
        "state": "IDLE",
        "temperatures": {"nozzle": 25.0, "nozzle_target": 0, "bed": 24.0, "bed_target": 0},
        "hms_errors": [{"code": "0300_4000", "severity": 2, "module": 3}],
        "awaiting_plate_clear": True,
    },
}

QUEUE_PENDING: list[dict[str, Any]] = [
    {"id": 11, "status": "pending", "position": 2, "printer_id": 1, "printer_name": "X1C Werkstatt",
     "archive_name": "Halterung", "print_time_seconds": 3600, "filament_type": "PETG"},
    {"id": 12, "status": "pending", "position": 1, "printer_id": None, "target_model": "A1 Mini",
     "library_file_name": "Schlüsselanhänger", "print_time_seconds": 900},
]
QUEUE_PRINTING: list[dict[str, Any]] = [
    {"id": 10, "status": "printing", "position": 0, "printer_id": 1, "printer_name": "X1C Werkstatt",
     "archive_name": "Benchy"},
]


def mock_bambuddy(aioclient_mock, *, status: dict[int, dict] | None = None, auth_status: int | None = None) -> None:
    """Register the fake Bambuddy endpoints."""
    aioclient_mock.clear_requests()
    if auth_status is not None:
        aioclient_mock.get(f"{API}/printers/", status=auth_status)
        aioclient_mock.get(f"{API}/queue/", status=auth_status)
        return
    status = status if status is not None else STATUS
    aioclient_mock.get(f"{API}/printers/", json=copy.deepcopy(PRINTERS))
    for printer_id, data in status.items():
        aioclient_mock.get(f"{API}/printers/{printer_id}/status", json=copy.deepcopy(data))
    aioclient_mock.get(f"{API}/queue/", params={"status": "pending"}, json=copy.deepcopy(QUEUE_PENDING))
    aioclient_mock.get(f"{API}/queue/", params={"status": "printing"}, json=copy.deepcopy(QUEUE_PRINTING))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield
