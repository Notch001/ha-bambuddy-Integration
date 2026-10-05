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
from .const import CONF_API_KEY, DOMAIN
from .coordinator import BambuddyConfigEntry, BambuddyCoordinator
from .entity import hub_device_info

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.IMAGE,
    Platform.LIGHT,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.TODO,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

CARD_URL = "/bambuddy/bambuddy-card.js"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the dashboard card and make every dashboard load it."""
    if getattr(hass, "http", None) is None:
        return True
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(Path(__file__).parent / "frontend" / "bambuddy-card.js"), True)]
    )
    # The version makes browsers fetch the new card after an update.
    url = f"{CARD_URL}?v={(await async_get_integration(hass, DOMAIN)).version}"

    if "frontend" in hass.config.components:
        from homeassistant.components.frontend import add_extra_js_url  # noqa: PLC0415

        # Covers YAML-mode dashboards; baked into the page HTML, which the
        # companion apps may keep cached across updates.
        add_extra_js_url(hass, url)

    async def _register(_event: Event | None = None) -> None:
        await _async_register_card_resource(hass, url)

    if hass.state is CoreState.running:
        await _register()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _register)
    return True


async def _async_register_card_resource(hass: HomeAssistant, url: str) -> None:
    """Add the card to the dashboard resources (storage mode), like HACS does.

    Dashboards fetch their resources fresh on every load, so this also works
    in the companion apps. Keeps exactly one entry and moves its version along.
    """
    lovelace = hass.data.get("lovelace")
    resources = getattr(lovelace, "resources", None)
    if resources is None or getattr(lovelace, "resource_mode", "storage") != "storage":
        return
    try:
        if not getattr(resources, "loaded", True):
            await resources.async_load()
            resources.loaded = True
        for item in resources.async_items():
            if item.get("url", "").split("?")[0] == CARD_URL:
                if item["url"] != url:
                    await resources.async_update_item(item["id"], {"res_type": "module", "url": url})
                return
        await resources.async_create_item({"res_type": "module", "url": url})
    except Exception:  # noqa: BLE001 - the card is a bonus, never fail setup over it
        _LOGGER.warning("Could not register the Bambuddy card as a dashboard resource", exc_info=True)


async def async_setup_entry(hass: HomeAssistant, entry: BambuddyConfigEntry) -> bool:
    """Set up Bambuddy from a config entry."""
    session = async_get_clientsession(hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, True))
    client = BambuddyApiClient(session, entry.data[CONF_URL], entry.data.get(CONF_API_KEY))

    coordinator = BambuddyCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Printers hang off the Bambuddy device (via_device), so it must exist
    # before any platform registers a printer.
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **hub_device_info(coordinator)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BambuddyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: BambuddyConfigEntry) -> None:
    """Reload after the options (scan interval) changed."""
    await hass.config_entries.async_reload(entry.entry_id)
