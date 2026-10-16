"""Spec device-setup: config and options flow."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import async_mock_service

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.run_timer.const import CONF_DEFAULT_MINUTES, CONF_ON_ACTION, DOMAIN

from .conftest import FAN, add_entry, advance, call

pytestmark = pytest.mark.usefixtures("base")


async def test_add_device(hass: HomeAssistant) -> None:
    """Gerät hinzufügen."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"entity_id": FAN, CONF_DEFAULT_MINUTES: 240}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Fan"
    assert result["data"] == {"entity_id": FAN}
    assert result["options"] == {CONF_DEFAULT_MINUTES: 240}
    await hass.async_block_till_done()
    assert hass.states.get("sensor.fan_next_stop") is not None


async def test_duplicate_entity(hass: HomeAssistant) -> None:
    """Doppelte Ziel-Entität."""
    await add_entry(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"entity_id": FAN, CONF_DEFAULT_MINUTES: 60}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_domain_without_on_off(hass: HomeAssistant) -> None:
    """Domain ohne an/aus."""
    hass.states.async_set("sensor.temperature", "21")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"entity_id": "sensor.temperature", CONF_DEFAULT_MINUTES: 60}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"entity_id": "no_on_off"}


async def test_options_change_action_without_restart(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Einschalt-Aktion später ändern: gilt ab dem nächsten Einschalten."""
    marker = async_mock_service(hass, "script", "marker")
    entry = await add_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    action = [{"action": "script.marker", "data": {"who": "{{ entity_id }}"}}]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DEFAULT_MINUTES: 120, CONF_ON_ACTION: action}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.states.get("number.fan_default_run_time").state == "120"
    await call(hass, "on_in", minutes=1)
    await advance(hass, freezer, timedelta(minutes=1))
    assert [c.data for c in marker] == [{"who": FAN}]


async def test_options_invalid_action(hass: HomeAssistant) -> None:
    """Ungültige Aktion wird abgelehnt."""
    entry = await add_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DEFAULT_MINUTES: 60, CONF_ON_ACTION: [{"nonsense": 1}]}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ON_ACTION: "invalid_action"}


async def test_add_device_with_default_zero(hass: HomeAssistant) -> None:
    """Standarddauer 0 ist beim Einrichten erlaubt."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"entity_id": FAN, CONF_DEFAULT_MINUTES: 0}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {CONF_DEFAULT_MINUTES: 0}
