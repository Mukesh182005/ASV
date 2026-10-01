"use client"

/**
 * useBLE — connect to the ASV ESP32 over Web Bluetooth.
 *
 * The firmware advertises "ASV-Device" with a custom 128-bit service and two
 * notify/write characteristics:
 *
 *   STATUS (notify, 20 Hz) — asv_ble.cpp::asvBleNotify
 *     [0]      0xA5 magic
 *     [1]      flags: bit0 streaming, bit1 adc_ok, bit2 lead_off_p, bit3 lead_off_n
 *     [2-3]    rate_hz x 10          (LE uint16)
 *     [4-7]    sample_count          (LE uint32)
 *     [8-9]    dropped               (LE uint16)
 *     [10-11]  baseline_counts       (LE int16)
 *     [12-13]  pp_counts             (LE uint16)  <- envelope we plot
 *     [14-15]  last_value            (LE int16)
 *
 *   WORD (notify, on recognition) — asv_ble.cpp::asvBleNotifyWord
 *     [0]      0xC3 magic
 *     [1]      confidence 0-100
 *     [2]      text length n (<= 16)
 *     [3..]    ASCII word
 *
 *   CMD (write) — single serial-menu letters ('s' start, 'x' stop, ...)
 *
 * Web Bluetooth requires Chrome/Edge on desktop or Android, over HTTPS or
 * localhost. Firefox, Safari and iOS have no support at all.
 */
import { useCallback, useEffect, useRef, useState } from "react"

const SERVICE_UUID     = "6e6b0001-b5a3-f393-e0a9-e50e24dcca9e"
const STATUS_CHAR_UUID = "6e6b0002-b5a3-f393-e0a9-e50e24dcca9e"
const CMD_CHAR_UUID    = "6e6b0003-b5a3-f393-e0a9-e50e24dcca9e"
const WORD_CHAR_UUID   = "6e6b0004-b5a3-f393-e0a9-e50e24dcca9e"
const CAPTURE_CHAR_UUID = "6e6b0005-b5a3-f393-e0a9-e50e24dcca9e"

const STATUS_MAGIC  = 0xa5
const WORD_MAGIC    = 0xc3
const CAPTURE_MAGIC = 0xc5

/** Generous: ~2400 samples in 24-sample chunks with an 8 ms gap is ~1 s. */
const CAPTURE_TIMEOUT_MS = 20000

/** ~6 s of history at the firmware's 20 Hz status cadence. */
export const ENVELOPE_POINTS = 120

export type BleStatus = "unsupported" | "idle" | "connecting" | "connected" | "error"

export interface AsvBlePacket {
  streaming: boolean
  adcOk: boolean
  leadOffP: boolean
  leadOffN: boolean
  rateHz: number
  sampleCount: number
  dropped: number
  baselineCounts: number
  ppCounts: number
  lastValue: number
}

export interface AsvWordEvent {
  word: string
  confidence: number
  at: Date
}

/** One utterance burst-transferred from the device. */
export interface AsvCapture {
  samples: number[]
  fs: number
}

interface PendingCapture {
  buf: Int16Array | null
  fs: number
  expected: number
  received: number
  resolve: ((c: AsvCapture) => void) | null
  reject: ((e: Error) => void) | null
  timer: ReturnType<typeof setTimeout> | null
}

type AnyBT = any // eslint-disable-line @typescript-eslint/no-explicit-any

export function useBLE(onWord?: (w: AsvWordEvent) => void) {
  const [supported, setSupported] = useState(false)
  const [status, setStatus] = useState<BleStatus>("idle")
  const [error, setError] = useState<string | null>(null)
  const [deviceName, setDeviceName] = useState<string | null>(null)
  const [packet, setPacket] = useState<AsvBlePacket | null>(null)
  const [envelope, setEnvelope] = useState<number[]>(() => Array(ENVELOPE_POINTS).fill(0))
  const [hasWordChannel, setHasWordChannel] = useState(false)
  const [hasCaptureChannel, setHasCaptureChannel] = useState(false)

  const deviceRef = useRef<AnyBT>(null)
  const cmdCharRef = useRef<AnyBT>(null)
  const onWordRef = useRef(onWord)
  onWordRef.current = onWord
  // Adaptive full-scale for the plot. EMG amplitude varies hugely between
  // electrode placements, so a fixed axis is either flat or clipped.
  const peakRef = useRef(1)

  const captureRef = useRef<PendingCapture>({
    buf: null,
    fs: 860,
    expected: 0,
    received: 0,
    resolve: null,
    reject: null,
    timer: null,
  })

  useEffect(() => {
    const ok = typeof navigator !== "undefined" && "bluetooth" in navigator
    setSupported(ok)
    setStatus(ok ? "idle" : "unsupported")
  }, [])

  const handleStatus = useCallback((dv: DataView) => {
    if (dv.byteLength < 16 || dv.getUint8(0) !== STATUS_MAGIC) return
    const flags = dv.getUint8(1)
    const pp = dv.getUint16(12, true)
    setPacket({
      streaming: !!(flags & 0x01),
      adcOk: !!(flags & 0x02),
      leadOffP: !!(flags & 0x04),
      leadOffN: !!(flags & 0x08),
      rateHz: dv.getUint16(2, true) / 10,
      sampleCount: dv.getUint32(4, true),
      dropped: dv.getUint16(8, true),
      baselineCounts: dv.getInt16(10, true),
      ppCounts: pp,
      lastValue: dv.getInt16(14, true),
    })
    peakRef.current = Math.max(pp, peakRef.current * 0.995, 1)
    setEnvelope((prev) => [...prev.slice(1), pp / peakRef.current])
  }, [])

  const handleWord = useCallback((dv: DataView) => {
    if (dv.byteLength < 3 || dv.getUint8(0) !== WORD_MAGIC) return
    const conf = dv.getUint8(1) / 100
    const len = Math.min(dv.getUint8(2), dv.byteLength - 3)
    if (len <= 0) return
    let word = ""
    for (let i = 0; i < len; i++) word += String.fromCharCode(dv.getUint8(3 + i))
    onWordRef.current?.({ word: word.trim(), confidence: conf, at: new Date() })
  }, [])

  /**
   * Reassemble one utterance from the burst of capture notifications.
   *
   * The device sends a header (how many samples, at what rate), then indexed
   * chunks, then a footer. Chunks carry their own start index rather than
   * relying on arrival order, so a reordered or repeated notification lands in
   * the right place instead of corrupting the recording.
   */
  const handleCapture = useCallback((dv: DataView) => {
    if (dv.byteLength < 2 || dv.getUint8(0) !== CAPTURE_MAGIC) return
    const pending = captureRef.current
    const type = dv.getUint8(1)

    if (type === 0x00 && dv.byteLength >= 6) {
      pending.expected = dv.getUint16(2, true)
      pending.fs = dv.getUint16(4, true) || 860
      pending.buf = new Int16Array(pending.expected)
      pending.received = 0
      return
    }

    if (type === 0x01 && pending.buf && dv.byteLength >= 6) {
      const start = dv.getUint16(2, true)
      const n = Math.floor((dv.byteLength - 4) / 2)
      for (let k = 0; k < n; k++) {
        const idx = start + k
        if (idx >= pending.buf.length) break
        pending.buf[idx] = dv.getInt16(4 + k * 2, true)
        pending.received++
      }
      return
    }

    if (type === 0x02) {
      const { buf, fs, resolve, reject, timer } = pending
      if (timer) clearTimeout(timer)
      pending.timer = null
      pending.resolve = null
      pending.reject = null
      if (!buf) {
        reject?.(new Error("Capture ended without any data."))
        return
      }
      resolve?.({ samples: Array.from(buf), fs })
      pending.buf = null
    }
  }, [])

  const connect = useCallback(async () => {
    if (!supported) return
    setError(null)
    setStatus("connecting")
    try {
      const device: AnyBT = await (navigator as AnyBT).bluetooth.requestDevice({
        filters: [{ name: "ASV-Device" }, { services: [SERVICE_UUID] }],
        optionalServices: [SERVICE_UUID],
      })
      deviceRef.current = device
      setDeviceName(device.name ?? "ASV-Device")

      device.addEventListener("gattserverdisconnected", () => {
        setStatus("idle")
        setPacket(null)
        setDeviceName(null)
        setHasWordChannel(false)
      })

      const server: AnyBT = await device.gatt.connect()
      const service = await server.getPrimaryService(SERVICE_UUID)

      const statusChar = await service.getCharacteristic(STATUS_CHAR_UUID)
      await statusChar.startNotifications()
      statusChar.addEventListener("characteristicvaluechanged", (ev: AnyBT) =>
        handleStatus(ev.target.value),
      )

      // Word and command channels are optional: older firmware still connects.
      try {
        const wordChar = await service.getCharacteristic(WORD_CHAR_UUID)
        await wordChar.startNotifications()
        wordChar.addEventListener("characteristicvaluechanged", (ev: AnyBT) =>
          handleWord(ev.target.value),
        )
        setHasWordChannel(true)
      } catch {
        setHasWordChannel(false)
      }

      try {
        const capChar = await service.getCharacteristic(CAPTURE_CHAR_UUID)
        await capChar.startNotifications()
        capChar.addEventListener("characteristicvaluechanged", (ev: AnyBT) =>
          handleCapture(ev.target.value),
        )
        setHasCaptureChannel(true)
      } catch {
        // Firmware predating the capture characteristic still connects fine —
        // the app just cannot recognise words over BLE on it.
        setHasCaptureChannel(false)
      }

      try {
        cmdCharRef.current = await service.getCharacteristic(CMD_CHAR_UUID)
      } catch {
        cmdCharRef.current = null
      }

      setStatus("connected")
    } catch (e: unknown) {
      if (e instanceof Error && e.name === "NotFoundError") {
        setStatus("idle") // user dismissed the chooser
      } else {
        setError(e instanceof Error ? e.message : String(e))
        setStatus("error")
      }
    }
  }, [supported, handleStatus, handleWord, handleCapture])

  const disconnect = useCallback(() => {
    try {
      deviceRef.current?.gatt?.disconnect()
    } catch {
      /* already gone */
    }
    deviceRef.current = null
    cmdCharRef.current = null
    // Fail any in-flight capture rather than leaving its promise hanging.
    const pending = captureRef.current
    if (pending.timer) clearTimeout(pending.timer)
    pending.reject?.(new Error("Band disconnected during capture."))
    pending.timer = null
    pending.resolve = null
    pending.reject = null
    pending.buf = null
    setHasCaptureChannel(false)
    setStatus(supported ? "idle" : "unsupported")
    setPacket(null)
    setDeviceName(null)
    setHasWordChannel(false)
  }, [supported])

  /** Send one firmware command letter, e.g. 's' to start streaming. */
  const sendCmd = useCallback(async (cmd: string) => {
    if (!cmdCharRef.current) return
    await cmdCharRef.current.writeValueWithoutResponse(new TextEncoder().encode(cmd))
  }, [])

  /**
   * Ask the device to record one utterance and send it back over BLE.
   *
   * This is the whole point of the capture channel: no USB anywhere. The device
   * records ASV_CAPTURE_SECONDS into its own RAM and bursts it back, so the
   * phone gets the raw samples and can hand them to the model.
   */
  const captureUtterance = useCallback((): Promise<AsvCapture> => {
    return new Promise<AsvCapture>((resolve, reject) => {
      if (!cmdCharRef.current) {
        reject(new Error("Not connected to the band."))
        return
      }
      const pending = captureRef.current
      if (pending.resolve) {
        reject(new Error("A capture is already running."))
        return
      }
      pending.buf = null
      pending.received = 0
      pending.expected = 0
      pending.resolve = resolve
      pending.reject = reject
      pending.timer = setTimeout(() => {
        pending.resolve = null
        pending.reject = null
        pending.timer = null
        reject(
          new Error(
            pending.received > 0
              ? `Capture incomplete — ${pending.received} of ${pending.expected} samples arrived.`
              : "No capture data arrived. Is the firmware new enough to support 'c'?",
          ),
        )
      }, CAPTURE_TIMEOUT_MS)

      cmdCharRef.current
        .writeValueWithoutResponse(new TextEncoder().encode("c"))
        .catch((e: unknown) => {
          if (pending.timer) clearTimeout(pending.timer)
          pending.timer = null
          pending.resolve = null
          pending.reject = null
          reject(e instanceof Error ? e : new Error(String(e)))
        })
    })
  }, [])

  useEffect(() => () => disconnect(), []) // eslint-disable-line react-hooks/exhaustive-deps

  const level = packet ? Math.min(1, packet.ppCounts / peakRef.current) : 0
  const electrodesOk = packet ? !packet.leadOffP && !packet.leadOffN : false

  return {
    supported,
    status,
    error,
    deviceName,
    packet,
    envelope,
    level,
    electrodesOk,
    hasWordChannel,
    hasCaptureChannel,
    connect,
    disconnect,
    sendCmd,
    captureUtterance,
  }
}
