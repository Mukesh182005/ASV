"use client"

/**
 * SIMULATED — NOT REAL BLUETOOTH
 *
 * Device discovery and connection are setTimeout animations over a hardcoded
 * device list. There is no navigator.bluetooth call anywhere in this file.
 *
 * To make real: replace mockDevices + the setTimeout chain with
 * navigator.bluetooth.requestDevice({ filters: [{ name: 'ASV-Device' }] }).
 * Firmware service UUID: 6e6b0001-b5a3-f393-e0a9-e50e24dcca9e
 */
import { motion } from "framer-motion"
import { Bluetooth, Battery, Signal, ChevronRight } from "lucide-react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useState, useEffect } from "react"

interface BluetoothScanProps {
  onDeviceConnected: () => void
}

interface Device {
  id: string
  name: string
  signal: number
  battery: number
  isASV: boolean
}

const mockDevices: Device[] = [
  { id: "asv-001", name: "ASV Neckband Pro", signal: 95, battery: 87, isASV: true },
  { id: "other-1", name: "AirPods Pro", signal: 78, battery: 65, isASV: false },
  { id: "other-2", name: "Galaxy Buds", signal: 45, battery: 30, isASV: false },
]

export function BluetoothScan({ onDeviceConnected }: BluetoothScanProps) {
  const [isScanning, setIsScanning] = useState(true)
  const [foundDevices, setFoundDevices] = useState<Device[]>([])
  const [connectingId, setConnectingId] = useState<string | null>(null)
  const [connectedId, setConnectedId] = useState<string | null>(null)

  useEffect(() => {
    if (isScanning) {
      const timers = mockDevices.map((device, index) =>
        setTimeout(() => {
          setFoundDevices((prev) => [...prev, device])
        }, 800 + index * 600)
      )

      const stopScan = setTimeout(() => {
        setIsScanning(false)
      }, 3500)

      return () => {
        timers.forEach(clearTimeout)
        clearTimeout(stopScan)
      }
    }
  }, [isScanning])

  const handleConnect = (device: Device) => {
    setConnectingId(device.id)
    setTimeout(() => {
      setConnectedId(device.id)
      setConnectingId(null)
      setTimeout(onDeviceConnected, 800)
    }, 1500)
  }

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-background">
      {/* Animated Background */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        {/* Gradient orbs */}
        <motion.div
          className="absolute -right-20 top-20 h-64 w-64 rounded-full bg-primary/8 blur-3xl"
          animate={{
            scale: [1, 1.3, 1],
            opacity: [0.3, 0.5, 0.3],
          }}
          transition={{ duration: 6, repeat: Infinity }}
        />
        <motion.div
          className="absolute -left-16 bottom-40 h-56 w-56 rounded-full bg-primary/6 blur-3xl"
          animate={{
            scale: [1.2, 1, 1.2],
            opacity: [0.4, 0.2, 0.4],
          }}
          transition={{ duration: 8, repeat: Infinity }}
        />
        
        {/* Grid pattern */}
        <div 
          className="absolute inset-0 opacity-[0.02]"
          style={{
            backgroundImage: `radial-gradient(circle at 1px 1px, currentColor 1px, transparent 0)`,
            backgroundSize: '24px 24px'
          }}
        />
      </div>

      {/* Content */}
      <div className="relative z-10 flex flex-1 flex-col px-6 py-12">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6"
        >
          <h1 className="text-2xl font-semibold text-foreground">Connect Device</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Find and connect your ASV neckband
          </p>
        </motion.div>

        {/* Neckband Illustration with Scanning Effect */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.1 }}
          className="relative mb-8 flex justify-center py-6"
        >
          <div className="relative">
            {/* Scanning rings */}
            {isScanning && (
              <>
                {[1, 2, 3].map((ring) => (
                  <motion.div
                    key={ring}
                    className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-primary/20"
                    initial={{ width: 60, height: 60, opacity: 0.6 }}
                    animate={{
                      width: [60, 200],
                      height: [60, 200],
                      opacity: [0.6, 0],
                    }}
                    transition={{
                      duration: 2,
                      repeat: Infinity,
                      delay: ring * 0.5,
                      ease: "easeOut",
                    }}
                  />
                ))}
              </>
            )}

            {/* Neckband near jawline illustration */}
            <svg
              viewBox="0 0 180 140"
              className="h-36 w-52"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              {/* Chin/jaw outline */}
              <motion.path
                d="M50 25 Q90 10 130 25 Q145 40 140 65 Q120 90 90 95 Q60 90 40 65 Q35 40 50 25"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                className="text-muted-foreground/30"
                fill="none"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 1.5 }}
              />
              
              {/* Neckband positioned under jaw */}
              <motion.path
                d="M35 75 Q35 100 55 110 Q90 125 125 110 Q145 100 145 75"
                stroke="currentColor"
                strokeWidth="6"
                strokeLinecap="round"
                className="text-foreground"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 1, delay: 0.5 }}
              />
              
              {/* Left sensor pod */}
              <motion.ellipse
                cx="38"
                cy="78"
                rx="10"
                ry="7"
                className="fill-primary"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ duration: 0.3, delay: 1.2 }}
              />
              
              {/* Right sensor pod */}
              <motion.ellipse
                cx="142"
                cy="78"
                rx="10"
                ry="7"
                className="fill-primary"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ duration: 0.3, delay: 1.3 }}
              />
              
              {/* EMG sensor points on band */}
              {[55, 75, 90, 105, 125].map((x, i) => (
                <motion.circle
                  key={i}
                  cx={x}
                  cy={115 - Math.abs(x - 90) * 0.15}
                  r="2.5"
                  className="fill-primary/60"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: [0.4, 1, 0.4] }}
                  transition={{
                    duration: 1.5,
                    repeat: Infinity,
                    delay: 1.5 + i * 0.15,
                  }}
                />
              ))}
              
              {/* Center indicator LED */}
              <motion.circle
                cx="90"
                cy="123"
                r="3"
                className="fill-primary"
                animate={{
                  opacity: isScanning ? [1, 0.3, 1] : 1,
                  scale: isScanning ? [1, 1.2, 1] : 1,
                }}
                transition={{ duration: 1, repeat: Infinity }}
              />
            </svg>

            {/* Bluetooth icon overlay */}
            <motion.div
              className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"
              animate={isScanning ? { scale: [1, 1.1, 1] } : {}}
              transition={{ duration: 1.5, repeat: Infinity }}
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                <Bluetooth className={`h-6 w-6 text-primary ${isScanning ? 'animate-pulse' : ''}`} />
              </div>
            </motion.div>
          </div>
        </motion.div>

        {/* Scanning Status */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="mb-6 text-center"
        >
          {isScanning ? (
            <div className="flex items-center justify-center gap-2">
              <motion.div
                className="h-2 w-2 rounded-full bg-primary"
                animate={{ scale: [1, 1.3, 1] }}
                transition={{ duration: 0.8, repeat: Infinity }}
              />
              <span className="text-sm font-medium text-muted-foreground">
                Searching for ASV devices...
              </span>
            </div>
          ) : (
            <span className="text-sm font-medium text-foreground">
              {foundDevices.length} devices found
            </span>
          )}
        </motion.div>

        {/* Nearby Devices */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="flex-1 space-y-3"
        >
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">
            NEARBY DEVICES
          </h2>
          
          {foundDevices.map((device, index) => (
            <motion.div
              key={device.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <Card 
                className={`p-4 shadow-sm transition-all ${
                  device.isASV 
                    ? 'border-primary/30 bg-primary/5' 
                    : ''
                } ${connectedId === device.id ? 'border-primary bg-primary/10' : ''}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div
                      className={`flex h-11 w-11 items-center justify-center rounded-xl ${
                        device.isASV
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted text-muted-foreground'
                      }`}
                    >
                      <Bluetooth className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="font-medium text-foreground">{device.name}</p>
                      <div className="mt-0.5 flex items-center gap-3 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Signal className="h-3 w-3" />
                          {device.signal}%
                        </span>
                        {device.isASV && (
                          <span className="flex items-center gap-1">
                            <Battery className="h-3 w-3" />
                            {device.battery}%
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  {device.isASV && (
                    <Button
                      size="sm"
                      onClick={() => handleConnect(device)}
                      disabled={connectingId !== null || connectedId !== null}
                      className={`h-9 rounded-xl px-4 ${
                        connectedId === device.id 
                          ? 'bg-primary/20 text-primary' 
                          : ''
                      }`}
                      variant={connectedId === device.id ? "ghost" : "default"}
                    >
                      {connectingId === device.id ? (
                        <motion.div
                          className="h-4 w-4 rounded-full border-2 border-primary-foreground border-t-transparent"
                          animate={{ rotate: 360 }}
                          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                        />
                      ) : connectedId === device.id ? (
                        "Connected"
                      ) : (
                        "Connect"
                      )}
                    </Button>
                  )}
                  
                  {!device.isASV && (
                    <ChevronRight className="h-5 w-5 text-muted-foreground/50" />
                  )}
                </div>
              </Card>
            </motion.div>
          ))}
        </motion.div>

        {/* Rescan Button */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          className="mt-6"
        >
          <Button
            variant="ghost"
            onClick={() => {
              setFoundDevices([])
              setIsScanning(true)
            }}
            disabled={isScanning || connectingId !== null}
            className="h-12 w-full gap-2 text-muted-foreground"
          >
            <Bluetooth className="h-4 w-4" />
            Scan Again
          </Button>
        </motion.div>
      </div>
    </div>
  )
}
