# ASV — A Silent Voice

EMG-based silent speech recognition. Surface electrodes on the jaw pick up muscle
activity during silent articulation; the goal is to classify a small vocabulary of
words without vocalisation.

```
jaw electrodes → AD8232 → ADS1115 (A0) → ESP32 → USB CSV → Python → model
                                              ↘ BLE status → app
```

---

## Project status — read this first

This project is at the **"getting clean signal off the hardware"** stage. It is not a
working end-to-end system, and this README will not claim otherwise.

| Layer | Status |
|---|---|
| Firmware (`firmware_arduino/`) | **Working.** 860 SPS, interrupt-paced, self-testing. Compiles clean. |
| Acquisition (`ml/acquisition/`) | **Working.** Matches the firmware stream format. 23/23 tests pass. |
| Inference backend (`backend/`) | Code complete, **untested** — no model exists to serve. |
| ML pipeline (`ml/`) | Code exists, **has never produced a trained model**. |
| Datasets | **Empty.** No valid recordings yet. |
| Frontend (`frontend/`) | Polished UI, **entirely simulated** — mock BLE, random waveforms, hardcoded results. |

The honest inventory of what is real versus mocked is in
[`docs/CURRENT_SYSTEM_AUDIT.md`](docs/CURRENT_SYSTEM_AUDIT.md).

---

## Getting started

**Bring the hardware up:** [`docs/ARDUINO_IDE_SETUP.md`](docs/ARDUINO_IDE_SETUP.md) —
wiring table, board settings, and a step-by-step bring-up with a pass criterion at
every stage. Start here.

**Let an agent drive it:** [`docs/CLAUDE_CODE_SETUP.md`](docs/CLAUDE_CODE_SETUP.md) —
connects Claude Code so builds, flashes and serial capture run from a terminal.

**Pin reference:** [`docs/GPIO_MAPPING.md`](docs/GPIO_MAPPING.md)

### Quick commands

```powershell
.\tools\asv.ps1 setup                # one-time: arduino-cli + esp32 core + libraries
.\tools\asv.ps1 doctor               # check the toolchain
.\tools\asv.ps1 flash -Port COM3     # compile + upload

python tools/asv_serial.py --port COM3 --check              # hardware self-test
python tools/asv_serial.py --port COM3 --cmd n --seconds 6  # noise floor
python ml/acquisition/collect_emg.py --subject S01 --label hello --reps 20 --port COM3
python ml/acquisition/validate_dataset.py
python -m pytest tests/ -q
```

---

## Hardware

**ESP32 DevKit V1** · serial **921600 baud**

| Signal | GPIO | Notes |
|---|---|---|
| I2C bus A — SDA / SCL | 21 / 22 | ADS1115 only, kept clear so sampling is never blocked |
| I2C bus B — SDA / SCL | 25 / 26 | OLED only (`Wire1`) |
| ADS1115 `ALRT` | 27 | Conversion-ready interrupt — the accuracy wire |
| AD8232 `LO+` / `LO-` | 34 / 35 | Lead-off detect (input-only pins) |

Both buses run at 400 kHz. ADS1115 `0x48`, SSD1306 `0x3C`.

Full wiring, including electrode placement on the masseter, is in
[`docs/ARDUINO_IDE_SETUP.md`](docs/ARDUINO_IDE_SETUP.md#1-wiring).

---

## Repository layout

```
firmware_arduino/ASV_Firmware/   Arduino IDE sketch — the current firmware
tools/                           arduino-cli driver + scriptable serial harness
ml/acquisition/                  serial reader, labelled collection, dataset QA
ml/preprocessing/ training/      filtering, segmentation, feature extraction, models
ml/inference/                    real-time inference engine
ml/config/settings.py            sampling rate, filters, vocabulary — keep in sync with firmware
backend/main.py                  FastAPI inference server (untested)
frontend/                        Next.js UI — simulated, not wired to hardware
tests/test_pipeline.py           unit tests for the acquisition + ML layers
docs/                            setup guides and the system audit
CLAUDE.md                        project brief for agent sessions
```

---

## Known limitations

- **No trained model exists.** `ml/outputs/` and `ml/models/` are empty. Nothing in this
  repository can currently recognise a word.
- **The stock SparkFun AD8232 is filtered for ECG (~0.5–40 Hz)** while EMG energy lives at
  20–450 Hz. Captures are envelope-dominated. Suspect this before blaming the model.
- **EMG is highly subject-specific.** A model trained on one person will not transfer to
  another without recalibration.
- **`settings.SAMPLING_RATE_HZ` must match the firmware** (860 with the ALRT wire, 500
  without). A mismatch silently destroys accuracy; `collect_emg.py` warns if it drifts.

---

## Next steps

1. Wire and flash; self-test must report `ALL CHECKS PASSED` with mode `RDY-INTERRUPT`.
2. Confirm the analog chain — baseline ~1.65 V, and peak-to-peak rises when you clench.
3. Record a first dataset: 4 distinct words plus a `rest` class, ~30 reps each, in blocks.
4. Run the ML pipeline against real data for the first time; split by block, not randomly.
5. Only then wire the backend and frontend to live data.

---

## License

MIT — see `LICENSE`.
