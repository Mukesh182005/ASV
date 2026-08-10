#ifndef BLE_TEST_H
#define BLE_TEST_H

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

/**
 * BLE (Bluetooth Low Energy) Module
 * Manages BLE initialization and advertising
 * 
 * Device Name: "ASV-Device"
 * Service UUID: 180A (Device Information)
 * Characteristic UUID: 2A29 (Manufacturer Name)
 */

#define BLE_DEVICE_NAME "ASV-Device"
#define SERVICE_UUID "180a"
#define CHAR_UUID "2a29"

class BLEModule {
public:
    /**
     * Initialize BLE device
     */
    void begin();
    
    /**
     * Start BLE advertising
     */
    void startAdvertising();
    
    /**
     * Stop BLE advertising
     */
    void stopAdvertising();
    
    /**
     * Check if BLE is connected
     * @return true if connected to a client
     */
    bool isConnected();
    
    /**
     * Get connection status string
     * @return Status message
     */
    const char* getStatusString();

    bool connected = false;
private:
    BLEServer* pServer = nullptr;
    BLECharacteristic* pCharacteristic = nullptr;
};

#endif // BLE_TEST_H
