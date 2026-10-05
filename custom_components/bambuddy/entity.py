"""Base entities for Bambuddy."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import BambuddyAuthError, BambuddyError, BambuddyRequestError
from .const import ACTIVE_PRINT_STATES, DOMAIN, MAX_JOBS_IN_ATTRIBUTES
from .coordinator import BambuddyConfigEntry, BambuddyCoordinator


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


def is_printing(status: dict[str, Any] | None) -> bool:
    return bool(status) and status.get("state") in ACTIVE_PRINT_STATES


def job_name(item: dict[str, Any]) -> str | None:
    """Human readable name of a queue item."""
    return item.get("archive_name") or item.get("library_file_name")


def job_summary(item: dict[str, Any]) -> dict[str, Any]:
    """The subset of a queue item that is useful in Home Assistant."""
    seconds = item.get("print_time_seconds")
    printer = item.get("printer_name")
    if printer is None and item.get("target_model"):
        printer = f"Any {item['target_model']}"
    return {
        "id": item.get("id"),
        "name": job_name(item),
        "status": item.get("status"),
        "printer": printer,
        "position": item.get("position"),
        "scheduled_time": item.get("scheduled_time"),
        "started_at": item.get("started_at"),
        "print_time_minutes": round(seconds / 60) if seconds else None,
        "filament_type": item.get("filament_type"),
        "filament_grams": item.get("filament_used_grams"),
        "manual_start": item.get("manual_start"),
        "waiting_reason": item.get("waiting_reason"),
    }


def jobs_attribute(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [job_summary(item) for item in items[:MAX_JOBS_IN_ATTRIBUTES]]


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
        except BambuddyAuthError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="no_control_permission"
            ) from err
        except BambuddyRequestError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="action_rejected",
                translation_placeholders={"detail": str(err)},
            ) from err
        except BambuddyError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"detail": str(err)},
            ) from err
        await self.coordinator.async_request_refresh()
