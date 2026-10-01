# ASV — GPIO and I2C Reference

Authoritative pin map for the current firmware (`firmware_arduino/ASV_Firmware/`).

Everything here is defined in **`firmware_arduino/ASV_Firmware/asv_config.h`**.
Change pins there, then update this file — nowhere else.

---

## Pin assignment

### I2C bus A — ADS1115 only

Deliberately kept clear of every other device so an ADC read is never blocked.

| ESP32 GPIO | Role | Connects to |
|---|---|---|
| 21 | SDA | ADS1115 `SDA` |
| 22 | SCL | ADS1115 `SCL` |

**Speed: 400 kHz.** 100 kHz cannot sustain 860 SPS and is the wrong setting here.

### I2C bus B — SSD1306 OLED only (`Wire1`)

| ESP32 GPIO | Role | Connects to |
|---|---|---|
| 25 | SDA | OLED `SDA` |
| 26 | SCL | OLED `SCL` |

**Speed: 400 kHz.** The display lives on a separate I2C peripheral because a full
1 KB framebuffer push blocks the bus for ~25 ms. On a shared bus that costs roughly
21 EMG samples on every refresh.

### Interrupt and status pins

| ESP32 GPIO | Role | Connects to | Notes |
|---|---|---|---|
| 27 | Conversion-ready IRQ | ADS1115 `ALRT` | Open-drain; internal pull-up enabled. Missing → firmware auto-falls back to 500 Hz polling |
| 34 | Lead-off detect + | AD8232 `LO+` | Input-only pin, no internal pull-up (AD8232 drives it) |
| 35 | Lead-off detect − | AD8232 `LO-` | Input-only pin, no internal pull-up |

### Power

| ESP32 pin | Role |
|---|---|
| `3V3` | Supply for ADS1115, SSD1306 and AD8232 |
| `GND` | Common ground — every board must share it |

---

## I2C addresses

| Device | Address | Set by |
|---|---|---|
| ADS1115 | `0x48` | `ADDR` pin tied to GND |
| SSD1306 | `0x3C` | SA0 jumper open |

ADS1115 alternatives: `ADDR`→VDD = `0x49`, →SDA = `0x4A`, →SCL = `0x4B`.
If the self-test reports one of these, your `ADDR` pin is not grounded.

---

## Analog input

| ADS1115 channel | Signal | Status |
|---|---|---|
| `A0` | AD8232 `OUTPUT` | **In use** — the EMG signal |
| `A1` – `A3` | — | Free for additional electrode sites |

### ADS1115 configuration

Driven by direct register writes, not the Adafruit library, because the
conversion-ready trick needs exact control of the threshold registers.

| Setting | Value |
|---|---|
| Mode | Continuous |
| Data rate | 860 SPS (maximum) |
| Comparator queue | Assert after 1 conversion |
| `lo_thresh` / `hi_thresh` | `0x0000` / `0x8000` — turns `ALRT` into a sample-ready strobe |

### PGA gain table

Cycle at runtime with the `g` serial command. Index 1 is the default: safe headroom
for the AD8232's ~1.65 V mid-supply bias.

| Index | Range | Resolution |
|---|---|---|
| 0 | ±6.144 V | 187.5 µV/LSB |
| **1** | **±4.096 V** | **125.0 µV/LSB** ← default |
| 2 | ±2.048 V | 62.5 µV/LSB |
| 3 | ±1.024 V | 31.25 µV/LSB |
| 4 | ±0.512 V | 15.625 µV/LSB |
| 5 | ±0.256 V | 7.8125 µV/LSB |

The `n` (noise floor) command measures the actual swing and recommends a gain index.

---

## Pins to avoid

| GPIO | Why |
|---|---|
| 6 – 11 | Wired to the SPI flash chip. Using them bricks the boot. |
| 0, 2, 12, 15 | Strapping pins — pulling them at reset changes boot mode |
| 34 – 39 | Input-only, and no internal pull-ups. Fine for LO+/LO-, useless for outputs |

---

## Verifying the wiring

```powershell
python tools/asv_serial.py --port COM3 --cmd i --seconds 4    # I2C scan, both buses
python tools/asv_serial.py --port COM3 --check                # full self-test
```

Expected scan result: `0x48` on bus A, `0x3C` on bus B.

The self-test goes further than a scan — it writes and reads back the ADS1115 threshold
registers, which proves you are talking to a real ADS1115 rather than seeing a stray ACK
on a noisy bus.

---

## BLE

| Item | Value |
|---|---|
| Device name | `ASV-Device` |
| Service UUID | `6e6b0001-b5a3-f393-e0a9-e50e24dcca9e` |
| Status characteristic (notify) | `6e6b0002-b5a3-f393-e0a9-e50e24dcca9e` |
| Command characteristic (write) | `6e6b0003-b5a3-f393-e0a9-e50e24dcca9e` |

Custom 128-bit UUIDs. Earlier firmware misused `0x180A`/`0x2A29`, which are reserved by
the Bluetooth SIG for the Device Information Service.

BLE carries a 20 Hz status/preview packet, **not** the raw sample stream — BLE throughput
cannot sustain 860 SPS, and forcing it would back up and distort sample timing. Raw data
goes over USB serial.
