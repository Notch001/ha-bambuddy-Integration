"""Printer camera, proxied through Bambuddy."""

from __future__ import annotations

from functools import partial
import logging

from aiohttp import web

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_web
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import BambuddyError
from .coordinator import BambuddyConfigEntry, BambuddyCoordinator
from .entity import BambuddyPrinterEntity, add_entities_when_seen

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
            yield (f"{printer_id}:camera", partial(BambuddyCamera, coordinator, printer_id))

    add_entities_when_seen(entry, async_add_entities, candidates)


class BambuddyCamera(BambuddyPrinterEntity, Camera):
    _attr_translation_key = "camera"

    def __init__(self, coordinator: BambuddyCoordinator, printer_id: int) -> None:
        super().__init__(coordinator, printer_id, "camera")
        Camera.__init__(self)

    @property
    def available(self) -> bool:
        status = self.status
        return super().available and status is not None and bool(status.get("connected"))

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        try:
            return await self.coordinator.client.get_camera_snapshot(self.printer_id)
        except BambuddyError as err:
            _LOGGER.debug("No camera image from printer %s: %s", self.printer_id, err)
            return None

    async def handle_async_mjpeg_stream(self, request: web.Request) -> web.StreamResponse | None:
        """Pass Bambuddy's MJPEG stream through to the browser."""
        client = self.coordinator.client
        try:
            url = await client.camera_stream_url(self.printer_id)
        except BambuddyError as err:
            _LOGGER.debug("Cannot open camera stream of printer %s: %s", self.printer_id, err)
            return None
        return await async_aiohttp_proxy_web(
            self.hass, request, client.session.get(url, headers=client.headers), timeout=30
        )
