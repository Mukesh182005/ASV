/**
 * asv_adc.h -- Register-level ADS1115 driver with conversion-ready interrupt.
 *
 * Why not the Adafruit library?
 *   The ALRT/RDY conversion-ready trick needs exact control of the comparator
 *   threshold registers, and the library API for that changed between versions.
 *   This driver talks to the four ADS1115 registers directly, so it behaves
 *   identically on every ESP32 core release.
 *
 * Threading model:
 *   ISR (GPIO27 falling edge) --notify--> sampler task (core 1, prio 5)
 *   sampler task --push--> lock-free ring buffer --pop--> loop() on core 0
 *   Single producer / single consumer, so no locking is needed on the ring.
 */
#pragma once
#include <Arduino.h>
#include "asv_config.h"

struct AsvSample {
  uint32_t t_us;    // micros() captured at the moment the sample was read
  int16_t  v;       // raw signed ADC counts
  uint16_t flags;   // bit0 = LO+ (lead off), bit1 = LO- (lead off)
};

#define ASV_FLAG_LO_P  0x0001
#define ASV_FLAG_LO_N  0x0002

enum AsvMode : uint8_t {
  ASV_MODE_NONE    = 0,
  ASV_MODE_RDY_IRQ = 1,   // hardware conversion-ready interrupt (best)
  ASV_MODE_POLLED  = 2    // timer-paced polling fallback
};

struct AsvAdcStats {
  volatile uint32_t produced;    // samples pushed into the ring
  volatile uint32_t consumed;    // samples pulled out by the consumer
  volatile uint32_t dropped;     // ring overflow -> host could not keep up
  volatile uint32_t irqs;        // ALRT/RDY edges seen
  volatile uint32_t timeouts;    // sampler waited and got nothing
  volatile uint32_t i2c_errors;  // failed conversion reads
  volatile uint32_t min_dt_us;
  volatile uint32_t max_dt_us;
  volatile uint32_t last_dt_us;
};

// ---- lifecycle -------------------------------------------------------------
bool    asvAdcBegin();            // init I2C bus A + configure ADS1115
bool    asvAdcPresent();          // does something ACK at 0x48?
bool    asvAdcRegisterSelfTest(); // write/read-back proof of real comms
AsvMode asvAdcSelectMode();       // probe the RDY line, fall back to polling
void    asvAdcStartSampler();     // launch the core-1 sampling task

// ---- data path -------------------------------------------------------------
bool    asvAdcPop(AsvSample &out);
uint32_t asvAdcAvailable();

// ---- control ---------------------------------------------------------------
void    asvAdcSetGain(uint8_t idx);
uint8_t asvAdcGetGain();
float   asvAdcVoltsPerLsb();
const char *asvAdcGainName();
AsvMode asvAdcMode();
const char *asvAdcModeName();

// ---- introspection ---------------------------------------------------------
AsvAdcStats *asvAdcStats();
void    asvAdcResetStats();
uint16_t asvAdcReadConfigRegister();
int16_t asvAdcReadBlocking();      // one-shot read, bypasses the ring
uint16_t asvAdcLeadOffFlags();

// ---- raw I2C helpers (also used by the diagnostics module) -----------------
bool    asvAdcWriteReg(uint8_t reg, uint16_t value);
bool    asvAdcReadReg(uint8_t reg, uint16_t &value);
void    asvI2cLock();
void    asvI2cUnlock();
