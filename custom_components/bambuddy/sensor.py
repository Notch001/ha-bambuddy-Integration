"""Sensors for Bambuddy printers and the print queue."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
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
    UnitOfEnergy,
    UnitOfMass,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .colors import color_name, hex_color, spool_picture
from .const import CONF_ENABLE_COSTS, MAX_JOBS_IN_ATTRIBUTES
from .coordinator import (
    BambuddyConfigEntry,
    BambuddyCoordinator,
    BambuddyStats,
    BambuddyStatsCoordinator,
)
from .entity import (
    BambuddyHubEntity,
    BambuddyPrinterEntity,
    add_entities_when_seen,
    hub_device_info,
    is_printing,
    job_name,
    jobs_attribute,
)
from .planner import ams_label

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


def _current_print(entity: BambuddyPrinterEntity) -> str | None:
    status = entity.status
    # After a print the name stays until the printer is idle again, so a
    # dashboard can say what just finished (or failed).
    if not is_printing(status) and (status or {}).get("state") not in ("FINISH", "FAILED"):
        return None
    return status.get("subtask_name") or status.get("current_print")


def _end_time(entity: BambuddyPrinterEntity) -> datetime | None:
    status = entity.status
    if not is_printing(status) or not status.get("remaining_time"):
        return None
    end = dt_util.utcnow() + timedelta(minutes=status["remaining_time"])
    # Round to the minute so the state doesn't change on every poll.
    return end.replace(second=0, microsecond=0)


def _status_field(key: str) -> Callable[[BambuddyPrinterEntity], Any]:
    return lambda entity: (entity.status or {}).get(key)


def _while_printing(key: str) -> Callable[[BambuddyPrinterEntity], Any]:
    def value(entity: BambuddyPrinterEntity) -> Any:
        status = entity.status
        return status.get(key) if is_printing(status) else None

    return value


def _has_field(key: str) -> Callable[[dict[str, Any] | None], bool]:
    return lambda status: (status or {}).get(key) is not None


def _stage(entity: BambuddyPrinterEntity) -> str | None:
    """What the printer is doing right now (heating bed, auto leveling, ...)."""
    status = entity.status or {}
    return status.get("stg_cur_name") if status.get("stg_cur", -1) >= 0 else None


def _nozzle(entity: BambuddyPrinterEntity) -> str | None:
    nozzles = (entity.status or {}).get("nozzles") or []
    if not nozzles or not nozzles[0].get("nozzle_diameter"):
        return None
    return f"{nozzles[0]['nozzle_diameter']} mm"


def _nozzle_attrs(entity: BambuddyPrinterEntity) -> dict[str, Any]:
    nozzles = (entity.status or {}).get("nozzles") or []
    return {
        "nozzles": [
            {"diameter": n.get("nozzle_diameter"), "type": n.get("nozzle_type")}
            for n in nozzles
        ]
    }


def _next_job_attrs(entity: BambuddyPrinterEntity) -> dict[str, Any]:
    pending = [i for i in entity.printer_queue if i.get("status") == "pending"]
    return {
        "printer_id": entity.printer_id,
        "next_job": job_name(pending[0]) if pending else None,
        "jobs": jobs_attribute(pending, entity.coordinator.data),
    }


def _schedule_attrs(entity: BambuddyPrinterEntity) -> dict[str, Any]:
    """The printer's timeline: running print, then queued jobs with estimates."""
    entries = entity.coordinator.data.plan.schedule.get(entity.printer_id, [])
    return {
        "schedule": [
            {
                "id": e["id"],
                "name": e["name"],
                "start": e["start"].isoformat() if e["start"] else None,
                "end": e["end"].isoformat() if e["end"] else None,
                "running": e["running"],
                "predicted": e.get("predicted", False),
            }
            for e in entries[:MAX_JOBS_IN_ATTRIBUTES]
        ]
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
        key="free_at",
        translation_key="free_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda e: e.coordinator.data.plan.free_at.get(e.printer_id),
        attrs_fn=_schedule_attrs,
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
        key="stage",
        translation_key="stage",
        value_fn=_stage,
    ),
    BambuddyPrinterSensorDescription(
        key="cooling_fan",
        translation_key="cooling_fan",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_status_field("cooling_fan_speed"),
        exists_fn=_has_field("cooling_fan_speed"),
    ),
    BambuddyPrinterSensorDescription(
        key="aux_fan",
        translation_key="aux_fan",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_status_field("big_fan1_speed"),
        exists_fn=_has_field("big_fan1_speed"),
    ),
    BambuddyPrinterSensorDescription(
        key="chamber_fan",
        translation_key="chamber_fan",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_status_field("big_fan2_speed"),
        exists_fn=_has_field("big_fan2_speed"),
    ),
    BambuddyPrinterSensorDescription(
        key="nozzle",
        translation_key="nozzle",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_nozzle,
        attrs_fn=_nozzle_attrs,
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
    async_add_entities([BambuddyFarmDoneSensor(coordinator)])
    stats = [d for d in STATS_SENSORS if not d.cost or entry.options.get(CONF_ENABLE_COSTS)]
    async_add_entities(BambuddyStatsSensor(coordinator, d) for d in stats)

    def candidates():
        for printer_id in coordinator.data.printers:
            status = coordinator.data.status.get(printer_id)
            for description in PRINTER_SENSORS:
                if description.exists_fn(status):
                    yield (
                        f"{printer_id}:{description.key}",
                        partial(BambuddyPrinterSensor, coordinator, printer_id, description),
                    )
            for unit in (status or {}).get("ams") or []:
                ams_id = unit["id"]
                for description in AMS_SENSORS:
                    if description.exists_fn(unit, status):
                        yield (
                            f"{printer_id}:ams{ams_id}:{description.key}",
                            partial(BambuddyAmsSensor, coordinator, printer_id, ams_id, description),
                        )
                for tray in unit.get("tray") or []:
                    yield (
                        f"{printer_id}:ams{ams_id}:tray{tray['id']}",
                        partial(BambuddySpoolSensor, coordinator, printer_id, ams_id, tray["id"]),
                    )
            for tray in (status or {}).get("vt_tray") or []:
                yield (
                    f"{printer_id}:external{tray['id']}",
                    partial(BambuddySpoolSensor, coordinator, printer_id, None, tray["id"]),
                )

    add_entities_when_seen(entry, async_add_entities, candidates)


def _find_unit(status: dict[str, Any] | None, ams_id: int) -> dict[str, Any] | None:
    for unit in (status or {}).get("ams") or []:
        if unit.get("id") == ams_id:
            return unit
    return None


def _find_tray(
    status: dict[str, Any] | None, ams_id: int | None, tray_id: int
) -> dict[str, Any] | None:
    if ams_id is None:
        trays = (status or {}).get("vt_tray") or []
    else:
        trays = (_find_unit(status, ams_id) or {}).get("tray") or []
    for tray in trays:
        if tray.get("id") == tray_id:
            return tray
    return None


@dataclass(frozen=True, kw_only=True)
class BambuddyAmsSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]
    exists_fn: Callable[[dict[str, Any], dict[str, Any] | None], bool] = lambda *_: True


AMS_SENSORS: tuple[BambuddyAmsSensorDescription, ...] = (
    BambuddyAmsSensorDescription(
        key="humidity",
        translation_key="ams_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda unit: unit.get("humidity"),
        exists_fn=lambda unit, _: unit.get("humidity") is not None,
    ),
    BambuddyAmsSensorDescription(
        key="temperature",
        translation_key="ams_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda unit: unit.get("temp") or None,
        exists_fn=lambda unit, _: bool(unit.get("temp")),
    ),
    BambuddyAmsSensorDescription(
        key="drying_remaining",
        translation_key="ams_drying_remaining",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda unit: unit.get("dry_time") or 0,
        exists_fn=lambda _, status: bool(
            (status or {}).get("supports_drying") or (status or {}).get("drying_screen_only")
        ),
    ),
)


class BambuddyAmsSensor(BambuddyPrinterEntity, SensorEntity):
    """Humidity, temperature and drying of one AMS unit."""

    entity_description: BambuddyAmsSensorDescription

    def __init__(
        self,
        coordinator: BambuddyCoordinator,
        printer_id: int,
        ams_id: int,
        description: BambuddyAmsSensorDescription,
    ) -> None:
        super().__init__(coordinator, printer_id, f"ams{ams_id}_{description.key}")
        self.ams_id = ams_id
        self.entity_description = description
        unit = _find_unit(self.status, ams_id) or {"id": ams_id}
        self._attr_translation_placeholders = {"unit": ams_label(unit)}

    @property
    def unit(self) -> dict[str, Any] | None:
        return _find_unit(self.status, self.ams_id)

    @property
    def available(self) -> bool:
        return super().available and self.unit is not None

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.unit or {})


class BambuddySpoolSensor(BambuddyPrinterEntity, SensorEntity):
    """The filament in one AMS slot or on the external spool holder."""

    def __init__(
        self,
        coordinator: BambuddyCoordinator,
        printer_id: int,
        ams_id: int | None,
        tray_id: int,
    ) -> None:
        if ams_id is None:
            key = f"external_{tray_id}"
            externals = (coordinator.data.status.get(printer_id) or {}).get("vt_tray") or []
            self._attr_translation_key = "external_spool" if len(externals) < 2 else "external_spool_n"
            placeholders = {"n": str(tray_id - 253)}
        else:
            key = f"ams{ams_id}_tray{tray_id}"
            unit = _find_unit(coordinator.data.status.get(printer_id), ams_id) or {"id": ams_id}
            self._attr_translation_key = "ams_tray"
            placeholders = {"unit": ams_label(unit), "slot": str(tray_id + 1)}
        super().__init__(coordinator, printer_id, key)
        self._attr_translation_placeholders = placeholders
        self.ams_id = ams_id
        self.tray_id = tray_id

    @property
    def tray(self) -> dict[str, Any] | None:
        return _find_tray(self.status, self.ams_id, self.tray_id)

    @property
    def available(self) -> bool:
        return super().available and self.tray is not None

    @property
    def _empty(self) -> bool:
        tray = self.tray or {}
        if tray.get("exists") is False or tray.get("state") == 9:
            return True
        return tray.get("exists") is None and not tray.get("tray_type")

    @property
    def native_value(self) -> str | None:
        tray = self.tray
        if tray is None:
            return None
        if self._empty:
            return "empty"
        material = tray.get("tray_sub_brands") or tray.get("tray_type")
        if not material:
            return "unknown"
        color = self._color_name
        return f"{material} · {color}" if color else material

    @property
    def _color_name(self) -> str | None:
        tray = self.tray or {}
        return color_name(
            hex_color(tray.get("tray_color")),
            tray.get("tray_sub_brands"),
            self.coordinator.data.colors,
            self.hass.config.language if self.hass else "en",
        )

    @property
    def entity_picture(self) -> str | None:
        color = hex_color((self.tray or {}).get("tray_color"))
        if self._empty or color is None:
            return None
        return spool_picture(color)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        tray = self.tray or {}
        remain = tray.get("remain")
        return {
            "type": tray.get("tray_type") or None,
            "name": tray.get("tray_sub_brands") or None,
            "color": hex_color(tray.get("tray_color")),
            "color_name": None if self._empty else self._color_name,
            "remaining": remain if isinstance(remain, int) and remain >= 0 else None,
            "nozzle_temp_min": tray.get("nozzle_temp_min"),
            "nozzle_temp_max": tray.get("nozzle_temp_max"),
            "k": tray.get("k"),
            "active": (self.status or {}).get("tray_now") == self._global_tray_id,
            # For dashboards that lay slots out like the real AMS.
            "ams": self._attr_translation_placeholders.get("unit"),
            "slot": self.tray_id + 1 if self.ams_id is not None else None,
        }

    @property
    def _global_tray_id(self) -> int:
        """The id Bambuddy uses in tray_now: ams*4+slot, 128+ for AMS HT, 254 external."""
        if self.ams_id is None:
            return self.tray_id
        if self.ams_id >= 128:
            return self.ams_id
        return self.ams_id * 4 + self.tray_id


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
            "jobs": jobs_attribute(items, self.coordinator.data),
        }


class BambuddyFarmDoneSensor(BambuddyHubEntity, SensorEntity):
    """When every running print and every estimable queued job is done."""

    _attr_translation_key = "farm_done_at"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: BambuddyCoordinator) -> None:
        super().__init__(coordinator, "farm_done_at")

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.data.plan.farm_done_at


def _rate(stats: dict[str, Any]) -> float | None:
    done = (stats.get("successful_prints") or 0) + (stats.get("failed_prints") or 0)
    return round(100 * (stats.get("successful_prints") or 0) / done, 1) if done else None


@dataclass(frozen=True, kw_only=True)
class BambuddyStatsSensorDescription(SensorEntityDescription):
    value_fn: Callable[[BambuddyStats], Any]
    attrs_fn: Callable[[BambuddyStats], dict[str, Any]] | None = None
    cost: bool = False  # only with the "costs" option
    money: bool = False  # unit is Bambuddy's currency


def _total_attrs(stats: BambuddyStats) -> dict[str, Any]:
    total = stats.total
    names = total.get("printer_names") or {}
    return {
        "successful": total.get("successful_prints"),
        "failed": total.get("failed_prints"),
        "cancelled": total.get("cancelled_prints"),
        "by_printer": {
            names.get(str(k), str(k)): v for k, v in (total.get("prints_by_printer") or {}).items()
        },
        "by_filament_type": total.get("prints_by_filament_type") or {},
    }


STATS_SENSORS: tuple[BambuddyStatsSensorDescription, ...] = (
    BambuddyStatsSensorDescription(
        key="prints_total",
        translation_key="prints_total",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda s: s.total.get("total_prints"),
        attrs_fn=_total_attrs,
    ),
    BambuddyStatsSensorDescription(
        key="prints_month",
        translation_key="prints_month",
        value_fn=lambda s: s.month.get("total_prints"),
    ),
    BambuddyStatsSensorDescription(
        key="prints_today",
        translation_key="prints_today",
        value_fn=lambda s: s.today.get("total_prints"),
    ),
    BambuddyStatsSensorDescription(
        key="success_rate",
        translation_key="success_rate",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: _rate(s.total),
    ),
    BambuddyStatsSensorDescription(
        key="print_time_total",
        translation_key="print_time_total",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        value_fn=lambda s: s.total.get("total_print_time_hours"),
    ),
    BambuddyStatsSensorDescription(
        key="filament_total",
        translation_key="filament_total",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.GRAMS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        value_fn=lambda s: s.total.get("total_filament_grams"),
    ),
    BambuddyStatsSensorDescription(
        key="filament_month",
        translation_key="filament_month",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.GRAMS,
        suggested_display_precision=0,
        value_fn=lambda s: s.month.get("total_filament_grams"),
    ),
    BambuddyStatsSensorDescription(
        key="filament_cost_total",
        translation_key="filament_cost_total",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        cost=True,
        money=True,
        value_fn=lambda s: s.total.get("total_cost"),
    ),
    BambuddyStatsSensorDescription(
        key="filament_cost_month",
        translation_key="filament_cost_month",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
        cost=True,
        money=True,
        value_fn=lambda s: s.month.get("total_cost"),
    ),
    BambuddyStatsSensorDescription(
        key="energy_total",
        translation_key="energy_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        cost=True,
        value_fn=lambda s: s.total.get("total_energy_kwh"),
    ),
    BambuddyStatsSensorDescription(
        key="energy_month",
        translation_key="energy_month",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        cost=True,
        value_fn=lambda s: s.month.get("total_energy_kwh"),
    ),
    BambuddyStatsSensorDescription(
        key="energy_cost_total",
        translation_key="energy_cost_total",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        cost=True,
        money=True,
        value_fn=lambda s: s.total.get("total_energy_cost"),
    ),
    BambuddyStatsSensorDescription(
        key="energy_cost_month",
        translation_key="energy_cost_month",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
        cost=True,
        money=True,
        value_fn=lambda s: s.month.get("total_energy_cost"),
    ),
)


class BambuddyStatsSensor(CoordinatorEntity[BambuddyStatsCoordinator], SensorEntity):
    """Statistics from Bambuddy's print log, on the Bambuddy device."""

    _attr_has_entity_name = True
    entity_description: BambuddyStatsSensorDescription

    def __init__(
        self, coordinator: BambuddyCoordinator, description: BambuddyStatsSensorDescription
    ) -> None:
        super().__init__(coordinator.stats)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = hub_device_info(coordinator)

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data is not None

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.entity_description.money:
            return (self.coordinator.data.currency if self.coordinator.data else None) or "EUR"
        return super().native_unit_of_measurement

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None or self.coordinator.data is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)
