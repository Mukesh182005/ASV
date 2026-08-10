/**
 * asv_oled.h -- SSD1306 status display on the SECOND I2C bus (Wire1).
 * Keeping the display off the ADC bus is what makes "OLED + BLE + 860 SPS"
 * possible without losing samples.
 */
#pragma once
#include <Arduino.h>
#include "asv_config.h"

struct AsvUiState {
  bool     ble_connected;
  bool     adc_ok;
  bool     streaming;
  float    measured_hz;
  uint32_t dropped;
  float    baseline_mv;
  float    pp_mv;
  bool     lead_off_p;
  bool     lead_off_n;
  const char *mode;
};

bool asvOledBegin();
bool asvOledPresent();
void asvOledSplash();
void asvOledStatus(const AsvUiState &s);
void asvOledShowPrediction(const char *word);
void asvOledMessage(const char *line1, const char *line2);
void asvOledSetEnabled(bool on);
bool asvOledEnabled();
uint32_t asvOledLastRenderUs();   // how long the last frame push took
