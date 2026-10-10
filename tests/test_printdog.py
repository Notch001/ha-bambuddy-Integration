"""PrintDog backend: the client translates PrintDog's API into what the entities read."""

from __future__ import annotations

import copy
import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bambuddy.api import BambuddyRequestError
from custom_components.bambuddy.const import CONF_API_KEY, CONF_BACKEND, DOMAIN
from custom_components.bambuddy.printdog import PrintDogApiClient, queue_item, status_from_detail

from .conftest import PD_API, PD_API_DATA, PD_KEY, PD_URL, mock_bambuddy, mock_printdog

SERIAL = "01S00C123456789"


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=PD_URL,
        data={CONF_URL: PD_URL, CONF_API_KEY: PD_KEY, CONF_VERIFY_SSL: True, CONF_BACKEND: "printdog"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _state(hass: HomeAssistant, domain: str, key: str):
    entity_id = er.async_get(hass).async_get_entity_id(domain, DOMAIN, f"{SERIAL}_{key}")
    assert entity_id, key
    return hass.states.get(entity_id)


async def test_entities_from_printdog(hass: HomeAssistant, aioclient_mock) -> None:
    mock_printdog(aioclient_mock)
    entry = await _setup(hass)
    assert all(h.get("X-API-Key") == PD_KEY for *_, h in aioclient_mock.mock_calls)
    assert _state(hass, "sensor", "state").state == "running"
    assert _state(hass, "sensor", "current_print").state == "Eule_Beige"
    assert float(_state(hass, "sensor", "progress").state) == 42
    assert _state(hass, "sensor", "remaining_time").state == "83"
    assert float(_state(hass, "sensor", "nozzle_temperature").state) == 219.6
    assert _state(hass, "binary_sensor", "online").state == "on"
    assert _state(hass, "binary_sensor", "printing").state == "on"
    queue = _state(hass, "sensor", "queue")
    assert queue.state == "2" and queue.attributes["next_job"] == "DM-2026-001 · Eule"
    assert entry.runtime_data.client.backend == "printdog"
    # AMS slot with colour and remaining amount
    registry = er.async_get(hass)
    slot = registry.async_get_entity_id("sensor", DOMAIN, f"{SERIAL}_ams0_tray0")
    assert slot and hass.states.get(slot).state not in ("unknown", "unavailable")
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{SERIAL}_external_254")


async def test_controls_hit_printdog(hass: HomeAssistant, aioclient_mock) -> None:
    mock_printdog(aioclient_mock)
    entry = await _setup(hass)
    client = entry.runtime_data.client
    for call, path in (
        (client.pause(1), "/printers/1/command/pause"),
        (client.resume(1), "/printers/1/command/resume"),
        (client.stop(1), "/printers/1/command/stop"),
        (client.clear_plate(1), "/printers/1/plate-cleared"),
        (client.set_chamber_light(1, True), "/printers/1/command/light_on"),
        (client.set_chamber_light(1, False), "/printers/1/command/light_off"),
        (client.set_print_speed(1, 3), "/printers/1/command/speed_3"),
    ):
        await call
        assert aioclient_mock.mock_calls[-1][0] == "POST" and str(aioclient_mock.mock_calls[-1][1]).endswith(f"/api{path}")
    with pytest.raises(BambuddyRequestError):
        await client.set_print_speed(1, 9)
    with pytest.raises(BambuddyRequestError):
        await client.start_job(11)
    with pytest.raises(BambuddyRequestError):
        await client.camera_stream_url(1)
    assert await client.get_camera_snapshot(1) == b"JPEGDATA"
    assert (await client.get_cover(1))[0] == b"PNGDATA"


async def test_queue_actions(hass: HomeAssistant, aioclient_mock) -> None:
    mock_printdog(aioclient_mock)
    entry = await _setup(hass)
    client = entry.runtime_data.client
    await client.reorder_queue([(21, 1), (11, 2)])
    body = aioclient_mock.mock_calls[-1][2]
    assert aioclient_mock.mock_calls[-1][1].path == "/api/queue/reorder" and body == {"printer_id": 1, "order": [21, 11]}
    await client.cancel_job(11)
    assert aioclient_mock.mock_calls[-1][0] == "DELETE"
    assert (await client.add_job({"library_file_id": 5, "printer_id": 1}))["id"] == 300
    assert (await client.add_job({"archive_id": 7}))["id"] == 301
    assert [f["filename"] for f in await client.list_library_files()] == ["Eule"]
    assert (await client.list_archives())[0]["print_name"] == "Eule"


def test_status_mapping_has_what_entities_read() -> None:
    status = status_from_detail(copy.deepcopy(PD_API_DATA["detail"]))
    assert status["connected"] and status["state"] == "RUNNING" and status["subtask_name"] == "Eule_Beige"
    assert status["temperatures"]["nozzle"] == 219.6 and status["temperatures"]["chamber"] == 32
    unit = status["ams"][0]
    assert unit["humidity"] == 31 and unit["tray"][0]["tray_color"] == "F5E6C8FF" and unit["tray"][0]["exists"] is True
    assert unit["tray"][1]["exists"] is False and unit["tray"][1]["state"] == 9
    assert status["vt_tray"][0]["tray_type"] == "PETG" and status["hms_errors"][0]["code"] == "0C00030000020001"
    offline = status_from_detail({"id": 2, "name": "A1 Mini", "online": False, "state": "offline"})
    assert offline["connected"] is False and offline["state"] == "IDLE" and offline["ams"] == []
    assert queue_item({"id": 1, "status": "queued", "name": "X", "label": None})["status"] == "pending"
    assert queue_item({"id": 1, "status": "sent", "name": "X"})["status"] == "printing"


async def test_config_flow_detects_printdog(hass: HomeAssistant, aioclient_mock) -> None:
    mock_printdog(aioclient_mock)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: "192.168.200.86:8090", CONF_API_KEY: PD_KEY, CONF_VERIFY_SSL: True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY and result["title"] == "PrintDog"
    assert result["data"][CONF_BACKEND] == "printdog" and result["data"][CONF_URL] == PD_URL
    await hass.async_block_till_done()


async def test_config_flow_wrong_key_on_printdog(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"{PD_URL}/api/status", status=401, json={"detail": "API-Schlüssel fehlt oder ist falsch"})
    aioclient_mock.get(f"{PD_API}/printers", status=401)
    aioclient_mock.get(f"{PD_API}/queue", status=401)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: PD_URL, CONF_API_KEY: "falsch", CONF_VERIFY_SSL: True}
    )
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reconfigure_switches_bambuddy_entry_to_printdog(hass: HomeAssistant, aioclient_mock) -> None:
    """The existing entry keeps its devices and entity ids; only the server changes."""
    from .conftest import API_KEY, URL

    mock_bambuddy(aioclient_mock)
    entry = MockConfigEntry(domain=DOMAIN, unique_id=URL, title="Bambuddy",
                            data={CONF_URL: URL, CONF_API_KEY: API_KEY, CONF_VERIFY_SSL: True})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.client.backend == "bambuddy"

    mock_printdog(aioclient_mock)
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: PD_URL, CONF_API_KEY: PD_KEY, CONF_VERIFY_SSL: True}
    )
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert entry.data[CONF_BACKEND] == "printdog" and entry.title == "PrintDog" and entry.unique_id == PD_URL
    assert entry.runtime_data.client.backend == "printdog"


async def test_client_without_backend_flag_stays_bambuddy(hass: HomeAssistant, aioclient_mock) -> None:
    mock_bambuddy(aioclient_mock)
    from .conftest import API_KEY, URL

    entry = MockConfigEntry(domain=DOMAIN, unique_id=URL, data={CONF_URL: URL, CONF_API_KEY: API_KEY, CONF_VERIFY_SSL: True})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert not isinstance(entry.runtime_data.client, PrintDogApiClient)

