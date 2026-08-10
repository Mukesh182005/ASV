/**
 * ASV - A Silent Voice
 * ESP32 Firmware for Silent Speech Recognition System
 * 
 * Hardware Configuration:
 * - ESP32 DevKit V1
 * - ADS1115 16-bit ADC (I2C Address: 0x48)
 * - SSD1306 128x64 OLED Display (I2C Address: 0x3C)
 * - I2C Bus: GPIO21 (SDA), GPIO22 (SCL)
 * - Serial Monitor: 115200 baud
 * 
 * Features:
 * - I2C device detection and scanning
 * - Real-time ADC data acquisition from ADS1115
 * - OLED status display
 * - BLE advertising as "ASV-Device"
 * - Professional serial debugging output
 * 
 * Author: ASV Development Team
 * Date: 2024
 */

#include <Arduino.h>
#include "i2c_scanner.h"
#include "oled_display.h"
#include "ads1115_test.h"
#include "ble_test.h"

// ============================================================================
// GLOBAL INSTANCES
// ============================================================================

I2CScanner i2c_scanner;          // I2C device scanner
OLEDDisplay oled_display;        // OLED display manager
ADS1115Module adc_module;        // ADC module
BLEModule ble_module;            // BLE module

// ============================================================================
// CONFIGURATION CONSTANTS
// ============================================================================

#define I2C_SDA_PIN 21           // GPIO21 for I2C SDA
#define I2C_SCL_PIN 22           // GPIO22 for I2C SCL
#define I2C_FREQUENCY 100000     // 100kHz I2C bus speed

#define TARGET_SAMPLE_RATE_HZ 500
#define SAMPLE_INTERVAL_US (1000000 / TARGET_SAMPLE_RATE_HZ)
#define NUM_CHANNELS 1  // Currently: AD8232 OUTPUT -> A0 only

// ============================================================================
// GLOBAL STATE VARIABLES
// ============================================================================

bool system_ready = false;
bool ble_initialized = false;
bool ads_connected = false;
bool oled_connected = false;

unsigned long last_sample_us = 0;
unsigned long last_display_ms = 0;
unsigned long sample_count = 0;

// ============================================================================
// SERIAL COMMUNICATION UTILITIES
// ============================================================================

void print_separator(const char* title) {
    Serial.println("\n════════════════════════════════════════════════════════════");
    if (title) {
        Serial.print("  ");
        Serial.println(title);
        Serial.println("════════════════════════════════════════════════════════════");
    }
}

void print_system_info() {
    print_separator("SYSTEM INFORMATION");
    Serial.println("[INFO] Device: ESP32 DevKit V1");
    Serial.println("[INFO] Firmware: ASV Silent Speech Recognition - ACQUISITION MODE");
    Serial.println("[INFO] Version: 1.1.0");
    Serial.print("[INFO] Target Rate: ");
    Serial.print(TARGET_SAMPLE_RATE_HZ);
    Serial.println(" Hz");
}

// ============================================================================
// INITIALIZATION FUNCTIONS
// ============================================================================

void setup() {
    // Initialize Serial first for debugging
    Serial.begin(921600);
    delay(100);
    
    print_system_info();
    
    i2c_scanner.begin(I2C_SDA_PIN, I2C_SCL_PIN, I2C_FREQUENCY);
    delay(500);
    int devices_found = i2c_scanner.scan();
    
    if (oled_display.begin()) {
        oled_connected = true;
        oled_display.showSplash();
        delay(1000);
    }
    
    if (adc_module.begin()) {
        ads_connected = true;
    }
    
    ble_module.begin();
    ble_module.startAdvertising();
    ble_initialized = true;
    
    system_ready = (ads_connected && oled_connected && ble_initialized);
    
    if (system_ready) {
        Serial.println("\n✓ ALL SYSTEMS OPERATIONAL - ACQUISITION STARTING");
        if (oled_connected) {
            oled_display.showStatus(ble_module.isConnected(), ads_connected, 0);
        }
    } else {
        Serial.println("\n✗ SYSTEM NOT READY - Check Hardware");
    }
    
    // Add a slight delay before data spam starts
    delay(2000);
    Serial.println("--- START DATA ---");
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
    if (!system_ready) {
        delay(1000);
        return;
    }
    
    unsigned long current_us = micros();
    
    // High-speed ADC sampling and structured CSV output
    if (current_us - last_sample_us >= SAMPLE_INTERVAL_US) {
        last_sample_us = current_us;
        
        if (ads_connected) {
            int16_t buffer[NUM_CHANNELS];
            adc_module.readChannels(buffer, NUM_CHANNELS);
            
            // Output CSV format: timestamp_ms,ch0,ch1,ch2,ch3
            Serial.print(millis());
            for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
                Serial.print(",");
                Serial.print(buffer[i]);
            }
            Serial.println();
            sample_count++;
        }
    }
    
    // Low-speed OLED and BLE updates (every 1 second)
    unsigned long current_ms = millis();
    if (current_ms - last_display_ms >= 1000) {
        last_display_ms = current_ms;
        if (oled_connected && ads_connected) {
            oled_display.showStatus(ble_module.isConnected(), ads_connected, 0);
        }
    }
}


// ============================================================================
// END OF FIRMWARE
// ============================================================================
