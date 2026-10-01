"use client"

/**
 * useSpeech — real audible output via the Web Speech API (speechSynthesis).
 *
 * This is the half of ASV that people other than the user actually experience:
 * a recognised word is spoken out loud so a conversation can happen without
 * anyone reading a screen.
 *
 * Browser realities worth knowing:
 *  - getVoices() is empty on first call in Chrome; it fills asynchronously and
 *    fires `voiceschanged`. We listen for both.
 *  - Most browsers refuse to speak until the page has had a user gesture, so
 *    `primed` tracks whether a gesture has happened and `prime()` is called
 *    from the first tap the app receives.
 *  - Chrome silently stops speaking after ~15s of continuous utterance; ASV
 *    speaks short phrases so this is not worked around here.
 */
import { useCallback, useEffect, useRef, useState } from "react"

export interface VoiceSettings {
  voiceURI: string | null
  rate: number
  pitch: number
  volume: number
  autoSpeak: boolean
}

export const DEFAULT_VOICE_SETTINGS: VoiceSettings = {
  voiceURI: null,
  rate: 0.95,
  pitch: 1,
  volume: 1,
  autoSpeak: true,
}

const STORAGE_KEY = "asv.voice"

function loadSettings(): VoiceSettings {
  if (typeof window === "undefined") return DEFAULT_VOICE_SETTINGS
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULT_VOICE_SETTINGS
    return { ...DEFAULT_VOICE_SETTINGS, ...JSON.parse(raw) }
  } catch {
    return DEFAULT_VOICE_SETTINGS
  }
}

export function useSpeech() {
  const [supported, setSupported] = useState(false)
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([])
  const [speaking, setSpeaking] = useState(false)
  const [spokenText, setSpokenText] = useState<string | null>(null)
  const [settings, setSettings] = useState<VoiceSettings>(DEFAULT_VOICE_SETTINGS)
  const [primed, setPrimed] = useState(false)

  const settingsRef = useRef(settings)
  settingsRef.current = settings

  useEffect(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return
    setSupported(true)
    setSettings(loadSettings())

    const refresh = () => setVoices(window.speechSynthesis.getVoices())
    refresh()
    window.speechSynthesis.addEventListener("voiceschanged", refresh)
    return () => {
      window.speechSynthesis.removeEventListener("voiceschanged", refresh)
      window.speechSynthesis.cancel()
    }
  }, [])

  // Chrome drops `onend` often enough that a stuck "speaking" banner is a real
  // failure mode — the listener sees the app claim it is still talking while it
  // is silent. The engine's own flag is the source of truth once we are started.
  useEffect(() => {
    if (!speaking) return
    const id = window.setInterval(() => {
      if (!window.speechSynthesis.speaking && !window.speechSynthesis.pending) {
        setSpeaking(false)
      }
    }, 250)
    return () => window.clearInterval(id)
  }, [speaking])

  const update = useCallback((patch: Partial<VoiceSettings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch }
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      } catch {
        /* private mode — settings just won't persist */
      }
      return next
    })
  }, [])

  /** Unlock audio on the first user gesture. Safe to call repeatedly. */
  const prime = useCallback(() => {
    if (primed || typeof window === "undefined" || !("speechSynthesis" in window)) return
    const u = new SpeechSynthesisUtterance("")
    u.volume = 0
    window.speechSynthesis.speak(u)
    setPrimed(true)
  }, [primed])

  const cancel = useCallback(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return
    window.speechSynthesis.cancel()
    setSpeaking(false)
  }, [])

  const speak = useCallback(
    (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || typeof window === "undefined" || !("speechSynthesis" in window)) return

      // Barge-in: a newer word always wins over one still being spoken, so the
      // output tracks what the person is saying right now.
      window.speechSynthesis.cancel()

      const s = settingsRef.current
      const u = new SpeechSynthesisUtterance(trimmed)
      const voice = window.speechSynthesis.getVoices().find((v) => v.voiceURI === s.voiceURI)
      if (voice) {
        u.voice = voice
        u.lang = voice.lang
      }
      u.rate = s.rate
      u.pitch = s.pitch
      u.volume = s.volume
      u.onstart = () => {
        setSpeaking(true)
        setSpokenText(trimmed)
      }
      u.onend = () => setSpeaking(false)
      u.onerror = () => setSpeaking(false)

      window.speechSynthesis.speak(u)
      setPrimed(true)
    },
    [],
  )

  const selectedVoice = voices.find((v) => v.voiceURI === settings.voiceURI) ?? null

  return {
    supported,
    voices,
    selectedVoice,
    speaking,
    spokenText,
    settings,
    update,
    speak,
    cancel,
    prime,
    primed,
  }
}
