#include <Arduino.h>
#include "i2c_scanner.h"

/**
 * I2C Scanner Implementation
 * Scans the I2C bus and identifies connected devices
 */

void I2CScanner::begin(int sda_pin, int scl_pin, uint32_t frequency) {
    if (!is_initialized) {
        Wire.begin(sda_pin, scl_pin, frequency);
        is_initialized = true;
        Serial.println("[I2C] Scanner initialized on SDA=" + String(sda_pin) + 
                      " SCL=" + String(scl_pin) + " Freq=" + String(frequency) + "Hz");
    }
}

int I2CScanner::scan() {
    if (!is_initialized) {
        Serial.println("[I2C] ERROR: Scanner not initialized!");
        return 0;
    }
    
    Serial.println("\n[I2C] ========== I2C DEVICE SCAN START ==========");
    Serial.println("[I2C] Scanning addresses 0x00 to 0x7F...\n");
    
    int found_count = 0;
    
    for (uint8_t i = 1; i < 127; i++) {
        Wire.beginTransmission(i);
        uint8_t error = Wire.endTransmission();
        
        if (error == 0) {
            Serial.print("[I2C] Device found at address: 0x");
            if (i < 16) Serial.print("0");
            Serial.print(i, HEX);
            Serial.println(" !");
            
            // Identify known devices
            if (i == 0x48) {
                Serial.println("      └─> Identified as: ADS1115 ADC");
            } else if (i == 0x3C || i == 0x3D) {
                Serial.println("      └─> Identified as: SSD1306 OLED");
            }
            
            found_count++;
        }
    }
    
    Serial.println("\n[I2C] ========== I2C DEVICE SCAN END ===========");
    Serial.println("[I2C] Total devices found: " + String(found_count) + "\n");
    
    return found_count;
}

bool I2CScanner::deviceExists(uint8_t address) {
    if (!is_initialized) {
        Serial.println("[I2C] ERROR: Scanner not initialized!");
        return false;
    }
    
    Wire.beginTransmission(address);
    uint8_t error = Wire.endTransmission();
    
    return (error == 0);
}
