"use client"

/**
 * HistoryScreen — Google Assistant History Edition.
 *
 * Everything spoken today, organized as Google Activity cards with
 * instant replay and categorized badges.
 */
import { motion } from "framer-motion"
import { Clock, RotateCcw, Trash2, Volume2 } from "lucide-react"
import type { SpokenEntry } from "@/lib/asv-vocab"

interface HistoryScreenProps {
  entries: SpokenEntry[]
  onReplay: (text: string) => void
  onClear: () => void
}

const GOOGLE_SOURCE_TAG: Record<
  SpokenEntry["source"],
  { label: string; badge: string; dot: string }
> = {
  emg: {
    label: "EMG Band",
    badge: "bg-[#e8f0fe] text-[#1967d2] dark:bg-[#1a2c42] dark:text-[#8ab4f8]",
    dot: "bg-[#1a73e8]",
  },
  phrase: {
    label: "Phrasebook",
    badge: "bg-[#e6f4ea] text-[#137333] dark:bg-[#1b3323] dark:text-[#81c995]",
    dot: "bg-[#34a853]",
  },
  sentence: {
    label: "Sentence",
    badge: "bg-[#fef7e0] text-[#b06000] dark:bg-[#383018] dark:text-[#fdd663]",
    dot: "bg-[#fbbc04]",
  },
}

export function HistoryScreen({ entries, onReplay, onClear }: HistoryScreenProps) {
  return (
    <div className="flex h-full flex-col">
      <header className="flex items-start justify-between px-4 pb-3 pt-4">
        <div>
          <div className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-[#1a73e8]" />
            <h1 className="font-display text-2xl font-bold tracking-tight text-foreground">
              Said Today
            </h1>
          </div>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {entries.length === 0
              ? "No phrases spoken yet this session."
              : `${entries.length} ${entries.length === 1 ? "phrase" : "phrases"} spoken aloud`}
          </p>
        </div>

        {entries.length > 0 && (
          <button
            onClick={onClear}
            aria-label="Clear history"
            className="flex h-9 w-9 items-center justify-center rounded-full border border-border bg-card text-muted-foreground transition-colors hover:bg-[#fce8e6] hover:text-[#c5221f] dark:hover:bg-[#3c2020] dark:hover:text-[#f28b82]"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        )}
      </header>

      <div className="flex-1 overflow-y-auto no-scrollbar px-4 pb-4">
        {entries.length === 0 ? (
          <div className="mt-16 flex flex-col items-center px-6 text-center">
            {/* Google Speech Bubble Badge */}
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-[#e8f0fe] dark:bg-[#1a2c42]">
              <Volume2 className="h-8 w-8 text-[#1a73e8]" />
            </div>
            <p className="text-base font-semibold text-foreground">Your history starts here</p>
            <p className="mt-1.5 max-w-xs text-xs leading-relaxed text-muted-foreground">
              Every phrase spoken by ASV is recorded here so you can replay it immediately without remouthing or retyping.
            </p>
          </div>
        ) : (
          <div className="space-y-2.5">
            {[...entries].reverse().map((e, i) => {
              const tag = GOOGLE_SOURCE_TAG[e.source]
              return (
                <motion.div
                  key={e.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: Math.min(i * 0.03, 0.2) }}
                  className="card-google flex items-center justify-between gap-3 p-3.5"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold leading-snug text-foreground">{e.text}</p>
                    <div className="mt-1.5 flex flex-wrap items-center gap-2">
                      <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[0.62rem] font-semibold ${tag.badge}`}>
                        <span className={`h-1.5 w-1.5 rounded-full ${tag.dot}`} />
                        {tag.label}
                      </span>

                      <span className="text-[0.68rem] tabular-nums text-muted-foreground">
                        {e.at.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
                      </span>

                      {e.confidence != null && (
                        <span className="text-[0.68rem] tabular-nums text-muted-foreground">
                          · {Math.round(e.confidence * 100)}% sure
                        </span>
                      )}
                    </div>
                  </div>

                  <button
                    onClick={() => onReplay(e.text)}
                    aria-label={`Replay "${e.text}"`}
                    title="Speak again"
                    className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#e8f0fe] text-[#1a73e8] shadow-xs transition-transform hover:scale-105 active:scale-95 dark:bg-[#1a2c42] dark:text-[#8ab4f8]"
                  >
                    <RotateCcw className="h-4 w-4" />
                  </button>
                </motion.div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
