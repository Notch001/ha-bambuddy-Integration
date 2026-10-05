"""Config flow for the Bambuddy integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    BambuddyApiClient,
    BambuddyAuthError,
    BambuddyConnectionError,
    normalize_url,
)
from .const import (
    CONF_API_KEY,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .coordinator import BambuddyConfigEntry

_LOGGER = logging.getLogger(__name__)


class BambuddyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the setup UI for Bambuddy."""

    VERSION = 1

    async def _async_validate(
        self, url: str, api_key: str | None, verify_ssl: bool
    ) -> str | None:
        """Try the credentials; return an error key or None on success."""
        client = BambuddyApiClient(
            async_get_clientsession(self.hass, verify_ssl=verify_ssl), url, api_key
        )
        try:
            await client.get_printers()
            await client.get_queue("pending")
        except BambuddyAuthError:
            return "invalid_auth"
        except BambuddyConnectionError:
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error while validating Bambuddy")
            return "unknown"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = normalize_url(user_input[CONF_URL])
            api_key = user_input.get(CONF_API_KEY, "").strip() or None
            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()

            error = await self._async_validate(url, api_key, user_input[CONF_VERIFY_SSL])
            if error is None:
                return self.async_create_entry(
                    title="Bambuddy",
                    data={
                        CONF_URL: url,
                        CONF_API_KEY: api_key,
                        CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                    },
                )
            errors["base"] = error

        schema = vol.Schema(
            {
                vol.Required(CONF_URL): str,
                vol.Optional(CONF_API_KEY): str,
                vol.Required(CONF_VERIFY_SSL, default=True): bool,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            api_key = user_input.get(CONF_API_KEY, "").strip() or None
            error = await self._async_validate(
                entry.data[CONF_URL], api_key, entry.data.get(CONF_VERIFY_SSL, True)
            )
            if error is None:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: api_key}
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Optional(CONF_API_KEY): str}),
            description_placeholders={"url": entry.data[CONF_URL]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: BambuddyConfigEntry) -> OptionsFlow:
        return BambuddyOptionsFlow()


class BambuddyOptionsFlow(OptionsFlow):
    """Let the user change how often Bambuddy is polled."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    )
                }
            ),
        )
