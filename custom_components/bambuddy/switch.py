"""One-shot "notify me when this print is done" switch per printer."""

from __future__ import annotations

from functools import partial
import logging
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_NOTIFY_TARGETS
from .coordinator import BambuddyConfigEntry, BambuddyCoordinator
from .entity import BambuddyPrinterEntity, add_entities_when_seen, job_name
from .event import _snapshot, detect_events

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

TEXTS = {
    "de": {
        "print_finished": ("{p} ist fertig", "{j} ist fertig."),
        "print_failed": ("{p}: Druck fehlgeschlagen", "{j} ist fehlgeschlagen."),
        "next": " Als Nächstes: {n}",
    },
    "en": {
        "print_finished": ("{p} is done", "{j} has finished."),
        "print_failed": ("{p}: print failed", "{j} has failed."),
        "next": " Up next: {n}",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BambuddyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data

    def candidates():
        for printer_id in coordinator.data.printers:
            yield (f"{printer_id}:notify", partial(BambuddyNotifyWhenDone, coordinator, printer_id))

    add_entities_when_seen(entry, async_add_entities, candidates)


class BambuddyNotifyWhenDone(BambuddyPrinterEntity, SwitchEntity, RestoreEntity):
    """Turn on, and the next finished (or failed) print sends a notification.

    It switches itself off afterwards. Notifications go to the targets chosen
    under the integration's options, or appear in Home Assistant's
    notification panel if none are chosen.
    """

    _attr_translation_key = "notify_when_done"

    def __init__(self, coordinator: BambuddyCoordinator, printer_id: int) -> None:
        super().__init__(coordinator, printer_id, "notify_when_done")
        self._attr_is_on = False
        self._last = _snapshot(self.status)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self._attr_is_on = last.state == "on"

    @property
    def _targets(self) -> list[str]:
        return list(self.coordinator.config_entry.options.get(CONF_NOTIFY_TARGETS) or [])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"targets": self._targets}

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._attr_is_on = False
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        current = _snapshot(self.status)
        events = detect_events(self._last, current)
        if current is not None:
            self._last = current
        done = [e for e in events if e in ("print_finished", "print_failed")]
        if self._attr_is_on and done:
            self._attr_is_on = False
            self.hass.async_create_task(self._async_notify(done[0], current))
        super()._handle_coordinator_update()

    async def _async_notify(self, event: str, snapshot: dict[str, Any] | None) -> None:
        texts = TEXTS["de" if self.hass.config.language.startswith("de") else "en"]
        printer = (self.printer or {}).get("name") or ""
        job = (snapshot or {}).get("job") or printer
        title, message = (t.replace("{p}", printer).replace("{j}", job) for t in texts[event])
        pending = [i for i in self.printer_queue if i.get("status") == "pending"]
        if event == "print_finished" and pending:
            message += texts["next"].replace("{n}", job_name(pending[0]) or "?")

        if not self._targets:
            persistent_notification.async_create(
                self.hass, message, title, f"bambuddy_done_{self.printer_id}"
            )
            return
        for target in self._targets:
            service = target.removeprefix("notify.")
            try:
                await self.hass.services.async_call(
                    "notify", service, {"title": title, "message": message}, blocking=True
                )
            except Exception:  # noqa: BLE001 - one broken target must not block the others
                _LOGGER.warning("Could not send the Bambuddy notification via notify.%s", service, exc_info=True)
