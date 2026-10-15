"""Base entity for run_timer."""

from __future__ import annotations

from homeassistant.helpers.device import async_entity_id_to_device
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .controller import RunTimerController


class RunTimerEntity(Entity):
    """Entity that shows a value of the controller."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, controller: RunTimerController, key: str) -> None:
        """Attach to the device of the managed entity, or to an own device."""
        self.controller = controller
        entry = controller.entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        device = async_entity_id_to_device(controller.hass, controller.target)
        if device is not None:
            self.device_entry = device
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, entry.entry_id)}, name=entry.title
            )

    async def async_added_to_hass(self) -> None:
        """Follow the controller."""
        self.async_on_remove(self.controller.async_add_listener(self.async_write_ha_state))
