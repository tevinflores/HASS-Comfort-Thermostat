"""Tests for the Comfort Thermostat config / options flow."""
from __future__ import annotations

import pytest
import voluptuous as vol
from unittest.mock import MagicMock

from custom_components.comfort_thermostat.config_flow import (
    ComfortThermostatConfigFlow,
    ComfortThermostatOptionsFlow,
)
from custom_components.comfort_thermostat.const import (
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
    DEFAULT_HOME_MAX,
    DEFAULT_HOME_MIN,
)


REAL_CLIMATE_ID = "climate.real_ac"
INSIDE_SENSOR_ID = "sensor.whole_home_temperature"
SLEEP_SENSOR_ID = "sensor.upstairs_avg_temp"
AWAY_SENSOR_ID = "sensor.whole_home_temperature"
OUTSIDE_SENSOR_ID = "sensor.outside_temp"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _schema_keys(schema: vol.Schema) -> list[str]:
    """Return the field names (as strings) from a voluptuous schema."""
    return [str(k) for k in schema.schema.keys()]


def _schema_defaults(schema: vol.Schema) -> dict[str, object]:
    """Return {field name: default value} for fields that have a default."""
    out: dict[str, object] = {}
    for key in schema.schema.keys():
        # vol.Optional / vol.Required wrap the key string; default callable
        # exists on Marker.  Calling default() with no default raises.
        if hasattr(key, "default") and key.default is not vol.UNDEFINED:
            try:
                out[str(key)] = key.default()
            except (TypeError, vol.Invalid):
                pass
    return out


def _schema_suggested(schema: vol.Schema) -> dict[str, object]:
    """Return {field: suggested_value} from each marker's description."""
    out: dict[str, object] = {}
    for key in schema.schema.keys():
        desc = getattr(key, "description", None)
        if isinstance(desc, dict) and "suggested_value" in desc:
            out[str(key)] = desc["suggested_value"]
    return out


def _make_entry(data: dict, options: dict | None = None) -> MagicMock:
    """Build a mock ConfigEntry."""
    entry = MagicMock()
    entry.data = data
    entry.options = options or {}
    return entry


def _make_options_flow(entry: MagicMock, unit: str = "°C") -> ComfortThermostatOptionsFlow:
    """Build an options flow on a hass mock using the given system unit."""
    flow = ComfortThermostatOptionsFlow(entry)
    flow.hass = MagicMock()
    flow.hass.config.units.temperature_unit = unit
    return flow


async def _build_options_schema(entry: MagicMock, unit: str = "°C") -> vol.Schema:
    """Invoke async_step_init's form path and return the data_schema."""
    flow = _make_options_flow(entry, unit)
    captured: dict = {}

    def _capture(*, step_id, data_schema, **_):
        captured["schema"] = data_schema
        return {"step_id": step_id}

    flow.async_show_form = _capture  # type: ignore[assignment]
    await flow.async_step_init(None)
    return captured["schema"]


async def _build_user_schema() -> vol.Schema:
    """Invoke async_step_user's form path and return the data_schema."""
    flow = ComfortThermostatConfigFlow()
    flow.hass = MagicMock()
    captured: dict = {}

    def _capture(*, step_id, data_schema, **_):
        captured["schema"] = data_schema
        return {"step_id": step_id}

    flow.async_show_form = _capture  # type: ignore[assignment]
    await flow.async_step_user(None)
    return captured["schema"]


# ---------------------------------------------------------------------------
# Initial config flow — sensor fields present
# ---------------------------------------------------------------------------

class TestUserStepSchema:
    """Initial setup (config flow) must expose all per-preset sensors."""

    @pytest.mark.asyncio
    async def test_user_step_includes_all_inside_sensors(self):
        schema = await _build_user_schema()
        keys = _schema_keys(schema)
        assert CONF_INSIDE_SENSOR in keys
        assert CONF_INSIDE_SENSOR_SLEEP in keys
        assert CONF_INSIDE_SENSOR_AWAY in keys
        assert CONF_OUTSIDE_SENSOR in keys


# ---------------------------------------------------------------------------
# Options flow — the missing-UI bug
# ---------------------------------------------------------------------------

class TestOptionsFlowSensors:
    """Existing installs must reach the per-preset sensors via Configure."""

    def _base_entry(self, options: dict | None = None) -> MagicMock:
        return _make_entry(
            data={
                CONF_REAL_CLIMATE: REAL_CLIMATE_ID,
                CONF_INSIDE_SENSOR: INSIDE_SENSOR_ID,
            },
            options=options,
        )

    @pytest.mark.asyncio
    async def test_options_flow_exposes_inside_sensor(self):
        schema = await _build_options_schema(self._base_entry())
        assert CONF_INSIDE_SENSOR in _schema_keys(schema)

    @pytest.mark.asyncio
    async def test_options_flow_exposes_sleep_sensor(self):
        """Bug: opening Configure on an existing v6.0.0 install showed no
        Sleep sensor field.  Options flow must list every per-preset sensor
        so users without sleep/away set up via initial flow can add them."""
        schema = await _build_options_schema(self._base_entry())
        assert CONF_INSIDE_SENSOR_SLEEP in _schema_keys(schema)

    @pytest.mark.asyncio
    async def test_options_flow_exposes_away_sensor(self):
        schema = await _build_options_schema(self._base_entry())
        assert CONF_INSIDE_SENSOR_AWAY in _schema_keys(schema)

    @pytest.mark.asyncio
    async def test_options_flow_exposes_outside_sensor(self):
        schema = await _build_options_schema(self._base_entry())
        assert CONF_OUTSIDE_SENSOR in _schema_keys(schema)

    @pytest.mark.asyncio
    async def test_options_flow_keeps_preset_temp_fields(self):
        """The fix must not regress the existing preset-range editing."""
        schema = await _build_options_schema(self._base_entry())
        keys = _schema_keys(schema)
        for expected in (
            CONF_HOME_MIN, CONF_HOME_MAX,
            CONF_SLEEP_MIN, CONF_SLEEP_MAX,
            CONF_AWAY_MIN, CONF_AWAY_MAX,
        ):
            assert expected in keys, f"missing {expected}"

    # ------------------------------------------------------------------
    # Defaults / suggested values come from data ∪ options
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_inside_sensor_default_from_entry_data(self):
        """Home sensor (Required) shows the original initial-setup value."""
        schema = await _build_options_schema(self._base_entry())
        defaults = _schema_defaults(schema)
        assert defaults.get(CONF_INSIDE_SENSOR) == INSIDE_SENSOR_ID

    @pytest.mark.asyncio
    async def test_options_override_data_for_inside_sensor_default(self):
        """If options already changed the Home sensor, that value wins."""
        new_home = "sensor.downstairs_avg_temp"
        entry = self._base_entry(options={CONF_INSIDE_SENSOR: new_home})
        schema = await _build_options_schema(entry)
        defaults = _schema_defaults(schema)
        assert defaults.get(CONF_INSIDE_SENSOR) == new_home

    @pytest.mark.asyncio
    async def test_sleep_suggested_when_already_configured(self):
        """When the Sleep sensor is set, the form pre-fills it."""
        entry = self._base_entry(options={CONF_INSIDE_SENSOR_SLEEP: SLEEP_SENSOR_ID})
        schema = await _build_options_schema(entry)
        suggested = _schema_suggested(schema)
        assert suggested.get(CONF_INSIDE_SENSOR_SLEEP) == SLEEP_SENSOR_ID

    @pytest.mark.asyncio
    async def test_sleep_has_no_default_when_unset(self):
        """No previous value → no default, so the field renders empty.

        Setting default=None for an EntitySelector would render an invalid
        pre-selection, so the absence of a default is the correct state.
        """
        schema = await _build_options_schema(self._base_entry())
        defaults = _schema_defaults(schema)
        suggested = _schema_suggested(schema)
        assert CONF_INSIDE_SENSOR_SLEEP not in defaults
        assert CONF_INSIDE_SENSOR_SLEEP not in suggested

    @pytest.mark.asyncio
    async def test_preset_temp_defaults_preserved(self):
        """Preset min/max defaults still come from options, falling back
        to const defaults — the original options-flow behavior."""
        entry = self._base_entry(options={CONF_HOME_MIN: 20.5, CONF_HOME_MAX: 24.5})
        schema = await _build_options_schema(entry)
        defaults = _schema_defaults(schema)
        assert defaults.get(CONF_HOME_MIN) == 20.5
        assert defaults.get(CONF_HOME_MAX) == 24.5

    @pytest.mark.asyncio
    async def test_preset_temp_falls_back_to_const_defaults(self):
        schema = await _build_options_schema(self._base_entry())
        defaults = _schema_defaults(schema)
        assert defaults.get(CONF_HOME_MIN) == DEFAULT_HOME_MIN
        assert defaults.get(CONF_HOME_MAX) == DEFAULT_HOME_MAX

    @pytest.mark.asyncio
    async def test_field_order_sensors_before_temperatures(self):
        """Sensors must appear before preset temperatures so they aren't
        buried below a wall of numeric inputs."""
        schema = await _build_options_schema(self._base_entry())
        keys = _schema_keys(schema)
        sensor_idx = keys.index(CONF_INSIDE_SENSOR)
        temp_idx = keys.index(CONF_HOME_MIN)
        assert sensor_idx < temp_idx


# ---------------------------------------------------------------------------
# Options flow — preset temperatures follow the HA system unit
# ---------------------------------------------------------------------------

class TestOptionsFlowFahrenheit:
    """Preset temps are stored in °C but shown / entered in the system unit."""

    def _entry(self, options: dict | None = None) -> MagicMock:
        return _make_entry(
            data={
                CONF_REAL_CLIMATE: REAL_CLIMATE_ID,
                CONF_INSIDE_SENSOR: INSIDE_SENSOR_ID,
            },
            options=options,
        )

    @pytest.mark.asyncio
    async def test_defaults_shown_in_fahrenheit(self):
        entry = self._entry(options={CONF_HOME_MIN: 20.0, CONF_HOME_MAX: 24.0})
        defaults = _schema_defaults(await _build_options_schema(entry, "°F"))
        assert defaults[CONF_HOME_MIN] == 68.0
        assert defaults[CONF_HOME_MAX] == 75.2

    @pytest.mark.asyncio
    async def test_selector_uses_fahrenheit_unit_and_bounds(self):
        schema = await _build_options_schema(self._entry(), "°F")
        selector = next(
            v for k, v in schema.schema.items() if str(k) == CONF_HOME_MIN
        )
        assert selector.config["unit_of_measurement"] == "°F"
        assert selector.config["min"] == 50.0  # MIN_TEMP 10 °C
        assert selector.config["max"] == 95.0  # MAX_TEMP 35 °C

    @pytest.mark.asyncio
    async def test_submitted_fahrenheit_stored_as_celsius(self):
        flow = _make_options_flow(self._entry(), "°F")
        created: dict = {}

        def _capture(*, title, data):
            created.update(data)
            return {"type": "create_entry"}

        flow.async_create_entry = _capture  # type: ignore[assignment]
        await flow.async_step_init(
            {
                CONF_INSIDE_SENSOR: INSIDE_SENSOR_ID,
                CONF_HOME_MIN: 68.0,
                CONF_HOME_MAX: 75.2,
                CONF_SLEEP_MIN: 66.2,
                CONF_SLEEP_MAX: 71.6,
                CONF_AWAY_MIN: 64.4,
                CONF_AWAY_MAX: 78.8,
            }
        )
        assert created[CONF_INSIDE_SENSOR] == INSIDE_SENSOR_ID
        assert created[CONF_HOME_MIN] == 20.0
        assert created[CONF_HOME_MAX] == 24.0
        assert created[CONF_SLEEP_MIN] == 19.0
        assert created[CONF_AWAY_MAX] == 26.0

    @pytest.mark.asyncio
    async def test_celsius_system_unchanged(self):
        entry = self._entry(options={CONF_HOME_MIN: 20.5})
        defaults = _schema_defaults(await _build_options_schema(entry, "°C"))
        assert defaults[CONF_HOME_MIN] == 20.5
