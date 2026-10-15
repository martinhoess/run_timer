"""Restart, reload and unreachable entity at plan time."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.run_timer.const import DOMAIN

from .conftest import FAN, add_entry, advance, call, dt_state, eid, local, off_time, switch

pytestmark = pytest.mark.usefixtures("base")

ENTRY_ID = "restoretest"


def stored(hass_storage: dict[str, Any], **data: Any) -> None:
    """Put run_timer data into storage as if written before a restart."""
    full = {"off_at": None, "off_fixed": None, "on_at": None, "on_minutes": None}
    full.update({k: v.isoformat() if hasattr(v, "isoformat") else v for k, v in data.items()})
    key = f"{DOMAIN}.{ENTRY_ID}"
    hass_storage[key] = {"version": 1, "minor_version": 1, "key": key, "data": full}


async def test_restart_keeps_timer(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_storage: dict[str, Any]
) -> None:
    """Neustart mit laufendem Timer."""
    await switch(hass, True)
    stored(hass_storage, off_at=local("2026-10-15 14:00"))
    entry = await add_entry(hass, entry_id=ENTRY_ID)
    assert off_time(hass, entry) == local("2026-10-15 14:00")
    await advance(hass, freezer, timedelta(hours=2))
    assert hass.states.get(FAN).state == "off"


async def test_missed_off_time(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Ausschaltzeit während Neustart verpasst."""
    await switch(hass, True)
    stored(hass_storage, off_at=local("2026-10-15 11:50"))
    entry = await add_entry(hass, entry_id=ENTRY_ID)
    assert hass.states.get(FAN).state == "off"
    assert off_time(hass, entry) is None


async def test_on_without_timer_after_start(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Gerät an ohne Timer nach Start."""
    await switch(hass, True)
    stored(hass_storage)
    entry = await add_entry(hass, entry_id=ENTRY_ID)
    assert off_time(hass, entry) == local("2026-10-15 16:00")


async def test_missed_plan_with_time_left(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Nachholen mit Restdauer."""
    stored(hass_storage, on_at=local("2026-10-15 11:20"))
    entry = await add_entry(hass, entry_id=ENTRY_ID)
    assert hass.states.get(FAN).state == "on"
    assert off_time(hass, entry) == local("2026-10-15 15:20")
    assert dt_state(hass, entry, "switch_on_at") is None


async def test_missed_plan_too_late(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Zu spät."""
    stored(hass_storage, on_at=local("2026-10-15 11:00"), on_minutes=30)
    entry = await add_entry(hass, entry_id=ENTRY_ID)
    assert hass.states.get(FAN).state == "off"
    assert dt_state(hass, entry, "switch_on_at") is None


async def test_missed_fixed_off_dropped(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Abgelaufenes „aus um“ wird beim Start geleert."""
    stored(hass_storage, off_fixed=local("2026-10-15 11:00"))
    entry = await add_entry(hass, entry_id=ENTRY_ID)
    assert dt_state(hass, entry, "switch_off_at") is None


async def test_reload_keeps_timer(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Reload eines Eintrags behält laufende Timer."""
    entry = await add_entry(hass)
    await switch(hass, True)
    await call(hass, "on_at", at="20:00")
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert off_time(hass, entry) == local("2026-10-15 16:00")
    assert dt_state(hass, entry, "switch_on_at") == local("2026-10-15 20:00")
    await advance(hass, freezer, timedelta(hours=4))
    assert hass.states.get(FAN).state == "off"


async def test_plan_waits_for_unreachable_entity(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Gerät zur Planzeit nicht erreichbar: nachholen, sobald es zurück ist."""
    entry = await add_entry(hass)
    await call(hass, "on_at", at="13:00")
    hass.states.async_set(FAN, "unavailable")
    await advance(hass, freezer, timedelta(hours=1, minutes=10))
    assert dt_state(hass, entry, "switch_on_at") == local("2026-10-15 13:00")
    hass.states.async_set(FAN, "off")
    await hass.async_block_till_done()
    assert hass.states.get(FAN).state == "on"
    assert off_time(hass, entry) == local("2026-10-15 17:00")
    assert dt_util.utcnow() == local("2026-10-15 13:10")


async def test_real_start_path(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_storage: dict[str, Any]
) -> None:
    """Eintrag lädt vor dem Start; Nachholen erst nach EVENT_HOMEASSISTANT_STARTED."""
    await switch(hass, True)
    stored(hass_storage, off_at=local("2026-10-15 11:50"))
    hass.set_state(CoreState.not_running)
    entry = await add_entry(hass, entry_id=ENTRY_ID)
    assert hass.states.get(FAN).state == "on"
    assert off_time(hass, entry) == local("2026-10-15 11:50")
    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    assert hass.states.get(FAN).state == "off"


async def test_unreachable_at_start_then_on(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Gerät beim Start noch unavailable, meldet danach an: Standarddauer startet."""
    hass.states.async_set(FAN, "unavailable")
    stored(hass_storage)
    entry = await add_entry(hass, entry_id=ENTRY_ID)
    hass.states.async_set(FAN, "on")
    await hass.async_block_till_done()
    assert off_time(hass, entry) == local("2026-10-15 16:00")


async def test_unreachable_at_start_keeps_restored_timer(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Gespeicherter Timer bleibt, wenn das Gerät nach dem Start erst später an meldet."""
    hass.states.async_set(FAN, "unavailable")
    stored(hass_storage, off_at=local("2026-10-15 14:00"))
    entry = await add_entry(hass, entry_id=ENTRY_ID)
    hass.states.async_set(FAN, "on")
    await hass.async_block_till_done()
    assert off_time(hass, entry) == local("2026-10-15 14:00")


async def test_stale_timer_of_switched_off_entity(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_storage: dict[str, Any]
) -> None:
    """Gerät ging während des Neustarts aus: alter Timer verfällt, Einschalten startet neu."""
    stored(hass_storage, off_at=local("2026-10-15 14:00"))
    entry = await add_entry(hass, entry_id=ENTRY_ID)
    assert off_time(hass, entry) is None
    await advance(hass, freezer, timedelta(minutes=30))
    await switch(hass, True)
    assert off_time(hass, entry) == local("2026-10-15 16:30")


async def test_unreachable_plan_expires_at_end(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Gerät bleibt über Planzeit + Dauer hinaus weg: Plan verfällt ohne Schalten."""
    entry = await add_entry(hass)
    await call(hass, "on_in", minutes=1, duration=30)
    hass.states.async_set(FAN, "unavailable")
    await advance(hass, freezer, timedelta(minutes=2))
    assert dt_state(hass, entry, "switch_on_at") == local("2026-10-15 12:01")
    await advance(hass, freezer, timedelta(minutes=30))
    assert dt_state(hass, entry, "switch_on_at") is None
    assert hass.states.get(eid(hass, entry, "sensor", "on_time")).state == "unknown"
    hass.states.async_set(FAN, "off")
    await hass.async_block_till_done()
    assert hass.states.get(FAN).state == "off"


async def test_expired_plan_dropped_at_start_while_unreachable(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Plan + Dauer schon vorbei, Gerät beim Start nicht erreichbar: Plan ist weg."""
    hass.states.async_set(FAN, "unavailable")
    stored(hass_storage, on_at=local("2026-10-15 09:00"), on_minutes=30)
    entry = await add_entry(hass, entry_id=ENTRY_ID)
    assert dt_state(hass, entry, "switch_on_at") is None


async def test_due_plan_at_start_waits_until_end(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_storage: dict[str, Any]
) -> None:
    """Beim Start fällig, Gerät weg, Planende noch offen: Plan wartet bis zum Ende."""
    hass.states.async_set(FAN, "unavailable")
    stored(hass_storage, on_at=local("2026-10-15 11:50"), on_minutes=30)
    entry = await add_entry(hass, entry_id=ENTRY_ID)
    assert dt_state(hass, entry, "switch_on_at") == local("2026-10-15 11:50")
    await advance(hass, freezer, timedelta(minutes=21))
    assert dt_state(hass, entry, "switch_on_at") is None


async def test_default_change_moves_plan_end(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Plan ohne Dauer: geänderte Standarddauer verschiebt das Planende mit."""
    entry = await add_entry(hass, minutes=30)
    await call(hass, "on_in", minutes=1)
    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": eid(hass, entry, "number", "default_minutes"), "value": 120},
        blocking=True,
    )
    await hass.async_block_till_done()
    hass.states.async_set(FAN, "unavailable")
    await advance(hass, freezer, timedelta(minutes=40))
    assert dt_state(hass, entry, "switch_on_at") == local("2026-10-15 12:01")
    hass.states.async_set(FAN, "off")
    await hass.async_block_till_done()
    assert hass.states.get(FAN).state == "on"
    assert off_time(hass, entry) == local("2026-10-15 14:01")


async def test_plan_ended_by_passed_fixed_off_at_start(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Neustart: Plan ohne Dauer, sein Ende „aus um“ ist schon vorbei: nicht einschalten."""
    await switch(hass, False)
    stored(hass_storage, on_at=local("2026-10-15 09:00"), off_fixed=local("2026-10-15 11:00"))
    entry = await add_entry(hass, entry_id=ENTRY_ID)
    assert hass.states.get(FAN).state == "off"
    assert dt_state(hass, entry, "switch_on_at") is None
    assert off_time(hass, entry) is None
