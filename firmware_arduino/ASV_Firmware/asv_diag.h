/**
 * asv_diag.h -- Hardware bring-up self-test.
 * Answers one question: "is every link in the chain actually working?"
 */
#pragma once
#include <Arduino.h>
#include "asv_config.h"

struct AsvSignalStats {
  uint32_t n;
  float    mean_counts;
  int16_t  min_counts;
  int16_t  max_counts;
  float    rms_ac_counts;    // RMS after removing DC -- this is your noise floor
  float    mean_mv;
  float    pp_mv;
  float    rms_ac_uv;
  float    measured_hz;
  uint32_t lead_off_samples;
  bool     railed_low;
  bool     railed_high;
};

void  asvDiagI2cScan(TwoWire &bus, const char *label, int sda, int scl);
bool  asvDiagRunSelfTest();                      // prints a full PASS/FAIL report
AsvSignalStats asvDiagMeasureSignal(uint32_t ms);
void  asvDiagPrintSignalStats(const AsvSignalStats &s);
void  asvDiagRecommendGain(const AsvSignalStats &s);
void  asvDiagPrintLeadOff();
void  asvDiagPrintHelp();
