"""Current off time and planned switch-on of a managed entity."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RunTimerConfigEntry
from .entity import RunTimerEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RunTimerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the off time and on time sensors."""
    controller = entry.runtime_data
    async_add_entities(
        [OffTimeSensor(controller, "off_time"), OnTimeSensor(controller, "on_time")]
    )


class OffTimeSensor(RunTimerEntity, SensorEntity):
    """When the managed entity will be switched off."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        """Return the off time."""
        return self.controller.off_at

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Show whether the hold condition keeps the entity on."""
        return {"held": self.controller.holding}


class OnTimeSensor(RunTimerEntity, SensorEntity):
    """When the managed entity will be switched on by the plan."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        """Return the planned switch-on."""
        return self.controller.on_at
