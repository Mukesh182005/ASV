"use client"

import { motion } from "framer-motion"
import { Volume2, Play, Pause, RotateCcw, ChevronLeft, Copy } from "lucide-react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useState } from "react"

interface SpeechOutputProps {
  onBack: () => void
}

const conversationHistory = [
  { id: 1, text: "Hello, how are you?", time: "2:34 PM", isUser: true },
  { id: 2, text: "I would like some water please", time: "2:35 PM", isUser: true },
  { id: 3, text: "Thank you very much", time: "2:36 PM", isUser: true },
  { id: 4, text: "Yes, I understand", time: "2:38 PM", isUser: true },
]

export function SpeechOutput({ onBack }: SpeechOutputProps) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentText] = useState("Hello, how are you today?")
  const [playbackProgress, setPlaybackProgress] = useState(0)

  // Simulate playback
  const handlePlay = () => {
    setIsPlaying(true)
    setPlaybackProgress(0)
    
    const interval = setInterval(() => {
      setPlaybackProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval)
          setIsPlaying(false)
          return 0
        }
        return prev + 2
      })
    }, 50)
  }

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-background px-6 py-8">
      {/* Enhanced Background */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <motion.div
          className="absolute -left-32 top-40 h-80 w-80 rounded-full bg-primary/5 blur-3xl"
          animate={{ scale: [1, 1.3, 1], opacity: [0.2, 0.4, 0.2] }}
          transition={{ duration: 10, repeat: Infinity }}
        />
        <motion.div
          className="absolute -right-20 bottom-20 h-64 w-64 rounded-full bg-primary/8 blur-3xl"
          animate={{ scale: [1.2, 1, 1.2] }}
          transition={{ duration: 8, repeat: Infinity }}
        />
        <svg className="absolute left-0 right-0 top-1/3 h-32 opacity-[0.03]" viewBox="0 0 400 50" preserveAspectRatio="none">
          <motion.path
            d="M0 25 Q50 10 100 25 T200 25 T300 25 T400 25"
            stroke="currentColor"
            strokeWidth="1"
            fill="none"
            className="text-primary"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 3 }}
          />
        </svg>
      </div>
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-6 flex items-center gap-4"
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
          <h1 className="text-2xl font-semibold text-foreground">Speech Output</h1>
          <p className="mt-1 text-sm text-muted-foreground">Voice synthesis</p>
        </div>
      </motion.div>

      {/* Current Speech Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="mb-6"
      >
        <Card className="p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Volume2 className="h-5 w-5 text-primary" />
              <span className="text-sm font-medium text-muted-foreground">
                Generated Speech
              </span>
            </div>
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <Copy className="h-4 w-4 text-muted-foreground" />
            </Button>
          </div>

          {/* Speech Text */}
          <p className="mb-6 text-xl font-medium leading-relaxed text-foreground">
            {`"${currentText}"`}
          </p>

          {/* Sound Wave Animation */}
          <div className="mb-6 flex h-16 items-center justify-center gap-1 rounded-2xl bg-secondary/50 px-4">
            {Array(20)
              .fill(0)
              .map((_, i) => (
                <motion.div
                  key={i}
                  className="w-1 rounded-full bg-primary"
                  animate={{
                    height: isPlaying
                      ? [8, 24 + Math.sin(i * 0.5) * 16, 8]
                      : 8,
                  }}
                  transition={{
                    duration: 0.5,
                    repeat: isPlaying ? Infinity : 0,
                    delay: i * 0.05,
                  }}
                />
              ))}
          </div>

          {/* Progress Bar */}
          <div className="mb-4 h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <motion.div
              className="h-full rounded-full bg-primary"
              animate={{ width: `${playbackProgress}%` }}
              transition={{ duration: 0.1 }}
            />
          </div>

          {/* Playback Controls */}
          <div className="flex items-center justify-center gap-4">
            <Button
              variant="ghost"
              size="icon"
              className="h-12 w-12 rounded-full"
              onClick={() => setPlaybackProgress(0)}
            >
              <RotateCcw className="h-5 w-5 text-muted-foreground" />
            </Button>
            <Button
              size="icon"
              className="h-16 w-16 rounded-full shadow-lg shadow-primary/20"
              onClick={isPlaying ? () => setIsPlaying(false) : handlePlay}
            >
              {isPlaying ? (
                <Pause className="h-6 w-6" />
              ) : (
                <Play className="ml-1 h-6 w-6" />
              )}
            </Button>
            <div className="h-12 w-12" /> {/* Spacer for alignment */}
          </div>
        </Card>
      </motion.div>

      {/* Voice Settings */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="mb-6"
      >
        <Card className="p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-foreground">Voice Profile</p>
              <p className="text-sm text-muted-foreground">Natural Male - English</p>
            </div>
            <Button variant="secondary" size="sm" className="rounded-xl">
              Change
            </Button>
          </div>
        </Card>
      </motion.div>

      {/* Conversation History */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="flex-1"
      >
        <div className="mb-4 flex items-center justify-between">
          <p className="text-sm font-medium text-muted-foreground">
            Conversation History
          </p>
          <Button variant="ghost" size="sm" className="text-xs text-muted-foreground">
            Clear All
          </Button>
        </div>

        <div className="space-y-3">
          {conversationHistory.map((item, index) => (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4 + index * 0.1 }}
            >
              <Card className="p-4 shadow-sm transition-shadow hover:shadow-md">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <p className="text-foreground">{item.text}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{item.time}</p>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 shrink-0"
                    onClick={handlePlay}
                  >
                    <Play className="h-4 w-4 text-primary" />
                  </Button>
                </div>
              </Card>
            </motion.div>
          ))}
        </div>
      </motion.div>
    </div>
  )
}
