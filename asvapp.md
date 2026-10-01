# ASV App — UI/UX Audit & Redesign Spec

> What exists right now, what's real vs fake, and exactly what needs to change.

---

## Current Screen Inventory (8 screens)

```
splash → login → bluetooth → device → dashboard → detection → speech → settings
```

| Screen | File | Status | Keep? |
|--------|------|--------|-------|
| Splash | `splash-screen.tsx` | ✅ Works, looks good | ✅ Keep as-is |
| Login | `login-screen.tsx` | ❌ Fake — email/password, Google auth, no backend | ❌ **DELETE** |
| Bluetooth Scan | `bluetooth-scan.tsx` | ❌ Fake — hardcoded mock devices, no real BLE | ❌ **REPLACE** |
| Device Connection | `device-connection.tsx` | ❌ Simulated, hardcoded stats | ❌ **REPLACE** |
| Dashboard | `dashboard-screen.tsx` | ⚠️ Fake stats (--/--/--), "Smart Neckband" framing | ⚠️ **SIMPLIFY** |
| Live Detection | `live-detection.tsx` | ✅ Real backend wired, real waveform, real model | ✅ **REFINE** |
| Speech Output | `speech-output.tsx` | ❌ Fake playback timer, hardcoded conversation history | ❌ **REPLACE** |
| Settings | `settings-screen.tsx` | ⚠️ Needs audit | ⚠️ Review |

---

## The Core Problem

The app currently pretends to be a consumer Bluetooth neckband app.  
**Reality:** It's a USB-serial ESP32 device that plugs into a PC/laptop.

Every screen that shows "Neckband Pro", "BLE scan", "Battery 87%" is fiction.  
**The user wants to see only what's real: the ASV ESP32 device when it's connected.**

---

## What the Python GUI Does (the ground truth)

```
plot_words.py flow:
  1. Connects to ESP32 over USB serial (COM9)
  2. Background thread streams 860 Hz EMG continuously into a ring buffer
  3. Matplotlib shows a live scrolling EMG waveform (the whole graph)
  4. User presses SPACE → captures 4s window → runs feature extraction → SVM prediction
  5. Shows predicted word + confidence bar chart for all 5 words
  6. Sends prediction back to ESP32 → shown on OLED
```

**The app should mirror this — nothing more, nothing less.**

---

## New Screen Flow (Simplified: 3 real screens + splash)

```
[SPLASH] → [ESP32 CONNECTION CHECK] → [LIVE DETECTION] → [HISTORY/OUTPUT]
```

| # | Screen | Purpose |
|---|--------|---------|
| 1 | **Splash** | Keep as-is. "A Silent Voice" branding. |
| 2 | **Device Connect** | Show ONLY ESP32 via Web Serial. No BLE. No mock devices. If ESP32 connected → go to 3. If not → wait/prompt. |
| 3 | **Live Detection** | The main screen. Always visible when connected. Mirror of plot_words.py. |
| 4 | **Word History** | Simple log of detected words in this session. Replace fake Speech Output. |

---

## Screen-by-Screen Redesign Spec

---

### SCREEN 1 — Splash ✅ (Keep)
No changes needed. It's clean and fits the brand.

---

### SCREEN 2 — ESP32 Connect (Replace bluetooth-scan + device-connection + login)

**Kill:** Login, Bluetooth scan with mock devices, device-connection screen.

**New single screen: "Connect ASV Device"**

```
┌─────────────────────────────────┐
│                                 │
│         [ESP32 icon / SVG]      │
│                                 │
│      ASV — A Silent Voice       │
│                                 │
│  ┌─────────────────────────┐    │
│  │  ESP32 not connected    │    │
│  │  Plug in via USB        │    │
│  └─────────────────────────┘    │
│                                 │
│  [Connect via Web Serial]       │  ← navigator.serial.requestPort()
│                                 │
│  ─── or ───                     │
│                                 │
│  [Use Replay Mode (no device)]  │  ← goes straight to detection, demo mode
│                                 │
│  Works in: Chrome / Edge only   │
│  (Web Serial API required)      │
│                                 │
└─────────────────────────────────┘
```

**State machine:**
- `idle` → show connect button
- `connecting` → spinner
- `connected` → green pulse + "ASV Device connected at 860 Hz" → auto-advance
- `error` → red + error message + retry

**What's real:** `navigator.serial.requestPort()` already works in `use-web-serial.tsx`.  
**What to remove:** All BLE code, all mock devices, login form.

---

### SCREEN 3 — Live Detection ✅ (Refine — this is the heart)

This screen is mostly working. Needs these specific changes:

#### ✅ Keep:
- EMG waveform bars (real signal)
- Detected word display (big text, real model)
- Confidence bar
- Word ranking (all 5 words + prob)
- Replay vs Live mode toggle
- Backend offline warning
- Model status indicator

#### ❌ Remove:
- "Surprise me" button (confusing for demo)
- The "Speak detected word" button (leads to fake speech screen)
- Replay mode word chips (tap hello/help/no/rest/yes) — too cluttered for mobile

#### 🔧 Change:
- **Capture button:** Change "Capture 2s & classify" → big prominent `[CAPTURE]` button, full width, prominent. Matches the SPACE key in the Python GUI.
- **Capture window:** Update from 2s to 4s to match training data.
- **Waveform:** Make it taller — use more vertical space. The Python GUI shows the full signal. App shows tiny bars. Increase to ~160px height.
- **Live waveform scrolling:** When in live mode + connected, waveform should scroll continuously (like plot_words.py), not just update on capture.
- **Model status:** Show `■ Model ready — hello / help / no / rest / yes` always visible at top. If model not loaded → show warning. The app should NOT work without the model.
- **Word display:** After capture, animate the detected word in large text. It should be the dominant UI element — not buried under the waveform card.

#### Mobile layout priority order (top → bottom):
```
1. Status bar (device connected + model ready)    ← always visible
2. Live EMG waveform (scrolling, full width)      ← dominant visual
3. Detected word (giant text, center)             ← result
4. Confidence + word ranking bars                 ← supporting info
5. [CAPTURE] button (large, full width)           ← primary action
```

---

### SCREEN 4 — Word History (Replace speech-output.tsx)

Simple session log. No fake audio playback.

```
┌─────────────────────────────────┐
│  ← Session History              │
│                                 │
│  09:14:32   YES    87%          │
│  09:14:18   HELLO  91%          │
│  09:13:55   HELP   74%          │
│  09:13:41   NO     82%          │
│  09:13:22   REST   99%          │
│                                 │
│  [Clear Session]                │
└─────────────────────────────────┘
```

Real data: populated from prediction results in Live Detection.  
Pass detected words + confidence + timestamp up to a shared state.

---

## Navigation

**Kill the bottom nav** (currently shows Dashboard / Detect / Speech / Settings).  
It implies a complex multi-section app. This is a single-purpose tool.

**Replace with:** Top-right icon only:
- History icon → Word History screen
- When on History → back arrow to return to Live Detection

No dashboard, no settings tab in bottom nav.

---

## What to Remove Entirely

| Component | Reason |
|-----------|--------|
| `login-screen.tsx` | No user accounts exist or are needed |
| `bluetooth-scan.tsx` | Not BLE — it's USB Serial. Entire premise is wrong. |
| `device-connection.tsx` | Fake stats, wrong device framing |
| `bottom-nav.tsx` | Too many tabs for a single-purpose tool |
| `settings-screen.tsx` | Review — keep only backend URL setting |
| Speech synthesis in `speech-output.tsx` | Fake timer, hardcoded history — replace with real word log |
| Dashboard "KEY FEATURES" cards | Wrong framing (Smart Neckband, ECG) |
| Fake accuracy/latency/sensor stats (--/--/--) | They're just dashes — meaningless |

---

## What Needs to Work in Real-Time (from backend)

The backend at `http://localhost:8000` exposes:

| Endpoint | Used by | Status |
|----------|---------|--------|
| `GET /health` | App startup check | ✅ Already wired |
| `GET /model/status` | Model ready indicator | ✅ Already wired |
| `POST /predict_utterance` | Live capture → word | ✅ Already wired |
| `GET /demo/recording` | Replay mode | ✅ Already wired |

No new backend endpoints needed. Only frontend needs to change.

---

## Web Serial (the real hardware bridge)

File: `hooks/use-web-serial.tsx` — **already implemented**.

```
ESP32 (COM9, 921600 baud)
    → USB cable → PC Chrome browser
    → navigator.serial.requestPort()
    → use-web-serial.tsx parses CSV lines (timestamp_us, channel_0)
    → onSample(mv) callback fires at ~860 Hz
    → liveBuf ring buffer fills
    → capture() returns last N seconds of samples
    → POST /predict_utterance → word
```

**Constraint:** Web Serial API only works in:
- Chrome 89+ / Edge 89+ over `localhost` or HTTPS
- Does NOT work in Firefox, Safari, or mobile browsers natively

**For mobile display:** The app can run on a phone pointed at `http://[pc-ip]:3000`
but Web Serial won't work (phone ≠ USB host for ESP32). Options:
- Mobile shows replay mode (demo recordings from backend)
- Mobile shows live predictions PUSHED from PC via WebSocket (not yet built)

---

## Breakpoints

App is `max-w-md mx-auto` — essentially phone-width even on desktop.  
No landscape layout needed. Portrait mobile only.

```css
/* Current — correct */
max-width: 448px   /* ~md breakpoint */
min-height: 100vh
```

This is the right call. Keep it.

---

## Implementation Order

1. **Delete:** login, bluetooth-scan, device-connection screens
2. **Create:** `esp32-connect.tsx` — Web Serial connect screen (real)
3. **Update:** `asv-app.tsx` — new flow: splash → esp32-connect → detection
4. **Update:** `live-detection.tsx` — remove clutter, improve waveform, add history state
5. **Create:** `word-history.tsx` — session log
6. **Delete:** `bottom-nav.tsx`, `speech-output.tsx` (or repurpose)
7. **Update:** `asv-app.tsx` — remove nav, simplify routing

---

## Summary

> **Before:** 8-screen app pretending to be a BLE neckband consumer product with login, fake stats, fake Bluetooth, fake speech playback.

> **After:** 3-screen focused tool — connect the ESP32, watch the EMG, see the word. Matches what `plot_words.py` does, in a mobile-friendly web UI.
