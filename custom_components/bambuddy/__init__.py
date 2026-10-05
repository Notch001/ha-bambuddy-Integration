"""The Bambuddy integration."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.const import CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .api import BambuddyApiClient
from .const import CONF_API_KEY, DOMAIN
from .coordinator import BambuddyConfigEntry, BambuddyCoordinator
from .entity import hub_device_info

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
    """Serve the dashboard card and load it into every browser."""
    if getattr(hass, "http", None) is None:
        return True
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(Path(__file__).parent / "frontend" / "bambuddy-card.js"), True)]
    )
    if "frontend" in hass.config.components:
        from homeassistant.components.frontend import add_extra_js_url  # noqa: PLC0415

        # The version makes browsers fetch the new card after an update.
        version = (await async_get_integration(hass, DOMAIN)).version
        add_extra_js_url(hass, f"{CARD_URL}?v={version}")
    return True


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
