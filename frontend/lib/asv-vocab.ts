/**
 * The vocabulary ASV can currently recognise, plus the tap-to-speak phrasebook.
 *
 * Two separate things live here on purpose:
 *
 *  - `VOCAB` mirrors the words the EMG model is trained on. A recognised token
 *    is short ("help"), but what gets spoken aloud should sound like a person
 *    ("I need help"), so each entry carries both.
 *  - `PHRASEBOOK` needs no hardware or model at all. It is the fallback that
 *    makes the app useful the moment it is installed — and the thing a user
 *    reaches for when the electrodes are off.
 */

export interface VocabWord {
  /** Token as the model emits it. */
  token: string
  /** What is shown on screen. */
  display: string
  /** What is spoken aloud — a full, natural phrase. */
  spoken: string
  glyph: string
  urgent?: boolean
}

export const VOCAB: VocabWord[] = [
  { token: "hello", display: "Hello", spoken: "Hello", glyph: "" },
  { token: "yes", display: "Yes", spoken: "Yes", glyph: "" },
  { token: "water", display: "Water", spoken: "Water", glyph: "" },
  { token: "rest", display: "Rest", spoken: "I need to rest", glyph: "" },
  { token: "help", display: "Help", spoken: "I need help", glyph: "", urgent: true },
]

const VOCAB_BY_TOKEN = new Map(VOCAB.map((w) => [w.token.toLowerCase(), w]))

/** Resolve a recognised token to its vocabulary entry, or synthesise one. */
export function resolveWord(token: string): VocabWord {
  const key = token.trim().toLowerCase()
  const known = VOCAB_BY_TOKEN.get(key)
  if (known) return known
  return {
    token: key,
    display: token.trim(),
    spoken: token.trim(),
    glyph: "",
  }
}

/** One thing the app has said out loud, from any source. */
export interface SpokenEntry {
  id: string
  text: string
  at: Date
  source: "emg" | "phrase" | "sentence"
  confidence?: number
}

export interface Phrase {
  text: string
  glyph: string
}

export interface PhraseCategory {
  id: string
  label: string
  glyph: string
  tone: "urgent" | "need" | "social" | "reply"
  phrases: Phrase[]
}

export const PHRASEBOOK: PhraseCategory[] = [
  {
    id: "urgent",
    label: "Urgent",
    glyph: "",
    tone: "urgent",
    phrases: [
      { text: "I need help right now", glyph: "" },
      { text: "Please call a doctor", glyph: "" },
      { text: "I am in pain", glyph: "" },
      { text: "I cannot breathe well", glyph: "" },
      { text: "Please call my family", glyph: "" },
      { text: "Something is wrong", glyph: "" },
    ],
  },
  {
    id: "needs",
    label: "Needs",
    glyph: "",
    tone: "need",
    phrases: [
      { text: "I would like some water", glyph: "" },
      { text: "I am hungry", glyph: "" },
      { text: "I need the bathroom", glyph: "" },
      { text: "I am cold", glyph: "" },
      { text: "I would like to rest", glyph: "" },
      { text: "Please help me sit up", glyph: "" },
    ],
  },
  {
    id: "social",
    label: "Everyday",
    glyph: "",
    tone: "social",
    phrases: [
      { text: "Hello, good to see you", glyph: "" },
      { text: "Thank you very much", glyph: "" },
      { text: "I am doing okay today", glyph: "" },
      { text: "Please give me a moment", glyph: "" },
      { text: "Could you say that again?", glyph: "" },
      { text: "Goodbye, take care", glyph: "" },
    ],
  },
  {
    id: "reply",
    label: "Replies",
    glyph: "",
    tone: "reply",
    phrases: [
      { text: "Yes", glyph: "" },
      { text: "No", glyph: "" },
      { text: "Maybe", glyph: "" },
      { text: "I don't know", glyph: "" },
      { text: "Please wait", glyph: "" },
      { text: "I understand", glyph: "" },
    ],
  },
]
