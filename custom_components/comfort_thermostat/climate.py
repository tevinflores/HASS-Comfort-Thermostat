"""Comfort Thermostat - EcoBee-like thermostat platform for Home Assistant.

Wraps a physical climate device and adds:
- Comfort presets (Home, Sleep, Away) with configurable temperature ranges
- Automatic heat/cool switching based on inside temperature vs setpoint range
- Outside temperature awareness for smarter mode decisions
- Manual mode for direct control
"""
from __future__ import annotations

import collections
import datetime
import logging
import math
from typing import Any

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.climate.const import (
    PRESET_AWAY,
    PRESET_HOME,
    PRESET_NONE,
    PRESET_SLEEP,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    PRECISION_TENTHS,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
)
from homeassistant.helpers.restore_state import RestoreEntity
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
    COMMAND_GRACE_SECONDS,
    DEFAULT_AWAY_MAX,
    DEFAULT_AWAY_MIN,
    DEFAULT_HOME_MAX,
    DEFAULT_HOME_MIN,
    DEFAULT_SLEEP_MAX,
    DEFAULT_SLEEP_MIN,
    FAST_FLIP_CONFIRM,
    FLIP_DWELL,
    FLIP_MARGIN,
    INSIDE_TEMP_PLAUSIBLE_MAX,
    INSIDE_TEMP_PLAUSIBLE_MIN,
    MAX_DRIFT_RESENDS,
    MAX_TEMP,
    MIN_CHANGEOVER_INTERVAL,
    MIN_TEMP,
    MIN_TEMP_DIFF,
    OUT_OF_BAND_ALERT_MINUTES,
    SENSOR_STALE_MINUTES,
    SHORT_CYCLE_THRESHOLD_PER_H,
    TEMP_STEP,
)

_LOGGER = logging.getLogger(__name__)

# Presets offered to the user (HA standard preset constants)
SUPPORTED_PRESETS = [PRESET_HOME, PRESET_SLEEP, PRESET_AWAY, PRESET_NONE]

# Real-device actions that count as a compressor start when entered from a
# stopped one (#8), and the actions during which the compressor is running.
# Defrost reverses the cycle without stopping, so heating → defrosting →
# heating is not a start.
_STARTS = (HVACAction.HEATING, HVACAction.COOLING)
_RUNNING = (*_STARTS, HVACAction.DEFROSTING, HVACAction.DRYING)
CURRENT_TEMP_DISPLAY_DECIMALS = 2


def _widen_band(
    low: float, high: float, keep_high: bool = False
) -> tuple[float, float]:
    """Return (low, high) widened to at least MIN_TEMP_DIFF apart.

    Moves ``low`` down when ``keep_high`` (the user just set high), otherwise
    moves ``high`` up, then shifts the band back inside [MIN_TEMP, MAX_TEMP].
    """
    if high - low >= MIN_TEMP_DIFF:
        return low, high
    if keep_high:
        low = high - MIN_TEMP_DIFF
    else:
        high = low + MIN_TEMP_DIFF
    if low < MIN_TEMP:
        low, high = MIN_TEMP, MIN_TEMP + MIN_TEMP_DIFF
    if high > MAX_TEMP:
        low, high = MAX_TEMP - MIN_TEMP_DIFF, MAX_TEMP
    return low, high


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Comfort Thermostat from a config entry."""
    config = {**entry.data, **entry.options}
    entity = ComfortThermostatEntity(hass, entry.entry_id, entry.title, config)
    async_add_entities([entity])


class ComfortThermostatEntity(ClimateEntity, RestoreEntity):
    """EcoBee-like smart thermostat that wraps a real climate entity.

    In AUTO mode the entity manages a *temperature range* (low/high setpoints)
    and picks HEAT or COOL once, holding that mode while the (modulating)
    real device settles on the comfort-band midpoint.  HEAT↔COOL flips only
    after the inside temperature has been continuously past the midpoint by
    FLIP_MARGIN for FLIP_DWELL seconds — i.e. the room is genuinely asking
    for the opposite mode, not just jittering across the boundary.  The real
    device is never commanded OFF in AUTO; on inverter heat pumps a steady
    setpoint at low modulation costs less than the start-up of an OFF→ON
    cycle, and short OFF cycles defeat the unit's own steady-state operation.

    Four presets are supported:
      - Home  – default daytime comfort range
      - Sleep – cooler nighttime comfort range
      - Away  – wider range for unoccupied periods
      - None  – manual/direct control (no preset enforced)

    Master/slave relationship with the real climate entity:
    This entity is the sole writer of the wrapped device's hvac_mode and
    temperature.  State-change events from the real device are used only to
    mirror its hvac_action for UI display – they never feed back into the
    authoritative state owned here (hvac_mode, preset_mode, setpoints).
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    # Keep climate control precision at tenths (HA-supported value for climate
    # entity precision); current_temperature display is overridden to hundredths
    # in state_attributes for smoother charting.
    _attr_precision = PRECISION_TENTHS
    # Suppress backwards-compat warning for turn_on / turn_off
    _enable_turn_on_off_backwards_compat = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        name: str,
        config: dict,
    ) -> None:
        """Initialize the entity."""
        self.hass = hass
        self._entry_id = entry_id
        self._attr_name = name
        self._attr_unique_id = entry_id

        self._real_climate_id: str = config[CONF_REAL_CLIMATE]

        # Per-preset inside sensors.  The Home / default sensor stays under
        # CONF_INSIDE_SENSOR (no key migration) and doubles as the fallback
        # for any preset whose dedicated sensor is unset or unavailable, and
        # as the sensor used in PRESET_NONE (manual mode).  Sleep / Away
        # sensors are optional.
        self._inside_sensor_id: str = config[CONF_INSIDE_SENSOR]
        self._preset_sensor_ids: dict[str, str] = {
            PRESET_HOME: self._inside_sensor_id,
        }
        sleep_sensor = config.get(CONF_INSIDE_SENSOR_SLEEP)
        if sleep_sensor:
            self._preset_sensor_ids[PRESET_SLEEP] = sleep_sensor
        away_sensor = config.get(CONF_INSIDE_SENSOR_AWAY)
        if away_sensor:
            self._preset_sensor_ids[PRESET_AWAY] = away_sensor

        self._outside_sensor_id: str | None = config.get(CONF_OUTSIDE_SENSOR)

        # Preset temperature ranges keyed by HA preset constant
        self._preset_ranges: dict[str, tuple[float, float]] = {
            PRESET_HOME: (
                config.get(CONF_HOME_MIN, DEFAULT_HOME_MIN),
                config.get(CONF_HOME_MAX, DEFAULT_HOME_MAX),
            ),
            PRESET_SLEEP: (
                config.get(CONF_SLEEP_MIN, DEFAULT_SLEEP_MIN),
                config.get(CONF_SLEEP_MAX, DEFAULT_SLEEP_MAX),
            ),
            PRESET_AWAY: (
                config.get(CONF_AWAY_MIN, DEFAULT_AWAY_MIN),
                config.get(CONF_AWAY_MAX, DEFAULT_AWAY_MAX),
            ),
        }
        # Entries saved before #6 could hold bands as narrow as 0.5 °C,
        # which park the room above the band (see MIN_TEMP_DIFF).  Widen
        # them here; the options flow rejects them on the next edit.
        for preset, (low, high) in self._preset_ranges.items():
            widened = _widen_band(low, high)
            if widened != (low, high):
                _LOGGER.warning(
                    "%s: %s range %s–%s °C is narrower than %s °C; using %s–%s °C",
                    name, preset, low, high, MIN_TEMP_DIFF, *widened,
                )
                self._preset_ranges[preset] = widened

        # Internal state
        self._hvac_mode: HVACMode = HVACMode.OFF
        self._preset_mode: str = PRESET_HOME
        self._target_temp_low: float = DEFAULT_HOME_MIN
        self._target_temp_high: float = DEFAULT_HOME_MAX
        self._target_temperature: float = (DEFAULT_HOME_MIN + DEFAULT_HOME_MAX) / 2.0
        self._current_temperature: float | None = None
        self._outside_temperature: float | None = None
        self._hvac_action: HVACAction | None = None

        # Guard flag – skip sensor-triggered syncs while a control call is in
        # flight so the two paths do not issue overlapping service calls.
        self._updating_from_control: bool = False

        # Sticky HEAT/COOL choice for AUTO mode.  None means no AUTO decision
        # has been made yet (initial entry, or after leaving AUTO).  Once
        # set, _desired_real_mode returns this value until the flip rule
        # commits the opposite mode.
        self._auto_mode: HVACMode | None = None

        # Timestamp at which the inside temperature first crossed FLIP_MARGIN
        # past the midpoint *against* the current _auto_mode.  Cleared when
        # the temperature returns to the correct half of the band; flips
        # _auto_mode once it has been set continuously for FLIP_DWELL.
        self._pending_flip_since: datetime.datetime | None = None

        # Timestamp at which the fast-flip band-edge violation was first
        # seen; it must hold for FAST_FLIP_CONFIRM before the flip fires.
        self._fast_flip_since: datetime.datetime | None = None

        # When AUTO last changed direction (fast or dwell flip, not the
        # initial pick).  Spaces changeovers by MIN_CHANGEOVER_INTERVAL.
        self._last_changeover_at: datetime.datetime | None = None

        # Pending re-check for a fast-flip that is waiting on confirmation
        # or on the changeover interval.  Needed because a report-on-change
        # sensor can sit steadily past the band edge and never send the
        # reading that would otherwise re-run the decision.
        self._flip_recheck_unsub: CALLBACK_TYPE | None = None

        # Last unit command (HEAT/COOL/OFF) the wrapper computed for the
        # real device.  Used by the hvac_action property to surface IDLE
        # while in AUTO + deliberate-OFF (inside the comfort band) so the
        # frontend distinguishes "AUTO resting" from "user turned it off".
        self._unit_command: HVACMode | None = None

        # Timestamp of the last `_unit_command` change.  Used by the
        # desync detector to allow the real device a grace period to
        # transition into the commanded state.  Don't update this on
        # every sync — only when the command itself changes.
        self._unit_command_at: datetime.datetime | None = None

        # Setpoint (in the device's unit) sent with `_unit_command`; None
        # for OFF.  Together they are what the real device should show.
        self._unit_setpoint: float | None = None

        # Drift re-send (#7): a pending re-check while the real device
        # doesn't match `_unit_command` / `_unit_setpoint`, how many
        # re-sends in a row it has taken, and whether the device was
        # available at the last event (to catch it coming back).
        self._drift_recheck_unsub: CALLBACK_TYPE | None = None
        self._drift_resends: int = 0
        self._real_available: bool = False

        # Whether the real device has shown `_unit_command` since it was
        # sent.  A mode change after that came from someone else (IR
        # remote); `_foreign_mode` is that mode and `_foreign_since` when
        # it started.  It is only undone once it has run for
        # MIN_CHANGEOVER_INTERVAL, so undoing it can't short-cycle the unit.
        self._device_matched: bool = False
        self._foreign_mode: str | None = None
        self._foreign_since: datetime.datetime | None = None

        # Problem-detection state (surfaced via `problems` attribute).
        # Updated by sensor / sync callbacks; checked at attribute read.
        self._out_of_band_since: datetime.datetime | None = None
        # When the real device's hvac_action last went into heating or
        # cooling (#8); counted over the trailing hour for short_cycle.
        self._compressor_starts: collections.deque[datetime.datetime] = (
            collections.deque(maxlen=20)
        )

    # ------------------------------------------------------------------
    # ClimateEntity properties
    # ------------------------------------------------------------------

    @property
    def temperature_unit(self) -> str:
        """Return the native unit of every temperature this entity holds.

        All internal state, constants, preset ranges and config-flow values
        are °C, so the entity is natively Celsius regardless of the HA
        system unit.  HA core converts our properties to the display unit
        and converts incoming ``set_temperature`` values back to °C.  The
        boundaries HA does *not* convert for us — sensor states, the real
        device's attributes and service calls to it — go through
        ``_to_celsius`` / ``_from_celsius``.
        """
        return UnitOfTemperature.CELSIUS

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available HVAC modes."""
        return [HVACMode.OFF, HVACMode.AUTO, HVACMode.HEAT, HVACMode.COOL]

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC operation mode."""
        return self._hvac_mode

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running HVAC action mirrored from the real
        device.  v3.0.x had a special case here that surfaced IDLE when
        the wrapper had commanded OFF in AUTO+COOL (deliberate-OFF).
        Removed in v5.0.0 along with the deliberate-OFF design — the
        wrapper now just commands HEAT or COOL in AUTO and lets the unit
        idle internally via its own setpoint logic; the unit's own
        `hvac_action=idle` is the right signal.
        """
        return self._hvac_action

    @property
    def preset_modes(self) -> list[str]:
        """Return the list of available preset modes."""
        return SUPPORTED_PRESETS

    @property
    def preset_mode(self) -> str:
        """Return current preset mode."""
        return self._preset_mode

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature from the inside sensor."""
        return self._current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return single-point target temperature.

        In HEAT / COOL modes this is the direct user-configured setpoint.
        In AUTO mode the midpoint of the active comfort range is returned so
        that the ``temperature`` state attribute is never ``null`` – it gives
        users a meaningful reference value while ``target_temp_low`` /
        ``target_temp_high`` still describe the full range.
        """
        if self._hvac_mode == HVACMode.AUTO:
            return (self._target_temp_low + self._target_temp_high) / 2.0
        return self._target_temperature

    @property
    def target_temperature_low(self) -> float | None:
        """Return low end of target temperature range (AUTO mode only)."""
        if self._hvac_mode == HVACMode.AUTO:
            return self._target_temp_low
        return None

    @property
    def target_temperature_high(self) -> float | None:
        """Return high end of target temperature range (AUTO mode only)."""
        if self._hvac_mode == HVACMode.AUTO:
            return self._target_temp_high
        return None

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return bitmask of supported features."""
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

    @property
    def min_temp(self) -> float:
        """Return the minimum settable temperature."""
        return MIN_TEMP

    @property
    def max_temp(self) -> float:
        """Return the maximum settable temperature."""
        return MAX_TEMP

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step size for target temperature."""
        return TEMP_STEP

    @property
    def state_attributes(self) -> dict[str, Any]:
        """Return state attributes with two-decimal current temperature."""
        attrs = dict(super().state_attributes)
        if self._current_temperature is not None:
            attrs["current_temperature"] = round(
                self._from_celsius(self._current_temperature),
                CURRENT_TEMP_DISPLAY_DECIMALS,
            )
        return attrs

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Surface diagnostic + persisted state alongside HA's standard ones.

        - ``problems`` is a list of detected issues (empty when healthy).
        - ``auto_mode_committed`` is the sticky direction (`heat`/`cool`)
          the wrapper has chosen in AUTO mode.  Persisted via RestoreEntity
          so it survives HA restarts; the wrapper restores it in
          `async_added_to_hass` to skip the initial pick on potentially
          glitchy post-restart sensor data.
        - ``last_unit_command`` is the wrapper's last command to the
          real device (`heat`/`cool`/`off`).  Persisted for the same
          reason — keeps COOL hysteresis state continuous across
          restarts.
        """
        return {
            "problems": self._detect_problems(),
            "auto_mode_committed": (
                self._auto_mode.value if self._auto_mode else None
            ),
            "last_unit_command": (
                self._unit_command.value if self._unit_command else None
            ),
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Run when entity is added; restore state and subscribe to changes."""
        await super().async_added_to_hass()

        # Restore previous state.  Any failure here degrades to the
        # __init__ defaults rather than taking the whole entity down: a
        # raise out of async_added_to_hass aborts add_to_platform_finish,
        # so the device silently fails to appear at all (and a manual
        # reload then "fixes" it, because the removal path overwrites the
        # stored state with the unavailable placeholder).  Restoring seven
        # loosely-typed attributes is not worth that blast radius.
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
            None,
        ):
            try:
                self._restore_from_state(last_state)
            except Exception:  # noqa: BLE001 - defensive, see comment above
                _LOGGER.warning(
                    "Could not restore previous state for %s; "
                    "falling back to defaults",
                    self.entity_id,
                    exc_info=True,
                )

        # Populate initial state from current entity states
        self._sync_from_real_climate()
        self._sync_from_sensors()

        # Push the restored state to the real climate device so that the
        # correct heat/cool commands are sent after a HA restart.
        if self._hvac_mode != HVACMode.OFF:
            await self._async_sync_real_climate()

        # Subscribe to state changes on all tracked entities.  All configured
        # inside sensors are tracked even when not currently active so that
        # the moment a preset switch makes one of them active we already have
        # its latest reading buffered.  The dispatcher below filters updates
        # by the currently-active sensor.
        entities_to_track = [self._real_climate_id]
        entities_to_track.extend(self._all_inside_sensor_ids())
        if self._outside_sensor_id:
            entities_to_track.append(self._outside_sensor_id)

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                entities_to_track,
                self._async_entity_state_changed,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cancel pending re-checks so they can't fire after removal."""
        self._cancel_flip_recheck()
        self._cancel_drift_recheck()
        await super().async_will_remove_from_hass()

    def _restore_from_state(self, last_state: State) -> None:
        """Rehydrate internal state from a previously saved HA state.

        Every attribute is checked for ``None`` rather than key presence.
        HA's ClimateEntity emits ``target_temp_low`` / ``target_temp_high``
        unconditionally whenever ``TARGET_TEMPERATURE_RANGE`` is advertised
        (which we always do), and this wrapper only returns real values for
        them in AUTO — so a state saved in OFF / HEAT / COOL carries the
        keys with a ``None`` value.  Testing membership alone made
        ``float(None)`` raise on every restart that didn't happen to be in
        AUTO.  Attributes left as ``None`` keep their ``__init__`` defaults;
        for a real preset the band is re-derived from ``_preset_ranges``.
        """
        try:
            self._hvac_mode = HVACMode(last_state.state)
        except ValueError:
            self._hvac_mode = HVACMode.OFF

        attrs = last_state.attributes
        restored_preset = attrs.get("preset_mode", PRESET_HOME)
        self._preset_mode = (
            restored_preset if restored_preset in SUPPORTED_PRESETS else PRESET_HOME
        )
        # Saved temperatures are in the system (display) unit — HA converts
        # our °C properties before writing the state.  Values that land
        # outside [MIN_TEMP, MAX_TEMP] after conversion are dropped: they
        # come from pre-fix Fahrenheit installs, which stored raw °C
        # numbers under a °F label (21 "°F" would restore as -6 °C).
        restored = self._restore_temp(attrs.get(ATTR_TARGET_TEMP_LOW))
        if restored is not None:
            self._target_temp_low = restored
        restored = self._restore_temp(attrs.get(ATTR_TARGET_TEMP_HIGH))
        if restored is not None:
            self._target_temp_high = restored
        self._target_temp_low, self._target_temp_high = _widen_band(
            self._target_temp_low, self._target_temp_high
        )
        restored = self._restore_temp(attrs.get(ATTR_TEMPERATURE))
        if restored is not None:
            self._target_temperature = restored

        # Restore the AUTO state machine: the sticky committed
        # direction and the last unit command.  Without this, every
        # HA restart re-runs the initial pick — and on 2026-04-26
        # that picked HEAT against a glitchy startup sensor reading
        # (Z-Wave aggregator briefly reported 21.66 °C while
        # sensors were re-initialising), committing the wrapper to
        # 30 minutes of wrong-direction heating.  Persisting these
        # across restarts keeps the state machine stable.
        committed = attrs.get("auto_mode_committed")
        if committed:
            try:
                self._auto_mode = HVACMode(committed)
            except ValueError:
                self._auto_mode = None
        last_cmd = attrs.get("last_unit_command")
        if last_cmd:
            try:
                self._unit_command = HVACMode(last_cmd)
            except ValueError:
                self._unit_command = None

    def _restore_temp(self, value: Any) -> float | None:
        """Convert a saved display-unit temperature to °C, or ``None``.

        Guards on the value, not key presence — see ``_restore_from_state``.
        """
        if value is None:
            return None
        celsius = self._to_celsius(float(value))
        if not MIN_TEMP <= celsius <= MAX_TEMP:
            return None
        return celsius

    def _all_inside_sensor_ids(self) -> list[str]:
        """Return every configured inside-sensor id (deduplicated, stable order).

        Home / default first (always present), then any per-preset sensors
        that don't share the same entity id.
        """
        ordered: list[str] = [self._inside_sensor_id]
        for preset in (PRESET_SLEEP, PRESET_AWAY):
            sid = self._preset_sensor_ids.get(preset)
            if sid and sid not in ordered:
                ordered.append(sid)
        return ordered

    def _active_sensor_id(self) -> str:
        """Resolve which inside sensor drives ``current_temperature`` *now*.

        Rules:
          - PRESET_HOME / PRESET_SLEEP / PRESET_AWAY → the preset's dedicated
            sensor if configured, else fall back to CONF_INSIDE_SENSOR.
          - PRESET_NONE (manual mode) → CONF_INSIDE_SENSOR.
          - If the per-preset sensor is configured but currently
            unavailable / unknown / missing, fall back to CONF_INSIDE_SENSOR
            so AUTO never stalls on a missing reading.  The fallback is
            surfaced as a ``preset_sensor_unavailable:<preset>`` entry in
            the ``problems`` attribute (see _detect_problems).
        """
        configured = self._preset_sensor_ids.get(self._preset_mode)
        if configured is None:
            return self._inside_sensor_id
        if configured == self._inside_sensor_id:
            return configured
        state = self.hass.states.get(configured)
        if state is None or state.state in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
            None,
            "",
        ):
            return self._inside_sensor_id
        return configured

    @callback
    def _async_entity_state_changed(self, event: Any) -> None:
        """Dispatch state-change events to the appropriate handler.

        Inside-sensor updates dispatch only when the changed entity is the
        currently-active sensor for the active preset.  Updates from
        configured-but-not-active sensors are ignored — they are still
        observed by HA so that switching preset can read their latest
        value synchronously.
        """
        entity_id: str = event.data.get("entity_id", "")
        if entity_id == self._real_climate_id:
            self._on_real_climate_update()
        elif entity_id in (
            self._active_sensor_id(),
            # The preset's own sensor, even when it is no longer the active
            # one: its going unavailable is exactly what makes the fallback
            # active, and dropping that event left its last reading stuck.
            self._preset_sensor_ids.get(self._preset_mode),
        ):
            self._on_inside_sensor_update()
        elif entity_id == self._outside_sensor_id:
            self._on_outside_sensor_update()

    # ------------------------------------------------------------------
    # Initial state sync helpers
    # ------------------------------------------------------------------

    def _sync_from_real_climate(self) -> None:
        """Pull current state from the real climate entity at startup."""
        state = self.hass.states.get(self._real_climate_id)
        self._real_available = self._is_available(state)
        if not self._real_available:
            return
        action = state.attributes.get("hvac_action")
        if action:
            try:
                self._hvac_action = HVACAction(action)
            except ValueError:
                pass

    def _read_inside_temperature(self) -> float | None:
        """Return the active inside sensor's reading in °C, or ``None``.

        ``None`` covers unavailable, unknown, missing, unparsable and
        implausible states (outside ``INSIDE_TEMP_PLAUSIBLE_MIN``..``_MAX``
        after conversion, #3).
        Callers must publish it as-is rather than keep the previous value:
        ``current_temperature`` is forwarded to the unit via Follow Me, so a
        stale number there is regulated against as if it were live (#4).
        """
        state = self.hass.states.get(self._active_sensor_id())
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, None):
            return None
        try:
            value = float(state.state)
        except (ValueError, TypeError):
            return None
        if math.isnan(value):
            return None
        celsius = self._to_celsius(value, self._sensor_unit(state))
        if not INSIDE_TEMP_PLAUSIBLE_MIN <= celsius <= INSIDE_TEMP_PLAUSIBLE_MAX:
            return None
        return celsius

    def _sync_from_sensors(self) -> None:
        """Pull current temperatures from the sensor entities at startup."""
        self._current_temperature = self._read_inside_temperature()

        if self._outside_sensor_id:
            outside_state = self.hass.states.get(self._outside_sensor_id)
            if outside_state and outside_state.state not in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
                None,
            ):
                try:
                    self._outside_temperature = self._to_celsius(
                        float(outside_state.state), self._sensor_unit(outside_state)
                    )
                except (ValueError, TypeError):
                    pass

    # ------------------------------------------------------------------
    # State-change callbacks
    # ------------------------------------------------------------------

    @callback
    def _on_real_climate_update(self) -> None:
        """Mirror the real device's hvac_action and correct drift.

        Comfort Thermostat is the authoritative source of truth for mode, preset,
        and setpoints – see the master/slave note at the top of this class.
        Real-device state-change events never feed back into that state:
        they surface the current action (heating / cooling / idle / off) in
        the frontend, and re-send our command when the device stops
        matching it (#7).
        """
        state = self.hass.states.get(self._real_climate_id)
        available = self._is_available(state)
        came_back = available and not self._real_available
        self._real_available = available
        if not available:
            self._cancel_drift_recheck()
            return

        self._check_drift(state, came_back)

        action_str = state.attributes.get("hvac_action")
        if not action_str:
            return

        try:
            new_action = HVACAction(action_str)
        except ValueError:
            return

        if self._hvac_action != new_action:
            if (
                new_action in _STARTS
                and self._hvac_action not in _RUNNING
            ):
                self._compressor_starts.append(self._now())
            self._hvac_action = new_action
            self.async_write_ha_state()

    @callback
    def _on_inside_sensor_update(self) -> None:
        """Handle inside temperature sensor state changes."""
        new_temp = self._read_inside_temperature()
        old_temp = self._current_temperature
        self._current_temperature = new_temp

        if new_temp is None:
            # No usable reading: publish it as unknown and make no AUTO
            # decision.  The committed direction and the device command
            # stay as they are until a fresh reading arrives.
            if old_temp is not None:
                self.async_write_ha_state()
            return

        # Track sustained out-of-band excursions for problem detection.
        # Only meaningful in AUTO mode — manual HEAT/COOL/OFF is on the
        # user's terms.
        if self._hvac_mode == HVACMode.AUTO:
            low, high = self._active_range()
            if new_temp < low or new_temp > high:
                if self._out_of_band_since is None:
                    self._out_of_band_since = self._now()
            else:
                self._out_of_band_since = None
        else:
            self._out_of_band_since = None

        # In AUTO, re-evaluate the real device's mode.  This includes
        # PRESET_NONE: a manual range edit drops the preset, and skipping
        # it here froze the committed direction until a preset was picked
        # again (#2).  _active_range() supplies the manual low/high.
        if self._hvac_mode == HVACMode.AUTO and not self._updating_from_control:
            self.hass.async_create_task(self._async_sync_real_climate())

        if old_temp != new_temp:
            self.async_write_ha_state()

    @callback
    def _on_outside_sensor_update(self) -> None:
        """Handle outside temperature sensor state changes."""
        state = self.hass.states.get(self._outside_sensor_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        try:
            new_temp = float(state.state)
        except (ValueError, TypeError):
            return
        if math.isnan(new_temp):
            return

        self._outside_temperature = self._to_celsius(
            new_temp, self._sensor_unit(state)
        )

        # In AUTO (with or without a preset), re-evaluate the real device
        if self._hvac_mode == HVACMode.AUTO and not self._updating_from_control:
            self.hass.async_create_task(self._async_sync_real_climate())

    # ------------------------------------------------------------------
    # Temperature / preset helpers
    # ------------------------------------------------------------------

    def _system_unit(self) -> str:
        """Return the HA system temperature unit (the display unit)."""
        return self.hass.config.units.temperature_unit

    def _to_celsius(self, value: float, unit: str | None = None) -> float:
        """Convert ``value`` from ``unit`` (default: system unit) to °C."""
        return TemperatureConverter.convert(
            value, unit or self._system_unit(), UnitOfTemperature.CELSIUS
        )

    def _from_celsius(self, value: float) -> float:
        """Convert a °C ``value`` to the system unit.

        Used for anything HA core does not convert for us: the
        current-temperature override in ``state_attributes`` and the
        setpoints we send to the real device (climate services interpret
        temperatures in the system unit).
        """
        return TemperatureConverter.convert(
            value, UnitOfTemperature.CELSIUS, self._system_unit()
        )

    def _device_setpoint(
        self,
        target: float,
        mode: HVACMode,
        low: float | None = None,
        high: float | None = None,
    ) -> float:
        """Return the °C ``target`` as a whole degree in the device's unit.

        Real thermostats only accept whole-degree setpoints, and their
        advertised ``target_temp_step`` cannot be trusted to reflect that.
        Send exactly what the device will store — otherwise it silently
        rounds (e.g. 22.5 → 22) and every inside-sensor update drives
        another set_temperature trying to "correct" the mismatch.

        The device works in the system unit, so round there: whole °F on a
        °F install (1 °F steps), not whole °C (1.8 °F steps, then rounded
        again by the device) (#9).

        Round directionally (up for HEAT, down for COOL).  With band-edge
        setpoints that usually lands on the band edge itself; when it lands
        outside the comfort band ``[low, high]``, fall back to the
        opposite-direction whole degree inside it.
        """
        # Round to tenths first: °F values stored as 2-decimal °C convert
        # back with noise (71 °F → 21.67 °C → 71.006 °F) that must not
        # ceil up a whole degree.
        def to_device(celsius: float) -> float:
            return round(self._from_celsius(celsius), 1)

        value = to_device(target)
        if mode == HVACMode.HEAT:
            value = math.ceil(value)
            if high is not None and value > to_device(high):
                value = math.floor(to_device(high))
        else:  # COOL
            value = math.floor(value)
            if low is not None and value < to_device(low):
                value = math.ceil(to_device(low))
        return float(value)

    def _sensor_unit(self, state: State) -> str:
        """Return a sensor's temperature unit, falling back to the system unit.

        Temperature sensors normally report in the system unit, but users
        can override a sensor's display unit, and template sensors may not
        declare one at all.
        """
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if unit in TemperatureConverter.VALID_UNITS:
            return unit
        return self._system_unit()

    def _preset_midpoint(self) -> float:
        """Return the midpoint of the current comfort range."""
        low, high = self._active_range()
        return (low + high) / 2.0

    def _active_range(self) -> tuple[float, float]:
        """Return the (low, high) temperature range for the active preset."""
        if self._preset_mode in self._preset_ranges:
            return self._preset_ranges[self._preset_mode]
        # PRESET_NONE / manual – use whatever was last set
        return (self._target_temp_low, self._target_temp_high)

    def _now(self) -> datetime.datetime:
        """Return the current UTC time.  Indirection point for tests."""
        return datetime.datetime.now(datetime.timezone.utc)

    def _detect_problems(self) -> list[str]:
        """Return a list of detected issues, empty when healthy.

        Checks (in order):
        - inside-sensor unavailable / unknown / missing
        - inside-sensor stale (no update for SENSOR_STALE_MINUTES)
        - real climate device unavailable
        - sustained out-of-band temperature in AUTO
        - short-cycling (more than SHORT_CYCLE_THRESHOLD_PER_H compressor
          starts/h)

        Each problem is a short string code with optional context, e.g.
        ``out_of_band:42min``, ``short_cycle:8/h``, ``sensor_stale:18min``.
        """
        problems: list[str] = []
        now = self._now()

        # Per-preset sensor fallback.  If the active preset has a dedicated
        # sensor configured but it is unavailable, _active_sensor_id() will
        # silently fall back to CONF_INSIDE_SENSOR.  Surface that here so a
        # dashboard alert can pick it up — the wrapper keeps running, but a
        # chronic preset-sensor outage means the preset isn't actually
        # zoning anything.
        configured = self._preset_sensor_ids.get(self._preset_mode)
        if (
            configured is not None
            and configured != self._inside_sensor_id
        ):
            preset_state = self.hass.states.get(configured)
            if preset_state is None:
                problems.append(f"preset_sensor_unavailable:{self._preset_mode}")
            elif preset_state.state in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
                None,
                "",
            ):
                problems.append(f"preset_sensor_unavailable:{self._preset_mode}")

        # Inside sensor health — checked against the *active* sensor (which
        # may have already fallen back to CONF_INSIDE_SENSOR above).  If
        # even the fallback is unavailable, the wrapper has nothing to
        # work with — that's the real failure mode.
        active_sensor_id = self._active_sensor_id()
        inside_state = self.hass.states.get(active_sensor_id)
        if inside_state is None:
            problems.append("inside_sensor_missing")
        elif inside_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, None, ""):
            problems.append(f"inside_sensor_{inside_state.state}")
        else:
            # Readings _read_inside_temperature() rejects (#3), so AUTO is
            # running without them; say which, in °C.
            try:
                reading = self._to_celsius(
                    float(inside_state.state), self._sensor_unit(inside_state)
                )
            except (ValueError, TypeError):
                problems.append("inside_sensor_invalid")
            else:
                if not INSIDE_TEMP_PLAUSIBLE_MIN <= reading <= INSIDE_TEMP_PLAUSIBLE_MAX:
                    problems.append(f"inside_sensor_implausible:{round(reading, 1)}")
            try:
                last = inside_state.last_updated
                if last.tzinfo is None:
                    last = last.replace(tzinfo=datetime.timezone.utc)
                stale_min = (now - last).total_seconds() / 60.0
                if stale_min > SENSOR_STALE_MINUTES:
                    problems.append(f"sensor_stale:{int(stale_min)}min")
            except (AttributeError, TypeError):
                pass

        # Real climate device health.
        real_state = self.hass.states.get(self._real_climate_id)
        if real_state is None:
            problems.append("real_climate_missing")
        elif real_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, None, ""):
            problems.append("real_climate_unavailable")

        # AUTO with no reading and no committed direction leaves the device
        # untouched (#5).  The sensor codes above say *why*; this one says
        # AUTO is not controlling anything yet.
        if (
            self._hvac_mode == HVACMode.AUTO
            and self._auto_mode is None
            and self._current_temperature is None
        ):
            problems.append("auto_waiting_for_reading")

        # Sustained out-of-band in AUTO.  AUTO that can't keep the room
        # in band over half-hour windows means the unit is undersized,
        # blocked, or fighting an unmet load — the user should know.
        if (
            self._hvac_mode == HVACMode.AUTO
            and self._out_of_band_since is not None
        ):
            duration = (now - self._out_of_band_since).total_seconds() / 60.0
            if duration > OUT_OF_BAND_ALERT_MINUTES:
                problems.append(f"out_of_band:{int(duration)}min")

        # Short cycling.  Count the real device's compressor starts (heat
        # or cool) in the trailing hour.  The unit cycles on its own while
        # the wrapper's command stays put, so commands can't show this.
        one_hour_ago = now - datetime.timedelta(hours=1)
        recent = sum(1 for t in self._compressor_starts if t > one_hour_ago)
        if recent > SHORT_CYCLE_THRESHOLD_PER_H:
            problems.append(f"short_cycle:{recent}/h")

        # Command desync.  We track the wrapper's last commanded state
        # (`_unit_command`) and the timestamp of the last *change*.  If
        # more than COMMAND_GRACE_SECONDS have passed since the change
        # AND the real device's state still doesn't match what the
        # wrapper believes it commanded, surface that — silently
        # diverging state is the failure mode that produced the
        # 2026-04-26 ghost-HEAT incident.  We compare against
        # `_unit_command.value` (e.g. "cool") which is what the real
        # device's state should read.  The check skips when the real
        # device is unavailable (already covered by another problem
        # code) or when no command has been sent yet.
        if (
            self._unit_command is not None
            and self._unit_command_at is not None
            and real_state is not None
            and real_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN, None, "")
        ):
            elapsed = (now - self._unit_command_at).total_seconds()
            if elapsed > COMMAND_GRACE_SECONDS:
                expected = self._unit_command.value
                actual = real_state.state
                if expected != actual:
                    problems.append(f"command_desync:want={expected}_got={actual}")

        return problems

    def _desired_real_mode(self) -> HVACMode | None:
        """Determine which mode (HEAT/COOL/OFF) the real device should be in.

        For non-AUTO modes the user's choice is passed through.

        Returns ``None`` in AUTO when there is no inside reading and no
        committed direction yet: there is nothing to decide on, so the
        device must be left alone.  Never returns ``HVACMode.AUTO`` — that
        would hand control to the unit's own changeover logic (#5).

        In AUTO mode the wrapper maintains a sticky **committed direction**
        (HEAT or COOL) and just commands that direction.  No in-band
        hysteresis — the unit's own ±0.5 °C internal hysteresis around the
        asymmetric setpoint (HEAT=low, COOL=high-1) handles when to
        actually pump:

        - **HEAT** with setpoint=low: unit holds room at `[low, low+0.5]`.
          Idles when room ≥ low+0.5; heats when below.
        - **COOL** with setpoint=high-1: unit holds room at
          `[high-1, high-0.5]`.  Idles when room ≤ high-1; cools when
          above.

        Direction is changed by:

        - **Initial pick**: inside-vs-mid on first AUTO entry.
        - **Fast-flip**: inside past the wrong band edge → flip
          immediately (no dwell).
        - **Dwell-flip**: inside past `mid ± FLIP_MARGIN` against the
          committed direction for `FLIP_DWELL` seconds → flip.

        v3.0.x added a wrapper-level deliberate-OFF for the COOL-in-band
        case to fix a Midea min-frequency-floor symptom.  v4.0.0's
        asymmetric-setpoint design already prevents that symptom (with
        setpoint=high-1, the unit only actively cools above its own
        threshold, ~22.5 for [21, 23]).  Keeping deliberate-OFF on top
        of the corrected setpoint just added cycling overhead — empirical
        2026-05-02 comparison showed manual constant-cool used **~50×
        less power** than comfort_thermostat's deliberate-OFF cycling on a
        warm afternoon (1.17 kW avg vs 23 W avg).  Removed in v5.0.0.
        """
        if self._hvac_mode == HVACMode.OFF:
            return HVACMode.OFF
        if self._hvac_mode in (HVACMode.HEAT, HVACMode.COOL):
            return self._hvac_mode

        # AUTO mode – need an inside reading to make any decision.  Hold a
        # committed direction (e.g. restored after a restart); without one,
        # leave the device alone until a reading arrives.
        if self._current_temperature is None or math.isnan(self._current_temperature):
            return self._auto_mode

        inside = self._current_temperature
        low, high = self._active_range()
        mid = (low + high) / 2.0

        # Initial mode pick — inside-vs-midpoint, full stop.  Outside is
        # NOT consulted: empirically the outside sensor in this
        # deployment doesn't correlate with the building's thermodynamics
        # (solar gain, occupancy, internal sources dominate), and using
        # it caused the live HEAT-at-23 bug on 2026-04-26 where cool
        # outside drove a HEAT pick while the room sat at the band's
        # high edge.  FLIP_DWELL (30 min sustained excursion past
        # mid + FLIP_MARGIN) corrects any wrong pick.
        if self._auto_mode is None:
            self._auto_mode = HVACMode.HEAT if inside < mid else HVACMode.COOL
            self._pending_flip_since = None
            # fall through to the band-aware unit-command logic below

        # Fast-flip on band-edge violation: when the committed direction
        # is the *opposite* of what's needed AND the room is past the
        # band edge, flip without waiting out FLIP_DWELL — but only once the
        # violation has held for FAST_FLIP_CONFIRM, and no sooner than
        # MIN_CHANGEOVER_INTERVAL after the previous changeover (#3).  One
        # bad reading used to reverse the heat pump on the spot.
        #
        # The dwell timer (30 min sustained excursion past mid ± FLIP_MARGIN)
        # is sized for sensor jitter / natural drift around the midpoint.
        # That's the wrong filter for the case where committed=HEAT but
        # inside is already > high (or committed=COOL and inside < low):
        # there's no jitter explanation for that, only a wrong pick or
        # an external swing the dwell would take 30 min to correct.
        # During those 30 min the wrapper actively heats a hot room (or
        # cools a cold one), making the excursion worse.  Live bug
        # 2026-04-26 (PR #62 fixed the *initial* pick that caused it;
        # this is the belt-and-suspenders catch for any future scenario
        # that lands committed-direction at odds with the band).
        now = self._now()
        if (
            (self._auto_mode == HVACMode.HEAT and inside > high)
            or (self._auto_mode == HVACMode.COOL and inside < low)
        ):
            if self._fast_flip_since is None:
                self._fast_flip_since = now
            confirm_left = (
                FAST_FLIP_CONFIRM - (now - self._fast_flip_since).total_seconds()
            )
            wait = max(confirm_left, self._changeover_wait(now))
            if wait <= 0:
                self._flip_direction(now)
            else:
                self._schedule_flip_recheck(wait)
        elif self._fast_flip_since is not None:
            # Back on the right side of the edge: the violation was a blip.
            self._fast_flip_since = None
            self._cancel_flip_recheck()

        # Sticky direction-flip evaluation (unchanged from v2.0.0).  Wrong-
        # side / right-side bands have a deadzone in between (mid ± FLIP_MARGIN)
        # where the timer keeps running but is not reset, so sensor jitter
        # near the margin doesn't repeatedly cancel an in-progress flip.
        # This handles the in-band drift case the fast-flip above doesn't.
        if self._auto_mode == HVACMode.COOL:
            wrong_side = inside <= mid - FLIP_MARGIN
            right_side = inside >= mid
        else:  # HEAT
            wrong_side = inside >= mid + FLIP_MARGIN
            right_side = inside <= mid

        if wrong_side:
            if self._pending_flip_since is None:
                self._pending_flip_since = now
            elif (
                (now - self._pending_flip_since).total_seconds() >= FLIP_DWELL
                and self._changeover_wait(now) <= 0
            ):
                self._flip_direction(now)
        elif right_side:
            self._pending_flip_since = None

        # Unit command — just the committed direction.  Wrapper does NOT
        # add in-band hysteresis on top of the unit; the unit's own
        # setpoint logic (HEAT setpoint=low, COOL setpoint=high-1) keeps
        # the room near the band edge that matches the committed
        # direction without the wrapper's intervention.
        return self._auto_mode

    def _flip_direction(self, now: datetime.datetime) -> None:
        """Commit the opposite AUTO direction and start the changeover clock."""
        self._auto_mode = (
            HVACMode.COOL if self._auto_mode == HVACMode.HEAT else HVACMode.HEAT
        )
        self._pending_flip_since = None
        self._fast_flip_since = None
        self._last_changeover_at = now
        self._cancel_flip_recheck()

    def _changeover_wait(self, now: datetime.datetime) -> float:
        """Seconds until MIN_CHANGEOVER_INTERVAL allows another changeover."""
        if self._last_changeover_at is None:
            return 0.0
        elapsed = (now - self._last_changeover_at).total_seconds()
        return max(0.0, MIN_CHANGEOVER_INTERVAL - elapsed)

    def _schedule_flip_recheck(self, delay: float) -> None:
        """Re-run the AUTO decision after ``delay`` seconds, replacing any
        pending re-check."""
        self._cancel_flip_recheck()
        self._flip_recheck_unsub = async_call_later(
            self.hass, delay, self._async_flip_recheck
        )

    def _cancel_flip_recheck(self) -> None:
        if self._flip_recheck_unsub is not None:
            self._flip_recheck_unsub()
            self._flip_recheck_unsub = None

    @callback
    def _async_flip_recheck(self, _now: datetime.datetime | None) -> None:
        self._flip_recheck_unsub = None
        if self._hvac_mode == HVACMode.AUTO and not self._updating_from_control:
            self.hass.async_create_task(self._async_sync_real_climate())

    # ------------------------------------------------------------------
    # Drift correction (#7)
    # ------------------------------------------------------------------

    @staticmethod
    def _is_available(state: State | None) -> bool:
        return state is not None and state.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
            None,
            "",
        )

    def _device_drifted(self, state: State) -> bool:
        """Return True when the real device doesn't show our last command."""
        if state.state != self._unit_command.value:
            return True
        if self._unit_setpoint is None:
            return False
        try:
            current = float(state.attributes.get("temperature"))
        except (TypeError, ValueError):
            return False
        return abs(current - self._unit_setpoint) >= 0.5

    def _check_drift(self, state: State, came_back: bool) -> None:
        """Re-send our command when the real device stops matching it.

        A device returning from unavailable (power blip) comes back in its
        own default state, so it is re-synced at once.  Any other mismatch
        gets COMMAND_GRACE_SECONDS to settle first — events from a command
        we just sent arrive mid-transition — and is re-sent only if it
        persists, at most MAX_DRIFT_RESENDS times in a row.  A mode someone
        else switched the device to after it had matched our command is
        left running for MIN_CHANGEOVER_INTERVAL first, so a remote can't
        make the wrapper short-cycle the unit.  Nothing is enforced before
        the wrapper has commanded anything.
        """
        if self._unit_command is None:
            return
        if came_back:
            self._cancel_drift_recheck()
            self._drift_resends = 0
            self._device_matched = False
            self._foreign_mode = None
            if not self._updating_from_control:
                self.hass.async_create_task(self._async_sync_real_climate())
            return
        if state.state == self._unit_command.value:
            self._device_matched = True
            self._foreign_mode = None
        elif self._device_matched and state.state != self._foreign_mode:
            self._foreign_mode = state.state
            self._foreign_since = self._now()
        if not self._device_drifted(state):
            self._cancel_drift_recheck()
            self._drift_resends = 0
            return
        # Keep an already-pending re-check rather than pushing it out on
        # every event of the grace window; it re-reads the wait when it runs.
        if (
            self._drift_recheck_unsub is None
            and self._drift_resends < MAX_DRIFT_RESENDS
        ):
            self._drift_recheck_unsub = async_call_later(
                self.hass,
                max(COMMAND_GRACE_SECONDS, self._foreign_mode_wait()),
                self._async_drift_recheck,
            )

    def _foreign_mode_wait(self) -> float:
        """Seconds until a mode someone else set may be undone."""
        if self._foreign_mode is None or self._foreign_since is None:
            return 0.0
        elapsed = (self._now() - self._foreign_since).total_seconds()
        return max(0.0, MIN_CHANGEOVER_INTERVAL - elapsed)

    def _cancel_drift_recheck(self) -> None:
        if self._drift_recheck_unsub is not None:
            self._drift_recheck_unsub()
            self._drift_recheck_unsub = None

    @callback
    def _async_drift_recheck(self, _now: datetime.datetime | None) -> None:
        self._drift_recheck_unsub = None
        if self._updating_from_control or self._unit_command is None:
            return
        state = self.hass.states.get(self._real_climate_id)
        if not self._is_available(state) or not self._device_drifted(state):
            return
        wait = self._foreign_mode_wait()
        if wait > 0:
            # The device changed mode again during the wait.
            self._drift_recheck_unsub = async_call_later(
                self.hass, wait, self._async_drift_recheck
            )
            return
        self._drift_resends += 1
        if self._drift_resends == MAX_DRIFT_RESENDS:
            _LOGGER.warning(
                "%s: %s still shows %s / %s after %d re-sends of %s / %s; "
                "giving up until it matches or the command changes",
                self.name,
                self._real_climate_id,
                state.state,
                state.attributes.get("temperature"),
                MAX_DRIFT_RESENDS,
                self._unit_command.value,
                self._unit_setpoint,
            )
        self.hass.async_create_task(self._async_sync_real_climate())

    # ------------------------------------------------------------------
    # Real-climate synchronisation
    # ------------------------------------------------------------------

    async def _async_sync_real_climate(self) -> None:
        """Push the desired mode and setpoint to the real climate device.

        Not gated on ``_updating_from_control``: the control methods set
        that flag and then call this, so gating here dropped every user
        change (#27).  The flag is checked by the sensor callbacks instead,
        before they schedule a sync, which is what keeps the two paths from
        overlapping.
        """
        real_mode = self._desired_real_mode()
        if real_mode is None:
            # AUTO with nothing to decide on yet; reported as
            # auto_waiting_for_reading.  The next reading re-runs this.
            return
        # Track command changes for desync detection (only when the
        # command actually changes — re-issuing the same command
        # shouldn't reset the grace window).
        command_changed = real_mode != self._unit_command
        if command_changed:
            self._unit_command_at = self._now()
            self._drift_resends = 0
            self._device_matched = False
            self._foreign_mode = None
        # Record the wrapper's intent so hvac_action can surface IDLE for
        # deliberate-OFF (AUTO + OFF inside the comfort band) without
        # re-running _desired_real_mode (which has timer side-effects).
        self._unit_command = real_mode

        real_state = self.hass.states.get(self._real_climate_id)
        if real_state is None:
            return

        current_mode = real_state.state
        if current_mode == real_mode.value:
            self._device_matched = True
        elif (
            not command_changed
            and not self._updating_from_control
            and current_mode == self._foreign_mode
            and self._foreign_mode_wait() > 0
        ):
            # Someone else switched the device to this mode; the drift
            # re-check undoes it once it has run long enough.  A sensor
            # reading must not undo it sooner.  The user's own changes
            # (control methods) still go through.
            return

        # OFF reaches here in two cases now: (a) the user commanded smart
        # climate OFF, and (b) AUTO is in deliberate-OFF — the wrapper
        # provides the idle state Midea inverters can't (their HEAT/COOL
        # modes hold a min-frequency floor instead of truly idling).
        # Forward the OFF; only send the command if the real device isn't
        # already off.
        if real_mode == HVACMode.OFF:
            self._unit_setpoint = None
            if current_mode != HVACMode.OFF.value:
                await self.hass.services.async_call(
                    "climate",
                    "set_hvac_mode",
                    {"entity_id": self._real_climate_id, "hvac_mode": HVACMode.OFF.value},
                    blocking=False,
                )
            return

        # In AUTO mode, the setpoint sent to the real device is biased
        # toward the band edge that matches the committed direction —
        # NOT the band midpoint, NOT the band edge itself.  The Midea
        # unit's actual hysteresis is asymmetric: it holds the room
        # **at or slightly above setpoint** in BOTH modes (~setpoint to
        # setpoint + 0.3-0.5).  Live observation 2026-04-29 with COOL
        # setpoint=23 showed room sitting at 23.2-23.3 — *above* the
        # band high edge (23).  v4.0.0's `setpoint=high` formula was
        # therefore wrong: it pushed the room out of the comfort band.
        #
        # Corrected formulas (since v4.0.x):
        #
        #   HEAT setpoint = low      → unit holds room at [low, low+0.5]
        #   COOL setpoint = high - 1 → unit holds room at [high-1, high-0.5]
        #
        # For default home preset (21-23):
        #   HEAT setpoint=21 → room ~21..21.5  (in band, near low)
        #   COOL setpoint=22 → room ~22..22.5  (in band, mid)
        #   Intermediate band (no active pumping): 21.5..22
        #
        # Why "-1" for COOL but "+0" for HEAT: the unit's overshoot is
        # always positive (above setpoint), so HEAT setpoint=low gives
        # room at low+ε (above floor, OK) while COOL setpoint=high
        # would give room at high+ε (above ceiling, NOT OK).  Subtract
        # 1 °C from COOL's setpoint to leave room for the overshoot.
        #
        # The mid-targeting that v2.0.0 used was actively wasteful in
        # sunny PNW climates: HEAT mode at mid=22 would heat a 21.4 °C
        # room to 22 even though 21.4 is well within the comfort band.
        # Diagnosed empirically from 48 h of v3.1.x data showing two
        # 64-min daily HEAT pulses initiated at inside ~21.45 °C.
        # Band-edge setpoints fix this by leveraging the unit's own
        # setpoint logic as defense in depth: even if the wrapper
        # commits HEAT incorrectly, the unit refuses to actively pump
        # heat unless the room is genuinely below the floor.
        low: float | None = None
        high: float | None = None
        if self._hvac_mode == HVACMode.AUTO:
            low, high = self._active_range()
            if real_mode == HVACMode.HEAT:
                target_temp = float(low)
            elif real_mode == HVACMode.COOL:
                target_temp = float(high) - 1.0
            else:
                # OFF — value is irrelevant (set_hvac_mode=off path); use
                # mid as a neutral fallback.
                target_temp = (low + high) / 2.0
        else:
            target_temp = self._target_temperature

        setpoint = self._device_setpoint(target_temp, real_mode, low, high)
        self._unit_setpoint = setpoint

        # The real device's attributes and its set_temperature service both
        # use the system unit, as does ``setpoint``.
        current_temp = real_state.attributes.get("temperature")

        # Half a whole-degree step, so the next sensor update doesn't
        # trigger a spurious resend when the device is already holding the
        # exact value we sent.
        mode_changed = current_mode != real_mode.value
        temp_changed = (
            current_temp is None or abs(float(current_temp) - setpoint) >= 0.5
        )

        if not (mode_changed or temp_changed):
            return

        service_data: dict[str, Any] = {
            "entity_id": self._real_climate_id,
            "temperature": setpoint,
            "hvac_mode": real_mode.value,
        }
        await self.hass.services.async_call(
            "climate",
            "set_temperature",
            service_data,
            blocking=False,
        )

    # ------------------------------------------------------------------
    # ClimateEntity control methods
    # ------------------------------------------------------------------

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        self._updating_from_control = True
        try:
            old_mode = self._hvac_mode
            self._hvac_mode = hvac_mode

            # Leaving AUTO clears the sticky AUTO state so the next AUTO entry
            # picks a fresh mode from current temperatures rather than reusing
            # a stale commitment.
            if hvac_mode != HVACMode.AUTO:
                self._auto_mode = None
                self._pending_flip_since = None
                self._fast_flip_since = None
                self._cancel_flip_recheck()

            if hvac_mode == HVACMode.OFF:
                await self.hass.services.async_call(
                    "climate",
                    "set_hvac_mode",
                    {"entity_id": self._real_climate_id, "hvac_mode": HVACMode.OFF.value},
                    blocking=False,
                )
            elif hvac_mode == HVACMode.AUTO:
                # Entering AUTO mode – reload the active preset's range
                if self._preset_mode != PRESET_NONE:
                    low, high = self._active_range()
                    self._target_temp_low = low
                    self._target_temp_high = high
                await self._async_sync_real_climate()
            else:
                # HEAT or COOL: use single target temperature
                if old_mode == HVACMode.AUTO:
                    # Carry the preset midpoint over as the single-point target
                    self._target_temperature = self._preset_midpoint()
                await self._async_sync_real_climate()

            self.async_write_ha_state()
        finally:
            # Always clear: a stuck flag would silently block every later
            # sensor-driven sync.
            self._updating_from_control = False

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the active preset, updating the temperature range accordingly.

        The active inside sensor changes with the preset (each preset can
        point at its own sensor — common rooms for Home, bedroom average
        for Sleep, whole-home for Away).  Seed ``_current_temperature``
        synchronously from the new sensor's last_state so the AUTO
        decision logic does not run one tick on a stale reading from
        the previous preset's sensor.
        """
        self._updating_from_control = True
        try:
            old_preset = self._preset_mode
            self._preset_mode = preset_mode

            # Re-seed current_temperature from the (possibly new) active sensor.
            # Cheap and idempotent when the sensor didn't actually change.
            if preset_mode != old_preset:
                self._sync_from_sensors()

            if preset_mode != PRESET_NONE:
                low, high = self._active_range()
                self._target_temp_low = low
                self._target_temp_high = high
                if self._hvac_mode == HVACMode.AUTO:
                    await self._async_sync_real_climate()

            self.async_write_ha_state()
        finally:
            self._updating_from_control = False

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature.

        In AUTO mode this accepts ``target_temp_low`` / ``target_temp_high``
        to update the comfort band.  In HEAT / COOL mode it accepts a single
        ``temperature`` value.  Either way the preset is cleared to NONE
        (manual mode) because the user is directly editing setpoints.
        """
        self._updating_from_control = True
        try:
            # Any manual temperature edit exits preset mode
            self._preset_mode = PRESET_NONE

            if ATTR_TARGET_TEMP_LOW in kwargs or ATTR_TARGET_TEMP_HIGH in kwargs:
                if ATTR_TARGET_TEMP_LOW in kwargs:
                    new_low = float(kwargs[ATTR_TARGET_TEMP_LOW])
                    self._target_temp_low = new_low
                if ATTR_TARGET_TEMP_HIGH in kwargs:
                    new_high = float(kwargs[ATTR_TARGET_TEMP_HIGH])
                    self._target_temp_high = new_high

                # Enforce minimum separation between low and high
                self._target_temp_low, self._target_temp_high = _widen_band(
                    self._target_temp_low,
                    self._target_temp_high,
                    keep_high=ATTR_TARGET_TEMP_HIGH in kwargs,
                )

                if self._hvac_mode == HVACMode.AUTO:
                    await self._async_sync_real_climate()

            elif ATTR_TEMPERATURE in kwargs:
                temp = float(kwargs[ATTR_TEMPERATURE])
                self._target_temperature = temp
                setpoint = self._device_setpoint(temp, self._hvac_mode)
                if self._hvac_mode in (HVACMode.HEAT, HVACMode.COOL):
                    # So drift correction (#7) expects the new value.
                    self._unit_setpoint = setpoint
                await self.hass.services.async_call(
                    "climate",
                    "set_temperature",
                    {
                        "entity_id": self._real_climate_id,
                        "temperature": setpoint,
                    },
                    blocking=False,
                )

            self.async_write_ha_state()
        finally:
            self._updating_from_control = False

    async def async_turn_on(self) -> None:
        """Turn on by entering AUTO mode."""
        await self.async_set_hvac_mode(HVACMode.AUTO)

    async def async_turn_off(self) -> None:
        """Turn off."""
        await self.async_set_hvac_mode(HVACMode.OFF)
