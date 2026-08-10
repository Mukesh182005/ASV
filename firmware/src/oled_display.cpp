#include "oled_display.h"

/**
 * OLED Display Implementation
 * SSD1306 128x64 I2C Display Driver
 */

bool OLEDDisplay::begin() {
    if (is_initialized) {
        return true;
    }
    
    // Initialize OLED display
    if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
        Serial.println("[OLED] ERROR: SSD1306 allocation failed!");
        return false;
    }
    
    is_initialized = true;
    
    // Clear display and set text properties
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 0);
    display.println("[OLED] Initialized");
    display.display();
    
    Serial.println("[OLED] Successfully initialized at 0x3C");
    delay(1000);
    
    return true;
}

void OLEDDisplay::showSplash() {
    if (!is_initialized) {
        Serial.println("[OLED] ERROR: Display not initialized!");
        return;
    }
    
    display.clearDisplay();
    display.setTextSize(2);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(15, 10);
    display.println("ASV");
    
    display.setTextSize(1);
    display.setCursor(10, 30);
    display.println("A Silent Voice");
    
    display.setCursor(5, 45);
    display.println("EMG Silent Speech");
    display.setCursor(15, 55);
    display.println("Recognition");
    
    display.display();
    Serial.println("[OLED] Splash screen displayed");
}

void OLEDDisplay::showStatus(bool ble_connected, bool ads_connected, int adc_value) {
    if (!is_initialized) {
        return;
    }
    
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    
    // Header
    display.setCursor(0, 0);
    display.println("=== ASV STATUS ===");
    
    // Status line 1
    display.setCursor(0, 12);
    display.print("BLE: ");
    display.println(ble_connected ? "CONNECTED" : "ADVERTISING");
    
    // Status line 2
    display.setCursor(0, 22);
    display.print("ADS1115: ");
    display.println(ads_connected ? "READY" : "OFFLINE");
    
    // ADC value display
    display.setCursor(0, 32);
    display.print("ADC: ");
    display.print(adc_value);
    display.println(" mV");
    
    // System status
    display.setCursor(0, 42);
    display.println("=================");
    
    display.setCursor(0, 52);
    display.println("SYSTEM: READY");
    
    display.display();
}

void OLEDDisplay::showError(const char* error_msg) {
    if (!is_initialized) {
        return;
    }
    
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    
    display.setCursor(0, 0);
    display.println("=== ERROR ===");
    
    display.setCursor(0, 15);
    display.println(error_msg);
    
    display.setCursor(0, 50);
    display.println("Check Serial Monitor");
    
    display.display();
}

void OLEDDisplay::printAt(int x, int y, const char* text) {
    if (!is_initialized) {
        return;
    }
    
    display.setCursor(x, y);
    display.println(text);
}

void OLEDDisplay::clear() {
    if (!is_initialized) {
        return;
    }
    display.clearDisplay();
}

void OLEDDisplay::update() {
    if (!is_initialized) {
        return;
    }
    display.display();
}
