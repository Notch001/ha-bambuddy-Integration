"""Buttons to pause, resume and stop prints and to confirm a cleared plate."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import BambuddyApiClient
from .coordinator import BambuddyConfigEntry, BambuddyCoordinator
from .entity import BambuddyPrinterEntity, add_entities_when_seen, is_printing

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class BambuddyButtonDescription(ButtonEntityDescription):
    press_fn: Callable[[BambuddyApiClient, int], Awaitable[Any]]
    # Only offered when it makes sense, so nobody "stops" an idle printer.
    available_fn: Callable[[dict[str, Any]], bool]


BUTTONS: tuple[BambuddyButtonDescription, ...] = (
    BambuddyButtonDescription(
        key="pause",
        translation_key="pause",
        press_fn=lambda client, pid: client.pause(pid),
        available_fn=lambda s: s.get("state") == "RUNNING",
    ),
    BambuddyButtonDescription(
        key="resume",
        translation_key="resume",
        press_fn=lambda client, pid: client.resume(pid),
        available_fn=lambda s: s.get("state") == "PAUSE",
    ),
    BambuddyButtonDescription(
        key="stop",
        translation_key="stop",
        press_fn=lambda client, pid: client.stop(pid),
        available_fn=is_printing,
    ),
    BambuddyButtonDescription(
        key="clear_plate",
        translation_key="clear_plate",
        press_fn=lambda client, pid: client.clear_plate(pid),
        available_fn=lambda s: bool(s.get("awaiting_plate_clear")),
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
            for description in BUTTONS:
                yield (
                    f"{printer_id}:{description.key}",
                    partial(BambuddyButton, coordinator, printer_id, description),
                )

    add_entities_when_seen(entry, async_add_entities, candidates)


class BambuddyButton(BambuddyPrinterEntity, ButtonEntity):
    entity_description: BambuddyButtonDescription

    def __init__(
        self,
        coordinator: BambuddyCoordinator,
        printer_id: int,
        description: BambuddyButtonDescription,
    ) -> None:
        super().__init__(coordinator, printer_id, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        status = self.status
        return (
            super().available
            and status is not None
            and bool(status.get("connected"))
            and self.entity_description.available_fn(status)
        )

    async def async_press(self) -> None:
        await self.run_action(
            lambda: self.entity_description.press_fn(self.coordinator.client, self.printer_id)
        )
