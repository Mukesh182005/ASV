"use client"

/**
 * Live Detection — wired to the refined utterance-level model.
 *
 *  • Replay mode  — runs a REAL recorded utterance through the backend
 *                   (/demo/recording) and shows the model's real prediction.
 *  • Live mode    — streams the ESP32 over Web Serial, captures a 2 s window,
 *                   and classifies it via /predict_utterance.
 *
 * No Math.random anywhere: the waveform is the real EMG envelope and the word
 * is whatever the model returns.
 */
import { motion, AnimatePresence } from "framer-motion"
import { Activity, Settings, Volume2, Sparkles, Usb, RefreshCw, Check, X, Loader2 } from "lucide-react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useCallback, useEffect, useRef, useState } from "react"
import { asvApi, type ModelStatus, type RecordingRef, type Ranking } from "@/lib/asv-api"
import { useWebSerial } from "@/hooks/use-web-serial"

interface LiveDetectionProps {
  onNavigate: (screen: string) => void
}

interface Result {
  envelope: number[]
  prediction: string | null
  confidence: number
  ranking: Ranking[]
  trueLabel?: string
}

const BAR_COUNT = 44
const FALLBACK_BARS = Array.from({ length: BAR_COUNT }, () => 3)

/** Downsample an envelope to a fixed number of bars (max per bucket). */
function toBars(arr: number[], n = BAR_COUNT): number[] {
  if (!arr.length) return FALLBACK_BARS
  if (arr.length <= n) return arr
  const out: number[] = []
  const size = arr.length / n
  for (let i = 0; i < n; i++) {
    const a = Math.floor(i * size)
    const b = Math.max(a + 1, Math.floor((i + 1) * size))
    let m = 0
    for (let j = a; j < b && j < arr.length; j++) m = Math.max(m, arr[j])
    out.push(m)
  }
  return out
}

export function LiveDetection({ onNavigate }: LiveDetectionProps) {
  const [mode, setMode] = useState<"replay" | "live">("replay")
  const [model, setModel] = useState<ModelStatus | null>(null)
  const [recordings, setRecordings] = useState<RecordingRef[]>([])
  const [result, setResult] = useState<Result | null>(null)
  const [busy, setBusy] = useState(false)
  const [offline, setOffline] = useState(false)

  // live streaming buffer
  const [liveWave, setLiveWave] = useState<number[]>(FALLBACK_BARS)
  const liveBuf = useRef<number[]>([])

  const serial = useWebSerial({
    onSample: (mv) => {
      const b = liveBuf.current
      b.push(Math.abs(mv))
      if (b.length > 48) b.shift()
    },
  })

  // ---- initial load: model status + recordings ----
  useEffect(() => {
    const ac = new AbortController()
    ;(async () => {
      try {
        const [ms, rec] = await Promise.all([
          asvApi.modelStatus(ac.signal),
          asvApi.recordings(ac.signal),
        ])
        setModel(ms)
        setRecordings(rec.recordings)
        setOffline(false)
      } catch {
        setOffline(true)
      }
    })()
    return () => ac.abort()
  }, [])

  // ---- live waveform refresh ----
  useEffect(() => {
    if (mode !== "live" || serial.status !== "streaming") return
    const id = setInterval(() => {
      setLiveWave(liveBuf.current.length ? [...liveBuf.current] : FALLBACK_BARS)
    }, 80)
    return () => clearInterval(id)
  }, [mode, serial.status])

  const subject = recordings[0]?.subject ?? "S01"
  const words = Array.from(new Set(recordings.map((r) => r.label))).sort()

  // ---- replay: run a real recording of `word` through the model ----
  const classifyWord = useCallback(
    async (word: string) => {
      if (offline) return
      const reps = recordings.filter((r) => r.label === word)
      if (!reps.length) return
      const pick = reps[Math.floor(Math.random() * reps.length)]
      setBusy(true)
      try {
        const d = await asvApi.demoRecording(subject, word, pick.rep)
        setResult({
          envelope: d.envelope_mv,
          prediction: d.prediction,
          confidence: d.confidence,
          ranking: d.ranking,
          trueLabel: d.true_label,
        })
      } catch {
        setOffline(true)
      } finally {
        setBusy(false)
      }
    },
    [offline, recordings, subject],
  )

  const surprise = useCallback(() => {
    if (!recordings.length) return
    const r = recordings[Math.floor(Math.random() * recordings.length)]
    classifyWord(r.label)
  }, [recordings, classifyWord])

  // ---- live: capture 2 s and classify ----
  const captureAndClassify = useCallback(async () => {
    const samples = serial.captureUtterance(2)
    if (samples.length < 200) return
    setBusy(true)
    try {
      const p = await asvApi.predictUtterance(samples, model?.sampling_rate)
      const b = liveBuf.current
      setResult({
        envelope: b.length ? [...b] : FALLBACK_BARS,
        prediction: p.prediction,
        confidence: p.confidence,
        ranking: p.ranking,
      })
    } catch {
      setOffline(true)
    } finally {
      setBusy(false)
    }
  }, [serial, model])

  const bars = toBars(mode === "live" ? liveWave : result?.envelope ?? FALLBACK_BARS)
  const maxBar = Math.max(...bars, 1)
  const correct =
    result?.trueLabel != null && result.prediction != null
      ? result.trueLabel === result.prediction
      : null

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-background px-5 py-7">
      {/* Gemini aura background */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <motion.div
          className="absolute -right-24 -top-16 h-72 w-72 rounded-full blur-3xl"
          style={{ background: "radial-gradient(circle, rgba(66,133,244,0.28), transparent 70%)" }}
          animate={{ scale: [1, 1.15, 1], opacity: [0.6, 0.85, 0.6] }}
          transition={{ duration: 9, repeat: Infinity }}
        />
        <motion.div
          className="absolute -left-20 top-40 h-64 w-64 rounded-full blur-3xl"
          style={{ background: "radial-gradient(circle, rgba(155,114,203,0.26), transparent 70%)" }}
          animate={{ scale: [1.1, 1, 1.1], opacity: [0.5, 0.75, 0.5] }}
          transition={{ duration: 11, repeat: Infinity }}
        />
        <motion.div
          className="absolute -bottom-20 right-0 h-64 w-64 rounded-full blur-3xl"
          style={{ background: "radial-gradient(circle, rgba(217,101,112,0.22), transparent 70%)" }}
          animate={{ scale: [1, 1.12, 1], opacity: [0.45, 0.7, 0.45] }}
          transition={{ duration: 10, repeat: Infinity }}
        />
      </div>

      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -16 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative mb-5 flex items-start justify-between"
      >
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5" style={{ color: "var(--gemini-purple)" }} />
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">Live Detection</h1>
          </div>
          <div className="mt-1 flex items-center gap-2">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                offline ? "bg-destructive" : model?.loaded ? "bg-emerald-500" : "bg-amber-500"
              }`}
            />
            <p className="text-xs text-muted-foreground">
              {offline
                ? "Backend offline"
                : model?.loaded
                ? `Model ready · ${model.labels.length} words · ${model.sampling_rate} Hz`
                : "Loading model…"}
            </p>
          </div>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onNavigate("settings")}
          className="h-9 w-9 rounded-xl"
        >
          <Settings className="h-5 w-5 text-muted-foreground" />
        </Button>
      </motion.div>

      {/* Mode segmented control */}
      <div className="relative mb-5 grid grid-cols-2 gap-1 rounded-2xl border border-border/60 bg-card/70 p-1 backdrop-blur">
        {(["replay", "live"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`relative flex items-center justify-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition-colors ${
              mode === m ? "text-white" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {mode === m && (
              <motion.span
                layoutId="mode-pill"
                className="gemini-gradient absolute inset-0 rounded-xl"
                transition={{ type: "spring", stiffness: 400, damping: 32 }}
              />
            )}
            <span className="relative flex items-center gap-1.5">
              {m === "replay" ? <RefreshCw className="h-4 w-4" /> : <Usb className="h-4 w-4" />}
              {m === "replay" ? "Replay recording" : "Live device"}
            </span>
          </button>
        ))}
      </div>

      {/* Waveform card */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
        <Card className="relative mb-5 overflow-hidden border-border/60 bg-card/80 p-5 backdrop-blur">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              EMG envelope
            </p>
            <div className="flex items-center gap-1.5">
              <span
                className={`h-2 w-2 rounded-full ${
                  (mode === "live" && serial.status === "streaming") || busy
                    ? "animate-pulse"
                    : ""
                }`}
                style={{ background: "var(--gemini-blue)" }}
              />
              <span className="text-[11px] text-muted-foreground">
                {mode === "live" ? (serial.status === "streaming" ? "streaming" : "idle") : "recording"}
              </span>
            </div>
          </div>
          <div className="flex h-24 items-end justify-center gap-[3px]">
            {bars.map((h, i) => (
              <motion.div
                key={i}
                className="gemini-gradient w-1.5 rounded-full"
                initial={false}
                animate={{ height: `${Math.max(6, (h / maxBar) * 92)}%` }}
                transition={{ duration: 0.12 }}
                style={{ opacity: 0.55 + 0.45 * (h / maxBar) }}
              />
            ))}
          </div>
        </Card>
      </motion.div>

      {/* Detected word */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
        <Card className="gemini-glow relative mb-5 overflow-hidden border-transparent bg-card/90 p-7 text-center backdrop-blur">
          <div className="gemini-gradient-soft pointer-events-none absolute inset-0 opacity-60" />
          <div className="relative">
            <p className="mb-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Detected word
            </p>
            <AnimatePresence mode="wait">
              <motion.h2
                key={result?.prediction ?? "none"}
                initial={{ scale: 0.85, opacity: 0, y: 8 }}
                animate={{ scale: 1, opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="gemini-text mb-1 text-5xl font-bold uppercase tracking-wide"
              >
                {busy ? "…" : result?.prediction ?? "—"}
              </motion.h2>
            </AnimatePresence>

            {/* true vs predicted (replay only) */}
            {correct !== null && !busy && (
              <div className="mb-3 flex items-center justify-center gap-1.5 text-xs">
                <span
                  className={`flex items-center gap-1 rounded-full px-2 py-0.5 font-medium ${
                    correct
                      ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                      : "bg-destructive/15 text-destructive"
                  }`}
                >
                  {correct ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
                  spoken: {result?.trueLabel}
                </span>
              </div>
            )}

            {/* confidence */}
            <div className="mx-auto mt-2 max-w-xs">
              <div className="mb-1.5 flex justify-between text-xs">
                <span className="text-muted-foreground">Confidence</span>
                <span className="font-semibold text-foreground">
                  {result ? `${Math.round(result.confidence * 100)}%` : "—"}
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                <motion.div
                  className="gemini-gradient h-full rounded-full"
                  animate={{ width: `${result ? result.confidence * 100 : 0}%` }}
                  transition={{ duration: 0.4 }}
                />
              </div>
            </div>

            {/* ranking */}
            {result?.ranking && result.ranking.length > 1 && !busy && (
              <div className="mt-4 space-y-1.5">
                {result.ranking.slice(0, 3).map((r, i) => (
                  <div key={r.word} className="flex items-center gap-2 text-xs">
                    <span
                      className={`w-12 text-left font-medium ${
                        i === 0 ? "text-foreground" : "text-muted-foreground"
                      }`}
                    >
                      {r.word}
                    </span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                      <div
                        className={i === 0 ? "gemini-gradient h-full" : "h-full bg-muted-foreground/40"}
                        style={{ width: `${r.prob * 100}%` }}
                      />
                    </div>
                    <span className="w-9 text-right tabular-nums text-muted-foreground">
                      {Math.round(r.prob * 100)}%
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>
      </motion.div>

      {/* Controls */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
        {offline ? (
          <Card className="mb-5 border-destructive/30 bg-destructive/5 p-4 text-center text-sm text-muted-foreground">
            Backend not reachable at <code className="text-foreground">{asvApi.base}</code>.
            <br />
            Start it: <code className="text-foreground">uvicorn backend.main:app --port 8000</code>
          </Card>
        ) : mode === "replay" ? (
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Tap a word to classify a real recording
            </p>
            <div className="mb-3 flex flex-wrap gap-2">
              {words.map((w) => (
                <button
                  key={w}
                  disabled={busy}
                  onClick={() => classifyWord(w)}
                  className="gemini-ring rounded-full px-4 py-2 text-sm font-medium capitalize text-foreground transition-transform active:scale-95 disabled:opacity-50"
                >
                  {w}
                </button>
              ))}
            </div>
            <Button
              onClick={surprise}
              disabled={busy}
              className="gemini-gradient h-12 w-full rounded-2xl border-0 text-white shadow-lg"
            >
              {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
              Surprise me
            </Button>
          </div>
        ) : (
          <div>
            {!serial.supported && (
              <Card className="mb-3 border-amber-500/30 bg-amber-500/5 p-3 text-center text-xs text-muted-foreground">
                Web Serial needs a Chromium browser (Chrome/Edge) over localhost.
              </Card>
            )}
            {serial.status === "streaming" ? (
              <div className="grid grid-cols-2 gap-3">
                <Button
                  onClick={captureAndClassify}
                  disabled={busy}
                  className="gemini-gradient col-span-2 h-12 rounded-2xl border-0 text-white shadow-lg"
                >
                  {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Activity className="mr-2 h-4 w-4" />}
                  Capture 2 s &amp; classify
                </Button>
                <Button variant="secondary" onClick={serial.disconnect} className="col-span-2 h-11 rounded-2xl">
                  Disconnect
                </Button>
              </div>
            ) : (
              <Button
                onClick={serial.connect}
                disabled={!serial.supported || serial.status === "connecting"}
                className="gemini-gradient h-12 w-full rounded-2xl border-0 text-white shadow-lg disabled:opacity-50"
              >
                {serial.status === "connecting" ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Usb className="mr-2 h-4 w-4" />
                )}
                Connect ESP32
              </Button>
            )}
            {serial.error && (
              <p className="mt-2 text-center text-xs text-destructive">{serial.error}</p>
            )}
          </div>
        )}
      </motion.div>

      {/* Speak action */}
      <div className="relative mt-auto pt-5">
        <Button
          variant="outline"
          onClick={() => onNavigate("speech")}
          className="h-12 w-full rounded-2xl border-border/60"
        >
          <Volume2 className="mr-2 h-5 w-5" />
          Speak detected word
        </Button>
      </div>
    </div>
  )
}
