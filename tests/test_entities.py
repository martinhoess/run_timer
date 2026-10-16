"""Spec device-setup: entities and devices."""

from __future__ import annotations

from datetime import timedelta
import json
from pathlib import Path

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.run_timer.const import DOMAIN

from .conftest import add_entry, advance, call, dt_state, eid, local, off_time, switch

pytestmark = pytest.mark.usefixtures("base")

KEYS = [
    ("number", "default_minutes"),
    ("sensor", "off_time"),
    ("sensor", "on_time"),
    ("time", "switch_on_at"),
    ("time", "switch_off_at"),
]


async def test_entities_join_existing_device(hass: HomeAssistant) -> None:
    """Ziel-Entität mit Gerät."""
    other = MockConfigEntry(domain="test")
    other.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=other.entry_id, identifiers={("test", "fan1")}, name="Living Fan"
    )
    er.async_get(hass).async_get_or_create(
        "switch", "test", "fan1", device_id=device.id, suggested_object_id="living_fan"
    )
    hass.states.async_set("switch.living_fan", "off")
    for service in ("turn_on", "turn_off"):
        async_mock_service(hass, "switch", service)
    entry = await add_entry(hass, entity_id="switch.living_fan")
    registry = er.async_get(hass)
    for platform, key in KEYS:
        assert registry.async_get(eid(hass, entry, platform, key)).device_id == device.id
    assert (
        dr.async_get(hass).async_get_device_by_identifier((DOMAIN, entry.entry_id), entry.entry_id)
        is None
    )


async def test_entities_get_own_device(hass: HomeAssistant) -> None:
    """Ziel-Entität ohne Gerät."""
    entry = await add_entry(hass)
    own = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )
    assert own is not None
    registry = er.async_get(hass)
    for platform, key in KEYS:
        assert registry.async_get(eid(hass, entry, platform, key)).device_id == own.id


async def test_empty_values(hass: HomeAssistant) -> None:
    """Leere Werte."""
    entry = await add_entry(hass)
    assert off_time(hass, entry) is None
    assert dt_state(hass, entry, "switch_on_at") is None
    assert dt_state(hass, entry, "switch_off_at") is None
    assert hass.states.get(eid(hass, entry, "sensor", "off_time")).state == "unknown"
    assert hass.states.get(eid(hass, entry, "sensor", "on_time")).state == "unknown"


async def test_default_change_applies_next_start(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Standarddauer ändern bei laufendem Timer."""
    entry = await add_entry(hass)
    await switch(hass, True)
    number = eid(hass, entry, "number", "default_minutes")
    await hass.services.async_call(
        "number", "set_value", {"entity_id": number, "value": 120}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(number).state == "120"
    assert off_time(hass, entry) == local("2026-10-15 16:00")
    await switch(hass, False)
    await advance(hass, freezer, timedelta(minutes=10))
    await switch(hass, True)
    assert off_time(hass, entry) == local("2026-10-15 14:10")


@pytest.mark.parametrize("value", [-1, 1441])
async def test_default_out_of_range(hass: HomeAssistant, value: int) -> None:
    """Wert außerhalb des Bereichs."""
    entry = await add_entry(hass)
    number = eid(hass, entry, "number", "default_minutes")
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "number", "set_value", {"entity_id": number, "value": value}, blocking=True
        )
    assert hass.states.get(number).state == "240"


async def test_time_entity_off_at_passed_means_tomorrow(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """„Aus um“ per Entität auf eine vergangene Uhrzeit heißt morgen."""
    entry = await add_entry(hass)
    await hass.services.async_call(
        "time",
        "set_value",
        {"entity_id": eid(hass, entry, "time", "switch_off_at"), "time": "08:00:00"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert dt_state(hass, entry, "switch_off_at") == local("2026-10-16 08:00")


async def test_time_entity_shows_hours_and_minutes(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Die Uhrzeit-Entität zeigt volle Minuten, auch bei krummer Sekunde."""
    entry = await add_entry(hass)
    freezer.tick(timedelta(seconds=7, microseconds=482913))
    await call(hass, "off_in", minutes=15)
    state = hass.states.get(eid(hass, entry, "time", "switch_off_at"))
    assert state.state == "12:15:00"


def on_time(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    """Return the raw state of the on time sensor."""
    return hass.states.get(eid(hass, entry, "sensor", "on_time")).state


async def test_on_time_shows_exact_plan(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Einschaltzeit zeigt den Plan mit Datum und Sekunden, bis er gelaufen ist."""
    entry = await add_entry(hass)
    freezer.tick(timedelta(seconds=27))
    await call(hass, "on_in", minutes=1)
    assert on_time(hass, entry) == "2026-10-15T10:01:27+00:00"
    assert hass.states.get(eid(hass, entry, "time", "switch_on_at")).state == "12:01:00"
    await call(hass, "on_at", at="2026-10-17 06:00:00")
    assert on_time(hass, entry) == local("2026-10-17 06:00").isoformat()
    await call(hass, "cancel", what="on")
    assert on_time(hass, entry) == "unknown"
    await call(hass, "on_in", minutes=1)
    await advance(hass, freezer, timedelta(minutes=1))
    assert hass.states.get("input_boolean.fan").state == "on"
    assert on_time(hass, entry) == "unknown"


@pytest.mark.parametrize("lang", ["en", "de"])
def test_names_sort_start_before_stop(lang: str) -> None:
    """Auf der Geräteseite (alphabetisch) steht Ein vor Aus, in beiden Sprachen."""
    path = Path(__file__).parent.parent / "custom_components/run_timer/translations" / f"{lang}.json"
    names = json.loads(path.read_text(encoding="utf-8"))["entity"]
    for platform, first, second in (
        ("time", "switch_on_at", "switch_off_at"),
        ("sensor", "on_time", "off_time"),
    ):
        a, b = names[platform][first]["name"], names[platform][second]["name"]
        assert a.casefold() < b.casefold(), (a, b)
        assert a.split()[0] == b.split()[0], (a, b)


async def test_websocket_list_managed_entities(hass: HomeAssistant, hass_ws_client) -> None:
    """Das Panel bekommt je verwaltetem Gerät seine run_timer-Entitäten."""
    from homeassistant.components import websocket_api
    from homeassistant.setup import async_setup_component

    from custom_components.run_timer.frontend import websocket_list

    assert await async_setup_component(hass, "websocket_api", {})
    websocket_api.async_register_command(hass, websocket_list)
    entry = await add_entry(hass)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "run_timer/list"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "input_boolean.fan": {key: eid(hass, entry, platform, key) for platform, key in KEYS}
    }


async def test_frontend_setup_registers_panel(hass: HomeAssistant, hass_ws_client) -> None:
    """Mit Frontend: Skript liegt bereit, wird auf jeder Seite geladen, der Befehl antwortet."""
    from pathlib import Path as _Path
    from unittest.mock import AsyncMock, Mock

    from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, UrlManager
    from homeassistant.setup import async_setup_component

    # hass_frontend fehlt in der Testumgebung: Frontend-Teile nachbilden, die run_timer nutzt.
    assert await async_setup_component(hass, "websocket_api", {})
    real_http, mock_http = hass.http, Mock(async_register_static_paths=AsyncMock())
    hass.http = mock_http
    hass.data[DATA_EXTRA_MODULE_URL] = UrlManager(lambda *_: None, [])
    hass.config.components.add("frontend")
    entry = await add_entry(hass)
    hass.http = real_http

    (config,) = mock_http.async_register_static_paths.call_args.args[0]
    assert config.url_path == "/run_timer_static/run-timer-panel.js"
    assert _Path(config.path).is_file()
    manifest = json.loads((_Path(config.path).parent.parent / "manifest.json").read_text())
    assert hass.data[DATA_EXTRA_MODULE_URL].urls == {
        f"/run_timer_static/run-timer-panel.js?v={manifest['version']}"
    }
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "run_timer/list"})
    msg = await client.receive_json()
    assert msg["result"]["input_boolean.fan"]["off_time"] == eid(hass, entry, "sensor", "off_time")
