"use client"

/**
 * PhrasebookScreen — Google Material Design 3 Edition.
 *
 * Tap to speak out loud instantly without hardware.
 * Organized with Google colored categories and Google Keep style card tiles.
 */
import { useState } from "react"
import { motion } from "framer-motion"
import { BookOpen, Sparkles, Volume2 } from "lucide-react"
import { PHRASEBOOK } from "@/lib/asv-vocab"

interface PhrasebookScreenProps {
  onSpeak: (text: string) => void
  speakingText: string | null
  isSpeaking: boolean
}

const GOOGLE_TONE_STYLES: Record<
  string,
  {
    chipActive: string
    tile: string
    activeBorder: string
    accentDot: string
  }
> = {
  urgent: {
    chipActive: "bg-[#EA4335] text-white shadow-sm",
    tile: "border-[#f28b82]/40 bg-[#fce8e6]/60 dark:bg-[#3c2020]/50 dark:border-[#5c2424]",
    activeBorder: "border-[#EA4335] ring-2 ring-[#EA4335]/30",
    accentDot: "bg-[#EA4335]",
  },
  need: {
    chipActive: "bg-[#FBBC05] text-[#202124] shadow-sm font-bold",
    tile: "border-[#fbbc04]/40 bg-[#fef7e0]/70 dark:bg-[#383018]/50 dark:border-[#52441c]",
    activeBorder: "border-[#FBBC05] ring-2 ring-[#FBBC05]/30",
    accentDot: "bg-[#FBBC05]",
  },
  social: {
    chipActive: "bg-[#34A853] text-white shadow-sm",
    tile: "border-[#81c995]/40 bg-[#e6f4ea]/60 dark:bg-[#1b3323]/50 dark:border-[#264e32]",
    activeBorder: "border-[#34A853] ring-2 ring-[#34A853]/30",
    accentDot: "bg-[#34A853]",
  },
  reply: {
    chipActive: "bg-[#1a73e8] text-white shadow-sm",
    tile: "border-[#d2e3fc]/50 bg-[#e8f0fe]/60 dark:bg-[#1a2c42]/50 dark:border-[#283e58]",
    activeBorder: "border-[#1a73e8] ring-2 ring-[#1a73e8]/30",
    accentDot: "bg-[#1a73e8]",
  },
}

export function PhrasebookScreen({ onSpeak, speakingText, isSpeaking }: PhrasebookScreenProps) {
  const [activeId, setActiveId] = useState(PHRASEBOOK[0].id)
  const active = PHRASEBOOK.find((c) => c.id === activeId) ?? PHRASEBOOK[0]
  const currentTone = GOOGLE_TONE_STYLES[active.tone]

  return (
    <div className="flex h-full flex-col">
      <header className="px-4 pb-2 pt-4">
        <div className="flex items-center gap-2">
          <BookOpen className="h-5 w-5 text-[#1a73e8]" />
          <h1 className="font-display text-2xl font-bold tracking-tight text-foreground">
            Phrasebook
          </h1>
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Single-tap instant speech aloud. No hardware required.
        </p>
      </header>

      {/* Google Filter Chips */}
      <div className="flex gap-2 overflow-x-auto no-scrollbar px-4 py-2">
        {PHRASEBOOK.map((cat) => {
          const on = cat.id === active.id
          const tone = GOOGLE_TONE_STYLES[cat.tone]
          return (
            <button
              key={cat.id}
              onClick={() => setActiveId(cat.id)}
              className={`flex shrink-0 items-center gap-1.5 rounded-full px-4 py-2 text-xs font-semibold transition-all ${
                on
                  ? tone.chipActive
                  : "border border-border bg-card text-muted-foreground hover:bg-secondary/70 hover:text-foreground"
              }`}
            >
              <span>{cat.label}</span>
            </button>
          )
        })}
      </div>

      {/* Google Keep Style Phrase Cards Grid */}
      <div className="flex-1 overflow-y-auto no-scrollbar px-4 pb-4 pt-1">
        <div className="grid grid-cols-2 gap-2.5">
          {active.phrases.map((p) => {
            const nowSpeaking = isSpeaking && speakingText === p.text
            return (
              <motion.button
                key={p.text}
                whileTap={{ scale: 0.96 }}
                onClick={() => onSpeak(p.text)}
                className={`card-google flex min-h-[5.5rem] flex-col items-start justify-between p-3.5 text-left transition-all ${
                  currentTone.tile
                } ${nowSpeaking ? currentTone.activeBorder : ""}`}
              >
                <div className="flex w-full items-start justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">{active.label}</span>
                  {nowSpeaking && (
                    <span className="flex items-center gap-1 rounded-full bg-card px-2 py-0.5 text-[0.65rem] font-bold text-[#1a73e8] shadow-xs">
                      <Volume2 className="h-3 w-3 animate-pulse" />
                    </span>
                  )}
                </div>

                <span className="mt-2.5 text-sm font-semibold leading-snug text-foreground">
                  {p.text}
                </span>

                <div className="mt-1 flex items-center gap-1">
                  <span className={`h-1.5 w-1.5 rounded-full ${currentTone.accentDot}`} />
                  <span className="text-[0.65rem] font-medium text-muted-foreground capitalize">
                    {active.label}
                  </span>
                </div>
              </motion.button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
