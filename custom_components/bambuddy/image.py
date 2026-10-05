"""Preview image of the print that is currently running."""

from __future__ import annotations

from functools import partial
import logging

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import BambuddyError
from .coordinator import BambuddyConfigEntry, BambuddyCoordinator
from .entity import BambuddyPrinterEntity, add_entities_when_seen, is_printing

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BambuddyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data

    def candidates():
        for printer_id in coordinator.data.printers:
            yield (
                f"{printer_id}:cover",
                partial(BambuddyCoverImage, coordinator, printer_id),
            )

    add_entities_when_seen(entry, async_add_entities, candidates)


class BambuddyCoverImage(BambuddyPrinterEntity, ImageEntity):
    _attr_translation_key = "cover"

    def __init__(self, coordinator: BambuddyCoordinator, printer_id: int) -> None:
        super().__init__(coordinator, printer_id, "cover")
        ImageEntity.__init__(self, coordinator.hass)
        self._print_key = self._current_print_key()
        self._image: bytes | None = None
        self._attr_image_last_updated = dt_util.utcnow()

    def _current_print_key(self) -> tuple | None:
        status = self.status
        if not is_printing(status):
            return None
        return (
            status.get("current_archive_id"),
            status.get("subtask_name"),
            status.get("gcode_file"),
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        key = self._current_print_key()
        if key != self._print_key:
            # New print (or print ended): make the frontend fetch the image again.
            self._print_key = key
            self._image = None
            self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        if self._print_key is None:
            return None
        if self._image is not None:
            return self._image
        try:
            data, content_type = await self.coordinator.client.get_cover(self.printer_id)
        except BambuddyError as err:
            _LOGGER.debug("No cover image for printer %s: %s", self.printer_id, err)
            return None
        self._attr_content_type = content_type or "image/png"
        self._image = data
        return data
