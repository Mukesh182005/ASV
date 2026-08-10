/**
 * ASV backend client.
 *
 * Talks to the FastAPI inference server (backend/main.py) that serves the
 * refined utterance-level model. Base URL is configurable via
 * NEXT_PUBLIC_ASV_API (default http://127.0.0.1:8000).
 */
export const ASV_API =
  process.env.NEXT_PUBLIC_ASV_API?.replace(/\/$/, "") || "http://127.0.0.1:8000"

export interface Ranking {
  word: string
  prob: number
}

export interface Prediction {
  status: string
  prediction: string | null
  confidence: number
  ranking: Ranking[]
}

export interface ModelStatus {
  loaded: boolean
  status: string
  model_dir: string
  labels: string[]
  sampling_rate: number
  channels: number
}

export interface RecordingRef {
  subject: string
  label: string
  rep: string
  file: string
}

export interface DemoRecording extends Prediction {
  subject: string
  label: string
  rep: string
  true_label: string
  duration_s: number
  n_samples: number
  envelope_mv: number[]
}

async function getJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${ASV_API}${path}`, { signal })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const asvApi = {
  base: ASV_API,

  health: (signal?: AbortSignal) => getJSON<{ status: string }>("/health", signal),

  modelStatus: (signal?: AbortSignal) => getJSON<ModelStatus>("/model/status", signal),

  recordings: (signal?: AbortSignal) =>
    getJSON<{ count: number; recordings: RecordingRef[] }>("/recordings", signal),

  demoRecording: (subject: string, label: string, rep: string, points = 140, signal?: AbortSignal) =>
    getJSON<DemoRecording>(
      `/demo/recording?subject=${encodeURIComponent(subject)}&label=${encodeURIComponent(
        label,
      )}&rep=${encodeURIComponent(rep)}&points=${points}`,
      signal,
    ),

  predictUtterance: async (samples: number[], fs?: number): Promise<Prediction> => {
    const res = await fetch(`${ASV_API}/predict_utterance`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ samples, fs }),
    })
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
    return res.json() as Promise<Prediction>
  },
}
