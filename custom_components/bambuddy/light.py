"""Chamber light of a Bambu printer."""

from __future__ import annotations

from functools import partial
from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BambuddyConfigEntry, BambuddyCoordinator
from .entity import BambuddyPrinterEntity, add_entities_when_seen

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BambuddyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data

    def candidates():
        for printer_id in coordinator.data.printers:
            yield (
                f"{printer_id}:chamber_light",
                partial(BambuddyChamberLight, coordinator, printer_id),
            )

    add_entities_when_seen(entry, async_add_entities, candidates)


class BambuddyChamberLight(BambuddyPrinterEntity, LightEntity):
    _attr_translation_key = "chamber_light"
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(self, coordinator: BambuddyCoordinator, printer_id: int) -> None:
        super().__init__(coordinator, printer_id, "chamber_light")
        # Shown right after switching, until Bambuddy reports the new state.
        self._assumed: bool | None = None

    @property
    def available(self) -> bool:
        status = self.status
        return super().available and status is not None and bool(status.get("connected"))

    @property
    def is_on(self) -> bool | None:
        if self._assumed is not None:
            return self._assumed
        return bool((self.status or {}).get("chamber_light"))

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._assumed is not None and (self.status or {}).get("chamber_light") == self._assumed:
            self._assumed = None
        super()._handle_coordinator_update()

    async def _switch(self, on: bool) -> None:
        await self.run_action(
            lambda: self.coordinator.client.set_chamber_light(self.printer_id, on)
        )
        self._assumed = on
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._switch(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._switch(False)
