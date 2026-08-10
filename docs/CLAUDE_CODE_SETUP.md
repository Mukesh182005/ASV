# Giving the agent hands on the hardware — Claude Code setup

This connects Claude Code to the ASV project so it can compile, flash, and read the
ESP32's serial output **on your machine**, without you relaying output by hand.

One-time setup: ~15 minutes, most of it the ESP32 core download.

---

## Why this and not the chat sandbox

The Cowork sandbox is an isolated Linux VM. It has no USB passthrough to your COM port
and its network blocks the Arduino toolchain, so nothing running there can reach the
board. Claude Code runs a shell on **your** Windows machine, which can.

---

## 1. Install Claude Code

Open **PowerShell** (your prompt starts with `PS C:\`) and run:

```powershell
irm https://claude.ai/install.ps1 | iex
```

If your prompt has no `PS` prefix you're in CMD — use this instead:

```batch
curl -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd && del install.cmd
```

You do not need Administrator. Native installs auto-update in the background.

**Also install [Git for Windows](https://git-scm.com/downloads/win).** It's technically
optional, but without it Claude Code falls back to the PowerShell tool instead of Bash,
and the permission rules in step 3 are written for Bash.

Verify:

```powershell
claude --version     # prints something like 2.1.211 (Claude Code)
claude doctor        # read-only diagnostics if anything looks off
```

**Account requirement:** Claude Code needs a Pro, Max, Team, Enterprise, or Console
account. The free plan does not include it.

---

## 2. Install the ASV toolchain

```powershell
cd C:\Users\Asus\Downloads\ASV-main\ASV-main
.\tools\asv.ps1 setup
```

This installs `arduino-cli`, registers the ESP32 board index, installs the `esp32:esp32`
core and the two Adafruit libraries, and adds `pyserial`.

The core download is a few hundred MB — expect a wait the first time.

If `arduino-cli` isn't found afterwards, **open a new terminal** (winget doesn't refresh
`PATH` in the current one) and re-run `setup`.

Check it:

```powershell
.\tools\asv.ps1 doctor
```

Every line should read `OK`.

---

## 3. Enable the permission allowlist

Without this the agent asks for approval on every single command, which defeats the point.

```powershell
mkdir .claude -Force
copy tools\claude-settings.json .claude\settings.json
```

This auto-approves only the ASV toolchain — build, flash, serial capture, dataset
validation, local git. It explicitly **denies** `git push`, `git reset --hard`, core
uninstall, and reading the 3.4 GB NinaPro CSV (which would blow up context for nothing).

Anything outside that list still prompts you. Widen it later if you find yourself
approving the same command repeatedly.

---

## 4. Start a session

Plug in the ESP32, then:

```powershell
cd C:\Users\Asus\Downloads\ASV-main\ASV-main
claude
```

`CLAUDE.md` in the repo root loads automatically. It contains the hardware map, the pin
assignments, the architecture decisions that must not be undone, and the gotchas —
so the agent starts with the same context I have, not a cold read of the repo.

### A good first prompt

```
Read CLAUDE.md. The ESP32 is plugged in. Run .\tools\asv.ps1 doctor, then build
and flash the firmware, then run the self-test and tell me exactly what passed
and what failed. Don't fix anything yet - just report.
```

That exercises the whole loop end to end and tells you whether the wiring is right
before any code changes happen.

### Useful follow-ups

```
Capture 5 seconds of stream and report the jitter ratio and baseline.
```
```
The self-test says POLLED instead of RDY-INTERRUPT. Diagnose it.
```
```
Run a collection of 20 reps for "hello" on subject S01, then validate the dataset
and tell me if any trial should be re-recorded.
```

---

## 5. What the agent can actually do now

| Task | Command it will use |
|---|---|
| Check toolchain health | `.\tools\asv.ps1 doctor` |
| Find the board | `.\tools\asv.ps1 ports` |
| Compile | `.\tools\asv.ps1 build` |
| Flash | `.\tools\asv.ps1 flash -Port COM3` |
| Run the self-test and read the result | `python tools/asv_serial.py --port COM3 --check` |
| Measure noise floor | `python tools/asv_serial.py --port COM3 --cmd n --seconds 6` |
| Capture + analyse timing | `python tools/asv_serial.py --port COM3 --stream --seconds 5 --out probe.csv` |
| Validate recordings | `python ml/acquisition/validate_dataset.py` |

`asv_serial.py` exits non-zero when the self-test fails, jitter exceeds 0.25, or the
sample rate drifts more than 15% from the firmware's target — so the agent gets a real
pass/fail signal instead of having to interpret prose.

Use `asv_serial.py`, not `.\tools\asv.ps1 monitor` — the latter blocks until Ctrl+C and
will hang an agent session.

---

## 6. Things that will trip you up

| Symptom | Cause |
|---|---|
| `cannot open COM3` | Something else holds the port. Close the Arduino IDE Serial Monitor. Only one program can own it. |
| Upload hangs at "Connecting..." | Hold the **BOOT** button on the ESP32, then release once it starts. |
| `arduino-cli not found` after setup | `PATH` not refreshed. Open a new terminal. |
| Agent says it can't find the board | It's not plugged in, or the driver is missing (CP2102/CH340). |
| Agent claims a fix works without flashing | Push back. `CLAUDE.md` tells it a clean compile is not sufficient evidence — self-test output is. |

---

## 7. Keeping the two of us in sync

`CLAUDE.md` is the shared brief. If you change pins, add a command, or make a design
decision worth remembering, tell the agent to update `CLAUDE.md` — otherwise the next
session starts without it.

Sources: [Claude Code setup](https://docs.claude.com/en/docs/claude-code/setup) ·
[Claude Code settings](https://docs.claude.com/en/docs/claude-code/settings)
