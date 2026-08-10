/**
 * ============================================================================
 *  ASV - A Silent Voice
 *  ESP32 EMG acquisition firmware  --  ARDUINO IDE BUILD
 * ============================================================================
 *
 *  Chain:  jaw/facial electrodes -> AD8232 -> ADS1115 (A0) -> ESP32 -> USB CSV
 *                                                                  \-> BLE status
 *
 *  Board  : ESP32 Dev Module (DOIT ESP32 DEVKIT V1)
 *  Serial : 921600 baud
 *  Libs   : Adafruit SSD1306, Adafruit GFX  (ADS1115 is driven directly here)
 *
 *  Read docs/ARDUINO_IDE_SETUP.md before flashing - the partition scheme
 *  MUST be changed or the BLE build will not fit.
 *
 *  Type 'h' in the Serial Monitor for the command list.
 * ============================================================================
 */

#include <Arduino.h>
#include <Wire.h>

#include "asv_config.h"
#include "asv_adc.h"
#include "asv_oled.h"
#include "asv_ble.h"
#include "asv_diag.h"

// ============================================================================
// RUNTIME STATE
// ============================================================================
static bool     g_streaming   = false;
static bool     g_monitor     = false;
static bool     g_adcOk       = false;

static uint32_t g_lastUiMs    = 0;
static uint32_t g_lastBleMs   = 0;
static uint32_t g_lastMonMs   = 0;

// rolling window used for the measured-rate / peak-to-peak readouts
static uint32_t g_winStartMs  = 0;
static uint32_t g_winCount    = 0;
static double   g_winSum      = 0;
static int16_t  g_winMin      = 32767;
static int16_t  g_winMax      = -32768;
static float    g_measuredHz  = 0;
static float    g_baselineMv  = 0;
static float    g_ppMv        = 0;
static int16_t  g_lastValue   = 0;
static uint16_t g_lastFlags   = 0;
static uint32_t g_totalOut    = 0;

// ============================================================================
// HELPERS
// ============================================================================
static void printBanner() {
  Serial.println();
  Serial.println(F("============================================================"));
  Serial.println(F("  ASV - A SILENT VOICE   |   EMG ACQUISITION FIRMWARE"));
  Serial.println(F("============================================================"));
  Serial.print  (F("  firmware   : ")); Serial.println(F(ASV_FW_VERSION));
  Serial.print  (F("  build      : ")); Serial.print(F(__DATE__)); Serial.print(' '); Serial.println(F(__TIME__));
  Serial.print  (F("  chip       : ")); Serial.print(ESP.getChipModel());
  Serial.print  (F(" rev ")); Serial.print(ESP.getChipRevision());
  Serial.print  (F(", ")); Serial.print(ESP.getCpuFreqMHz()); Serial.println(F(" MHz"));
  Serial.print  (F("  free heap  : ")); Serial.println(ESP.getFreeHeap());
  Serial.print  (F("  ADC bus    : SDA=GPIO")); Serial.print(PIN_I2C_SDA);
  Serial.print  (F(" SCL=GPIO")); Serial.print(PIN_I2C_SCL);
  Serial.print  (F(" @ ")); Serial.print(I2C_FREQ_HZ / 1000); Serial.println(F(" kHz"));
#if ASV_ENABLE_OLED && ASV_OLED_ON_SECOND_BUS
  Serial.print  (F("  OLED bus   : SDA=GPIO")); Serial.print(PIN_I2C1_SDA);
  Serial.print  (F(" SCL=GPIO")); Serial.print(PIN_I2C1_SCL);
  Serial.print  (F(" @ ")); Serial.print(I2C1_FREQ_HZ / 1000); Serial.println(F(" kHz"));
#endif
  Serial.print  (F("  ALRT/RDY   : GPIO")); Serial.println(PIN_ADS_ALERT);
#if ASV_HAS_AD8232
  Serial.print  (F("  AD8232 LO  : LO+=GPIO")); Serial.print(PIN_AD8232_LO_P);
  Serial.print  (F("  LO-=GPIO")); Serial.println(PIN_AD8232_LO_N);
#endif
  Serial.println(F("============================================================"));
}

static void printStatusLine() {
  AsvAdcStats *st = asvAdcStats();
  Serial.print(F("[STATUS] "));
  Serial.print(g_streaming ? F("STREAMING") : F("IDLE"));
  Serial.print(F(" | mode=")); Serial.print(asvAdcModeName());
  Serial.print(F(" | rate=")); Serial.print(g_measuredHz, 1); Serial.print(F("Hz"));
  Serial.print(F(" | base=")); Serial.print(g_baselineMv, 1); Serial.print(F("mV"));
  Serial.print(F(" | pp=")); Serial.print(g_ppMv, 2); Serial.print(F("mV"));
  Serial.print(F(" | drops=")); Serial.print(st->dropped);
  Serial.print(F(" | i2cerr=")); Serial.print(st->i2c_errors);
  Serial.print(F(" | ble=")); Serial.print(asvBleStateName());
  Serial.print(F(" | leadoff="));
  Serial.print((g_lastFlags & ASV_FLAG_LO_P) ? F("+") : F("."));
  Serial.print((g_lastFlags & ASV_FLAG_LO_N) ? F("-") : F("."));
  Serial.println();
}

static void streamHeader() {
  // Lines starting with '#' are ignored by ml/acquisition/serial_reader.py
  Serial.println();
  Serial.print(F("# ASV_STREAM v2 ts_unit=us channels="));
  Serial.print(ASV_NUM_CHANNELS);
  Serial.print(F(" fs="));
  Serial.print(asvAdcMode() == ASV_MODE_RDY_IRQ ? ASV_SPS : ASV_POLL_FALLBACK_HZ);
  Serial.print(F(" uv_per_lsb="));
  Serial.print(asvAdcVoltsPerLsb() * 1e6f, 4);
  Serial.print(F(" mode="));
  Serial.println(asvAdcMode() == ASV_MODE_RDY_IRQ ? F("rdy_irq") : F("polled"));
  Serial.println(F("# columns: timestamp_us,ch0_counts"));
  Serial.println(F("--- START DATA ---"));
}

static void startStream() {
  if (g_streaming) return;
  g_monitor = false;
  asvAdcResetStats();
  AsvSample junk;
  while (asvAdcPop(junk)) {}
  g_totalOut = 0;
  streamHeader();
  g_streaming = true;
}

static void stopStream() {
  if (!g_streaming) return;
  g_streaming = false;
  Serial.println(F("--- END DATA ---"));
  AsvAdcStats *st = asvAdcStats();
  Serial.print(F("# samples_out=")); Serial.print(g_totalOut);
  Serial.print(F(" produced=")); Serial.print(st->produced);
  Serial.print(F(" dropped=")); Serial.print(st->dropped);
  Serial.print(F(" i2c_errors=")); Serial.print(st->i2c_errors);
  Serial.print(F(" dt_min_us=")); Serial.print(st->min_dt_us == 0xFFFFFFFF ? 0 : st->min_dt_us);
  Serial.print(F(" dt_max_us=")); Serial.println(st->max_dt_us);
  Serial.println();
}

// ============================================================================
// COMMANDS
// ============================================================================
static void handleCommand(char c) {
  switch (c) {
    case 'h': case 'H': asvDiagPrintHelp(); break;

    case 't': case 'T':
      stopStream();
      asvDiagRunSelfTest();
      break;

    case 'i': case 'I':
      asvDiagI2cScan(Wire, "bus A (ADS1115)", PIN_I2C_SDA, PIN_I2C_SCL);
#if ASV_ENABLE_OLED && ASV_OLED_ON_SECOND_BUS
      asvDiagI2cScan(Wire1, "bus B (OLED)", PIN_I2C1_SDA, PIN_I2C1_SCL);
#endif
      break;

    case 'n': case 'N': {
      stopStream();
      Serial.println(F("\n[NOISE] Measuring for 3 s - stay completely still..."));
      AsvSignalStats s = asvDiagMeasureSignal(3000);
      asvDiagPrintSignalStats(s);
      asvDiagRecommendGain(s);
      asvDiagPrintLeadOff();
      Serial.println();
      break;
    }

    case 'm': case 'M':
      stopStream();
      g_monitor = !g_monitor;
      Serial.println(g_monitor ? F("[MON] live monitor ON") : F("[MON] live monitor OFF"));
      break;

    case 's': case 'S': startStream(); break;
    case 'x': case 'X': stopStream();  break;

    case 'g': case 'G': {
      uint8_t next = (asvAdcGetGain() + 1) % 6;
      asvAdcSetGain(next);
      Serial.print(F("[ADC] gain -> "));
      Serial.println(asvAdcGainName());
      break;
    }

    case 'o': case 'O':
      asvOledSetEnabled(!asvOledEnabled());
      Serial.println(asvOledEnabled() ? F("[OLED] enabled") : F("[OLED] disabled"));
      break;

    case 'r': case 'R':
      asvAdcResetStats();
      g_totalOut = 0;
      Serial.println(F("[STATS] counters reset"));
      break;

    case '?': printStatusLine(); break;

    default: break;   // ignore CR/LF and stray bytes
  }
}

// ============================================================================
// SETUP
// ============================================================================
void setup() {
  Serial.setTxBufferSize(ASV_SERIAL_TX_BUF);
  Serial.begin(ASV_SERIAL_BAUD);
  delay(400);

  printBanner();

  // ---- OLED first so it can show progress -----------------------------------
#if ASV_ENABLE_OLED
  Serial.println(F("[BOOT] OLED..."));
  if (asvOledBegin()) {
    Serial.println(F("[BOOT] OLED ready"));
    asvOledSplash();
  } else {
    Serial.println(F("[BOOT] OLED NOT FOUND (continuing without display)"));
  }
#endif

  // ---- ADS1115 ---------------------------------------------------------------
  Serial.println(F("[BOOT] ADS1115..."));
  g_adcOk = asvAdcBegin();
  if (!g_adcOk) {
    Serial.println(F("[BOOT] *** ADS1115 NOT RESPONDING AT 0x48 ***"));
    Serial.println(F("       Check: VDD->3.3V, GND->GND, SDA->GPIO21, SCL->GPIO22,"));
    Serial.println(F("              ADDR->GND, and that both boards share a ground."));
    asvOledMessage("ADS1115 MISSING", "check I2C wiring");
  } else {
    Serial.println(F("[BOOT] ADS1115 configured (continuous, 860 SPS)"));
    Serial.print  (F("[BOOT] gain: ")); Serial.println(asvAdcGainName());

    Serial.println(F("[BOOT] probing ALRT/RDY line..."));
    AsvMode m = asvAdcSelectMode();
    Serial.print(F("[BOOT] sampling mode: "));
    Serial.println(asvAdcModeName());
    if (m == ASV_MODE_POLLED)
      Serial.println(F("[BOOT] tip: wire ADS1115 ALRT -> GPIO27 for hardware-paced 860 SPS"));

    asvAdcStartSampler();
    Serial.println(F("[BOOT] sampler task running on core 1 (priority 5)"));
  }

  // ---- BLE -------------------------------------------------------------------
#if ASV_ENABLE_BLE
  Serial.println(F("[BOOT] BLE..."));
  asvBleBegin();
#endif

  delay(300);
  asvDiagRunSelfTest();
  asvDiagPrintHelp();

  g_winStartMs = millis();
}

// ============================================================================
// LOOP  (runs on core 0 - the sampler owns core 1)
// ============================================================================
void loop() {
  // ---- commands --------------------------------------------------------------
  while (Serial.available()) handleCommand((char)Serial.read());
  char bc = asvBleTakeCommand();
  if (bc) handleCommand(bc);

  // ---- drain the ring --------------------------------------------------------
  // Bounded per pass so the UI/BLE work below never starves.
  uint32_t budget = 512;
  AsvSample s;
  while (budget-- && asvAdcPop(s)) {
    g_lastValue = s.v;
    g_lastFlags = s.flags;

    g_winCount++;
    g_winSum += s.v;
    if (s.v < g_winMin) g_winMin = s.v;
    if (s.v > g_winMax) g_winMax = s.v;

    if (g_streaming) {
      char buf[24];
      int n = snprintf(buf, sizeof(buf), "%lu,%d\n", (unsigned long)s.t_us, (int)s.v);
      Serial.write((const uint8_t *)buf, n);
      g_totalOut++;
    }
  }

  uint32_t now = millis();

  // ---- rolling stats every 500 ms -------------------------------------------
  if (now - g_winStartMs >= 500) {
    float dt = (now - g_winStartMs) / 1000.0f;
    g_measuredHz = g_winCount / dt;
    if (g_winCount) {
      float vpl_mv = asvAdcVoltsPerLsb() * 1000.0f;
      g_baselineMv = (float)(g_winSum / g_winCount) * vpl_mv;
      g_ppMv       = (float)(g_winMax - g_winMin) * vpl_mv;
    }
    g_winStartMs = now;
    g_winCount = 0;
    g_winSum = 0;
    g_winMin = 32767;
    g_winMax = -32768;
  }

  // ---- human-readable monitor -----------------------------------------------
  if (g_monitor && now - g_lastMonMs >= 200) {
    g_lastMonMs = now;
    Serial.print(F("[MON] raw="));
    Serial.print(g_lastValue);
    Serial.print(F("  "));
    Serial.print(g_lastValue * asvAdcVoltsPerLsb() * 1000.0f, 2);
    Serial.print(F(" mV | rate="));
    Serial.print(g_measuredHz, 1);
    Serial.print(F(" Hz | pp="));
    Serial.print(g_ppMv, 2);
    Serial.print(F(" mV | lead="));
    Serial.print((g_lastFlags & ASV_FLAG_LO_P) ? F("OFF+") : F("ok+"));
    Serial.print((g_lastFlags & ASV_FLAG_LO_N) ? F(" OFF-") : F(" ok-"));
    Serial.println();
  }

  // ---- OLED (second I2C bus - never blocks the ADC) --------------------------
#if ASV_ENABLE_OLED
  if (now - g_lastUiMs >= OLED_REFRESH_MS) {
    g_lastUiMs = now;
    AsvUiState ui;
    ui.ble_connected = asvBleConnected();
    ui.adc_ok        = g_adcOk;
    ui.streaming     = g_streaming;
    ui.measured_hz   = g_measuredHz;
    ui.dropped       = asvAdcStats()->dropped;
    ui.baseline_mv   = g_baselineMv;
    ui.pp_mv         = g_ppMv;
    ui.lead_off_p    = (g_lastFlags & ASV_FLAG_LO_P) != 0;
    ui.lead_off_n    = (g_lastFlags & ASV_FLAG_LO_N) != 0;
    ui.mode          = asvAdcModeName();
    asvOledStatus(ui);
  }
#endif

  // ---- BLE status ------------------------------------------------------------
#if ASV_ENABLE_BLE
  if (now - g_lastBleMs >= ASV_BLE_NOTIFY_MS) {
    g_lastBleMs = now;
    if (asvBleConnected()) {
      AsvBleStatus b;
      b.streaming       = g_streaming;
      b.adc_ok          = g_adcOk;
      b.lead_off_p      = (g_lastFlags & ASV_FLAG_LO_P) != 0;
      b.lead_off_n      = (g_lastFlags & ASV_FLAG_LO_N) != 0;
      b.rate_hz         = g_measuredHz;
      b.sample_count    = asvAdcStats()->produced;
      b.dropped         = asvAdcStats()->dropped;
      b.baseline_counts = (int16_t)(g_baselineMv / (asvAdcVoltsPerLsb() * 1000.0f));
      b.pp_counts       = (uint16_t)(g_ppMv / (asvAdcVoltsPerLsb() * 1000.0f));
      b.last_value      = g_lastValue;
      asvBleNotify(b);
    }
  }
#endif

  // Yield to the idle task; sampling is unaffected (it lives on core 1).
  if (!g_streaming) delay(1);
}
