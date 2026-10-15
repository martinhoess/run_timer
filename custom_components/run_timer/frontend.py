"""More-info panel (experiment): serve the script, load it on every page, list managed entities."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import async_get_integration

from .const import DOMAIN

URL = "/run_timer_static/run-timer-panel.js"


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Register the panel script and the websocket command."""
    version = (await async_get_integration(hass, DOMAIN)).version
    await hass.http.async_register_static_paths(
        [StaticPathConfig(URL, str(Path(__file__).parent / "www" / "run-timer-panel.js"), False)]
    )
    add_extra_js_url(hass, f"{URL}?v={version}")
    websocket_api.async_register_command(hass, websocket_list)


@websocket_api.websocket_command({vol.Required("type"): "run_timer/list"})
@callback
def websocket_list(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return {managed entity: {translation_key: entity_id}}."""
    registry = er.async_get(hass)
    connection.send_result(
        msg["id"],
        {
            entry.data[CONF_ENTITY_ID]: {
                e.translation_key: e.entity_id
                for e in er.async_entries_for_config_entry(registry, entry.entry_id)
            }
            for entry in hass.config_entries.async_loaded_entries(DOMAIN)
        },
    )
