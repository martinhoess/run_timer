"""Planned switch-on and fixed switch-off of a managed entity, as time of day."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import RunTimerConfigEntry
from .entity import RunTimerEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RunTimerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add switch-on and switch-off times."""
    controller = entry.runtime_data
    async_add_entities(
        [SwitchOnAt(controller, "switch_on_at"), SwitchOffAt(controller, "switch_off_at")]
    )


class SwitchOnAt(RunTimerEntity, TimeEntity):
    """Planned switch-on; setting it plans the next occurrence with the default run time."""

    @property
    def native_value(self) -> time | None:
        """Return the planned switch-on as local time of day."""
        on_at = self.controller.on_at
        return dt_util.as_local(on_at).time().replace(second=0, microsecond=0) if on_at else None

    async def async_set_value(self, value: time) -> None:
        """Plan a switch-on."""
        await self.controller.async_on_at(value, None)


class SwitchOffAt(RunTimerEntity, TimeEntity):
    """Fixed switch-off time; setting it means the next occurrence."""

    @property
    def native_value(self) -> time | None:
        """Return the fixed switch-off time as local time of day."""
        off_fixed = self.controller.off_fixed
        return dt_util.as_local(off_fixed).time().replace(second=0, microsecond=0) if off_fixed else None

    async def async_set_value(self, value: time) -> None:
        """Set the fixed switch-off time."""
        await self.controller.async_off_at(value)
