# ASV — Tonight's Bring-Up Guide (Arduino IDE)

Goal: **real EMG samples, precisely timed, landing in a CSV file on your PC.**
Follow this top to bottom. Every step has a pass criterion — do not move on until you hit it.

Estimated time: **45–60 minutes**, most of it wiring.

---

## 0. What changed and why

Your existing firmware was a PlatformIO project that Arduino IDE cannot compile,
and it had four problems that would have made the captured data unusable:

| Problem in old firmware | Effect | Fix in the new sketch |
|---|---|---|
| I2C bus at 100 kHz | Cannot sustain 860 SPS; an OLED refresh blocks the bus for ~100 ms | Bus raised to 400 kHz |
| OLED shares the ADC's I2C bus | ~21 lost samples on every screen refresh | OLED moved to the ESP32's **second** I2C peripheral (`Wire1`) |
| Sampling paced by software in `loop()` | Jitter from BLE/serial/display work | ADS1115 **ALRT/RDY** interrupt → sampler task pinned to **core 1** |
| `millis()` timestamps | 1 ms resolution vs a 1.16 ms sample period | Microsecond timestamps |

Because sampling now lives on core 1 with its own I2C bus, **BLE and the OLED can
stay fully enabled without costing you a single sample** — which is what you asked for.

---

## 1. Wiring

> Power everything from the ESP32's **3.3V** pin. Every board must share the **same GND**.
> Two OLED wires move, and three wires are new. Everything else stays where it is.

### 1.1 Power rails

| From | To |
|---|---|
| ESP32 `3V3` | breadboard **+** rail |
| ESP32 `GND` | breadboard **−** rail |

### 1.2 ADS1115 — I2C bus A (unchanged, plus one new wire)

| ADS1115 pin | Connect to | Note |
|---|---|---|
| `VDD` | + rail (3.3V) | |
| `GND` | − rail | |
| `SDA` | ESP32 **GPIO21** | |
| `SCL` | ESP32 **GPIO22** | |
| `ADDR` | − rail (GND) | sets address `0x48` |
| **`ALRT`** | **ESP32 GPIO27** | **← NEW. This is the accuracy wire.** |
| `A0` | AD8232 `OUTPUT` | the EMG signal |

If ALRT is left unwired the firmware detects it at boot and falls back to
software-paced 500 Hz — it still works, just with more jitter. It will tell you which
mode it chose.

### 1.3 SSD1306 OLED — I2C bus B (**move these two wires**)

| OLED pin | Connect to | Note |
|---|---|---|
| `VCC` | + rail (3.3V) | |
| `GND` | − rail | |
| `SDA` | ESP32 **GPIO25** | **← moved from GPIO21** |
| `SCL` | ESP32 **GPIO26** | **← moved from GPIO22** |

> Don't want to move them? Open `asv_config.h` and set
> `#define ASV_OLED_ON_SECOND_BUS 0`. It compiles and runs, but you will lose
> roughly 20 samples every half second, and the self-test will warn you about it.

### 1.4 AD8232 EMG front-end

| AD8232 pin | Connect to |
|---|---|
| `3.3V` | + rail |
| `GND` | − rail |
| `OUTPUT` | ADS1115 `A0` |
| `LO+` | ESP32 **GPIO34** |
| `LO-` | ESP32 **GPIO35** |
| `SDN` | + rail (3.3V) — keeps the amp awake |
| `RA` / `LA` / `RL` | electrode leads (see below) |

GPIO34/35 are input-only pins with no internal pull-ups. That is correct here —
the AD8232 drives them actively.

### 1.5 Electrode placement (jaw / masseter)

1. Clench your teeth and feel for the hard bulge about 2 cm in front of your earlobe,
   along the jaw angle. That is the **masseter**.
2. `RA` (+) → centre of the masseter belly.
3. `LA` (−) → ~2 cm away on the same muscle, along the fibre direction (roughly vertical).
4. `RL` (reference) → **bone, not muscle**: the mastoid bump behind the ear, or the collarbone.
5. Clean the skin with alcohol and let it dry. Dry or oily skin is the single most
   common cause of a garbage EMG trace.

### 1.6 I2C pull-ups

Most ADS1115 and SSD1306 breakouts already carry them. If the self-test finds no
devices, add **4.7 kΩ from SDA to 3.3V** and **4.7 kΩ from SCL to 3.3V** on each bus.

### 1.7 Two safety notes

- **Skin-contact electrodes:** run the laptop on **battery**, not a charger, while
  electrodes are on your face. This is standard practice for any mains-adjacent
  biopotential setup and costs you nothing.
- **Do not** feed the TP4056/AMS1117 battery rail and USB power into the ESP32 at the
  same time tonight. USB only until the signal chain is proven.

---

## 2. Arduino IDE setup

### 2.1 Install the ESP32 core

1. **File → Preferences → Additional Boards Manager URLs**, add:
   ```
   https://espressif.github.io/arduino-esp32/package_esp32_index.json
   ```
2. **Tools → Board → Boards Manager**, search `esp32`, install **"esp32" by Espressif Systems**.

### 2.2 Install libraries

**Tools → Manage Libraries**, install:

- `Adafruit SSD1306`
- `Adafruit GFX Library`

Accept the prompt to install dependencies (`Adafruit BusIO`).

> You do **not** need an ADS1115 library. This sketch drives the chip's registers
> directly so it behaves identically on every ESP32 core version.

### 2.3 Board settings — **the partition scheme matters**

**Tools → Board → esp32 → "ESP32 Dev Module"** (DOIT DEVKIT V1 also works), then:

| Setting | Value |
|---|---|
| Upload Speed | `921600` |
| CPU Frequency | `240 MHz` |
| Flash Frequency | `80 MHz` |
| Flash Size | `4MB (32Mb)` |
| **Partition Scheme** | **`Minimal SPIFFS (1.9MB APP with OTA/190KB SPIFFS)`** |
| Core Debug Level | `None` |
| Port | your COM port |

> **If you skip the partition change you will get `Sketch too big`.** The default
> 1.2 MB app partition cannot hold the BLE stack plus the display libraries.
> `Huge APP (3MB No OTA)` works too.

### 2.4 Open and upload

```
File → Open → firmware_arduino/ASV_Firmware/ASV_Firmware.ino
```

All the `.h`/`.cpp` files open as tabs automatically. Press **Upload**.

If upload fails to start, hold the **BOOT** button on the ESP32 while it says
"Connecting…", then release.

### 2.5 Serial Monitor

Open it and set the baud to **921600** (bottom-right). Press the ESP32's **EN/RST**
button to see the boot banner from the start.

---

## 3. Bring-up sequence

The firmware runs a full self-test automatically at boot and then waits for commands.

### Commands (type the letter in the Serial Monitor input box, then Send)

| Key | Action |
|---|---|
| `h` | help |
| `t` | full hardware self-test |
| `i` | I2C scan on both buses |
| `m` | live human-readable monitor (toggle) |
| `n` | 3-second noise-floor / baseline measurement |
| `s` | **start** the raw CSV stream |
| `x` | **stop** the stream |
| `g` | cycle ADC gain |
| `o` | toggle OLED |
| `r` | reset counters |
| `?` | one-line status |

### Step 1 — devices are on the bus

Press `i`. **Pass:** `0x48` on bus A, `0x3C` on bus B.

If nothing appears: power, GND, or swapped SDA/SCL. If `0x49`/`0x4A`/`0x4B` appears
instead of `0x48`, the ADS1115 `ADDR` pin is not tied to GND.

### Step 2 — self-test

Press `t`. **Pass:** the report ends with `RESULT: ALL CHECKS PASSED`.

What each section proves:

| Section | What a PASS means |
|---|---|
| ADS1115 register read-back | You are genuinely talking to an ADS1115 — not a stray ACK or a noisy bus |
| Sampling clock | `RDY-INTERRUPT` = the ALRT wire works; `POLLED` = it doesn't (still usable) |
| Live signal | Real samples are arriving at the expected rate |
| Electrodes | LO+/LO- report `attached`, so the pads are actually on skin |
| Peripherals | OLED found, and confirmation it's on the non-blocking bus |

### Step 3 — is the analog chain alive?

Press `n` and hold still for 3 seconds. Read the **DC baseline**:

| Baseline | Meaning |
|---|---|
| **~1500–1800 mV** | Correct. The AD8232 is powered and its output sits at mid-supply. |
| ~0 mV, peak-to-peak < 5 mV | `A0` is shorted to GND, or AD8232 `OUTPUT` isn't connected. |
| ~0 mV but noisy | `A0` is floating — nothing is wired to it. |
| Pinned at min/max | Clipping. Press `g` to change gain, or check the electrodes. |

The **AC RMS** figure is your noise floor. With clean electrodes and no clenching it
should be a few hundred µV or less. If it's milli-volts, the skin prep or the `RL`
reference is the problem.

### Step 4 — does it respond to muscle?

Press `m` for the live monitor, then **clench your jaw**.

**Pass:** the `pp=` (peak-to-peak) number jumps clearly — typically several times its
resting value — and returns when you relax. That is your EMG signal.

If nothing moves: re-seat the electrodes, check `RL` is on bone, and confirm both
`LO+`/`LO-` read `ok`.

### Step 5 — stream and record

Press `x` to leave the monitor, then run from the project root:

```bash
python ml/acquisition/collect_emg.py --subject S01 --label hello --reps 20 --port COM3
```

The Python reader now performs the `s` handshake itself, reads the firmware's
`# ASV_STREAM` header, and records microsecond timestamps.

Then check the quality of what you captured:

```bash
python ml/acquisition/validate_dataset.py
```

**Pass:** every trial reports `GOOD`, with `actual_sampling_rate_hz` ≈ 860 and no
jitter warnings.

---

## 4. Read this before you trust the data

**The stock SparkFun AD8232 breakout is filtered for ECG (roughly 0.5–40 Hz).**
Surface EMG energy lives mostly in **20–450 Hz**. So on an unmodified board you are
capturing the low-frequency part of the EMG envelope, not the full signal.

This is not a blocker for tonight — envelope energy is still discriminative and the
existing feature set (MAV, RMS, WL, VAR) works on it. But you should know it, because:

- Sampling at 860 Hz is still correct; it costs nothing and future-proofs the capture.
- If word-classification accuracy plateaus later, the front-end bandwidth is the first
  thing to suspect, not the model.
- The `n` command's AC RMS gives you a number to compare before and after any
  front-end change.

Confirm which AD8232 board you have before drawing conclusions from spectral features.

---

## 5. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Sketch too big` | Default partition | Set Partition Scheme to `Minimal SPIFFS` |
| Garbage in Serial Monitor | Wrong baud | Set **921600** |
| `*** ADS1115 NOT RESPONDING AT 0x48 ***` | Wiring / address | Check VDD, GND, GPIO21/22, `ADDR`→GND |
| Self-test says `POLLED` | ALRT not detected | Wire ADS1115 `ALRT` → GPIO27; add a 10 kΩ pull-up to 3.3V if it still won't trigger |
| `LEAD OFF` on LO+/LO- | Electrode not on skin | Re-seat pads; check `RL` on bone |
| Rising `drops=` while streaming | Host isn't reading fast enough | Close other serial monitors; the Arduino Serial Monitor and Python can't both hold the port |
| OLED blank but I2C finds `0x3C` | Contrast/panel | Press `o` twice; acquisition is unaffected either way |
| `collect_emg.py` gets 0 samples | Serial Monitor still open | Close it — only one program can own the COM port |
| Rate ≈ 500 Hz not 860 Hz | Running in polled fallback | Expected without the ALRT wire; update `settings.SAMPLING_RATE_HZ` to 500 if you keep it that way |

---

## 6. File map

```
firmware_arduino/ASV_Firmware/
├── ASV_Firmware.ino   main loop, serial commands, CSV output
├── asv_config.h       ALL pins, rates and switches  <- edit this one
├── asv_adc.{h,cpp}    ADS1115 registers, RDY interrupt, core-1 sampler, ring buffer
├── asv_oled.{h,cpp}   SSD1306 on Wire1
├── asv_ble.{h,cpp}    BLE server, custom UUIDs, 20 Hz status packets
└── asv_diag.{h,cpp}   self-test, I2C scan, noise floor, lead-off, gain advice
```

The old PlatformIO project in `firmware/` is left untouched as a reference.
