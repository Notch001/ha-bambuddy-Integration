"""Print events per printer, for notifications and automations."""

from __future__ import annotations

from functools import partial
from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ACTIVE_PRINT_STATES
from .coordinator import BambuddyConfigEntry, BambuddyCoordinator
from .entity import BambuddyPrinterEntity, add_entities_when_seen, job_name

PARALLEL_UPDATES = 0

EVENT_TYPES = [
    "print_started",
    "print_finished",
    "print_failed",
    "plate_clear_required",
    "error",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BambuddyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data

    def candidates():
        for printer_id in coordinator.data.printers:
            yield (f"{printer_id}:events", partial(BambuddyPrintEvent, coordinator, printer_id))

    add_entities_when_seen(entry, async_add_entities, candidates)


def _snapshot(status: dict[str, Any] | None) -> dict[str, Any] | None:
    if not status or not status.get("connected"):
        return None
    return {
        "state": status.get("state"),
        "job": status.get("subtask_name") or status.get("current_print"),
        "plate": bool(status.get("awaiting_plate_clear")),
        "errors": len(status.get("hms_errors") or []),
    }


def detect_events(old: dict[str, Any] | None, new: dict[str, Any] | None) -> list[str]:
    """What happened between two polls. Nothing while either side is unknown."""
    if old is None or new is None:
        return []
    events = []
    was_active = old["state"] in ACTIVE_PRINT_STATES
    if new["state"] == "RUNNING" and not was_active:
        events.append("print_started")
    if new["state"] != old["state"]:
        if new["state"] == "FINISH" and was_active:
            events.append("print_finished")
        elif new["state"] == "FAILED":
            events.append("print_failed")
    if new["plate"] and not old["plate"]:
        events.append("plate_clear_required")
    if new["errors"] > old["errors"]:
        events.append("error")
    return events


class BambuddyPrintEvent(BambuddyPrinterEntity, EventEntity):
    """Fires print_started, print_finished, print_failed, plate_clear_required, error."""

    _attr_translation_key = "print_event"
    _attr_event_types = EVENT_TYPES

    def __init__(self, coordinator: BambuddyCoordinator, printer_id: int) -> None:
        super().__init__(coordinator, printer_id, "events")
        self._last = _snapshot(self.status)

    @callback
    def _handle_coordinator_update(self) -> None:
        current = _snapshot(self.status)
        events = detect_events(self._last, current)
        if current is not None:
            self._last = current
        if events:
            pending = [
                i for i in self.printer_queue if i.get("status") == "pending"
            ]
            attributes = {
                "printer": (self.printer or {}).get("name"),
                "job": (current or {}).get("job") or (self._last or {}).get("job"),
                "next_job": job_name(pending[0]) if pending else None,
                "queue_length": len(pending),
            }
            for event in events:
                # One state write per event, or automations only see the last one.
                self._trigger_event(event, attributes)
                self.async_write_ha_state()
        super()._handle_coordinator_update()
