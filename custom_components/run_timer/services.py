"""Services of run_timer."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_AT,
    ATTR_DURATION,
    ATTR_MINUTES,
    ATTR_WHAT,
    DEFAULT_MINUTES_MAX,
    DOMAIN,
    SERVICE_CANCEL,
    SERVICE_EXTEND,
    SERVICE_OFF_AT,
    SERVICE_OFF_IN,
    SERVICE_ON_AT,
    SERVICE_ON_IN,
)
from .controller import RunTimerController

_ENTITY = {vol.Required(ATTR_ENTITY_ID): cv.entity_id}
_POSITIVE = vol.All(vol.Coerce(int), vol.Range(min=1))
_AT = vol.Any(cv.datetime, cv.time)
_DURATION = vol.All(vol.Coerce(int), vol.Range(min=1, max=DEFAULT_MINUTES_MAX))

SCHEMAS = {
    SERVICE_EXTEND: vol.Schema(
        {**_ENTITY, vol.Required(ATTR_MINUTES): vol.All(vol.Coerce(int), vol.NotIn([0]))}
    ),
    SERVICE_OFF_IN: vol.Schema({**_ENTITY, vol.Required(ATTR_MINUTES): _POSITIVE}),
    SERVICE_OFF_AT: vol.Schema({**_ENTITY, vol.Required(ATTR_AT): _AT}),
    SERVICE_ON_IN: vol.Schema(
        {
            **_ENTITY,
            vol.Required(ATTR_MINUTES): _POSITIVE,
            vol.Optional(ATTR_DURATION): _DURATION,
        }
    ),
    SERVICE_ON_AT: vol.Schema(
        {**_ENTITY, vol.Required(ATTR_AT): _AT, vol.Optional(ATTR_DURATION): _DURATION}
    ),
    SERVICE_CANCEL: vol.Schema(
        {**_ENTITY, vol.Optional(ATTR_WHAT, default="all"): vol.In(["off", "on", "all"])}
    ),
}


def _controller(hass: HomeAssistant, entity_id: str) -> RunTimerController:
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        if entry.runtime_data.target == entity_id:
            return entry.runtime_data
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="not_managed",
        translation_placeholders={"entity_id": entity_id},
    )


async def _async_handle(call: ServiceCall) -> None:
    controller = _controller(call.hass, call.data[ATTR_ENTITY_ID])
    data = call.data
    match call.service:
        case "extend":
            await controller.async_extend(data[ATTR_MINUTES])
        case "off_in":
            await controller.async_off_in(data[ATTR_MINUTES])
        case "off_at":
            await controller.async_off_at(data[ATTR_AT])
        case "on_in":
            await controller.async_on_in(data[ATTR_MINUTES], data.get(ATTR_DURATION))
        case "on_at":
            await controller.async_on_at(data[ATTR_AT], data.get(ATTR_DURATION))
        case "cancel":
            await controller.async_cancel(data[ATTR_WHAT])


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register all services."""
    for name, schema in SCHEMAS.items():
        hass.services.async_register(DOMAIN, name, _async_handle, schema=schema)
