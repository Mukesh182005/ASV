"use client"

/**
 * SIMULATED — NOT REAL EMG
 *
 * The waveform is Math.random(). The detected words are picked at random from a
 * hardcoded array every few seconds. The confidence percentages are invented.
 *
 * To make real: subscribe to the BLE status characteristic
 * (6e6b0002-b5a3-f393-e0a9-e50e24dcca9e) for live status, and POST sample
 * windows to the backend /predict endpoint for classification.
 */
import { motion } from "framer-motion"
import { Activity, Mic, Volume2, Settings } from "lucide-react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useEffect, useState } from "react"

interface LiveDetectionProps {
  onNavigate: (screen: string) => void
}

const words = ["HELLO", "THANK YOU", "YES", "PLEASE", "HELP"]

export function LiveDetection({ onNavigate }: LiveDetectionProps) {
  const [isListening, setIsListening] = useState(true)
  const [isDemoMode, setIsDemoMode] = useState(true)
  const [detectedWord, setDetectedWord] = useState("--")
  const [confidence, setConfidence] = useState(0)
  const [waveformData, setWaveformData] = useState<number[]>(
    Array(30).fill(0)
  )

  // Simulate EMG waveform
  useEffect(() => {
    if (!isListening) return

    const interval = setInterval(() => {
      setWaveformData((prev) => {
        const newData = [...prev.slice(1)]
        newData.push(Math.random() * 40 + 10)
        return newData
      })
    }, 100)

    return () => clearInterval(interval)
  }, [isListening])

  // Simulate word detection
  useEffect(() => {
    if (!isListening || !isDemoMode) return

    const interval = setInterval(() => {
      const randomWord = words[Math.floor(Math.random() * words.length)]
      setDetectedWord(randomWord)
      setConfidence(Math.floor(Math.random() * 15) + 85)
    }, 4000)

    return () => clearInterval(interval)
  }, [isListening, isDemoMode])

  // Clear data when not in demo mode (since we have no real data yet)
  useEffect(() => {
    if (!isDemoMode) {
      setDetectedWord("--")
      setConfidence(0)
      setWaveformData(Array(30).fill(4))
    }
  }, [isDemoMode])

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-background px-6 py-8">
      {/* Enhanced Background */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <motion.div
          className="absolute -right-24 top-20 h-72 w-72 rounded-full bg-primary/6 blur-3xl"
          animate={{ scale: [1, 1.2, 1], opacity: [0.3, 0.5, 0.3] }}
          transition={{ duration: 8, repeat: Infinity }}
        />
        <motion.div
          className="absolute -left-20 bottom-32 h-64 w-64 rounded-full bg-primary/8 blur-3xl"
          animate={{ scale: [1.2, 1, 1.2] }}
          transition={{ duration: 10, repeat: Infinity }}
        />
        <div 
          className="absolute inset-0 opacity-[0.015]"
          style={{
            backgroundImage: `radial-gradient(circle at 1px 1px, currentColor 1px, transparent 0)`,
            backgroundSize: '28px 28px'
          }}
        />
      </div>
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-6 flex items-center justify-between"
      >
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Live Detection</h1>
          <div className="mt-1 flex items-center gap-2">
            <p className="text-sm text-muted-foreground">Real-time EMG analysis</p>
            {isDemoMode && (
              <span className="rounded-md bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-500">
                Demo Mode
              </span>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsDemoMode(!isDemoMode)}
            className="text-xs"
          >
            {isDemoMode ? "Live Mode" : "Demo Mode"}
          </Button>
          <Button
          variant="ghost"
          size="icon"
          onClick={() => onNavigate("settings")}
          className="h-10 w-10 rounded-xl"
        >
          <Settings className="h-5 w-5 text-muted-foreground" />
        </Button>
      </motion.div>

      {/* Status Indicator */}
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 0.1 }}
        className="mb-6"
      >
        <Card className="p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div
                className={`flex h-12 w-12 items-center justify-center rounded-2xl ${
                  isListening ? "bg-primary/10" : "bg-muted"
                }`}
              >
                <Activity
                  className={`h-6 w-6 ${
                    isListening ? "text-primary" : "text-muted-foreground"
                  }`}
                />
              </div>
              {isListening && (
                <motion.div
                  className="absolute -right-1 -top-1 h-3 w-3 rounded-full bg-primary"
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 1, repeat: Infinity }}
                />
              )}
            </div>
            <div className="flex-1">
              <p className="font-medium text-foreground">
                {isListening ? "Listening" : "Paused"}
              </p>
              <p className="text-sm text-muted-foreground">
                {isListening ? "Processing EMG signals" : "Tap to resume"}
              </p>
            </div>
            <Button
              variant={isListening ? "secondary" : "default"}
              size="sm"
              onClick={() => setIsListening(!isListening)}
              className="rounded-xl"
            >
              {isListening ? "Pause" : "Resume"}
            </Button>
          </div>
        </Card>
      </motion.div>

      {/* EMG Waveform Visualization */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="mb-6"
      >
        <Card className="overflow-hidden p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <p className="text-sm font-medium text-muted-foreground">EMG Signal</p>
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-primary animate-pulse" />
              <span className="text-xs text-muted-foreground">Live</span>
            </div>
          </div>
          
          {/* Waveform */}
          <div className="flex h-24 items-center justify-center gap-0.5">
            {waveformData.map((height, i) => (
              <motion.div
                key={i}
                className="w-1.5 rounded-full bg-primary/70"
                animate={{ height: isListening ? height : 4 }}
                transition={{ duration: 0.1 }}
              />
            ))}
          </div>
        </Card>
      </motion.div>

      {/* Detected Word Display */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="mb-6"
      >
        <Card className="p-8 text-center shadow-sm">
          <p className="mb-2 text-sm font-medium text-muted-foreground">
            Detected Word
          </p>
          <motion.h2
            key={detectedWord}
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="mb-4 text-4xl font-bold tracking-wide text-foreground"
          >
            {detectedWord}
          </motion.h2>
          
          {/* Confidence Bar */}
          <div className="mx-auto max-w-xs">
            <div className="mb-2 flex justify-between text-sm">
              <span className="text-muted-foreground">Confidence</span>
              <span className="font-semibold text-primary">{confidence}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <motion.div
                className="h-full rounded-full bg-primary"
                animate={{ width: `${confidence}%` }}
                transition={{ duration: 0.3 }}
              />
            </div>
          </div>
        </Card>
      </motion.div>

      {/* AI Processing Status */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="mb-8"
      >
        <Card className="p-4 shadow-sm">
          <div className="flex items-center gap-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-secondary">
              <Mic className="h-5 w-5 text-secondary-foreground" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-foreground">AI Model</span>
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${isDemoMode ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'}`}>
                  {isDemoMode ? 'Mock Active' : 'Not Trained'}
                </span>
              </div>
              <p className="text-sm text-muted-foreground">
                ASV Neural Engine
              </p>
            </div>
            <div className="text-right">
              <p className="text-lg font-semibold text-foreground">--</p>
              <p className="text-xs text-muted-foreground">Latency</p>
            </div>
          </div>
        </Card>
      </motion.div>

      {/* Quick Actions */}
      <div className="mt-auto grid grid-cols-2 gap-4">
        <Button
          variant="secondary"
          onClick={() => onNavigate("device")}
          className="h-14 rounded-2xl"
        >
          <Activity className="mr-2 h-5 w-5" />
          Device
        </Button>
        <Button
          onClick={() => onNavigate("speech")}
          className="h-14 rounded-2xl shadow-lg shadow-primary/20"
        >
          <Volume2 className="mr-2 h-5 w-5" />
          Speak
        </Button>
      </div>
    </div>
  )
}
