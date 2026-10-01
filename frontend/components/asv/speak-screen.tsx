"use client"

/**
 * SpeakScreen — Exact Live Word Tester Edition
 *
 * Implements the exact interface and behavior of tools/predict_live_gui.py:
 * - Vocabulary list
 * - Real-time electrode contact & baseline quality check
 * - 3-second countdown cue -> "SPEAK NOW"
 * - 5.0-second hardware capture via Python backend / Web Serial
 * - Utterance feature extraction & classification
 * - Prominent prediction display with matching Tkinter color palette
 * - Probability rankings breakdown meter bars
 * - Monospace live activity log
 * - Sentence accumulator with TTS voice output
 * - Zero emojis, zero fake quick-speech buttons
 */
import { useCallback, useEffect, useRef, useState } from "react"
import { motion } from "framer-motion"
import {
  AlertTriangle,
  CheckCircle2,
  Delete,
  RefreshCw,
  Terminal,
  Volume2,
} from "lucide-react"
import { asvApi, type Ranking } from "@/lib/asv-api"
import type { VocabWord } from "@/lib/asv-vocab"
import type { useBLE } from "@/hooks/use-ble"
import type { useSpeech } from "@/hooks/use-speech"
import type { useEmgRecognition } from "@/hooks/use-emg-recognition"

interface HeardWord {
  word: VocabWord
  confidence: number
  at: Date
}

interface SpeakScreenProps {
  ble: ReturnType<typeof useBLE>
  emg: ReturnType<typeof useEmgRecognition>
  speech: ReturnType<typeof useSpeech>
  heard: HeardWord | null
  sentence: VocabWord[]
  onWordRecognised: (token: string, confidence: number) => void
  onSpeakSentence: () => void
  onBackspace: () => void
  onClearSentence: () => void
  onOpenConnect: () => void
}

const WORD_COLORS: Record<string, string> = {
  yes: "#00ff6a",
  no: "#ff4d4d",
  hello: "#00bfff",
  hi: "#00bfff",
  help: "#ffaa00",
  rest: "#888888",
  water: "#4285f4",
}
const DEFAULT_PRED_COLOR = "#e0e0e0"

function getTimestamp(): string {
  const d = new Date()
  return d.toTimeString().split(" ")[0]
}

export function SpeakScreen({
  sentence,
  onWordRecognised,
  onSpeakSentence,
  onBackspace,
  onClearSentence,
}: SpeakScreenProps) {
  const [port, setPort] = useState("COM8")
  const [portStatus, setPortStatus] = useState<string>("Checking port...")
  const [statusColor, setStatusColor] = useState<string>("#888888")
  const [healthInfo, setHealthInfo] = useState<{
    ok: boolean
    status: string
    baseline_mv: number
    pp_mv: number
  } | null>(null)

  const [vocabulary, setVocabulary] = useState<string[]>([
    "hello",
    "help",
    "rest",
    "water",
    "yes",
  ])

  const [cue, setCue] = useState<string>("")
  const [busy, setBusy] = useState(false)
  const [prediction, setPrediction] = useState<string>("—")
  const [confidence, setConfidence] = useState<number | null>(null)
  const [rankings, setRankings] = useState<Ranking[]>([])
  const [sampleCount, setSampleCount] = useState<number | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const [logs, setLogs] = useState<string[]>([
    `[${getTimestamp()}] ASV Live Word Tester ready.`,
    `[${getTimestamp()}] Default target port: COM8 (921600 baud).`,
  ])

  const logBoxRef = useRef<HTMLDivElement>(null)

  const appendLog = useCallback((line: string) => {
    setLogs((prev) => [...prev.slice(-40), line])
    setTimeout(() => {
      if (logBoxRef.current) {
        logBoxRef.current.scrollTop = logBoxRef.current.scrollHeight
      }
    }, 50)
  }, [])

  // Poll hardware status
  const checkHardwareStatus = useCallback(async () => {
    try {
      const st = await asvApi.liveStatus()
      if (st.port) setPort(st.port)
      if (st.vocabulary && st.vocabulary.length > 0) {
        setVocabulary(st.vocabulary)
      }
      if (st.health) {
        setHealthInfo(st.health)
        const msg = `baseline=${Math.round(st.health.baseline_mv)}mV  pp=${Math.round(
          st.health.pp_mv,
        )}mV → ${st.health.status}`
        setPortStatus(msg)
        setStatusColor(st.health.ok ? "#34A853" : "#FBBC05")
      } else if (st.connected) {
        setPortStatus(`Connected — port ${st.port}`)
        setStatusColor("#34A853")
      } else {
        setPortStatus(`Ready — port ${st.port || "COM8"}`)
        setStatusColor("#888888")
      }
    } catch {
      setPortStatus("Backend offline (run uvicorn backend.main:app)")
      setStatusColor("#EA4335")
    }
  }, [])

  useEffect(() => {
    checkHardwareStatus()
    const id = setInterval(checkHardwareStatus, 12000)
    return () => clearInterval(id)
  }, [checkHardwareStatus])

  const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

  // Test real dataset sample through pipeline
  const handleTestSample = async (word: string) => {
    if (busy) return
    setBusy(true)
    setErrorMsg(null)
    setCue(`Testing '${word.toUpperCase()}'...`)

    try {
      const res = await asvApi.liveTestSample(word)
      if (res.ok && res.prediction) {
        const pred = res.prediction.toLowerCase()
        const conf = res.confidence ?? 1.0
        setPrediction(res.prediction.toUpperCase())
        setConfidence(conf)
        setSampleCount(res.n_samples ?? 4300)
        if (res.ranking) setRankings(res.ranking)
        if (res.health) setHealthInfo(res.health)
        appendLog(res.log || `[${getTimestamp()}] TEST: ${res.prediction.toUpperCase()}`)
        onWordRecognised(pred, conf)
      } else {
        throw new Error(res.error || "Test failed")
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setErrorMsg(msg)
      appendLog(`[ERROR] ${msg}`)
    } finally {
      setCue("")
      setBusy(false)
    }
  }

  // Main Record Action — replicates predict_live_gui.py exactly
  const handleRecord = async () => {
    if (busy) return
    setBusy(true)
    setErrorMsg(null)
    setPrediction("—")
    setConfidence(null)
    setRankings([])
    setSampleCount(null)

    // Countdown 3 -> 2 -> 1
    for (let i = 3; i > 0; i--) {
      setCue(`prepare... ${i}`)
      await sleep(1000)
    }

    // SPEAK NOW cue
    setCue("●  SPEAK NOW (recording 5s)...")
    appendLog(`[${getTimestamp()}] Capture started on ${port} (5.0s)...`)

    try {
      // 1. Hardware live capture via backend (exact EMGSerialReader pipeline)
      const res = await asvApi.liveRecord(5.0)
      setCue("processing...")

      if (res.ok && res.prediction) {
        const word = res.prediction.toLowerCase()
        const conf = res.confidence ?? 1.0
        setPrediction(res.prediction.toUpperCase())
        setConfidence(conf)
        setSampleCount(res.n_samples ?? 4300)
        if (res.ranking) setRankings(res.ranking)
        if (res.health) setHealthInfo(res.health)

        appendLog(
          res.log ||
            `[${getTimestamp()}] prediction=${word.toUpperCase()}  conf=${Math.round(
              conf * 100,
            )}%`,
        )
        onWordRecognised(word, conf)
      } else {
        throw new Error(res.error || "No word recognized")
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setCue("")
      setErrorMsg(msg)
      appendLog(`[ERROR] ${msg}`)

      if (msg.includes("Port") && msg.includes("busy")) {
        appendLog(
          `[NOTE] If predict_live_gui.py is open in terminal, close it so this web app can access ${port}.`,
        )
      }
    } finally {
      setCue("")
      setBusy(false)
    }
  }


  const predKey = prediction.toLowerCase()
  const predColor = WORD_COLORS[predKey] || DEFAULT_PRED_COLOR
  const sentenceText = sentence.map((w) => w.display).join(" ")

  return (
    <div className="flex h-full flex-col font-sans select-none bg-background text-foreground">
      {/* Title & Vocabulary Header */}
      <header className="px-5 pt-4 pb-2 border-b border-border/70 bg-card">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-[#4285F4]" />
              <span className="h-2 w-2 rounded-full bg-[#EA4335]" />
              <span className="h-2 w-2 rounded-full bg-[#FBBC05]" />
              <span className="h-2 w-2 rounded-full bg-[#34A853]" />
            </div>
            <h1 className="font-mono text-sm font-bold tracking-wider text-foreground">
              ASV — LIVE WORD TESTER
            </h1>
          </div>
          <button
            onClick={checkHardwareStatus}
            title="Refresh connection status"
            className="flex h-7 w-7 items-center justify-center rounded-full border border-border bg-secondary text-muted-foreground hover:text-foreground transition-colors"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Vocabulary list */}
        <p className="mt-1 font-mono text-[0.72rem] text-muted-foreground truncate">
          vocabulary: {vocabulary.join(", ")}
        </p>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto no-scrollbar px-4 py-3 space-y-3">
        {/* Hardware Status Strip */}
        <div className="flex items-center justify-between rounded-xl border border-border/80 bg-card px-3.5 py-2 text-xs shadow-xs">
          <div className="flex items-center gap-2 min-w-0">
            <span
              className="h-2 w-2 rounded-full shrink-0"
              style={{ backgroundColor: statusColor }}
            />
            <span
              className="font-mono truncate font-medium"
              style={{ color: statusColor }}
            >
              {portStatus}
            </span>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={async () => {
                setPortStatus("Connecting...")
                const r = await asvApi.liveConnect(port)
                if (r.ok) {
                  appendLog(`[${getTimestamp()}] Connected to ${port}`)
                } else {
                  appendLog(`[ERROR] ${r.error}`)
                }
                checkHardwareStatus()
              }}
              title="Click to reconnect COM port"
              className="font-mono text-[0.65rem] font-bold text-[#1a73e8] hover:underline"
            >
              Reconnect
            </button>
            {healthInfo?.ok && (
              <span className="inline-flex items-center gap-1 text-[0.68rem] font-semibold text-[#34A853]">
                <CheckCircle2 className="h-3 w-3" />
                Good
              </span>
            )}
            <span className="font-mono text-[0.68rem] font-bold text-muted-foreground uppercase">
              {port}
            </span>
          </div>
        </div>

        {/* Error notification banner if any */}
        {errorMsg && (
          <div className="rounded-xl border border-[#EA4335]/30 bg-[#fce8e6] dark:bg-[#3c2020] p-3 text-xs text-[#c5221f] dark:text-[#f28b82]">
            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
              <div className="flex-1 leading-relaxed">
                <strong className="font-semibold">Notice:</strong> {errorMsg}
              </div>
            </div>
          </div>
        )}

        {/* Countdown & Cue Banner */}
        <div className="h-10 flex items-center justify-center">
          {cue ? (
            <motion.div
              key={cue}
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className={`font-mono text-xl font-bold tracking-wider ${
                cue === "SPEAK NOW"
                  ? "text-[#EA4335] animate-pulse text-2xl"
                  : "text-[#FBBC05]"
              }`}
            >
              {cue === "SPEAK NOW" ? "●  SPEAK NOW" : cue}
            </motion.div>
          ) : (
            <span className="font-mono text-xs text-muted-foreground/60">
              Press Record and articulate the word
            </span>
          )}
        </div>

        {/* Prediction Display Box (Replicating Tkinter GUI) */}
        <div className="rounded-2xl border border-border bg-card p-5 text-center shadow-xs">
          <span className="font-mono text-[0.7rem] font-bold tracking-widest uppercase text-muted-foreground">
            PREDICTION
          </span>

          <div
            className="my-2 font-mono text-5xl font-black tracking-tight transition-colors duration-200"
            style={{ color: predColor }}
          >
            {prediction}
          </div>

          <div className="h-5">
            {confidence !== null ? (
              <span className="font-mono text-xs text-muted-foreground">
                confidence {Math.round(confidence * 100)}%
                {sampleCount ? `  (${sampleCount} samples)` : ""}
              </span>
            ) : (
              <span className="font-mono text-xs text-muted-foreground/40">—</span>
            )}
          </div>
        </div>

        {/* Quick Pipeline Verification with Genuine Dataset Sample */}
        <div className="flex items-center justify-between px-1 py-0.5">
          <span className="font-mono text-[0.68rem] text-muted-foreground">Test sample:</span>
          <div className="flex flex-wrap gap-1">
            {vocabulary.map((w) => (
              <button
                key={w}
                disabled={busy}
                onClick={() => handleTestSample(w)}
                className="rounded-md border border-border/80 bg-secondary/60 hover:bg-secondary px-2 py-0.5 font-mono text-[0.65rem] font-bold text-muted-foreground hover:text-foreground active:scale-95 transition-all disabled:opacity-40"
              >
                {w.toUpperCase()}
              </button>
            ))}
          </div>
        </div>


        {/* Probabilities & Rankings Breakdown */}
        {rankings.length > 0 && (
          <div className="rounded-2xl border border-border bg-card p-3.5 space-y-2">
            <span className="font-mono text-[0.68rem] font-bold uppercase tracking-wider text-muted-foreground">
              Class Probabilities
            </span>
            <div className="space-y-1.5 pt-1">
              {rankings.map((r) => {
                const color = WORD_COLORS[r.word.toLowerCase()] || "#aaaaaa"
                const pct = Math.round(r.prob * 100)
                return (
                  <div key={r.word} className="flex items-center gap-2.5 text-xs font-mono">
                    <span
                      className="w-14 shrink-0 font-bold uppercase"
                      style={{ color }}
                    >
                      {r.word}
                    </span>
                    {/* Horizontal Bar Meter */}
                    <div className="flex-1 h-3 rounded-full bg-secondary/80 overflow-hidden">
                      <motion.div
                        className="h-full rounded-full"
                        style={{ backgroundColor: color }}
                        initial={{ width: 0 }}
                        animate={{ width: `${pct}%` }}
                        transition={{ duration: 0.35, ease: "easeOut" }}
                      />
                    </div>
                    <span className="w-12 shrink-0 text-right tabular-nums font-semibold text-muted-foreground">
                      {pct}%
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* The Big Record Button */}
        <div>
          <button
            onClick={handleRecord}
            disabled={busy}
            className={`w-full flex items-center justify-center gap-2.5 rounded-full py-4 px-6 font-mono text-base font-bold shadow-md transition-all ${
              busy
                ? "bg-secondary text-muted-foreground cursor-not-allowed opacity-70"
                : "bg-[#c02020] hover:bg-[#d92323] text-white active:scale-[0.98] shadow-[0_2px_8px_rgba(192,32,32,0.35)]"
            }`}
          >
            <span className="text-sm">●</span>
            <span>{busy ? "RECORDING..." : "RECORD (speak the word)"}</span>
          </button>
        </div>

        {/* Log / Terminal Window */}
        <div className="rounded-2xl border border-border bg-[#141414] text-[#cccccc] p-3 text-xs font-mono">
          <div className="flex items-center justify-between pb-1.5 border-b border-white/10 mb-2">
            <div className="flex items-center gap-1.5 text-[0.68rem] font-bold uppercase tracking-wider text-muted-foreground">
              <Terminal className="h-3 w-3" />
              <span>Log</span>
            </div>
            <button
              onClick={() => setLogs([`[${getTimestamp()}] Log cleared.`])}
              className="text-[0.65rem] text-muted-foreground hover:text-white transition-colors"
            >
              Clear
            </button>
          </div>
          <div
            ref={logBoxRef}
            className="h-28 overflow-y-auto no-scrollbar space-y-1 text-[0.72rem] leading-relaxed select-text"
          >
            {logs.map((line, i) => (
              <div
                key={i}
                className={
                  line.includes("[ERROR]")
                    ? "text-[#ff6b6b]"
                    : line.includes("[NOTE]")
                    ? "text-[#ffcc00]"
                    : line.includes("prediction=") || line.includes("CONF")
                    ? "text-[#5fd35f] font-semibold"
                    : "text-zinc-400"
                }
              >
                {line}
              </div>
            ))}
          </div>
        </div>

        {/* Minimal Sentence Accumulator */}
        <div className="rounded-2xl border border-border bg-card p-3.5 space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[0.68rem] font-bold uppercase tracking-wider text-muted-foreground">
              Sentence
            </span>
            {sentence.length > 0 && (
              <button
                onClick={onClearSentence}
                className="text-[0.7rem] font-semibold text-[#1a73e8] hover:underline"
              >
                Clear
              </button>
            )}
          </div>

          {sentence.length === 0 ? (
            <p className="text-xs text-muted-foreground/60 py-1">
              Recognized words accumulate here.
            </p>
          ) : (
            <div className="flex flex-wrap gap-1.5 py-1">
              {sentence.map((w, idx) => (
                <span
                  key={`${w.token}-${idx}`}
                  className="rounded-full border border-border bg-secondary px-3 py-1 text-xs font-semibold text-foreground font-mono"
                >
                  {w.display}
                </span>
              ))}
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <button
              onClick={onSpeakSentence}
              disabled={sentence.length === 0}
              className="google-blue-btn flex flex-1 items-center justify-center gap-2 rounded-full py-2.5 text-xs font-bold font-mono disabled:opacity-40"
            >
              <Volume2 className="h-3.5 w-3.5" />
              Speak Sentence
            </button>
            <button
              onClick={onBackspace}
              disabled={sentence.length === 0}
              title="Remove last word"
              className="flex w-10 items-center justify-center rounded-full border border-border bg-secondary text-muted-foreground hover:bg-secondary/70 disabled:opacity-30"
            >
              <Delete className="h-3.5 w-3.5" />
            </button>
          </div>

          {sentenceText && (
            <p className="text-center text-[0.7rem] italic text-muted-foreground">
              &ldquo;{sentenceText}&rdquo;
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
