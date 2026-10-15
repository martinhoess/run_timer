"""Randfälle aus der Mutationsprobe (ripley, 2026-10-15)."""
from __future__ import annotations
from datetime import timedelta
from typing import Any
import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_mock_service
from .conftest import FAN, add_entry, advance, call, dt_state, local, off_time, switch
from .test_restore import ENTRY_ID, stored

pytestmark = pytest.mark.usefixtures("base")


async def test_cancel_stops_retry(hass, freezer):
    """cancel stoppt einen wartenden Wiederholversuch."""
    attempts = []
    async def turn_off(c: ServiceCall) -> None:
        attempts.append(1)
        raise HomeAssistantError("cloud timeout")
    hass.states.async_set("switch.plug", "off")
    hass.services.async_register("switch", "turn_off", turn_off)
    await add_entry(hass, entity_id="switch.plug", minutes=10)
    hass.states.async_set("switch.plug", "on")
    await advance(hass, freezer, timedelta(minutes=10))
    await call(hass, "cancel", entity_id="switch.plug", what="off")
    await advance(hass, freezer, timedelta(minutes=5))
    assert attempts == [1]


async def test_failed_plan_on_running_device_keeps_end(hass, freezer):
    """Plan scheitert bei laufendem Gerät: Plan-Ausschaltzeit bleibt."""
    entry = await add_entry(hass, on_action=[{"action": "script.does_not_exist"}])
    await switch(hass, True)
    await call(hass, "on_at", at="13:00", duration=30)
    await advance(hass, freezer, timedelta(hours=1))
    assert off_time(hass, entry) == local("2026-10-15 13:30")


async def test_slow_action_keeps_plan_end(hass, freezer):
    """Gerät meldet „an“ erst nach der Aktion: Plandauer statt Standarddauer."""
    hass.states.async_set("climate.room", "off")
    async_mock_service(hass, "climate", "set_hvac_mode")
    action = [{"action": "climate.set_hvac_mode", "target": {"entity_id": "{{ entity_id }}"}, "data": {"hvac_mode": "cool"}}]
    entry = await add_entry(hass, entity_id="climate.room", on_action=action)
    await call(hass, "on_at", entity_id="climate.room", at="13:00", duration=30)
    await advance(hass, freezer, timedelta(hours=1))
    hass.states.async_set("climate.room", "cool")
    await hass.async_block_till_done()
    assert off_time(hass, entry) == local("2026-10-15 13:30")


async def test_cancel_after_restart_survives_blip(hass, hass_storage):
    """Nach Neustart abgebrochener Timer bleibt nach kurzem Ausfall abgebrochen."""
    await switch(hass, True)
    stored(hass_storage, off_at=local("2026-10-15 14:00"))
    entry = await add_entry(hass, entry_id=ENTRY_ID)
    await call(hass, "cancel", what="off")
    hass.states.async_set(FAN, "unavailable")
    await hass.async_block_till_done()
    hass.states.async_set(FAN, "on")
    await hass.async_block_till_done()
    assert off_time(hass, entry) is None


async def test_missed_plan_waits_for_unreachable_at_start(hass, hass_storage):
    """Verpasster Plan wartet, wenn das Gerät beim Start nicht erreichbar ist."""
    hass.states.async_set("switch.plug", "unavailable")
    async_mock_service(hass, "switch", "turn_on")
    stored(hass_storage, on_at=local("2026-10-15 11:20"))
    entry = await add_entry(hass, entity_id="switch.plug", entry_id=ENTRY_ID)
    assert dt_state(hass, entry, "switch_on_at") == local("2026-10-15 11:20")


async def test_plan_not_run_on_unknown(hass, freezer):
    """Fälliger Plan läuft nicht bei unavailable → unknown."""
    entry = await add_entry(hass)
    await call(hass, "on_at", at="13:00")
    hass.states.async_set(FAN, "unavailable")
    await advance(hass, freezer, timedelta(hours=1, minutes=10))
    hass.states.async_set(FAN, "unknown")
    await hass.async_block_till_done()
    assert dt_state(hass, entry, "switch_on_at") == local("2026-10-15 13:00")


async def test_rename_updates_unique_id(hass):
    """Umbenennung zieht die unique_id mit (Dublettenprüfung)."""
    entry = await add_entry(hass)
    er.async_get(hass).async_update_entity(FAN, new_entity_id="input_boolean.fan2")
    await hass.async_block_till_done()
    assert entry.unique_id == "input_boolean.fan2"


async def test_invalid_action_leaves_no_timer(hass, freezer):
    """Ungültige Einschalt-Aktion zur Laufzeit hinterlässt keine Ausschaltzeit."""
    entry = await add_entry(hass, on_action=[{"delay": "nonsense"}])
    await call(hass, "on_at", at="13:00", duration=30)
    await advance(hass, freezer, timedelta(hours=1))
    assert off_time(hass, entry) is None


async def test_retry_not_before_5min(hass, freezer):
    """Wiederholversuch frühestens nach 5 Minuten."""
    attempts = []
    async def turn_off(c: ServiceCall) -> None:
        attempts.append(1)
        raise HomeAssistantError("x")
    hass.states.async_set("switch.plug", "off")
    hass.services.async_register("switch", "turn_off", turn_off)
    await add_entry(hass, entity_id="switch.plug", minutes=10)
    hass.states.async_set("switch.plug", "on")
    await advance(hass, freezer, timedelta(minutes=10))
    await advance(hass, freezer, timedelta(minutes=4))
    assert attempts == [1]
