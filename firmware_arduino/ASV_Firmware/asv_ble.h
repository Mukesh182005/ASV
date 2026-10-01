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
// Push a recognised word to the app so it can be shown and spoken aloud.
// confidence is 0-100; word is truncated to ASV_BLE_WORD_MAXLEN so the packet
// stays inside a single notification. No classifier runs on the ESP32 yet, so
// nothing calls this during normal operation - it is the channel the model will
// publish through, and 'w' on the serial menu exercises it end to end.
void  asvBleNotifyWord(const char *word, uint8_t confidence);
// Send one captured utterance to the app as a burst of notifications on the
// capture characteristic. Blocks for roughly (n / ASV_BLE_CAPTURE_CHUNK) *
// ASV_BLE_CAPTURE_GAP_MS milliseconds, which is safe: this runs in loop() on
// core 0 while the sampler owns core 1, so no samples are lost.
//
// Wire format, little-endian throughout:
//   header  [0]=0xC5 [1]=0x00 [2..3]=total samples [4..5]=sample rate Hz
//   chunk   [0]=0xC5 [1]=0x01 [2..3]=start index   [4..]=int16 counts
//   footer  [0]=0xC5 [1]=0x02
void  asvBleSendCapture(const int16_t *samples, uint16_t n, uint16_t fs);
bool  asvBleConnected();
const char *asvBleStateName();
// Returns and clears the last single-byte command written by a BLE client
// (same letters as the serial menu). 0 = nothing pending.
char  asvBleTakeCommand();
