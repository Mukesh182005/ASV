#include "ads1115_test.h"

bool ADS1115Module::begin() {
    if (is_initialized) {
        return true;
    }
    
    if (!ads.begin(ADS_ADDR)) {
        Serial.println("[ADS1115] ERROR: Could not find ADS1115 at 0x48!");
        return false;
    }
    
    is_initialized = true;
    ads.setGain(GAIN_ONE);  // +/- 4.096V range
    ads.setDataRate(RATE_ADS1115_860SPS); // Max speed
    
    // Start continuous conversion on AIN0 to allow non-blocking reads
    ads.startADCReading(ADS1X15_REG_CONFIG_MUX_SINGLE_0, true);
    
    Serial.println("[ADS1115] Successfully initialized at 0x48");
    Serial.println("[ADS1115] Configuration:");
    Serial.println("         - Gain: +/- 4.096V");
    Serial.println("         - Rate: 860 SPS (Continuous Mode)");
    
    return true;
}

int16_t ADS1115Module::readValue(uint8_t channel) {
    if (!is_initialized || channel > 3) {
        return -1;
    }
    last_value = ads.readADC_SingleEnded(channel);
    return last_value;
}

void ADS1115Module::readChannels(int16_t* buffer, uint8_t num_channels) {
    if (!is_initialized) return;
    
    if (num_channels == 1) {
        // Continuous mode is running for ch0, instantly fetch the latest result (non-blocking)
        buffer[0] = ads.getLastConversionResults();
    } else {
        // Fallback for multiple channels (blocking)
        for (uint8_t i = 0; i < num_channels && i < 4; i++) {
            buffer[i] = ads.readADC_SingleEnded(i);
        }
    }
}

bool ADS1115Module::isConnected() {
    if (!is_initialized) return false;
    int16_t test_value = ads.readADC_SingleEnded(0);
    return true; 
}

const char* ADS1115Module::getMeasurementString() {
    static char buffer[32];
    float voltage = last_value * 0.125f;
    snprintf(buffer, sizeof(buffer), "ADC: %d (%.2f mV)", last_value, voltage);
    return buffer;
}
