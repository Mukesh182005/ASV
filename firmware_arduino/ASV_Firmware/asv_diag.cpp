#include <Arduino.h>
#include <Wire.h>
#include <math.h>
#include <string.h>
#include "asv_diag.h"
#include "asv_adc.h"
#include "asv_oled.h"
#include "asv_ble.h"

static void rule() {
  Serial.println(F("------------------------------------------------------------"));
}
static void pass(const char *what) { Serial.print(F("  [PASS] ")); Serial.println(what); }
static void fail(const char *what) { Serial.print(F("  [FAIL] ")); Serial.println(what); }
static void warn(const char *what) { Serial.print(F("  [WARN] ")); Serial.println(what); }

// ============================================================================
// I2C SCAN
// ============================================================================
void asvDiagI2cScan(TwoWire &bus, const char *label, int sda, int scl) {
  Serial.print(F("\n[I2C] Scanning "));
  Serial.print(label);
  Serial.print(F("  (SDA=GPIO"));
  Serial.print(sda);
  Serial.print(F(", SCL=GPIO"));
  Serial.print(scl);
  Serial.println(F(")"));

  int found = 0;
  for (uint8_t a = 1; a < 127; a++) {
    bus.beginTransmission(a);
    if (bus.endTransmission() == 0) {
      Serial.print(F("      0x"));
      if (a < 16) Serial.print('0');
      Serial.print(a, HEX);
      if      (a == 0x48) Serial.print(F("  <- ADS1115 ADC"));
      else if (a == 0x49 || a == 0x4A || a == 0x4B)
                          Serial.print(F("  <- ADS1115 (wrong ADDR strap! expected 0x48)"));
      else if (a == 0x3C || a == 0x3D) Serial.print(F("  <- SSD1306 OLED"));
      Serial.println();
      found++;
    }
  }
  if (found == 0) Serial.println(F("      (nothing responded - check power, GND and pull-ups)"));
  Serial.print(F("      total: "));
  Serial.println(found);
}

// ============================================================================
// SIGNAL MEASUREMENT
// ============================================================================
AsvSignalStats asvDiagMeasureSignal(uint32_t ms) {
  AsvSignalStats s;
  memset(&s, 0, sizeof(s));
  s.min_counts = 32767;
  s.max_counts = -32768;

  double sum = 0.0, sumsq = 0.0;
  uint32_t first_us = 0, last_us = 0;

  // flush whatever is already buffered so we measure "now"
  AsvSample tmp;
  while (asvAdcPop(tmp)) {}

  uint32_t t0 = millis();
  while (millis() - t0 < ms) {
    AsvSample x;
    if (!asvAdcPop(x)) { delay(1); continue; }
    if (s.n == 0) first_us = x.t_us;
    last_us = x.t_us;
    s.n++;
    sum   += x.v;
    sumsq += (double)x.v * (double)x.v;
    if (x.v < s.min_counts) s.min_counts = x.v;
    if (x.v > s.max_counts) s.max_counts = x.v;
    if (x.flags & (ASV_FLAG_LO_P | ASV_FLAG_LO_N)) s.lead_off_samples++;
  }

  if (s.n == 0) return s;

  s.mean_counts = (float)(sum / s.n);
  double var = (sumsq / s.n) - ((sum / s.n) * (sum / s.n));
  if (var < 0) var = 0;
  s.rms_ac_counts = (float)sqrt(var);

  float vpl_mv = asvAdcVoltsPerLsb() * 1000.0f;
  s.mean_mv  = s.mean_counts * vpl_mv;
  s.pp_mv    = (float)(s.max_counts - s.min_counts) * vpl_mv;
  s.rms_ac_uv= s.rms_ac_counts * asvAdcVoltsPerLsb() * 1e6f;

  if (s.n > 1 && last_us > first_us)
    s.measured_hz = (float)(s.n - 1) * 1e6f / (float)(last_us - first_us);

  s.railed_low  = (s.min_counts <= -32700);
  s.railed_high = (s.max_counts >=  32700);
  return s;
}

void asvDiagPrintSignalStats(const AsvSignalStats &s) {
  if (s.n == 0) { fail("no samples captured - the ADC is not producing data"); return; }

  Serial.print(F("      samples      : ")); Serial.println(s.n);
  Serial.print(F("      measured rate: ")); Serial.print(s.measured_hz, 2); Serial.println(F(" Hz"));
  Serial.print(F("      DC baseline  : ")); Serial.print(s.mean_counts, 1);
  Serial.print(F(" counts  = ")); Serial.print(s.mean_mv, 1); Serial.println(F(" mV"));
  Serial.print(F("      min / max    : ")); Serial.print(s.min_counts);
  Serial.print(F(" / ")); Serial.println(s.max_counts);
  Serial.print(F("      peak-to-peak : ")); Serial.print(s.pp_mv, 2); Serial.println(F(" mV"));
  Serial.print(F("      AC RMS       : ")); Serial.print(s.rms_ac_uv, 1);
  Serial.println(F(" uV  <- noise floor when you hold still"));
  if (s.lead_off_samples) {
    Serial.print(F("      lead-off hits: "));
    Serial.println(s.lead_off_samples);
  }
}

void asvDiagRecommendGain(const AsvSignalStats &s) {
  if (s.n == 0) return;

  // Largest absolute excursion we saw, in volts, plus 60% headroom.
  float vpl = asvAdcVoltsPerLsb();
  float peak_v = fmaxf(fabsf((float)s.max_counts), fabsf((float)s.min_counts)) * vpl;
  float needed = peak_v * 1.6f;

  const float fs[6] = { 6.144f, 4.096f, 2.048f, 1.024f, 0.512f, 0.256f };
  int best = 0;
  for (int i = 5; i >= 0; i--) { if (fs[i] > needed) { best = i; break; } }

  Serial.print(F("      current gain : ")); Serial.println(asvAdcGainName());
  if (best != (int)asvAdcGetGain()) {
    Serial.print(F("      SUGGESTION   : gain index "));
    Serial.print(best);
    Serial.print(F(" (+/-"));
    Serial.print(fs[best], 3);
    Serial.println(F(" V) would give better resolution. Press 'g' to cycle."));
  } else {
    Serial.println(F("      gain setting : optimal for the observed swing"));
  }

  if (s.railed_low || s.railed_high)
    fail("input is RAILED (clipping). Increase the range or check the AD8232 output.");
}

void asvDiagPrintLeadOff() {
#if ASV_HAS_AD8232
  uint16_t f = asvAdcLeadOffFlags();
  Serial.print(F("      AD8232 LO+   : "));
  Serial.println((f & ASV_FLAG_LO_P) ? F("LEAD OFF (electrode not on skin)") : F("attached"));
  Serial.print(F("      AD8232 LO-   : "));
  Serial.println((f & ASV_FLAG_LO_N) ? F("LEAD OFF (electrode not on skin)") : F("attached"));
#else
  Serial.println(F("      AD8232 lead-off detection disabled in asv_config.h"));
#endif
}

// ============================================================================
// FULL SELF-TEST
// ============================================================================
bool asvDiagRunSelfTest() {
  bool allGood = true;

  Serial.println();
  rule();
  Serial.println(F("  ASV HARDWARE SELF-TEST"));
  rule();

  // ---- 1. I2C buses --------------------------------------------------------
  Serial.println(F("\n[1/6] I2C BUS SCAN"));
  asvDiagI2cScan(Wire, "bus A (ADS1115)", PIN_I2C_SDA, PIN_I2C_SCL);
#if ASV_ENABLE_OLED && ASV_OLED_ON_SECOND_BUS
  asvDiagI2cScan(Wire1, "bus B (OLED)", PIN_I2C1_SDA, PIN_I2C1_SCL);
#endif

  // ---- 2. ADS1115 presence + register proof --------------------------------
  Serial.println(F("\n[2/6] ADS1115"));
  if (!asvAdcPresent()) {
    fail("no ACK at 0x48. Check VDD/GND, SDA=GPIO21, SCL=GPIO22, ADDR->GND.");
    allGood = false;
  } else {
    pass("device ACKs at 0x48");
    if (asvAdcRegisterSelfTest()) {
      pass("threshold register write/read-back matches (real ADS1115, real bus)");
    } else {
      fail("register read-back mismatch - bad wiring, noise, or not an ADS1115");
      allGood = false;
    }
    uint16_t cfg = asvAdcReadConfigRegister();
    Serial.print(F("      config reg   : 0x"));
    Serial.println(cfg, HEX);
    if ((cfg & 0x0100) != 0) {
      warn("device is in single-shot mode - continuous mode expected");
    }
  }

  // ---- 3. Sampling clock ---------------------------------------------------
  Serial.println(F("\n[3/6] SAMPLING CLOCK"));
  Serial.print(F("      mode         : "));
  Serial.println(asvAdcModeName());
  if (asvAdcMode() == ASV_MODE_RDY_IRQ) {
    pass("ALRT/RDY interrupt is live - hardware-paced sampling");
  } else if (asvAdcMode() == ASV_MODE_POLLED) {
    warn("ALRT/RDY not detected on GPIO27 - running software-paced fallback.");
    Serial.println(F("             Wire ADS1115 ALRT -> ESP32 GPIO27 for best timing."));
  } else {
    fail("sampler is not running");
    allGood = false;
  }

  // ---- 4. Live signal ------------------------------------------------------
  Serial.println(F("\n[4/6] LIVE SIGNAL (1 s capture - hold still)"));
  AsvSignalStats s = asvDiagMeasureSignal(1000);
  asvDiagPrintSignalStats(s);

  if (s.n == 0) {
    allGood = false;
  } else {
    float expected = (asvAdcMode() == ASV_MODE_RDY_IRQ) ? (float)ASV_SPS
                                                        : (float)ASV_POLL_FALLBACK_HZ;
    if (s.measured_hz < expected * 0.85f) {
      warn("measured rate is well below target - check I2C speed and bus load");
      allGood = false;
    } else {
      pass("sample rate is within 15% of target");
    }

    // A completely open ADS1115 input floats and wanders; a working AD8232
    // output sits at a stable mid-supply bias (~1.65 V).
    if (fabsf(s.mean_mv) < 20.0f && s.pp_mv < 5.0f) {
      warn("input looks tied to 0 V / shorted - is AD8232 OUTPUT wired to A0?");
    } else if (fabsf(s.mean_mv) < 20.0f) {
      warn("input is near 0 V but noisy - A0 may be floating (nothing connected)");
    } else if (s.mean_mv > 1300.0f && s.mean_mv < 2000.0f) {
      pass("DC baseline ~mid-supply: consistent with a live AD8232 output");
    } else {
      Serial.println(F("      note         : baseline is not near 1.65 V. That is fine for a"));
      Serial.println(F("                     pot/function generator, unexpected for AD8232."));
    }
    asvDiagRecommendGain(s);
  }

  // ---- 5. Electrodes -------------------------------------------------------
  Serial.println(F("\n[5/6] ELECTRODES / LEAD-OFF"));
  asvDiagPrintLeadOff();

  // ---- 6. Peripherals ------------------------------------------------------
  Serial.println(F("\n[6/6] PERIPHERALS"));
#if ASV_ENABLE_OLED
  if (asvOledPresent()) {
    pass("SSD1306 responding at 0x3C");
    Serial.print(F("      frame push   : "));
    Serial.print(asvOledLastRenderUs() / 1000.0f, 1);
    Serial.println(F(" ms"));
  #if ASV_OLED_ON_SECOND_BUS
    Serial.println(F("      bus          : Wire1 - does NOT block ADC sampling"));
  #else
    warn("OLED shares the ADC bus; every refresh costs samples.");
    Serial.println(F("             Set ASV_OLED_ON_SECOND_BUS 1 and move SDA/SCL to GPIO25/26."));
  #endif
  } else {
    warn("SSD1306 not found - display disabled, acquisition unaffected");
  }
#else
  Serial.println(F("      OLED disabled at compile time"));
#endif

#if ASV_ENABLE_BLE
  Serial.print(F("      BLE          : "));
  Serial.println(asvBleStateName());
#else
  Serial.println(F("      BLE disabled at compile time"));
#endif

  AsvAdcStats *st = asvAdcStats();
  Serial.print(F("      i2c errors   : ")); Serial.println(st->i2c_errors);
  Serial.print(F("      ring drops   : ")); Serial.println(st->dropped);
  if (st->min_dt_us != 0xFFFFFFFF) {
    Serial.print(F("      sample dt    : min "));
    Serial.print(st->min_dt_us);
    Serial.print(F(" us / max "));
    Serial.print(st->max_dt_us);
    Serial.println(F(" us  <- jitter"));
  }

  rule();
  if (allGood) Serial.println(F("  RESULT: ALL CHECKS PASSED - ready to stream ('s')"));
  else         Serial.println(F("  RESULT: PROBLEMS FOUND - fix the [FAIL] lines above"));
  rule();
  Serial.println();
  return allGood;
}

// ============================================================================
void asvDiagPrintHelp() {
  Serial.println();
  rule();
  Serial.println(F("  ASV SERIAL COMMANDS  (type a letter, no Enter needed)"));
  rule();
  Serial.println(F("   h  this help"));
  Serial.println(F("   t  full hardware self-test"));
  Serial.println(F("   i  I2C bus scan"));
  Serial.println(F("   m  live monitor (human readable, 5 Hz)"));
  Serial.println(F("   n  measure noise floor / baseline (3 s)"));
  Serial.println(F("   s  START raw CSV stream  -> for ml/acquisition/collect_emg.py"));
  Serial.println(F("   x  STOP stream"));
  Serial.println(F("   g  cycle ADC gain (resolution vs range)"));
  Serial.println(F("   o  toggle OLED"));
  Serial.println(F("   r  reset counters"));
  Serial.println(F("   ?  print current status line"));
  rule();
  Serial.println();
}
