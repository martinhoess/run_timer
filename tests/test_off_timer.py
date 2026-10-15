"""Spec off-timer: switching off after the run time."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.core import HomeAssistant, ServiceCall, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from custom_components.run_timer.controller import is_on

from .conftest import FAN, add_entry, advance, call, dt_state, local, off_time, switch

pytestmark = pytest.mark.usefixtures("base")


def test_climate_heat_counts_as_on() -> None:
    """Klimagerät im Modus heat."""
    assert is_on(State("climate.room", "heat"))
    assert not is_on(State("climate.room", "off"))
    assert not is_on(State("climate.room", "unavailable"))
    assert not is_on(State("climate.room", "unknown"))


async def test_switch_on_starts_default(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Einschalten am Gerät + Ausschaltzeit erreicht."""
    entry = await add_entry(hass)
    assert off_time(hass, entry) is None
    await switch(hass, True)
    assert off_time(hass, entry) == local("2026-10-15 16:00")
    await advance(hass, freezer, timedelta(hours=3, minutes=59))
    assert hass.states.get(FAN).state == "on"
    await advance(hass, freezer, timedelta(minutes=1))
    assert hass.states.get(FAN).state == "off"
    assert off_time(hass, entry) is None
    assert dt_state(hass, entry, "switch_off_at") is None


async def test_attribute_change_keeps_off_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Nur Attribut ändert sich."""
    entry = await add_entry(hass)
    await switch(hass, True)
    before = off_time(hass, entry)
    await advance(hass, freezer, timedelta(minutes=10))
    hass.states.async_set(FAN, "on", {"percentage": 75})
    await hass.async_block_till_done()
    assert off_time(hass, entry) == before


async def test_fixed_off_time_wins_on_switch_on(hass: HomeAssistant) -> None:
    """„aus um“ ist gesetzt: 18:00 statt 16:00."""
    entry = await add_entry(hass)
    await call(hass, "off_at", at="18:00")
    assert off_time(hass, entry) is None
    await switch(hass, True)
    assert off_time(hass, entry) == local("2026-10-15 18:00")


async def test_back_from_unavailable_keeps_timer(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Gerät kommt von unavailable zurück."""
    entry = await add_entry(hass)
    await switch(hass, True)
    before = off_time(hass, entry)
    await advance(hass, freezer, timedelta(minutes=30))
    hass.states.async_set(FAN, "unavailable")
    await hass.async_block_till_done()
    hass.states.async_set(FAN, "on")
    await hass.async_block_till_done()
    assert off_time(hass, entry) == before


async def test_manual_off_keeps_plan(hass: HomeAssistant) -> None:
    """Von Hand aus mit Plan."""
    entry = await add_entry(hass)
    await switch(hass, True)
    await call(hass, "on_at", at="06:00")
    await switch(hass, False)
    assert off_time(hass, entry) is None
    assert dt_state(hass, entry, "switch_on_at") == local("2026-10-16 06:00")


async def test_fixed_off_survives_off_and_on(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """„aus um“ übersteht Aus und An."""
    entry = await add_entry(hass)
    await call(hass, "off_at", at="18:00")
    await advance(hass, freezer, timedelta(hours=1))
    await switch(hass, True)
    await switch(hass, False)
    await advance(hass, freezer, timedelta(hours=1))
    await switch(hass, True)
    assert off_time(hass, entry) == local("2026-10-15 18:00")


async def test_fixed_off_expires_while_off(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """„aus um“ läuft ab, während das Gerät aus ist."""
    entry = await add_entry(hass)
    await call(hass, "off_at", at="18:00")
    await advance(hass, freezer, timedelta(hours=6))
    assert dt_state(hass, entry, "switch_off_at") is None
    assert hass.states.get(FAN).state == "off"


async def test_unreachable_at_off_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """WLAN weg zur Ausschaltzeit: Ausschalten, sobald es wieder an meldet."""
    entry = await add_entry(hass, minutes=60)
    await switch(hass, True)
    await advance(hass, freezer, timedelta(minutes=50))
    hass.states.async_set(FAN, "unavailable")
    await advance(hass, freezer, timedelta(minutes=30))
    assert off_time(hass, entry) == local("2026-10-15 13:00")
    hass.states.async_set(FAN, "on")
    await hass.async_block_till_done()
    assert hass.states.get(FAN).state == "off"
    assert off_time(hass, entry) is None


async def test_remove_entry_drops_timer(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Entfernen bei laufendem Timer."""
    entry = await add_entry(hass)
    await switch(hass, True)
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    await advance(hass, freezer, timedelta(hours=5))
    assert hass.states.get(FAN).state == "on"


async def test_power_loss_counts_as_switch_on(hass: HomeAssistant) -> None:
    """Aus → unavailable → an (Stromausfall, Steckdose schaltet ein): Standarddauer startet."""
    entry = await add_entry(hass)
    hass.states.async_set(FAN, "unavailable")
    await hass.async_block_till_done()
    hass.states.async_set(FAN, "on")
    await hass.async_block_till_done()
    assert off_time(hass, entry) == local("2026-10-15 16:00")


async def test_cancelled_timer_stays_cancelled_after_blip(hass: HomeAssistant) -> None:
    """Nach cancel startet ein kurzer Ausfall keinen neuen Timer."""
    entry = await add_entry(hass)
    await switch(hass, True)
    await call(hass, "cancel", what="off")
    hass.states.async_set(FAN, "unavailable")
    await hass.async_block_till_done()
    hass.states.async_set(FAN, "on")
    await hass.async_block_till_done()
    assert off_time(hass, entry) is None


async def test_failed_switch_off_is_retried(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Ausschalten scheitert: nach 5 min neuer Versuch."""
    attempts: list[str] = []

    async def turn_off(call: ServiceCall) -> None:
        attempts.append("x")
        if len(attempts) == 1:
            raise HomeAssistantError("cloud timeout")
        hass.states.async_set("switch.plug", "off")

    hass.states.async_set("switch.plug", "off")
    hass.services.async_register("switch", "turn_off", turn_off)
    hass.services.async_register("switch", "turn_on", lambda call: None)
    entry = await add_entry(hass, entity_id="switch.plug", minutes=10)
    hass.states.async_set("switch.plug", "on")
    await advance(hass, freezer, timedelta(minutes=10))
    assert attempts == ["x"]
    assert hass.states.get("switch.plug").state == "on"
    await advance(hass, freezer, timedelta(minutes=5))
    assert len(attempts) == 2
    assert hass.states.get("switch.plug").state == "off"
    assert off_time(hass, entry) is None


async def test_renamed_entity_is_followed(hass: HomeAssistant) -> None:
    """Umbenannte Ziel-Entität: Timer und Dienste folgen der neuen entity_id."""
    entry = await add_entry(hass)
    er.async_get(hass).async_update_entity(FAN, new_entity_id="input_boolean.fan2")
    await hass.async_block_till_done()
    assert entry.data["entity_id"] == "input_boolean.fan2"
    await switch(hass, True, entity_id="input_boolean.fan2")
    assert off_time(hass, entry) == local("2026-10-15 16:00")
    await call(hass, "extend", entity_id="input_boolean.fan2", minutes=15)
    assert off_time(hass, entry) == local("2026-10-15 16:15")
