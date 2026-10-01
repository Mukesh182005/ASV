"use client"

/**
 * SettingsScreen — Google Material 3 Settings Edition.
 *
 * Customize speech synthesis, voice attributes, accessibility,
 * and hardware connectivity with Google Android settings design.
 */
import { Bluetooth, Check, Settings2, Sliders, Volume2 } from "lucide-react"
import type { useSpeech } from "@/hooks/use-speech"
import type { useBLE } from "@/hooks/use-ble"

interface SettingsScreenProps {
  speech: ReturnType<typeof useSpeech>
  ble: ReturnType<typeof useBLE>
  largeText: boolean
  onLargeTextChange: (v: boolean) => void
  darkMode: boolean
  onDarkModeChange: (v: boolean) => void
}

const PREVIEW = "Hello, I am using ASV Google Silent Speech to talk with you."

export function SettingsScreen({
  speech,
  ble,
  largeText,
  onLargeTextChange,
  darkMode,
  onDarkModeChange,
}: SettingsScreenProps) {
  const voices = speech.voices.filter((v) => v.lang.toLowerCase().startsWith("en"))
  const listed = voices.length > 0 ? voices : speech.voices

  return (
    <div className="flex h-full flex-col">
      <header className="px-4 pb-2 pt-4">
        <div className="flex items-center gap-2">
          <Settings2 className="h-5 w-5 text-[#1a73e8]" />
          <h1 className="font-display text-2xl font-bold tracking-tight text-foreground">
            Voice & Preferences
          </h1>
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground">
          How your spoken identity sounds and behaves.
        </p>
      </header>

      <div className="flex-1 space-y-4 overflow-y-auto no-scrollbar px-4 pb-5 pt-1">
        {!speech.supported && (
          <div className="rounded-2xl border border-destructive/30 bg-[#fce8e6] dark:bg-[#3c2020] p-4 text-xs leading-relaxed text-[#c5221f] dark:text-[#f28b82]">
            Speech synthesis is not available in this browser. Please use Chrome, Edge, or Safari for full audio speech output.
          </div>
        )}

        {/* Voice Selection Card */}
        <section className="card-google p-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-[#4285F4]" />
              <span className="text-[0.72rem] font-bold uppercase tracking-wider text-muted-foreground">
                Synthesized Voice
              </span>
            </div>

            <button
              onClick={() => speech.speak(PREVIEW)}
              className="google-blue-btn flex min-h-0 items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-semibold"
            >
              <Volume2 className="h-3.5 w-3.5" />
              Preview
            </button>
          </div>

          <div className="max-h-52 space-y-1 overflow-y-auto no-scrollbar">
            {listed.length === 0 ? (
              <p className="py-4 text-center text-xs text-muted-foreground">
                Loading available system voices…
              </p>
            ) : (
              listed.map((v) => {
                const on = v.voiceURI === speech.settings.voiceURI
                return (
                  <button
                    key={v.voiceURI}
                    onClick={() => speech.update({ voiceURI: v.voiceURI })}
                    className={`flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-left transition-colors ${
                      on
                        ? "bg-[#e8f0fe] text-[#1967d2] dark:bg-[#1a2c42] dark:text-[#8ab4f8]"
                        : "hover:bg-secondary/70 text-foreground"
                    }`}
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-xs font-semibold">{v.name}</span>
                      <span className="block text-[0.65rem] text-muted-foreground">{v.lang}</span>
                    </span>
                    {on && <Check className="h-4 w-4 shrink-0 text-[#1a73e8] dark:text-[#8ab4f8]" />}
                  </button>
                )
              })
            )}
          </div>
        </section>

        {/* Voice Controls Card */}
        <section className="card-google space-y-4 p-4">
          <div className="flex items-center gap-1.5">
            <Sliders className="h-3.5 w-3.5 text-[#34A853]" />
            <span className="text-[0.72rem] font-bold uppercase tracking-wider text-muted-foreground">
              Acoustic Tuning
            </span>
          </div>

          <GoogleSlider
            label="Speaking Rate"
            value={speech.settings.rate}
            min={0.5}
            max={1.6}
            step={0.05}
            format={(v) => `${v.toFixed(2)}×`}
            onChange={(rate) => speech.update({ rate })}
          />

          <GoogleSlider
            label="Pitch"
            value={speech.settings.pitch}
            min={0.5}
            max={1.8}
            step={0.05}
            format={(v) => v.toFixed(2)}
            onChange={(pitch) => speech.update({ pitch })}
          />

          <GoogleSlider
            label="Volume"
            value={speech.settings.volume}
            min={0.1}
            max={1}
            step={0.05}
            format={(v) => `${Math.round(v * 100)}%`}
            onChange={(volume) => speech.update({ volume })}
          />
        </section>

        {/* Behavior & Display Toggles */}
        <section className="card-google divide-y divide-border/80">
          <GoogleToggle
            label="Auto-speak recognized words"
            hint="Spoken aloud immediately as soon as a muscle gesture is classified."
            value={speech.settings.autoSpeak}
            onChange={(autoSpeak) => speech.update({ autoSpeak })}
          />
          <GoogleToggle
            label="Large readable text"
            hint="Scales the entire typography up for high-visibility from distance."
            value={largeText}
            onChange={onLargeTextChange}
          />
          <GoogleToggle
            label="Dark theme"
            hint="Google Material Dark palette optimized for night and low-light environments."
            value={darkMode}
            onChange={onDarkModeChange}
          />
        </section>

        {/* Hardware Band Card */}
        <section className="card-google p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-[#FBBC05]" />
              <span className="text-[0.72rem] font-bold uppercase tracking-wider text-muted-foreground">
                Hardware Link
              </span>
            </div>

            {ble.status === "connected" && (
              <span className="inline-flex items-center gap-1 rounded-full bg-[#e6f4ea] px-2.5 py-0.5 text-[0.65rem] font-semibold text-[#137333] dark:bg-[#1b3323] dark:text-[#81c995]">
                <span className="h-1.5 w-1.5 rounded-full bg-[#34A853] animate-pulse" />
                Connected
              </span>
            )}
          </div>

          <div className="mt-3 flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-secondary">
              <Bluetooth
                className={`h-5 w-5 ${
                  ble.status === "connected" ? "text-[#1a73e8]" : "text-muted-foreground"
                }`}
              />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-semibold text-foreground">
                {ble.status === "connected" ? ble.deviceName ?? "ASV Band" : "No device connected"}
              </p>
              {ble.packet && (
                <p className="text-[0.68rem] tabular-nums text-muted-foreground">
                  {ble.packet.rateHz.toFixed(0)} Hz · {ble.packet.sampleCount.toLocaleString()}{" "}
                  samples · {ble.packet.dropped} dropped
                </p>
              )}
            </div>
            {ble.status === "connected" && (
              <button
                onClick={ble.disconnect}
                className="min-h-0 rounded-full border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-secondary hover:text-foreground"
              >
                Disconnect
              </button>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}

function GoogleSlider({
  label,
  value,
  min,
  max,
  step,
  format,
  onChange,
}: {
  label: string
  value: number
  min: number
  max: number
  step: number
  format: (v: number) => string
  onChange: (v: number) => void
}) {
  return (
    <label className="block">
      <span className="mb-1.5 flex items-center justify-between">
        <span className="text-xs font-semibold text-foreground">{label}</span>
        <span className="rounded-full bg-secondary px-2 py-0.5 text-[0.68rem] font-semibold tabular-nums text-muted-foreground">
          {format(value)}
        </span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-2 w-full cursor-pointer appearance-none rounded-full bg-secondary accent-[#1a73e8]"
      />
    </label>
  )
}

function GoogleToggle({
  label,
  hint,
  value,
  onChange,
}: {
  label: string
  hint: string
  value: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <button
      role="switch"
      aria-checked={value}
      onClick={() => onChange(!value)}
      className="flex w-full items-center gap-3.5 p-3.5 text-left transition-colors hover:bg-secondary/40"
    >
      <span className="min-w-0 flex-1">
        <span className="block text-xs font-semibold text-foreground">{label}</span>
        <span className="mt-0.5 block text-[0.68rem] leading-relaxed text-muted-foreground">{hint}</span>
      </span>

      {/* Material 3 Switch */}
      <span
        className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out ${
          value ? "bg-[#1a73e8]" : "bg-[#dadce0] dark:bg-[#444746]"
        }`}
      >
        <span
          className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-md ring-0 transition duration-200 ease-in-out ${
            value ? "translate-x-5" : "translate-x-0"
          }`}
        />
      </span>
    </button>
  )
}
