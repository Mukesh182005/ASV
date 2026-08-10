"use client"

/**
 * SIMULATED — HARDCODED DEVICE STATE
 *
 * batteryLevel, signalStrength and isConnected are fixed literals. The device is
 * always 'connected' because isConnected is useState(true).
 *
 * To make real: drive these from the BLE status packet, which carries sample
 * rate, dropped-sample count and AD8232 lead-off flags.
 */
import { motion } from "framer-motion"
import { Bluetooth, Battery, Signal, Check, RefreshCw } from "lucide-react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useState } from "react"

interface DeviceConnectionProps {
  onContinue: () => void
}

export function DeviceConnection({ onContinue }: DeviceConnectionProps) {
  const [isConnected, setIsConnected] = useState(true)
  const [batteryLevel] = useState(87)
  const [signalStrength] = useState(92)

  return (
    <div className="flex min-h-screen flex-col bg-background px-6 py-12">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8"
      >
        <h1 className="text-2xl font-semibold text-foreground">Device</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          ASV EMG Neckband
        </p>
      </motion.div>

      {/* Device Illustration */}
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 0.1 }}
        className="relative mb-8 flex justify-center"
      >
        <div className="relative">
          {/* Neckband SVG Illustration */}
          <svg
            viewBox="0 0 200 120"
            className="h-40 w-64"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            {/* Neckband body */}
            <motion.path
              d="M30 80 Q30 40 60 30 Q100 20 140 30 Q170 40 170 80"
              stroke="currentColor"
              strokeWidth="8"
              strokeLinecap="round"
              className="text-foreground"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 1, delay: 0.3 }}
            />
            
            {/* Left sensor pod */}
            <motion.ellipse
              cx="35"
              cy="82"
              rx="12"
              ry="8"
              className="fill-primary"
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ duration: 0.3, delay: 0.8 }}
            />
            
            {/* Right sensor pod */}
            <motion.ellipse
              cx="165"
              cy="82"
              rx="12"
              ry="8"
              className="fill-primary"
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ duration: 0.3, delay: 0.9 }}
            />
            
            {/* Center LED indicator */}
            <motion.circle
              cx="100"
              cy="28"
              r="4"
              className="fill-primary"
              animate={{
                opacity: [1, 0.5, 1],
              }}
              transition={{ duration: 2, repeat: Infinity }}
            />
            
            {/* EMG sensor dots */}
            {[50, 75, 100, 125, 150].map((x, i) => (
              <motion.circle
                key={i}
                cx={x}
                cy={35 + Math.sin((x - 100) * 0.05) * 5}
                r="2"
                className="fill-muted-foreground/50"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 1 + i * 0.1 }}
              />
            ))}
          </svg>

          {/* Pulse effect */}
          {isConnected && (
            <motion.div
              className="absolute inset-0 flex items-center justify-center"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              <motion.div
                className="h-32 w-52 rounded-full border-2 border-primary/20"
                animate={{
                  scale: [1, 1.2],
                  opacity: [0.5, 0],
                }}
                transition={{ duration: 2, repeat: Infinity }}
              />
            </motion.div>
          )}
        </div>
      </motion.div>

      {/* Connection Status Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <Card className="mb-6 p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div
                className={`flex h-10 w-10 items-center justify-center rounded-xl ${
                  isConnected
                    ? "bg-primary/10 text-primary"
                    : "bg-muted text-muted-foreground"
                }`}
              >
                <Bluetooth className="h-5 w-5" />
              </div>
              <div>
                <p className="font-medium text-foreground">
                  {isConnected ? "Connected" : "Disconnected"}
                </p>
                <p className="text-sm text-muted-foreground">ASV-NB-001</p>
              </div>
            </div>
            {isConnected && (
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="flex h-8 w-8 items-center justify-center rounded-full bg-primary"
              >
                <Check className="h-4 w-4 text-primary-foreground" />
              </motion.div>
            )}
          </div>
        </Card>
      </motion.div>

      {/* Stats Grid */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="mb-8 grid grid-cols-2 gap-4"
      >
        {/* Battery Card */}
        <Card className="p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
              <Battery className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="text-2xl font-semibold text-foreground">
                {batteryLevel}%
              </p>
              <p className="text-xs text-muted-foreground">Battery</p>
            </div>
          </div>
          {/* Battery bar */}
          <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <motion.div
              className="h-full rounded-full bg-primary"
              initial={{ width: 0 }}
              animate={{ width: `${batteryLevel}%` }}
              transition={{ duration: 1, delay: 0.5 }}
            />
          </div>
        </Card>

        {/* Signal Card */}
        <Card className="p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
              <Signal className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="text-2xl font-semibold text-foreground">
                {signalStrength}%
              </p>
              <p className="text-xs text-muted-foreground">Signal</p>
            </div>
          </div>
          {/* Signal bars */}
          <div className="mt-3 flex items-end gap-1">
            {[1, 2, 3, 4, 5].map((level) => (
              <motion.div
                key={level}
                className={`w-2 rounded-sm ${
                  level <= Math.ceil(signalStrength / 20)
                    ? "bg-primary"
                    : "bg-muted"
                }`}
                initial={{ height: 0 }}
                animate={{ height: 4 + level * 3 }}
                transition={{ duration: 0.3, delay: 0.5 + level * 0.1 }}
              />
            ))}
          </div>
        </Card>
      </motion.div>

      {/* Device Info */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
      >
        <Card className="mb-8 p-4 shadow-sm">
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">Firmware</span>
              <span className="text-sm font-medium text-foreground">v2.4.1</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">Last Synced</span>
              <span className="text-sm font-medium text-foreground">Just now</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">Sensors</span>
              <span className="text-sm font-medium text-primary">8 Active</span>
            </div>
          </div>
        </Card>
      </motion.div>

      {/* Action Buttons */}
      <div className="mt-auto space-y-3">
        <Button
          onClick={onContinue}
          className="h-14 w-full rounded-2xl text-base font-medium shadow-lg shadow-primary/20"
        >
          Continue to Dashboard
        </Button>
        <Button
          variant="ghost"
          onClick={() => setIsConnected(!isConnected)}
          className="h-12 w-full gap-2 text-muted-foreground"
        >
          <RefreshCw className="h-4 w-4" />
          Reconnect Device
        </Button>
      </div>
    </div>
  )
}
