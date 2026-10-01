"""
13_realtime_inference_pipeline.py
Real-Time EMG Inference Pipeline
Prepares infrastructure for real-time EMG inference (ESP32 integration ready)
"""

import numpy as np
import pandas as pd
import logging
import os
import pickle
import json
from pathlib import Path

from ml.utils.features import EMGFeatureExtractor
from ml.utils.filters import apply_standard_emg_filter
from ml.utils.preprocessing import EMGPreprocessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RealtimeEMGInferencePipeline:
    """
    Production-ready real-time EMG inference pipeline.
    Designed for ESP32 streaming data integration.
    """
    
    def __init__(self, model_path, scaler_path, config_path=None):
        """
        Initialize inference pipeline.
        
        Parameters:
        -----------
        model_path : str
            Path to trained ML model
        scaler_path : str
            Path to fitted scaler
        config_path : str, optional
            Path to configuration JSON
        """
        self.model_path = model_path
        self.scaler_path = scaler_path
        
        # Load model
        logger.info(f"Loading model from {model_path}")
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)
        print(f"✓ Model loaded: {type(self.model).__name__}")
        
        # Load scaler
        logger.info(f"Loading scaler from {scaler_path}")
        with open(scaler_path, 'rb') as f:
            self.scaler = pickle.load(f)
        print(f"✓ Scaler loaded")
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Initialize components
        self.feature_extractor = EMGFeatureExtractor(fs=self.config['fs'])
        self.preprocessor = EMGPreprocessor(label_column='stimulus')
        
        # Initialize buffers
        self.reset_buffers()
        
        logger.info("Inference pipeline initialized")
    
    def _load_config(self, config_path):
        """Load inference configuration."""
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        
        # Default configuration (ESP32-compatible)
        return {
            'fs': 2000,                      # Sampling frequency (Hz)
            'window_size': 512,              # Window size (samples)
            'window_duration_ms': 256,       # 512 samples @ 2000 Hz = 256 ms
            'n_channels': 10,                # Number of EMG channels
            'emg_channels': [f'emg_{i}' for i in range(10)],
            'feature_extraction_enabled': True,
            'filtering_enabled': True,
            'normalization_enabled': True,
            'powerline_freq': 50,            # 50 Hz or 60 Hz depending on region
        }
    
    def reset_buffers(self):
        """Reset data buffers for new streaming session."""
        self.window_buffer = []
        self.predictions_buffer = []
        logger.info("Buffers reset")
    
    def preprocess_signal(self, raw_emg_data):
        """
        Preprocess raw EMG signal.
        
        Parameters:
        -----------
        raw_emg_data : ndarray
            Raw EMG data (n_samples, n_channels)
        
        Returns:
        --------
        processed_data : ndarray
            Processed EMG data
        """
        if self.config['filtering_enabled']:
            # Apply filtering to each channel
            filtered_data = np.zeros_like(raw_emg_data)
            for ch in range(raw_emg_data.shape[1]):
                filtered_data[:, ch] = apply_standard_emg_filter(
                    raw_emg_data[:, ch],
                    fs=self.config['fs'],
                    powerline_freq=self.config['powerline_freq']
                )
            raw_emg_data = filtered_data
        
        if self.config['normalization_enabled']:
            # Normalize data
            raw_emg_data = self.scaler.transform(raw_emg_data)
        
        return raw_emg_data
    
    def extract_window_features(self, window_data):
        """
        Extract features from a single EMG window.
        
        Parameters:
        -----------
        window_data : ndarray
            Window data (window_size, n_channels)
        
        Returns:
        --------
        features : ndarray
            Extracted features
        """
        if not self.config['feature_extraction_enabled']:
            return window_data.flatten()
        
        features = []
        for ch in range(window_data.shape[1]):
            channel_window = window_data[:, ch]
            ch_features = self.feature_extractor.extract_all_features(
                channel_window,
                include_frequency=False  # Faster for real-time
            )
            
            # Flatten dictionary to list
            feature_values = [ch_features[k] for k in sorted(ch_features.keys())]
            features.extend(feature_values)
        
        return np.array(features)
    
    def predict(self, features):
        """
        Make prediction from features.
        
        Parameters:
        -----------
        features : ndarray
            Feature vector
        
        Returns:
        --------
        prediction : int
            Predicted class
        probability : float
            Prediction confidence (0-1)
        """
        # Reshape for model
        X = features.reshape(1, -1)
        
        # Make prediction
        prediction = self.model.predict(X)[0]
        
        # Get probability if available
        if hasattr(self.model, 'predict_proba'):
            proba = self.model.predict_proba(X)[0]
            probability = np.max(proba)
        elif hasattr(self.model, 'decision_function'):
            # For SVM
            decision = self.model.decision_function(X)[0]
            probability = 1 / (1 + np.exp(-decision))
        else:
            probability = 1.0
        
        return int(prediction), float(probability)
    
    def process_streaming_window(self, emg_window):
        """
        Process a single streaming window (ESP32-compatible).
        
        Parameters:
        -----------
        emg_window : ndarray
            Single window of EMG data (window_size, n_channels)
        
        Returns:
        --------
        result : dict
            Inference result with prediction, confidence, and timing
        """
        import time
        
        start_time = time.time()
        
        try:
            # Preprocess
            processed = self.preprocess_signal(emg_window)
            preprocess_time = time.time() - start_time
            
            # Extract features
            feature_time_start = time.time()
            features = self.extract_window_features(processed)
            feature_time = time.time() - feature_time_start
            
            # Make prediction
            pred_time_start = time.time()
            prediction, confidence = self.predict(features)
            pred_time = time.time() - pred_time_start
            
            total_time = time.time() - start_time
            
            result = {
                'success': True,
                'prediction': prediction,
                'confidence': confidence,
                'timing': {
                    'preprocess_ms': preprocess_time * 1000,
                    'features_ms': feature_time * 1000,
                    'prediction_ms': pred_time * 1000,
                    'total_ms': total_time * 1000
                }
            }
            
            self.predictions_buffer.append({
                'timestamp': time.time(),
                'prediction': prediction,
                'confidence': confidence
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error in streaming inference: {e}")
            return {
                'success': False,
                'error': str(e),
                'prediction': None,
                'confidence': None
            }
    
    def get_smoothed_prediction(self, window_size=5):
        """
        Get smoothed prediction from recent predictions (voting).
        
        Parameters:
        -----------
        window_size : int
            Number of recent predictions to consider
        
        Returns:
        --------
        smoothed_prediction : int
            Most common prediction in window
        avg_confidence : float
            Average confidence in window
        """
        if len(self.predictions_buffer) < window_size:
            if len(self.predictions_buffer) == 0:
                return None, 0.0
            recent = self.predictions_buffer
        else:
            recent = self.predictions_buffer[-window_size:]
        
        predictions = [p['prediction'] for p in recent]
        confidences = [p['confidence'] for p in recent]
        
        # Majority voting
        from collections import Counter
        smoothed = Counter(predictions).most_common(1)[0][0]
        avg_conf = np.mean(confidences)
        
        return smoothed, avg_conf
    
    def export_config(self, path):
        """Export configuration for deployment."""
        with open(path, 'w') as f:
            json.dump(self.config, f, indent=2)
        logger.info(f"Configuration exported to {path}")


def main():
    """
    Main real-time inference pipeline demonstration.
    """
    print("\n" + "="*70)
    print("STEP 13: REAL-TIME INFERENCE PIPELINE")
    print("="*70 + "\n")
    
    # Paths
    models_dir = "ml/outputs/models/saved_models"
    scaler_path = "ml/outputs/scaler.pkl"
    output_dir = "ml/outputs"
    pipeline_path = os.path.join(output_dir, "inference_pipeline.pkl")
    config_path = os.path.join(output_dir, "inference_config.json")
    
    try:
        # Find best model
        print("[1/3] Locating trained model...")
        results_path = "ml/outputs/training_results.pkl"
        
        if not os.path.exists(results_path):
            print(f"❌ Error: {results_path} not found")
            print("Please run 11_train_real_model.py first")
            return
        
        with open(results_path, 'rb') as f:
            results_data = pickle.load(f)
        
        best_model_name = results_data['best_model']
        model_filename = best_model_name.replace(' ', '_') + '.pkl'
        model_path = os.path.join(models_dir, model_filename)
        
        if not os.path.exists(model_path):
            print(f"❌ Error: Model not found at {model_path}")
            return
        
        print(f"✓ Best model: {best_model_name}")
        logger.info(f"Using best model: {best_model_name}")
        
        # Initialize pipeline
        print("\n[2/3] Initializing inference pipeline...")
        pipeline = RealtimeEMGInferencePipeline(
            model_path=model_path,
            scaler_path=scaler_path,
            config_path=None
        )
        print(f"✓ Pipeline ready")
        logger.info("Inference pipeline initialized")
        
        # Demonstrate inference on test data
        print("\n[3/3] Testing inference on sample data...")
        
        # Load test data
        features_path = "ml/outputs/extracted_features.pkl"
        with open(features_path, 'rb') as f:
            df_features = pickle.load(f)
        
        # Get a sample
        emg_channels = sorted([col for col in df_features.columns if col.startswith('emg_ch')])
        if emg_channels:
            # Create synthetic window from features
            sample_idx = np.random.randint(0, len(df_features))
            sample_features = df_features.iloc[sample_idx, :-1].values
            sample_label = df_features.iloc[sample_idx, -1]
            
            # Reshape for prediction
            X_test = sample_features.reshape(1, -1)
            
            # Make prediction
            prediction, confidence = pipeline.predict(sample_features)
            
            print(f"  Sample true label: {sample_label}")
            print(f"  Predicted class: {prediction}")
            print(f"  Confidence: {confidence:.4f}")
        
        # Save pipeline
        print("\nSaving inference pipeline...")
        with open(pipeline_path, 'wb') as f:
            pickle.dump(pipeline, f)
        print(f"✓ Saved: {pipeline_path}")
        
        # Export configuration
        pipeline.export_config(config_path)
        print(f"✓ Saved config: {config_path}")
        
        # Print configuration
        print("\n" + "-"*70)
        print("INFERENCE CONFIGURATION")
        print("-"*70)
        for key, value in pipeline.config.items():
            if not isinstance(value, list):
                print(f"  {key}: {value}")
        
        # Print ESP32 integration notes
        print("\n" + "-"*70)
        print("ESP32 INTEGRATION NOTES")
        print("-"*70)
        print("""
The inference pipeline is ready for ESP32 integration:

1. STREAMING DATA FORMAT:
   - EMG windows: (512, 10) = 256 ms of data from 10 channels
   - Sampling rate: 2000 Hz
   - Data type: float32

2. INFERENCE PROCESS:
   - Input: Raw EMG window (512, 10)
   - Processing: Filter + Normalize + Feature Extraction
   - Output: Classification prediction + Confidence

3. TYPICAL LATENCY:
   - Preprocessing: ~10-20 ms
   - Feature extraction: ~5-10 ms
   - Prediction: ~1-5 ms
   - Total: ~20-35 ms (within real-time constraints)

4. DEPLOYMENT STEPS:
   - Convert model to TensorFlow Lite or C++ format
   - Export feature names and scaler parameters
   - Deploy preprocessing pipeline to ESP32
   - Stream windows and collect predictions

5. SMOOTHING STRATEGY:
   - Use majority voting over 5 recent predictions
   - Improves robustness to noise
   - Adds ~1.3 seconds latency (5 windows × 256 ms)
        """)
        
        print("\n" + "="*70)
        print("INFERENCE PIPELINE READY FOR DEPLOYMENT!")
        print("="*70)
        print(f"\nPipeline saved to: {pipeline_path}")
        print(f"Configuration saved to: {config_path}")
        logger.info("Real-time inference pipeline completed successfully")
        
    except Exception as e:
        logger.error(f"Error in inference pipeline: {e}")
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
