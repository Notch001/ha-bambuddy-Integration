"""Schedule estimates, filament check, in-use and print events (pure logic)."""

from datetime import UTC, datetime, timedelta

from custom_components.bambuddy.event import detect_events
from custom_components.bambuddy.planner import build_plan, filament_check, in_use

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
PRINTERS = {
    1: {"id": 1, "model": "X1C"},
    2: {"id": 2, "model": "A1 Mini"},
    3: {"id": 3, "model": "A1 Mini"},
}


def _status(state="IDLE", remaining=None, connected=True, **extra):
    return {"connected": connected, "state": state, "remaining_time": remaining, **extra}


def test_jobs_stack_after_running_print_and_by_model() -> None:
    status = {1: _status("RUNNING", 30), 2: _status("RUNNING", 120), 3: _status()}
    queue = [
        {"id": 10, "status": "printing", "printer_id": 1},
        {"id": 11, "status": "pending", "printer_id": 1, "print_time_seconds": 3600},
        {"id": 12, "status": "pending", "printer_id": 1, "print_time_seconds": 600},
        # "Any A1 Mini": goes to printer 3, which is free now
        {"id": 13, "status": "pending", "printer_id": None, "target_model": "A1 Mini", "print_time_seconds": 1800},
        # next one: printer 3 is busy until 12:30, printer 2 until 14:00 -> 3 again
        {"id": 14, "status": "pending", "printer_id": None, "target_model": "a1 mini", "print_time_seconds": 1800},
        # unassigned, no model: no estimate
        {"id": 15, "status": "pending", "printer_id": None},
    ]
    plan = build_plan(PRINTERS, status, queue, NOW)

    assert plan.jobs[11].start == NOW + timedelta(minutes=30)
    assert plan.jobs[11].end == NOW + timedelta(minutes=90)
    assert plan.jobs[12].start == NOW + timedelta(minutes=90)
    assert plan.jobs[13].printer_id == 3 and plan.jobs[13].predicted
    assert plan.jobs[13].start == NOW
    assert plan.jobs[14].printer_id == 3 and plan.jobs[14].start == NOW + timedelta(minutes=30)
    assert plan.jobs[15].start is None
    assert plan.free_at[1] == NOW + timedelta(minutes=100)
    assert plan.free_at[2] == NOW + timedelta(minutes=120)
    assert plan.farm_done_at == NOW + timedelta(minutes=120)
    assert [e["running"] for e in plan.schedule[1]] == [True, False, False]


def test_scheduled_time_and_unknown_duration() -> None:
    status = {1: _status(), 2: _status(), 3: _status()}
    later = NOW + timedelta(hours=3)
    queue = [
        {"id": 1, "status": "pending", "printer_id": 1, "print_time_seconds": 600,
         "scheduled_time": later.isoformat()},
        {"id": 2, "status": "pending", "printer_id": 2},  # no print time
        {"id": 3, "status": "pending", "printer_id": 2, "print_time_seconds": 600},
    ]
    plan = build_plan(PRINTERS, status, queue, NOW)
    assert plan.jobs[1].start == later
    assert plan.jobs[2].start == NOW and plan.jobs[2].end is None
    # After a job of unknown length, later times for that printer are unknown
    assert plan.jobs[3].start is None
    assert plan.free_at[3] is None  # idle, nothing planned


def test_filament_check() -> None:
    status = {
        1: _status(ams=[{"tray": [{"tray_type": "PLA"}, {"tray_type": "", "state": 9}]}],
                   vt_tray=[{"tray_type": "TPU"}]),
        2: _status(connected=False),
    }
    job = {"filament_type": "PLA, PETG", "filament_short": True}
    assert filament_check(job, 1, status) == {"ok": False, "missing": ["PETG"], "short": True}
    assert filament_check({"filament_type": "pla"}, 1, status)["ok"] is True
    assert filament_check({"required_filament_types": ["TPU"]}, 1, status)["ok"] is True
    # Offline printer or no printer yet: can't tell
    assert filament_check(job, 2, status)["ok"] is None
    assert filament_check(job, None, status)["ok"] is None


def test_in_use() -> None:
    status = {1: _status(temperatures={"nozzle": 30, "bed": 25}), 2: _status(temperatures={"nozzle": 180})}
    queue = [{"id": 1, "status": "pending", "printer_id": 3, "print_time_seconds": 60}]
    plan = build_plan(PRINTERS, {**status, 3: _status(connected=False)}, queue, NOW)
    assert in_use(1, status[1], plan) is False  # idle and cool -> may be switched off
    assert in_use(2, status[2], plan) is True  # still hot
    assert in_use(3, None, plan) is True  # switched off, but a job is waiting for it


def test_detect_events() -> None:
    base = {"state": "IDLE", "job": None, "plate": False, "errors": 0}
    running = {**base, "state": "RUNNING", "job": "Benchy"}
    assert detect_events(None, running) == []
    assert detect_events(base, running) == ["print_started"]
    assert detect_events({**base, "state": "PAUSE"}, running) == []  # resume is not a start
    assert detect_events(running, {**running, "state": "FINISH", "plate": True}) == [
        "print_finished",
        "plate_clear_required",
    ]
    assert detect_events(running, {**running, "state": "FAILED", "errors": 1}) == ["print_failed", "error"]
