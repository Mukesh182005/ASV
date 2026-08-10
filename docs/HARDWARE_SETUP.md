# ASV - Hardware Setup Guide

## Overview
This guide covers the complete hardware setup for the ASV (A Silent Voice) silent speech recognition system prototype using ESP32, ADS1115 ADC, and SSD1306 OLED display.

---

## Components Required

### Already Available
- ✓ ESP32 DevKit V1
- ✓ ADS1115 ADC Module (16-bit I2C)
- ✓ SSD1306 OLED Display (128x64, I2C)
- ✓ Breadboard
- ✓ Jumper Wires (Male-to-Male, Male-to-Female)
- ✓ LiPo Battery
- ✓ TP4056 Charging Module
- ✓ AMS1117 3.3V Voltage Regulator
- ✓ Resistors and Capacitors

### Not Yet Available
- ✗ AD8232 EMG Sensor (for future implementation)

---

## Pin Configuration

### ESP32 I2C Pins
| Function | GPIO Pin | Purpose |
|----------|----------|---------|
| SDA | GPIO 21 | I2C Data Line (serial data) |
| SCL | GPIO 22 | I2C Clock Line (serial clock) |
| GND | GND | Ground Reference |
| 3.3V | 3.3V | Power Supply |

### I2C Device Addresses
| Device | I2C Address | Status |
|--------|------------|--------|
| ADS1115 ADC | 0x48 | Connected to I2C Bus |
| SSD1306 OLED | 0x3C | Connected to I2C Bus |

### ADS1115 Analog Inputs
| Channel | GPIO/Pin | Purpose |
|---------|----------|---------|
| A0 | Analog Input 0 | EMG Signal Input (future) |
| A1 | Analog Input 1 | Available |
| A2 | Analog Input 2 | Available |
| A3 | Analog Input 3 | Available |

---

## Breadboard Connection Diagram

### Power Distribution
```
┌─────────────────────────────────────────┐
│         POWER BUS (3.3V)                │
├─────────────────────────────────────────┤
│         GROUND BUS (GND)                │
└─────────────────────────────────────────┘
```

### Current Hardware Setup

```
ESP32 DevKit V1
┌───────────────────────────┐
│   3.3V ──────────────┐    │
│   GND ───────────────┤    │
│   GPIO21 (SDA) ──┐   │    │
│   GPIO22 (SCL) ──┤   │    │
└───────────────────────────┘
         │   │   │
         │   │   └──────┬──────────────┐
         │   │          │              │
         │   │          │              │
    ┌────┴───┴──────────┴──────────────┴─┐
    │     BREADBOARD (I2C BUS)           │
    └────────────────────────────────────┘
         │              │
         │              │
    ┌────┴────┐    ┌────┴────┐
    │ ADS1115 │    │ SSD1306 │
    │ (0x48)  │    │ (0x3C)  │
    └─────────┘    └─────────┘
```

---

## Detailed Wiring Instructions

### Step 1: ESP32 to Breadboard
1. Connect **ESP32 3.3V** → **Red rail (positive) on breadboard**
2. Connect **ESP32 GND** → **Blue rail (negative) on breadboard**

### Step 2: I2C Bus Wiring
1. Connect **ESP32 GPIO21 (SDA)** → **Column A on breadboard**
2. Connect **ESP32 GPIO22 (SCL)** → **Column B on breadboard**

### Step 3: Pull-up Resistors (Optional but Recommended)
Add 4.7kΩ pull-up resistors for I2C bus stability:
- Connect **4.7kΩ resistor** between GPIO21 and 3.3V
- Connect **4.7kΩ resistor** between GPIO22 and 3.3V

### Step 4: ADS1115 ADC Connection
| ADS1115 Pin | Breadboard Connection |
|-------------|----------------------|
| VDD | Red Rail (3.3V) |
| GND | Blue Rail (Ground) |
| SDA | Column A (GPIO21) |
| SCL | Column B (GPIO22) |
| ADDR | Blue Rail (0x48 address) |
| A0 | Open (for future EMG input) |

### Step 5: SSD1306 OLED Display Connection
| OLED Pin | Breadboard Connection |
|----------|----------------------|
| VCC | Red Rail (3.3V) |
| GND | Blue Rail (Ground) |
| SDA | Column A (GPIO21) |
| SCL | Column B (GPIO22) |

### Step 6: Power Management (Battery Setup)
```
LiPo Battery (3.7V)
        ↓
   TP4056 Module (Charging)
        ↓
   AMS1117 3.3V Regulator
        ↓
   3.3V Power Supply
        ↓
   ┌────────────────────┐
   │   ESP32 + I2C Bus  │
   └────────────────────┘
```

---

## I2C Device Detection

Once hardware is connected, the firmware will automatically:

1. **Initialize I2C Bus** with GPIO21 (SDA) and GPIO22 (SCL)
2. **Scan for Devices** at addresses 0x00-0x7F
3. **Identify Devices**:
   - ADS1115 at 0x48 ✓
   - SSD1306 at 0x3C ✓
4. **Print Results** to Serial Monitor

Expected output:
```
[I2C] ========== I2C DEVICE SCAN START ==========
[I2C] Scanning addresses 0x00 to 0x7F...

[I2C] Device found at address: 0x48 !
      └─> Identified as: ADS1115 ADC
[I2C] Device found at address: 0x3C !
      └─> Identified as: SSD1306 OLED

[I2C] ========== I2C DEVICE SCAN END ===========
[I2C] Total devices found: 2
```

---

## Verification Checklist

Before uploading firmware, verify:

- [ ] ESP32 is securely placed on breadboard
- [ ] 3.3V power supply is connected to positive rail
- [ ] Ground is connected to negative rail
- [ ] GPIO21 is connected to SDA line
- [ ] GPIO22 is connected to SCL line
- [ ] ADS1115 VDD and GND are connected
- [ ] ADS1115 SDA/SCL connected to breadboard I2C bus
- [ ] SSD1306 VCC and GND are connected
- [ ] SSD1306 SDA/SCL connected to breadboard I2C bus
- [ ] No loose wires or shorts
- [ ] All components seated firmly

---

## Troubleshooting Hardware

### Problem: I2C Bus Not Detected
**Solution:**
1. Check all wires are firmly connected
2. Verify correct GPIO pins (21 for SDA, 22 for SCL)
3. Add 4.7kΩ pull-up resistors if not already present

### Problem: ADS1115 Not Found
**Solution:**
1. Verify device address (should be 0x48)
2. Check ADDR pin is connected to GND
3. Verify I2C communication

### Problem: OLED Not Displaying
**Solution:**
1. Check contrast might be too low
2. Verify device address (should be 0x3C)
3. Ensure I2C bus is functioning

### Problem: Power Issues
**Solution:**
1. Verify 3.3V supply voltage with multimeter
2. Check current draw (should be <500mA during normal operation)
3. Ensure battery has sufficient charge

---

## Power Consumption Estimate

| Component | Typical Current |
|-----------|-----------------|
| ESP32 (idle) | 20-30 mA |
| ESP32 (BLE advertising) | 50-100 mA |
| ADS1115 | 1-2 mA |
| SSD1306 OLED | 10-15 mA |
| **Total Estimated** | **80-150 mA** |

---

## Next Steps

After hardware verification:
1. Upload firmware using PlatformIO
2. Open Serial Monitor at 115200 baud
3. Verify I2C devices are detected
4. Check OLED display output
5. Monitor ADC readings from ADS1115

---

## References

- [ESP32 Pinout Reference](https://randomnerdtutorials.com/esp32-pinout-reference-diagrams/)
- [ADS1115 Datasheet](https://www.ti.com/product/ADS1115)
- [SSD1306 OLED Documentation](https://github.com/adafruit/Adafruit_SSD1306)
- I2C Standard: Two-wire protocol at 100-400 kHz

---

*Last Updated: 2024*
*ASV Development Team*
