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
        "speed_level": 2,
        "chamber_light": False,
        "stg_cur": 2,
        "stg_cur_name": "Heatbed preheating",
        "cooling_fan_speed": 100,
        "big_fan1_speed": 0,
        "big_fan2_speed": None,
        "nozzles": [{"nozzle_type": "hardened_steel", "nozzle_diameter": "0.4"}],
        "supports_drying": False,
        "tray_now": 1,
        "ams": [
            {
                "id": 0, "humidity": 23, "temp": 26.5, "is_ams_ht": False, "dry_time": 0,
                "tray": [
                    {"id": 0, "tray_type": "PLA", "tray_sub_brands": "PLA Basic", "tray_color": "FF0000FF", "remain": 80, "state": 11, "exists": True},
                    {"id": 1, "tray_type": "PETG", "tray_sub_brands": "PETG HF", "tray_color": "00AE42FF", "remain": -1, "state": 11, "exists": True},
                    {"id": 2, "tray_type": "", "tray_color": "", "remain": 0, "state": 9, "exists": False},
                    {"id": 3, "tray_type": "", "tray_color": "", "remain": 0, "state": 10, "exists": True},
                ],
            }
        ],
        "vt_tray": [{"id": 254, "tray_type": "TPU", "tray_color": "000000FF", "remain": 0}],
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


STATS: dict[str, Any] = {
    "total_prints": 120, "successful_prints": 100, "failed_prints": 20, "cancelled_prints": 3,
    "total_print_time_hours": 480.5, "total_filament_grams": 9876.5, "total_cost": 210.4,
    "prints_by_filament_type": {"PLA": 90, "PETG": 30}, "prints_by_printer": {"1": 80, "2": 40},
    "printer_names": {"1": "X1C Werkstatt", "2": "A1 Mini"},
    "total_energy_kwh": 55.2, "total_energy_cost": 17.1,
}


def mock_bambuddy(aioclient_mock, *, status: dict[int, dict] | None = None, auth_status: int | None = None) -> None:
    """Register the fake Bambuddy endpoints."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/api/status", status=404)  # backend detection: not PrintDog
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
    aioclient_mock.get(f"{API}/archives/stats", json=copy.deepcopy(STATS))
    aioclient_mock.get(f"{API}/settings/ui-flags", json={"currency": "EUR"})
    aioclient_mock.get(f"{API}/inventory/colors/map", json={
        "colors": {"ff0000": "Red", "00ae42": "Bambu Green", "ffffff": "Jade White"},
        "by_material": {"pla matte|ffffff": "Ivory White"},
    })
    aioclient_mock.get(f"{API}/printers/1/cover", content=b"PNGDATA", headers={"Content-Type": "image/png"})
    aioclient_mock.post(f"{API}/printers/camera/stream-token", json={"token": "camtoken"})
    aioclient_mock.get(f"{API}/printers/1/camera/snapshot", params={"token": "camtoken"}, content=b"JPEGDATA")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


# --------------------------------------------------------------------------- PrintDog

PD_URL = "http://192.168.200.86:8090"
PD_API = f"{PD_URL}/api"
PD_KEY = "pd_testkey"
PD_SERIAL = "01S00C123456789"

PD_DETAIL: dict[str, Any] = {
    "id": 1, "name": "P1P", "model": "P1P", "serial": PD_SERIAL, "online": True, "state": "running", "label": "Druckt",
    "printing": True, "progress": 42, "remaining_min": 83, "file": "Eule_Beige", "layer": 50, "layers": 120,
    "nozzle": 219.6, "nozzle_target": 220.0, "bed": 54.9, "bed_target": 55.0, "chamber": 32.0, "nozzle_diameter": 0.4,
    "light": True, "speed_level": 2, "stage": 255, "plate_free": False, "awaiting_plate_clear": False,
    "hms": [{"code": "0C00030000020001", "module": 12, "severity": 2}], "sdcard": True, "timelapse": False,
    "door_open": None, "tray_now": 0,
    "ams_units": [{
        "id": 0, "humidity": 4, "humidity_pct": 31, "temp": 26.5, "dry_time": 0, "ht": False,
        "trays": [
            {"id": 0, "exists": True, "type": "PLA", "name": "PLA Basic", "color": "#F5E6C8", "remain": 80, "k": 0.02,
             "nozzle_temp_min": 190, "nozzle_temp_max": 230},
            {"id": 1, "exists": False, "type": "", "name": "", "color": "", "remain": None, "k": None,
             "nozzle_temp_min": None, "nozzle_temp_max": None},
        ],
    }],
    "external": [{"id": 254, "exists": True, "type": "PETG", "name": "", "color": "#000000", "remain": None, "k": None,
                  "nozzle_temp_min": None, "nozzle_temp_max": None}],
}
PD_API_DATA: dict[str, Any] = {
    "detail": PD_DETAIL,
    "printers": [{"id": 1, "name": "P1P", "model": "P1P", "serial": PD_SERIAL}],
    "queue": [
        {"id": 10, "status": "printing", "printer_id": 1, "printer_name": "P1P", "position": 0, "name": "Eule",
         "label": "DM-2026-001 · Eule", "print_time_s": 5025, "filament_grams": 14.7, "filament_types": ["PLA"],
         "filament_colors": ["#F5E6C8"], "started_at": "2026-10-10T08:00:00Z"},
        {"id": 11, "status": "queued", "printer_id": 1, "printer_name": "P1P", "position": 1, "name": "Eule",
         "label": "DM-2026-001 · Eule", "print_time_s": 5025, "filament_grams": 14.7, "filament_types": ["PLA"],
         "filament_colors": ["#F5E6C8"]},
        {"id": 21, "status": "queued", "printer_id": 1, "printer_name": "P1P", "position": 2, "name": "Fuchs",
         "label": None, "print_time_s": 900, "filament_grams": 3.0, "filament_types": ["PETG"], "filament_colors": []},
    ],
    "stats": {"total_prints": 12, "successful_prints": 10, "failed_prints": 1, "cancelled_prints": 1,
              "total_print_time_hours": 48.5, "total_filament_grams": 987.6, "total_energy_kwh": 5.2,
              "printer_names": {"1": "P1P"}, "prints_by_printer": {"1": 12}, "prints_by_filament_type": {"PLA": 12}},
    "files": [{"id": 5, "name": "Eule", "printer_model": "P1P", "plates": []}],
    "history": [{"id": 7, "name": "Eule", "printer_id": 1, "plate": 1, "status": "finished"}],
}
PD_API = f"{PD_URL}/api"


def mock_printdog(aioclient_mock) -> None:
    """Register the fake PrintDog endpoints."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{PD_API}/status", json={"app": "printdog", "version": "0.9.1", "printers": 1, "online": 1})
    aioclient_mock.get(f"{PD_API}/printers", json=copy.deepcopy(PD_API_DATA["printers"]))
    aioclient_mock.get(f"{PD_API}/printers/1/detail", json=copy.deepcopy(PD_API_DATA["detail"]))
    aioclient_mock.get(f"{PD_API}/queue", json=copy.deepcopy(PD_API_DATA["queue"]))
    aioclient_mock.get(f"{PD_API}/stats", json=copy.deepcopy(PD_API_DATA["stats"]))
    aioclient_mock.get(f"{PD_API}/files", json=copy.deepcopy(PD_API_DATA["files"]))
    aioclient_mock.get(f"{PD_API}/history", json=copy.deepcopy(PD_API_DATA["history"]))
    aioclient_mock.get(f"{PD_API}/printers/1/preview.png", content=b"PNGDATA", headers={"Content-Type": "image/png"})
    aioclient_mock.get(f"{PD_API}/printers/1/camera.jpg", content=b"JPEGDATA")
    for command in ("pause", "resume", "stop", "light_on", "light_off", "speed_1", "speed_2", "speed_3", "speed_4"):
        aioclient_mock.post(f"{PD_API}/printers/1/command/{command}", json={"sent": True})
    aioclient_mock.post(f"{PD_API}/printers/1/plate-cleared", json={"plate_free": True})
    aioclient_mock.post(f"{PD_API}/queue/reorder", json={"reordered": True})
    aioclient_mock.post(f"{PD_API}/jobs", json={"jobs": [{"id": 300}], "mapping": {}, "notes": []})
    aioclient_mock.post(f"{PD_API}/jobs/7/requeue", json={"id": 301})
    aioclient_mock.delete(f"{PD_API}/jobs/11", json={"deleted": True})
