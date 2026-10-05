"""Base entities for Bambuddy."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MAX_JOBS_IN_ATTRIBUTES
from .coordinator import BambuddyCoordinator


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
        super().__init__(coordinator)
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
