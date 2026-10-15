"""Run Timer: switch a device off after a run time."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device import async_entity_id_to_device_id
from homeassistant.helpers.helper_integration import async_handle_source_entity_changes
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, STORAGE_VERSION
from .controller import RunTimerController
from .frontend import async_setup_frontend
from .services import async_setup_services

PLATFORMS = [Platform.NUMBER, Platform.SENSOR, Platform.TIME]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type RunTimerConfigEntry = ConfigEntry[RunTimerController]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the services and, with a frontend, the more-info panel."""
    async_setup_services(hass)
    if "frontend" in hass.config.components:
        await async_setup_frontend(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: RunTimerConfigEntry) -> bool:
    """Set up one managed entity."""

    def set_target(entity_id: str) -> None:
        # Follow a renamed entity.
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_ENTITY_ID: entity_id}, unique_id=entity_id
        )
        hass.config_entries.async_schedule_reload(entry.entry_id)

    target = entry.data[CONF_ENTITY_ID]
    entry.async_on_unload(
        async_handle_source_entity_changes(
            hass,
            helper_config_entry_id=entry.entry_id,
            set_source_entity_id_or_uuid=set_target,
            source_device_id=async_entity_id_to_device_id(hass, target),
            source_entity_id_or_uuid=target,
        )
    )
    controller = RunTimerController(hass, entry)
    await controller.async_load()
    entry.runtime_data = controller
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: RunTimerConfigEntry) -> None:
    entry.runtime_data.async_options_updated()


async def async_unload_entry(hass: HomeAssistant, entry: RunTimerConfigEntry) -> bool:
    """Unload a config entry."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_unload()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: RunTimerConfigEntry) -> None:
    """Drop the stored times of a removed entry."""
    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}").async_remove()
