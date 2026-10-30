"""Change add-auto-mode: mode on, time of day instead of a duration, start time of the timer."""

from __future__ import annotations

from datetime import time, timedelta
import json
from pathlib import Path
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util

from custom_components.run_timer.const import (
    CONF_AT_TIME,
    CONF_DEFAULT_MINUTES,
    CONF_HOLD_MINUTES,
    CONF_MODE,
)

from custom_components.run_timer.controller import resolve_at

from .conftest import FAN, add_entry, advance, call, dt_state, eid, local, off_time, switch
from .test_restore import ENTRY_ID, stored

pytestmark = pytest.mark.usefixtures("base")


def on_time(hass: HomeAssistant, entry) -> object:
    return dt_state(hass, entry, "switch_on_at")


def started(hass: HomeAssistant, entry) -> object:
    return hass.states.get(eid(hass, entry, "sensor", "off_time")).attributes["started_at"]


async def test_mode_on_back_after_default(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Wieder an nach der Standarddauer, danach kein Auto-Aus."""
    await switch(hass, True)
    entry = await add_entry(hass, minutes=60, mode="on")
    assert off_time(hass, entry) is None, "kein Aus-Timer im Modus on"
    await switch(hass, False)
    assert on_time(hass, entry) == local("2026-10-15 13:00")
    await advance(hass, freezer, timedelta(minutes=60))
    assert hass.states.get(FAN).state == "on"
    assert on_time(hass, entry) is None
    assert off_time(hass, entry) is None
    await advance(hass, freezer, timedelta(hours=3))
    assert hass.states.get(FAN).state == "on"


async def test_mode_on_at_time(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Wieder an zur Uhrzeit, auch mit Standarddauer 0."""
    await switch(hass, True)
    entry = await add_entry(hass, minutes=0, mode="on", at_time="04:00:00")
    await switch(hass, False)
    assert on_time(hass, entry) == local("2026-10-16 04:00")
    await advance(hass, freezer, timedelta(hours=16))
    assert hass.states.get(FAN).state == "on"


async def test_mode_on_nothing_to_plan(hass: HomeAssistant) -> None:
    await switch(hass, True)
    entry = await add_entry(hass, minutes=0, mode="on")
    await switch(hass, False)
    assert on_time(hass, entry) is None


async def test_mode_on_by_hand_drops_plan(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Von Hand früher eingeschaltet."""
    await switch(hass, True)
    entry = await add_entry(hass, minutes=60, mode="on")
    await switch(hass, False)
    await switch(hass, True)
    assert on_time(hass, entry) is None
    await switch(hass, False)
    assert on_time(hass, entry) == local("2026-10-15 13:00"), "nächstes Aus plant neu"


async def test_mode_on_manual_plan_stays(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Plan von Hand bleibt, mit eigener Dauer."""
    await switch(hass, True)
    entry = await add_entry(hass, minutes=60, mode="on")
    await call(hass, "on_in", minutes=10, duration=20)
    await switch(hass, False)
    assert on_time(hass, entry) == local("2026-10-15 12:10")
    await advance(hass, freezer, timedelta(minutes=10))
    assert hass.states.get(FAN).state == "on"
    assert off_time(hass, entry) == local("2026-10-15 12:30")
    await advance(hass, freezer, timedelta(minutes=20))
    assert hass.states.get(FAN).state == "off"
    assert on_time(hass, entry) == local("2026-10-15 13:30"), "das Aus des Laufs plant wieder"


async def test_mode_on_cancel_stays_cancelled(hass: HomeAssistant) -> None:
    """Verworfener Plan bleibt verworfen, auch über unavailable."""
    await switch(hass, True)
    entry = await add_entry(hass, minutes=60, mode="on")
    await switch(hass, False)
    await call(hass, "cancel", what="on")
    attrs = hass.states.get(FAN).attributes
    hass.states.async_set(FAN, "unavailable", attrs)
    await hass.async_block_till_done()
    hass.states.async_set(FAN, "off", attrs)
    await hass.async_block_till_done()
    assert on_time(hass, entry) is None


async def test_mode_on_switched_off_while_down(hass: HomeAssistant) -> None:
    """Beim Start aus und kein Plan: danach steht einer."""
    entry = await add_entry(hass, minutes=60, mode="on")
    assert on_time(hass, entry) == local("2026-10-15 13:00")


async def test_mode_on_ignores_hold(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Einschalten von Hand im Modus on startet keinen gehaltenen Lauf."""
    hass.states.async_set("binary_sensor.room", "on")
    entry = await add_entry(hass, minutes=60, mode="on", hold="{{ is_state('binary_sensor.room', 'on') }}", hold_minutes=15)
    await switch(hass, True)
    sensor = hass.states.get(eid(hass, entry, "sensor", "off_time"))
    assert sensor.attributes["held"] is False
    hass.states.async_set("binary_sensor.room", "off")
    await hass.async_block_till_done()
    assert off_time(hass, entry) is None
    await advance(hass, freezer, timedelta(minutes=30))
    assert hass.states.get(FAN).state == "on"


async def test_mode_on_fixed_off_still_works(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """„Aus um“ bleibt auch im Modus on: Einschalten übernimmt es als Ausschaltzeit."""
    entry = await add_entry(hass, minutes=60, mode="on")
    await call(hass, "cancel", what="on")
    await call(hass, "off_at", at="15:00:00")
    await switch(hass, True)
    assert off_time(hass, entry) == local("2026-10-15 15:00")


async def test_mode_on_plan_ends_at_fixed_off(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Ein Plan ohne eigene Dauer endet auch im Modus on an einem späteren „aus um“."""
    entry = await add_entry(hass, minutes=60, mode="on")
    await call(hass, "off_at", at="15:00:00")
    await advance(hass, freezer, timedelta(minutes=60))
    assert hass.states.get(FAN).state == "on"
    assert off_time(hass, entry) == local("2026-10-15 15:00")


async def test_mode_off_plan_survives_switching_on(hass: HomeAssistant) -> None:
    """Der Modus off leert einen Plan beim Einschalten nicht."""
    entry = await add_entry(hass)
    await call(hass, "on_in", minutes=30)
    await switch(hass, True)
    assert on_time(hass, entry) == local("2026-10-15 12:30")


async def test_mode_on_plan_survives_restart(hass: HomeAssistant) -> None:
    """Ein Neustart lässt den Plan eines laufenden Geräts stehen."""
    await switch(hass, True)
    entry = await add_entry(hass, minutes=60, mode="on")
    await call(hass, "on_in", minutes=30, duration=20)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert on_time(hass, entry) == local("2026-10-15 12:30")


async def test_mode_on_failed_switch_on_plans_again(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Scheitert das Einschalten, bleibt das Gerät nicht ohne Rückweg."""
    await switch(hass, True)
    entry = await add_entry(hass, minutes=60, mode="on", on_action=[{"action": "script.does_not_exist"}])
    await switch(hass, False)
    await advance(hass, freezer, timedelta(minutes=60))
    assert hass.states.get(FAN).state == "off"
    assert on_time(hass, entry) == local("2026-10-15 14:00")


async def test_at_time_instead_of_default(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Aus um 18:00."""
    entry = await add_entry(hass, minutes=30, at_time="18:00:00")
    await switch(hass, True)
    assert off_time(hass, entry) == local("2026-10-15 18:00")
    await advance(hass, freezer, timedelta(hours=6))
    assert hass.states.get(FAN).state == "off"


async def test_at_time_passed_means_tomorrow(hass: HomeAssistant) -> None:
    entry = await add_entry(hass, minutes=0, at_time="04:00:00")
    await switch(hass, True)
    assert off_time(hass, entry) == local("2026-10-16 04:00")


async def test_at_time_fixed_off_wins(hass: HomeAssistant) -> None:
    entry = await add_entry(hass, at_time="18:00:00")
    await call(hass, "off_at", at="15:00:00")
    await switch(hass, True)
    assert off_time(hass, entry) == local("2026-10-15 15:00")


async def test_at_time_plan_end(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Plan ohne Dauer endet an der nächsten Uhrzeit nach der Planzeit."""
    entry = await add_entry(hass, at_time="18:00:00")
    await call(hass, "on_in", minutes=60)
    await advance(hass, freezer, timedelta(minutes=60))
    assert hass.states.get(FAN).state == "on"
    assert off_time(hass, entry) == local("2026-10-15 18:00")


async def test_at_time_plan_end_next_day(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Das Planende zählt ab der Planzeit, nicht ab jetzt."""
    entry = await add_entry(hass, at_time="18:00:00")
    await call(hass, "on_at", at="19:00:00")
    await advance(hass, freezer, timedelta(hours=6))
    assert on_time(hass, entry) == local("2026-10-15 19:00"), "18:00 liegt vor der Planzeit, der Plan bleibt"
    await advance(hass, freezer, timedelta(hours=1))
    assert hass.states.get(FAN).state == "on"
    assert off_time(hass, entry) == local("2026-10-16 18:00")


def test_resolve_at_second_pass_of_dst_change() -> None:
    """Im zweiten Durchlauf der Rückstellung liegt die erste 02:30 hinter uns: nächster Tag."""
    now = dt_util.parse_datetime("2026-10-25T01:15:00+00:00")   # 02:15 MEZ, zweiter Durchlauf
    assert resolve_at(time(2, 30), now) > now


async def test_started_at(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Timer läuft und wird verlängert, Ausschalten leert die Startzeit."""
    entry = await add_entry(hass)
    assert started(hass, entry) is None
    await switch(hass, True)
    assert started(hass, entry) == local("2026-10-15 12:00")
    await advance(hass, freezer, timedelta(minutes=30))
    await call(hass, "extend", minutes=15)
    assert started(hass, entry) == local("2026-10-15 12:00")
    await switch(hass, False)
    assert started(hass, entry) is None


async def test_started_at_survives_restart(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    entry = await add_entry(hass)
    await switch(hass, True)
    await advance(hass, freezer, timedelta(minutes=5))
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert started(hass, entry) == local("2026-10-15 12:00")


async def test_started_at_cleared_when_off_while_down(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Ausgeschaltet, während Home Assistant aus war: der nächste Lauf erbt die alte Startzeit nicht."""
    entry = await add_entry(hass)
    await switch(hass, True)
    await hass.config_entries.async_unload(entry.entry_id)
    await switch(hass, False)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert started(hass, entry) is None
    await advance(hass, freezer, timedelta(minutes=5))
    await switch(hass, True)
    assert started(hass, entry) == local("2026-10-15 12:05")


async def options(hass: HomeAssistant, entry, **data) -> None:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DEFAULT_MINUTES: 60, CONF_HOLD_MINUTES: 15, **data}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


async def test_options_mode_and_time(hass: HomeAssistant) -> None:
    """Modus setzen, leere Uhrzeit löscht sie."""
    entry = await add_entry(hass)
    await options(hass, entry, **{CONF_MODE: "on", CONF_AT_TIME: "04:00:00"})
    assert entry.options[CONF_MODE] == "on"
    assert entry.options[CONF_AT_TIME] == "04:00:00"
    await options(hass, entry)
    assert entry.options[CONF_MODE] == "off"
    assert not entry.options[CONF_AT_TIME]


async def test_options_off_entity_to_mode_on_plans(hass: HomeAssistant) -> None:
    """Ausgeschaltetes Gerät wechselt auf on."""
    entry = await add_entry(hass)
    assert on_time(hass, entry) is None
    await options(hass, entry, **{CONF_MODE: "on"})
    assert on_time(hass, entry) == local("2026-10-15 13:00")


async def test_options_keep_cancelled_plan_cancelled(hass: HomeAssistant) -> None:
    """Nur der Wechsel auf on plant: eine andere Änderung holt einen verworfenen Plan nicht zurück."""
    entry = await add_entry(hass)
    await options(hass, entry, **{CONF_MODE: "on"})
    await call(hass, "cancel", what="on")
    await options(hass, entry, **{CONF_MODE: "on", CONF_DEFAULT_MINUTES: 90})
    assert on_time(hass, entry) is None


async def test_options_mode_back_and_forth_plans_again(hass: HomeAssistant) -> None:
    entry = await add_entry(hass, mode="on")
    await call(hass, "cancel", what="on")
    await options(hass, entry, **{CONF_MODE: "off"})
    await options(hass, entry, **{CONF_MODE: "on"})
    assert on_time(hass, entry) == local("2026-10-15 13:00")


async def test_options_running_entity_to_mode_on_plans_nothing(hass: HomeAssistant) -> None:
    await switch(hass, True)
    entry = await add_entry(hass)
    await options(hass, entry, **{CONF_MODE: "on"})
    assert on_time(hass, entry) is None


async def test_options_form_shows_stored_values(hass: HomeAssistant) -> None:
    """Speichern ohne Änderung darf Modus und Uhrzeit nicht verlieren."""
    entry = await add_entry(hass, mode="on", at_time="04:00:00")
    result = await hass.config_entries.options.async_init(entry.entry_id)
    shown = {str(k): (k.description or {}).get("suggested_value") for k in result["data_schema"].schema}
    assert shown[CONF_MODE] == "on"
    assert shown[CONF_AT_TIME] == "04:00:00"
    selector = next(v for k, v in result["data_schema"].schema.items() if str(k) == CONF_MODE)
    assert selector.config["translation_key"] == CONF_MODE


@pytest.mark.parametrize("lang", ["en", "de"])
def test_options_translated(lang: str) -> None:
    path = Path(__file__).parents[1] / f"custom_components/run_timer/translations/{lang}.json"
    text = json.loads(path.read_text(encoding="utf-8"))
    assert {CONF_MODE, CONF_AT_TIME} <= text["options"]["step"]["init"]["data"].keys()
    assert text["selector"][CONF_MODE]["options"].keys() == {"off", "on"}


async def test_mode_on_unavailable_at_start_then_off_plans(hass: HomeAssistant) -> None:
    hass.states.async_set(FAN, "unavailable")
    entry = await add_entry(hass, minutes=60, mode="on")
    hass.states.async_set(FAN, "off")
    await hass.async_block_till_done()
    assert on_time(hass, entry) == local("2026-10-15 13:00")


async def test_mode_on_off_via_unavailable_plans(hass: HomeAssistant) -> None:
    """Von an über unavailable auf aus ist ein echtes Ausschalten."""
    await switch(hass, True)
    entry = await add_entry(hass, minutes=60, mode="on")
    attrs = hass.states.get(FAN).attributes
    hass.states.async_set(FAN, "unavailable", attrs)
    await hass.async_block_till_done()
    hass.states.async_set(FAN, "off", attrs)
    await hass.async_block_till_done()
    assert on_time(hass, entry) == local("2026-10-15 13:00")


async def test_mode_on_unreachable_restart_keeps_plan(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Nach einem Neustart ist der letzte Zustand unbekannt: das erste „an“ ist kein Einschalten von Hand."""
    hass.states.async_set(FAN, "unavailable")
    stored(hass_storage, on_at=local("2026-10-15 12:30"))
    entry = await add_entry(hass, minutes=60, mode="on", entry_id=ENTRY_ID)
    hass.states.async_set(FAN, "on")
    await hass.async_block_till_done()
    assert on_time(hass, entry) == local("2026-10-15 12:30")


async def test_mode_on_plan_without_duration_stays(hass: HomeAssistant) -> None:
    await switch(hass, True)
    entry = await add_entry(hass, minutes=60, mode="on")
    await call(hass, "on_in", minutes=10)
    await switch(hass, False)
    assert on_time(hass, entry) == local("2026-10-15 12:10")


async def test_mode_on_running_entity_gets_no_plan(hass: HomeAssistant) -> None:
    await switch(hass, True)
    entry = await add_entry(hass, minutes=60, mode="on")
    assert on_time(hass, entry) is None


async def test_mode_on_by_hand_drops_plan_with_duration(hass: HomeAssistant) -> None:
    entry = await add_entry(hass, minutes=60, mode="on")
    await call(hass, "cancel", what="on")
    await call(hass, "on_in", minutes=10, duration=20)
    await switch(hass, True)
    assert on_time(hass, entry) is None


async def test_at_time_later_fixed_off_ends_plan(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    entry = await add_entry(hass, at_time="18:00:00")
    await call(hass, "off_at", at="20:00:00")
    await call(hass, "on_in", minutes=60)
    await advance(hass, freezer, timedelta(minutes=60))
    assert off_time(hass, entry) == local("2026-10-15 20:00")


async def test_at_time_own_duration_wins(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    entry = await add_entry(hass, at_time="18:00:00")
    await call(hass, "on_in", minutes=10, duration=20)
    await advance(hass, freezer, timedelta(minutes=10))
    assert off_time(hass, entry) == local("2026-10-15 12:30")
