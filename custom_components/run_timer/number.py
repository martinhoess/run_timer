"""Default run time of a managed entity."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RunTimerConfigEntry
from .const import DEFAULT_MINUTES_MAX, DEFAULT_MINUTES_MIN
from .entity import RunTimerEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RunTimerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the default run time."""
    async_add_entities([DefaultMinutesNumber(entry.runtime_data, "default_minutes")])


class DefaultMinutesNumber(RunTimerEntity, NumberEntity):
    """Default run time in minutes."""

    _attr_device_class = NumberDeviceClass.DURATION
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = DEFAULT_MINUTES_MIN
    _attr_native_max_value = DEFAULT_MINUTES_MAX
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    @property
    def native_value(self) -> int:
        """Return the default run time."""
        return self.controller.default_minutes

    async def async_set_native_value(self, value: float) -> None:
        """Store a new default run time."""
        await self.controller.async_set_default_minutes(int(value))
