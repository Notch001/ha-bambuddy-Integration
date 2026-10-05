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


async def test_card_registered_as_dashboard_resource(hass: HomeAssistant, aioclient_mock) -> None:
    """Dashboards (also in the companion apps) load the card as a resource."""
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, "lovelace", {})
    mock_bambuddy(aioclient_mock)
    await _setup(hass)
    await hass.async_block_till_done()

    resources = hass.data["lovelace"].resources
    urls = [item["url"] for item in resources.async_items()]
    assert len([u for u in urls if u.startswith("/bambuddy/bambuddy-card.js?v=")]) == 1

    # An entry from an older version is updated, not duplicated.
    from custom_components.bambuddy import _async_register_card_resource

    await _async_register_card_resource(hass, "/bambuddy/bambuddy-card.js?v=9.9.9")
    urls = [item["url"] for item in resources.async_items()]
    assert [u for u in urls if u.startswith("/bambuddy/")] == ["/bambuddy/bambuddy-card.js?v=9.9.9"]
