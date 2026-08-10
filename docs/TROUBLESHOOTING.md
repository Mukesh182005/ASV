# ASV Troubleshooting Guide

## Overview

This guide covers common issues encountered during ASV hardware and firmware setup, with step-by-step solutions.

---

## Serial Communication Issues

### Problem: "Port Not Found" or "Upload Failed"

#### Symptom
```
ERROR: Could not find COM port
```

#### Root Causes & Solutions

**Cause 1: USB Driver Not Installed**
1. Check Device Manager on Windows
2. Look for "Unknown Device" or "CH340"
3. Download [CH340 USB Driver](https://github.com/nodemcu/CH340)
4. Install driver and restart computer
5. Reconnect ESP32

**Cause 2: USB Cable Issue**
1. Use a different USB cable (data cable, not power-only)
2. Try a different USB port
3. Avoid USB hubs (use direct port)
4. Test with a different computer

**Cause 3: Port Already in Use**
1. Close Serial Monitor before uploading
2. Restart VS Code
3. Unplug and replug USB

**Solution:**
```bash
# List available ports
pio device list

# Use correct port in platformio.ini
monitor_port = COM3  # Windows
# OR
monitor_port = /dev/ttyUSB0  # Linux
```

---

### Problem: "Garbage" Characters in Serial Monitor

#### Symptom
```
⸮⸮⸮⸮⸮⸮⸮⸮⸮⸮
```

#### Root Causes & Solutions

**Cause 1: Wrong Baud Rate**
- Serial monitor running at 9600, firmware at 115200
- **Solution:** Change to **115200 baud**

**Cause 2: ESP32 Reset**
- Pressing reset button during upload
- **Solution:** Don't touch ESP32 during upload

**Cause 3: Incorrect Port**
- Connected to wrong COM port
- **Solution:** Check Device Manager and select correct port

**Solution:**
```bash
# Set correct baud rate
pio device monitor --baud 115200
```

---

### Problem: "Binary Mismatch" During Upload

#### Symptom
```
ERROR: A fatal error occurred: Invalid head of packet
```

#### Root Causes & Solutions

**Cause 1: Corrupted Flash**
1. Boot ESP32 into bootloader mode:
   - Hold BOOT button
   - Click EN (reset) button
   - Release BOOT button
   - Release EN button
2. Upload again

**Cause 2: Power Supply Issue**
- USB port not providing enough current
- **Solution:** Use powered USB hub

**Solution:**
```bash
# Erase entire flash
pio run --target erase

# Rebuild and upload
pio run --target upload
```

---

## Hardware Detection Issues

### Problem: I2C Devices Not Detected

#### Symptom
```
[I2C] ========== I2C DEVICE SCAN END ===========
[I2C] Total devices found: 0
```

#### Root Causes & Solutions

**Cause 1: GPIO Pins Not Connected**
- Verify GPIO21 (SDA) is connected to I2C bus
- Verify GPIO22 (SCL) is connected to I2C bus
- Check all connections are firm

**Cause 2: Power Not Connected**
- 3.3V not connected to positive rail
- GND not connected to negative rail
- **Solution:** Measure voltage with multimeter

**Cause 3: I2C Pull-up Resistors**
- Missing or incorrect pull-up resistors
- **Solution:** Add 4.7kΩ resistors between SDA-3.3V and SCL-3.3V

**Cause 4: Device Address Conflict**
- Both devices can't be at same address
- **Solution:** Check address selection pins

**Debugging Steps:**
```cpp
// Add to serial output for debugging
Serial.print("SDA Pin: "); Serial.println(21);
Serial.print("SCL Pin: "); Serial.println(22);

// Measure with multimeter:
// - 3.3V rail: should show 3.3V
// - GND: should show 0V
// - SDA line: should show ~3.3V (pulled up)
// - SCL line: should show ~3.3V (pulled up)
```

---

### Problem: ADS1115 Not Found (0x48 Not Detected)

#### Symptom
```
[I2C] Device found at address: 0x3C !
      └─> Identified as: SSD1306 OLED
[I2C] Total devices found: 1
[ADS1115] ERROR: Could not find ADS1115 at 0x48!
```

#### Root Causes & Solutions

**Cause 1: Address Pin Misconfiguration**
- ADDR pin not connected to GND
- **Solution:** Connect ADS1115 ADDR pin to GND for address 0x48

**Address selection for ADS1115:**
```
ADDR Pin Connected To  |  I2C Address
─────────────────────────────────────
GND                    |  0x48  ✓ (Current)
VDD (3.3V)            |  0x49
SDA                    |  0x4A
SCL                    |  0x4B
```

**Cause 2: I2C Communication Failure**
- SDA/SCL not connected properly
- Missing pull-up resistors
- **Solution:** Check all I2C connections

**Cause 3: ADS1115 Not Powered**
- VDD pin not connected to 3.3V
- GND pin not connected to ground
- **Solution:** Verify power connections

**Debugging:**
```bash
# Check with I2C scanner
pio device monitor --baud 115200
# Look for "0x48" in output

# Manually verify with multimeter:
# - ADS1115 VDD: should read 3.3V
# - ADS1115 GND: should read 0V
# - ADS1115 SDA: should read ~3.3V
# - ADS1115 SCL: should read ~3.3V
```

---

### Problem: SSD1306 OLED Not Found (0x3C Not Detected)

#### Symptom
```
[I2C] Device found at address: 0x48 !
      └─> Identified as: ADS1115 ADC
[I2C] Total devices found: 1
[OLED] ERROR: SSD1306 allocation failed!
```

#### Root Causes & Solutions

**Cause 1: Wrong Display Address**
- Display jumpers set to 0x3D instead of 0x3C
- **Solution:** Check SA0 jumper on display

**Address selection for SSD1306:**
```
SA0 Jumper   |  I2C Address
──────────────────────────
Not Connected|  0x3C  ✓ (Current)
Connected    |  0x3D
```

**Cause 2: Display Not Powered**
- VCC not connected to 3.3V
- GND not connected to ground
- **Solution:** Check power connections

**Cause 3: I2C Communication Failure**
- SDA/SCL lines not connected
- I2C frequency too high
- **Solution:** Lower I2C frequency to 100kHz

**Cause 4: Display Defective**
- Rare but possible
- **Solution:** Try different OLED display

**Debugging:**
```bash
# Check for 0x3C in I2C scan
# If not found, try 0x3D:

# Edit ads1115_test.h
#define OLED_ADDR 0x3D  // Change from 0x3C

# Rebuild and upload
pio run --target upload
```

---

## OLED Display Issues

### Problem: Display Powered On But Nothing Shows

#### Symptom
- Display is blank or shows only white/black
- No text visible
- Device appears detected (0x3C found)

#### Root Causes & Solutions

**Cause 1: Contrast Too Low**
- Display initialized but contrast at minimum
- **Solution:** Modify contrast in code

**Cause 2: Display Rotated**
- Text displayed outside visible area
- **Solution:** Adjust rotation parameter

**Cause 3: Display Buffer Not Updated**
- Code writes to buffer but doesn't display
- **Solution:** Ensure `display.display()` called

**Cause 4: Wrong I2C Address**
- Communicating with wrong address
- **Solution:** Try 0x3D instead of 0x3C

**Solution Code:**
```cpp
// Fix contrast (in oled_display.cpp)
display.setContrast(255);  // Max contrast

// Ensure display updates
display.display();  // Required after drawing

// Try different address
#define OLED_ADDR 0x3D  // Change if 0x3C doesn't work
```

---

### Problem: Display Glitches or Corruption

#### Symptom
- Partial text visible
- Random pixels lit
- Display flickers
- Text appears multiple times

#### Root Causes & Solutions

**Cause 1: I2C Noise or Interference**
- Long wires causing signal degradation
- **Solution:** Keep I2C wires short and together

**Cause 2: Inadequate Power Supply**
- Brownout during display refresh
- **Solution:** Add 100µF capacitor near display VCC

**Cause 3: I2C Bus Conflict**
- Multiple devices interfering
- **Solution:** Add termination resistors (4.7kΩ)

**Cause 4: Display Overclocking**
- I2C frequency too high
- **Solution:** Reduce to 100kHz

**Solution:**
```ini
; In platformio.ini
[env:esp32dev]
build_flags =
    -DI2C_FREQUENCY=100000  # Slow down I2C
```

---

## ADC (ADS1115) Issues

### Problem: ADC Readings All Zeros or Max Value

#### Symptom
```
[ADC] Raw: 0 | Voltage: 0.00 mV | BLE: ADVERTISING
[ADC] Raw: 32767 | Voltage: 4095.88 mV | BLE: ADVERTISING
```

#### Root Causes & Solutions

**Cause 1: Analog Input Not Connected**
- A0 pin floating (not connected to anything)
- **Solution:** Connect test signal or ground through resistor

**Cause 2: Wrong Gain Setting**
- Measuring voltage outside of selected range
- **Solution:** Adjust gain or voltage range

**Gain Settings and Ranges:**
```cpp
ads.setGain(GAIN_TWOTHIRDS);  // ±6.144V
ads.setGain(GAIN_ONE);         // ±4.096V (current)
ads.setGain(GAIN_TWO);         // ±2.048V
ads.setGain(GAIN_FOUR);        // ±1.024V
ads.setGain(GAIN_EIGHT);       // ±0.512V
ads.setGain(GAIN_SIXTEEN);     // ±0.256V
```

**Cause 3: ADC Not Connected Properly**
- SDA/SCL not connected to I2C bus
- VDD/GND not powered
- **Solution:** Verify all connections

**Debugging:**
```cpp
// Check ADC configuration
Serial.println("[ADC] Testing read...");
int16_t value = ads.readADC_SingleEnded(0);
Serial.print("[ADC] Raw value: ");
Serial.println(value);

// Should see values between 0-32767
// If always 0 or 32767, check connections
```

---

### Problem: Noisy or Erratic ADC Readings

#### Symptom
```
[ADC] Raw: 512 | Voltage: 64.00 mV
[ADC] Raw: 520 | Voltage: 65.00 mV
[ADC] Raw: 495 | Voltage: 61.88 mV  <- Suddenly different
[ADC] Raw: 518 | Voltage: 64.75 mV
```

#### Root Causes & Solutions

**Cause 1: EMI/RFI Interference**
- Noise from nearby electronics
- Loose wires picking up noise
- **Solution:** Shorten wires, add shielding

**Cause 2: Insufficient Filtering**
- Taking single samples
- **Solution:** Increase averaging samples

**Cause 3: Power Supply Ripple**
- Unstable 3.3V supply
- **Solution:** Add 100µF capacitor near ADS1115 VDD

**Cause 4: High Impedance Input**
- ADC input not properly biased
- **Solution:** Add 10kΩ pull-down resistor to GND

**Solution Code:**
```cpp
// Increase averaging (in ads1115_test.cpp)
int16_t adc_raw = adc_module.readAveraged(20);  // Was 10, now 20

// Or add RC filter:
// 10kΩ resistor + 100nF capacitor to GND on A0
```

---

## BLE Issues

### Problem: BLE Not Advertising

#### Symptom
```
[BLE] Advertising started...
# But no devices appear in BLE scanner
```

#### Root Causes & Solutions

**Cause 1: BLE Disabled in Firmware**
- Check startAdvertising() is called
- **Solution:** Add to setup after BLE initialization

**Cause 2: Device Name Too Long**
- Device name exceeds 20 characters
- **Solution:** Shorten to "ASV-Device" (10 chars)

**Cause 3: Radio Disabled**
- WiFi interference
- **Solution:** Move away from WiFi routers

**Debugging:**
```cpp
// Check BLE status
Serial.println(ble_module.getStatusString());  // Should print "ADVERTISING" or "CONNECTED"

// Verify device name
Serial.println("[BLE] Device name: ASV-Device");
```

---

### Problem: BLE Connects But Disconnects Immediately

#### Symptom
```
[BLE] CLIENT CONNECTED!
[BLE] CLIENT DISCONNECTED!
[BLE] CLIENT CONNECTED!
[BLE] CLIENT DISCONNECTED!
```

#### Root Causes & Solutions

**Cause 1: Memory Leak**
- Insufficient RAM causing crashes
- **Solution:** Add `delay(100)` between connections

**Cause 2: BLE Stack Overflow**
- Too many services/characteristics
- **Solution:** Simplify BLE configuration

**Solution:**
```cpp
// Add delay in onConnect callback
if (pServer) {
    delay(100);  // Give time to settle
}
```

---

## Power and Reset Issues

### Problem: ESP32 Keeps Resetting

#### Symptom
```
ets Jun  8 2016 00:22:57 rst:0x1 (POWERON_RESET),...
[I2C] Scanner initialized...
ets Jun  8 2016 00:22:57 rst:0x1 (POWERON_RESET),...
```

#### Root Causes & Solutions

**Cause 1: Insufficient Power Supply**
- USB power insufficient for BLE
- **Solution:** Use powered USB hub or external 3.3V supply

**Cause 2: Watchdog Timeout**
- Code taking too long in loop
- **Solution:** Add `yield()` calls in loops

**Cause 3: Stack Overflow**
- Too many local variables
- **Solution:** Move to global scope

**Solution:**
```cpp
// In main loop
void loop() {
    yield();  // Feed the watchdog
    // ... rest of loop
}

// Or disable watchdog (not recommended)
// disableWatchdog();
```

---

### Problem: High Current Draw or Rapid Battery Drain

#### Symptom
- Battery dies in minutes
- USB port gets hot
- Current draw >500mA

#### Root Causes & Solutions

**Cause 1: BLE Continuous Scanning**
- High power consumption during scanning
- **Solution:** Reduce scan interval

**Cause 2: I2C Bus Shorted**
- SDA/SCL shorted together or to ground
- **Solution:** Check wiring for shorts

**Cause 3: Weak 3.3V Supply**
- Voltage regulator overheating
- **Solution:** Use higher capacity regulator

**Typical Current Consumption:**
```
Idle:           20-30 mA
BLE Advertising: 50-100 mA  ← Normal
With OLED:      10-15 mA additional
With ADC:       1-2 mA additional
Total Expected: 80-150 mA
```

---

## Debugging Techniques

### Technique 1: Serial Print Debugging

Add strategic print statements:
```cpp
void loop() {
    Serial.println("[DEBUG] Starting ADC read");
    int16_t val = adc_module.readValue();
    Serial.println("[DEBUG] ADC read complete: " + String(val));
    
    Serial.println("[DEBUG] Updating display");
    oled_display.showStatus(ble_module.isConnected(), ads_connected, val);
    Serial.println("[DEBUG] Display updated");
}
```

### Technique 2: LED Indicator

Use LED to indicate status:
```cpp
#define LED_PIN 5

void setup() {
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, HIGH);  // Indicate startup
}

void loop() {
    digitalWrite(LED_PIN, LOW);   // Indicate processing
    // ... code ...
    digitalWrite(LED_PIN, HIGH);  // Indicate ready
    delay(100);
}
```

### Technique 3: Multimeter Measurements

Verify with multimeter:
```
Measurement          |  Expected      | Action
─────────────────────────────────────────────────
3.3V rail            |  3.2-3.4V      | Check regulator
GND connection       |  0V            | Check continuity
SDA line voltage     |  ~3.3V resting | Add resistor if <1V
SCL line voltage     |  ~3.3V resting | Add resistor if <1V
Current draw (USB)   |  <500mA        | Check for shorts
```

---

## Recovery Procedures

### Full Factory Reset

```bash
# 1. Erase entire flash
pio run --target erase

# 2. Rebuild firmware
pio run

# 3. Upload fresh
pio run --target upload
```

### Bootloader Mode (if stuck)

1. Hold **BOOT** button on ESP32
2. Click **EN** (reset) button
3. Release **BOOT** button
4. Release **EN** button
5. Upload again

### Manual Serial Recovery

```bash
# Use Python to interact with ESP32
python -m serial.tools.list_ports  # List ports

# Connect to serial
python -m serial.tools.miniterm COM3 115200

# Try sending reset command
```

---

## Performance Optimization

### If System is Too Slow

1. **Reduce ADC Averaging:**
   ```cpp
   int16_t adc = adc_module.readAveraged(5);  // Reduce from 10
   ```

2. **Increase Update Interval:**
   ```cpp
   #define LOOP_DELAY_MS 250  // Reduce from 500
   ```

3. **Disable OLED Updates:**
   ```cpp
   if (false) {  // Temporarily disable
       oled_display.showStatus(...);
   }
   ```

### If System Uses Too Much Power

1. **Sleep Between Reads:**
   ```cpp
   delay(LOOP_DELAY_MS);  // Processor sleeps
   ```

2. **Reduce BLE Advertising:**
   ```cpp
   // Modify BLE to advertise less frequently
   ```

3. **Dim OLED Display:**
   ```cpp
   display.setContrast(100);  // Reduce from 255
   ```

---

## When to Ask for Help

If you've tried all troubleshooting steps:

1. **Collect diagnostic information:**
   ```bash
   # Save entire serial output
   pio device monitor --baud 115200 > debug.log
   
   # Note down:
   # - ESP32 Chip ID
   # - I2C addresses found
   # - Error messages
   ```

2. **Document your setup:**
   - Photo of breadboard connections
   - Voltmeter readings
   - USB power source used

3. **Ask with details:**
   - "After [X steps], I get [Y error]"
   - "I've verified [connections/power/addresses]"
   - "Baud rate/port: [info]"

---

## Quick Reference Checklist

Before declaring "not working":

- [ ] USB cable connected and detected
- [ ] Correct COM port in platformio.ini
- [ ] Baud rate set to 115200
- [ ] 3.3V measured on power rail
- [ ] GND connected
- [ ] GPIO21/GPIO22 connected to I2C bus
- [ ] ADS1115 at 0x48 detected
- [ ] SSD1306 at 0x3C detected
- [ ] OLED showing text (check contrast)
- [ ] ADC showing non-zero values
- [ ] BLE advertising or connected

If all checked, create issue with full serial output.

---

*Last Updated: 2024*
*ASV Development Team*
