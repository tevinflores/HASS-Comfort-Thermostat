"""Constants for the Comfort Thermostat integration."""

DOMAIN = "comfort_thermostat"

# Configuration keys
CONF_REAL_CLIMATE = "real_climate"

# Inside-temperature sensors.  CONF_INSIDE_SENSOR is the *default / Home preset*
# sensor and also the fallback used when:
#   - the active preset has no dedicated sensor configured, or
#   - the active preset's sensor is unavailable / unknown, or
#   - no preset is active (PRESET_NONE, i.e. the user is manually driving
#     mode and setpoint).
# It stays under the key `inside_sensor` for backwards compatibility with
# existing config entries — older installs that only set this single sensor
# keep working unchanged.
CONF_INSIDE_SENSOR = "inside_sensor"
CONF_INSIDE_SENSOR_SLEEP = "inside_sensor_sleep"
CONF_INSIDE_SENSOR_AWAY = "inside_sensor_away"

CONF_OUTSIDE_SENSOR = "outside_sensor"

# Preset temperature range configuration keys
CONF_HOME_MIN = "home_min"
CONF_HOME_MAX = "home_max"
CONF_SLEEP_MIN = "sleep_min"
CONF_SLEEP_MAX = "sleep_max"
CONF_AWAY_MIN = "away_min"
CONF_AWAY_MAX = "away_max"

# Default preset temperatures (°C)
DEFAULT_HOME_MIN = 21.0
DEFAULT_HOME_MAX = 24.0
DEFAULT_SLEEP_MIN = 19.0
DEFAULT_SLEEP_MAX = 22.0
DEFAULT_AWAY_MIN = 18.0
DEFAULT_AWAY_MAX = 26.0

# Safety limits (°C), checked against the inside reading in every mode so a
# house left OFF can't freeze or overheat unnoticed (#12).  Reported in
# `problems` as below_safety_min / above_safety_max.
CONF_SAFETY_MIN = "safety_min"
CONF_SAFETY_MAX = "safety_max"
DEFAULT_SAFETY_MIN = 7.0
DEFAULT_SAFETY_MAX = 32.0

# Temperature constraints
MIN_TEMP = 10.0
MAX_TEMP = 35.0
TEMP_STEP = 0.5

# Minimum allowed difference between low and high setpoints.  Setpoints sent
# to the device are whole degrees and the unit holds the room up to ~0.5 °C
# *above* whatever it is given, so the band must leave room for both:
#   HEAT sends ceil(low):       low = 21.5 → 22, room 22–22.5, needs high ≥ low + 1.0
#   COOL sends floor(high - 1): high = 22.5 → 21, needs low ≤ 21, i.e. high ≥ low + 1.5
# 1.5 °C is the smallest width that keeps the room in band in both
# directions for every band on the TEMP_STEP grid (#6).
MIN_TEMP_DIFF = 1.5

# AUTO mode picks HEAT or COOL once and holds it, sending the real device an
# asymmetric setpoint (HEAT → low, COOL → high - 1) and leaving the
# (modulating) device to hold it.  Within the band, HEAT↔COOL flips only
# when the inside temperature has been continuously past the midpoint by
# FLIP_MARGIN for FLIP_DWELL seconds — i.e. the room is asking for the
# opposite mode, not just jittering across the boundary.  This is sized for
# inverter heat pumps where the cost of restarting the compressor far
# exceeds the energy of holding low modulation, and where short OFF cycles
# defeat the unit's own steady-state operation.
FLIP_MARGIN = 0.5
FLIP_DWELL = 1800  # 30 min

# Fast-flip (committed direction opposite to demand AND inside past the band
# edge) skips FLIP_DWELL, but the violation must still hold this long so one
# bad reading — e.g. a Z-Wave sensor re-initialising — can't reverse the heat
# pump.  Short next to the 30 min of wrong-direction running fast-flip exists
# to prevent, and the HEAT setpoint at `low` keeps the unit idle meanwhile.
FAST_FLIP_CONFIRM = 180  # 3 min

# Minimum spacing between AUTO's own HEAT↔COOL changeovers (fast or dwell),
# so the wrapper can't ping-pong the reversing valve.  The initial pick and
# the user's explicit mode changes are not counted (they only get the
# OFF_SETTLE pause, #11).
MIN_CHANGEOVER_INTERVAL = 600  # 10 min

# After the wrapper turns the unit OFF, HEAT/COOL isn't sent again until this
# has passed, so an automation or preset that toggles the mode quickly can't
# restart the compressor straight away (#31).  OFF itself is never delayed:
# AUTO never sends it, so every OFF is a user's or automation's request.
# Midea inverters have their own ~3 min restart delay; this is the backstop.
MIN_OFF_TIME = 300  # 5 min

# HEAT↔COOL goes through OFF for this long, so the compressor spins down and
# refrigerant pressures equalise before the reversing valve changes (#11).
# Applies to AUTO flips and the user's own changes alike, whenever the device
# is running the opposite mode.  An extra start ~1–2 times a day costs
# nothing measurable.
OFF_SETTLE = 60  # 1 min

# Inside readings outside this range (°C, after unit conversion) are treated
# as no reading at all: a failed sensor reporting -40 or 85 must not drive
# AUTO.  Reported in `problems` as inside_sensor_implausible:<value>.
INSIDE_TEMP_PLAUSIBLE_MIN = 0.0
INSIDE_TEMP_PLAUSIBLE_MAX = 45.0

# NOTE: COOL_RESTART_OFFSET (used in v3.0.x – v4.0.x for in-band COOL
# hysteresis driven by the wrapper) was removed in v5.0.0.  Empirical
# 2026-05-02 data showed the wrapper's deliberate-OFF cycling used
# ~50× more power than just letting the unit handle its own hysteresis
# via the asymmetric setpoints (HEAT=low, COOL=high-1).  The
# Midea unit's own ±0.5 °C internal hysteresis around setpoint keeps
# the room near the band edge that matches the committed direction;
# the wrapper just commits the direction.

# Problem-detection thresholds.  Surfaced as the wrapper's `problems`
# attribute (a list of detected issues, empty when healthy).  Sized
# generously so transient blips don't fire false alarms; tune down if
# false-negatives matter more than false-alarms in a given deployment.
OUT_OF_BAND_ALERT_MINUTES   = 30   # sustained outside [low, high] in AUTO
SHORT_CYCLE_THRESHOLD_PER_H = 6    # compressor starts/hour above this is "too much"
SENSOR_STALE_MINUTES        = 15   # no inside-temp update for this long

# Command-desync detection: how long we wait for the real device to
# settle into the wrapper's last commanded state before flagging the
# divergence as a problem.  60 s is generous — `set_hvac_mode` is
# fire-and-forget (`blocking=False`), and the real device's
# soft-start ramp + state-event propagation takes a few seconds even
# in the happy path.
COMMAND_GRACE_SECONDS       = 60

# When the real device still doesn't match the wrapper's command after
# COMMAND_GRACE_SECONDS (power blip, IR remote, dropped command), the
# command is re-sent — at most this many times in a row, so a device that
# refuses a mode isn't spammed.  The count resets once the device matches
# or the wrapper's command changes; command_desync stays in `problems` (#7).
MAX_DRIFT_RESENDS           = 3
