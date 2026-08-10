#include <Arduino.h>
#include "asv_oled.h"

#if ASV_ENABLE_OLED

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#if ASV_OLED_ON_SECOND_BUS
  static TwoWire &OLED_BUS = Wire1;
#else
  static TwoWire &OLED_BUS = Wire;
#endif

static Adafruit_SSD1306 g_disp(OLED_W, OLED_H, &OLED_BUS, -1);
static bool     g_ok       = false;
static bool     g_enabled  = true;
static uint32_t g_lastRenderUs = 0;

bool asvOledPresent() {
  OLED_BUS.beginTransmission(OLED_I2C_ADDR);
  return OLED_BUS.endTransmission() == 0;
}

bool asvOledBegin() {
#if ASV_OLED_ON_SECOND_BUS
  OLED_BUS.begin(PIN_I2C1_SDA, PIN_I2C1_SCL, I2C1_FREQ_HZ);
#endif
  OLED_BUS.setClock(I2C1_FREQ_HZ);

  if (!asvOledPresent()) { g_ok = false; return false; }
  if (!g_disp.begin(SSD1306_SWITCHCAPVCC, OLED_I2C_ADDR)) { g_ok = false; return false; }

  g_ok = true;
  g_disp.clearDisplay();
  g_disp.setTextColor(SSD1306_WHITE);
  g_disp.setTextSize(1);
  g_disp.display();
  return true;
}

void asvOledSetEnabled(bool on) {
  g_enabled = on;
  if (g_ok && !on) { g_disp.clearDisplay(); g_disp.display(); }
}
bool asvOledEnabled() { return g_enabled; }
uint32_t asvOledLastRenderUs() { return g_lastRenderUs; }

static void push() {
  uint32_t t0 = micros();
  g_disp.display();
  g_lastRenderUs = micros() - t0;
}

void asvOledSplash() {
  if (!g_ok || !g_enabled) return;
  g_disp.clearDisplay();
  g_disp.setTextSize(2);
  g_disp.setCursor(28, 6);
  g_disp.println("ASV");
  g_disp.setTextSize(1);
  g_disp.setCursor(14, 30);
  g_disp.println("A Silent Voice");
  g_disp.setCursor(6, 44);
  g_disp.println("EMG ACQUISITION");
  g_disp.setCursor(6, 54);
  g_disp.print("fw ");
  g_disp.print(ASV_FW_VERSION);
  push();
}

void asvOledMessage(const char *line1, const char *line2) {
  if (!g_ok || !g_enabled) return;
  g_disp.clearDisplay();
  g_disp.setTextSize(1);
  g_disp.setCursor(0, 0);
  g_disp.println(line1 ? line1 : "");
  g_disp.setCursor(0, 12);
  g_disp.println(line2 ? line2 : "");
  push();
}

void asvOledStatus(const AsvUiState &s) {
  if (!g_ok || !g_enabled) return;

  g_disp.clearDisplay();
  g_disp.setTextSize(1);

  g_disp.setCursor(0, 0);
  g_disp.print(s.streaming ? "STREAMING" : "IDLE");
  g_disp.setCursor(74, 0);
  g_disp.print(s.ble_connected ? "BLE:CON" : "BLE:ADV");

  g_disp.drawFastHLine(0, 10, 128, SSD1306_WHITE);

  g_disp.setCursor(0, 14);
  g_disp.print("Rate ");
  g_disp.print(s.measured_hz, 1);
  g_disp.print(" Hz");

  g_disp.setCursor(0, 24);
  g_disp.print("Drop ");
  g_disp.print(s.dropped);

  g_disp.setCursor(0, 34);
  g_disp.print("Base ");
  g_disp.print(s.baseline_mv, 0);
  g_disp.print("mV");

  g_disp.setCursor(0, 44);
  g_disp.print("Pk-Pk ");
  g_disp.print(s.pp_mv, 1);
  g_disp.print("mV");

  g_disp.setCursor(0, 54);
  if (!s.adc_ok) {
    g_disp.print("ADS1115 OFFLINE!");
  } else if (s.lead_off_p || s.lead_off_n) {
    g_disp.print("LEAD OFF ");
    if (s.lead_off_p) g_disp.print("+");
    if (s.lead_off_n) g_disp.print("-");
  } else {
    g_disp.print("ELECTRODES OK");
  }

  push();
}

#else  // ---------------------------------------------------------------- stub

bool asvOledBegin()      { return false; }
bool asvOledPresent()    { return false; }
void asvOledSplash()     {}
void asvOledStatus(const AsvUiState &) {}
void asvOledMessage(const char *, const char *) {}
void asvOledSetEnabled(bool) {}
bool asvOledEnabled()    { return false; }
uint32_t asvOledLastRenderUs() { return 0; }

#endif
