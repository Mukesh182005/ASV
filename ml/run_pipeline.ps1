# ASV ML Pipeline - Quick Start Script (PowerShell)
# Runs all stages of the EMG classification pipeline
# Usage: powershell -ExecutionPolicy Bypass -File run_pipeline.ps1

Write-Host "=================================================="
Write-Host "ASV - A Silent Voice" -ForegroundColor Cyan
Write-Host "EMG ML Pipeline - Complete Execution" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "🐍 Python version: $pythonVersion"
}
catch {
    Write-Host "❌ Python not found. Please install Python 3.8+" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Install dependencies
Write-Host "📦 Installing dependencies..."
pip install -q -r requirements.txt
Write-Host "✅ Dependencies installed" -ForegroundColor Green
Write-Host ""

# Define stages
$stages = @(
    @{
        Number = 7
        Name = "EMG SIGNAL VISUALIZATION"
        Description = "📊 Visualizing raw EMG signals..."
        Script = "07_visualize_real_emg.py"
    },
    @{
        Number = 8
        Name = "DATA PREPROCESSING"
        Description = "🧹 Cleaning and preprocessing data..."
        Script = "08_preprocess_real_emg.py"
    },
    @{
        Number = 9
        Name = "SIGNAL SEGMENTATION"
        Description = "✂️ Segmenting signals into windows..."
        Script = "09_segment_signals.py"
    },
    @{
        Number = 10
        Name = "FEATURE EXTRACTION"
        Description = "🔍 Extracting features from windows..."
        Script = "10_feature_extraction_real.py"
    },
    @{
        Number = 11
        Name = "MODEL TRAINING"
        Description = "🤖 Training classification models..."
        Script = "11_train_real_model.py"
    },
    @{
        Number = 12
        Name = "MODEL EVALUATION"
        Description = "📈 Evaluating models and generating visualizations..."
        Script = "12_evaluate_model.py"
    },
    @{
        Number = 13
        Name = "REAL-TIME INFERENCE SETUP"
        Description = "⚡ Preparing real-time inference pipeline..."
        Script = "13_realtime_inference_pipeline.py"
    }
)

# Run each stage
foreach ($stage in $stages) {
    Write-Host "===================================================" -ForegroundColor Yellow
    Write-Host "STAGE $($stage.Number): $($stage.Name)" -ForegroundColor Yellow
    Write-Host "===================================================" -ForegroundColor Yellow
    Write-Host $stage.Description
    
    try {
        python $stage.Script
        Write-Host ""
    }
    catch {
        Write-Host "❌ Error in Stage $($stage.Number): $_" -ForegroundColor Red
        exit 1
    }
}

# Summary
Write-Host "===================================================" -ForegroundColor Green
Write-Host "✅ PIPELINE COMPLETE!" -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Green
Write-Host ""

Write-Host "📂 Outputs saved to: ml/outputs/" -ForegroundColor Cyan
Write-Host ""
Write-Host "📊 Key outputs:"
Write-Host "   • Visualizations: ml/outputs/visualizations/" -ForegroundColor White
Write-Host "   • Processed data: ml/outputs/processed_emg_data.pkl" -ForegroundColor White
Write-Host "   • Extracted features: ml/outputs/extracted_features.csv" -ForegroundColor White
Write-Host "   • Trained models: ml/outputs/models/saved_models/" -ForegroundColor White
Write-Host "   • Evaluation report: ml/outputs/evaluation_report.txt" -ForegroundColor White
Write-Host "   • Inference pipeline: ml/outputs/inference_pipeline.pkl" -ForegroundColor White
Write-Host ""
Write-Host "📖 For more information, see README.md" -ForegroundColor Cyan
Write-Host ""
