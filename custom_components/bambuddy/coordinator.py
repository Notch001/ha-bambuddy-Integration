"""Data update coordinator for Bambuddy."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BambuddyApiClient, BambuddyAuthError, BambuddyError
from .const import (
    COLOR_MAP_REFRESH,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    QUEUE_ACTIVE_STATUSES,
)

_LOGGER = logging.getLogger(__name__)

type BambuddyConfigEntry = ConfigEntry[BambuddyCoordinator]


@dataclass
class BambuddyData:
    """Snapshot of everything the entities read."""

    # printer id -> printer config (name, serial_number, model, ...)
    printers: dict[int, dict[str, Any]] = field(default_factory=dict)
    # printer id -> live status, None if Bambuddy could not report it
    status: dict[int, dict[str, Any] | None] = field(default_factory=dict)
    # Pending and printing queue items, in dispatch order
    queue: list[dict[str, Any]] = field(default_factory=list)
    # Bambuddy's colour catalogue, see BambuddyApiClient.get_color_map
    colors: dict[str, Any] = field(default_factory=dict)


class BambuddyCoordinator(DataUpdateCoordinator[BambuddyData]):
    """Polls printers, their status and the print queue."""

    config_entry: BambuddyConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: BambuddyConfigEntry,
        client: BambuddyApiClient,
    ) -> None:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.client = client
        self._colors: dict[str, Any] = {}
        self._colors_fetched = 0.0

    async def _async_update_data(self) -> BambuddyData:
        try:
            printers = await self.client.get_printers()
            queue_lists = await asyncio.gather(
                *(self.client.get_queue(status) for status in QUEUE_ACTIVE_STATUSES)
            )
        except BambuddyAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except BambuddyError as err:
            raise UpdateFailed(str(err)) from err

        # One printer failing (e.g. removed between the two calls) must not
        # take every other printer's entities down with it.
        results = await asyncio.gather(
            *(self.client.get_printer_status(p["id"]) for p in printers),
            return_exceptions=True,
        )
        status: dict[int, dict[str, Any] | None] = {}
        for printer, result in zip(printers, results, strict=True):
            if isinstance(result, BambuddyAuthError):
                raise ConfigEntryAuthFailed(str(result)) from result
            if isinstance(result, BaseException):
                _LOGGER.debug(
                    "Could not fetch status of printer %s: %s", printer["id"], result
                )
                status[printer["id"]] = None
            else:
                status[printer["id"]] = result

        queue = sorted(
            (item for items in queue_lists for item in items),
            key=lambda item: (item.get("position", 0), item.get("id", 0)),
        )

        return BambuddyData(
            printers={p["id"]: p for p in printers},
            status=status,
            queue=queue,
            colors=await self._async_colors(),
        )

    async def _async_colors(self) -> dict[str, Any]:
        """The colour catalogue changes rarely; refresh it once an hour.

        Only used for nicer names, so a failure keeps the last copy (or none).
        """
        now = self.hass.loop.time()
        if self._colors_fetched and now - self._colors_fetched < COLOR_MAP_REFRESH.total_seconds():
            return self._colors
        self._colors_fetched = now
        try:
            self._colors = await self.client.get_color_map()
        except BambuddyError as err:
            _LOGGER.debug("Could not fetch Bambuddy colour names: %s", err)
        return self._colors
