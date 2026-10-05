"""Queue actions, to-do editing, statistics and costs."""

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from custom_components.bambuddy.const import CONF_ENABLE_COSTS, DOMAIN

from .conftest import API, mock_bambuddy
from .test_sensor import _entity_id, _setup, _state

X1 = "00M09A111111111"


def _calls(aioclient_mock, method: str, suffix: str):
    return [c for c in aioclient_mock.mock_calls if c[0] == method and c[1].path.endswith(suffix)]


async def test_reorder_and_delete_via_todo(hass: HomeAssistant, aioclient_mock) -> None:
    mock_bambuddy(aioclient_mock)
    entry = await _setup(hass)
    todo = _entity_id(hass, "todo", f"{entry.entry_id}_queue_list")
    aioclient_mock.post(f"{API}/queue/reorder", json={})
    aioclient_mock.post(f"{API}/queue/12/cancel", json={})

    # Waiting order is 12, 11; move 11 to the front
    entity = hass.data["todo"].get_entity(todo)
    await entity.async_move_todo_item("11", None)
    body = _calls(aioclient_mock, "POST", "/queue/reorder")[-1][2]
    assert body == {"items": [{"id": 11, "position": 1}, {"id": 12, "position": 2}]}

    await hass.services.async_call("todo", "remove_item", {ATTR_ENTITY_ID: todo, "item": ["12"]}, blocking=True)
    assert _calls(aioclient_mock, "POST", "/queue/12/cancel")

    # The running job can't be moved or deleted
    with pytest.raises(ServiceValidationError):
        await entity.async_move_todo_item("10", None)


async def test_services(hass: HomeAssistant, aioclient_mock) -> None:
    mock_bambuddy(aioclient_mock)
    await _setup(hass)
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, X1)})

    aioclient_mock.post(f"{API}/printers/1/clear-plate", json={})
    await hass.services.async_call(DOMAIN, "clear_plate", {"device_id": device.id}, blocking=True)
    assert _calls(aioclient_mock, "POST", "/printers/1/clear-plate")

    aioclient_mock.post(f"{API}/queue/12/start", json={})
    await hass.services.async_call(DOMAIN, "start_job", {"job_id": 12}, blocking=True)
    assert _calls(aioclient_mock, "POST", "/queue/12/start")

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "cancel_job", {"job_id": 999}, blocking=True)

    aioclient_mock.get(f"{API}/archives/", json=[
        {"id": 7, "print_name": "Kabelclip x20", "filename": "kabelclip.3mf", "printer_id": 2, "plate_id": 1},
        {"id": 3, "print_name": "Kabelclip x20", "filename": "kabelclip.3mf", "printer_id": 1, "plate_id": 1},
    ])
    aioclient_mock.post(f"{API}/queue/", json={"id": 99})
    result = await hass.services.async_call(
        DOMAIN, "print_again", {"name": "kabelclip"}, blocking=True, return_response=True
    )
    assert result == {"job_id": 99, "name": "Kabelclip x20"}
    # newest archive, on the printer it was printed on
    assert _calls(aioclient_mock, "POST", "/queue/")[-1][2] == {"archive_id": 7, "printer_id": 2, "plate_id": 1}

    aioclient_mock.get(f"{API}/library/files/", json=[
        {"id": 5, "filename": "Halter links.3mf"}, {"id": 6, "filename": "Halter rechts.3mf"},
    ])
    with pytest.raises(ServiceValidationError):  # ambiguous
        await hass.services.async_call(DOMAIN, "print_file", {"name": "halter", "device_id": device.id}, blocking=True)
    await hass.services.async_call(
        DOMAIN, "print_file", {"name": "Halter rechts", "device_id": device.id}, blocking=True
    )
    assert _calls(aioclient_mock, "POST", "/queue/")[-1][2] == {"library_file_id": 6, "printer_id": 1}


async def test_queue_action_without_permission(hass: HomeAssistant, aioclient_mock) -> None:
    mock_bambuddy(aioclient_mock)
    await _setup(hass)
    aioclient_mock.post(f"{API}/queue/12/cancel", status=403)
    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(DOMAIN, "cancel_job", {"job_id": 12}, blocking=True)
    assert exc.value.translation_key == "no_control_permission"


async def test_statistics_and_schedule_sensors(hass: HomeAssistant, aioclient_mock) -> None:
    mock_bambuddy(aioclient_mock)
    entry = await _setup(hass)
    eid = entry.entry_id

    total = _state(hass, "sensor", f"{eid}_prints_total")
    assert total.state == "120"
    assert total.attributes["by_printer"] == {"X1C Werkstatt": 80, "A1 Mini": 40}
    assert _state(hass, "sensor", f"{eid}_success_rate").state == "83.3"
    assert float(_state(hass, "sensor", f"{eid}_filament_total").state) == 9876.5
    # Costs are off by default
    assert hass.states.async_entity_ids("sensor") and not any(
        "cost" in e for e in hass.states.async_entity_ids("sensor")
    )
    # Schedule: X1C prints 83 more minutes, then Halterung (60 min)
    assert _state(hass, "sensor", f"{X1}_free_at").state not in ("unknown", "unavailable")
    assert _state(hass, "sensor", f"{eid}_farm_done_at").state not in ("unknown", "unavailable")
    jobs = _state(hass, "sensor", f"{eid}_queue_pending").attributes["jobs"]
    assert all(j["estimated_start"] for j in jobs)
    assert _state(hass, "binary_sensor", f"{X1}_in_use").state == "on"
    assert hass.states.get(_entity_id(hass, "event", f"{X1}_events")) is not None


async def test_cost_sensors_option(hass: HomeAssistant, aioclient_mock) -> None:
    mock_bambuddy(aioclient_mock)
    entry = await _setup(hass)
    hass.config_entries.async_update_entry(entry, options={**entry.options, CONF_ENABLE_COSTS: True})
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    cost = _state(hass, "sensor", f"{entry.entry_id}_filament_cost_total")
    assert float(cost.state) == 210.4
    assert cost.attributes["unit_of_measurement"] == "EUR"
    assert float(_state(hass, "sensor", f"{entry.entry_id}_energy_total").state) == 55.2


async def test_print_event_fires(hass: HomeAssistant, aioclient_mock) -> None:
    from .conftest import STATUS

    mock_bambuddy(aioclient_mock)
    entry = await _setup(hass)
    event_id = _entity_id(hass, "event", f"{X1}_events")

    finished = {**STATUS, 1: {**STATUS[1], "state": "FINISH", "awaiting_plate_clear": True}}
    mock_bambuddy(aioclient_mock, status=finished)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(event_id)
    assert state.attributes["event_type"] == "plate_clear_required"  # the last of the two events
    assert state.attributes["job"] == "Benchy"
    assert state.attributes["next_job"] == "Halterung"
