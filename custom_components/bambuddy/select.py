"""Print speed of a Bambu printer."""

from __future__ import annotations

from functools import partial

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SPEED_LEVELS
from .coordinator import BambuddyConfigEntry, BambuddyCoordinator
from .entity import BambuddyPrinterEntity, add_entities_when_seen, is_printing

PARALLEL_UPDATES = 1

SPEED_BY_NAME = {name: level for level, name in SPEED_LEVELS.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BambuddyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data

    def candidates():
        for printer_id in coordinator.data.printers:
            yield (
                f"{printer_id}:print_speed",
                partial(BambuddyPrintSpeed, coordinator, printer_id),
            )

    add_entities_when_seen(entry, async_add_entities, candidates)


class BambuddyPrintSpeed(BambuddyPrinterEntity, SelectEntity):
    _attr_translation_key = "print_speed"
    _attr_options = list(SPEED_LEVELS.values())

    def __init__(self, coordinator: BambuddyCoordinator, printer_id: int) -> None:
        super().__init__(coordinator, printer_id, "print_speed")

    @property
    def available(self) -> bool:
        # The printer only accepts a speed change while a print is running.
        status = self.status
        return (
            super().available
            and status is not None
            and bool(status.get("connected"))
            and is_printing(status)
        )

    @property
    def current_option(self) -> str | None:
        return SPEED_LEVELS.get((self.status or {}).get("speed_level"))

    async def async_select_option(self, option: str) -> None:
        await self.run_action(
            lambda: self.coordinator.client.set_print_speed(
                self.printer_id, SPEED_BY_NAME[option]
            )
        )
