"""Config flow for Smart Climate integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import UnitOfTemperature
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    CONF_AWAY_MAX,
    CONF_AWAY_MIN,
    CONF_HOME_MAX,
    CONF_HOME_MIN,
    CONF_INSIDE_SENSOR,
    CONF_INSIDE_SENSOR_AWAY,
    CONF_INSIDE_SENSOR_SLEEP,
    CONF_OUTSIDE_SENSOR,
    CONF_REAL_CLIMATE,
    CONF_SLEEP_MAX,
    CONF_SLEEP_MIN,
    DEFAULT_AWAY_MAX,
    DEFAULT_AWAY_MIN,
    DEFAULT_HOME_MAX,
    DEFAULT_HOME_MIN,
    DEFAULT_SLEEP_MAX,
    DEFAULT_SLEEP_MIN,
    DOMAIN,
    MAX_TEMP,
    MIN_TEMP,
    TEMP_STEP,
)

_PRESET_TEMP_KEYS = (
    CONF_HOME_MIN,
    CONF_HOME_MAX,
    CONF_SLEEP_MIN,
    CONF_SLEEP_MAX,
    CONF_AWAY_MIN,
    CONF_AWAY_MAX,
)


def _temp_selector(unit: str) -> NumberSelector:
    """Return a preset-temperature selector bounded in the display ``unit``."""
    return NumberSelector(
        NumberSelectorConfig(
            min=_to_display(MIN_TEMP, unit),
            max=_to_display(MAX_TEMP, unit),
            step=TEMP_STEP,
            unit_of_measurement=unit,
            mode=NumberSelectorMode.BOX,
        )
    )


def _to_display(celsius: float, unit: str) -> float:
    """Convert a stored °C preset value to the display unit for the form."""
    return round(
        TemperatureConverter.convert(celsius, UnitOfTemperature.CELSIUS, unit), 1
    )


def _from_display(value: float, unit: str) -> float:
    """Convert a form value in the display unit back to °C for storage."""
    return round(
        TemperatureConverter.convert(value, unit, UnitOfTemperature.CELSIUS), 2
    )


class SmartClimateConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial config flow for Smart Climate."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the first (and only) user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(
                title=user_input["name"],
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required("name", default="Smart Climate"): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Required(CONF_REAL_CLIMATE): EntitySelector(
                    EntitySelectorConfig(domain=CLIMATE_DOMAIN)
                ),
                vol.Required(CONF_INSIDE_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain=SENSOR_DOMAIN)
                ),
                vol.Optional(CONF_INSIDE_SENSOR_SLEEP): EntitySelector(
                    EntitySelectorConfig(domain=SENSOR_DOMAIN)
                ),
                vol.Optional(CONF_INSIDE_SENSOR_AWAY): EntitySelector(
                    EntitySelectorConfig(domain=SENSOR_DOMAIN)
                ),
                vol.Optional(CONF_OUTSIDE_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain=SENSOR_DOMAIN)
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SmartClimateOptionsFlow:
        """Return the options flow handler."""
        return SmartClimateOptionsFlow(config_entry)


class SmartClimateOptionsFlow(OptionsFlow):
    """Handle options (preset temperatures) for Smart Climate."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage sensors and preset temperature options for an existing entry.

        Includes the per-preset inside sensors so existing installs can wire
        up Sleep / Away zones without deleting and re-adding the integration.
        Pre-populates every field from the union of ``entry.data`` (initial
        setup values) and ``entry.options`` (previous edits via this flow)
        so the form always shows the currently effective configuration.

        Preset temperatures are stored in °C (the entity's native unit) but
        shown and entered in the HA system unit, converted at this boundary.
        """
        unit = self.hass.config.units.temperature_unit

        if user_input is not None:
            data = dict(user_input)
            for key in _PRESET_TEMP_KEYS:
                if key in data:
                    data[key] = _from_display(data[key], unit)
            return self.async_create_entry(title="", data=data)

        current = {**self._config_entry.data, **self._config_entry.options}

        # Build optional EntitySelector entries with suggested_value rather
        # than `default=...` so clearing a field in the form removes the
        # key from user_input (default= would re-fill the previous value
        # and make optional sensors un-clearable).
        def _optional_sensor(key: str) -> dict:
            value = current.get(key)
            description = {"suggested_value": value} if value else {}
            return {
                vol.Optional(key, description=description): EntitySelector(
                    EntitySelectorConfig(domain=SENSOR_DOMAIN)
                )
            }

        sensor_schema: dict = {
            vol.Required(
                CONF_INSIDE_SENSOR,
                default=current.get(CONF_INSIDE_SENSOR),
            ): EntitySelector(EntitySelectorConfig(domain=SENSOR_DOMAIN)),
        }
        sensor_schema.update(_optional_sensor(CONF_INSIDE_SENSOR_SLEEP))
        sensor_schema.update(_optional_sensor(CONF_INSIDE_SENSOR_AWAY))
        sensor_schema.update(_optional_sensor(CONF_OUTSIDE_SENSOR))

        defaults = {
            CONF_HOME_MIN: DEFAULT_HOME_MIN,
            CONF_HOME_MAX: DEFAULT_HOME_MAX,
            CONF_SLEEP_MIN: DEFAULT_SLEEP_MIN,
            CONF_SLEEP_MAX: DEFAULT_SLEEP_MAX,
            CONF_AWAY_MIN: DEFAULT_AWAY_MIN,
            CONF_AWAY_MAX: DEFAULT_AWAY_MAX,
        }
        temp_selector = _temp_selector(unit)
        preset_schema = {
            vol.Required(
                key,
                default=_to_display(current.get(key, defaults[key]), unit),
            ): temp_selector
            for key in _PRESET_TEMP_KEYS
        }

        schema = vol.Schema({**sensor_schema, **preset_schema})

        return self.async_show_form(step_id="init", data_schema=schema)
