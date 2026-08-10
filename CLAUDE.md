# ASV — A Silent Voice

EMG-based silent speech recognition. Electrodes on the jaw pick up muscle activity
during silent articulation; the goal is to classify a small vocabulary of words.

**Signal chain:**
```
jaw electrodes -> AD8232 -> ADS1115 (A0) -> ESP32 -> USB CSV -> Python -> model
                                                  \-> BLE status -> app
```

---

## Current state — read this before claiming anything works

| Layer | Reality |
|---|---|
| Firmware (`firmware_arduino/`) | **Working and current.** 860 SPS, interrupt-paced, self-testing. |
| Firmware (`firmware/`) | **Legacy PlatformIO. Do not edit.** Kept only as reference. |
| Acquisition (`ml/acquisition/`) | Working; matches firmware v2 stream format. |
| Datasets | **No valid data yet.** See "Dataset warning" below. |
| ML pipeline (`ml/`) | Code exists, has never produced a trained model. `ml/outputs/` is empty. |
| Frontend (`frontend/`) | Polished UI, **100% simulated** — mock BLE, `Math.random()` waveforms, hardcoded words. |
| `README.md` (root) | **Aspirational.** Claims features that are not implemented. Trust `docs/CURRENT_SYSTEM_AUDIT.md` instead. |

**Do not** describe this project as working end-to-end. It is at the "getting real
signal off the hardware" stage.

### Dataset warning

- `datasets/emg_dataset.csv`, `emg_features.csv` — synthetic Gaussian noise. Meaningless.
- `datasets/ninapro_db1/` — real EMG, but **forearm/hand gestures**, not facial speech.
  A model trained on it cannot generalize to jaw EMG. Do not build on it.
- The only path forward is collecting real jaw-EMG with `ml/acquisition/collect_emg.py`.

---

## Hardware map

**Board:** ESP32 DevKit V1 · **Serial:** 921600 baud

| Signal | GPIO | Notes |
|---|---|---|
| I2C bus A: SDA / SCL | 21 / 22 | **ADS1115 only** — kept clear so sampling is never blocked |
| I2C bus B: SDA / SCL | 25 / 26 | **OLED only** (`Wire1`) |
| ADS1115 `ALRT` → conversion-ready IRQ | 27 | The accuracy wire. Absent → auto-fallback to 500 Hz polling |
| AD8232 `LO+` / `LO-` | 34 / 35 | Lead-off detect; input-only pins, no pull-ups (correct) |

I2C addresses: ADS1115 `0x48`, SSD1306 `0x3C`. Both buses run at 400 kHz.

**All configuration lives in `firmware_arduino/ASV_Firmware/asv_config.h`.** Change pins
and rates there, nowhere else.

---

## Architecture decisions — do not undo these

These exist to fix specific measured problems. Reverting any of them silently corrupts data.

1. **Sampler runs on core 1, priority 5**, notified by the ADS1115 ALRT/RDY interrupt.
   `loop()` on core 0 only drains a ring buffer. This is why BLE and the OLED can stay
   enabled without dropping samples.
2. **OLED is on `Wire1`, not the ADC bus.** A 1 KB framebuffer push blocks I2C for ~25 ms;
   on a shared bus that costs ~21 samples per refresh.
3. **I2C at 400 kHz, not 100 kHz.** 100 kHz cannot sustain 860 SPS.
4. **Microsecond timestamps**, not `millis()`. At 860 Hz the sample period is 1.16 ms;
   millisecond resolution cannot represent it.
5. **ADS1115 is driven by direct register writes**, not the Adafruit library. The
   conversion-ready trick needs exact control of the threshold registers, and that
   library's API changed between versions.
6. **BLE carries a 20 Hz status packet, not the raw stream.** BLE throughput cannot
   sustain 860 SPS; pretending otherwise backs up and distorts timing.
7. **The I2C pointer register is cached** (`g_pointerReg`) so a sample read is one
   transaction, not two. Any code that writes an ADS1115 register must update it.

---

## Commands

All paths relative to repo root. `COM3` is a placeholder — check with `ports`.

```powershell
# one-time toolchain install (arduino-cli + esp32 core + libraries)
.\tools\asv.ps1 setup

.\tools\asv.ps1 ports              # list connected boards
.\tools\asv.ps1 build              # compile only
.\tools\asv.ps1 flash -Port COM3   # compile + upload
.\tools\asv.ps1 monitor -Port COM3 # interactive serial (blocks; avoid in agent use)
```

**Scriptable serial (use this instead of `monitor` — it returns):**

```powershell
python tools/asv_serial.py --port COM3 --cmd t --seconds 10   # self-test, prints report
python tools/asv_serial.py --port COM3 --cmd n --seconds 6    # noise floor / baseline
python tools/asv_serial.py --port COM3 --stream --seconds 3 --out /tmp/probe.csv
python tools/asv_serial.py --list                             # available ports
```

**Data collection and QA:**

```powershell
python ml/acquisition/collect_emg.py --subject S01 --label hello --reps 20 --port COM3
python ml/acquisition/validate_dataset.py
```

---

## Firmware serial commands

Single letters, no Enter needed:
`h` help · `t` self-test · `i` I2C scan · `m` live monitor · `n` noise floor ·
`s` start CSV stream · `x` stop · `g` cycle gain · `o` toggle OLED · `r` reset counters · `?` status

The firmware **boots into IDLE** and streams only after `s`. `collect_emg.py` does this
handshake automatically. If something reports zero samples, that handshake is the first
thing to check.

---

## Gotchas that will waste your time

- **Only one program can hold the COM port.** Close the Arduino IDE Serial Monitor before
  running any Python script, and vice versa. Zero samples usually means a port conflict.
- **Partition scheme must be `min_spiffs`.** The default 1.2 MB app partition cannot fit
  BLE + display libraries. `asv.ps1` bakes this into the FQBN; the Arduino IDE does not.
- **`Wire.requestFrom((uint8_t), (uint8_t))` is ambiguous** on the ESP32 core and will not
  compile. Cast to `(int, int)`.
- **`settings.SAMPLING_RATE_HZ` must match the firmware.** 860 with the ALRT wire, 500
  without. A mismatch between collection and inference destroys accuracy silently.
  `collect_emg.py` warns if measured rate drifts >10% from the configured value.
- **The stock SparkFun AD8232 is filtered for ECG (~0.5–40 Hz)**, while EMG lives at
  20–450 Hz. Captures are envelope-dominated. This is a known front-end limitation, not
  a firmware bug — suspect it before blaming the model.
- **GPIO34/35 are input-only** and have no internal pull-ups. That is intentional here.
- **Do not use GPIO 6–11** (SPI flash) or GPIO 0/2/12/15 (strapping pins) for new signals.

---

## Verification expectations

Firmware changes are not "done" on a clean compile. Before claiming success:

1. `.\tools\asv.ps1 build` — must compile clean.
2. `python tools/asv_serial.py --port COM3 --cmd t --seconds 10` — must end with
   `RESULT: ALL CHECKS PASSED`.
3. For timing-related changes, capture a stream and confirm the measured rate and jitter:
   `python tools/asv_serial.py --port COM3 --stream --seconds 5 --out probe.csv`, then
   check `dt` std/mean. With the ALRT interrupt it should be well under 0.25.

If the board is not plugged in, say so rather than reporting an untested change as working.

---

## Style

- C++: 2-space indent, `asv_` prefix on module files, explain *why* in comments — the
  non-obvious timing decisions above are the ones worth documenting.
- Python: standard library + numpy/scipy/sklearn. Match the existing module layout under `ml/`.
- Keep `docs/ARDUINO_IDE_SETUP.md` in sync when pins or commands change.
