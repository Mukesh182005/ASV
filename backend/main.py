"""
ASV Inference Backend (refined, utterance-level)
================================================

Serves the refined model (refined_model/) that classifies a whole articulated
word from raw ADC counts.

Endpoints
  GET  /health
  GET  /model/status                      model + labels
  GET  /recordings                        list real recordings (for replay demo)
  GET  /demo/recording?subject&label&rep  real recording -> envelope + real prediction
  POST /predict_utterance                 {samples:[counts], fs?} -> prediction + ranking
"""
import sys
import logging
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.append(str(Path(__file__).resolve().parent.parent))

from ml.inference.utterance_engine import UtteranceEngine
from ml.refined.utterance_features import preprocess, FS_DEFAULT
from ml.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ASV Inference Backend", version="2.0")

# NOTE: wildcard origin cannot be combined with credentials in browsers, so we
# enumerate the dev origins explicitly and keep credentials off (no cookies used).
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = UtteranceEngine()
RAW_DIR = settings.RAW_DATA_DIR  # datasets/custom_silent_speech/raw


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
class PredictRequest(BaseModel):
    samples: list[float]          # raw ADC counts, channel_0
    fs: float | None = None


class Ranking(BaseModel):
    word: str
    prob: float


class PredictResponse(BaseModel):
    status: str
    prediction: str | None
    confidence: float
    ranking: list[Ranking]


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/model/status")
def model_status():
    return {
        "loaded": engine.is_loaded,
        "status": "READY" if engine.is_loaded else "MODEL_NOT_TRAINED",
        "model_dir": str(engine.model_dir.name),
        "labels": engine.labels,
        "sampling_rate": settings.SAMPLING_RATE_HZ,
        "channels": settings.NUM_CHANNELS,
    }


@app.get("/recordings")
def recordings():
    """List available real recordings for the replay demo."""
    items = []
    if RAW_DIR.exists():
        for csv in sorted(RAW_DIR.rglob("rep*.csv")):
            parts = csv.relative_to(RAW_DIR).parts
            if len(parts) < 3:
                continue
            subject, label = parts[0], parts[1]
            rep = "".join(ch for ch in csv.stem.split("_")[0] if ch.isdigit())
            items.append({"subject": subject, "label": label, "rep": rep, "file": csv.name})
    return {"count": len(items), "recordings": items}


def _find_recording(subject: str, label: str, rep: str) -> Path | None:
    d = RAW_DIR / subject / label
    if not d.exists():
        return None
    rep_num = "".join(ch for ch in rep if ch.isdigit()).zfill(3)
    for csv in d.glob(f"rep{rep_num}_*.csv"):
        return csv
    return None


@app.get("/demo/recording")
def demo_recording(
    subject: str = Query(...),
    label: str = Query(...),
    rep: str = Query(...),
    points: int = Query(140, ge=20, le=1000),
):
    """Load one real recording, return its envelope (downsampled, mV) plus the
    model's real prediction. This is a genuine recording through the real model —
    honest end-to-end without hardware."""
    csv = _find_recording(subject, label, rep)
    if csv is None:
        raise HTTPException(status_code=404, detail=f"recording not found: {subject}/{label}/{rep}")

    import pandas as pd
    df = pd.read_csv(csv)
    counts = df[df.columns[1]].to_numpy(dtype=float)

    _, env = preprocess(counts, fs=FS_DEFAULT)
    # downsample the envelope to `points` for plotting
    if len(env) > points:
        idx = np.linspace(0, len(env) - 1, points).astype(int)
        env_ds = env[idx]
    else:
        env_ds = env
    duration_s = float(len(counts) / FS_DEFAULT)

    result = engine.predict(counts, fs=FS_DEFAULT)
    return {
        "subject": subject, "label": label, "rep": rep,
        "true_label": label,
        "duration_s": round(duration_s, 3),
        "n_samples": int(len(counts)),
        "envelope_mv": [round(float(v), 3) for v in env_ds],
        **result,
    }


@app.post("/predict_utterance", response_model=PredictResponse)
def predict_utterance(req: PredictRequest):
    if not engine.is_loaded:
        return PredictResponse(status="MODEL_NOT_TRAINED", prediction=None,
                               confidence=0.0, ranking=[])
    try:
        fs = req.fs or float(settings.SAMPLING_RATE_HZ)
        result = engine.predict(np.asarray(req.samples, dtype=float), fs=fs)
        return PredictResponse(**result)
    except Exception as e:  # noqa: BLE001
        logger.error(f"predict_utterance error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
