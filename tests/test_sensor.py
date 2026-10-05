"""Entity tests against a fake Bambuddy."""

import copy

from homeassistant.const import CONF_URL, CONF_VERIFY_SSL, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bambuddy.const import CONF_API_KEY, DOMAIN

from .conftest import API_KEY, STATUS, URL, mock_bambuddy


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=URL,
        data={CONF_URL: URL, CONF_API_KEY: API_KEY, CONF_VERIFY_SSL: True},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _entity_id(hass: HomeAssistant, domain: str, unique_id: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(domain, DOMAIN, unique_id)
    assert entity_id, unique_id
    return entity_id


def _state(hass, domain, unique_id):
    return hass.states.get(_entity_id(hass, domain, unique_id))


async def test_printer_sensors(hass: HomeAssistant, aioclient_mock) -> None:
    mock_bambuddy(aioclient_mock)
    await _setup(hass)

    # API key is sent on every request
    assert all(headers.get("X-API-Key") == API_KEY for *_, headers in aioclient_mock.mock_calls)

    x1 = "00M09A111111111"
    assert _state(hass, "sensor", f"{x1}_state").state == "running"
    assert _state(hass, "sensor", f"{x1}_current_print").state == "Benchy"
    assert float(_state(hass, "sensor", f"{x1}_progress").state) == 42.0
    assert _state(hass, "sensor", f"{x1}_remaining_time").state == "83"
    assert _state(hass, "sensor", f"{x1}_end_time").state not in ("unknown", STATE_UNAVAILABLE)
    assert float(_state(hass, "sensor", f"{x1}_chamber_temperature").state) == 35.0
    assert _state(hass, "binary_sensor", f"{x1}_online").state == "on"
    assert _state(hass, "binary_sensor", f"{x1}_printing").state == "on"
    assert _state(hass, "binary_sensor", f"{x1}_error").state == "off"

    queue = _state(hass, "sensor", f"{x1}_queue")
    assert queue.state == "1"
    assert queue.attributes["next_job"] == "Halterung"
    assert queue.attributes["jobs"][0]["print_time_minutes"] == 60

    a1 = "0300AA222222222"
    assert _state(hass, "sensor", f"{a1}_state").state == "offline"
    assert _state(hass, "sensor", f"{a1}_progress").state == "unknown"
    assert _state(hass, "binary_sensor", f"{a1}_online").state == "off"
    assert _state(hass, "binary_sensor", f"{a1}_error").state == "on"
    assert _state(hass, "binary_sensor", f"{a1}_awaiting_plate_clear").state == "on"
    assert _state(hass, "sensor", f"{a1}_hms_errors").state == "1"
    # A1 Mini has no chamber thermometer -> no entity
    assert er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{a1}_chamber_temperature") is None


async def test_queue_sensors(hass: HomeAssistant, aioclient_mock) -> None:
    mock_bambuddy(aioclient_mock)
    entry = await _setup(hass)

    pending = _state(hass, "sensor", f"{entry.entry_id}_queue_pending")
    assert pending.state == "2"
    # Ordered by queue position, unassigned jobs shown as "Any <model>"
    assert pending.attributes["next_job"] == "Schlüsselanhänger"
    assert [j["id"] for j in pending.attributes["jobs"]] == [12, 11]
    assert pending.attributes["jobs"][0]["printer"] == "Any A1 Mini"

    printing = _state(hass, "sensor", f"{entry.entry_id}_queue_printing")
    assert printing.state == "1"
    assert printing.attributes["jobs"][0]["name"] == "Benchy"


async def test_missing_status_marks_printer_unavailable(hass: HomeAssistant, aioclient_mock) -> None:
    from .conftest import STATUS

    mock_bambuddy(aioclient_mock, status={1: STATUS[1]})
    aioclient_mock.get(f"{URL}/api/v1/printers/2/status", status=404)
    await _setup(hass)

    a1 = "0300AA222222222"
    assert _state(hass, "sensor", f"{a1}_state").state == STATE_UNAVAILABLE
    assert _state(hass, "binary_sensor", f"{a1}_online").state == "off"
    assert _state(hass, "sensor", "00M09A111111111_state").state == "running"


async def test_auth_failure_starts_reauth(hass: HomeAssistant, aioclient_mock) -> None:
    mock_bambuddy(aioclient_mock, auth_status=401)
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=URL,
        data={CONF_URL: URL, CONF_API_KEY: "bb_wrong", CONF_VERIFY_SSL: True},
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == "reauth" for f in flows)


async def test_current_print_kept_after_finish(hass: HomeAssistant, aioclient_mock) -> None:
    """The dashboard can say what just finished; idle clears it."""
    status = copy.deepcopy(STATUS)
    status[1]["state"] = "FINISH"
    status[2] = {**status[2], "state": "IDLE", "subtask_name": "Old"}
    mock_bambuddy(aioclient_mock, status=status)
    await _setup(hass)

    assert _state(hass, "sensor", "00M09A111111111_current_print").state == "Benchy"
    assert _state(hass, "sensor", "00M09A111111111_progress").state == "unknown"
    assert _state(hass, "sensor", "0300AA222222222_current_print").state == "unknown"
