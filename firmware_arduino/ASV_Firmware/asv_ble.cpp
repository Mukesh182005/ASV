#include <Arduino.h>
#include "asv_ble.h"

#if ASV_ENABLE_BLE

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>

#if defined(ESP_ARDUINO_VERSION_MAJOR) && (ESP_ARDUINO_VERSION_MAJOR >= 3)
  #define ASV_CORE3 1
#else
  #define ASV_CORE3 0
#endif

// Client Characteristic Configuration Descriptor. We add it by raw UUID rather
// than via BLE2902, because BLE2902 is deprecated on core 3.x and absent from
// some builds, while BLEDescriptor + getDescriptorByUUID exist on every version.
static const uint16_t kCccdUuid = 0x2902;
static uint8_t kCccdInit[2] = { 0x00, 0x00 };

static BLEServer         *g_server  = nullptr;
static BLECharacteristic *g_status  = nullptr;
static BLECharacteristic *g_cmd     = nullptr;
static BLECharacteristic *g_word    = nullptr;
static BLECharacteristic *g_capture = nullptr;
static volatile bool      g_connected = false;
static volatile char      g_pendingCmd = 0;

class AsvServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer *) override {
    g_connected = true;
    Serial.println("[BLE] client connected");
  }
  void onDisconnect(BLEServer *srv) override {
    g_connected = false;
    Serial.println("[BLE] client disconnected - re-advertising");
    srv->startAdvertising();
  }
};

class AsvCmdCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *c) override {
    uint8_t *data = c->getData();
    size_t   len  = c->getLength();
    if (data && len > 0) g_pendingCmd = (char)data[0];
  }
};

static AsvServerCallbacks g_serverCb;
static AsvCmdCallbacks    g_cmdCb;

void asvBleBegin() {
#if ASV_CORE3
  BLEDevice::init(String(ASV_BLE_NAME));
#else
  BLEDevice::init(std::string(ASV_BLE_NAME));
#endif
  BLEDevice::setMTU(64);

  g_server = BLEDevice::createServer();
  g_server->setCallbacks(&g_serverCb);

  BLEService *svc = g_server->createService(ASV_BLE_SERVICE_UUID);

  g_status = svc->createCharacteristic(
      ASV_BLE_STATUS_UUID,
      BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY);
  if (g_status->getDescriptorByUUID(BLEUUID(kCccdUuid)) == nullptr) {
    BLEDescriptor *cccd = new BLEDescriptor(BLEUUID(kCccdUuid));
    cccd->setValue(kCccdInit, sizeof(kCccdInit));
    g_status->addDescriptor(cccd);
  }

  g_cmd = svc->createCharacteristic(
      ASV_BLE_CMD_UUID,
      BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
  g_cmd->setCallbacks(&g_cmdCb);

  g_word = svc->createCharacteristic(
      ASV_BLE_WORD_UUID,
      BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY);
  if (g_word->getDescriptorByUUID(BLEUUID(kCccdUuid)) == nullptr) {
    BLEDescriptor *cccd = new BLEDescriptor(BLEUUID(kCccdUuid));
    cccd->setValue(kCccdInit, sizeof(kCccdInit));
    g_word->addDescriptor(cccd);
  }

  g_capture = svc->createCharacteristic(
      ASV_BLE_CAPTURE_UUID,
      BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY);
  if (g_capture->getDescriptorByUUID(BLEUUID(kCccdUuid)) == nullptr) {
    BLEDescriptor *cccd = new BLEDescriptor(BLEUUID(kCccdUuid));
    cccd->setValue(kCccdInit, sizeof(kCccdInit));
    g_capture->addDescriptor(cccd);
  }

  svc->start();

  BLEAdvertising *adv = BLEDevice::getAdvertising();
  adv->addServiceUUID(ASV_BLE_SERVICE_UUID);
  adv->setScanResponse(true);
  adv->setMinPreferred(0x06);
  adv->setMaxPreferred(0x12);
  BLEDevice::startAdvertising();

  Serial.print("[BLE] advertising as \"");
  Serial.print(ASV_BLE_NAME);
  Serial.println("\"");
  Serial.print("[BLE] service   ");
  Serial.println(ASV_BLE_SERVICE_UUID);
  Serial.print("[BLE] status ch ");
  Serial.println(ASV_BLE_STATUS_UUID);
  Serial.print("[BLE] cmd ch    ");
  Serial.println(ASV_BLE_CMD_UUID);
}

void asvBleNotify(const AsvBleStatus &s) {
  if (!g_status || !g_connected) return;

  uint8_t pkt[20];
  uint16_t rate10 = (uint16_t)(s.rate_hz * 10.0f);
  uint8_t flags = 0;
  if (s.streaming)  flags |= 0x01;
  if (s.adc_ok)     flags |= 0x02;
  if (s.lead_off_p) flags |= 0x04;
  if (s.lead_off_n) flags |= 0x08;

  pkt[0]  = 0xA5;                       // magic
  pkt[1]  = flags;
  pkt[2]  = (uint8_t)(rate10 & 0xFF);
  pkt[3]  = (uint8_t)(rate10 >> 8);
  pkt[4]  = (uint8_t)(s.sample_count      & 0xFF);
  pkt[5]  = (uint8_t)((s.sample_count>>8) & 0xFF);
  pkt[6]  = (uint8_t)((s.sample_count>>16)& 0xFF);
  pkt[7]  = (uint8_t)((s.sample_count>>24)& 0xFF);
  pkt[8]  = (uint8_t)(s.dropped      & 0xFF);
  pkt[9]  = (uint8_t)((s.dropped>>8) & 0xFF);
  pkt[10] = (uint8_t)(s.baseline_counts      & 0xFF);
  pkt[11] = (uint8_t)((s.baseline_counts>>8) & 0xFF);
  pkt[12] = (uint8_t)(s.pp_counts      & 0xFF);
  pkt[13] = (uint8_t)((s.pp_counts>>8) & 0xFF);
  pkt[14] = (uint8_t)(s.last_value      & 0xFF);
  pkt[15] = (uint8_t)((s.last_value>>8) & 0xFF);
  pkt[16] = 0; pkt[17] = 0; pkt[18] = 0; pkt[19] = 0;

  g_status->setValue(pkt, sizeof(pkt));
  g_status->notify();
}

void asvBleNotifyWord(const char *word, uint8_t confidence) {
  if (!g_word || !g_connected || !word) return;

  uint8_t n = 0;
  while (word[n] && n < ASV_BLE_WORD_MAXLEN) n++;
  if (n == 0) return;

  uint8_t pkt[3 + ASV_BLE_WORD_MAXLEN];
  pkt[0] = 0xC3;                                    // magic
  pkt[1] = confidence > 100 ? 100 : confidence;
  pkt[2] = n;
  for (uint8_t i = 0; i < n; i++) pkt[3 + i] = (uint8_t)word[i];

  g_word->setValue(pkt, (size_t)(3 + n));
  g_word->notify();
}

void asvBleSendCapture(const int16_t *samples, uint16_t n, uint16_t fs) {
  if (!g_capture || !g_connected || !samples || n == 0) return;

  uint8_t hdr[6];
  hdr[0] = 0xC5;
  hdr[1] = 0x00;                        // header
  hdr[2] = (uint8_t)(n & 0xFF);
  hdr[3] = (uint8_t)(n >> 8);
  hdr[4] = (uint8_t)(fs & 0xFF);
  hdr[5] = (uint8_t)(fs >> 8);
  g_capture->setValue(hdr, sizeof(hdr));
  g_capture->notify();
  delay(ASV_BLE_CAPTURE_GAP_MS);

  uint8_t buf[4 + ASV_BLE_CAPTURE_CHUNK * 2];
  for (uint16_t i = 0; i < n; i += ASV_BLE_CAPTURE_CHUNK) {
    // The client drops the whole capture if it disconnects mid-burst; stop
    // early rather than spending a second notifying nobody.
    if (!g_connected) return;

    uint16_t m = n - i;
    if (m > ASV_BLE_CAPTURE_CHUNK) m = ASV_BLE_CAPTURE_CHUNK;

    buf[0] = 0xC5;
    buf[1] = 0x01;                      // chunk
    buf[2] = (uint8_t)(i & 0xFF);
    buf[3] = (uint8_t)(i >> 8);
    for (uint16_t k = 0; k < m; k++) {
      int16_t v = samples[i + k];
      buf[4 + k * 2] = (uint8_t)(v & 0xFF);
      buf[5 + k * 2] = (uint8_t)((v >> 8) & 0xFF);
    }
    g_capture->setValue(buf, (size_t)(4 + m * 2));
    g_capture->notify();
    delay(ASV_BLE_CAPTURE_GAP_MS);
  }

  uint8_t ftr[2] = { 0xC5, 0x02 };      // footer
  g_capture->setValue(ftr, sizeof(ftr));
  g_capture->notify();
}

bool asvBleConnected() { return g_connected; }

const char *asvBleStateName() { return g_connected ? "CONNECTED" : "ADVERTISING"; }

char asvBleTakeCommand() {
  char c = g_pendingCmd;
  g_pendingCmd = 0;
  return c;
}

#else  // ---------------------------------------------------------------- stub

void asvBleBegin() {}
void asvBleNotify(const AsvBleStatus &) {}
void asvBleNotifyWord(const char *, uint8_t) {}
void asvBleSendCapture(const int16_t *, uint16_t, uint16_t) {}
bool asvBleConnected() { return false; }
const char *asvBleStateName() { return "DISABLED"; }
char asvBleTakeCommand() { return 0; }

#endif
