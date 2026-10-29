# HASS-Comfort-Thermostat

A HACS-compatible custom component for Home Assistant that turns any climate device into an **EcoBee-like smart thermostat** with comfort presets and automatic heat/cool switching.

## Features

- **Comfort Presets** – Home, Sleep, Away, and Manual modes with independently configurable temperature ranges (low/high setpoints).
- **Auto Heat/Cool Switching** – Sticky direction commitment with two-tier flip logic (3-min confirmed fast-flip on band-edge violations + 30-min dwell-flip for sustained excursions), with at least 10 minutes between changeovers.
- **Band-edge setpoints** – In AUTO the real device gets `low` when heating and `high - 1` when cooling, so the unit's own regulation keeps the room in band without the thermostat cycling it.  See [`docs/state-machine.md`](docs/state-machine.md).
- **Problem detection** – `problems` attribute lists detected issues (sensor unavailable / stale, sustained out-of-band, short-cycling, device not following commands) for dashboards and notifications.
- **State Restoration** – Thermostat state (mode, preset, setpoints) survives Home Assistant restarts.
- **HACS Compatible** – Install and update via the Home Assistant Community Store.
- **UI Configuration** – Set up via the Home Assistant Integrations UI; adjust preset temperatures via the Options flow.

## Installation

### Via HACS (recommended)

1. Open **HACS → Integrations**.
2. Click the three-dot menu (⋮) → **Custom repositories**.
3. Add `https://github.com/tevinflores/HASS-Comfort-Thermostat` with category **Integration**.
4. Find **Comfort Thermostat** in the HACS store and click **Download**.
5. Restart Home Assistant.

### Manual

1. Copy the `custom_components/comfort_thermostat/` folder into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

## Configuration

### Add the integration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Comfort Thermostat**.
3. Fill in the form:
   | Field | Required | Description |
   |-------|----------|-------------|
   | **Thermostat Name** | ✅ | Friendly name for the new thermostat entity |
   | **Climate Device** | ✅ | The real/dumb climate entity to control (e.g. `climate.heatpump`) |
   | **Inside Temperature Sensor** | ✅ | Sensor entity for the indoor temperature |
   | **Outside Temperature Sensor** | ❌ | Optional sensor — tracked for display and future use (free-cooling detection, forecast preconditioning).  No longer consulted for the AUTO direction pick (see [v3.0.2 changelog](CHANGELOG.md)). |

### Configure preset temperatures

After setup, click **Configure** on the integration card (or go to **Options**) to adjust the comfort temperature ranges for each preset:

| Preset | Default Range |
|--------|--------------|
| **Home** | 21 °C – 24 °C |
| **Sleep** | 19 °C – 22 °C |
| **Away** | 18 °C – 26 °C |

## How It Works

### AUTO mode

The thermostat maintains a sticky **direction commitment** (HEAT or COOL) that
flips on demand mismatch, and sends the real device that mode with a setpoint
at the matching edge of the comfort band.  It never turns the device OFF in
AUTO; the unit idles on its own when the room is at its setpoint.

- **Initial pick** when entering AUTO: `inside < midpoint → HEAT, otherwise COOL`.
- **HEAT committed** sends setpoint `low` (21 °C for a 21–23 band).  The unit
  holds the room at about `low` to `low + 0.5`.
- **COOL committed** sends setpoint `high - 1` (22 °C for a 21–23 band).  The
  unit overshoots above its setpoint, so this holds the room at about
  `high - 1` to `high - 0.5`, inside the band.
- Setpoints are sent in **whole degrees of your Home Assistant unit** (°C or
  °F), rounded toward the inside of the band.
- **Direction flips** on demand mismatch happen via two mechanisms: a
  **fast-flip** when inside has been past the wrong band edge for 3 minutes,
  and a 30-min **dwell-flip** for sustained excursions in band.  Changeovers
  are at least 10 minutes apart.
- **No reading, no decision.**  If the inside sensor is unavailable, AUTO
  keeps the current direction and command until a reading arrives.

📐 **See [`docs/state-machine.md`](docs/state-machine.md) for the full state
diagrams, decision flowchart, and design rationale.**

### Problem detection

The wrapper exposes a `problems` extra-state-attribute — a list of detected
issues (empty list `[]` when healthy).  Conditions checked: inside-sensor
unavailable / stale / implausible, real-device unavailable, sustained
out-of-band in AUTO, compressor short-cycling (more than 6 starts an hour),
and the real device not following the thermostat's command.  Use in
templates / dashboards:

```jinja
{% if state_attr('climate.comfort_thermostat', 'problems') %}
  ⚠ {{ state_attr('climate.comfort_thermostat', 'problems') | join('; ') }}
{% endif %}
```

### Manual mode (PRESET_NONE)

- The preset is cleared whenever the user directly adjusts setpoints.
- All temperature changes are forwarded directly to the real device.

### Compressor protection

After the thermostat turns the unit OFF, it waits at least 5 minutes before
starting heating or cooling again, so an automation or preset that toggles
the mode quickly can't restart the compressor straight away.  A held start
shows up in `problems` as `min_off_time_wait:<seconds>s` and is sent
automatically when the wait ends.  Turning OFF is never delayed.

Switching between heating and cooling (an AUTO changeover or your own
HEAT↔COOL change) turns the unit OFF for 1 minute first, so the compressor
spins down and the refrigerant pressures settle before the unit reverses.

### External changes

The thermostat is the only thing that should control the real device's mode
and setpoint.  Changes made elsewhere (a physical remote, another automation)
never change the thermostat's own mode, preset or range; the thermostat
puts the device back instead:

- **Device comes back after a power blip:** settings are re-sent right away.
- **Setpoint changed, or a command didn't land:** re-sent after 60 seconds if
  the difference is still there.
- **Mode changed on the device** (e.g. switched to COOL with the remote while
  the thermostat is heating, or turned on while the thermostat is OFF): that
  mode is left running for 10 minutes before it is undone, so fighting the
  remote can't short-cycle the compressor.

After 3 re-sends in a row the thermostat stops trying and reports
`command_desync` in `problems`.  To change the temperature, use the
thermostat, not the device.

## Credits

Comfort Thermostat is a fork of [HASS-Smart-Climate](https://github.com/HomeOps/HASS-Smart-Climate), created by Oscar Calvo ([@ocalvo](https://github.com/ocalvo)). The AUTO-mode design, the Midea unit research and every release up to 6.0.2 are his work. Thank you!

The upstream integration's domain was `smart_climate`; this fork uses `comfort_thermostat`, so the two can be installed side by side. Moving from Smart Climate means adding Comfort Thermostat as a new integration (settings don't carry over).

## Inspiration

The original integration is inspired by the [ESPHome-Midea-XYE `smart_climate` component](https://github.com/HomeOps/ESPHome-Midea-XYE), which implements the same EcoBee-like logic as an ESPHome external component for ESP8266/ESP32 devices.

## License

See [LICENSE](LICENSE) for details.
