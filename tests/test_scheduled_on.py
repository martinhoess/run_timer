"""Spec scheduled-on (and device-setup: own switch-on action)."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import async_mock_service

from homeassistant.core import HomeAssistant

from .conftest import FAN, add_entry, advance, call, dt_state, local, off_time, switch

pytestmark = pytest.mark.usefixtures("base")


async def test_on_at_passed_time_means_tomorrow(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Ein um 06:00, gesetzt um 23:00."""
    entry = await add_entry(hass)
    await advance(hass, freezer, timedelta(hours=11))
    await call(hass, "on_at", at="06:00")
    assert dt_state(hass, entry, "switch_on_at") == local("2026-10-16 06:00")


async def test_new_plan_replaces_old(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Neuer Plan ersetzt alten."""
    entry = await add_entry(hass)
    await call(hass, "on_at", at="06:00")
    await call(hass, "on_in", minutes=30)
    assert dt_state(hass, entry, "switch_on_at") == local("2026-10-15 12:30")
    await advance(hass, freezer, timedelta(minutes=30))
    assert hass.states.get(FAN).state == "on"
    await switch(hass, False)
    await advance(hass, freezer, timedelta(hours=18))
    assert hass.states.get(FAN).state == "off"


async def test_plan_with_duration(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Plan mit Dauer: an, Ausschaltzeit Planzeit + 90 min."""
    entry = await add_entry(hass)
    await call(hass, "on_at", at="13:00", duration=90)
    await advance(hass, freezer, timedelta(hours=1))
    assert hass.states.get(FAN).state == "on"
    assert off_time(hass, entry) == local("2026-10-15 14:30")
    assert dt_state(hass, entry, "switch_on_at") is None
    await advance(hass, freezer, timedelta(minutes=90))
    assert hass.states.get(FAN).state == "off"


async def test_plan_overrides_running_timer(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Gerät läuft schon: Plan setzt die kürzere Ausschaltzeit."""
    entry = await add_entry(hass)
    await switch(hass, True)
    await call(hass, "off_at", at="20:00")
    await call(hass, "on_at", at="13:00", duration=30)
    await advance(hass, freezer, timedelta(hours=1))
    assert off_time(hass, entry) == local("2026-10-15 13:30")
    assert dt_state(hass, entry, "switch_off_at") is None


async def test_plan_survives_manual_off(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Ausgeschaltet vor dem Plan."""
    await add_entry(hass)
    await switch(hass, True)
    await call(hass, "on_at", at="14:00")
    await switch(hass, False)
    await advance(hass, freezer, timedelta(hours=2))
    assert hass.states.get(FAN).state == "on"


async def test_time_entity_plans_switch_on(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Setzen von „ein um“ entspricht on_at ohne Dauer (nächstes Vorkommen)."""
    entry = await add_entry(hass, minutes=60)
    from .conftest import eid

    await hass.services.async_call(
        "time",
        "set_value",
        {"entity_id": eid(hass, entry, "time", "switch_on_at"), "time": "13:00:00"},
        blocking=True,
    )
    await advance(hass, freezer, timedelta(hours=1))
    assert hass.states.get(FAN).state == "on"
    assert off_time(hass, entry) == local("2026-10-15 14:00")


async def test_own_switch_on_action(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Eigene Einschalt-Aktion statt homeassistant.turn_on."""
    hass.states.async_set("climate.room", "off")
    set_mode = async_mock_service(hass, "climate", "set_hvac_mode")
    turn_on = async_mock_service(hass, "climate", "turn_on")
    async_mock_service(hass, "climate", "turn_off")
    action = [
        {
            "action": "climate.set_hvac_mode",
            "target": {"entity_id": "{{ entity_id }}"},
            "data": {"hvac_mode": "cool"},
        }
    ]
    await add_entry(hass, entity_id="climate.room", on_action=action)
    await call(hass, "on_in", entity_id="climate.room", minutes=1)
    await advance(hass, freezer, timedelta(minutes=1))
    assert len(set_mode) == 1
    assert set_mode[0].data == {"entity_id": ["climate.room"], "hvac_mode": "cool"}
    assert turn_on == []


async def test_failed_switch_on_leaves_no_timer(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Einschalt-Aktion scheitert: keine Ausschaltzeit, späteres Einschalten nutzt die Standarddauer."""
    entry = await add_entry(hass, on_action=[{"action": "script.does_not_exist"}])
    await call(hass, "on_at", at="13:00", duration=30)
    await advance(hass, freezer, timedelta(hours=1))
    assert hass.states.get(FAN).state == "off"
    assert off_time(hass, entry) is None
    await switch(hass, True)
    assert off_time(hass, entry) == local("2026-10-15 17:00")


async def test_plan_without_duration_keeps_fixed_off(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Plan ohne Dauer bei gesetztem „aus um“: Ausschaltzeit ist „aus um“, es bleibt stehen."""
    entry = await add_entry(hass, minutes=5)
    await switch(hass, True)
    await call(hass, "off_at", at="16:35")
    await call(hass, "on_at", at="13:12")
    await advance(hass, freezer, timedelta(hours=1, minutes=12))
    assert off_time(hass, entry) == local("2026-10-15 16:35")
    assert dt_state(hass, entry, "switch_off_at") == local("2026-10-15 16:35")
    await advance(hass, freezer, timedelta(minutes=10))
    assert hass.states.get(FAN).state == "on"


async def test_fixed_off_before_plan_does_not_count(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """„Aus um“ liegt vor der Planzeit: es läuft vorher ab, der Plan nimmt die Standarddauer."""
    entry = await add_entry(hass, minutes=5)
    await call(hass, "off_at", at="12:30")
    await call(hass, "on_at", at="13:00")
    await advance(hass, freezer, timedelta(hours=1))
    assert hass.states.get(FAN).state == "on"
    assert off_time(hass, entry) == local("2026-10-15 13:05")


async def test_waiting_plan_lasts_until_fixed_off(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Gerät weg, Plan ohne Dauer mit späterem „aus um“: Plan wartet bis „aus um“."""
    entry = await add_entry(hass)
    await call(hass, "on_at", at="13:00")
    await call(hass, "off_at", at="14:00")
    hass.states.async_set(FAN, "unavailable")
    await advance(hass, freezer, timedelta(minutes=70))
    assert dt_state(hass, entry, "switch_on_at") == local("2026-10-15 13:00")
    hass.states.async_set(FAN, "off")
    await hass.async_block_till_done()
    assert hass.states.get(FAN).state == "on"
    assert off_time(hass, entry) == local("2026-10-15 14:00")


async def test_waiting_plan_ends_with_fixed_off(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Gerät bleibt über „aus um“ hinaus weg: Plan verfällt dort, nicht erst nach der Standarddauer."""
    entry = await add_entry(hass)
    await call(hass, "on_at", at="13:00")
    await call(hass, "off_at", at="14:00")
    hass.states.async_set(FAN, "unavailable")
    await advance(hass, freezer, timedelta(hours=2, minutes=1))
    assert dt_state(hass, entry, "switch_on_at") is None
    hass.states.async_set(FAN, "off")
    await hass.async_block_till_done()
    assert hass.states.get(FAN).state == "off"


async def test_default_zero_plan_without_duration_stays_on(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Standarddauer 0: ein Plan ohne Dauer schaltet ein und lässt das Gerät an."""
    entry = await add_entry(hass, minutes=0)
    await call(hass, "on_at", at="13:00")
    await advance(hass, freezer, timedelta(hours=1))
    assert hass.states.get(FAN).state == "on"
    assert off_time(hass, entry) is None
    assert dt_state(hass, entry, "switch_on_at") is None
    await advance(hass, freezer, timedelta(hours=10))
    assert hass.states.get(FAN).state == "on"


async def test_default_zero_plan_with_duration_ends(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Standarddauer 0: ein Plan mit Dauer endet wie sonst."""
    entry = await add_entry(hass, minutes=0)
    await call(hass, "on_in", minutes=30, duration=45)
    await advance(hass, freezer, timedelta(minutes=30))
    assert off_time(hass, entry) == local("2026-10-15 13:15")
    await advance(hass, freezer, timedelta(minutes=46))
    assert hass.states.get(FAN).state == "off"


async def test_default_zero_open_plan_waits_for_unreachable(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Standarddauer 0, Plan ohne Ende, Gerät weg: Plan wartet, bis es zurück ist."""
    entry = await add_entry(hass, minutes=0)
    await call(hass, "on_at", at="13:00")
    hass.states.async_set(FAN, "unavailable")
    await advance(hass, freezer, timedelta(hours=5))
    assert dt_state(hass, entry, "switch_on_at") == local("2026-10-15 13:00")
    hass.states.async_set(FAN, "off")
    await hass.async_block_till_done()
    assert hass.states.get(FAN).state == "on"
    assert off_time(hass, entry) is None


async def test_default_zero_open_plan_keeps_running_off_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Standarddauer 0: ein offener Plan lässt „aus in 60 min“ stehen."""
    entry = await add_entry(hass, minutes=0)
    await switch(hass, True)
    await call(hass, "off_in", minutes=60)
    await call(hass, "on_in", minutes=10)
    await advance(hass, freezer, timedelta(minutes=10))
    assert off_time(hass, entry) == local("2026-10-15 13:00")
    await advance(hass, freezer, timedelta(minutes=51))
    assert hass.states.get(FAN).state == "off"


@pytest.mark.parametrize("back", ["on", "off"])
async def test_default_zero_open_plan_with_passed_off_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, back: str
) -> None:
    """Standarddauer 0: Ausschaltzeit lief ab, während das Gerät weg war; der offene Plan holt das Aus nach."""
    entry = await add_entry(hass, minutes=0)
    await switch(hass, True)
    await call(hass, "off_in", minutes=60)
    await call(hass, "on_in", minutes=10)
    await advance(hass, freezer, timedelta(minutes=5))
    hass.states.async_set(FAN, "unavailable")
    await advance(hass, freezer, timedelta(hours=2))
    hass.states.async_set(FAN, back)
    await hass.async_block_till_done()
    assert hass.states.get(FAN).state == "off"
    assert off_time(hass, entry) is None
    assert dt_state(hass, entry, "switch_on_at") is None
    await switch(hass, True)
    assert hass.states.get(FAN).state == "on"
