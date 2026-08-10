/**
 * ASV - A Silent Voice
 * asv_config.h  --  Single source of truth for pins, rates and build switches.
 *
 * Everything you might need to change to match your breadboard is in THIS file.
 * Nothing else should need editing.
 */
#pragma once
#include <Arduino.h>

#define ASV_FW_VERSION      "2.0.0-arduino"

// ============================================================================
// BUILD SWITCHES
// ============================================================================
#define ASV_ENABLE_OLED           1   // SSD1306 status display
#define ASV_ENABLE_BLE            1   // BLE server + status notifications
#define ASV_OLED_ON_SECOND_BUS    1   // 1 = OLED on Wire1 (RECOMMENDED, see note)
                                      // 0 = OLED shares the ADS1115 bus (costs samples)

// NOTE on ASV_OLED_ON_SECOND_BUS:
//   A full SSD1306 frame is 1024 bytes. On a 400 kHz I2C bus that is ~25 ms
//   during which the ADS1115 cannot be read -> ~21 lost EMG samples every
//   refresh. Putting the OLED on the ESP32's SECOND I2C peripheral (Wire1)
//   means the display and the ADC never contend. Cost: move 2 jumper wires.

// ============================================================================
// I2C BUS A  --  ADS1115 ONLY (kept clear so sampling is never blocked)
// ============================================================================
#define PIN_I2C_SDA         21
#define PIN_I2C_SCL         22
#define I2C_FREQ_HZ         400000UL   // was 100 kHz - too slow for 860 SPS

// ============================================================================
// I2C BUS B  --  SSD1306 OLED
// ============================================================================
#define PIN_I2C1_SDA        25
#define PIN_I2C1_SCL        26
#define I2C1_FREQ_HZ        400000UL

// ============================================================================
// ADS1115
// ============================================================================
#define ADS1115_I2C_ADDR    0x48
#define PIN_ADS_ALERT       27         // ADS1115 ALRT/RDY  ->  ESP32 GPIO27
                                       // (open drain; internal pull-up enabled)

// ============================================================================
// AD8232 EMG FRONT-END
//   OUTPUT -> ADS1115 A0
//   LO+ / LO- -> ESP32 input-only pins (lead-off / electrode-detached detect)
//   SDN -> 3.3V (keep the amplifier awake)
// ============================================================================
#define ASV_HAS_AD8232      1
#define PIN_AD8232_LO_P     34         // input-only, no internal pull-up (AD8232 drives it)
#define PIN_AD8232_LO_N     35         // input-only
#define AD8232_LO_ACTIVE_HIGH 1        // AD8232 drives LO high when the lead is OFF

// ============================================================================
// SSD1306
// ============================================================================
#define OLED_I2C_ADDR       0x3C
#define OLED_W              128
#define OLED_H              64
#define OLED_REFRESH_MS     500

// ============================================================================
// ACQUISITION
// ============================================================================
#define ASV_NUM_CHANNELS    1          // AD8232 OUTPUT -> A0
#define ASV_SPS             860        // ADS1115 continuous data rate (max)
#define ASV_POLL_FALLBACK_HZ 500       // used only if the ALRT/RDY wire is missing
#define ASV_RING_SIZE       2048       // MUST be a power of two (~2.4 s of buffer)
#define ASV_SERIAL_BAUD     921600UL   // 860 Hz CSV needs ~155 kbps; 115200 will drop data
#define ASV_SERIAL_TX_BUF   4096

// Default PGA index (see asv_adc.cpp gain table).
//   1 = +/-4.096 V, 125.0 uV/LSB  <-- safe default for the AD8232's ~1.65 V bias
//   2 = +/-2.048 V,  62.5 uV/LSB  <-- 2x resolution, only if the signal fits
#define ASV_DEFAULT_GAIN_IDX 1

// ============================================================================
// BLE
// ============================================================================
// Custom 128-bit UUIDs. The old firmware misused 0x180A / 0x2A29, which are
// reserved by the Bluetooth SIG for the Device Information Service.
#define ASV_BLE_NAME        "ASV-Device"
#define ASV_BLE_SERVICE_UUID  "6e6b0001-b5a3-f393-e0a9-e50e24dcca9e"
#define ASV_BLE_STATUS_UUID   "6e6b0002-b5a3-f393-e0a9-e50e24dcca9e"
#define ASV_BLE_CMD_UUID      "6e6b0003-b5a3-f393-e0a9-e50e24dcca9e"
#define ASV_BLE_NOTIFY_MS   50         // 20 Hz status/preview packets
