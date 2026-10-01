"use client"

/**
 * ASVApp — application shell.
 *
 * Owns the three things every screen needs: the BLE link to the band, the
 * speech engine that makes words audible, and the sentence currently being
 * built. Screens below are presentational.
 *
 * Signal paths for live muscle recognition:
 *   USB serial (always available in Chrome/Edge):
 *     ESP32 --USB CSV--> browser Web Serial -> /predict_utterance -> word
 *   BLE capture (when ESP32 is paired and firmware supports it):
 *     browser --write 'c'--> ESP32 records 2.5s --BLE burst--> /predict_utterance -> word
 */
import { useCallback, useEffect, useState } from "react"
import { motion } from "framer-motion"
import { BookOpen, Clock, Mic, Settings } from "lucide-react"
import { ConnectScreen } from "./connect-screen"
import { SpeakScreen } from "./speak-screen"
import { PhrasebookScreen } from "./phrasebook-screen"
import { HistoryScreen } from "./history-screen"
import { SettingsScreen } from "./settings-screen"
import { useBLE, type AsvWordEvent } from "@/hooks/use-ble"
import { useSpeech } from "@/hooks/use-speech"
import { useEmgRecognition } from "@/hooks/use-emg-recognition"
import { resolveWord, type SpokenEntry, type VocabWord } from "@/lib/asv-vocab"

type Screen = "connect" | "speak" | "phrases" | "history" | "settings"

interface HeardWord {
  word: VocabWord
  confidence: number
  at: Date
}

const TABS = [
  { id: "speak", label: "Speak", Icon: Mic },
  { id: "phrases", label: "Phrases", Icon: BookOpen },
  { id: "history", label: "History", Icon: Clock },
  { id: "settings", label: "Voice", Icon: Settings },
] as const

export function ASVApp() {
  const [screen, setScreen] = useState<Screen>("connect")
  const [heard, setHeard] = useState<HeardWord | null>(null)
  const [sentence, setSentence] = useState<VocabWord[]>([])
  const [history, setHistory] = useState<SpokenEntry[]>([])
  const [largeText, setLargeText] = useState(false)
  const [darkMode, setDarkMode] = useState(false)

  const speech = useSpeech()

  const record = useCallback(
    (text: string, source: SpokenEntry["source"], confidence?: number) => {
      setHistory((prev) => [
        ...prev,
        { id: `${Date.now()}-${prev.length}`, text, at: new Date(), source, confidence },
      ])
    },
    [],
  )

  const say = useCallback(
    (text: string, source: SpokenEntry["source"], confidence?: number) => {
      speech.speak(text)
      record(text, source, confidence)
    },
    [speech, record],
  )

  /** A word arrived — from the band, or from a tap on the vocabulary grid. */
  const handleWord = useCallback(
    (token: string, confidence: number) => {
      const word = resolveWord(token)
      setHeard({ word, confidence, at: new Date() })
      setSentence((prev) => [...prev, word])
      if (speech.settings.autoSpeak) say(word.spoken, "emg", confidence)
    },
    [speech.settings.autoSpeak, say],
  )

  const handleBleWord = useCallback(
    (e: AsvWordEvent) => handleWord(e.word, e.confidence),
    [handleWord],
  )

  const ble = useBLE(handleBleWord)

  // Wire the recognition pipeline: real muscle signals → backend → word in the ring.
  // Prefers BLE capture when the firmware supports it; falls back to USB serial.
  const emg = useEmgRecognition({
    onWord: handleWord,
    bleCapture: ble.hasCaptureChannel ? ble.captureUtterance : undefined,
    bleReady: ble.hasCaptureChannel && ble.status === "connected",
  })


  const speakSentence = useCallback(() => {
    if (sentence.length === 0) return
    // Join the natural phrasings, not the display labels: "I need help" reads as
    // a sentence, "Help" reads as a button.
    const text = sentence.map((w) => w.spoken).join(", ")
    say(text, "sentence")
    setSentence([])
  }, [sentence, say])

  // Accessibility preferences drive real document state, so every screen and
  // any portal-rendered UI picks them up.
  useEffect(() => {
    document.documentElement.style.setProperty("--text-scale", largeText ? "1.15" : "1")
  }, [largeText])

  useEffect(() => {
    document.documentElement.classList.toggle("dark", darkMode)
  }, [darkMode])

  const showNav = screen !== "connect"

  return (
    <div
      onPointerDownCapture={speech.prime}
      className="relative mx-auto flex h-[100dvh] w-full max-w-md flex-col overflow-hidden bg-background sm:h-[92dvh] sm:max-h-[890px] sm:rounded-[28px] sm:border sm:border-border sm:shadow-[0_2px_6px_rgba(60,64,67,0.15),0_8px_24px_rgba(60,64,67,0.12)]"
    >
      {/* Google Top Bar */}
      {showNav && (
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-border/80 bg-card/90 px-4 backdrop-blur-md">
          <div className="flex items-center gap-2.5">
            {/* Google 4-Color Dots Emblem */}
            <div className="flex items-center gap-1 rounded-full bg-secondary/70 px-2 py-1">
              <span className="h-2 w-2 rounded-full bg-[#4285F4]" />
              <span className="h-2 w-2 rounded-full bg-[#EA4335]" />
              <span className="h-2 w-2 rounded-full bg-[#FBBC05]" />
              <span className="h-2 w-2 rounded-full bg-[#34A853]" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-1.5">
                <span className="font-display text-base font-bold tracking-tight text-foreground">
                  ASV
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setScreen("connect")}
              className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
                ble.status === "connected"
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                  : emg.serialStatus === "streaming"
                  ? "border-[#4285F4]/30 bg-[#e8f0fe] text-[#1a73e8] dark:bg-[#1a2c42] dark:text-[#8ab4f8]"
                  : "border-border bg-card text-muted-foreground hover:bg-secondary"
              }`}
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  ble.status === "connected"
                    ? "bg-emerald-500 animate-pulse"
                    : emg.serialStatus === "streaming"
                    ? "bg-[#4285F4] animate-pulse"
                    : "bg-muted-foreground/40"
                }`}
              />
              <span className="text-[0.7rem]">
                {ble.status === "connected"
                  ? "BLE Active"
                  : emg.serialStatus === "streaming"
                  ? "USB Active"
                  : "Offline"}
              </span>
            </button>
          </div>
        </header>
      )}

      <div className="relative flex-1 overflow-hidden">
        <motion.div
          key={screen}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.16 }}
          className="absolute inset-0"
        >
          {screen === "connect" && (
            <ConnectScreen
              ble={ble}
              onSkip={() => setScreen("speak")}
              onConnected={() => setScreen("speak")}
            />
          )}

          {screen === "speak" && (
            <SpeakScreen
              ble={ble}
              emg={emg}
              speech={speech}
              heard={heard}
              sentence={sentence}
              onWordRecognised={handleWord}
              onSpeakSentence={speakSentence}
              onBackspace={() => setSentence((p) => p.slice(0, -1))}
              onClearSentence={() => setSentence([])}
              onOpenConnect={() => setScreen("connect")}
            />
          )}

          {screen === "phrases" && (
            <PhrasebookScreen
              onSpeak={(text) => say(text, "phrase")}
              speakingText={speech.spokenText}
              isSpeaking={speech.speaking}
            />
          )}

          {screen === "history" && (
            <HistoryScreen
              entries={history}
              onReplay={(text) => speech.speak(text)}
              onClear={() => setHistory([])}
            />
          )}

          {screen === "settings" && (
            <SettingsScreen
              speech={speech}
              ble={ble}
              largeText={largeText}
              onLargeTextChange={setLargeText}
              darkMode={darkMode}
              onDarkModeChange={setDarkMode}
            />
          )}
        </motion.div>
      </div>

      {/* Google Assistant Speaking Pill */}
      {speech.speaking && (
        <motion.div
          aria-live="polite"
          initial={{ opacity: 0, y: 16, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 16, scale: 0.95 }}
          className={`pointer-events-none absolute inset-x-4 z-30 ${showNav ? "bottom-22" : "bottom-6"}`}
        >
          <div className="flex items-center gap-3.5 rounded-full border border-border/80 bg-card px-5 py-3 shadow-[0_4px_16px_rgba(60,64,67,0.25)] dark:bg-[#202124]">
            {/* Google 4-Color Waveform Dancing Bars */}
            <span className="flex items-end gap-1">
              {[
                { bg: "bg-[#4285F4]", delay: 0 },
                { bg: "bg-[#EA4335]", delay: 0.12 },
                { bg: "bg-[#FBBC05]", delay: 0.24 },
                { bg: "bg-[#34A853]", delay: 0.36 },
              ].map((dot, i) => (
                <motion.span
                  key={i}
                  className={`w-1 rounded-full ${dot.bg}`}
                  animate={{ height: [6, 18, 6] }}
                  transition={{ duration: 0.55, repeat: Infinity, delay: dot.delay }}
                />
              ))}
            </span>
            <div className="min-w-0 flex-1">
              <span className="block text-[0.68rem] font-medium uppercase tracking-wider text-muted-foreground">
                Speaking aloud
              </span>
              <span className="truncate text-sm font-semibold text-foreground">
                {speech.spokenText}
              </span>
            </div>
          </div>
        </motion.div>
      )}

      {/* Google Material 3 Navigation Bar */}
      {showNav && (
        <nav className="flex shrink-0 items-center justify-around border-t border-border bg-card px-2 pb-[max(0.6rem,env(safe-area-inset-bottom))] pt-2">
          {TABS.map(({ id, label, Icon }) => {
            const on = id === screen
            return (
              <button
                key={id}
                onClick={() => setScreen(id)}
                className="group relative flex flex-1 flex-col items-center gap-1 py-1 focus:outline-none"
              >
                <div
                  className={`flex h-8 w-16 items-center justify-center rounded-full transition-all duration-200 ${
                    on
                      ? "bg-[#c2e7ff] text-[#001d35] dark:bg-[#004a77] dark:text-[#c2e7ff]"
                      : "text-muted-foreground group-hover:bg-secondary/70 group-hover:text-foreground"
                  }`}
                >
                  <Icon className="h-5 w-5" strokeWidth={on ? 2.3 : 1.7} />
                </div>
                <span
                  className={`text-[0.72rem] tracking-wide transition-colors ${
                    on
                      ? "font-bold text-foreground"
                      : "font-medium text-muted-foreground group-hover:text-foreground"
                  }`}
                >
                  {label}
                </span>
              </button>
            )
          })}
        </nav>
      )}
    </div>
  )
}
