"""Shared fixtures and helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.run_timer.const import (
    CONF_DEFAULT_MINUTES,
    CONF_ON_ACTION,
    DOMAIN,
)

FAN = "input_boolean.fan"
# Thursday 12:00 local time (Europe/Berlin, CEST).
NOON = "2026-10-15T10:00:00+00:00"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom_components/run_timer."""


@pytest.fixture
async def base(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Berlin time zone, noon, homeassistant and input_boolean set up."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to(NOON)
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(
        hass, "input_boolean", {"input_boolean": {"fan": {"name": "Fan"}}}
    )
    await hass.async_block_till_done()


async def add_entry(
    hass: HomeAssistant,
    entity_id: str = FAN,
    minutes: int = 240,
    on_action: list[dict[str, Any]] | None = None,
    entry_id: str | None = None,
) -> MockConfigEntry:
    """Add and set up a run_timer entry."""
    options: dict[str, Any] = {CONF_DEFAULT_MINUTES: minutes}
    if on_action is not None:
        options[CONF_ON_ACTION] = on_action
    kwargs: dict[str, Any] = {"entry_id": entry_id} if entry_id else {}
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Fan",
        data={CONF_ENTITY_ID: entity_id},
        options=options,
        unique_id=entity_id,
        **kwargs,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def eid(hass: HomeAssistant, entry: MockConfigEntry, platform: str, key: str) -> str:
    """Return the entity id of one of the entry's entities."""
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{entry.entry_id}_{key}"
    )
    assert entity_id is not None
    return entity_id


def off_time(hass: HomeAssistant, entry: MockConfigEntry) -> datetime | None:
    """Return the off time shown by the sensor."""
    state = hass.states.get(eid(hass, entry, "sensor", "off_time"))
    assert state is not None
    return dt_util.parse_datetime(state.state)


def dt_state(hass: HomeAssistant, entry: MockConfigEntry, key: str) -> datetime | None:
    """Return the full time behind a time entity and check what the entity shows.

    The time entity only shows the local time of day; the date is checked
    against the controller.
    """
    state = hass.states.get(eid(hass, entry, "time", key))
    assert state is not None
    controller = entry.runtime_data
    value = controller.on_at if key == "switch_on_at" else controller.off_fixed
    if value is None:
        assert state.state == "unknown"
        return None
    shown = dt_util.as_local(value).replace(second=0, microsecond=0)
    assert state.state == shown.strftime("%H:%M:%S")
    return value


def local(text: str) -> datetime:
    """Parse a local Berlin time like '2026-10-15 18:00'."""
    return dt_util.as_utc(
        datetime.fromisoformat(text).replace(tzinfo=dt_util.get_default_time_zone())
    )


async def advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    """Move the clock forward and let timers fire."""
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def switch(hass: HomeAssistant, on: bool, entity_id: str = FAN) -> None:
    """Switch the input_boolean like a user would."""
    await hass.services.async_call(
        "input_boolean", "turn_on" if on else "turn_off", {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()


async def call(hass: HomeAssistant, service: str, **data: Any) -> None:
    """Call a run_timer service for the fan."""
    data.setdefault("entity_id", FAN)
    await hass.services.async_call(DOMAIN, service, data, blocking=True)
    await hass.async_block_till_done()
