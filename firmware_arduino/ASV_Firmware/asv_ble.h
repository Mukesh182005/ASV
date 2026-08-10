/**
 * asv_ble.h -- BLE server, status/preview notifications, and a command channel.
 *
 * Design note (important):
 *   Raw 860 SPS EMG is ~1.7 kB/s. BLE notifications with a default 20-byte MTU
 *   and a 15-30 ms connection interval top out well below that, so pushing the
 *   raw stream over BLE would silently back up and distort timing. Tonight the
 *   raw stream goes over USB serial (which has ample headroom) and BLE carries
 *   a 20 Hz status + envelope preview packet. That keeps the link honest and
 *   keeps the sampler jitter-free.
 */
#pragma once
#include <Arduino.h>
#include "asv_config.h"

struct AsvBleStatus {
  bool     streaming;
  bool     adc_ok;
  bool     lead_off_p;
  bool     lead_off_n;
  float    rate_hz;
  uint32_t sample_count;
  uint32_t dropped;
  int16_t  baseline_counts;
  uint16_t pp_counts;
  int16_t  last_value;
};

void  asvBleBegin();
void  asvBleNotify(const AsvBleStatus &s);
bool  asvBleConnected();
const char *asvBleStateName();
// Returns and clears the last single-byte command written by a BLE client
// (same letters as the serial menu). 0 = nothing pending.
char  asvBleTakeCommand();
