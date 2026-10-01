# ASV Firmware — Arduino IDE build

This is the **active** firmware. The PlatformIO project in `../firmware/` is kept
as a reference and is no longer the build target.

**Start here → [`../docs/ARDUINO_IDE_SETUP.md`](../docs/ARDUINO_IDE_SETUP.md)**

## Quick facts

| | |
|---|---|
| Board | ESP32 Dev Module / DOIT DEVKIT V1 |
| **Partition Scheme** | **`Minimal SPIFFS (1.9MB APP)`** — required, BLE won't fit otherwise |
| Serial | **921600 baud** |
| Libraries | `Adafruit SSD1306`, `Adafruit GFX` (no ADS1115 library needed) |
| Sample rate | 860 SPS, hardware-paced by the ADS1115 ALRT/RDY interrupt |
| Fallback | 500 SPS software-paced if the ALRT wire is absent (auto-detected) |
| Output | `timestamp_us,ch0_counts` CSV over USB, after the `s` command |

## Pin summary

| Signal | GPIO |
|---|---|
| I2C bus A — SDA / SCL (ADS1115 only) | 21 / 22 |
| I2C bus B — SDA / SCL (OLED only) | 25 / 26 |
| ADS1115 `ALRT` → conversion-ready IRQ | 27 |
| AD8232 `LO+` / `LO-` lead-off | 34 / 35 |

Everything configurable lives in **`ASV_Firmware/asv_config.h`**.

## Serial commands

`h` help · `t` self-test · `i` I2C scan · `m` live monitor · `n` noise floor ·
`s` start stream · `x` stop · `g` cycle gain · `o` toggle OLED · `r` reset counters · `?` status

## Why it's split this way

- **`asv_adc`** owns core 1 and a private I2C bus, so nothing else can perturb sample timing.
- **`asv_oled`** uses `Wire1`, so a 1 KB framebuffer push never blocks the ADC.
- **`asv_ble`** sends a 20 Hz status/preview packet, not the raw stream — BLE
  throughput can't carry 860 SPS reliably, and pretending otherwise would corrupt timing.
- **`asv_diag`** exists so a failure tells you *which wire* is wrong, not just "it didn't work".
