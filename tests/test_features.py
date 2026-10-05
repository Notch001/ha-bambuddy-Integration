"""AMS, controls, cover image and camera."""

import pytest

from homeassistant.components.camera import async_get_image
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from custom_components.bambuddy.const import DOMAIN

from .conftest import API, mock_bambuddy
from .test_sensor import _entity_id, _setup, _state

X1 = "00M09A111111111"
A1 = "0300AA222222222"


async def test_ams_sensors(hass: HomeAssistant, aioclient_mock) -> None:
    mock_bambuddy(aioclient_mock)
    await _setup(hass)

    assert _state(hass, "sensor", f"{X1}_ams0_humidity").state == "23"
    assert float(_state(hass, "sensor", f"{X1}_ams0_temperature").state) == 26.5
    # Printer can't dry -> no drying sensor
    assert er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{X1}_ams0_drying_remaining") is None

    slot1 = _state(hass, "sensor", f"{X1}_ams0_tray0")
    assert slot1.state == "PLA Basic"
    assert slot1.attributes["color"] == "#FF0000"
    assert slot1.attributes["remaining"] == 80
    assert slot1.attributes["active"] is False
    assert "%23FF0000" in slot1.attributes["entity_picture"]
    assert slot1.name.endswith("AMS 1 Slot 1") or slot1.name.endswith("AMS 1 slot 1")

    slot2 = _state(hass, "sensor", f"{X1}_ams0_tray1")
    assert slot2.attributes["remaining"] is None  # -1 = unknown
    assert slot2.attributes["active"] is True  # tray_now == 1

    assert _state(hass, "sensor", f"{X1}_ams0_tray2").state == "empty"
    assert _state(hass, "sensor", f"{X1}_ams0_tray3").state == "unknown"
    assert _state(hass, "sensor", f"{X1}_external_254").state == "TPU"

    assert _state(hass, "sensor", f"{X1}_stage").state == "Heatbed preheating"
    assert _state(hass, "sensor", f"{X1}_nozzle").state == "0.4 mm"


async def test_buttons(hass: HomeAssistant, aioclient_mock) -> None:
    mock_bambuddy(aioclient_mock)
    await _setup(hass)

    # Running print: pause and stop offered, resume and clear plate not
    assert _state(hass, "button", f"{X1}_pause").state != STATE_UNAVAILABLE
    assert _state(hass, "button", f"{X1}_stop").state != STATE_UNAVAILABLE
    assert _state(hass, "button", f"{X1}_resume").state == STATE_UNAVAILABLE
    assert _state(hass, "button", f"{X1}_clear_plate").state == STATE_UNAVAILABLE

    aioclient_mock.post(f"{API}/printers/1/print/pause", json={"status": "paused"})
    await hass.services.async_call(
        "button", "press", {ATTR_ENTITY_ID: _entity_id(hass, "button", f"{X1}_pause")}, blocking=True
    )
    assert any(str(url).endswith("/printers/1/print/pause") for _, url, *_ in aioclient_mock.mock_calls)


async def test_button_without_permission(hass: HomeAssistant, aioclient_mock) -> None:
    mock_bambuddy(aioclient_mock)
    await _setup(hass)
    aioclient_mock.post(f"{API}/printers/1/print/stop", status=403)

    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            "button", "press", {ATTR_ENTITY_ID: _entity_id(hass, "button", f"{X1}_stop")}, blocking=True
        )
    assert exc.value.translation_key == "no_control_permission"


async def test_button_rejected(hass: HomeAssistant, aioclient_mock) -> None:
    mock_bambuddy(aioclient_mock)
    await _setup(hass)
    aioclient_mock.post(f"{API}/printers/1/print/pause", status=400, json={"detail": "Printer not connected"})

    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            "button", "press", {ATTR_ENTITY_ID: _entity_id(hass, "button", f"{X1}_pause")}, blocking=True
        )
    assert exc.value.translation_placeholders == {"detail": "Printer not connected"}


async def test_chamber_light_and_speed(hass: HomeAssistant, aioclient_mock) -> None:
    mock_bambuddy(aioclient_mock)
    await _setup(hass)

    light = _entity_id(hass, "light", f"{X1}_chamber_light")
    assert hass.states.get(light).state == "off"
    aioclient_mock.post(f"{API}/printers/1/chamber-light", json={"status": "ok"})
    await hass.services.async_call("light", "turn_on", {ATTR_ENTITY_ID: light}, blocking=True)
    assert hass.states.get(light).state == "on"
    call = next(c for c in aioclient_mock.mock_calls if c[1].path.endswith("/chamber-light"))
    assert call[1].query["on"] == "true"

    speed = _entity_id(hass, "select", f"{X1}_print_speed")
    assert hass.states.get(speed).state == "standard"
    aioclient_mock.post(f"{API}/printers/1/print-speed", json={"status": "ok"})
    await hass.services.async_call(
        "select", "select_option", {ATTR_ENTITY_ID: speed, "option": "sport"}, blocking=True
    )
    call = next(c for c in aioclient_mock.mock_calls if c[1].path.endswith("/print-speed"))
    assert call[1].query["mode"] == "3"

    # Idle/offline printer: no speed change possible
    assert _state(hass, "select", f"{A1}_print_speed").state == STATE_UNAVAILABLE


async def test_cover_image(hass: HomeAssistant, aioclient_mock, hass_client) -> None:
    mock_bambuddy(aioclient_mock)
    await _setup(hass)

    entity_id = _entity_id(hass, "image", f"{X1}_cover")
    client = await hass_client()
    resp = await client.get(f"/api/image_proxy/{entity_id}")
    assert resp.status == 200
    assert await resp.read() == b"PNGDATA"


async def test_camera_snapshot(hass: HomeAssistant, aioclient_mock) -> None:
    mock_bambuddy(aioclient_mock)
    await _setup(hass)

    image = await async_get_image(hass, _entity_id(hass, "camera", f"{X1}_camera"))
    assert image.content == b"JPEGDATA"
    # Snapshot used a stream token, not the API key in the URL
    token_calls = [c for c in aioclient_mock.mock_calls if str(c[1]).endswith("/camera/stream-token")]
    assert len(token_calls) == 1

    # Offline printer -> camera unavailable
    assert _state(hass, "camera", f"{A1}_camera").state == STATE_UNAVAILABLE
