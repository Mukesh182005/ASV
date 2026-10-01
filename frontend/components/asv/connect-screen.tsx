"use client"

/**
 * ConnectScreen — Google Fast Pair Style.
 *
 * Fast, intuitive pairing with the ASV headset over Web Bluetooth.
 * Clean Google Material 3 card and animated multi-color beacon.
 */
import { motion } from "framer-motion"
import { Bluetooth, ChevronRight, ShieldAlert, Sparkles, Zap } from "lucide-react"
import type { useBLE } from "@/hooks/use-ble"

interface ConnectScreenProps {
  ble: ReturnType<typeof useBLE>
  onSkip: () => void
  onConnected: () => void
}

export function ConnectScreen({ ble, onSkip, onConnected }: ConnectScreenProps) {
  const connecting = ble.status === "connecting"
  const connected = ble.status === "connected"

  return (
    <div className="flex h-full w-full flex-col px-6 pb-6 pt-8">
      <div className="flex flex-1 flex-col items-center justify-center text-center">
        {/* Google 4-Color Fast Pair Beacon */}
        <div className="relative mb-8 flex h-40 w-40 items-center justify-center">
          {/* Animated 4-color glowing ripple rings */}
          <motion.div
            className="google-conic-glow absolute inset-0 rounded-full"
            animate={{ scale: [0.95, 1.15, 0.95], opacity: [0.35, 0.6, 0.35] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
          />
          <span className="animate-google-ripple absolute inset-0 rounded-full border border-[#4285F4]/40" />
          <span
            className="animate-google-ripple absolute inset-0 rounded-full border border-[#34A853]/40"
            style={{ animationDelay: "1.2s" }}
          />

          <div className="relative flex h-28 w-28 items-center justify-center rounded-full border border-border bg-card shadow-[0_4px_16px_rgba(60,64,67,0.15)]">
            <Bluetooth className="h-12 w-12 text-[#1a73e8]" strokeWidth={1.75} />
          </div>
        </div>

        {/* Google 4-Color Brand Indicator */}
        <div className="mb-3 flex items-center gap-1.5 rounded-full bg-secondary/80 px-3 py-1 text-xs font-semibold text-muted-foreground">
          <span className="h-2 w-2 rounded-full bg-[#4285F4]" />
          <span className="h-2 w-2 rounded-full bg-[#EA4335]" />
          <span className="h-2 w-2 rounded-full bg-[#FBBC05]" />
          <span className="h-2 w-2 rounded-full bg-[#34A853]" />
          <span className="ml-1 text-[0.68rem] tracking-wider uppercase">Fast Pair</span>
        </div>

        <h1 className="font-display text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
          Find your <span className="google-text">voice</span>
        </h1>
        <p className="mt-3 max-w-xs text-sm leading-relaxed text-muted-foreground">
          Connect your ASV armband. High-precision sEMG sensors read the muscle patterns of your silent speech in real time.
        </p>

        {!ble.supported && (
          <div className="mt-6 flex w-full items-start gap-3 rounded-2xl border border-[#ea4335]/30 bg-[#fce8e6] dark:bg-[#3c2020] p-4 text-left">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-[#c5221f] dark:text-[#f28b82]" />
            <p className="text-xs leading-relaxed text-[#c5221f] dark:text-[#f28b82]">
              This browser doesn&apos;t support Web Bluetooth. Please open ASV in{" "}
              <strong>Google Chrome or Microsoft Edge</strong>. The phrasebook and manual modes still work completely offline.
            </p>
          </div>
        )}

        {ble.error && (
          <p className="mt-4 rounded-xl bg-[#fce8e6] px-3 py-1.5 text-xs font-medium text-[#c5221f] dark:bg-[#3c2020] dark:text-[#f28b82]">
            {ble.error}
          </p>
        )}
      </div>

      <div className="space-y-3">
        <motion.button
          whileTap={{ scale: 0.98 }}
          onClick={connected ? onConnected : ble.connect}
          disabled={!ble.supported || connecting}
          className="google-blue-btn flex w-full items-center justify-center gap-2.5 rounded-full py-4 text-base font-semibold disabled:opacity-40"
        >
          {connecting ? (
            <>
              <Zap className="h-5 w-5 animate-pulse text-[#FBBC05]" />
              Searching for ASV Band…
            </>
          ) : connected ? (
            <>
              Start Speaking
              <ChevronRight className="h-5 w-5" />
            </>
          ) : (
            <>
              <Bluetooth className="h-5 w-5" />
              Pair ASV Band
            </>
          )}
        </motion.button>

        <button
          onClick={onSkip}
          className="w-full rounded-full border border-border bg-card py-3.5 text-sm font-semibold text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
        >
          Continue Without Band
        </button>

        <p className="px-2 pt-1 text-center text-xs leading-relaxed text-muted-foreground">
          Built-in speech synthesis and phrasebook work anytime without hardware.
        </p>
      </div>
    </div>
  )
}
