# ASV - A Silent Voice
## Silent Speech Recognition System using EMG Technology

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-1.0.0-brightgreen.svg)](CHANGELOG.md)
[![Status](https://img.shields.io/badge/Status-Development-yellow.svg)]()

---

## Overview

ASV (A Silent Voice) is an innovative AI-powered wearable system for silent speech recognition using EMG (Electromyography) sensors. The system captures subtle muscle movements from facial and laryngeal muscles during speech without vocalization, processes the signals in real-time, and enables communication through muscle signals alone.

### Key Features

✅ **Real-time EMG Signal Processing**
- 16-bit ADC acquisition (ADS1115)
- Multi-channel analog input support
- High-frequency sampling capability

✅ **Professional Firmware Architecture**
- Modular, extensible C++ codebase
- Clean separation of concerns
- Production-ready error handling

✅ **Comprehensive Debugging**
- Professional serial monitor output
- I2C device detection and scanning
- Real-time status display

✅ **Mobile Integration**
- Bluetooth Low Energy (BLE) connectivity
- OLED status display
- Power-efficient wireless protocol

✅ **Developer-Friendly**
- Complete hardware documentation
- GPIO mapping reference
- Troubleshooting guides
- Quick start instructions

---

## System Architecture

### Hardware Layer
```
Physical Devices:
├── ESP32 DevKit V1 (Main Controller)
├── ADS1115 (16-bit ADC, I2C 0x48)
└── SSD1306 OLED (Display, I2C 0x3C)

Future Addition:
└── AD8232 (EMG Front-End Amplifier)
```

### Communication Protocol
```
I2C Bus (GPIO21/GPIO22, 100kHz):
├── ADS1115 (ADC data acquisition)
├── SSD1306 (Display updates)
└── Pull-up resistors (4.7kΩ recommended)

BLE (Bluetooth Low Energy):
├── Device Name: ASV-Device
├── Service UUID: 180A
└── Characteristic UUID: 2A29
```

### Software Layers
```
┌─────────────────────────────────────┐
│   Application Layer                 │
│   (main.cpp - Initialization)       │
├─────────────────────────────────────┤
│   Device Driver Layer               │
│   ├─ I2C Scanner                    │
│   ├─ OLED Display Driver            │
│   ├─ ADS1115 ADC Driver             │
│   └─ BLE Module                     │
├─────────────────────────────────────┤
│   HAL (Hardware Abstraction Layer)  │
│   ├─ Wire (I2C)                     │
│   ├─ Serial (UART)                  │
│   └─ BLEDevice                      │
├─────────────────────────────────────┤
│   Arduino Framework (ESP32)         │
├─────────────────────────────────────┤
│   ESP32 Hardware                    │
└─────────────────────────────────────┘
```

---

## Project Structure

```
ASV/
├── firmware/                         # Embedded C++ firmware
│   ├── platformio.ini                # PlatformIO configuration
│   ├── include/                      # Header files
│   │   ├── i2c_scanner.h             # I2C device detection
│   │   ├── oled_display.h            # OLED SSD1306 driver
│   │   ├── ads1115_test.h            # ADC data acquisition
│   │   └── ble_test.h                # Bluetooth Low Energy
│   └── src/                          # Implementation files
│       ├── main.cpp                  # Main program entry point
│       ├── i2c_scanner.cpp           # I2C scanning logic
│       ├── oled_display.cpp          # Display driver implementation
│       ├── ads1115_test.cpp          # ADC driver implementation
│       └── ble_test.cpp              # BLE implementation
│
├── frontend/                         # Next.js web application
│   ├── app/                          # Next.js app directory
│   ├── components/                   # React components
│   ├── package.json                  # Dependencies
│   └── ... (web UI)
│
├── ml/                               # Machine Learning pipelines
│   ├── 01_synthetic_generator.py     # Generate test data
│   ├── 02_visualize_signals.py       # Signal visualization
│   ├── 03_signal_filtering.py        # EMG preprocessing
│   ├── 04_feature_extraction.py      # Feature engineering
│   └── 05_train_model.py             # Model training
│
├── datasets/                         # Data storage
│   ├── emg_dataset.csv               # Raw EMG data
│   └── emg_features.csv              # Extracted features
│
├── docs/                             # Documentation
│   ├── HARDWARE_SETUP.md             # ← Start here
│   ├── GPIO_MAPPING.md               # Pin configuration reference
│   ├── QUICK_START.md                # Upload and testing guide
│   ├── TROUBLESHOOTING.md            # Common issues & solutions
│   └── README.md                     # This file
│
└── tests/                            # Test files
    └── (unit and integration tests)
```

---

## Getting Started

### Prerequisites

**Hardware:**
- ESP32 DevKit V1
- ADS1115 ADC Module
- SSD1306 128x64 OLED Display
- Breadboard and jumper wires
- USB Type-B cable

**Software:**
- VS Code with PlatformIO IDE extension
- Python 3.8+ (for ML components)
- USB serial driver for ESP32

### Quick Setup (5 minutes)

1. **Install PlatformIO**
   - Open VS Code → Extensions → Search "PlatformIO" → Install

2. **Verify Hardware**
   - Follow [HARDWARE_SETUP.md](docs/HARDWARE_SETUP.md)
   - Ensure all I2C connections secure

3. **Upload Firmware**
   ```bash
   cd firmware
   pio run --target upload
   pio device monitor --baud 115200
   ```

4. **Verify Output**
   - Should see I2C device scan results
   - OLED displays "SYSTEM: READY"
   - ADC readings printing continuously

See [QUICK_START.md](docs/QUICK_START.md) for detailed instructions.

---

## Hardware Documentation

### Pin Configuration

| Function | GPIO | Purpose |
|----------|------|---------|
| I2C SDA | GPIO 21 | Serial Data Line |
| I2C SCL | GPIO 22 | Serial Clock Line |
| Power | 3.3V | Logic supply |
| Ground | GND | Reference |

### I2C Device Addresses

| Device | Address | Hex | Status |
|--------|---------|-----|--------|
| ADS1115 ADC | 72 | 0x48 | ✓ Active |
| SSD1306 OLED | 60 | 0x3C | ✓ Active |

### Wiring Diagram

See [HARDWARE_SETUP.md](docs/HARDWARE_SETUP.md#breadboard-connection-diagram) for complete breadboard layout and connection instructions.

---

## Firmware Features

### ✓ Implemented

- **I2C Bus Management**
  - Automatic device scanning
  - Address detection and identification
  - Error reporting

- **ADS1115 ADC Driver**
  - Single-ended analog input reading
  - Multi-sample averaging
  - Voltage conversion
  - Continuous monitoring

- **SSD1306 OLED Display**
  - Splash screen animation
  - Real-time status display
  - Error messages
  - Professional formatting

- **Bluetooth Low Energy**
  - BLE server initialization
  - Device advertising
  - Connection monitoring
  - Characteristic notifications

- **Serial Debugging**
  - Formatted console output
  - System startup logging
  - Real-time status updates
  - Error messages with context

### 🔄 In Progress

- AD8232 EMG sensor integration
- Advanced signal processing algorithms
- BLE data streaming
- Power management modes

### 📋 Planned

- Machine learning inference on device
- Gesture recognition
- Multi-muscle EMG processing
- Over-the-air firmware updates

---

## Configuration

### PlatformIO Settings

Edit `firmware/platformio.ini`:

```ini
[env:esp32dev]
platform = espressif32
board = esp32doit-devkit1
monitor_speed = 115200
upload_speed = 921600
monitor_port = COM3  # Change to your port
```

### GPIO Configuration

Edit `firmware/src/main.cpp`:

```cpp
#define I2C_SDA_PIN 21           // GPIO21 (I2C SDA)
#define I2C_SCL_PIN 22           // GPIO22 (I2C SCL)
#define I2C_FREQUENCY 100000     // 100kHz I2C clock
```

---

## Building and Testing

### Build Firmware

```bash
cd firmware
pio run                    # Compile
pio run --target upload    # Upload to ESP32
pio device monitor         # Monitor serial output (Ctrl+C to exit)
```

### Expected Output

On successful startup:
```
════════════════════════════════════════════════════════════
  ASV - A SILENT VOICE
════════════════════════════════════════════════════════════
[STARTUP] Initializing ESP32 firmware...

[INFO] Device: ESP32 DevKit V1
[INFO] Firmware: ASV Silent Speech Recognition
[INFO] Version: 1.0.0

[I2C] Device found at address: 0x48 !
      └─> Identified as: ADS1115 ADC

[I2C] Device found at address: 0x3C !
      └─> Identified as: SSD1306 OLED

[STATUS] System Status:   ✓ READY

✓ ALL SYSTEMS OPERATIONAL - READY FOR TESTING

[ADC] Raw: 512 | Voltage: 64.00 mV | BLE: ADVERTISING
```

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| "Port not found" | Check USB cable and drivers |
| "Garbage in serial" | Set baud to 115200 |
| "I2C devices not found" | Verify GPIO21/GPIO22 connections |
| "OLED blank" | Check address 0x3C, adjust contrast |
| "ADC reads zero" | Verify I2C connection to 0x48 |

See [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for detailed solutions.

---

## Code Examples

### Reading ADC Values

```cpp
#include "ads1115_test.h"

ADS1115Module adc;

void setup() {
    adc.begin();
}

void loop() {
    int16_t raw = adc.readAveraged(10);
    float voltage = raw * 0.125f;  // 0.125mV per LSB
    Serial.println(adc.getMeasurementString());
}
```

### Displaying on OLED

```cpp
#include "oled_display.h"

OLEDDisplay display;

void setup() {
    display.begin();
    display.showSplash();
}

void loop() {
    display.showStatus(ble_connected, ads_ready, adc_value);
    display.update();
}
```

### I2C Device Scanning

```cpp
#include "i2c_scanner.h"

I2CScanner scanner;

void setup() {
    scanner.begin(21, 22, 100000);  // SDA, SCL, frequency
    int devices = scanner.scan();
    Serial.println(devices);  // Number of devices found
}
```

---

## Performance Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| Boot Time | ~2 seconds | From reset to "READY" |
| ADC Sample Rate | 100-200 Hz | Configurable |
| I2C Bus Speed | 100 kHz | Standard mode |
| OLED Update Rate | 2 Hz | Every 500ms |
| Current Draw | 80-150 mA | Average during operation |
| BLE Latency | <100ms | Advertising interval |

---

## Power Consumption

### Typical Current Draw

| Component | Current |
|-----------|---------|
| ESP32 (idle) | 20-30 mA |
| ESP32 (BLE active) | 50-100 mA |
| ADS1115 | 1-2 mA |
| SSD1306 OLED | 10-15 mA |
| **Total** | **80-150 mA** |

### Battery Life Estimate

With 2000mAh LiPo battery:
- Continuous operation: ~13-25 hours
- With power management: ~24-48 hours

---

## Security Considerations

⚠️ **Development Firmware Only**

This firmware is designed for development and testing. For production use:

- [ ] Implement authentication for BLE
- [ ] Add encryption for data transmission
- [ ] Validate all external inputs
- [ ] Implement rate limiting
- [ ] Add secure boot configuration
- [ ] Review wireless security standards

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

See `CONTRIBUTING.md` for guidelines.

---

## Documentation

- [📖 Hardware Setup Guide](docs/HARDWARE_SETUP.md) - Wiring and connection instructions
- [🔌 GPIO & I2C Address Reference](docs/GPIO_MAPPING.md) - Pin assignment table
- [🚀 Quick Start Guide](docs/QUICK_START.md) - Upload and testing instructions
- [🔧 Troubleshooting Guide](docs/TROUBLESHOOTING.md) - Common issues and solutions

---

## Resources

### Official Documentation
- [ESP32 Arduino Framework](https://docs.espressif.com/projects/arduino-esp32/)
- [PlatformIO Documentation](https://docs.platformio.org/)
- [Adafruit Libraries](https://github.com/adafruit)

### Datasheets
- [ADS1115 Datasheet](https://www.ti.com/product/ADS1115)
- [SSD1306 Datasheet](https://cdn-shop.adafruit.com/datasheets/SSD1306.pdf)
- [ESP32 Datasheet](https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf)

### Tutorials
- [I2C Protocol Guide](https://en.wikipedia.org/wiki/I%C2%B2C)
- [EMG Signal Processing](https://en.wikipedia.org/wiki/Electromyography)
- [BLE Overview](https://www.bluetooth.com/specifications/specs/)

---

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

---

## Authors

**ASV Development Team**
- Initial Development: 2024
- Version: 1.0.0

---

## Acknowledgments

- Adafruit for excellent libraries and community support
- ESP32/Arduino community for comprehensive documentation
- EMG research community for signal processing insights

---

## Support

### Getting Help

1. **Check Documentation**: Start with [QUICK_START.md](docs/QUICK_START.md)
2. **Review Troubleshooting**: See [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
3. **Check Serial Output**: Look for error messages
4. **Hardware Verification**: Follow [HARDWARE_SETUP.md](docs/HARDWARE_SETUP.md)

### Reporting Issues

When reporting issues, include:
- Complete serial monitor output
- ESP32 board type and version
- Exact steps to reproduce
- Screenshots if applicable

---

## Roadmap

### Version 1.1 (Q2 2024)
- [ ] AD8232 EMG sensor integration
- [ ] Real-time signal filtering
- [ ] Basic gesture recognition
- [ ] Android companion app

### Version 1.2 (Q3 2024)
- [ ] Machine learning inference
- [ ] Multi-muscle EMG processing
- [ ] Advanced gesture library
- [ ] iOS companion app

### Version 2.0 (Q4 2024)
- [ ] Distributed processing
- [ ] Cloud connectivity
- [ ] Advanced analytics
- [ ] Commercial prototype

---

## Contact

For questions or feedback:
- 📧 Email: asv-dev@example.com
- 🐦 Twitter: [@ASVProject](https://twitter.com/asvproject)
- 💬 Discord: [Join Server](https://discord.gg/asv)

---

**Last Updated:** 2024-05-14
**Status:** Development - Ready for Hardware Testing ✅

---

## Quick Navigation

| What I want to... | Go to... |
|-------------------|----------|
| Set up hardware | [HARDWARE_SETUP.md](docs/HARDWARE_SETUP.md) |
| Understand pins/addresses | [GPIO_MAPPING.md](docs/GPIO_MAPPING.md) |
| Upload firmware | [QUICK_START.md](docs/QUICK_START.md) |
| Fix a problem | [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) |
| Understand architecture | This README |

