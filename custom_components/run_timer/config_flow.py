"""Config flow for run_timer."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import callback, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.script import async_validate_actions_config
from homeassistant.helpers.selector import (
    ActionSelector,
    EntitySelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    CONF_DEFAULT_MINUTES,
    CONF_ON_ACTION,
    DEFAULT_MINUTES_MAX,
    DEFAULT_MINUTES_MIN,
    DOMAIN,
)

_MINUTES = NumberSelector(
    NumberSelectorConfig(
        min=DEFAULT_MINUTES_MIN,
        max=DEFAULT_MINUTES_MAX,
        step=1,
        mode=NumberSelectorMode.BOX,
        unit_of_measurement="min",
    )
)


class RunTimerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add one managed entity."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the entity and its default run time."""
        errors: dict[str, str] = {}
        if user_input is not None:
            entity_id = user_input[CONF_ENTITY_ID]
            await self.async_set_unique_id(entity_id)
            self._abort_if_unique_id_configured()
            domain = split_entity_id(entity_id)[0]
            services = self.hass.services
            if services.has_service(domain, SERVICE_TURN_ON) and services.has_service(
                domain, SERVICE_TURN_OFF
            ):
                state = self.hass.states.get(entity_id)
                return self.async_create_entry(
                    title=state.name if state else entity_id,
                    data={CONF_ENTITY_ID: entity_id},
                    options={
                        CONF_DEFAULT_MINUTES: int(user_input[CONF_DEFAULT_MINUTES])
                    },
                )
            errors[CONF_ENTITY_ID] = "no_on_off"
        schema = vol.Schema(
            {
                vol.Required(CONF_ENTITY_ID): EntitySelector(),
                vol.Required(CONF_DEFAULT_MINUTES, default=240): _MINUTES,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return RunTimerOptionsFlow()


class RunTimerOptionsFlow(OptionsFlow):
    """Change default run time and switch-on action."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            actions = user_input.get(CONF_ON_ACTION) or []
            try:
                await async_validate_actions_config(
                    self.hass, cv.SCRIPT_SCHEMA(actions)
                )
            except (vol.Invalid, HomeAssistantError):
                errors[CONF_ON_ACTION] = "invalid_action"
            else:
                return self.async_create_entry(
                    data={
                        CONF_DEFAULT_MINUTES: int(user_input[CONF_DEFAULT_MINUTES]),
                        CONF_ON_ACTION: actions,
                    }
                )
        schema = vol.Schema(
            {
                vol.Required(CONF_DEFAULT_MINUTES): _MINUTES,
                vol.Optional(CONF_ON_ACTION): ActionSelector(),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input or self.config_entry.options
            ),
            errors=errors,
        )
