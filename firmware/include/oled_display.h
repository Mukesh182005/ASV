#ifndef OLED_DISPLAY_H
#define OLED_DISPLAY_H

#include <Adafruit_SSD1306.h>
#include <Adafruit_GFX.h>

/**
 * OLED Display Module
 * Manages SSD1306 128x64 OLED display over I2C
 * 
 * Pin Configuration:
 * - SDA: GPIO21
 * - SCL: GPIO22
 * - Address: 0x3C
 */

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_ADDR 0x3C

class OLEDDisplay {
public:
    /**
     * Initialize OLED display
     * @return true if successful
     */
    bool begin();
    
    /**
     * Show startup splash screen
     */
    void showSplash();
    
    /**
     * Display system status
     * @param ble_connected BLE connection status
     * @param ads_connected ADS1115 connection status
     * @param adc_value Current ADC value
     */
    void showStatus(bool ble_connected, bool ads_connected, int adc_value = 0);
    
    /**
     * Display error message
     * @param error_msg Error message to display
     */
    void showError(const char* error_msg);
    
    /**
     * Display custom text at position
     * @param x X coordinate
     * @param y Y coordinate
     * @param text Text to display
     */
    void printAt(int x, int y, const char* text);
    
    /**
     * Clear display
     */
    void clear();
    
    /**
     * Update display with current buffer
     */
    void update();

private:
    Adafruit_SSD1306 display;
    bool is_initialized = false;
};

#endif // OLED_DISPLAY_H
