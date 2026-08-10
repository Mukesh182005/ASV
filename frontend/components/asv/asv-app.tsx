"use client"

import { useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { SplashScreen } from "./splash-screen"
import { LoginScreen } from "./login-screen"
import { BluetoothScan } from "./bluetooth-scan"
import { DeviceConnection } from "./device-connection"
import { DashboardScreen } from "./dashboard-screen"
import { LiveDetection } from "./live-detection"
import { SpeechOutput } from "./speech-output"
import { SettingsScreen } from "./settings-screen"
import { BottomNav } from "./bottom-nav"

type Screen = 
  | "splash" 
  | "login" 
  | "bluetooth" 
  | "device" 
  | "dashboard"
  | "detection" 
  | "speech" 
  | "settings"

export function ASVApp() {
  const [currentScreen, setCurrentScreen] = useState<Screen>("splash")
  const [showNav, setShowNav] = useState(false)

  const handleSplashComplete = () => {
    setCurrentScreen("login")
  }

  const handleLogin = () => {
    setCurrentScreen("bluetooth")
  }

  const handleDeviceConnected = () => {
    setCurrentScreen("device")
  }

  const handleDeviceContinue = () => {
    setCurrentScreen("dashboard")
  }

  const handleDashboardContinue = () => {
    setCurrentScreen("detection")
    setShowNav(true)
  }

  const handleNavigate = (screen: string) => {
    setCurrentScreen(screen as Screen)
  }

  const renderScreen = () => {
    switch (currentScreen) {
      case "splash":
        return <SplashScreen onComplete={handleSplashComplete} />
      case "login":
        return <LoginScreen onLogin={handleLogin} />
      case "bluetooth":
        return <BluetoothScan onDeviceConnected={handleDeviceConnected} />
      case "device":
        return <DeviceConnection onContinue={handleDeviceContinue} />
      case "dashboard":
        return <DashboardScreen onContinue={handleDashboardContinue} />
      case "detection":
        return <LiveDetection onNavigate={handleNavigate} />
      case "speech":
        return <SpeechOutput onBack={() => setCurrentScreen("detection")} />
      case "settings":
        return <SettingsScreen onBack={() => setCurrentScreen("detection")} />
      default:
        return <LiveDetection onNavigate={handleNavigate} />
    }
  }

  return (
    <div className="relative mx-auto min-h-screen max-w-md overflow-hidden bg-background">
      {/* Phone frame effect */}
      <div className="pointer-events-none absolute inset-0 z-50 rounded-[2.5rem] ring-1 ring-border/50" />
      
      <AnimatePresence mode="wait">
        <motion.div
          key={currentScreen}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -20 }}
          transition={{ duration: 0.2 }}
          className={showNav ? "pb-24" : ""}
        >
          {renderScreen()}
        </motion.div>
      </AnimatePresence>

      {showNav && (
        <BottomNav currentScreen={currentScreen} onNavigate={handleNavigate} />
      )}
    </div>
  )
}
