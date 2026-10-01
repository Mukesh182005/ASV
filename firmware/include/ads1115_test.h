#ifndef ADS1115_TEST_H
#define ADS1115_TEST_H

#include <Adafruit_ADS1X15.h>

/**
 * ADS1115 ADC Module
 * Manages 16-bit I2C ADC for EMG signal acquisition
 */

#define ADS_ADDR 0x48

class ADS1115Module {
public:
    bool begin();
    
    // Read single channel
    int16_t readValue(uint8_t channel = 0);
    
    // Read multiple channels sequentially
    void readChannels(int16_t* buffer, uint8_t num_channels = 1);
    
    bool isConnected();
    const char* getMeasurementString();

private:
    Adafruit_ADS1115 ads;
    bool is_initialized = false;
    int16_t last_value = 0;
};

#endif // ADS1115_TEST_H
