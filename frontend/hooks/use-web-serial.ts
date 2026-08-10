"use client"

/**
 * useWebSerial — read the ESP32 EMG stream directly from the browser.
 *
 * The firmware streams `timestamp_us,channel_0` CSV over USB at 921600 baud
 * after receiving the `s` command (and stops on `x`). Chromium browsers expose
 * this via the Web Serial API. This hook opens the port, streams samples for a
 * live waveform, and captures a fixed-length utterance window on demand so it
 * can be sent to the backend `/predict_utterance` endpoint.
 *
 * Web Serial requires a Chromium browser, HTTPS or localhost, and a user
 * gesture to pick the port. It is unavailable in Firefox/Safari — callers
 * should check `supported`.
 */
import { useCallback, useEffect, useRef, useState } from "react"

type SerialStatus = "unsupported" | "idle" | "connecting" | "streaming" | "error"

interface UseWebSerialOptions {
  baudRate?: number
  onSample?: (mv: number) => void // live sample in mV (DC-removed estimate)
  uvPerLsb?: number
  fs?: number
}

// Minimal Web Serial typing (not always present in TS lib).
type AnySerial = any // eslint-disable-line @typescript-eslint/no-explicit-any

export function useWebSerial({
  baudRate = 921600,
  onSample,
  uvPerLsb = 125.0,
  fs = 860,
}: UseWebSerialOptions = {}) {
  const [supported, setSupported] = useState(false)
  const [status, setStatus] = useState<SerialStatus>("idle")
  const [error, setError] = useState<string | null>(null)

  const portRef = useRef<AnySerial>(null)
  const readerRef = useRef<AnySerial>(null)
  const writerRef = useRef<AnySerial>(null)
  const keepReadingRef = useRef(false)
  const ringRef = useRef<number[]>([]) // recent raw counts
  const baselineRef = useRef<number>(13080) // ~1.635V mid-supply

  useEffect(() => {
    const ok = typeof navigator !== "undefined" && "serial" in navigator
    setSupported(ok)
    setStatus(ok ? "idle" : "unsupported")
  }, [])

  const send = useCallback(async (cmd: string) => {
    if (!writerRef.current) return
    await writerRef.current.write(new TextEncoder().encode(cmd))
  }, [])

  const readLoop = useCallback(async () => {
    const decoder = new TextDecoder()
    let buf = ""
    while (keepReadingRef.current && readerRef.current) {
      let value: Uint8Array | undefined, done: boolean
      try {
        ;({ value, done } = await readerRef.current.read())
      } catch {
        break
      }
      if (done) break
      if (!value) continue
      buf += decoder.decode(value, { stream: true })
      let nl: number
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim()
        buf = buf.slice(nl + 1)
        if (!line || line[0] === "#" || line[0] === "-" || line[0] === "[") continue
        const comma = line.indexOf(",")
        if (comma < 0) continue
        const ch0 = parseInt(line.slice(comma + 1), 10)
        if (Number.isNaN(ch0)) continue
        const ring = ringRef.current
        ring.push(ch0)
        if (ring.length > fs * 4) ring.shift() // keep ~4s
        // slow baseline tracker for a DC-removed live view
        baselineRef.current += (ch0 - baselineRef.current) * 0.0005
        onSample?.(((ch0 - baselineRef.current) * uvPerLsb) / 1000)
      }
    }
  }, [fs, onSample, uvPerLsb])

  const connect = useCallback(async () => {
    if (!supported) return
    setError(null)
    setStatus("connecting")
    try {
      const serial = (navigator as AnySerial).serial
      const port = await serial.requestPort()
      await port.open({ baudRate })
      portRef.current = port
      writerRef.current = port.writable.getWriter()
      readerRef.current = port.readable.getReader()
      keepReadingRef.current = true
      ringRef.current = []
      await send("s") // start firmware stream
      setStatus("streaming")
      readLoop()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setStatus("error")
    }
  }, [supported, baudRate, send, readLoop])

  const disconnect = useCallback(async () => {
    keepReadingRef.current = false
    try {
      await send("x")
    } catch {
      /* ignore */
    }
    try {
      await readerRef.current?.cancel()
      readerRef.current?.releaseLock()
    } catch {
      /* ignore */
    }
    try {
      writerRef.current?.releaseLock()
    } catch {
      /* ignore */
    }
    try {
      await portRef.current?.close()
    } catch {
      /* ignore */
    }
    readerRef.current = writerRef.current = portRef.current = null
    setStatus(supported ? "idle" : "unsupported")
  }, [send, supported])

  /** Capture the most recent `seconds` of samples as raw counts (for /predict_utterance). */
  const captureUtterance = useCallback(
    (seconds = 2): number[] => {
      const n = Math.round(seconds * fs)
      const ring = ringRef.current
      return ring.slice(Math.max(0, ring.length - n))
    },
    [fs],
  )

  useEffect(() => () => void disconnect(), []) // cleanup on unmount

  return { supported, status, error, connect, disconnect, captureUtterance }
}
