#include <Arduino.h>
#include <Wire.h>
#include "asv_adc.h"

// ============================================================================
// ADS1115 REGISTER MAP
// ============================================================================
#define ADS_REG_CONVERSION  0x00
#define ADS_REG_CONFIG      0x01
#define ADS_REG_LO_THRESH   0x02
#define ADS_REG_HI_THRESH   0x03

// Config register fields
#define ADS_OS_SINGLE       0x8000
#define ADS_MUX_AIN0        0x4000   // AIN0 vs GND
#define ADS_MODE_CONTINUOUS 0x0000
#define ADS_MODE_SINGLE     0x0100
#define ADS_DR_860SPS       0x00E0
#define ADS_COMP_QUE_1CONV  0x0000   // required so ALRT asserts every conversion
#define ADS_COMP_QUE_OFF    0x0003

// PGA table.  index -> {config bits, volts-per-LSB, human name}
struct GainEntry { uint16_t bits; float vpl; const char *name; };
static const GainEntry kGains[6] = {
  { 0x0000, 187.5e-6f, "+/-6.144V (187.5 uV/LSB)" },
  { 0x0200, 125.0e-6f, "+/-4.096V (125.0 uV/LSB)" },
  { 0x0400,  62.5e-6f, "+/-2.048V ( 62.5 uV/LSB)" },
  { 0x0600,  31.25e-6f,"+/-1.024V ( 31.2 uV/LSB)" },
  { 0x0800,  15.625e-6f,"+/-0.512V ( 15.6 uV/LSB)" },
  { 0x0A00,  7.8125e-6f,"+/-0.256V (  7.8 uV/LSB)" }
};

// ============================================================================
// STATE
// ============================================================================
static uint8_t        g_gainIdx  = ASV_DEFAULT_GAIN_IDX;
static AsvMode        g_mode     = ASV_MODE_NONE;
static TaskHandle_t   g_sampler  = nullptr;
static SemaphoreHandle_t g_wireMux = nullptr;
static AsvAdcStats    g_stats;

static AsvSample      g_ring[ASV_RING_SIZE];
static volatile uint32_t g_head = 0;
static volatile uint32_t g_tail = 0;

static volatile uint32_t g_irqCount = 0;

// The ADS1115 keeps its address-pointer between transactions, so once it points
// at the conversion register we can read a sample with a single I2C read
// instead of a write+read. That halves bus traffic in the 860 Hz sampling path.
// Any register write moves the pointer, so every writer updates this.
static uint8_t g_pointerReg = 0xFF;   // 0xFF = unknown

// ============================================================================
// I2C PRIMITIVES  (bus A / Wire is reserved for the ADS1115)
// ============================================================================
void asvI2cLock()   { if (g_wireMux) xSemaphoreTake(g_wireMux, portMAX_DELAY); }
void asvI2cUnlock() { if (g_wireMux) xSemaphoreGive(g_wireMux); }

bool asvAdcWriteReg(uint8_t reg, uint16_t value) {
  asvI2cLock();
  Wire.beginTransmission(ADS1115_I2C_ADDR);
  Wire.write(reg);
  Wire.write((uint8_t)(value >> 8));
  Wire.write((uint8_t)(value & 0xFF));
  bool ok = (Wire.endTransmission() == 0);
  g_pointerReg = ok ? reg : 0xFF;
  asvI2cUnlock();
  if (!ok) g_stats.i2c_errors++;
  return ok;
}

bool asvAdcReadReg(uint8_t reg, uint16_t &value) {
  asvI2cLock();
  Wire.beginTransmission(ADS1115_I2C_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission() != 0) {
    g_pointerReg = 0xFF;
    asvI2cUnlock(); g_stats.i2c_errors++; return false;
  }
  g_pointerReg = reg;
  // NOTE: cast to (int,int) picks the unambiguous TwoWire overload. Passing
  // (uint8_t,uint8_t) is ambiguous on the ESP32 core and will not compile.
  if (Wire.requestFrom((int)ADS1115_I2C_ADDR, (int)2) != 2) {
    asvI2cUnlock(); g_stats.i2c_errors++; return false;
  }
  uint16_t hi = Wire.read();
  uint16_t lo = Wire.read();
  asvI2cUnlock();
  value = (hi << 8) | lo;
  return true;
}

// Fast path used by the sampler task: read the conversion register only.
static inline bool readConversionFast(int16_t &out) {
  asvI2cLock();

  // Point at the conversion register only when it isn't already there.
  if (g_pointerReg != ADS_REG_CONVERSION) {
    Wire.beginTransmission(ADS1115_I2C_ADDR);
    Wire.write((uint8_t)ADS_REG_CONVERSION);
    if (Wire.endTransmission() != 0) {
      g_pointerReg = 0xFF;
      asvI2cUnlock();
      g_stats.i2c_errors++;
      return false;
    }
    g_pointerReg = ADS_REG_CONVERSION;
  }

  if (Wire.requestFrom((int)ADS1115_I2C_ADDR, (int)2) != 2) {
    g_pointerReg = 0xFF;                    // resync on the next read
    asvI2cUnlock();
    g_stats.i2c_errors++;
    return false;
  }
  uint16_t hi = Wire.read();
  uint16_t lo = Wire.read();
  asvI2cUnlock();
  out = (int16_t)((hi << 8) | lo);
  return true;
}

// ============================================================================
// CONFIGURATION
// ============================================================================
static uint16_t buildConfig() {
  return ADS_MUX_AIN0
       | kGains[g_gainIdx].bits
       | ADS_MODE_CONTINUOUS
       | ADS_DR_860SPS
       | ADS_COMP_QUE_1CONV;   // comparator queue = 1 -> ALRT pulses per conversion
}

// Turning ALRT/RDY into a conversion-ready strobe:
//   lo_thresh MSB = 0, hi_thresh MSB = 1  (datasheet section "Conversion Ready Pin")
static bool armReadyPin() {
  bool ok = asvAdcWriteReg(ADS_REG_LO_THRESH, 0x0000);
  ok &= asvAdcWriteReg(ADS_REG_HI_THRESH, 0x8000);
  return ok;
}

static bool applyConfig() {
  if (!armReadyPin()) return false;
  return asvAdcWriteReg(ADS_REG_CONFIG, buildConfig());
}

// ============================================================================
// RING BUFFER  (single producer on core 1, single consumer on core 0)
// ============================================================================
static inline bool ringPush(const AsvSample &s) {
  uint32_t h = g_head;
  uint32_t n = (h + 1) & (ASV_RING_SIZE - 1);
  if (n == g_tail) return false;          // full -- consumer is too slow
  g_ring[h] = s;
  g_head = n;
  return true;
}

bool asvAdcPop(AsvSample &out) {
  uint32_t t = g_tail;
  if (t == g_head) return false;
  out = g_ring[t];
  g_tail = (t + 1) & (ASV_RING_SIZE - 1);
  g_stats.consumed++;
  return true;
}

uint32_t asvAdcAvailable() {
  return (g_head - g_tail) & (ASV_RING_SIZE - 1);
}

// ============================================================================
// LEAD-OFF (AD8232 LO+ / LO-)
// ============================================================================
uint16_t asvAdcLeadOffFlags() {
#if ASV_HAS_AD8232
  uint16_t f = 0;
  int p = digitalRead(PIN_AD8232_LO_P);
  int n = digitalRead(PIN_AD8232_LO_N);
  #if AD8232_LO_ACTIVE_HIGH
    if (p == HIGH) f |= ASV_FLAG_LO_P;
    if (n == HIGH) f |= ASV_FLAG_LO_N;
  #else
    if (p == LOW)  f |= ASV_FLAG_LO_P;
    if (n == LOW)  f |= ASV_FLAG_LO_N;
  #endif
  return f;
#else
  return 0;
#endif
}

// ============================================================================
// INTERRUPT + SAMPLER TASK
// ============================================================================
static void IRAM_ATTR asvRdyIsr() {
  g_irqCount++;
  if (g_sampler) {
    BaseType_t hpw = pdFALSE;
    vTaskNotifyGiveFromISR(g_sampler, &hpw);
    if (hpw) portYIELD_FROM_ISR();
  }
}

static void asvSamplerTask(void *) {
  TickType_t lastWake = xTaskGetTickCount();
  const TickType_t pollPeriod = pdMS_TO_TICKS(1000 / ASV_POLL_FALLBACK_HZ);
  uint32_t prev_us = 0;

  for (;;) {
    if (g_mode == ASV_MODE_RDY_IRQ) {
      if (ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(50)) == 0) {
        g_stats.timeouts++;
        continue;                       // RDY line went quiet -- report, keep trying
      }
    } else {
      vTaskDelayUntil(&lastWake, pollPeriod ? pollPeriod : 1);
    }

    AsvSample s;
    s.t_us  = micros();
    s.flags = asvAdcLeadOffFlags();

    if (!readConversionFast(s.v)) continue;

    if (prev_us) {
      uint32_t dt = s.t_us - prev_us;
      g_stats.last_dt_us = dt;
      if (dt < g_stats.min_dt_us) g_stats.min_dt_us = dt;
      if (dt > g_stats.max_dt_us) g_stats.max_dt_us = dt;
    }
    prev_us = s.t_us;

    if (ringPush(s)) g_stats.produced++;
    else             g_stats.dropped++;
  }
}

// ============================================================================
// PUBLIC LIFECYCLE
// ============================================================================
bool asvAdcBegin() {
  if (!g_wireMux) g_wireMux = xSemaphoreCreateMutex();

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL, I2C_FREQ_HZ);
  Wire.setTimeOut(50);

#if ASV_HAS_AD8232
  pinMode(PIN_AD8232_LO_P, INPUT);   // GPIO34/35 are input-only, no pull-ups
  pinMode(PIN_AD8232_LO_N, INPUT);
#endif

  pinMode(PIN_ADS_ALERT, INPUT_PULLUP);

  asvAdcResetStats();

  if (!asvAdcPresent()) return false;
  return applyConfig();
}

bool asvAdcPresent() {
  asvI2cLock();
  Wire.beginTransmission(ADS1115_I2C_ADDR);
  bool ok = (Wire.endTransmission() == 0);
  asvI2cUnlock();
  return ok;
}

// Proves we are really talking to an ADS1115, not just seeing a stray ACK.
bool asvAdcRegisterSelfTest() {
  uint16_t saveLo = 0, saveHi = 0;
  if (!asvAdcReadReg(ADS_REG_LO_THRESH, saveLo)) return false;
  if (!asvAdcReadReg(ADS_REG_HI_THRESH, saveHi)) return false;

  const uint16_t patternLo = 0x1234;
  const uint16_t patternHi = 0x5A5A;
  uint16_t back = 0;
  bool ok = true;

  if (!asvAdcWriteReg(ADS_REG_LO_THRESH, patternLo)) return false;
  if (!asvAdcReadReg(ADS_REG_LO_THRESH, back)) return false;
  ok &= (back == patternLo);

  if (!asvAdcWriteReg(ADS_REG_HI_THRESH, patternHi)) return false;
  if (!asvAdcReadReg(ADS_REG_HI_THRESH, back)) return false;
  ok &= (back == patternHi);

  // restore RDY arming regardless of the outcome
  asvAdcWriteReg(ADS_REG_LO_THRESH, 0x0000);
  asvAdcWriteReg(ADS_REG_HI_THRESH, 0x8000);
  (void)saveLo; (void)saveHi;
  return ok;
}

uint16_t asvAdcReadConfigRegister() {
  uint16_t v = 0;
  asvAdcReadReg(ADS_REG_CONFIG, v);
  return v;
}

AsvMode asvAdcSelectMode() {
  // Make sure conversions are actually running before we look at the line.
  applyConfig();
  delay(20);

  noInterrupts();
  g_irqCount = 0;
  interrupts();

  attachInterrupt(digitalPinToInterrupt(PIN_ADS_ALERT), asvRdyIsr, FALLING);
  uint32_t t0 = millis();
  while (millis() - t0 < 250) { delay(1); }
  uint32_t seen = g_irqCount;

  // At 860 SPS we expect ~215 edges in 250 ms. Accept anything above 50 as
  // "the wire is really there"; below that the pin is floating or unwired.
  if (seen >= 50) {
    g_mode = ASV_MODE_RDY_IRQ;
  } else {
    detachInterrupt(digitalPinToInterrupt(PIN_ADS_ALERT));
    g_mode = ASV_MODE_POLLED;
  }
  g_stats.irqs = seen;
  return g_mode;
}

void asvAdcStartSampler() {
  if (g_sampler) return;
  // Core 1, priority 5: above loop() (prio 1) and away from the BLE/WiFi stack
  // which lives on core 0. This is what lets BLE and the OLED stay enabled
  // without stealing samples.
  xTaskCreatePinnedToCore(asvSamplerTask, "asv_adc", 4096, nullptr, 5, &g_sampler, 1);
}

// ============================================================================
// CONTROL / INTROSPECTION
// ============================================================================
void asvAdcSetGain(uint8_t idx) {
  if (idx > 5) idx = 5;
  g_gainIdx = idx;
  applyConfig();
}
uint8_t     asvAdcGetGain()     { return g_gainIdx; }
float       asvAdcVoltsPerLsb() { return kGains[g_gainIdx].vpl; }
const char *asvAdcGainName()    { return kGains[g_gainIdx].name; }
AsvMode     asvAdcMode()        { return g_mode; }

const char *asvAdcModeName() {
  switch (g_mode) {
    case ASV_MODE_RDY_IRQ: return "RDY-INTERRUPT (860 SPS, hardware paced)";
    case ASV_MODE_POLLED:  return "POLLED (500 SPS, software paced)";
    default:               return "NOT RUNNING";
  }
}

AsvAdcStats *asvAdcStats() { return &g_stats; }

void asvAdcResetStats() {
  g_stats.produced = g_stats.consumed = g_stats.dropped = 0;
  g_stats.irqs = g_stats.timeouts = g_stats.i2c_errors = 0;
  g_stats.min_dt_us = 0xFFFFFFFF;
  g_stats.max_dt_us = 0;
  g_stats.last_dt_us = 0;
}

int16_t asvAdcReadBlocking() {
  int16_t v = 0;
  readConversionFast(v);
  return v;
}
