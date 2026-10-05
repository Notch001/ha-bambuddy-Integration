"""The shipped blueprints load and behave as documented."""

import asyncio
from datetime import timedelta
from pathlib import Path
import shutil

from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.bambuddy.const import DOMAIN

from .conftest import API, STATUS, mock_bambuddy
from .test_sensor import _setup

BLUEPRINTS = Path(__file__).parent.parent / "blueprints" / "automation" / "bambuddy"


def _install(hass: HomeAssistant) -> None:
    target = Path(hass.config.path("blueprints/automation/bambuddy"))
    target.mkdir(parents=True, exist_ok=True)
    for file in BLUEPRINTS.glob("*.yaml"):
        shutil.copy(file, target / file.name)


async def test_auto_power_blueprint(hass: HomeAssistant) -> None:
    _install(hass)
    calls: list[str] = []

    async def record(call):
        calls.append(call.service)
        hass.states.async_set("switch.plug", "on" if call.service == "turn_on" else "off")

    hass.services.async_register("switch", "turn_on", record)
    hass.services.async_register("switch", "turn_off", record)
    hass.states.async_set("switch.plug", "on")
    hass.states.async_set("binary_sensor.x1c_in_use", "on")

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "id": "power",
                "use_blueprint": {
                    "path": "bambuddy/auto_power.yaml",
                    "input": {
                        "in_use": "binary_sensor.x1c_in_use",
                        "plug": "switch.plug",
                        "off_delay": {"minutes": 15},
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()
    autos = hass.states.async_all("automation")
    assert [a.state for a in autos] == ["on"], [(a.entity_id, a.state, a.attributes) for a in autos]

    # Unused, but not long enough yet
    hass.states.async_set("binary_sensor.x1c_in_use", "off")
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
    await hass.async_block_till_done()
    assert calls == []

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=16))
    await hass.async_block_till_done()
    assert calls == ["turn_off"]

    # A job is waiting for the printer again
    hass.states.async_set("binary_sensor.x1c_in_use", "on")
    await hass.async_block_till_done()
    assert calls == ["turn_off", "turn_on"]


async def test_notification_blueprint_is_valid(hass: HomeAssistant) -> None:
    """Validates against Home Assistant's blueprint and automation schemas."""
    from homeassistant.components.blueprint import models

    _install(hass)
    assert await async_setup_component(hass, "automation", {})
    domain_blueprints = hass.data["blueprint"]["automation"]
    blueprint = await domain_blueprints.async_get_blueprint("bambuddy/print_notifications.yaml")
    assert isinstance(blueprint, models.Blueprint)
    assert set(blueprint.inputs) == {"printer_events", "notify_device", "events", "clear_button", "language"}


async def test_notification_blueprint_flow(hass: HomeAssistant, aioclient_mock) -> None:
    """Print finishes -> two notifications; tapping "Cleared" releases the next job."""
    _install(hass)
    mock_bambuddy(aioclient_mock)
    entry = await _setup(hass)
    event_entity = er.async_get(hass).async_get_entity_id("event", DOMAIN, "00M09A111111111_events")

    phone_entry = MockConfigEntry(domain="mobile_app", data={})
    phone_entry.add_to_hass(hass)
    phone = dr.async_get(hass).async_get_or_create(
        config_entry_id=phone_entry.entry_id, identifiers={("mobile_app", "phone")}, name="Phone"
    )

    sent: list[dict] = []

    async def fake_notify(hass, config, variables, context):
        from homeassistant.helpers import template

        sent.append({k: template.render_complex(config[k], variables) for k in ("title", "message", "data") if k in config})

    with patch("homeassistant.components.mobile_app.device_action.async_call_action_from_config", fake_notify):
        assert await async_setup_component(
            hass,
            "automation",
            {
                "automation": {
                    "id": "notify",
                    "use_blueprint": {
                        "path": "bambuddy/print_notifications.yaml",
                        "input": {"printer_events": [event_entity], "notify_device": phone.id, "language": "en"},
                    },
                }
            },
        )
        await hass.async_block_till_done()

        finished = {**STATUS, 1: {**STATUS[1], "state": "FINISH", "awaiting_plate_clear": True}}
        mock_bambuddy(aioclient_mock, status=finished)
        aioclient_mock.post(f"{API}/printers/1/clear-plate", json={})
        await entry.runtime_data.async_refresh()
        # Not async_block_till_done: the automation now waits (up to a day) for the tap.
        for _ in range(20):
            await asyncio.sleep(0)

        titles = [s["title"] for s in sent]
        assert titles == ["X1C Werkstatt is done", "X1C Werkstatt: clear the build plate"]
        assert sent[0]["message"] == "Benchy has finished. Up next: Halterung"
        button = sent[1]["data"]["actions"][0]
        assert button["title"] == "Cleared"

        hass.bus.async_fire("mobile_app_notification_action", {"action": button["action"]})
        await hass.async_block_till_done(wait_background_tasks=False)
        assert any(
            c[0] == "POST" and c[1].path.endswith("/printers/1/clear-plate") for c in aioclient_mock.mock_calls
        )
