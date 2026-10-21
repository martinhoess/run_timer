"""Spec off-timer: hold while a template is true."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from custom_components.run_timer.const import DOMAIN

from .conftest import FAN, add_entry, advance, call, eid, local, off_time, switch

pytestmark = pytest.mark.usefixtures("base")

ROOM = "binary_sensor.room"
IN_ROOM = "{{ is_state('binary_sensor.room', 'on') }}"
ENTRY_ID = "holdtest"


async def room(hass: HomeAssistant, on: bool) -> None:
    """Set the condition entity."""
    hass.states.async_set(ROOM, "on" if on else "off")
    await hass.async_block_till_done()


def held(hass: HomeAssistant, entry: Any) -> bool:
    """Return the held attribute of the off time sensor."""
    state = hass.states.get(eid(hass, entry, "sensor", "off_time"))
    assert state is not None
    return state.attributes["held"]


async def test_hold_until_condition_false(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Raum verlassen: halten, dann Nachlauf, dann aus."""
    await room(hass, True)
    entry = await add_entry(hass, hold=IN_ROOM)
    await switch(hass, True)
    assert off_time(hass, entry) is None
    assert held(hass, entry)
    await advance(hass, freezer, timedelta(hours=5))
    assert hass.states.get(FAN).state == "on"
    await room(hass, False)
    assert off_time(hass, entry) == local("2026-10-15 17:15")
    assert not held(hass, entry)
    await advance(hass, freezer, timedelta(minutes=15))
    assert hass.states.get(FAN).state == "off"


async def test_back_within_grace(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Kurz raus und zurück: Nachlauf fällt weg, beim nächsten Verlassen neu."""
    await room(hass, True)
    entry = await add_entry(hass, hold=IN_ROOM, hold_minutes=10)
    await switch(hass, True)
    await room(hass, False)
    await advance(hass, freezer, timedelta(minutes=8))
    await room(hass, True)
    assert off_time(hass, entry) is None
    await advance(hass, freezer, timedelta(minutes=30))
    assert hass.states.get(FAN).state == "on"
    await room(hass, False)
    assert off_time(hass, entry) == local("2026-10-15 12:48")


async def test_negated_condition(hass: HomeAssistant) -> None:
    """Umgekehrte Bedingung: an, solange niemand zuhause ist."""
    hass.states.async_set("input_boolean.home", "off")
    entry = await add_entry(hass, hold="{{ not is_state('input_boolean.home', 'on') }}")
    await switch(hass, True)
    assert off_time(hass, entry) is None
    hass.states.async_set("input_boolean.home", "on")
    await hass.async_block_till_done()
    assert off_time(hass, entry) == local("2026-10-15 12:15")


async def test_false_at_switch_on_uses_default(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Bedingung beim Einschalten falsch: Standarddauer, dann halten, dann Nachlauf."""
    await room(hass, False)
    entry = await add_entry(hass, hold=IN_ROOM)
    await switch(hass, True)
    assert off_time(hass, entry) == local("2026-10-15 16:00")
    await room(hass, True)
    assert off_time(hass, entry) is None
    await advance(hass, freezer, timedelta(hours=6))
    await room(hass, False)
    assert off_time(hass, entry) == local("2026-10-15 18:15")


async def test_manual_off_in_wins(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Eingriff von Hand: „aus in 30“ gilt, obwohl die Bedingung hält."""
    await room(hass, True)
    entry = await add_entry(hass, hold=IN_ROOM)
    await switch(hass, True)
    await call(hass, "off_in", minutes=30)
    assert not held(hass, entry)
    await room(hass, False)
    await room(hass, True)
    assert off_time(hass, entry) == local("2026-10-15 12:30")
    await advance(hass, freezer, timedelta(minutes=30))
    assert hass.states.get(FAN).state == "off"
    # Next switch-on follows the condition again.
    await switch(hass, True)
    assert held(hass, entry)


async def test_cancel_ends_hold(hass: HomeAssistant) -> None:
    """Eingriff von Hand: nach cancel bleibt das Gerät an, auch wenn die Bedingung fällt."""
    await room(hass, True)
    entry = await add_entry(hass, hold=IN_ROOM)
    await switch(hass, True)
    await call(hass, "cancel", what="off")
    await room(hass, False)
    assert off_time(hass, entry) is None
    assert hass.states.get(FAN).state == "on"


async def test_fixed_off_at_switch_on_is_not_held(hass: HomeAssistant) -> None:
    """„aus um“ beim Einschalten hat Vorrang vor der Bedingung."""
    await room(hass, True)
    entry = await add_entry(hass, hold=IN_ROOM)
    await call(hass, "off_at", at="18:00")
    await switch(hass, True)
    assert off_time(hass, entry) == local("2026-10-15 18:00")
    await room(hass, False)
    assert off_time(hass, entry) == local("2026-10-15 18:00")


async def test_plan_on_held_device_wins(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Ein Plan auf einem gehaltenen Gerät hat Vorrang: sein Ende gilt."""
    await room(hass, True)
    entry = await add_entry(hass, hold=IN_ROOM)
    await switch(hass, True)
    await call(hass, "on_in", minutes=1, duration=30)
    await advance(hass, freezer, timedelta(minutes=1))
    assert off_time(hass, entry) == local("2026-10-15 12:31")
    assert not held(hass, entry)
    await room(hass, False)
    await room(hass, True)
    assert off_time(hass, entry) == local("2026-10-15 12:31")


async def test_open_plan_is_not_held(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Offener Plan (Standarddauer 0, ohne Dauer): die Bedingung greift nicht."""
    await room(hass, True)
    entry = await add_entry(hass, minutes=0, hold=IN_ROOM)
    await call(hass, "on_in", minutes=1)
    await advance(hass, freezer, timedelta(minutes=1))
    assert hass.states.get(FAN).state == "on"
    assert not held(hass, entry)
    await room(hass, False)
    assert off_time(hass, entry) is None


async def test_extend_ends_hold(hass: HomeAssistant) -> None:
    """Eingriff von Hand: extend zählt ab jetzt, die Bedingung greift nicht mehr."""
    await room(hass, True)
    entry = await add_entry(hass, hold=IN_ROOM)
    await switch(hass, True)
    await call(hass, "extend", minutes=15)
    assert off_time(hass, entry) == local("2026-10-15 12:15")
    await room(hass, False)
    await room(hass, True)
    assert off_time(hass, entry) == local("2026-10-15 12:15")


async def test_failed_extend_keeps_hold(hass: HomeAssistant) -> None:
    """Ein abgelehntes extend (Gerät nicht erreichbar) beendet das Halten nicht."""
    await room(hass, True)
    entry = await add_entry(hass, hold=IN_ROOM)
    await switch(hass, True)
    hass.states.async_set(FAN, "unavailable")
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError):
        await call(hass, "extend", minutes=15)
    hass.states.async_set(FAN, "on")
    await hass.async_block_till_done()
    await room(hass, False)
    assert off_time(hass, entry) == local("2026-10-15 12:15")


async def test_change_while_unavailable(hass: HomeAssistant) -> None:
    """Bedingung wechselt, während das Gerät nicht erreichbar ist: bei Rückkehr nachgeholt."""
    await room(hass, True)
    entry = await add_entry(hass, hold=IN_ROOM)
    await switch(hass, True)
    hass.states.async_set(FAN, "unavailable")
    await hass.async_block_till_done()
    await room(hass, False)
    assert off_time(hass, entry) is None
    hass.states.async_set(FAN, "on")
    await hass.async_block_till_done()
    assert off_time(hass, entry) == local("2026-10-15 12:15")
    assert not held(hass, entry)


async def test_default_zero_never_held_gets_no_grace(hass: HomeAssistant) -> None:
    """Standarddauer 0, Bedingung nie wahr: eine Options-Änderung startet keinen Nachlauf."""
    await room(hass, False)
    entry = await add_entry(hass, minutes=0, hold=IN_ROOM)
    await switch(hass, True)
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": eid(hass, entry, "number", "default_minutes"), "value": 10},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert off_time(hass, entry) is None
    assert hass.states.get(FAN).state == "on"


async def test_render_error_counts_false(hass: HomeAssistant) -> None:
    """Nachlauf 0 und Rendering-Fehler: sofort aus."""
    await room(hass, True)
    template = "{{ 1 / (1 if is_state('binary_sensor.room', 'on') else 0) }}"
    await add_entry(hass, hold=template, hold_minutes=0)
    await switch(hass, True)
    assert hass.states.get(FAN).state == "on"
    await room(hass, False)
    assert hass.states.get(FAN).state == "off"


async def test_options_change_starts_tracking(hass: HomeAssistant) -> None:
    """Haltebedingung später setzen: gilt ohne Neustart."""
    await room(hass, True)
    entry = await add_entry(hass)
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "hold_template": IN_ROOM, "hold_minutes": 5}
    )
    await hass.async_block_till_done()
    await switch(hass, True)
    assert off_time(hass, entry) is None
    await room(hass, False)
    assert off_time(hass, entry) == local("2026-10-15 12:05")


def stored(hass_storage: dict[str, Any], **data: Any) -> None:
    """Put run_timer data into storage as if written before a restart."""
    full = {
        "off_at": None,
        "off_fixed": None,
        "on_at": None,
        "on_minutes": None,
        "hold_run": True,
    }
    full.update({k: v.isoformat() if hasattr(v, "isoformat") else v for k, v in data.items()})
    key = f"{DOMAIN}.{ENTRY_ID}"
    hass_storage[key] = {"version": 1, "minor_version": 1, "key": key, "data": full}


async def test_restart_keeps_hold(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Neustart, Bedingung wahr: hält weiter ohne Ausschaltzeit."""
    await room(hass, True)
    await switch(hass, True)
    stored(hass_storage, hold_applied=True)
    entry = await add_entry(hass, entry_id=ENTRY_ID, hold=IN_ROOM)
    assert off_time(hass, entry) is None
    assert held(hass, entry)


async def test_restart_condition_false_starts_grace(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Neustart, Bedingung falsch: Nachlauf ab Start, nicht Standarddauer."""
    await room(hass, False)
    await switch(hass, True)
    stored(hass_storage, hold_applied=True)
    entry = await add_entry(hass, entry_id=ENTRY_ID, hold=IN_ROOM)
    assert off_time(hass, entry) == local("2026-10-15 12:15")


async def test_restart_never_held_gets_no_grace(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Neustart, Standarddauer 0, Bedingung nie wahr: kein Nachlauf."""
    await room(hass, False)
    await switch(hass, True)
    stored(hass_storage, hold_applied=False)
    entry = await add_entry(hass, entry_id=ENTRY_ID, minutes=0, hold=IN_ROOM)
    assert off_time(hass, entry) is None
    assert hass.states.get(FAN).state == "on"


async def test_restart_device_off_not_held(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Neustart, Gerät inzwischen aus: nicht mehr gehalten."""
    await room(hass, True)
    stored(hass_storage, hold_applied=True)
    entry = await add_entry(hass, entry_id=ENTRY_ID, hold=IN_ROOM)
    assert not held(hass, entry)


async def test_restart_drops_grace_when_true(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Neustart, Bedingung wieder wahr: gespeicherter Nachlauf fällt weg."""
    await room(hass, True)
    await switch(hass, True)
    # Grace time ran out during the restart, but the condition is true again.
    stored(hass_storage, hold_applied=False, off_at=local("2026-10-15 11:58"))
    entry = await add_entry(hass, entry_id=ENTRY_ID, hold=IN_ROOM)
    assert hass.states.get(FAN).state == "on"
    assert off_time(hass, entry) is None
    assert held(hass, entry)


async def test_reload_keeps_hold_state(hass: HomeAssistant) -> None:
    """Neustart echt gespeichert: Bedingung fällt während des Neuladens, Nachlauf ab Start."""
    await room(hass, True)
    entry = await add_entry(hass, hold=IN_ROOM)
    await switch(hass, True)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await room(hass, False)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert off_time(hass, entry) == local("2026-10-15 12:15")


async def test_unloaded_controller_ignores_hold(hass: HomeAssistant) -> None:
    """Ein nach dem Entladen fälliges Nachziehen setzt keinen Timer mehr."""
    await room(hass, True)
    entry = await add_entry(hass, hold=IN_ROOM)
    await switch(hass, True)
    controller = entry.runtime_data
    assert await hass.config_entries.async_unload(entry.entry_id)
    await controller._async_follow_hold()
    assert controller.off_at is None
    assert not controller._timers


async def test_switch_off_clears_held(hass: HomeAssistant) -> None:
    """Gehaltenes Gerät von Hand aus: held ist falsch."""
    await room(hass, True)
    entry = await add_entry(hass, hold=IN_ROOM)
    await switch(hass, True)
    assert held(hass, entry)
    await switch(hass, False)
    assert not held(hass, entry)


async def test_restart_unreachable_then_on_follows_hold(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Neustart, Gerät erst nicht erreichbar, Bedingung inzwischen falsch: Nachlauf statt Standarddauer."""
    await room(hass, False)
    hass.states.async_set(FAN, "unavailable")
    stored(hass_storage, hold_applied=True)
    entry = await add_entry(hass, entry_id=ENTRY_ID, minutes=0, hold=IN_ROOM)
    hass.states.async_set(FAN, "on")
    await hass.async_block_till_done()
    assert off_time(hass, entry) == local("2026-10-15 12:15")


async def test_options_change_while_held_applies_now(hass: HomeAssistant) -> None:
    """Bedingung ändern, während sie hält: der Lauf folgt sofort der neuen."""
    await room(hass, True)
    entry = await add_entry(hass, hold=IN_ROOM)
    await switch(hass, True)
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "hold_template": "{{ is_state('binary_sensor.room', 'off') }}"}
    )
    await hass.async_block_till_done()
    assert off_time(hass, entry) == local("2026-10-15 12:15")


@pytest.mark.parametrize("stored_off", ["2026-10-15 11:58", "2026-10-15 12:10"])
async def test_restart_unreachable_grace_dropped_when_true(
    hass: HomeAssistant, hass_storage: dict[str, Any], stored_off: str
) -> None:
    """Neustart im Nachlauf, Gerät erst nicht erreichbar, Bedingung wieder wahr: Nachlauf fällt weg."""
    await room(hass, True)
    hass.states.async_set(FAN, "unavailable")
    stored(hass_storage, hold_applied=False, off_at=local(stored_off))
    entry = await add_entry(hass, entry_id=ENTRY_ID, hold=IN_ROOM)
    hass.states.async_set(FAN, "on")
    await hass.async_block_till_done()
    assert hass.states.get(FAN).state == "on"
    assert off_time(hass, entry) is None
    assert held(hass, entry)


@pytest.mark.parametrize(
    ("stored_off", "state", "shown"),
    [("2026-10-15 11:58", "off", None), ("2026-10-15 12:10", "on", "2026-10-15 12:10")],
)
async def test_restart_unreachable_grace_still_false(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    stored_off: str,
    state: str,
    shown: str | None,
) -> None:
    """Neustart im Nachlauf, Gerät erst nicht erreichbar, Bedingung weiter falsch: abgelaufener schaltet aus, künftiger bleibt."""
    await room(hass, False)
    hass.states.async_set(FAN, "unavailable")
    stored(hass_storage, hold_applied=False, off_at=local(stored_off))
    entry = await add_entry(hass, entry_id=ENTRY_ID, hold=IN_ROOM)
    hass.states.async_set(FAN, "on")
    await hass.async_block_till_done()
    assert hass.states.get(FAN).state == state
    assert off_time(hass, entry) == (local(shown) if shown else None)
