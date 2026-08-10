# ASV GPIO and I2C Address Mapping

## GPIO Pin Assignment

### I2C Communication Pins
| ESP32 GPIO | Function | I2C Role | Connected To |
|-----------|----------|----------|--------------|
| GPIO 21 | I2C Serial Data | SDA | ADS1115, SSD1306 |
| GPIO 22 | I2C Serial Clock | SCL | ADS1115, SSD1306 |

### Power and Ground
| ESP32 Pin | Function | Usage |
|-----------|----------|-------|
| 3.3V | Power Supply | Breadboard Positive Rail |
| GND | Ground | Breadboard Negative Rail |

### Reserved Pins (Future Use)
| GPIO | Purpose | Status |
|-----|---------|--------|
| GPIO 34 | ADC Input | Available for future sensors |
| GPIO 35 | ADC Input | Available for future sensors |
| GPIO 32 | ADC Input | Available for future sensors |
| GPIO 33 | ADC Input | Available for future sensors |

---

## I2C Address Map

### Active Devices
| Device | I2C Address | Hex | Binary | Status |
|--------|------------|-----|--------|--------|
| ADS1115 ADC | 72 | 0x48 | 1001000 | **ACTIVE** ✓ |
| SSD1306 OLED | 60 | 0x3C | 0111100 | **ACTIVE** ✓ |

### Address Configuration

#### ADS1115 (Texas Instruments)
```
Address Selection via ADDR Pin:
┌─────────────────┬──────────────┐
│   ADDR Pin      │  I2C Address │
├─────────────────┼──────────────┤
│ GND (0V)        │ 0x48 (72)    │ ← Current Configuration
│ VDD (3.3V)      │ 0x49 (73)    │
│ SDA             │ 0x4A (74)    │
│ SCL             │ 0x4B (75)    │
└─────────────────┴──────────────┘
```

#### SSD1306 OLED (Solomon Systech)
```
Address Selection:
┌─────────────────┬──────────────┐
│   Jumper SA0    │  I2C Address │
├─────────────────┼──────────────┤
│ Not Connected   │ 0x3C (60)    │ ← Current Configuration
│ Connected       │ 0x3D (61)    │
└─────────────────┴──────────────┘
```

---

## I2C Bus Configuration

### Timing Parameters
| Parameter | Value | Unit |
|-----------|-------|------|
| Bus Speed (Standard Mode) | 100 | kHz |
| Rise Time | ~1 | µs |
| Fall Time | ~1 | µs |
| Hold Time | ~300 | ns |

### Pull-up Resistors
| Line | Recommended | Implementation |
|------|-------------|-----------------|
| SDA (GPIO21) | 4.7 kΩ | Optional (internal pullup available) |
| SCL (GPIO22) | 4.7 kΩ | Optional (internal pullup available) |

---

## ADS1115 Analog Input Channels

### Channel Mapping
| Channel | GPIO/Pin | Purpose | Current Status |
|---------|----------|---------|-----------------|
| A0 | AIN0 | EMG Signal Primary Input | Ready for AD8232 |
| A1 | AIN1 | Available | Reserved |
| A2 | AIN2 | Available | Reserved |
| A3 | AIN3 | Available | Reserved |

### Single-Ended Mode (Current)
```
Each channel measures voltage relative to GND:

┌─────────────────────────┐
│ A0 ──→ [ADC] ──→ 0-32767 │
│ A1 ──→ [ADC] ──→ 0-32767 │
│ A2 ──→ [ADC] ──→ 0-32767 │
│ A3 ──→ [ADC] ──→ 0-32767 │
└─────────────────────────┘
```

### Gain Settings (ADS1115)
| Gain | Voltage Range | Resolution/LSB | Current Setting |
|------|---------------|-----------------|-----------------|
| GAIN_ONE | ±4.096V | 0.125 mV | ✓ Active |
| GAIN_TWOTHIRDS | ±6.144V | 0.1875 mV | Alternative |
| GAIN_TWO | ±2.048V | 0.0625 mV | Alternative |
| GAIN_FOUR | ±1.024V | 0.03125 mV | Alternative |
| GAIN_EIGHT | ±0.512V | 0.015625 mV | Alternative |
| GAIN_SIXTEEN | ±0.256V | 0.0078125 mV | Alternative |

---

## SSD1306 OLED Display Configuration

### Display Specifications
| Property | Value |
|----------|-------|
| Resolution | 128 x 64 pixels |
| Color Depth | Monochrome (1-bit) |
| Controller | SSD1306 |
| Interface | I2C |
| Operating Voltage | 3.3V |
| Address (with SA0=0) | 0x3C |

### Memory Layout
```
Display Buffer (128 × 64 pixels):
┌─ Text Display ─────────────────────────────┐
│                                             │
│  Row 0-7 (8 pixels tall):   8 pages       │
│  Row 8-15:                   8 pages       │
│  Row 16-23:                  8 pages       │
│  Row 24-31:                  8 pages       │
│  Row 32-39:                  8 pages       │
│  Row 40-47:                  8 pages       │
│  Row 48-55:                  8 pages       │
│  Row 56-63:                  8 pages       │
│                                             │
└─────────────────────────────────────────────┘
 0                 64                        127
```

---

## BLE Configuration

### BLE Device Information
| Parameter | Value |
|-----------|-------|
| Device Name | "ASV-Device" |
| Service UUID | 180A (Device Information) |
| Characteristic UUID | 2A29 (Manufacturer Name) |
| Tx Power | -12 to +9 dBm |

---

## Code Constants

### Header Files Location
```
firmware/include/
├── i2c_scanner.h       (I2C scanning)
├── oled_display.h      (SSD1306 driver)
├── ads1115_test.h      (ADS1115 driver)
└── ble_test.h          (BLE module)
```

### Main Configuration (main.cpp)
```cpp
#define I2C_SDA_PIN 21              // GPIO21
#define I2C_SCL_PIN 22              // GPIO22
#define I2C_FREQUENCY 100000        // 100 kHz
#define LOOP_DELAY_MS 500           // 500ms main loop
#define ADC_SAMPLES 10              // 10-sample averaging
```

---

## Device Discovery

### I2C Bus Scan Order
On startup, the firmware scans in this order:
```
1. Initialize I2C Bus (GPIO21/GPIO22 @ 100kHz)
2. Scan address 0x00 → 0x7F
3. Record all responsive addresses
4. Identify known devices by address
5. Print results to Serial Monitor
```

Expected output:
```
[I2C] Device found at address: 0x48 !
      └─> Identified as: ADS1115 ADC

[I2C] Device found at address: 0x3C !
      └─> Identified as: SSD1306 OLED

[I2C] Total devices found: 2
```

---

## Verification Commands

### Check I2C Bus
```
# Print all detected devices
Serial Monitor Output: "I2C Device Scan" section
```

### Check ADS1115
```
# Look for continuous ADC readings
[ADC] Raw: 512 | Voltage: 64.00 mV | BLE: ADVERTISING
```

### Check SSD1306
```
# Display should show:
ASV READY
BLE INITIALIZED
ADS1115 CONNECTED
```

---

## Hardware Address Constants (Code Reference)

```cpp
// I2C Address Definitions
#define OLED_ADDR 0x3C              // SSD1306 address
#define ADS_ADDR 0x48               // ADS1115 address

// I2C Pin Definitions
#define I2C_SDA_PIN 21
#define I2C_SCL_PIN 22

// BLE Configuration
#define BLE_DEVICE_NAME "ASV-Device"
#define SERVICE_UUID "180a"
#define CHAR_UUID "2a29"
```

---

## Troubleshooting Quick Reference

| Issue | Check | Command |
|-------|-------|---------|
| I2C Device Not Found | Serial Monitor | Look for "Device found at address:" |
| Wrong Address | Hardware | Verify pin connections |
| No I2C Communication | Power | Check 3.3V and GND |
| Display Not Showing | I2C Bus | Run I2C scanner, verify 0x3C |
| ADC Not Reading | I2C Bus | Run I2C scanner, verify 0x48 |

---

*Last Updated: 2024*
*ASV Development Team*
