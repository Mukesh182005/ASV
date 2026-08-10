# ASV Quick Start Guide

## Prerequisites

### Software Required
- [PlatformIO IDE](https://platformio.org/) (VS Code extension)
- Python 3.8+ (usually included with PlatformIO)
- USB Serial Driver for ESP32

### Hardware Required
- ESP32 DevKit V1 (USB Type-B Cable)
- ADS1115 ADC Module
- SSD1306 128x64 OLED Display
- Breadboard with jumper wires
- 3.3V Power Supply

---

## Installation Steps

### Step 1: Install PlatformIO

1. **Open VS Code**
2. **Install PlatformIO Extension:**
   - Click Extensions icon (left sidebar)
   - Search for "PlatformIO"
   - Click Install

### Step 2: Connect Hardware

1. **Connect ESP32 to Computer:**
   - Plug USB cable into ESP32
   - Plug other end into computer USB port

2. **Verify Port Detection:**
   - **Windows:** Check Device Manager → COM ports
   - **Linux:** Run `ls /dev/ttyUSB*` or `ls /dev/ttyACM*`
   - **Mac:** Run `ls /dev/tty.usbserial*`

3. **Update platformio.ini (if needed):**
   ```ini
   monitor_port = COM3  # Windows
   # OR
   monitor_port = /dev/ttyUSB0  # Linux
   # OR  
   monitor_port = /dev/tty.usbserial-XXXXX  # Mac
   ```

### Step 3: Build and Upload Firmware

#### Method 1: Using PlatformIO IDE

```bash
# 1. Open project folder
# 2. Navigate to firmware/ directory
# 3. Build project
PlatformIO: Build (Ctrl+Alt+B)

# 4. Upload to device
PlatformIO: Upload (Ctrl+Alt+U)

# 5. Open Serial Monitor
PlatformIO: Serial Monitor (Ctrl+Alt+S)
```

#### Method 2: Using Terminal

```bash
# Navigate to firmware directory
cd c:\Users\sagar\ASV\firmware

# Build project
pio run

# Upload to ESP32
pio run --target upload

# Monitor serial output
pio device monitor --baud 115200
```

---

## Expected Output

### Serial Monitor (115200 baud)

After successful upload, you should see:

```
════════════════════════════════════════════════════════════
  ASV - A SILENT VOICE
════════════════════════════════════════════════════════════
[STARTUP] Initializing ESP32 firmware...

════════════════════════════════════════════════════════════
  SYSTEM INFORMATION
════════════════════════════════════════════════════════════
[INFO] Device: ESP32 DevKit V1
[INFO] Firmware: ASV Silent Speech Recognition
[INFO] Version: 1.0.0
[INFO] Board: esp32doit-devkit1
[INFO] Chip ID: 1A2B3C4D
[INFO] Flash Size: 4 MB
[INFO] Free RAM: 325 KB

════════════════════════════════════════════════════════════
  STEP 1: I2C BUS INITIALIZATION
════════════════════════════════════════════════════════════
[I2C] Initializing I2C bus...
[I2C] Configuration:
[I2C]   - SDA Pin: GPIO21
[I2C]   - SCL Pin: GPIO22
[I2C]   - Frequency: 100 kHz

[I2C] ========== I2C DEVICE SCAN START ==========
[I2C] Scanning addresses 0x00 to 0x7F...

[I2C] Device found at address: 0x48 !
      └─> Identified as: ADS1115 ADC
[I2C] Device found at address: 0x3C !
      └─> Identified as: SSD1306 OLED

[I2C] ========== I2C DEVICE SCAN END ===========
[I2C] Total devices found: 2

════════════════════════════════════════════════════════════
  STEP 2: OLED DISPLAY INITIALIZATION
════════════════════════════════════════════════════════════
[OLED] Initializing SSD1306 128x64 display...
[OLED] Successfully initialized at 0x3C
[OLED] ✓ Display initialized successfully

════════════════════════════════════════════════════════════
  STEP 3: ADS1115 ADC INITIALIZATION
════════════════════════════════════════════════════════════
[ADS1115] Initializing 16-bit ADC module...
[ADS1115] Successfully initialized at 0x48
[ADS1115] Configuration:
         - Gain: +/- 4.096V
         - Channel: A0 (single-ended)
         - Resolution: 16-bit
[ADS1115] ✓ ADC initialized successfully

════════════════════════════════════════════════════════════
  STEP 4: BLUETOOTH LOW ENERGY (BLE) INITIALIZATION
════════════════════════════════════════════════════════════
[BLE] Initializing Bluetooth Low Energy...
[BLE] Device name set to: ASV-Device
[BLE] Service created with UUID: 180a
[BLE] Characteristic created with UUID: 2a29
[BLE] Initialization complete!
[BLE] Advertising started...
[BLE] Device name: ASV-Device
[BLE] ✓ BLE initialized successfully

════════════════════════════════════════════════════════════
  SYSTEM STATUS
════════════════════════════════════════════════════════════
[STATUS] I2C Bus:         ✓ READY
[STATUS] OLED Display:    ✓ READY
[STATUS] ADS1115 ADC:     ✓ READY
[STATUS] BLE Module:      ✓ READY
[STATUS] System Status:   ✓ READY

✓ ALL SYSTEMS OPERATIONAL - READY FOR TESTING

════════════════════════════════════════════════════════════

[ADC] Raw: 512 | Voltage: 64.00 mV | BLE: ADVERTISING
[ADC] Raw: 510 | Voltage: 63.75 mV | BLE: ADVERTISING
[ADC] Raw: 514 | Voltage: 64.25 mV | BLE: ADVERTISING
[LOOP] Iterations: 20 | Uptime: 10 seconds
```

### OLED Display

Display should show:
```
═══════════════════
BLE: ADVERTISING
ADS1115: READY
ADC: 512 mV
═══════════════════
SYSTEM: READY
```

---

## Serial Monitor Usage

### Opening Serial Monitor

**In VS Code:**
1. Open PlatformIO: Serial Monitor (Ctrl+Alt+S)
2. Baud rate should be set to **115200**
3. Select your COM port

**Using Terminal:**
```bash
pio device monitor --baud 115200 --port COM3
# OR
pio device monitor --baud 115200 --port /dev/ttyUSB0
```

### Serial Monitor Commands

| Feature | How to Use |
|---------|-----------|
| Send command | Type in monitor and press Enter |
| Clear screen | Press Ctrl+L |
| Exit monitor | Press Ctrl+C |
| Change baud | Close and reopen with different rate |

### Interpreting Output

```
[COMPONENT] [LOG_LEVEL] Message
```

Log levels:
- `[INFO]` - Informational message
- `[ERROR]` - Error condition
- `[ADC]` - Analog-to-Digital Converter reading
- `[OLED]` - Display output
- `[I2C]` - I2C bus communication
- `[BLE]` - Bluetooth Low Energy status

---

## Troubleshooting

### Problem: Port Not Found

**Solution:**
1. Check USB cable is connected
2. Install [CH340 USB Driver](https://github.com/nodemcu/CH340)
3. Restart VS Code
4. Check Device Manager for unknown device

### Problem: Upload Fails

**Solution:**
1. Disconnect all other USB devices
2. Use a powered USB hub
3. Try different USB cable
4. Hold boot button on ESP32 during upload

### Problem: Garbage in Serial Monitor

**Solution:**
1. Change baud rate to 115200
2. Check correct port is selected
3. Power cycle ESP32

### Problem: I2C Devices Not Found

**Solution:**
1. Check hardware connections (see HARDWARE_SETUP.md)
2. Verify GPIO21 and GPIO22 are connected correctly
3. Check 3.3V power supply
4. Try adding 4.7kΩ pull-up resistors

### Problem: OLED Display Not Showing

**Solution:**
1. Verify I2C address is 0x3C
2. Check display contrast (not too low)
3. Look for "0x3C" in serial output
4. Try different display address: 0x3D

---

## Development Workflow

### Making Changes to Code

1. **Edit Source File:**
   ```
   firmware/src/main.cpp
   firmware/src/oled_display.cpp
   firmware/src/ads1115_test.cpp
   firmware/src/ble_test.cpp
   ```

2. **Rebuild:**
   ```bash
   pio run
   ```

3. **Upload:**
   ```bash
   pio run --target upload
   ```

4. **Monitor:**
   ```bash
   pio device monitor --baud 115200
   ```

---

## Project Structure

```
ASV/
├── firmware/
│   ├── platformio.ini          (PlatformIO configuration)
│   ├── include/                (Header files)
│   │   ├── i2c_scanner.h
│   │   ├── oled_display.h
│   │   ├── ads1115_test.h
│   │   └── ble_test.h
│   └── src/                    (Source files)
│       ├── main.cpp            (Main program)
│       ├── i2c_scanner.cpp
│       ├── oled_display.cpp
│       ├── ads1115_test.cpp
│       └── ble_test.cpp
├── docs/
│   ├── HARDWARE_SETUP.md
│   ├── GPIO_MAPPING.md
│   ├── QUICK_START.md          (You are here)
│   └── TROUBLESHOOTING.md
└── ml/
    (Machine Learning modules)
```

---

## Next Steps

1. ✓ **Complete Hardware Setup** (see HARDWARE_SETUP.md)
2. ✓ **Upload Firmware** (this guide)
3. ✓ **Verify Serial Output** (check expectations above)
4. → **Integrate AD8232 EMG Sensor** (when available)
5. → **Develop Signal Processing** (ml/ directory)
6. → **Build Frontend Application** (frontend/ directory)

---

## Getting Help

If you encounter issues:

1. **Check Serial Monitor output** for error messages
2. **Review HARDWARE_SETUP.md** for wiring verification
3. **See TROUBLESHOOTING.md** for common issues
4. **Check PlatformIO documentation** at https://docs.platformio.org/

---

## Performance Benchmarks

| Metric | Value | Notes |
|--------|-------|-------|
| Boot Time | ~2 seconds | From power-on to "READY" |
| ADC Sample Rate | ~100 Hz | With 10-sample averaging |
| OLED Update Rate | 2 Hz | Every 500ms |
| BLE Advertising | Continuous | Until connected |
| Current Draw | ~100 mA | Average during operation |

---

## Useful Resources

- [PlatformIO Documentation](https://docs.platformio.org/)
- [ESP32 Arduino Core](https://docs.espressif.com/projects/arduino-esp32/)
- [Adafruit Libraries](https://github.com/adafruit)
- [I2C Protocol Guide](https://en.wikipedia.org/wiki/I%C2%B2C)

---

*Last Updated: 2024*
*ASV Development Team*
