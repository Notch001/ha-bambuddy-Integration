"""Diagnostics must never leak secrets."""

import json

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)

from .conftest import API_KEY, URL, mock_bambuddy
from .test_sensor import _setup


async def test_diagnostics_redacted(hass: HomeAssistant, aioclient_mock, hass_client) -> None:
    assert await async_setup_component(hass, "diagnostics", {})
    mock_bambuddy(aioclient_mock)
    entry = await _setup(hass)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    text = json.dumps(diag)
    for secret in (API_KEY, URL, "bambuddy.local", "00M09A111111111", "0300AA222222222"):
        assert secret not in text
    assert diag["entry"]["data"]["api_key"] == "**REDACTED**"
    assert diag["printers"]["1"]["name"] == "X1C Werkstatt"
    assert diag["status"]["1"]["state"] == "RUNNING"
    assert len(diag["queue"]) == 3
