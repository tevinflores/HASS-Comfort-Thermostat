# Changelog

## [1.2.0](https://github.com/tevinflores/HASS-Comfort-Thermostat/compare/v1.1.4...v1.2.0) (2026-10-29)


### Miscellaneous Chores

* release 1.2.0 ([8c10906](https://github.com/tevinflores/HASS-Comfort-Thermostat/commit/8c10906b55b988130bca41a098791b2ab241aa81))

## [1.1.4](https://github.com/tevinflores/HASS-Comfort-Thermostat/compare/v1.1.3...v1.1.4) (2026-10-29)


### Bug Fixes

* **climate:** count real compressor starts for short_cycle ([#44](https://github.com/tevinflores/HASS-Comfort-Thermostat/issues/44)) ([2a462a2](https://github.com/tevinflores/HASS-Comfort-Thermostat/commit/2a462a21beeba2fe264613d18ce6371955f6acf9))

## [1.1.3](https://github.com/tevinflores/HASS-Comfort-Thermostat/compare/v1.1.2...v1.1.3) (2026-10-29)


### Bug Fixes

* **climate:** let a remote mode change run before undoing it ([b8f2e31](https://github.com/tevinflores/HASS-Comfort-Thermostat/commit/b8f2e3197a0b3d3769b203da52af0f93387cef74))
* **climate:** re-send commands when the real device drifts ([f9f2124](https://github.com/tevinflores/HASS-Comfort-Thermostat/commit/f9f2124b121ffcf3e6c7b8ff1f21b6b4d3564890)), closes [#8](https://github.com/tevinflores/HASS-Comfort-Thermostat/issues/8)

## [1.1.2](https://github.com/tevinflores/HASS-Comfort-Thermostat/compare/v1.1.1...v1.1.2) (2026-10-28)


### Bug Fixes

* **climate:** round device setpoints to whole degrees in the system unit ([3884f9f](https://github.com/tevinflores/HASS-Comfort-Thermostat/commit/3884f9ff8108b9dcdd9f61a1c81f5d7e5118cf2a)), closes [#7](https://github.com/tevinflores/HASS-Comfort-Thermostat/issues/7)

## [1.1.1](https://github.com/tevinflores/HASS-Comfort-Thermostat/compare/v1.1.0...v1.1.1) (2026-10-27)


### Bug Fixes

* **climate:** raise minimum comfort-band width to 1.5 °C ([#6](https://github.com/tevinflores/HASS-Comfort-Thermostat/issues/6)) ([0c48324](https://github.com/tevinflores/HASS-Comfort-Thermostat/commit/0c48324a460569cf9c7e58a090c70bbdb3ad91f8))

## [1.1.0](https://github.com/tevinflores/HASS-Comfort-Thermostat/compare/v1.0.3...v1.1.0) (2026-10-27)


### Miscellaneous Chores

* release 1.1.0 ([e6b19aa](https://github.com/tevinflores/HASS-Comfort-Thermostat/commit/e6b19aa3bc4bfb31d348a2ae8f68f61c1cad83a9))

## [1.0.3](https://github.com/tevinflores/HASS-Comfort-Thermostat/compare/v1.0.2...v1.0.3) (2026-10-27)


### Bug Fixes

* **climate:** confirm fast-flips and space AUTO changeovers ([63a5774](https://github.com/tevinflores/HASS-Comfort-Thermostat/commit/63a57747346e9f400dca9ee0e3ce4140806edcee)), closes [#3](https://github.com/tevinflores/HASS-Comfort-Thermostat/issues/3)

## [1.0.2](https://github.com/tevinflores/HASS-Comfort-Thermostat/compare/v1.0.1...v1.0.2) (2026-10-27)


### Bug Fixes

* **climate:** never send the unit its own AUTO mode ([cc0ec8b](https://github.com/tevinflores/HASS-Comfort-Thermostat/commit/cc0ec8b247048b15c75aa91e67fcd3555b443940)), closes [#5](https://github.com/tevinflores/HASS-Comfort-Thermostat/issues/5)

## [1.0.1](https://github.com/tevinflores/HASS-Comfort-Thermostat/compare/v1.0.0...v1.0.1) (2026-10-27)


### Bug Fixes

* **climate:** keep AUTO switching heat/cool after a manual range edit ([5bbe20e](https://github.com/tevinflores/HASS-Comfort-Thermostat/commit/5bbe20eedc49e46a8dd7b87d3d16b77f7dd41376)), closes [#2](https://github.com/tevinflores/HASS-Comfort-Thermostat/issues/2)

## [1.0.0](https://github.com/tevinflores/HASS-Comfort-Thermostat/compare/45cc397a5cb5d4b5ccb5d782a525c30e2c99bde5...v1.0.0) (2026-10-26)


### ⚠ BREAKING CHANGES

* the integration domain changed from smart_climate to comfort_thermostat. Existing installs must add Comfort Thermostat as a new integration; settings and entity ids do not carry over.

### Features

* rename to Comfort Thermostat ([a6d9108](https://github.com/tevinflores/HASS-Comfort-Thermostat/commit/a6d9108149a999bada0c0fdefea1aaf8e6f9b99f))


### Bug Fixes

* **climate:** enhance Fahrenheit support with proper temperature conversion and display ([40c2fa6](https://github.com/tevinflores/HASS-Comfort-Thermostat/commit/40c2fa603fcb06a1be268d29691f13ae2edd6e84))
* **climate:** ensure proper temperature conversion for Fahrenheit systems ([fe6bfac](https://github.com/tevinflores/HASS-Comfort-Thermostat/commit/fe6bfac947a9c4150143d61fa457a6ab46caa8d9))
* **climate:** improve Fahrenheit support by ensuring proper temperature conversions ([7db2040](https://github.com/tevinflores/HASS-Comfort-Thermostat/commit/7db2040bf6470731e5a6e9d02746932f0dfd63c3))

## [6.0.2](https://github.com/HomeOps/HASS-Smart-Climate/compare/v6.0.1...v6.0.2) (2026-08-06)


### Bug Fixes

* **climate:** don't abort setup restoring a non-AUTO state ([#82](https://github.com/HomeOps/HASS-Smart-Climate/issues/82)) ([5df8f8e](https://github.com/HomeOps/HASS-Smart-Climate/commit/5df8f8ee577e472f468ac369f41f4f130091c54d))

## [6.0.1](https://github.com/HomeOps/HASS-Smart-Climate/compare/v6.0.0...v6.0.1) (2026-05-25)


### Bug Fixes

* **config_flow:** expose per-preset sensors in options flow ([#80](https://github.com/HomeOps/HASS-Smart-Climate/issues/80)) ([1b221c9](https://github.com/HomeOps/HASS-Smart-Climate/commit/1b221c99607a67a8ac03799bd01d9cb533f2765e))

## [6.0.0](https://github.com/HomeOps/HASS-Smart-Climate/compare/v5.0.1...v6.0.0) (2026-05-25)


### ⚠ BREAKING CHANGES

* CONF_INSIDE_SENSOR's semantics change from "the one inside sensor for every preset" to "Home preset + fallback + manual mode." Existing config entries are valid as-is, but tooling or scripts that assumed the single-sensor model should be updated to consider the new per-preset sensors.

### Features

* smart zones — per-preset inside sensors ([#78](https://github.com/HomeOps/HASS-Smart-Climate/issues/78)) ([b025e45](https://github.com/HomeOps/HASS-Smart-Climate/commit/b025e4501f77e383ad8a83bac2870a045c316e21))

## [5.0.1](https://github.com/HomeOps/HASS-Smart-Climate/compare/v5.0.0...v5.0.1) (2026-05-15)


### Bug Fixes

* publish smart_climate current temperature with hundredths precision ([#76](https://github.com/HomeOps/HASS-Smart-Climate/issues/76)) ([a78b028](https://github.com/HomeOps/HASS-Smart-Climate/commit/a78b02801c934e98953e0c20899061f709356cfb))

## [5.0.0](https://github.com/HomeOps/HASS-Smart-Climate/compare/v4.0.1...v5.0.0) (2026-05-03)


### ⚠ BREAKING CHANGES

* AUTO can no longer return OFF.  v3.0.0''s "AUTO commands OFF in band" contract is undone.  Downstream automations that watched for hvac_mode=off on the wrapped device during AUTO must update — that mode change no longer happens. hvac_action no longer surfaces IDLE either (mirrors the unit directly now).

### Features

* remove deliberate-OFF design — let unit handle its own hysteresis ([#73](https://github.com/HomeOps/HASS-Smart-Climate/issues/73)) ([f161126](https://github.com/HomeOps/HASS-Smart-Climate/commit/f1611267e0e6b1da58ce151ee0be5ddf7c4f09e1))

## [4.0.1](https://github.com/HomeOps/HASS-Smart-Climate/compare/v4.0.0...v4.0.1) (2026-04-30)


### Bug Fixes

* COOL setpoint back to high - 1 (v4.0.0 setpoint=high was unsafe) ([#71](https://github.com/HomeOps/HASS-Smart-Climate/issues/71)) ([5cd6554](https://github.com/HomeOps/HASS-Smart-Climate/commit/5cd6554bd2cd050162a0d811638a3a2c6b5df232))

## [4.0.0](https://github.com/HomeOps/HASS-Smart-Climate/compare/v3.2.0...v4.0.0) (2026-04-29)


### ⚠ BREAKING CHANGES

* the AUTO setpoint sent to the wrapped device no longer equals the band midpoint.  Downstream automations or template sensors that assumed `state_attr(real_climate, "temperature") == midpoint(preset)` need to update.  This invariant was documented in CLAUDE.md and is inverted now.

### Features

* asymmetric setpoints — HEAT to low, COOL to high (intermediate band) ([#69](https://github.com/HomeOps/HASS-Smart-Climate/issues/69)) ([091db20](https://github.com/HomeOps/HASS-Smart-Climate/commit/091db20cb6292d9d2b3883654f750afd3b510789))

## [3.2.0](https://github.com/HomeOps/HASS-Smart-Climate/compare/v3.1.0...v3.2.0) (2026-04-26)


### Features

* persist AUTO state machine + add command-desync detection ([#67](https://github.com/HomeOps/HASS-Smart-Climate/issues/67)) ([2eb32dc](https://github.com/HomeOps/HASS-Smart-Climate/commit/2eb32dc333a697a1a0aee55a5cae3c85d9ad1379))

## [3.1.0](https://github.com/HomeOps/HASS-Smart-Climate/compare/v3.0.2...v3.1.0) (2026-04-26)


### Features

* fast-flip on band-edge violation + problems attribute ([#64](https://github.com/HomeOps/HASS-Smart-Climate/issues/64)) ([e7f4829](https://github.com/HomeOps/HASS-Smart-Climate/commit/e7f482912099a18cca5a0c7344a2b3acf202ab78))

## [3.0.2](https://github.com/HomeOps/HASS-Smart-Climate/compare/v3.0.1...v3.0.2) (2026-04-26)


### Bug Fixes

* ignore outside sensor in AUTO initial pick ([#62](https://github.com/HomeOps/HASS-Smart-Climate/issues/62)) ([b999453](https://github.com/HomeOps/HASS-Smart-Climate/commit/b999453e8e9b43096cb066caf71036697753885b))

## [3.0.1](https://github.com/HomeOps/HASS-Smart-Climate/compare/v3.0.0...v3.0.1) (2026-04-26)


### Bug Fixes

* add in-band COOL hysteresis (high → mid pull) ([#60](https://github.com/HomeOps/HASS-Smart-Climate/issues/60)) ([a87594a](https://github.com/HomeOps/HASS-Smart-Climate/commit/a87594a0e5cedfa4e843506a7c818ff891629312))

## [3.0.0](https://github.com/HomeOps/HASS-Smart-Climate/compare/v2.0.0...v3.0.0) (2026-04-26)


### ⚠ BREAKING CHANGES

* AUTO mode now commands the real device OFF when the current temperature is inside the comfort band. Downstream automations that assumed AUTO would never produce hvac_mode='off' on the wrapped entity must be updated.

### Features

* command OFF in AUTO+COOL when current is in band ([#58](https://github.com/HomeOps/HASS-Smart-Climate/issues/58)) ([e3f7412](https://github.com/HomeOps/HASS-Smart-Climate/commit/e3f7412a30d7bf576b9c6691fcaaa8433f3f5e8a))

## [2.0.0](https://github.com/HomeOps/HASS-Smart-Climate/compare/v1.0.3...v2.0.0) (2026-04-25)


### ⚠ BREAKING CHANGES

* AUTO no longer turns the real device OFF when inside is within the comfort band.  Users who relied on the wrapper to OFF their real device must switch smart_climate to OFF mode explicitly. INSIDE_DEADBAND constant removed; FLIP_MARGIN and FLIP_DWELL added.

### Features

* sticky AUTO mode for inverter heat pumps; never command OFF ([#54](https://github.com/HomeOps/HASS-Smart-Climate/issues/54)) ([d9a7f25](https://github.com/HomeOps/HASS-Smart-Climate/commit/d9a7f25b0a98a6e795fddc654407f3bd011319a2))

## [1.0.3](https://github.com/HomeOps/HASS-Smart-Climate/compare/v1.0.2...v1.0.3) (2026-04-20)


### Bug Fixes

* return OFF in-band to stop overnight heat/cool cycling ([#52](https://github.com/HomeOps/HASS-Smart-Climate/issues/52)) ([38cda4f](https://github.com/HomeOps/HASS-Smart-Climate/commit/38cda4f75b909b5d9808335fc8b82dc2154c30eb))

## [1.0.2](https://github.com/HomeOps/HASS-Smart-Climate/compare/v1.0.1...v1.0.2) (2026-04-20)


### Bug Fixes

* hysteresis on AUTO mode-commit edge to stop real-device flapping ([#50](https://github.com/HomeOps/HASS-Smart-Climate/issues/50)) ([9137129](https://github.com/HomeOps/HASS-Smart-Climate/commit/913712957694da286ee3085f4032baa2bed7bd19))

## [1.0.1](https://github.com/HomeOps/HASS-Smart-Climate/compare/v1.0.0...v1.0.1) (2026-04-20)


### Bug Fixes

* always send integer setpoint to real thermostat ([#46](https://github.com/HomeOps/HASS-Smart-Climate/issues/46)) ([#47](https://github.com/HomeOps/HASS-Smart-Climate/issues/47)) ([efe6a46](https://github.com/HomeOps/HASS-Smart-Climate/commit/efe6a466890452517074ef1d7cbf49cd5bdb8ad8))

## [1.0.0](https://github.com/HomeOps/HASS-Smart-Climate/compare/v0.2.1...v1.0.0) (2026-04-19)


### ⚠ BREAKING CHANGES

* Users whose wrapped climate device has a physical remote or knob will lose the automatic "drop out of preset when user overrides setpoint on the device" behavior. If that matters in your deployment, re-introduce the behavior explicitly (e.g. via an Automation on the real device''s state) rather than relying on implicit coupling.

### Code Refactoring

* make real climate a pure slave of smart climate ([#43](https://github.com/HomeOps/HASS-Smart-Climate/issues/43)) ([#44](https://github.com/HomeOps/HASS-Smart-Climate/issues/44)) ([e60d911](https://github.com/HomeOps/HASS-Smart-Climate/commit/e60d9114482a4ede34dc79e533ce2b4c3d0ea3cd))

## [0.2.1](https://github.com/HomeOps/HASS-Smart-Climate/compare/v0.2.0...v0.2.1) (2026-04-19)


### Bug Fixes

* keep preset when AUTO turns real device off ([#40](https://github.com/HomeOps/HASS-Smart-Climate/issues/40)) ([#41](https://github.com/HomeOps/HASS-Smart-Climate/issues/41)) ([8491a8a](https://github.com/HomeOps/HASS-Smart-Climate/commit/8491a8a5d2e5894880debfc4fbcee61879a375c6))

## [0.2.0](https://github.com/HomeOps/HASS-Smart-Climate/compare/v0.1.1...v0.2.0) (2026-04-18)


### Features

* turn off HVAC after 15 min stable in comfort band ([#38](https://github.com/HomeOps/HASS-Smart-Climate/issues/38)) ([dbab246](https://github.com/HomeOps/HASS-Smart-Climate/commit/dbab24607e94b767c907072fa851d7e8d4042a28))

## [0.1.1](https://github.com/HomeOps/HASS-Smart-Climate/compare/v0.1.0...v0.1.1) (2026-04-16)


### Bug Fixes

* use outside sensor to avoid excessive off/heat/cool cycling in comfort band ([#35](https://github.com/HomeOps/HASS-Smart-Climate/issues/35)) ([7aaa094](https://github.com/HomeOps/HASS-Smart-Climate/commit/7aaa0940b88bfd2a27bc5e04f37b2ab981eab871))

## [0.1.0](https://github.com/HomeOps/HASS-Smart-Climate/compare/v0.0.10...v0.1.0) (2026-04-14)


### Features

* turn off real climate when in-band; fix heat activation at low setpoint ([#32](https://github.com/HomeOps/HASS-Smart-Climate/issues/32)) ([e5d50dc](https://github.com/HomeOps/HASS-Smart-Climate/commit/e5d50dcf7a12ceba954e1229d774d9140e5a1099))

## [0.0.10](https://github.com/HomeOps/HASS-Smart-Climate/compare/v0.0.9...v0.0.10) (2026-04-13)


### Bug Fixes

* restore preset and sync real climate device on HA restart ([#29](https://github.com/HomeOps/HASS-Smart-Climate/issues/29)) ([a817bf4](https://github.com/HomeOps/HASS-Smart-Climate/commit/a817bf478772bc0b4caf24b33fd9761c39910970))

## [0.0.9](https://github.com/HomeOps/HASS-Smart-Climate/compare/v0.0.8...v0.0.9) (2026-04-13)


### Bug Fixes

* engage cooling at high - deadband instead of above high setpoint ([#26](https://github.com/HomeOps/HASS-Smart-Climate/issues/26)) ([e5dc4af](https://github.com/HomeOps/HASS-Smart-Climate/commit/e5dc4afd7ce15e2b072e09488724cf7ac2156400))

## [0.0.8](https://github.com/HomeOps/HASS-Smart-Climate/compare/v0.0.7...v0.0.8) (2026-04-09)


### Bug Fixes

* cool to `high - 1` to prevent integer-device upper-band overshoot ([#23](https://github.com/HomeOps/HASS-Smart-Climate/issues/23)) ([1bf6679](https://github.com/HomeOps/HASS-Smart-Climate/commit/1bf667936a58f506b62e322a87dd710f25a05296))

## [0.0.7](https://github.com/HomeOps/HASS-Smart-Climate/compare/v0.0.6...v0.0.7) (2026-04-08)


### Bug Fixes

* Return range midpoint as `temperature` in AUTO mode instead of null ([#16](https://github.com/HomeOps/HASS-Smart-Climate/issues/16)) ([38edd75](https://github.com/HomeOps/HASS-Smart-Climate/commit/38edd754454ee6a49395e7af8e0329ceea9e219e))

## [0.0.6](https://github.com/HomeOps/HASS-Smart-Climate/compare/v0.0.5...v0.0.6) (2026-04-08)


### Bug Fixes

* auto-publish releases on merge and auto-label PRs via release-drafter ([#18](https://github.com/HomeOps/HASS-Smart-Climate/issues/18)) ([f0b07c8](https://github.com/HomeOps/HASS-Smart-Climate/commit/f0b07c848188d74b03a8111f855d8fbf38d570f3))
* sync .release-please-manifest.json to 0.0.5 to match actual manifest.json version ([#20](https://github.com/HomeOps/HASS-Smart-Climate/issues/20)) ([f932244](https://github.com/HomeOps/HASS-Smart-Climate/commit/f9322441d7cf5f04b8fa66daedcaa68639d16815))
