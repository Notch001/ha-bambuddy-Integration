"""The Bambuddy integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.const import (
    CONF_URL,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STARTED,
    Platform,
)
from homeassistant.core import CoreState, Event, HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .api import BambuddyApiClient
from .const import BACKEND_PRINTDOG, CONF_API_KEY, CONF_BACKEND, DOMAIN
from .printdog import PrintDogApiClient
from .coordinator import BambuddyConfigEntry, BambuddyCoordinator, BambuddyStatsCoordinator
from .entity import hub_device_info
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.EVENT,
    Platform.IMAGE,
    Platform.LIGHT,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TODO,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

CARD_URL = "/bambuddy/bambuddy-card.js"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the dashboard card and make every dashboard load it."""
    if getattr(hass, "http", None) is None:
        async_setup_services(hass)
        return True
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(Path(__file__).parent / "frontend" / "bambuddy-card.js"), True)]
    )
    async_setup_services(hass)

    # The version makes browsers fetch the new card after an update.
    url = f"{CARD_URL}?v={(await async_get_integration(hass, DOMAIN)).version}"

    async def _register(_event: Event | None = None) -> None:
        if not await _async_register_card_resource(hass, url) and "frontend" in hass.config.components:
            # YAML-mode dashboards manage their own resources; fall back to
            # injecting the script into the page. Injected scripts run before
            # Home Assistant swaps in its scoped element registry, which the
            # card handles by registering itself again (see bambuddy-card.js).
            from homeassistant.components.frontend import add_extra_js_url  # noqa: PLC0415

            add_extra_js_url(hass, url)

    if hass.state is CoreState.running:
        await _register()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _register)
    return True


async def _async_register_card_resource(hass: HomeAssistant, url: str) -> bool:
    """Add the card to the dashboard resources (storage mode), like HACS does.

    Dashboards load their resources after Home Assistant's frontend has set
    itself up, so the card lands in the registry the editor and card picker
    use; it also works in the companion apps. Keeps exactly one entry and
    moves its version along. Returns False if resources can't be managed.
    """
    lovelace = hass.data.get("lovelace")
    resources = getattr(lovelace, "resources", None)
    if resources is None or getattr(lovelace, "resource_mode", "storage") != "storage":
        return False
    try:
        if not getattr(resources, "loaded", True):
            await resources.async_load()
            resources.loaded = True
        for item in resources.async_items():
            if item.get("url", "").split("?")[0] == CARD_URL:
                if item["url"] != url:
                    await resources.async_update_item(item["id"], {"res_type": "module", "url": url})
                return True
        await resources.async_create_item({"res_type": "module", "url": url})
    except Exception:  # noqa: BLE001 - the card is a bonus, never fail setup over it
        _LOGGER.warning("Could not register the Bambuddy card as a dashboard resource", exc_info=True)
        return False
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BambuddyConfigEntry) -> bool:
    """Set up Bambuddy from a config entry."""
    session = async_get_clientsession(hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, True))
    client_class = PrintDogApiClient if entry.data.get(CONF_BACKEND) == BACKEND_PRINTDOG else BambuddyApiClient
    client = client_class(session, entry.data[CONF_URL], entry.data.get(CONF_API_KEY))

    coordinator = BambuddyCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    # Statistics are a bonus: an older Bambuddy without them must not stop setup.
    coordinator.stats = BambuddyStatsCoordinator(hass, entry, client)
    await coordinator.stats.async_refresh()
    entry.runtime_data = coordinator

    # Printers hang off the Bambuddy device (via_device_id), so it must exist
    # before any platform registers a printer.
    coordinator.hub_device_id = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **hub_device_info(coordinator)
    ).id

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BambuddyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: BambuddyConfigEntry) -> None:
    """Drop the card resource with the last Bambuddy entry, so no dead resource stays behind."""
    if any(
        other.entry_id != entry.entry_id
        for other in hass.config_entries.async_entries(DOMAIN)
    ):
        return
    lovelace = hass.data.get("lovelace")
    resources = getattr(lovelace, "resources", None)
    if resources is None or getattr(lovelace, "resource_mode", "storage") != "storage":
        return
    try:
        if not getattr(resources, "loaded", True):
            await resources.async_load()
            resources.loaded = True
        for item in list(resources.async_items()):
            if item.get("url", "").split("?")[0] == CARD_URL:
                await resources.async_delete_item(item["id"])
    except Exception:  # noqa: BLE001 - cleanup is best effort
        _LOGGER.debug("Could not remove the Bambuddy card resource", exc_info=True)


async def _async_reload_entry(hass: HomeAssistant, entry: BambuddyConfigEntry) -> None:
    """Reload after the options (scan interval) changed."""
    await hass.config_entries.async_reload(entry.entry_id)
