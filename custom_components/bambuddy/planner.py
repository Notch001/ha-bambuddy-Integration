"""Estimates when queued jobs run and whether the right filament is loaded.

Pure functions over the coordinator snapshot, so they are easy to test and
every entity reads the same answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from .const import ACTIVE_PRINT_STATES

# Below these temperatures a printer counts as cooled down (see in_use()).
COOL_NOZZLE_C = 50
COOL_BED_C = 40


@dataclass
class JobPlan:
    printer_id: int | None  # where it is expected to run (predicted for "any <model>" jobs)
    start: datetime | None
    end: datetime | None
    predicted: bool = False


@dataclass
class Plan:
    jobs: dict[int, JobPlan] = field(default_factory=dict)
    # printer id -> when everything known for it is done; None = free now / unknown
    free_at: dict[int, datetime | None] = field(default_factory=dict)
    # printer id -> [(job id, start, end)] in order, including the running print as job id None
    schedule: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    farm_done_at: datetime | None = None


def _minute(value: datetime) -> datetime:
    return value.replace(second=0, microsecond=0)


def _future_time(raw: str | None, now: datetime) -> datetime | None:
    if not raw:
        return None
    parsed = dt_util.parse_datetime(raw)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.UTC)
    return parsed if parsed > now else None


def build_plan(
    printers: dict[int, dict[str, Any]],
    status: dict[int, dict[str, Any] | None],
    queue: list[dict[str, Any]],
    now: datetime | None = None,
) -> Plan:
    """Walk the queue in dispatch order and stack jobs per printer.

    A printer is busy until its running print's remaining time is over; a job
    pinned to a printer starts when that printer is free (or at its scheduled
    time, if later); an "any <model>" job goes to whichever printer of that
    model is free first. Jobs without a print time make later times for that
    printer unknown. Unassigned jobs without a model get no estimate.
    """
    now = now or dt_util.utcnow()
    plan = Plan()
    # None in free means "unknown from here on" for that printer.
    free: dict[int, datetime | None] = {}
    for printer_id in printers:
        st = status.get(printer_id) or {}
        plan.schedule[printer_id] = []
        if st.get("state") in ACTIVE_PRINT_STATES and st.get("remaining_time") is not None:
            end = _minute(now + timedelta(minutes=st["remaining_time"]))
            free[printer_id] = end
            plan.schedule[printer_id].append(
                {"id": None, "name": st.get("subtask_name") or st.get("current_print"),
                 "start": now, "end": end, "running": True}
            )
        else:
            free[printer_id] = now

    for item in queue:
        if item.get("status") != "pending":
            continue
        job_id = item.get("id")
        printer_id = item.get("printer_id")
        predicted = False
        if printer_id is None and item.get("target_model"):
            model = item["target_model"].lower()
            candidates = [
                pid for pid, p in printers.items() if (p.get("model") or "").lower() == model
            ]
            known = [pid for pid in candidates if free.get(pid) is not None]
            if known:
                printer_id = min(known, key=lambda pid: free[pid])
                predicted = True
        if printer_id not in free:
            plan.jobs[job_id] = JobPlan(None, None, None)
            continue
        start = free[printer_id]
        if start is not None:
            scheduled = _future_time(item.get("scheduled_time"), now)
            if scheduled and scheduled > start:
                start = scheduled
        seconds = item.get("print_time_seconds")
        end = start + timedelta(seconds=seconds) if start is not None and seconds else None
        free[printer_id] = end
        plan.jobs[job_id] = JobPlan(printer_id, start, end, predicted)
        plan.schedule[printer_id].append(
            {"id": job_id, "name": item.get("archive_name") or item.get("library_file_name"),
             "start": start, "end": end, "running": False, "predicted": predicted}
        )

    for printer_id, value in free.items():
        busy = bool(plan.schedule[printer_id])
        plan.free_at[printer_id] = value if busy else None
    ends = [v for v in plan.free_at.values() if v is not None]
    plan.farm_done_at = max(ends) if ends else None
    return plan


def loaded_filament_types(status: dict[str, Any] | None) -> set[str]:
    """Filament types currently loaded in the AMS units and on the external holder."""
    types: set[str] = set()
    status = status or {}
    trays = [t for unit in status.get("ams") or [] for t in unit.get("tray") or []]
    trays += status.get("vt_tray") or []
    for tray in trays:
        if tray.get("exists") is False or tray.get("state") == 9:
            continue
        if tray.get("tray_type"):
            types.add(tray["tray_type"].strip().upper())
    return types


def required_filament_types(item: dict[str, Any]) -> list[str]:
    raw = item.get("required_filament_types") or (item.get("filament_type") or "").split(",")
    return sorted({t.strip().upper() for t in raw if t and t.strip()})


def filament_check(
    item: dict[str, Any], printer_id: int | None, status: dict[int, dict[str, Any] | None]
) -> dict[str, Any]:
    """Which of the job's filament types are not loaded on the printer it will run on.

    ``ok`` is None when it cannot be told (no printer yet, printer offline,
    job without filament info). Bambuddy's own "not enough grams on the spool"
    verdict is passed through as ``short``.
    """
    required = required_filament_types(item)
    printer_status = status.get(printer_id) if printer_id is not None else None
    if not required or not printer_status or not printer_status.get("connected"):
        return {"ok": None, "missing": [], "short": bool(item.get("filament_short"))}
    loaded = loaded_filament_types(printer_status)
    missing = [t for t in required if t not in loaded]
    return {"ok": not missing, "missing": missing, "short": bool(item.get("filament_short"))}


def in_use(
    printer_id: int, status: dict[str, Any] | None, plan: Plan
) -> bool:
    """Whether the printer is needed: printing, has work planned, or still hot.

    Off means it can be switched off safely; used by the auto-power blueprint.
    """
    if plan.schedule.get(printer_id):
        return True
    st = status or {}
    if not st.get("connected"):
        return False
    if st.get("state") in ACTIVE_PRINT_STATES:
        return True
    temps = st.get("temperatures") or {}
    return (temps.get("nozzle") or 0) >= COOL_NOZZLE_C or (temps.get("bed") or 0) >= COOL_BED_C
