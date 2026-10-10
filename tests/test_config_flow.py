"""Config flow tests."""

from homeassistant import config_entries
from homeassistant.const import CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.bambuddy.const import CONF_API_KEY, CONF_SCAN_INTERVAL, DOMAIN

from .conftest import API_KEY, URL, mock_bambuddy


async def _start(hass):
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})


async def test_user_flow_success(hass: HomeAssistant, aioclient_mock) -> None:
    mock_bambuddy(aioclient_mock)
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "bambuddy.local:8000/", CONF_API_KEY: f" {API_KEY} ", CONF_VERIFY_SSL: True},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_URL: URL, CONF_API_KEY: API_KEY, CONF_VERIFY_SSL: True, "backend": "bambuddy"}
    await hass.async_block_till_done()


async def test_user_flow_invalid_auth(hass: HomeAssistant, aioclient_mock) -> None:
    mock_bambuddy(aioclient_mock, auth_status=401)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: URL, CONF_API_KEY: "bb_wrong", CONF_VERIFY_SSL: True}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"{URL}/api/status", status=404)
    aioclient_mock.get(f"{URL}/api/v1/printers/", exc=TimeoutError())
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: URL, CONF_VERIFY_SSL: True}
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_options_flow(hass: HomeAssistant, aioclient_mock) -> None:
    mock_bambuddy(aioclient_mock)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: URL, CONF_API_KEY: API_KEY, CONF_VERIFY_SSL: True}
    )
    await hass.async_block_till_done()
    entry = result["result"]

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 60, "enable_costs": False, "low_spool_threshold": 15, "notify_targets": []}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.runtime_data.update_interval.total_seconds() == 60
