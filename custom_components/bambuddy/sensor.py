"""Sensors for Bambuddy printers and the print queue."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import ACTIVE_PRINT_STATES
from .coordinator import BambuddyConfigEntry, BambuddyCoordinator
from .entity import (
    BambuddyHubEntity,
    BambuddyPrinterEntity,
    job_name,
    jobs_attribute,
)

PARALLEL_UPDATES = 0


def _temperature(key: str) -> Callable[[BambuddyPrinterEntity], Any]:
    def value(entity: BambuddyPrinterEntity) -> Any:
        status = entity.status or {}
        return (status.get("temperatures") or {}).get(key)

    return value


def _has_temperature(key: str) -> Callable[[dict[str, Any] | None], bool]:
    def exists(status: dict[str, Any] | None) -> bool:
        return key in ((status or {}).get("temperatures") or {})

    return exists


def _printer_state(entity: BambuddyPrinterEntity) -> str | None:
    status = entity.status
    if status is None:
        return None
    if not status.get("connected"):
        return "offline"
    return (status.get("state") or "unknown").lower()


def _is_printing(status: dict[str, Any] | None) -> bool:
    return bool(status) and status.get("state") in ACTIVE_PRINT_STATES


def _current_print(entity: BambuddyPrinterEntity) -> str | None:
    status = entity.status
    if not _is_printing(status):
        return None
    return status.get("subtask_name") or status.get("current_print")


def _end_time(entity: BambuddyPrinterEntity) -> datetime | None:
    status = entity.status
    if not _is_printing(status) or not status.get("remaining_time"):
        return None
    end = dt_util.utcnow() + timedelta(minutes=status["remaining_time"])
    # Round to the minute so the state doesn't change on every poll.
    return end.replace(second=0, microsecond=0)


def _status_field(key: str) -> Callable[[BambuddyPrinterEntity], Any]:
    return lambda entity: (entity.status or {}).get(key)


def _while_printing(key: str) -> Callable[[BambuddyPrinterEntity], Any]:
    def value(entity: BambuddyPrinterEntity) -> Any:
        status = entity.status
        return status.get(key) if _is_printing(status) else None

    return value


def _next_job_attrs(entity: BambuddyPrinterEntity) -> dict[str, Any]:
    pending = [i for i in entity.printer_queue if i.get("status") == "pending"]
    return {
        "next_job": job_name(pending[0]) if pending else None,
        "jobs": jobs_attribute(pending),
    }


def _hms_attrs(entity: BambuddyPrinterEntity) -> dict[str, Any]:
    errors = (entity.status or {}).get("hms_errors") or []
    return {
        "errors": [
            {"code": e.get("code"), "severity": e.get("severity"), "module": e.get("module")}
            for e in errors
        ]
    }


@dataclass(frozen=True, kw_only=True)
class BambuddyPrinterSensorDescription(SensorEntityDescription):
    value_fn: Callable[[BambuddyPrinterEntity], Any]
    attrs_fn: Callable[[BambuddyPrinterEntity], dict[str, Any]] | None = None
    # Decides from the first status whether this printer has the sensor at all
    # (e.g. no chamber thermometer on an A1).
    exists_fn: Callable[[dict[str, Any] | None], bool] = lambda _: True


PRINTER_SENSORS: tuple[BambuddyPrinterSensorDescription, ...] = (
    BambuddyPrinterSensorDescription(
        key="state",
        translation_key="printer_state",
        value_fn=_printer_state,
    ),
    BambuddyPrinterSensorDescription(
        key="current_print",
        translation_key="current_print",
        value_fn=_current_print,
    ),
    BambuddyPrinterSensorDescription(
        key="progress",
        translation_key="progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_while_printing("progress"),
    ),
    BambuddyPrinterSensorDescription(
        key="remaining_time",
        translation_key="remaining_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=_while_printing("remaining_time"),
    ),
    BambuddyPrinterSensorDescription(
        key="end_time",
        translation_key="end_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_end_time,
    ),
    BambuddyPrinterSensorDescription(
        key="current_layer",
        translation_key="current_layer",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_while_printing("layer_num"),
    ),
    BambuddyPrinterSensorDescription(
        key="total_layers",
        translation_key="total_layers",
        value_fn=_while_printing("total_layers"),
    ),
    BambuddyPrinterSensorDescription(
        key="nozzle_temperature",
        translation_key="nozzle_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_temperature("nozzle"),
    ),
    BambuddyPrinterSensorDescription(
        key="nozzle_target_temperature",
        translation_key="nozzle_target_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=_temperature("nozzle_target"),
    ),
    BambuddyPrinterSensorDescription(
        key="nozzle_2_temperature",
        translation_key="nozzle_2_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_temperature("nozzle_2"),
        exists_fn=_has_temperature("nozzle_2"),
    ),
    BambuddyPrinterSensorDescription(
        key="bed_temperature",
        translation_key="bed_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_temperature("bed"),
    ),
    BambuddyPrinterSensorDescription(
        key="bed_target_temperature",
        translation_key="bed_target_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=_temperature("bed_target"),
    ),
    BambuddyPrinterSensorDescription(
        key="chamber_temperature",
        translation_key="chamber_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_temperature("chamber"),
        exists_fn=_has_temperature("chamber"),
    ),
    BambuddyPrinterSensorDescription(
        key="queue",
        translation_key="printer_queue",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda e: sum(1 for i in e.printer_queue if i.get("status") == "pending"),
        attrs_fn=_next_job_attrs,
    ),
    BambuddyPrinterSensorDescription(
        key="hms_errors",
        translation_key="hms_errors",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda e: len((e.status or {}).get("hms_errors") or []),
        attrs_fn=_hms_attrs,
    ),
    BambuddyPrinterSensorDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_status_field("wifi_signal"),
    ),
    BambuddyPrinterSensorDescription(
        key="firmware",
        translation_key="firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_status_field("firmware_version"),
    ),
)


@dataclass(frozen=True, kw_only=True)
class BambuddyQueueSensorDescription(SensorEntityDescription):
    queue_status: str


QUEUE_SENSORS: tuple[BambuddyQueueSensorDescription, ...] = (
    BambuddyQueueSensorDescription(
        key="queue_pending",
        translation_key="queue_pending",
        state_class=SensorStateClass.MEASUREMENT,
        queue_status="pending",
    ),
    BambuddyQueueSensorDescription(
        key="queue_printing",
        translation_key="queue_printing",
        state_class=SensorStateClass.MEASUREMENT,
        queue_status="printing",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BambuddyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data

    async_add_entities(
        BambuddyQueueSensor(coordinator, description) for description in QUEUE_SENSORS
    )

    known: set[int] = set()

    @callback
    def _add_new_printers() -> None:
        new_ids = set(coordinator.data.printers) - known
        if not new_ids:
            return
        known.update(new_ids)
        async_add_entities(
            BambuddyPrinterSensor(coordinator, printer_id, description)
            for printer_id in new_ids
            for description in PRINTER_SENSORS
            if description.exists_fn(coordinator.data.status.get(printer_id))
        )

    _add_new_printers()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_printers))


class BambuddyPrinterSensor(BambuddyPrinterEntity, SensorEntity):
    entity_description: BambuddyPrinterSensorDescription

    def __init__(
        self,
        coordinator: BambuddyCoordinator,
        printer_id: int,
        description: BambuddyPrinterSensorDescription,
    ) -> None:
        super().__init__(coordinator, printer_id, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        # The state sensor reports "offline" itself; everything else needs a status.
        return super().available and self.status is not None

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self)


class BambuddyQueueSensor(BambuddyHubEntity, SensorEntity):
    entity_description: BambuddyQueueSensorDescription

    def __init__(
        self,
        coordinator: BambuddyCoordinator,
        description: BambuddyQueueSensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def _items(self) -> list[dict[str, Any]]:
        return [
            item
            for item in self.coordinator.data.queue
            if item.get("status") == self.entity_description.queue_status
        ]

    @property
    def native_value(self) -> int:
        return len(self._items)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        items = self._items
        return {
            "next_job": job_name(items[0]) if items else None,
            "jobs": jobs_attribute(items),
        }
