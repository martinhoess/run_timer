"""Spec off-timer: services extend, off_in, off_at, cancel."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .conftest import FAN, add_entry, advance, call, dt_state, local, off_time, switch

pytestmark = pytest.mark.usefixtures("base")


async def test_extend_four_times(hass: HomeAssistant) -> None:
    """Viermal +15: 12:00 + 240 + 60 = 17:00."""
    entry = await add_entry(hass)
    await switch(hass, True)
    for _ in range(4):
        await call(hass, "extend", minutes=15)
    assert off_time(hass, entry) == local("2026-10-15 17:00")


async def test_extend_negative_past_end_switches_off(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Minus über die Restzeit hinaus."""
    entry = await add_entry(hass, minutes=30)
    await switch(hass, True)
    await advance(hass, freezer, timedelta(minutes=20))
    await call(hass, "extend", minutes=-15)
    assert hass.states.get(FAN).state == "off"
    assert off_time(hass, entry) is None


async def test_extend_off_device_switches_on(hass: HomeAssistant) -> None:
    """Gerät ist aus: +15 schaltet für 15 min ein, ein Plan bleibt stehen."""
    entry = await add_entry(hass)
    await call(hass, "on_at", at="18:00")
    await call(hass, "off_at", at="23:00")
    await call(hass, "extend", minutes=15)
    assert hass.states.get(FAN).state == "on"
    assert off_time(hass, entry) == local("2026-10-15 12:15")
    assert dt_state(hass, entry, "switch_off_at") is None
    assert dt_state(hass, entry, "switch_on_at") == local("2026-10-15 18:00")


async def test_extend_negative_off_device_does_nothing(hass: HomeAssistant) -> None:
    """Gerät ist aus: −15 tut nichts."""
    entry = await add_entry(hass)
    await call(hass, "extend", minutes=-15)
    assert hass.states.get(FAN).state == "off"
    assert off_time(hass, entry) is None


async def test_extend_on_device_without_timer_counts_from_now(hass: HomeAssistant) -> None:
    """Gerät an, Timer weggenommen: +15 heißt aus in 15 min, −15 sofort aus."""
    entry = await add_entry(hass)
    await switch(hass, True)
    await call(hass, "cancel", what="off")
    await call(hass, "extend", minutes=15)
    assert off_time(hass, entry) == local("2026-10-15 12:15")
    await call(hass, "cancel", what="off")
    await call(hass, "extend", minutes=-15)
    assert hass.states.get(FAN).state == "off"


async def test_extend_unreachable_without_timer_fails(hass: HomeAssistant) -> None:
    """Gerät nicht erreichbar und kein Timer: verständliche Fehlermeldung."""
    await add_entry(hass)
    hass.states.async_set(FAN, "unavailable")
    with pytest.raises(ServiceValidationError):
        await call(hass, "extend", minutes=15)


async def test_extend_moves_fixed_off(hass: HomeAssistant) -> None:
    """Ein gesetztes „aus um“ wandert mit."""
    entry = await add_entry(hass)
    await switch(hass, True)
    await call(hass, "off_at", at="18:00")
    await call(hass, "extend", minutes=15)
    assert off_time(hass, entry) == local("2026-10-15 18:15")
    assert dt_state(hass, entry, "switch_off_at") == local("2026-10-15 18:15")


async def test_off_at_longer_than_default(hass: HomeAssistant) -> None:
    """Bis 18:00 bei längerer Laufzeit."""
    entry = await add_entry(hass)
    await switch(hass, True)
    await call(hass, "off_at", at="18:00")
    assert off_time(hass, entry) == local("2026-10-15 18:00")


async def test_off_at_passed_time_means_tomorrow(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Uhrzeit liegt zurück: 23:00 → 01:00 am Folgetag."""
    entry = await add_entry(hass)
    await advance(hass, freezer, timedelta(hours=11))
    await call(hass, "off_at", at="01:00")
    assert dt_state(hass, entry, "switch_off_at") == local("2026-10-16 01:00")


async def test_off_at_datetime_in_past_fails(hass: HomeAssistant) -> None:
    """Datum mit Uhrzeit in der Vergangenheit wird abgelehnt."""
    await add_entry(hass)
    with pytest.raises(ServiceValidationError):
        await call(hass, "off_at", at="2026-10-15T08:00:00")


async def test_off_in_clears_fixed(hass: HomeAssistant) -> None:
    """Aus in 30 Minuten."""
    entry = await add_entry(hass)
    await call(hass, "off_at", at="18:00")
    await switch(hass, True)
    await call(hass, "off_in", minutes=30)
    assert off_time(hass, entry) == local("2026-10-15 12:30")
    assert dt_state(hass, entry, "switch_off_at") is None


async def test_cancel_all(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Alles abbrechen."""
    entry = await add_entry(hass)
    await switch(hass, True)
    await call(hass, "off_at", at="18:00")
    await call(hass, "on_at", at="06:00")
    await call(hass, "cancel")
    assert off_time(hass, entry) is None
    assert dt_state(hass, entry, "switch_off_at") is None
    assert dt_state(hass, entry, "switch_on_at") is None
    await advance(hass, freezer, timedelta(hours=8))
    assert hass.states.get(FAN).state == "on"


async def test_cancel_on_only(hass: HomeAssistant) -> None:
    """cancel mit what=on lässt den Aus-Timer stehen."""
    entry = await add_entry(hass)
    await switch(hass, True)
    await call(hass, "on_at", at="06:00")
    await call(hass, "cancel", what="on")
    assert dt_state(hass, entry, "switch_on_at") is None
    assert off_time(hass, entry) == local("2026-10-15 16:00")


async def test_unmanaged_entity_fails(hass: HomeAssistant) -> None:
    """Dienst für eine nicht verwaltete Entität."""
    await add_entry(hass)
    with pytest.raises(ServiceValidationError):
        await call(hass, "off_in", entity_id="input_boolean.other", minutes=5)


async def test_off_in_while_off_sets_fixed(hass: HomeAssistant) -> None:
    """off_in bei ausgeschaltetem Gerät setzt „aus um“."""
    entry = await add_entry(hass)
    await call(hass, "off_in", minutes=30)
    assert off_time(hass, entry) is None
    assert dt_state(hass, entry, "switch_off_at") == local("2026-10-15 12:30")
    await switch(hass, True)
    assert off_time(hass, entry) == local("2026-10-15 12:30")


async def test_fixed_off_while_switching_on(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """„Aus um“ während das Einschalten noch läuft: gilt, sobald das Gerät an ist."""
    entry = await add_entry(hass, on_action=[{"event": "run_timer_test_noop"}])
    await call(hass, "extend", minutes=15)
    await call(hass, "off_at", at="12:05")
    hass.states.async_set(FAN, "on")
    await hass.async_block_till_done()
    assert off_time(hass, entry) == local("2026-10-15 12:05")
    await advance(hass, freezer, timedelta(minutes=6))
    assert hass.states.get(FAN).state == "off"


async def test_fixed_off_while_briefly_unavailable(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """„Aus um“ während das Gerät kurz weg ist: gilt nach der Rückkehr."""
    entry = await add_entry(hass)
    await switch(hass, True)
    hass.states.async_set(FAN, "unavailable")
    await hass.async_block_till_done()
    await call(hass, "off_at", at="12:30")
    hass.states.async_set(FAN, "on")
    await hass.async_block_till_done()
    assert off_time(hass, entry) == local("2026-10-15 12:30")
    await advance(hass, freezer, timedelta(minutes=31))
    assert hass.states.get(FAN).state == "off"


async def test_extend_off_device_failed_switch_on_raises(hass: HomeAssistant) -> None:
    """+15 am ausgeschalteten Gerät, Einschalten scheitert: Fehlermeldung statt stillem Erfolg."""
    entry = await add_entry(hass, on_action=[{"action": "script.does_not_exist"}])
    with pytest.raises(ServiceValidationError):
        await call(hass, "extend", minutes=15)
    assert off_time(hass, entry) is None
