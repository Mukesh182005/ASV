/**
 * ASV backend client.
 *
 * Talks to the FastAPI inference server (backend/main.py) that serves the
 * refined utterance-level model. Base URL is configurable via
 * NEXT_PUBLIC_ASV_API (default http://127.0.0.1:8000).
 */
const getApiUrl = () => {
  if (process.env.NEXT_PUBLIC_ASV_API) {
    return process.env.NEXT_PUBLIC_ASV_API.replace(/\/$/, "")
  }
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000`
  }
  return "http://127.0.0.1:8000"
}

export const ASV_API = getApiUrl()

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

  liveStatus: (signal?: AbortSignal) =>
    getJSON<{
      connected: boolean
      port: string
      available_ports: string[]
      vocabulary: string[]
      model_loaded: boolean
      model_error: string | null
      health: {
        ok: boolean
        status: string
        baseline_mv: number
        pp_mv: number
        peak_to_peak_mv?: number
      } | null
      busy: boolean
    }>("/live/status", signal),

  liveConnect: async (port?: string): Promise<{ ok: boolean; port: string; error?: string }> => {
    const res = await fetch(`${ASV_API}/live/connect`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ port }),
    })
    return res.json()
  },

  liveDisconnect: async (): Promise<{ ok: boolean }> => {
    const res = await fetch(`${ASV_API}/live/disconnect`, {
      method: "POST",
    })
    return res.json()
  },

  liveRecord: async (
    seconds = 5.0,
  ): Promise<{
    ok: boolean
    prediction?: string
    confidence?: number
    ranking?: Ranking[]
    health?: {
      ok: boolean
      status: string
      baseline_mv: number
      pp_mv: number
    }
    n_samples?: number
    log?: string
    error?: string
  }> => {
    try {
      const res = await fetch(`${ASV_API}/live/record`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ seconds }),
      })
      const data = await res.json().catch(() => null)
      if (!res.ok) {
        return { ok: false, error: data?.detail || `Server error (${res.status})` }
      }
      return data || { ok: false, error: "Empty response from server" }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      return { ok: false, error: `Network error: ${msg}` }
    }
  },

  liveTestSample: async (
    word = "help",
  ): Promise<{
    ok: boolean
    prediction?: string
    confidence?: number
    ranking?: Ranking[]
    health?: {
      ok: boolean
      status: string
      baseline_mv: number
      pp_mv: number
    }
    n_samples?: number
    source_file?: string
    log?: string
    error?: string
  }> => {
    try {
      const res = await fetch(`${ASV_API}/live/test_sample`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ word }),
      })
      const data = await res.json().catch(() => null)
      if (!res.ok) {
        return { ok: false, error: data?.detail || `Server error (${res.status})` }
      }
      return data || { ok: false, error: "Empty response from server" }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      return { ok: false, error: `Network error: ${msg}` }
    }
  },
}



