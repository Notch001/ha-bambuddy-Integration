"""The queue as a to-do list."""

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .conftest import mock_bambuddy
from .test_sensor import _entity_id, _setup


async def test_queue_todo_list(hass: HomeAssistant, aioclient_mock) -> None:
    mock_bambuddy(aioclient_mock)
    entry = await _setup(hass)

    entity_id = _entity_id(hass, "todo", f"{entry.entry_id}_queue_list")
    # State of a to-do list = number of open items (1 printing + 2 waiting)
    assert hass.states.get(entity_id).state == "3"

    result = await hass.services.async_call(
        "todo", "get_items", {ATTR_ENTITY_ID: entity_id}, blocking=True, return_response=True
    )
    items = result[entity_id]["items"]
    assert [i["summary"] for i in items] == ["▶ Benchy", "1. Schlüsselanhänger", "2. Halterung"]
    assert items[1]["description"] == "Any A1 Mini · 15 min"
    assert items[2]["description"] == "X1C Werkstatt · 60 min · PETG"
    # Read-only: Home Assistant must not offer editing
    assert hass.states.get(entity_id).attributes.get("supported_features", 0) == 0


async def test_card_is_served(hass: HomeAssistant, aioclient_mock, hass_client) -> None:
    """The dashboard card ships with the integration and is served by HA."""
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "http", {})
    mock_bambuddy(aioclient_mock)
    await _setup(hass)

    client = await hass_client()
    resp = await client.get("/bambuddy/bambuddy-card.js")
    assert resp.status == 200
    assert "customElements.define(\"bambuddy-card\"" in await resp.text()
