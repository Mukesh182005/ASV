#!/bin/bash
# ASV ML Pipeline - Quick Start Script
# Runs all stages of the EMG classification pipeline
# Usage: bash run_pipeline.sh

set -e  # Exit on error

echo "=================================================="
echo "ASV - A Silent Voice"
echo "EMG ML Pipeline - Complete Execution"
echo "=================================================="
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if Python is available
if ! command -v python &> /dev/null; then
    echo "❌ Python not found. Please install Python 3.8+"
    exit 1
fi

echo "🐍 Python version:"
python --version
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
pip install -q -r requirements.txt
echo "✅ Dependencies installed"
echo ""

# Stage 7: Visualization
echo "=================================================="
echo "STAGE 7: EMG SIGNAL VISUALIZATION"
echo "=================================================="
echo "📊 Visualizing raw EMG signals..."
python 07_visualize_real_emg.py
echo ""

# Stage 8: Preprocessing
echo "=================================================="
echo "STAGE 8: DATA PREPROCESSING"
echo "=================================================="
echo "🧹 Cleaning and preprocessing data..."
python 08_preprocess_real_emg.py
echo ""

# Stage 9: Segmentation
echo "=================================================="
echo "STAGE 9: SIGNAL SEGMENTATION"
echo "=================================================="
echo "✂️  Segmenting signals into windows..."
python 09_segment_signals.py
echo ""

# Stage 10: Feature Extraction
echo "=================================================="
echo "STAGE 10: FEATURE EXTRACTION"
echo "=================================================="
echo "🔍 Extracting features from windows..."
python 10_feature_extraction_real.py
echo ""

# Stage 11: Model Training
echo "=================================================="
echo "STAGE 11: MODEL TRAINING"
echo "=================================================="
echo "🤖 Training classification models..."
python 11_train_real_model.py
echo ""

# Stage 12: Evaluation
echo "=================================================="
echo "STAGE 12: MODEL EVALUATION"
echo "=================================================="
echo "📈 Evaluating models and generating visualizations..."
python 12_evaluate_model.py
echo ""

# Stage 13: Real-Time Inference
echo "=================================================="
echo "STAGE 13: REAL-TIME INFERENCE SETUP"
echo "=================================================="
echo "⚡ Preparing real-time inference pipeline..."
python 13_realtime_inference_pipeline.py
echo ""

# Summary
echo "=================================================="
echo "✅ PIPELINE COMPLETE!"
echo "=================================================="
echo ""
echo "📂 Outputs saved to: ml/outputs/"
echo ""
echo "📊 Key outputs:"
echo "   • Visualizations: ml/outputs/visualizations/"
echo "   • Processed data: ml/outputs/processed_emg_data.pkl"
echo "   • Extracted features: ml/outputs/extracted_features.csv"
echo "   • Trained models: ml/outputs/models/saved_models/"
echo "   • Evaluation report: ml/outputs/evaluation_report.txt"
echo "   • Inference pipeline: ml/outputs/inference_pipeline.pkl"
echo ""
echo "📖 For more information, see README.md"
echo ""
