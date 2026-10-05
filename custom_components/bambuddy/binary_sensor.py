"""Binary sensors for Bambuddy printers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BambuddyConfigEntry, BambuddyCoordinator
from .entity import BambuddyPrinterEntity, add_entities_when_seen

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BambuddyBinarySensorDescription(BinarySensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], bool | None]


BINARY_SENSORS: tuple[BambuddyBinarySensorDescription, ...] = (
    BambuddyBinarySensorDescription(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda s: bool(s.get("connected")),
    ),
    BambuddyBinarySensorDescription(
        key="printing",
        translation_key="printing",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda s: s.get("state") in ("PREPARE", "SLICING", "RUNNING"),
    ),
    BambuddyBinarySensorDescription(
        key="error",
        translation_key="error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda s: bool(s.get("hms_errors")) or s.get("state") == "FAILED",
    ),
    BambuddyBinarySensorDescription(
        key="awaiting_plate_clear",
        translation_key="awaiting_plate_clear",
        value_fn=lambda s: bool(s.get("awaiting_plate_clear")),
    ),
    BambuddyBinarySensorDescription(
        key="door",
        translation_key="door",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_registry_enabled_default=False,
        value_fn=lambda s: bool(s.get("door_open")),
    ),
    BambuddyBinarySensorDescription(
        key="sdcard",
        translation_key="sdcard",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda s: bool(s.get("sdcard")),
    ),
    BambuddyBinarySensorDescription(
        key="timelapse",
        translation_key="timelapse",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda s: bool(s.get("timelapse")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BambuddyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data

    def candidates():
        for printer_id in coordinator.data.printers:
            for description in BINARY_SENSORS:
                yield (
                    f"{printer_id}:{description.key}",
                    partial(BambuddyBinarySensor, coordinator, printer_id, description),
                )

    add_entities_when_seen(entry, async_add_entities, candidates)


class BambuddyBinarySensor(BambuddyPrinterEntity, BinarySensorEntity):
    entity_description: BambuddyBinarySensorDescription

    def __init__(
        self,
        coordinator: BambuddyCoordinator,
        printer_id: int,
        description: BambuddyBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator, printer_id, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        # "Online" stays available so it can say "off" when Bambuddy has no status.
        if self.entity_description.key == "online":
            return super().available
        return super().available and self.status is not None

    @property
    def is_on(self) -> bool | None:
        status = self.status
        if status is None:
            return False if self.entity_description.key == "online" else None
        return self.entity_description.value_fn(status)
