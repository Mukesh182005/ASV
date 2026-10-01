"use client"

/**
 * useEmgRecognition — turn a mouthed word into a recognised one.
 *
 * Nothing on the ESP32 classifies. The model lives off-device, so a prediction
 * always needs the raw samples to travel somewhere. There are two ways to move
 * them, and this hook prefers the first:
 *
 *   BLE (preferred, no cable):
 *     app --write 'c'--> device records 2.5 s into RAM --burst--> app --HTTP--> model
 *
 *   USB serial (fallback, development):
 *     device --CSV stream--> browser --HTTP--> model
 *
 * The BLE path is what makes the device usable with just a phone. It works
 * because one utterance is ~4.3 kB sent as a single burst — not a continuous
 * 860 SPS stream, which BLE genuinely cannot carry (see asv_ble.h).
 *
 * CAPTURE_SECONDS must match the training window (RECORD_SECONDS in the Python
 * tools, ASV_CAPTURE_SECONDS in the firmware). Changing one alone silently
 * shifts every feature the model sees.
 *
 * Requires the backend on port 8000. The BLE path needs firmware with the
 * capture characteristic; older firmware falls back to USB.
 */
import { useCallback, useEffect, useRef, useState } from "react"
import { useWebSerial } from "./use-web-serial"
import { asvApi, type Prediction } from "@/lib/asv-api"
import type { AsvCapture } from "./use-ble"

/** Must match RECORD_SECONDS in the Python tools and the training pipeline. */
export const CAPTURE_SECONDS = 5.0
const COUNTDOWN_SECONDS = 3
const FS = 860

/** Enough of the window must have arrived for the capture to be meaningful. */
const MIN_SAMPLE_FRACTION = 0.7

export type RecognitionPhase = "idle" | "countdown" | "recording" | "thinking"
export type RecognitionSource = "ble" | "usb"

interface UseEmgRecognitionOptions {
  /** Called with (token, confidence 0..1) when the backend returns a word. */
  onWord?: (token: string, confidence: number) => void
  /** Ask the band to record and burst one utterance back over BLE. */
  bleCapture?: () => Promise<AsvCapture>
  /** True when the connected firmware exposes the capture characteristic. */
  bleReady?: boolean
}

export function useEmgRecognition({
  onWord,
  bleCapture,
  bleReady = false,
}: UseEmgRecognitionOptions = {}) {
  const [phase, setPhase] = useState<RecognitionPhase>("idle")
  const [countdown, setCountdown] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [last, setLast] = useState<Prediction | null>(null)
  const [backendOk, setBackendOk] = useState<boolean | null>(null)
  const [level, setLevel] = useState(0)

  const onWordRef = useRef(onWord)
  onWordRef.current = onWord

  // Live level for a meter. This runs at the SAMPLE rate (860 Hz), so it must
  // never touch React state directly — doing so schedules ~860 renders a second,
  // which starves the serial read loop badly enough that almost no samples get
  // parsed ("Only 2 of ~2150 samples arrived"). Accumulate into a ref and flush
  // to state at a rate a screen can actually show.
  const levelRef = useRef(0)
  const handleSample = useCallback((mv: number) => {
    levelRef.current = levelRef.current * 0.92 + Math.min(Math.abs(mv) / 200, 1) * 0.08
  }, [])

  useEffect(() => {
    const id = setInterval(() => setLevel(levelRef.current), 50) // 20 Hz
    return () => clearInterval(id)
  }, [])

  const serial = useWebSerial({ onSample: handleSample, fs: FS })

  // Which transport a capture would use right now. BLE wins whenever the band
  // offers it, so the cable is never needed in normal use.
  const source: RecognitionSource = bleReady && bleCapture ? "ble" : "usb"

  // Probe the backend once so the UI can say "start the server" instead of
  // failing only at the moment the user tries to speak.
  useEffect(() => {
    let alive = true
    asvApi
      .health()
      .then(() => alive && setBackendOk(true))
      .catch(() => alive && setBackendOk(false))
    return () => {
      alive = false
    }
  }, [])

  const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

  const classify = useCallback(async (samples: number[], fs: number) => {
    const expected = CAPTURE_SECONDS * fs
    if (samples.length < expected * MIN_SAMPLE_FRACTION) {
      throw new Error(
        `Only ${samples.length} of ~${Math.round(expected)} samples arrived. ` +
          `Check the link and that the band is running.`,
      )
    }
    setPhase("thinking")
    const result = await asvApi.predictUtterance(samples, fs)
    setLast(result)
    setBackendOk(true)
    if (result.prediction) {
      onWordRef.current?.(result.prediction, result.confidence)
    } else {
      setError(result.status || "No word recognised.")
    }
  }, [])

  const listen = useCallback(async () => {
    if (phase !== "idle") return
    if (source === "usb" && serial.status !== "streaming") {
      setError("Connect the band — over Bluetooth, or over USB as a fallback.")
      return
    }
    setError(null)
    setLast(null)

    try {
      // Same ritual as collect_emg.py: a countdown, then articulate.
      setPhase("countdown")
      for (let i = COUNTDOWN_SECONDS; i > 0; i--) {
        setCountdown(i)
        await sleep(1000)
      }
      setCountdown(0)
      setPhase("recording")

      if (source === "ble" && bleCapture) {
        // The device does its own timing: 'c' starts the recording, and the
        // burst arrives once it has the full window. No local wait needed.
        const cap = await bleCapture()
        await classify(cap.samples, cap.fs || FS)
      } else {
        await sleep(CAPTURE_SECONDS * 1000)
        await classify(serial.captureUtterance(CAPTURE_SECONDS), FS)
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      // A network failure here almost always means the FastAPI server is down.
      if (msg.includes("Failed to fetch") || msg.includes("NetworkError")) {
        setBackendOk(false)
        setError("Backend not reachable. Start it: python -m uvicorn backend.main:app --port 8000")
      } else {
        setError(msg)
      }
    } finally {
      setPhase("idle")
      setCountdown(0)
    }
  }, [phase, source, serial, bleCapture, classify])

  return {
    source,
    supported: serial.supported,
    serialStatus: serial.status,
    serialError: serial.error,
    connect: serial.connect,
    disconnect: serial.disconnect,
    backendOk,
    phase,
    countdown,
    error,
    last,
    level,
    listen,
    busy: phase !== "idle",
    /** True when a capture can run right now, by either transport. */
    ready: source === "ble" || serial.status === "streaming",
  }
}
