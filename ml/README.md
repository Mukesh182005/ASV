# ASV (A Silent Voice) - EMG ML Pipeline
## Professional Real-Time EMG Signal Classification System

### 📋 Overview

This is a **production-grade machine learning pipeline** for EMG (Electromyography) signal classification using the NinaPro DB1 dataset. The system is specifically designed for the **ASV (A Silent Voice)** project - an AI-powered wearable silent speech recognition system.

**Key Features:**
- ✅ Complete end-to-end ML pipeline (load → preprocess → train → evaluate)
- ✅ Professional modular architecture with reusable utilities
- ✅ Multiple ML models (Random Forest, SVM, KNN)
- ✅ Real-time inference pipeline optimized for ESP32
- ✅ Comprehensive visualization and evaluation metrics
- ✅ Production-ready code with logging and error handling
- ✅ Support for large datasets (~12.5M rows) with chunking
- ✅ Biomedical signal processing best practices

---

## 📁 Project Structure

```
ml/
├── utils/                              # Reusable utility modules
│   ├── __init__.py                    # Package initialization
│   ├── filters.py                     # Signal filtering utilities
│   ├── features.py                    # Feature extraction (MAV, RMS, ZCR, etc.)
│   ├── visualization.py               # Plotting utilities
│   └── preprocessing.py               # Data loading and preprocessing
│
├── models/
│   └── saved_models/                  # Trained ML models directory
│
├── outputs/                           # Generated outputs
│   ├── visualizations/                # Plots and figures
│   ├── processed_emg_data.pkl         # Preprocessed data
│   ├── segmented_windows.pkl          # Signal windows
│   ├── extracted_features.csv/.pkl    # Features for ML
│   ├── training_results.pkl           # Model training results
│   ├── evaluation_report.txt          # Text report
│   └── inference_config.json          # Real-time inference config
│
├── 07_visualize_real_emg.py           # EMG signal visualization
├── 08_preprocess_real_emg.py          # Data preprocessing
├── 09_segment_signals.py              # Signal segmentation into windows
├── 10_feature_extraction_real.py      # Feature extraction
├── 11_train_real_model.py             # Model training
├── 12_evaluate_model.py               # Evaluation & visualization
├── 13_realtime_inference_pipeline.py  # Real-time inference setup
│
├── requirements.txt                   # Python dependencies
└── README.md                          # This file
```

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Navigate to project directory
cd ml

# Install required packages
pip install -r requirements.txt
```

### 2. Run the Complete Pipeline

Execute all steps in sequence:

```bash
# Step 7: Visualize raw EMG signals
python 07_visualize_real_emg.py

# Step 8: Preprocess data (clean, filter, normalize)
python 08_preprocess_real_emg.py

# Step 9: Segment signals into windows
python 09_segment_signals.py

# Step 10: Extract features
python 10_feature_extraction_real.py

# Step 11: Train ML models
python 11_train_real_model.py

# Step 12: Evaluate models & generate reports
python 12_evaluate_model.py

# Step 13: Prepare real-time inference pipeline
python 13_realtime_inference_pipeline.py
```

---

## 📊 Pipeline Stages Explained

### Stage 7: Visualization (`07_visualize_real_emg.py`)
**Purpose:** Understand raw EMG signal characteristics

**What it does:**
- Loads sample EMG data from NinaPro DB1
- Plots all 10 EMG channels
- Shows frequency spectrum for each channel
- Generates biomedical-style visualizations

**Outputs:**
- `outputs/visualizations/01_raw_emg_channels.png` - 10-second sample
- `outputs/visualizations/02_raw_emg_extended.png` - 30-second sample
- `outputs/visualizations/spectrum/` - Frequency domain plots

**Configuration:**
- Sample size: 50,000 rows (≈ 25 seconds at 2000 Hz)
- Channels: 10 EMG sensors (emg_0 to emg_9)
- Sampling frequency: 2000 Hz

---

### Stage 8: Preprocessing (`08_preprocess_real_emg.py`)
**Purpose:** Clean and prepare raw data for ML

**Processing Steps:**
1. **Load Data** - Read CSV in chunks (memory efficient)
2. **Clean Columns** - Keep only EMG channels and labels
3. **Handle Missing Values** - Forward fill strategy
4. **Remove Outliers** - IQR method (threshold=3σ)
5. **Normalize Signals** - StandardScaler (z-score normalization)
6. **Apply Filtering** - Bandpass (10-500 Hz) + Notch (50 Hz)

**Outputs:**
- `outputs/processed_emg_data.pkl` - Cleaned & normalized data
- `outputs/scaler.pkl` - Fitted StandardScaler for later use
- `outputs/visualizations/03_filtering_comparison.png` - Before/after

**Key Parameters:**
```
- Outlier threshold: 3 standard deviations
- Normalization: StandardScaler (mean=0, std=1)
- Bandpass filter: 10-500 Hz (standard EMG range)
- Notch filter: 50 Hz (powerline interference)
```

---

### Stage 9: Segmentation (`09_segment_signals.py`)
**Purpose:** Divide continuous signals into fixed-length windows

**Segmentation Strategy:**
- **Window Size:** 512 samples = 256 ms (optimal for hand gesture recognition)
- **Overlap:** 50% (256 samples step) - captures signal dynamics
- **Sliding Window:** Creates overlapping windows for better feature extraction

**Mathematical Background:**
```
Window Configuration:
- Duration: 512 samples / 2000 Hz = 0.256 seconds = 256 ms
- Step size: 512 × (1 - 0.5) = 256 samples = 128 ms
- Overlap: 50% ensures smooth transitions
```

**Outputs:**
- `outputs/segmented_windows.pkl` - Contains:
  - `windows`: ndarray of shape (n_windows, 512, 10)
  - `labels`: ndarray of shape (n_windows,)
- `outputs/segmentation_metadata.pkl` - Metadata

**Example Statistics:**
```
Input: 200,000 samples
Windows created: ~800 (with 50% overlap)
Channels: 10 EMG sensors
Classes: Multiple hand gestures
```

---

### Stage 10: Feature Extraction (`10_feature_extraction_real.py`)
**Purpose:** Extract meaningful features from each window

**Extracted Features (per channel):**

**Time-Domain Features:**
- **MAV** (Mean Absolute Value) - Average amplitude
- **RMS** (Root Mean Square) - Signal power
- **ZCR** (Zero Crossing Rate) - Frequency transitions
- **WL** (Waveform Length) - Signal complexity
- **VAR** (Variance) - Signal spread
- **STD** (Standard Deviation) - Amplitude variation

**Frequency-Domain Features:**
- **MF** (Mean Frequency) - Center of mass in spectrum
- **MEDF** (Median Frequency) - 50% power point

**Feature Matrix:**
```
Shape: (n_windows, n_features × n_channels)
Example: (800, 60) = 800 windows × (8 features × 10 channels)
```

**Outputs:**
- `outputs/extracted_features.csv` - Features in CSV format
- `outputs/extracted_features.pkl` - Binary pickle (for ML)
- `outputs/feature_names.pkl` - Feature name mapping

---

### Stage 11: Training (`11_train_real_model.py`)
**Purpose:** Train and compare multiple ML models

**Models Trained:**

1. **Random Forest** (Recommended)
   - Hyperparameters:
     - n_estimators: 100 trees
     - max_depth: 15 levels
     - Parallelized: n_jobs=-1
   - Pros: Interpretable, handles non-linear patterns, robust
   - Cons: Slower prediction time

2. **Support Vector Machine (SVM)**
   - Hyperparameters:
     - kernel: RBF (non-linear)
     - C: 1.0 (regularization)
     - gamma: 'scale' (auto)
   - Pros: Works well in high dimensions, memory efficient
   - Cons: Slower training, harder to tune

3. **K-Nearest Neighbors (KNN)**
   - Hyperparameters:
     - n_neighbors: 5
     - Distance metric: Euclidean
     - Parallelized: n_jobs=-1
   - Pros: Simple, interpretable
   - Cons: Slower prediction, sensitive to feature scaling

**Training Process:**
```
1. Load extracted features
2. Split: 80% train, 20% test (stratified)
3. Train each model
4. Evaluate on test set
5. Compare metrics: Accuracy, Precision, Recall, F1-Score
6. Select best model (highest F1-score)
7. Save all models
```

**Outputs:**
- `outputs/models/saved_models/Random_Forest.pkl` - Best model
- `outputs/models/saved_models/SVM.pkl` - Alternative
- `outputs/models/saved_models/KNN.pkl` - Alternative
- `outputs/training_results.pkl` - All results and metrics

**Expected Performance:**
```
Typical Range for Hand Gesture Recognition:
- Accuracy: 85-98% (depends on number of classes)
- F1-Score: 0.85-0.95
- Training Time: 10-30 seconds
```

---

### Stage 12: Evaluation (`12_evaluate_model.py`)
**Purpose:** Generate comprehensive evaluation metrics and visualizations

**Metrics Calculated:**
- **Accuracy** - Overall correctness
- **Precision** - False positive rate
- **Recall** - False negative rate
- **F1-Score** - Harmonic mean of precision and recall
- **Confusion Matrix** - Per-class accuracy breakdown

**Visualizations Generated:**
1. **Confusion Matrices** - For each model
   - Shows which classes are confused
   - Normalized to show percentages
2. **Model Comparison Chart** - Side-by-side metrics
3. **Feature Distributions** - Shows feature ranges

**Outputs:**
- `outputs/visualizations/confusion_matrix_*.png` - For each model
- `outputs/visualizations/model_comparison.png` - Bar chart
- `outputs/visualizations/feature_distributions.png` - Histograms
- `outputs/evaluation_report.txt` - Complete text report

**Interpretation Guide:**
```
Confusion Matrix (rows=true, columns=predicted):
- Diagonal = Correct predictions ✓
- Off-diagonal = Misclassifications ✗

For gesture recognition:
- If gesture A confused with B → they may have similar EMG patterns
- Suggests need for better feature engineering
```

---

### Stage 13: Real-Time Inference (`13_realtime_inference_pipeline.py`)
**Purpose:** Setup production-ready inference for ESP32 integration

**Pipeline Architecture:**
```
Raw EMG Window (512 samples, 10 channels)
           ↓
    [Filtering]
    (Bandpass + Notch)
           ↓
   [Normalization]
   (Apply scaler)
           ↓
 [Feature Extraction]
   (8 features × 10 ch)
           ↓
  [ML Classification]
  (Trained model)
           ↓
 Prediction + Confidence
```

**Real-Time Characteristics:**
```
Latency Breakdown:
- Filtering: ~10-20 ms
- Feature Extraction: ~5-10 ms
- Classification: ~1-5 ms
- Total: ~20-35 ms (well within real-time constraints)

ESP32 Requirements:
- Memory: ~10-50 MB (model + buffers)
- CPU: Can run on ESP32 with optimizations
- Communication: BLE for data streaming
```

**Outputs:**
- `outputs/inference_pipeline.pkl` - Ready-to-use pipeline
- `outputs/inference_config.json` - Configuration for ESP32
- ESP32 integration documentation

**Usage Example:**
```python
from utils.inference_pipeline import RealtimeEMGInferencePipeline

# Load pipeline
pipeline = RealtimeEMGInferencePipeline(
    model_path='models/saved_models/Random_Forest.pkl',
    scaler_path='scaler.pkl'
)

# Process streaming window
result = pipeline.process_streaming_window(emg_window)
print(f"Prediction: {result['prediction']}")
print(f"Confidence: {result['confidence']:.2f}")
```

---

## 🔧 Configuration & Customization

### Modify Window Size (Stage 9)
```python
# In 09_segment_signals.py
WINDOW_SIZE = 512      # Increase for longer context
OVERLAP = 0.5         # Increase for more windows
FS = 2000             # Sampling frequency
```

### Add/Remove Features (Stage 10)
```python
# In 10_feature_extraction_real.py
INCLUDE_FREQUENCY = True  # Set False for faster processing
```

### Tune ML Models (Stage 11)
```python
# In 11_train_real_model.py
RandomForestClassifier(
    n_estimators=150,   # More trees = better accuracy but slower
    max_depth=20,       # Deeper trees = more complex patterns
    random_state=42
)
```

### Adjust Preprocessing (Stage 8)
```python
# In 08_preprocess_real_emg.py
data_clean = preprocessor.remove_outliers(
    data_clean, 
    method='iqr', 
    threshold=2  # Stricter outlier detection (1.5-3.0)
)
```

---

## 📈 Performance Optimization

### For Large Datasets
```python
# Use chunked loading
data = pd.read_csv('data.csv', chunksize=10000)
for chunk in data:
    # Process chunk
    pass
```

### For Faster Training
```python
# Use fewer features
INCLUDE_FREQUENCY = False  # Skip frequency features

# Use simpler models
KNeighborsClassifier(n_neighbors=3)  # Faster than RF/SVM
```

### For Better Accuracy
```python
# More complex preprocessing
preprocessor.remove_outliers(threshold=1.5)  # Stricter

# Smaller windows
WINDOW_SIZE = 256  # Better temporal resolution

# More features
INCLUDE_FREQUENCY = True  # Add frequency domain
```

---

## 🔍 Troubleshooting

### Memory Issues
**Problem:** "Memory Error" when loading data

**Solution:**
```python
# Use chunking
data = pd.read_csv('data.csv', chunksize=10000)
```

### Slow Training
**Problem:** Training takes too long

**Solution:**
```python
# Use KNN instead of SVM
# Reduce window count
# Skip frequency features
```

### Low Accuracy
**Problem:** Model accuracy < 80%

**Solutions:**
1. Check feature distribution - are features meaningful?
2. Try different window sizes (256-1024 samples)
3. Use different classifier
4. Add more preprocessing (better filtering)
5. Collect more training data

### Segmentation Produces Few Windows
**Problem:** Very few windows generated

**Solution:**
```python
# Reduce window size
WINDOW_SIZE = 256  # Was 512

# Reduce overlap
OVERLAP = 0.25  # Was 0.5
```

---

## 📊 Expected Outputs

After running the complete pipeline, you should have:

```
outputs/
├── processed_emg_data.pkl (50-200 MB)
├── segmented_windows.pkl (50-500 MB)
├── extracted_features.csv (5-50 MB)
├── extracted_features.pkl
├── scaler.pkl
├── training_results.pkl
├── evaluation_report.txt (5-20 KB)
├── inference_pipeline.pkl (10-50 MB)
├── inference_config.json (1 KB)
└── visualizations/
    ├── 01_raw_emg_channels.png
    ├── 02_raw_emg_extended.png
    ├── 03_filtering_comparison.png
    ├── confusion_matrix_*.png (3 files)
    ├── model_comparison.png
    ├── feature_distributions.png
    └── spectrum/
        ├── channel_0_spectrum.png
        ├── channel_1_spectrum.png
        └── channel_2_spectrum.png
```

---

## 🧠 Biomedical Signal Processing Background

### Why EMG Signals?
- **Non-invasive** - Surface electrodes
- **Real-time** - Low latency
- **Direct neural interface** - Captures muscle activation
- **Reproducible** - Same movements produce similar patterns

### EMG Signal Characteristics
```
Amplitude: 0-5 mV (microvolts)
Frequency: 0-500 Hz (10-500 Hz useful range)
Duration: Milliseconds to seconds
Noise: 50-60 Hz powerline interference, motion artifacts
```

### Why Segmentation?
- EMG is non-stationary (changes over time)
- Fixed windows capture local stationarity
- 256 ms windows are optimal for hand gesture recognition
- Overlap ensures smooth transitions between windows

### Why Feature Extraction?
- Raw signals are high-dimensional (512 samples)
- Features reduce dimensionality (8 features per channel)
- Features capture meaningful signal characteristics
- ML models work better on feature space than raw signals

---

## 🔌 ESP32 Integration

### Streaming Data Format
```
// C++ on ESP32
struct EMGWindow {
    float data[512][10];        // 512 samples, 10 channels
    uint64_t timestamp_ms;      // When window was captured
};

// Send to Python inference pipeline
send_over_ble(window_data);
receive_prediction(gesture_id, confidence);
```

### Real-Time Processing Loop
```
1. Collect 512 samples from 10 EMG channels (256 ms)
2. Apply filtering (10-500 Hz bandpass + 50 Hz notch)
3. Normalize using fitted scaler
4. Extract 80 features (8 per channel)
5. Pass to ML model
6. Get prediction (gesture ID) + confidence
7. If confidence > 0.8: Execute gesture command
8. Send feedback to user (haptic/visual)
```

### Data Format for Transmission
```json
{
  "timestamp": 1234567890,
  "window_id": 42,
  "channels": 10,
  "samples": 512,
  "data": [
    [0.1, 0.2, -0.3, ...],  // Channel 0
    [0.05, -0.1, 0.15, ...], // Channel 1
    ...
  ]
}
```

---

## 📚 References & Further Reading

### EMG Signal Processing
- Phinyomark et al. - "A Review of the Feasibility and Effectiveness of EMG-based Gesture Recognition"
- Hudgins et al. - "A New Strategy for Multifunction Myoelectric Control"

### Machine Learning for EMG
- Atzori et al. - "Deep Learning with Convolutional Neural Networks Applied to EMG Data"
- NinaPro Dataset - https://ninapro.iit.unimi.it/

### Real-Time Inference
- TensorFlow Lite for Microcontrollers
- ESP32 Edge ML Optimization Techniques

---

## 📝 Citation

If you use this pipeline in your research, please cite:

```bibtex
@software{asv_emg_pipeline,
  title={ASV: A Silent Voice - Real-Time EMG Classification Pipeline},
  author={Your Name},
  year={2024},
  url={https://github.com/yourusername/ASV}
}
```

---

## 📄 License

MIT License - See LICENSE file for details

---

## ✉️ Support

For issues, questions, or suggestions:
1. Check the Troubleshooting section
2. Review the code comments
3. Check dataset documentation
4. Open an issue on GitHub

---

## 🎯 Next Steps

After completing the pipeline:

1. **Deploy to ESP32**
   - Convert model to TensorFlow Lite
   - Implement C++ inference code
   - Stream EMG data via BLE

2. **Collect Real User Data**
   - Record EMG from target users
   - Retrain model with real data
   - Improve accuracy

3. **Add More Gestures**
   - Extend to more hand movements
   - Retrain classifier
   - Expand gesture library

4. **Integration & Testing**
   - Test real-time performance
   - User acceptance testing
   - Iterate based on feedback

---

**Last Updated:** November 2024
**Version:** 1.0.0
**Status:** Production Ready ✅
