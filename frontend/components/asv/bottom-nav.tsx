"use client"

import { motion } from "framer-motion"
import { Activity, Volume2, Bluetooth, Settings } from "lucide-react"

interface BottomNavProps {
  currentScreen: string
  onNavigate: (screen: string) => void
}

const navItems = [
  { id: "detection", icon: Activity, label: "Detect" },
  { id: "speech", icon: Volume2, label: "Speak" },
  { id: "device", icon: Bluetooth, label: "Device" },
  { id: "settings", icon: Settings, label: "Settings" },
]

export function BottomNav({ currentScreen, onNavigate }: BottomNavProps) {
  return (
    <motion.nav
      initial={{ y: 100 }}
      animate={{ y: 0 }}
      className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-card/80 backdrop-blur-xl"
    >
      <div className="mx-auto flex max-w-md items-center justify-around px-6 py-2 pb-6">
        {navItems.map((item) => {
          const isActive = currentScreen === item.id
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className="relative flex flex-col items-center gap-1 px-4 py-2"
            >
              {isActive && (
                <motion.div
                  layoutId="activeTab"
                  className="absolute inset-0 rounded-2xl bg-primary/10"
                  transition={{ type: "spring", stiffness: 500, damping: 30 }}
                />
              )}
              <item.icon
                className={`h-6 w-6 transition-colors ${
                  isActive ? "text-primary" : "text-muted-foreground"
                }`}
              />
              <span
                className={`text-xs font-medium transition-colors ${
                  isActive ? "text-primary" : "text-muted-foreground"
                }`}
              >
                {item.label}
              </span>
            </button>
          )
        })}
      </div>
    </motion.nav>
  )
}
