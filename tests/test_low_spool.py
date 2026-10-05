"""Warning when an AMS spool runs low."""

from homeassistant.core import HomeAssistant

from custom_components.bambuddy.planner import low_spools

from .conftest import STATUS, mock_bambuddy
from .test_sensor import _setup, _state

X1 = "00M09A111111111"


def test_low_spools_logic() -> None:
    status = STATUS[1]
    # PLA at 80 %; PETG unknown (-1); slot 3 missing; slot 4 empty; external ignored.
    assert low_spools(status, 10) == []
    assert low_spools(status, 80) == [
        {"ams": "1", "slot": 1, "type": "PLA", "name": "PLA Basic", "remaining": 80}
    ]
    assert low_spools(status, 0) == []
    assert low_spools(None, 50) == []
    ht = {"ams": [{"id": 128, "is_ams_ht": True, "tray": [{"id": 0, "tray_type": "PETG", "remain": 0}]}]}
    assert low_spools(ht, 5)[0]["ams"] == "HT 1"


async def test_filament_low_sensor(hass: HomeAssistant, aioclient_mock) -> None:
    mock_bambuddy(aioclient_mock)
    entry = await _setup(hass)

    state = _state(hass, "binary_sensor", f"{X1}_filament_low")
    assert state.state == "off"
    assert state.attributes["threshold"] == 10
    assert state.attributes["spools"] == []

    hass.config_entries.async_update_entry(entry, options={**entry.options, "low_spool_threshold": 85})
    await hass.async_block_till_done()

    state = _state(hass, "binary_sensor", f"{X1}_filament_low")
    assert state.state == "on"
    assert state.attributes["spools"][0]["name"] == "PLA Basic"
    assert state.attributes["spools"][0]["remaining"] == 80
