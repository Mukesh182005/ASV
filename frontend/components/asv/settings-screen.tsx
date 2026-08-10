"use client"

import { motion } from "framer-motion"
import {
  ChevronLeft,
  ChevronRight,
  Sliders,
  Globe,
  Volume2,
  Moon,
  Sun,
  Accessibility,
  Info,
  HelpCircle,
  LogOut,
} from "lucide-react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import { useState } from "react"

interface SettingsScreenProps {
  onBack: () => void
}

export function SettingsScreen({ onBack }: SettingsScreenProps) {
  const [isDarkMode, setIsDarkMode] = useState(false)
  const [sensitivity, setSensitivity] = useState([75])
  const [volume, setVolume] = useState([80])

  const BackgroundElements = () => (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      <motion.div
        className="absolute -right-32 -top-32 h-80 w-80 rounded-full bg-primary/5 blur-3xl"
        animate={{ scale: [1, 1.2, 1] }}
        transition={{ duration: 12, repeat: Infinity }}
      />
      <motion.div
        className="absolute -bottom-24 -left-24 h-64 w-64 rounded-full bg-primary/6 blur-3xl"
        animate={{ scale: [1.2, 1, 1.2], opacity: [0.3, 0.5, 0.3] }}
        transition={{ duration: 10, repeat: Infinity }}
      />
    </div>
  )

  const settingsGroups = [
    {
      title: "Device",
      items: [
        {
          icon: Sliders,
          label: "Calibration",
          description: "Calibrate EMG sensors",
          action: "navigate",
        },
        {
          icon: Volume2,
          label: "Output Volume",
          description: `${volume}%`,
          action: "slider",
          sliderValue: volume,
          onSliderChange: setVolume,
        },
      ],
    },
    {
      title: "Detection",
      items: [
        {
          icon: Globe,
          label: "Language",
          description: "English (US)",
          action: "navigate",
        },
        {
          icon: Sliders,
          label: "Sensitivity",
          description: `${sensitivity}%`,
          action: "slider",
          sliderValue: sensitivity,
          onSliderChange: setSensitivity,
        },
      ],
    },
    {
      title: "Appearance",
      items: [
        {
          icon: isDarkMode ? Moon : Sun,
          label: "Dark Mode",
          description: isDarkMode ? "On" : "Off",
          action: "toggle",
          toggleValue: isDarkMode,
          onToggle: setIsDarkMode,
        },
        {
          icon: Accessibility,
          label: "Accessibility",
          description: "Visual & audio settings",
          action: "navigate",
        },
      ],
    },
    {
      title: "Support",
      items: [
        {
          icon: HelpCircle,
          label: "Help Center",
          description: "FAQs and guides",
          action: "navigate",
        },
        {
          icon: Info,
          label: "About ASV",
          description: "Version 1.0.0",
          action: "navigate",
        },
      ],
    },
  ]

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-background px-6 py-8">
      <BackgroundElements />
      
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8 flex items-center gap-4"
      >
        <Button
          variant="ghost"
          size="icon"
          onClick={onBack}
          className="h-10 w-10 rounded-xl"
        >
          <ChevronLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Settings</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Customize your experience
          </p>
        </div>
      </motion.div>

      {/* Settings Groups */}
      <div className="space-y-6">
        {settingsGroups.map((group, groupIndex) => (
          <motion.div
            key={group.title}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 + groupIndex * 0.1 }}
          >
            <p className="mb-3 px-1 text-sm font-medium text-muted-foreground">
              {group.title}
            </p>
            <Card className="overflow-hidden shadow-sm">
              {group.items.map((item, itemIndex) => (
                <div
                  key={item.label}
                  className={`p-4 ${
                    itemIndex !== group.items.length - 1
                      ? "border-b border-border"
                      : ""
                  }`}
                >
                  <div className="flex items-center gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-secondary">
                      <item.icon className="h-5 w-5 text-secondary-foreground" />
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-foreground">{item.label}</p>
                      <p className="text-sm text-muted-foreground">
                        {item.description}
                      </p>
                    </div>
                    {item.action === "navigate" && (
                      <ChevronRight className="h-5 w-5 text-muted-foreground" />
                    )}
                    {item.action === "toggle" && (
                      <Switch
                        checked={item.toggleValue}
                        onCheckedChange={item.onToggle}
                      />
                    )}
                  </div>
                  {item.action === "slider" && (
                    <div className="mt-4 px-14">
                      <Slider
                        value={item.sliderValue}
                        onValueChange={item.onSliderChange}
                        max={100}
                        step={1}
                        className="w-full"
                      />
                    </div>
                  )}
                </div>
              ))}
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Sign Out Button */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="mt-8"
      >
        <Button
          variant="ghost"
          className="h-14 w-full gap-2 rounded-2xl text-destructive hover:bg-destructive/10 hover:text-destructive"
        >
          <LogOut className="h-5 w-5" />
          Sign Out
        </Button>
      </motion.div>

      {/* Footer */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.6 }}
        className="mt-auto pt-8 text-center"
      >
        <p className="text-sm text-muted-foreground">ASV – A Silent Voice</p>
        <p className="text-xs text-muted-foreground/60">Version 1.0.0</p>
      </motion.div>
    </div>
  )
}
