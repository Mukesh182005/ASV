from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from ml.inference.realtime_engine import RealtimeASVEngine
from ml.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ASV Inference Backend")

# Allow CORS for local Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "*"],  # Update in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize engine globally
engine = RealtimeASVEngine()

class PredictRequest(BaseModel):
    window_data: list  # 2D list: [samples][channels]
    
class PredictResponse(BaseModel):
    status: str
    prediction: str | None
    confidence: float
    smoothed_prediction: str | None

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/system/status")
def system_status():
    return {
        "status": "ok",
        "sampling_rate": settings.SAMPLING_RATE_HZ,
        "channels": settings.NUM_CHANNELS,
        "window_size": settings.WINDOW_SIZE
    }

@app.get("/model/status")
def model_status():
    if engine.is_loaded:
        return {
            "loaded": True,
            "status": "READY",
            "classes": engine.label_encoder.classes_.tolist() if engine.label_encoder else []
        }
    else:
        return {
            "loaded": False,
            "status": "MODEL_NOT_TRAINED"
        }

@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest):
    import numpy as np
    
    if not engine.is_loaded:
        return PredictResponse(
            status="MODEL_NOT_TRAINED",
            prediction=None,
            confidence=0.0,
            smoothed_prediction=None
        )
        
    try:
        window_np = np.array(request.window_data, dtype=float)
        result = engine.predict_window(window_np)
        
        return PredictResponse(
            status=result["status"],
            prediction=result.get("prediction"),
            confidence=result.get("confidence", 0.0),
            smoothed_prediction=result.get("smoothed_prediction")
        )
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
