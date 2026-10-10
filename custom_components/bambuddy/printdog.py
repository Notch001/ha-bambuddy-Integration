"""PrintDog backend: translates PrintDog's REST API into the Bambuddy-shaped data the entities read.

PrintDog (https://github.com/Notch001/werkbank, folder ``printdog/``) is the printer service of the Dammer Manufaktur
workshop. It exposes printer details, controls, camera, queue and statistics under ``/api`` with the same
``X-API-Key`` header. Everything below the client (coordinator, entities, card, blueprints) stays unchanged: the
client returns the dicts the Bambuddy API would have returned. Fields PrintDog cannot supply stay absent or ``None``,
so the matching entities simply do not appear.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

import aiohttp

from .api import BambuddyApiClient, BambuddyRequestError, normalize_url

BACKEND_PRINTDOG = "printdog"
SPEED_MODES = {1, 2, 3, 4}


def _rgba(color: str | None) -> str:
    """PrintDog reports #RRGGBB; the entities expect Bambu's RRGGBBAA."""
    color = (color or "").lstrip("#")
    return f"{color.upper()}FF" if len(color) == 6 else ""


def _tray(tray: dict[str, Any]) -> dict[str, Any]:
    exists = bool(tray.get("exists"))
    return {
        "id": tray.get("id"),
        "tray_type": tray.get("type") or "",
        "tray_sub_brands": tray.get("name") or "",
        "tray_color": _rgba(tray.get("color")),
        "remain": tray.get("remain") if tray.get("remain") is not None else -1,
        "exists": exists,
        "state": 11 if exists else 9,
        "k": tray.get("k"),
        "nozzle_temp_min": tray.get("nozzle_temp_min"),
        "nozzle_temp_max": tray.get("nozzle_temp_max"),
    }


def status_from_detail(detail: dict[str, Any]) -> dict[str, Any]:
    """PrintDog ``/api/printers/{id}/detail`` -> Bambuddy ``/printers/{id}/status``."""
    connected = bool(detail.get("online"))
    state = (detail.get("state") or "").upper()
    if not connected or state in ("OFFLINE", "UNKNOWN"):
        state = "IDLE"
    temperatures = {
        "nozzle": detail.get("nozzle"), "nozzle_target": detail.get("nozzle_target"),
        "bed": detail.get("bed"), "bed_target": detail.get("bed_target"),
    }
    if detail.get("chamber") is not None:
        temperatures["chamber"] = detail["chamber"]
    ams = [
        {
            "id": unit.get("id"), "humidity": unit.get("humidity_pct"), "temp": unit.get("temp"),
            "is_ams_ht": bool(unit.get("ht")), "dry_time": unit.get("dry_time") or 0,
            "tray": [_tray(t) for t in unit.get("trays") or []],
        }
        for unit in detail.get("ams_units") or []
    ]
    result = {
        "id": detail.get("id"), "name": detail.get("name"), "connected": connected, "state": state,
        "subtask_name": detail.get("file") or None, "current_print": detail.get("file") or None,
        "progress": detail.get("progress"), "remaining_time": detail.get("remaining_min"),
        "layer_num": detail.get("layer"), "total_layers": detail.get("layers"),
        "temperatures": {k: v for k, v in temperatures.items() if v is not None},
        "hms_errors": [
            {"code": e.get("code"), "severity": e.get("severity"), "module": e.get("module")}
            for e in detail.get("hms") or []
        ],
        "awaiting_plate_clear": bool(detail.get("awaiting_plate_clear")),
        "speed_level": detail.get("speed_level"), "chamber_light": detail.get("light"),
        "stg_cur": detail.get("stage") if detail.get("stage") is not None else -1,
        "tray_now": detail.get("tray_now"), "ams": ams,
        "vt_tray": [_tray(t) for t in detail.get("external") or []],
        "sdcard": detail.get("sdcard"), "timelapse": detail.get("timelapse"),
        "supports_drying": False,
    }
    if detail.get("door_open") is not None:
        result["door_open"] = detail["door_open"]
    if detail.get("nozzle_diameter"):
        result["nozzles"] = [{"nozzle_diameter": str(detail["nozzle_diameter"])}]
    return result


def queue_item(job: dict[str, Any]) -> dict[str, Any]:
    """PrintDog ``/api/queue`` entry -> Bambuddy queue item."""
    running = job.get("status") != "queued"
    return {
        "id": job.get("id"), "status": "printing" if running else "pending", "position": job.get("position") or 0,
        "printer_id": job.get("printer_id"), "printer_name": job.get("printer_name"),
        "archive_name": job.get("label") or job.get("name"),
        "print_time_seconds": job.get("print_time_s"), "started_at": job.get("started_at"),
        "filament_type": ",".join(job.get("filament_types") or []) or None,
        "filament_used_grams": job.get("filament_grams"),
        "filament_color": ",".join(job.get("filament_colors") or []) or None,
    }


class PrintDogApiClient(BambuddyApiClient):
    """Talks to one PrintDog instance (same interface as the Bambuddy client)."""

    api_prefix = "/api"
    backend = BACKEND_PRINTDOG

    async def get_printers(self) -> list[dict[str, Any]]:
        return [
            {"id": p["id"], "name": p.get("name"), "serial_number": p.get("serial"), "model": p.get("model")}
            for p in await self._get("/printers")
        ]

    async def get_printer_status(self, printer_id: int) -> dict[str, Any]:
        return status_from_detail(await self._get(f"/printers/{printer_id}/detail"))

    async def get_queue(self, status: str | None = None) -> list[dict[str, Any]]:
        items = [queue_item(j) for j in await self._get("/queue")]
        return [i for i in items if status is None or i["status"] == status]

    async def get_stats(self, date_from: str | None = None) -> dict[str, Any]:
        return await self._get("/stats", {"date_from": date_from} if date_from else None)

    async def get_ui_flags(self) -> dict[str, Any]:
        return {"currency": "EUR"}

    async def get_color_map(self) -> dict[str, Any]:
        return {}

    async def list_archives(self, limit: int = 200) -> list[dict[str, Any]]:
        jobs = await self._get("/history", {"limit": limit})
        return [{"id": j["id"], "print_name": j.get("name"), "filename": j.get("name"),
                 "printer_id": j.get("printer_id"), "plate_id": j.get("plate")} for j in jobs]

    async def list_library_files(self) -> list[dict[str, Any]]:
        return [{"id": f["id"], "filename": f["name"]} for f in await self._get("/files")]

    async def add_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("archive_id") is not None:                 # "print again" = requeue the finished job
            return await self._post(f"/jobs/{payload['archive_id']}/requeue")
        if payload.get("library_file_id") is None or payload.get("printer_id") is None:
            raise BambuddyRequestError("PrintDog needs a file and a printer")
        data = await self._request(
            "POST", "/jobs",
            json={"file_id": payload["library_file_id"], "printer_id": payload["printer_id"], "plate": 1},
        )
        jobs = data.get("jobs") or []
        return {"id": jobs[0]["id"] if jobs else None}

    async def reorder_queue(self, positions: list[tuple[int, int]]) -> None:
        printers = {i["id"]: i["printer_id"] for i in await self.get_queue("pending")}
        groups: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for job_id, position in positions:
            if printers.get(job_id) is not None:
                groups[printers[job_id]].append((position, job_id))
        for printer_id, items in groups.items():
            await self._request(
                "POST", "/queue/reorder",
                json={"printer_id": printer_id, "order": [job_id for _, job_id in sorted(items)]},
            )

    async def cancel_job(self, job_id: int) -> None:
        await self._request("DELETE", f"/jobs/{job_id}")

    async def start_job(self, job_id: int) -> None:
        raise BambuddyRequestError(
            "PrintDog starts queued jobs only after \"build plate cleared\" (use the clear_plate action)"
        )

    async def get_cover(self, printer_id: int) -> tuple[bytes, str]:
        return await self._request("GET", f"/printers/{printer_id}/preview.png", raw=True)

    async def get_camera_snapshot(self, printer_id: int) -> bytes:
        data, _ = await self._request(
            "GET", f"/printers/{printer_id}/camera.jpg", raw=True, timeout=30
        )
        return data

    async def camera_stream_url(self, printer_id: int) -> str:
        raise BambuddyRequestError("PrintDog provides camera snapshots only")

    async def pause(self, printer_id: int) -> None:
        await self._post(f"/printers/{printer_id}/command/pause")

    async def resume(self, printer_id: int) -> None:
        await self._post(f"/printers/{printer_id}/command/resume")

    async def stop(self, printer_id: int) -> None:
        await self._post(f"/printers/{printer_id}/command/stop")

    async def clear_plate(self, printer_id: int) -> None:
        await self._post(f"/printers/{printer_id}/plate-cleared")

    async def set_chamber_light(self, printer_id: int, on: bool) -> None:
        await self._post(f"/printers/{printer_id}/command/{'light_on' if on else 'light_off'}")

    async def set_print_speed(self, printer_id: int, mode: int) -> None:
        if mode not in SPEED_MODES:
            raise BambuddyRequestError("Unknown print speed")
        await self._post(f"/printers/{printer_id}/command/speed_{mode}")


async def detect_backend(session: aiohttp.ClientSession, url: str, api_key: str | None) -> str:
    """"printdog" if the server answers like PrintDog (``GET /api/status`` with ``"app": "printdog"``), else "bambuddy".

    PrintDog's German "API-Schlüssel" 401 counts too, so a wrong key is reported as an auth error against PrintDog
    instead of "cannot connect".
    """
    headers = {"X-API-Key": api_key} if api_key else {}
    try:
        async with asyncio.timeout(10):
            async with session.get(f"{normalize_url(url)}/api/status", headers=headers) as resp:
                data = await resp.json(content_type=None) if resp.status in (200, 401, 403) else None
                if resp.status == 200 and isinstance(data, dict) and data.get("app") == "printdog":
                    return BACKEND_PRINTDOG
                if resp.status in (401, 403) and isinstance(data, dict) and "API-Schl" in str(data.get("detail", "")):
                    return BACKEND_PRINTDOG
    except (aiohttp.ClientError, TimeoutError, ValueError):
        pass
    return "bambuddy"
