#ifndef I2C_SCANNER_H
#define I2C_SCANNER_H

#include <Wire.h>

/**
 * I2C Scanner Module
 * Scans and identifies all I2C devices connected to the bus
 */

class I2CScanner {
public:
    /**
     * Initialize I2C with custom pins
     * @param sda_pin GPIO pin for SDA
     * @param scl_pin GPIO pin for SCL
     * @param frequency I2C bus frequency (default 100kHz)
     */
    void begin(int sda_pin, int scl_pin, uint32_t frequency = 100000);
    
    /**
     * Scan I2C bus and print found devices
     * @return number of devices found
     */
    int scan();
    
    /**
     * Check if specific device exists
     * @param address I2C address to check
     * @return true if device found
     */
    bool deviceExists(uint8_t address);

private:
    bool is_initialized = false;
};

#endif // I2C_SCANNER_H
