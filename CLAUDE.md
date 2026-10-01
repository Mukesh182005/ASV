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
| Firmware (`firmware_arduino/`) | **Working and current.** 860 SPS, interrupt-paced, self-testing. Flashed and verified 2026-08-26 (build `Aug 26 2026 23:13:01`): self-test passes, BLE word push reaches the app. |
| Acquisition (`ml/acquisition/`) | Working and tested; matches firmware v2 stream format. |
| Tests (`tests/test_pipeline.py`) | 46/46 passing. Run them after touching `ml/`. |
| Datasets | **Real data exists.** 250 jaw-EMG recordings, one subject (S01), five electrode sessions on 2026-08-26. See below. |
| ML pipeline (`ml/refined/`) | Trained. `refined_model/` holds an ExtraTrees: **67.0% on an unseen donning**, 66.4% pooled, over 5 words. A 3-word subset reaches 90%. See below. |
| Legacy ML (`ml/training/`, `ml/inference/`, `ml/preprocessing/`) | The old per-window pipeline, superseded — it labelled silence as speech and stalled near 48%. `ml/models/latest` and `ml/models/demo_hello_rest` are deleted; code still pointing at them is stale. |
| Backend (`backend/main.py`) | FastAPI inference server over `refined_model/`. **Verified working 2026-08-26**: `/health`, `/model/status` and `/predict_utterance` all respond correctly against real recordings. Start with `python -m uvicorn backend.main:app --port 8000`. |
| Frontend (`frontend/`) | Assistive-communication app, deliberately thin. Connects over Bluetooth, shows the word the OLED is showing, speaks it, and offers a tap-a-word phrasebook. No muscle-activity display, no USB connection of its own. |

The honest summary: acquisition, offline classification and the app's recognition
path all work, so a mouthed word can reach the screen and be spoken, and accuracy
now largely survives re-applying the electrodes. What is still missing is
on-device classification — a PC running the backend is always in the loop — and
five-word accuracy is 67%, workable but not reliable. **Do not** describe this
as a working wearable.

### The dataset — `datasets/custom_silent_speech/`

250 recordings: 5 words (`hi, help, no, rest, yes`) x 50 reps, subject S01,
**five electrode sessions** on 2026-08-26. 2.5 s each at ~860.9 Hz,
`mode: rdy_irq`, zero malformed packets, all validating `GOOD`.

| Session | Time | n | Words | Usable as a test fold |
|---|---|---|---|---|
| A | 16:40-16:46 | 40 | 4 (no `hi`) | no |
| B | 18:38-18:43 | 40 | 4 (no `hi`) | no |
| C | 19:04-19:07 | 20 | 1 (`hi` only) | no |
| D | 20:12-20:18 | 50 | all 5 | yes |
| E | 20:48-20:58 | 100 | all 5 | yes |

**Sessions come from recording timestamps, not the rep index.** `tools/session_eval.py`
splits wherever consecutive recordings are more than 15 minutes apart, which is why
the `timestamp` in each `_meta.json` matters — do not discard the sidecars.

A session is only a valid test fold if it contains **every** word. A and B predate the
`hi` rename; C holds `hi` alone and scored exactly chance, which told us nothing. Every
new donning should cover all five words.

`_excluded/` holds 44 earlier recordings quarantined rather than deleted
(`questionable_electrode_20260823/`, `TEST/`). Do not fold them back in without
re-checking electrode contact first.

**This data is committed to the repo** (~10 MB), deliberately: a clone has to
arrive with the recordings, or the next person starts from scratch on a dataset
that took hours of articulation to collect. `.gitignore` still excludes `*.csv`
globally, so the negations under `datasets/custom_silent_speech/` are what keep
it tracked — do not remove them.

Recording data is the one thing here that cannot be regenerated from source, so
keep a copy outside the repo as well; `git clean -xdf` and a bad rebase are both
capable of losing work git has not been told about yet.

`datasets/ninapro_db1/` stays ignored and must never be committed — 3.2 GB of
forearm/hand gesture EMG that cannot transfer to jaw articulation. Same for the
synthetic `datasets/emg_dataset.csv` / `emg_features.csv`, which are Gaussian
noise from the pre-hardware era.

**Vocabulary change 2026-08-26:** `hello` was dropped and replaced with `hi`. It was
the worst class in every evaluation and live testing confirmed it. Its recordings
survive in `asv_S01_100rec_2sessions_20260826_184910`. Worth knowing: `hi` initially
landed at the same weak precision, so the word itself was never the problem — it only
became the strongest non-`rest` class once several donnings existed.

### The model — `refined_model/`

One recording = one sample. 23 utterance-level features (energy, envelope shape,
burst timing, spectrum) from `ml/refined/utterance_features.py`, shared by training
and inference so the two cannot drift apart.

Retrained 2026-08-26 on 250 recordings: **ExtraTrees**, **67.0% out-of-session**,
66.4% pooled leave-one-out, chance 20%.

`train_refined.py` selects on out-of-session accuracy whenever the dataset has
sessions containing every word. That matters: on this data the two metrics
disagree and pick different winners.

| Candidate | Pooled LOO | Out-of-session |
|---|---|---|
| LDA | 64.0% | 63.0% |
| SVM_linear | 66.4% | 65.5% |
| SVM_rbf | **67.2%** | 63.5% |
| RandomForest | 66.8% | 65.0% |
| **ExtraTrees** | 66.4% | **67.0%** |

Selecting on pooled LOO picks SVM_rbf, which is 3.5 points *worse* on an unseen
donning — it is simply better at recognising the session. Quote the out-of-session
number and select on it.

The headline pooled figure has wandered (76% -> 67% -> 61% -> 66%) purely because
it tracks how much session leakage is available. Out-of-session went
29% -> 52% -> 67% over the same period. That is the real trajectory.

### Cross-session transfer — the problem that is being solved

A "session" is one donning of the electrodes. Re-applying them changes the signal
more than changing the word does, so a model trained on one donning historically
did not transfer to the next. Collecting more donnings is fixing it, and the
progression is the most important measurement in the project:

| Sessions in the dataset | Out-of-session accuracy |
|---|---|
| 2 (100 recordings) | 29% |
| 4 (150 recordings) | 52% — one valid fold |
| **5 (250 recordings)** | **67.0% — two valid folds** |

Chance is 20%. More telling than the rise: the gap between the optimistic and the
honest number has closed entirely. Pooled leave-one-recording-out is 66.4% against
67.0% out-of-session — the honest number is now the *higher* one, where at four
sessions pooled was inflated by +11%. The model has stopped keying on session
identity, which is exactly what more donnings were supposed to achieve.

**Keep collecting donnings.** This is the highest-value work available and it is
measurably paying off. Ten reps of every word per donning, electrodes re-applied
between batches.

Always measure with `python tools/session_eval.py`. It recovers sessions from
recording timestamps (splitting at gaps > 15 min), refuses to score a session
that does not contain every word, and prints both numbers side by side so the
inflation stays visible.

#### Vocabulary size is the other lever

Measured out-of-session on the 250-recording set (SVM_rbf), best subset at each size:

| Words | Out-of-session | Chance | Best subset |
|---|---|---|---|
| 5 | 63.5% | 20% | help, hi, no, rest, yes |
| 4 | 76.2% | 25% | help, hi, rest, yes |
| 3 | **90.0%** | 33% | hi, no, rest |
| 2 | 95.0% | 50% | hi, rest |

`rest` and `hi` are cleanly separable (out-of-session f1 0.90 and 0.88). The
errors concentrate almost entirely in `help` / `no` / `yes`, which confuse with
each other: `yes` is the worst class at f1 0.36, going to `no` 11 times and
`help` 9 times out of 30. Note that `no` appears in the best 3-word set but is
dropped from the best 4-word set — at 50 recordings per word that ordering is
within noise, so re-measure before treating any specific subset as settled.

**A three-word vocabulary is demo-quality today at 90%.** Five words is not.
That is a product decision, not a modelling one.

### How a word reaches the app

Nothing on the ESP32 classifies. The PC runs the model and pushes the answer to the
board, which shows it on the OLED **and** notifies it over BLE in the same step, so
the display and the phone can never disagree.

```
electrodes -> ESP32 --USB CSV--> PC runs the model
                                     |
                      "w<word>\n" over serial
                                     v
                          ESP32  --> OLED  (2 s)
                                 --> BLE   --> app shows + speaks it
```

That is the whole path. `tools/predict_live.py` and `tools/predict_live_gui.py`
both call it after every prediction; the firmware end is the word-reading branch
in `ASV_Firmware.ino`, which sets `g_predictedWord` and then calls
`asvBleNotifyWord(g_predictedWord, 90)`.

**Before 2026-08-26 the serial word path set the OLED text but never notified BLE**,
which is why words appeared on the display and never reached the phone. One line
fixed it. Any future code that changes what the OLED shows must keep the BLE
notify beside it.

The app is deliberately thin: it connects over Bluetooth, shows words that arrive,
speaks them, and offers a tap-a-word phrasebook. It does **not** display muscle
activity and does **not** open a USB connection of its own.

**Verified end to end on 2026-08-26** (firmware build `Aug 26 2026 23:13:01`):
self-test all checks passed at 860.94 Hz on the RDY interrupt, `c` captured and
sent 2150 samples cleanly, and with the app connected (`ble=CONNECTED`) three
pushed words reached the phone and were spoken aloud.

#### Order of operations — this one bites

**Opening the serial port reboots the ESP32**, which drops any BLE connection.
CP210x boards reset on DTR/RTS, so every Python tool that opens COM5 restarts the
firmware. So:

1. Start `predict_live_gui.py` / `predict_live.py` first — the board reboots once.
2. **Then** pair the app in Chrome/Edge.

The other order disconnects the phone the instant the predictor starts, and the
symptom is confusing: the app looks paired while the board reports `ADVERTISING`.
Check with `?` on the serial line — `ble=CONNECTED` is the only proof a client is
really attached. Pairing in Windows Bluetooth settings does **not** count; Web
Bluetooth makes its own GATT connection through the browser's device chooser.

#### Also present but unused: the BLE capture burst

`asvBleSendCapture()` in firmware and `captureUtterance()` in `use-ble.ts`
implement a different design — the app writes `c`, the ESP32 records 2.5 s into RAM
and bursts ~4.3 kB back, and the phone hands the samples to the backend. Wire format:

```
header  [0]=0xC5 [1]=0x00 [2..3]=total samples [4..5]=sample rate Hz
chunk   [0]=0xC5 [1]=0x01 [2..3]=start index   [4..]=int16 counts
footer  [0]=0xC5 [1]=0x02
```

It round-trips correctly under test and the firmware side was confirmed working on hardware (2150 samples captured and sent), but no screen calls it. It is the path to a
phone-only product that does not need a PC at all — worth reviving once the model
moves on-device. `frontend/hooks/use-emg-recognition.ts` is its unused driver.
Continuous 860 SPS over BLE still does not work; the burst is a one-shot after
recording, which is a different problem.

### Deleted — do not recreate

`ml/models/latest/` and `ml/models/demo_hello_rest/` (superseded by
`refined_model/`). Recoverable from git history if genuinely needed.

Note: `firmware/` (PlatformIO), `ml/legacy_experimental/` and `ml/run_pipeline.ps1`
are still present but dead — `firmware_arduino/` is the live firmware. Do not edit
the PlatformIO tree.

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
   sustain 860 SPS; pretending otherwise backs up and distorts timing. The `c`
   capture burst is not an exception to this: it records into RAM first and sends
   ~4.3 kB *afterwards*, so nothing is being sustained. Do not read it as licence
   to stream continuously.
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
# dataset manager — the front door for everything data-related
python tools/manage_dataset.py status                              # counts per word
python tools/manage_dataset.py collect-all --reps 10 --port COM5   # all 5 words
python tools/manage_dataset.py collect --word no --reps 10 --port COM5
python tools/manage_dataset.py delete --word no                    # destructive; back up first
python tools/manage_dataset.py retrain
python tools/session_eval.py                     # HONEST accuracy: leave-one-session-out

# or drive collection directly
python ml/acquisition/collect_emg.py --subject S01 --label hi --reps 20 --port COM3
python ml/acquisition/validate_dataset.py       # writes metadata/validation_report.json
python tools/check_interference.py --port COM5   # mains-hum / contact check BEFORE collecting
```

Recording duration is **2.5 s** everywhere (collection, live prediction). If you
change it, change it in all three places or the features shift under the model.

**Training and inference:**

```powershell
python ml/refined/train_refined.py              # rebuilds refined_model/ in place
python refined_model/predict.py <recording.csv> # classify one saved recording
python tools/predict_live.py --port COM5        # live, CLI
python tools/predict_live_gui.py --port COM5    # live, Tkinter window
```

`train_refined.py` overwrites `refined_model/` — the previous model is only in git
(and the `.pkl` files there *are* tracked). Commit before retraining if the current
one matters.

**The app:**

```powershell
cd frontend; npm install; npm run dev    # http://localhost:3000
```

Web Bluetooth needs Chrome or Edge on desktop/Android, over localhost or HTTPS —
Firefox, Safari and all iOS browsers have no support and the app falls back to the
phrasebook. To reach it from a phone on the same network, serve over HTTPS; plain
`http://<lan-ip>:3000` is treated as an insecure origin and Bluetooth is blocked.

The app subscribes to a fourth BLE characteristic, `ASV_BLE_WORD_UUID`, that carries
recognised words (`0xC3` magic, confidence byte, length byte, ASCII text — one
notification). Nothing on the ESP32 classifies yet, so the only producer today is the
`w` serial command; `asvBleNotifyWord()` is where a real model would publish.

---

## Firmware serial commands

Single letters, no Enter needed:
`h` help · `t` self-test · `i` I2C scan · `m` live monitor · `n` noise floor ·
`s` start CSV stream · `x` stop · `g` cycle gain · `o` toggle OLED · `r` reset counters ·
`w` push a test word over BLE · `c` capture one utterance and burst it over BLE · `?` status

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
- **Peak-to-peak jumping from ~100 mV to ~2000-3000 mV is mains hum, not a bad electrode.**
  Seen 2026-08-23 and again 2026-08-26. Three electrode swaps changed nothing both times,
  because the electrodes were never the fault: 78-85% of signal power sat in a 50 Hz band
  and the AD8232 was driven rail-to-rail (counts 3432..26269 against a 0..26500 rail).
  A saturated front end has *lost* the muscle signal — the 50/100 Hz notch in
  `utterance_features.preprocess()` cannot recover it, so never train on data captured in
  this state. Check with `python tools/check_interference.py --port COM5` before every
  collection run. Healthy reference (the 08-26 batch): pp 56..498 mV, 50 Hz power ~3.7%,
  baseline ~1692 mV. Usual cause, in order: laptop on its AC charger (run on battery), the
  reference/RL electrode not actually connected (jack not fully seated — put it on bone,
  not muscle), proximity to power strips and chargers, AD8232 GND not truly common with
  the ESP32.
- **`venv/` has no pyserial.** Anything touching the board (`collect_emg.py`,
  `predict_live*.py`, `check_interference.py`, `asv_serial.py`) must run under the system
  `python`. The venv is for offline model work only.
- **`venv/` has no pytest.** Run the suite with the system `python -m pytest tests/ -q`.
  `venv/Scripts/python.exe` does have sklearn 1.8 and is what loads the `.pkl` files.
- **Console output is cp1252 on Windows.** Any script printing `✓`/`⚠` will raise
  `UnicodeEncodeError` mid-run. `validate_dataset.py` used to die this way *before*
  writing its JSON report, silently leaving a stale report on disk — it now forces
  UTF-8 on stdout. Do the same in new CLI tools.
- **`collect_emg.py` continues rep numbering from the existing files.** Adding 10 more
  reps to a folder that already has `rep001..rep010` produces `rep011..rep020`, not a
  second `rep001..rep010`. The on-screen counter still shows `Trial 1/10` with the real
  index in brackets. It parses the highest existing `repNNN_` prefix, so don't rename
  recordings to something that doesn't match that pattern.

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
