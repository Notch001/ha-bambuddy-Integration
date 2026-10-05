"""Base entities for Bambuddy."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from typing import Any, NoReturn

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import BambuddyAuthError, BambuddyError, BambuddyRequestError
from .const import ACTIVE_PRINT_STATES, DOMAIN, MAX_JOBS_IN_ATTRIBUTES
from .coordinator import BambuddyConfigEntry, BambuddyCoordinator, BambuddyData
from .planner import filament_check


def add_entities_when_seen(
    entry: BambuddyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    candidates: Callable[[], Iterable[tuple[str, Callable[[], Entity]]]],
) -> None:
    """Add entities now and whenever a new printer, AMS or spool shows up.

    ``candidates`` yields (stable key, factory) pairs for everything that
    should exist given the current data; each key is created once.
    """
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new() -> None:
        new = []
        for key, factory in candidates():
            if key not in known:
                known.add(key)
                new.append(factory())
        if new:
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


def raise_for_action(err: BambuddyError) -> NoReturn:
    """Turn a failed Bambuddy call into a message the user can act on."""
    if isinstance(err, BambuddyAuthError):
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="no_control_permission"
        ) from err
    if isinstance(err, BambuddyRequestError):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="action_rejected",
            translation_placeholders={"detail": str(err)},
        ) from err
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="cannot_connect",
        translation_placeholders={"detail": str(err)},
    ) from err


def is_printing(status: dict[str, Any] | None) -> bool:
    return bool(status) and status.get("state") in ACTIVE_PRINT_STATES


def job_name(item: dict[str, Any]) -> str | None:
    """Human readable name of a queue item."""
    return item.get("archive_name") or item.get("library_file_name")


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


def job_summary(item: dict[str, Any], data: BambuddyData | None = None) -> dict[str, Any]:
    """The subset of a queue item that is useful in Home Assistant.

    With the coordinator snapshot it also carries the schedule estimate and
    the filament check.
    """
    seconds = item.get("print_time_seconds")
    printer = item.get("printer_name")
    if printer is None and item.get("target_model"):
        printer = f"Any {item['target_model']}"
    summary = {
        "id": item.get("id"),
        "name": job_name(item),
        "status": item.get("status"),
        "printer": printer,
        "printer_id": item.get("printer_id"),
        "position": item.get("position"),
        "scheduled_time": item.get("scheduled_time"),
        "started_at": item.get("started_at"),
        "print_time_minutes": round(seconds / 60) if seconds else None,
        "filament_type": item.get("filament_type"),
        "filament_grams": item.get("filament_used_grams"),
        "manual_start": item.get("manual_start"),
        "waiting_reason": item.get("waiting_reason"),
        "filament_colors": [
            c.strip() for c in (item.get("filament_color") or "").split(",") if c.strip()
        ],
        "estimated_cost": item.get("estimated_cost"),
    }
    if data is None:
        return summary
    job_plan = data.plan.jobs.get(item.get("id"))
    planned_printer = job_plan.printer_id if job_plan else item.get("printer_id")
    check = filament_check(item, planned_printer, data.status)
    summary.update(
        {
            "estimated_start": _iso(job_plan.start) if job_plan else None,
            "estimated_end": _iso(job_plan.end) if job_plan else None,
            "planned_printer_id": planned_printer,
            "filament_ok": check["ok"],
            "filament_missing": check["missing"],
            "filament_short": check["short"],
        }
    )
    return summary


def jobs_attribute(
    items: list[dict[str, Any]], data: BambuddyData | None = None
) -> list[dict[str, Any]]:
    return [job_summary(item, data) for item in items[:MAX_JOBS_IN_ATTRIBUTES]]


def hub_device_info(coordinator: BambuddyCoordinator) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
        name="Bambuddy",
        manufacturer="Bambuddy",
        model="Print farm manager",
        configuration_url=coordinator.client.base_url,
    )


class BambuddyHubEntity(CoordinatorEntity[BambuddyCoordinator]):
    """Entity that belongs to the Bambuddy server itself (queue)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BambuddyCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_device_info = hub_device_info(coordinator)


class BambuddyPrinterEntity(CoordinatorEntity[BambuddyCoordinator]):
    """Entity that belongs to one printer."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BambuddyCoordinator, printer_id: int, key: str) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        self.printer_id = printer_id
        printer = coordinator.data.printers[printer_id]
        serial = printer["serial_number"]
        self._attr_unique_id = f"{serial}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=printer["name"],
            manufacturer="Bambu Lab",
            model=printer.get("model"),
            serial_number=serial,
            via_device=(DOMAIN, coordinator.config_entry.entry_id),
            configuration_url=coordinator.client.base_url,
        )

    @property
    def printer(self) -> dict[str, Any] | None:
        return self.coordinator.data.printers.get(self.printer_id)

    @property
    def status(self) -> dict[str, Any] | None:
        return self.coordinator.data.status.get(self.printer_id)

    @property
    def printer_queue(self) -> list[dict[str, Any]]:
        """Queue items pinned to this printer."""
        return [
            item
            for item in self.coordinator.data.queue
            if item.get("printer_id") == self.printer_id
        ]

    @property
    def available(self) -> bool:
        return super().available and self.printer is not None

    async def run_action(self, action: Callable[[], Awaitable[Any]]) -> None:
        """Run a control call, translate errors, then refresh the data."""
        try:
            await action()
        except BambuddyError as err:
            raise_for_action(err)
        await self.coordinator.async_request_refresh()
