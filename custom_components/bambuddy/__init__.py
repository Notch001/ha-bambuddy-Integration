"""The Bambuddy integration."""

from __future__ import annotations

from homeassistant.const import CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BambuddyApiClient
from .const import CONF_API_KEY
from .coordinator import BambuddyConfigEntry, BambuddyCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: BambuddyConfigEntry) -> bool:
    """Set up Bambuddy from a config entry."""
    session = async_get_clientsession(hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, True))
    client = BambuddyApiClient(session, entry.data[CONF_URL], entry.data.get(CONF_API_KEY))

    coordinator = BambuddyCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BambuddyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: BambuddyConfigEntry) -> None:
    """Reload after the options (scan interval) changed."""
    await hass.config_entries.async_reload(entry.entry_id)
