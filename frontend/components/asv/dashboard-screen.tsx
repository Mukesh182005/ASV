"use client"

import { motion } from "framer-motion"
import { 
  Activity, 
  Brain, 
  Volume2, 
  Watch, 
  Bluetooth,
  Battery,
  ChevronRight 
} from "lucide-react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

interface DashboardScreenProps {
  onContinue: () => void
}

const features = [
  {
    icon: Activity,
    title: "EMG Signal Detection",
    description: "Captures muscle signals from vocal cords",
    color: "bg-emerald-500/10 text-emerald-600",
  },
  {
    icon: Brain,
    title: "ML Prediction",
    description: "AI-powered speech recognition",
    color: "bg-blue-500/10 text-blue-600",
  },
  {
    icon: Volume2,
    title: "Real-time Speech",
    description: "Instant audio output generation",
    color: "bg-violet-500/10 text-violet-600",
  },
  {
    icon: Watch,
    title: "Smart Neckband",
    description: "Comfortable wearable device",
    color: "bg-orange-500/10 text-orange-600",
  },
]

export function DashboardScreen({ onContinue }: DashboardScreenProps) {
  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-background">
      {/* Animated Background */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        {/* Gradient mesh */}
        <motion.div
          className="absolute -right-32 -top-32 h-96 w-96 rounded-full bg-primary/6 blur-3xl"
          animate={{
            scale: [1, 1.2, 1],
            rotate: [0, 45, 0],
          }}
          transition={{ duration: 15, repeat: Infinity }}
        />
        <motion.div
          className="absolute -bottom-32 -left-32 h-80 w-80 rounded-full bg-primary/8 blur-3xl"
          animate={{
            scale: [1.2, 1, 1.2],
          }}
          transition={{ duration: 12, repeat: Infinity }}
        />
        
        {/* Subtle organic shapes */}
        <svg className="absolute right-0 top-40 h-64 w-64 opacity-[0.03]" viewBox="0 0 200 200">
          <motion.circle
            cx="100"
            cy="100"
            r="80"
            fill="none"
            stroke="currentColor"
            strokeWidth="0.5"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1, rotate: 360 }}
            transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
          />
        </svg>
      </div>

      {/* Content */}
      <div className="relative z-10 flex flex-1 flex-col px-6 py-8">
        {/* Header with Status */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 flex items-center justify-between"
        >
          <div>
            <h1 className="text-2xl font-semibold text-foreground">Dashboard</h1>
            <p className="mt-0.5 text-sm text-muted-foreground">ASV Project Overview</p>
          </div>
          
          {/* Device Status Badge */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2 }}
            className="flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1.5"
          >
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
            </span>
            <span className="text-xs font-medium text-primary">Connected</span>
          </motion.div>
        </motion.div>

        {/* Project Overview Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card className="relative mb-6 overflow-hidden p-5 shadow-sm">
            {/* Subtle gradient overlay */}
            <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-transparent" />
            
            <div className="relative">
              <div className="mb-3 flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
                  <span className="text-sm font-bold text-primary-foreground">ASV</span>
                </div>
                <span className="text-sm font-medium text-muted-foreground">
                  A Silent Voice
                </span>
              </div>
              
              <p className="text-balance text-sm leading-relaxed text-foreground/80">
                AI-powered silent speech recognition wearable for mute and speech-impaired 
                individuals. Transform muscle signals into natural speech.
              </p>
              
              {/* Mini waveform animation */}
              <div className="mt-4 flex items-center gap-1">
                {[...Array(20)].map((_, i) => (
                  <motion.div
                    key={i}
                    className="w-1 rounded-full bg-primary/40"
                    animate={{
                      height: [4, 12 + Math.sin(i * 0.5) * 8, 4],
                    }}
                    transition={{
                      duration: 1.2,
                      repeat: Infinity,
                      delay: i * 0.05,
                      ease: "easeInOut",
                    }}
                  />
                ))}
              </div>
            </div>
          </Card>
        </motion.div>

        {/* System Status */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="mb-6"
        >
          <Card className="p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
                  <Bluetooth className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <p className="font-medium text-foreground">ASV Neckband Pro</p>
                  <p className="text-xs text-muted-foreground">Ready to detect</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Battery className="h-3.5 w-3.5" />
                  <span>87%</span>
                </div>
                <ChevronRight className="h-4 w-4 text-muted-foreground/50" />
              </div>
            </div>
          </Card>
        </motion.div>

        {/* Feature Cards Grid */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="mb-6"
        >
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">
            KEY FEATURES
          </h2>
          <div className="grid grid-cols-2 gap-3">
            {features.map((feature, index) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 + index * 0.1 }}
              >
                <Card className="h-full p-4 shadow-sm transition-shadow hover:shadow-md">
                  <div className={`mb-3 flex h-10 w-10 items-center justify-center rounded-xl ${feature.color}`}>
                    <feature.icon className="h-5 w-5" />
                  </div>
                  <h3 className="text-sm font-medium text-foreground">
                    {feature.title}
                  </h3>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {feature.description}
                  </p>
                </Card>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* Quick Stats */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="mb-8"
        >
          <Card className="p-4 shadow-sm">
            <div className="flex items-center justify-around">
              <div className="text-center">
                <p className="text-2xl font-semibold text-foreground">--</p>
                <p className="text-xs text-muted-foreground">Accuracy</p>
              </div>
              <div className="h-8 w-px bg-border" />
              <div className="text-center">
                <p className="text-2xl font-semibold text-foreground">--</p>
                <p className="text-xs text-muted-foreground">Latency</p>
              </div>
              <div className="h-8 w-px bg-border" />
              <div className="text-center">
                <p className="text-2xl font-semibold text-foreground">--</p>
                <p className="text-xs text-muted-foreground">Sensors</p>
              </div>
            </div>
          </Card>
        </motion.div>

        {/* Start Button */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
          className="mt-auto"
        >
          <Button
            onClick={onContinue}
            className="h-14 w-full rounded-2xl text-base font-semibold shadow-lg shadow-primary/25"
          >
            Start Speaking
          </Button>
        </motion.div>
      </div>
    </div>
  )
}
