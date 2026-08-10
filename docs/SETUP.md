# ASV Firmware Setup and Compilation Guide

## Overview

This guide provides step-by-step instructions for setting up the ASV firmware development environment, compiling the code, and uploading to your ESP32 device.

---

## Prerequisites Checklist

### Hardware
- [ ] ESP32 DevKit V1
- [ ] ADS1115 ADC Module
- [ ] SSD1306 128x64 OLED Display
- [ ] Breadboard with jumper wires
- [ ] USB Type-B cable for ESP32
- [ ] All devices connected per HARDWARE_SETUP.md

### Software
- [ ] Windows/Linux/macOS with USB support
- [ ] VS Code installed
- [ ] Internet connection for package downloads

### Drivers (Windows)
- [ ] CH340 USB-to-Serial driver installed

---

## Step-by-Step Installation

### Step 1: Install VS Code

**If not already installed:**

1. Download from https://code.visualstudio.com/
2. Run installer and follow prompts
3. Choose "Add to PATH" during installation
4. Complete installation

---

### Step 2: Install PlatformIO IDE

**In VS Code:**

1. Click **Extensions** icon (left sidebar, 4 squares)
2. Search for **"PlatformIO IDE"**
3. Click **Install** (by PlatformIO)
4. Wait for installation to complete
5. Reload VS Code when prompted
6. Click the **PlatformIO icon** (ant logo) to verify

**First-time setup:**
- PlatformIO will download additional tools
- This may take 2-5 minutes
- Check status in the bottom status bar

---

### Step 3: Install USB Drivers (Windows Only)

**For ESP32 CH340 chip:**

1. Check Device Manager for unknown device
2. Download [CH340 driver](https://github.com/nodemcu/CH340)
3. Extract and run installer
4. Restart computer
5. Verify port appears as COM3, COM4, etc.

**For Linux:**
- Drivers usually included with OS
- Verify with: `ls /dev/ttyUSB*` or `ls /dev/ttyACM*`

**For macOS:**
- Drivers usually included
- Verify with: `ls /dev/tty.usbserial*`

---

### Step 4: Verify Hardware Connections

**Before proceeding, verify:**

1. ✓ ESP32 powered and connected via USB
2. ✓ ADS1115 connected:
   - VDD → 3.3V
   - GND → Ground
   - SDA → GPIO21
   - SCL → GPIO22
3. ✓ SSD1306 connected:
   - VCC → 3.3V
   - GND → Ground
   - SDA → GPIO21
   - SCL → GPIO22

See [HARDWARE_SETUP.md](HARDWARE_SETUP.md) for detailed wiring.

---

### Step 5: Configure PlatformIO for Your Device

1. **Open ASV Project Folder**
   - File → Open Folder
   - Navigate to `c:\Users\sagar\ASV`
   - Click Open

2. **Update Serial Port Configuration**
   - Open `firmware/platformio.ini`
   - Find the line: `monitor_port = COM3`
   - Change `COM3` to your actual port:
     - **Windows:** Check Device Manager for COM port
     - **Linux:** Usually `/dev/ttyUSB0` or `/dev/ttyACM0`
     - **macOS:** `/dev/tty.usbserial-XXXXX`

3. **Save the file** (Ctrl+S)

---

## Building the Firmware

### Method 1: Using PlatformIO GUI (Recommended)

**In VS Code:**

1. Open the **PlatformIO: Home** tab (icon on left sidebar)
2. Click on ASV project (should auto-detect)
3. Or navigate to `firmware/` folder
4. Click **Build** button (checkmark icon)
   - Alternatively: Press `Ctrl+Alt+B`

**Building process:**
```
Starting PlatformIO build...
Building ASV firmware...
Compiling source files...
Linking...
Checking size...
BUILD SUCCESSFUL
```

**Expected build time:** 30-60 seconds first build, 5-10 seconds subsequent

---

### Method 2: Using Terminal

**In Terminal/PowerShell:**

```bash
# Navigate to firmware directory
cd c:\Users\sagar\ASV\firmware

# Clean previous build
pio run --target clean

# Build project
pio run

# Expected output:
# Building ASV firmware...
# BUILD SUCCESSFUL
```

---

## Uploading Firmware to ESP32

### Method 1: Using PlatformIO GUI

1. **In VS Code**, click **Upload** button (arrow icon)
   - Alternatively: Press `Ctrl+Alt+U`

2. **Watch upload progress:**
   ```
   Uploading firmware...
   esptool.py v4.0
   Connecting to ESP32...
   Uploading 100%
   UPLOAD SUCCESSFUL
   ```

3. **If upload fails:**
   - Unplug USB, wait 2 seconds
   - Replug USB
   - Try again
   - See TROUBLESHOOTING.md if still failing

---

### Method 2: Using Terminal

```bash
# In firmware directory
cd c:\Users\sagar\ASV\firmware

# Upload to device
pio run --target upload

# If successful, you should see:
# Uploading 100%
# UPLOAD SUCCESSFUL
```

---

### Method 3: Manual Upload (If Auto-Upload Fails)

1. **Put ESP32 in Bootloader Mode:**
   - Hold **BOOT** button on ESP32
   - Press **EN** (reset) button
   - Release **BOOT** button
   - Release **EN** button

2. **Upload:**
   ```bash
   pio run --target upload
   ```

3. **Reset ESP32:**
   - Press **EN** button to restart

---

## Verifying Successful Upload

### Checking Serial Monitor

1. **Open Serial Monitor:**
   - In VS Code: `Ctrl+Alt+S`
   - Or: PlatformIO icon → Serial Monitor

2. **Verify Output:**
   ```
   [STARTUP] Initializing ESP32 firmware...
   [I2C] Device found at address: 0x48 !
         └─> Identified as: ADS1115 ADC
   [I2C] Device found at address: 0x3C !
         └─> Identified as: SSD1306 OLED
   [STATUS] System Status:   ✓ READY
   ```

3. **Check OLED Display:**
   - Should display: "ASV READY"
   - Should show: "BLE INITIALIZED"
   - Should show: "ADS1115 CONNECTED"

4. **Check ADC Output:**
   ```
   [ADC] Raw: 512 | Voltage: 64.00 mV | BLE: ADVERTISING
   ```

If you see this, **firmware is working correctly!** ✅

---

## Serial Monitor Usage

### Basic Controls

| Command | Action |
|---------|--------|
| Type text | Send to ESP32 |
| Enter | Send command |
| Ctrl+L | Clear screen |
| Ctrl+C | Exit monitor |

### Baud Rate

- **Must be 115200** (already configured)
- If seeing garbage characters, verify this setting

### Saving Output

**To save output to file:**

```bash
# Terminal method
pio device monitor --baud 115200 > output.log

# In VS Code
# Click menu → ... → Save output
```

---

## Troubleshooting Build Issues

### Problem: "Port not found"

```
ERROR: Upload could not be completed. Port not found.
```

**Solution:**
1. Verify USB cable is connected
2. Check `platformio.ini` has correct port
3. In Device Manager, find your ESP32 COM port
4. Update `monitor_port = COM3` accordingly

### Problem: "Cannot access port"

```
ERROR: Cannot access port COM3 (Permission denied)
```

**Solution:**
1. Close Serial Monitor or other terminal programs
2. Wait 2 seconds
3. Try upload again
4. If persistent, restart VS Code

### Problem: Build fails with library errors

```
fatal error: Adafruit_SSD1306.h: No such file or directory
```

**Solution:**
1. Close VS Code completely
2. Delete `.pio/` folder in `firmware/`
3. Reopen VS Code
4. Wait for PlatformIO to reinitialize
5. Try build again

### Problem: "esptool error"

```
ERROR: A fatal error occurred: Invalid head of packet
```

**Solution:**
1. Erase flash: `pio run --target erase`
2. Wait 30 seconds
3. Upload: `pio run --target upload`

---

## Advanced Configuration

### Changing Board Type

Edit `firmware/platformio.ini`:

```ini
[env:esp32dev]
board = esp32doit-devkit1  # Your board type

# Other board options:
# board = esp32
# board = esp32s2
# board = esp32s3
```

### Changing Serial Port Dynamically

```bash
# Override port when running command
pio run --target upload --upload-port COM4

# Or specify in command
pio device monitor --baud 115200 --port COM4
```

### Optimizing for Size

```ini
build_flags =
    -Os              # Optimize for size
    -DCORE_DEBUG_LEVEL=ARDUHAL_LOG_LEVEL_ERROR
```

### Debug Build

```ini
[env:debug]
extends = esp32dev
build_type = debug
build_flags =
    -DDEBUG_ON
    -g
    -O0
```

Then build with: `pio run -e debug`

---

## Development Workflow

### Quick Iteration Loop

1. **Make code change** in `firmware/src/`
2. **Build:** `pio run` (Ctrl+Alt+B)
3. **Upload:** `pio run --target upload` (Ctrl+Alt+U)
4. **Monitor:** `pio device monitor` (Ctrl+Alt+S)
5. **View results** in Serial Monitor
6. **Repeat**

### Time Estimation

| Step | Time |
|------|------|
| Code edit | Variable |
| Compile | 5-60 seconds |
| Upload | 5-10 seconds |
| Serial view | Immediate |
| **Total cycle** | **15-80 seconds** |

---

## Project File Organization

```
ASV/firmware/
├── platformio.ini           # Main configuration ← EDIT THIS
├── include/
│   ├── i2c_scanner.h       # I2C device scanning
│   ├── oled_display.h      # OLED driver
│   ├── ads1115_test.h      # ADC driver
│   └── ble_test.h          # BLE module
├── src/
│   ├── main.cpp            # ← START EDITING HERE
│   ├── i2c_scanner.cpp     # I2C implementation
│   ├── oled_display.cpp    # Display implementation
│   ├── ads1115_test.cpp    # ADC implementation
│   └── ble_test.cpp        # BLE implementation
├── .pio/                   # Build artifacts (auto-generated)
└── .vscode/                # VS Code settings
```

---

## Common Code Modifications

### Changing ADC Sampling Rate

**File:** `firmware/src/main.cpp`

```cpp
// Find in loop():
int16_t adc_raw = adc_module.readAveraged(ADC_SAMPLES);
                                           // ^
// Change ADC_SAMPLES (line 7):
#define ADC_SAMPLES 10  // Increase for more averaging
```

### Changing I2C Speed

**File:** `firmware/src/main.cpp`

```cpp
// Find at top:
#define I2C_FREQUENCY 100000  // Change this to:
// 100000 = 100 kHz (standard)
// 200000 = 200 kHz (fast)
// 400000 = 400 kHz (very fast)
```

### Changing Display Update Rate

**File:** `firmware/src/main.cpp`

```cpp
// In loop():
if (current_time - last_update_time >= 500) {  // 500ms interval
    // Change to: 1000 (slower) or 250 (faster)
}
```

---

## Performance Optimization

### Faster Compilation

```bash
# Clean build cache
pio run --target clean

# Use single-threaded build (less CPU)
pio run -e esp32dev -j1
```

### Smaller Binary

```ini
; Add to platformio.ini
build_flags =
    -Os              ; Optimize for size
    -Wl,--gc-sections  ; Remove unused code
```

### Faster Upload

```ini
; Increase upload speed (if stable)
upload_speed = 921600  ; Default
; Or try: 460800 for slower connections
```

---

## Quality Assurance

### Pre-Upload Checks

Before uploading, ensure:

- [ ] Code compiles without errors: `pio run`
- [ ] Hardware is connected per HARDWARE_SETUP.md
- [ ] Correct port is in platformio.ini
- [ ] USB cable is reliable
- [ ] ESP32 is not running other tasks

### Post-Upload Verification

After upload, verify:

- [ ] Serial output appears at 115200 baud
- [ ] I2C devices detected (0x48 and 0x3C)
- [ ] OLED display shows status
- [ ] ADC readings printing
- [ ] No error messages in serial output

---

## Getting Help

### Debug Output

To capture full debug output:

```bash
# Save to file
pio run --verbose 2>&1 | Tee build_log.txt

# This shows compiler and linker details
```

### Clean Rebuild

If experiencing strange issues:

```bash
# Complete clean rebuild
rm -rf firmware/.pio firmware/build
pio run
pio run --target upload
```

### Check Dependencies

```bash
# List all installed libraries
pio lib list

# Update all libraries
pio lib update
```

---

## Next Steps After Setup

1. ✅ **Verify firmware works** (serial monitor shows data)
2. → **Integrate AD8232 EMG sensor** (when available)
3. → **Test signal processing** (ml/ directory)
4. → **Build mobile UI** (frontend/ directory)
5. → **Deploy to production** (security review needed)

---

## References

- [PlatformIO CLI Reference](https://docs.platformio.org/en/latest/core/cli/index.html)
- [ESP32 Arduino Framework](https://docs.espressif.com/projects/arduino-esp32/)
- [VS Code Settings](https://code.visualstudio.com/docs/editor/settings)

---

## Command Cheat Sheet

### Most Used Commands

```bash
# Build
pio run
pio run --target clean

# Upload
pio run --target upload
pio run --target erase

# Monitor
pio device monitor
pio device list

# Development
pio run && pio run --target upload  # Build and upload

# Full cycle
pio run && pio run --target upload && pio device monitor
```

---

## Conclusion

You now have a fully functional development environment for ASV firmware! 

**Next:** Upload the firmware using [QUICK_START.md](QUICK_START.md) or [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if issues arise.

---

*Last Updated: 2024*
*ASV Development Team*
