#include <Arduino.h>
#include "ble_test.h"

/**
 * BLE Module Implementation
 * Bluetooth Low Energy Server and Advertising
 */

// Server callback class for connection monitoring
class ServerCallbacks : public BLEServerCallbacks {
public:
    BLEModule* parent = nullptr;
    
    void onConnect(BLEServer* pServer) {
        Serial.println("[BLE] CLIENT CONNECTED!");
        connected = true;
        if (parent) parent->connected = true;
    }
    
    void onDisconnect(BLEServer* pServer) {
        Serial.println("[BLE] CLIENT DISCONNECTED!");
        connected = false;
        if (parent) parent->connected = false;
        
        // Restart advertising
        pServer->startAdvertising();
    }
    
    bool connected = false;
};

ServerCallbacks server_callbacks;

void BLEModule::begin() {
    Serial.println("[BLE] Initializing BLE Device...");
    
    // Initialize BLE
    BLEDevice::init(BLE_DEVICE_NAME);
    Serial.println("[BLE] Device name set to: " + String(BLE_DEVICE_NAME));
    
    // Create BLE Server
    pServer = BLEDevice::createServer();
    server_callbacks.parent = this;
    pServer->setCallbacks(&server_callbacks);
    
    // Create BLE Service
    BLEService *pService = pServer->createService(SERVICE_UUID);
    
    // Create BLE Characteristic
    pCharacteristic = pService->createCharacteristic(
        CHAR_UUID,
        BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY
    );
    
    // Add descriptor for notifications
    pCharacteristic->addDescriptor(new BLE2902());
    pCharacteristic->setValue("ASV Silent Speech Recognition System");
    
    // Start service
    pService->start();
    
    Serial.println("[BLE] Service created with UUID: " + String(SERVICE_UUID));
    Serial.println("[BLE] Characteristic created with UUID: " + String(CHAR_UUID));
    
    // Configure advertising
    BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
    pAdvertising->addServiceUUID(SERVICE_UUID);
    pAdvertising->setScanResponse(true);
    pAdvertising->setMinPreferred(0x06);
    pAdvertising->setMinPreferred(0x12);
    
    Serial.println("[BLE] Initialization complete!");
}

void BLEModule::startAdvertising() {
    if (pServer) {
        BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
        pAdvertising->start();
        Serial.println("[BLE] Advertising started...");
        Serial.println("[BLE] Device name: " + String(BLE_DEVICE_NAME));
    }
}

void BLEModule::stopAdvertising() {
    if (pServer) {
        BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
        pAdvertising->stop();
        Serial.println("[BLE] Advertising stopped");
    }
}

bool BLEModule::isConnected() {
    return connected;
}

const char* BLEModule::getStatusString() {
    return connected ? "CONNECTED" : "ADVERTISING";
}
