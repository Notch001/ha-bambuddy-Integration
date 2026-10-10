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
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import (
    BambuddyApiClient,
    BambuddyAuthError,
    BambuddyConnectionError,
    normalize_url,
)
from .const import (
    BACKEND_PRINTDOG,
    CONF_API_KEY,
    CONF_BACKEND,
    CONF_ENABLE_COSTS,
    CONF_LOW_SPOOL,
    CONF_NOTIFY_TARGETS,
    CONF_SCAN_INTERVAL,
    DEFAULT_LOW_SPOOL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .coordinator import BambuddyConfigEntry
from .printdog import PrintDogApiClient, detect_backend

_LOGGER = logging.getLogger(__name__)


class BambuddyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the setup UI for Bambuddy."""

    VERSION = 1

    async def _async_validate(
        self, url: str, api_key: str | None, verify_ssl: bool
    ) -> tuple[str | None, str]:
        """Try the credentials; return (error key or None, detected backend)."""
        session = async_get_clientsession(self.hass, verify_ssl=verify_ssl)
        backend = await detect_backend(session, url, api_key)
        client_class = PrintDogApiClient if backend == BACKEND_PRINTDOG else BambuddyApiClient
        client = client_class(session, url, api_key)
        try:
            await client.get_printers()
            await client.get_queue("pending")
        except BambuddyAuthError:
            return "invalid_auth", backend
        except BambuddyConnectionError:
            return "cannot_connect", backend
        except Exception:
            _LOGGER.exception("Unexpected error while validating the server")
            return "unknown", backend
        return None, backend

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = normalize_url(user_input[CONF_URL])
            api_key = user_input.get(CONF_API_KEY, "").strip() or None
            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()

            error, backend = await self._async_validate(url, api_key, user_input[CONF_VERIFY_SSL])
            if error is None:
                return self.async_create_entry(
                    title="PrintDog" if backend == BACKEND_PRINTDOG else "Bambuddy",
                    data={
                        CONF_URL: url,
                        CONF_API_KEY: api_key,
                        CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                        CONF_BACKEND: backend,
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
            error, _backend = await self._async_validate(
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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Point the existing entry at another server (e.g. from Bambuddy to PrintDog).

        The entry, its devices and entity ids stay, so dashboards and automations keep working.
        """
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            url = normalize_url(user_input[CONF_URL])
            api_key = user_input.get(CONF_API_KEY, "").strip() or None
            error, backend = await self._async_validate(url, api_key, user_input[CONF_VERIFY_SSL])
            if error is None:
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=url,
                    title="PrintDog" if backend == BACKEND_PRINTDOG else "Bambuddy",
                    data_updates={
                        CONF_URL: url,
                        CONF_API_KEY: api_key,
                        CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                        CONF_BACKEND: backend,
                    },
                )
            errors["base"] = error

        schema = vol.Schema(
            {
                vol.Required(CONF_URL, default=entry.data[CONF_URL]): str,
                vol.Optional(CONF_API_KEY, default=entry.data.get(CONF_API_KEY) or ""): str,
                vol.Required(CONF_VERIFY_SSL, default=entry.data.get(CONF_VERIFY_SSL, True)): bool,
            }
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
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

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    ),
                    vol.Required(
                        CONF_ENABLE_COSTS, default=options.get(CONF_ENABLE_COSTS, False)
                    ): bool,
                    vol.Required(
                        CONF_LOW_SPOOL, default=options.get(CONF_LOW_SPOOL, DEFAULT_LOW_SPOOL)
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
                    vol.Optional(
                        CONF_NOTIFY_TARGETS, default=options.get(CONF_NOTIFY_TARGETS, [])
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=sorted(
                                set(self.hass.services.async_services_for_domain("notify"))
                                - {"send_message"}
                                | set(options.get(CONF_NOTIFY_TARGETS, []))
                            ),
                            multiple=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )
