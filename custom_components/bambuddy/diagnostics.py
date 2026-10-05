"""Diagnostics for Bambuddy: what users attach to bug reports."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY, CONF_NOTIFY_TARGETS
from .coordinator import BambuddyConfigEntry

# Secrets and anything that identifies the user's printers or network.
TO_REDACT = {
    CONF_API_KEY,
    CONF_URL,
    CONF_NOTIFY_TARGETS,
    "serial_number",
    "serial",
    "dev_id",
    "ip_address",
    "ip",
    "access_code",
    "token",
    "api_key",
    "password",
    "wifi_ssid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BambuddyConfigEntry
) -> dict[str, Any]:
    """Return redacted data of a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data
    stats = coordinator.stats
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "last_update_success": coordinator.last_update_success,
        "printers": async_redact_data(
            {str(pid): printer for pid, printer in data.printers.items()}, TO_REDACT
        ),
        "status": async_redact_data(
            {str(pid): status for pid, status in data.status.items()}, TO_REDACT
        ),
        "queue": async_redact_data(data.queue, TO_REDACT),
        "plan": async_redact_data(asdict(data.plan), TO_REDACT),
        "colors_loaded": bool(data.colors),
        "stats": async_redact_data(asdict(stats.data), TO_REDACT)
        if stats is not None and stats.data is not None
        else None,
    }
