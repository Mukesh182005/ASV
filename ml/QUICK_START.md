# ASV ML Pipeline - Quick Reference Guide

## 🚀 Fastest Way to Run

### Option 1: Windows PowerShell (Recommended for Windows)
```powershell
cd ml
powershell -ExecutionPolicy Bypass -File run_pipeline.ps1
```

### Option 2: Unix/Linux/Mac Bash
```bash
cd ml
bash run_pipeline.sh
```

### Option 3: Manual (Step-by-Step)
```bash
cd ml
pip install -r requirements.txt

python 07_visualize_real_emg.py
python 08_preprocess_real_emg.py
python 09_segment_signals.py
python 10_feature_extraction_real.py
python 11_train_real_model.py
python 12_evaluate_model.py
python 13_realtime_inference_pipeline.py
```

---

## 📊 Individual Stage Execution

If you want to run specific stages:

```bash
# Only visualization
python 07_visualize_real_emg.py

# Only preprocessing (requires raw data)
python 08_preprocess_real_emg.py

# Only segmentation (requires preprocessed data from stage 8)
python 09_segment_signals.py

# Only feature extraction (requires segmented data from stage 9)
python 10_feature_extraction_real.py

# Only training (requires features from stage 10)
python 11_train_real_model.py

# Only evaluation (requires training results from stage 11)
python 12_evaluate_model.py

# Only inference setup (requires training results from stage 11)
python 13_realtime_inference_pipeline.py
```

---

## ⏱️ Expected Timing

| Stage | Duration | Status |
|-------|----------|--------|
| 7 - Visualization | ~5 sec | Quick |
| 8 - Preprocessing | ~10-15 sec | Quick |
| 9 - Segmentation | ~5 sec | Quick |
| 10 - Feature Extraction | ~10 sec | Quick |
| 11 - Training | ~30-60 sec | Takes time |
| 12 - Evaluation | ~10 sec | Quick |
| 13 - Inference | ~5 sec | Quick |
| **TOTAL** | **~2-3 min** | **Complete** |

---

## 📂 Output Files Generated

```
After Stage 7:
  ml/outputs/visualizations/
    ├── 01_raw_emg_channels.png
    ├── 02_raw_emg_extended.png
    └── spectrum/
        ├── channel_0_spectrum.png
        ├── channel_1_spectrum.png
        └── channel_2_spectrum.png

After Stage 8:
  ml/outputs/
    ├── processed_emg_data.pkl (50-200 MB)
    ├── scaler.pkl
    └── visualizations/
        └── 03_filtering_comparison.png

After Stage 9:
  ml/outputs/
    ├── segmented_windows.pkl (50-500 MB)
    └── segmentation_metadata.pkl

After Stage 10:
  ml/outputs/
    ├── extracted_features.csv (5-50 MB)
    ├── extracted_features.pkl
    └── feature_names.pkl

After Stage 11:
  ml/outputs/
    ├── models/saved_models/
    │   ├── Random_Forest.pkl
    │   ├── SVM.pkl
    │   └── KNN.pkl
    └── training_results.pkl

After Stage 12:
  ml/outputs/
    ├── evaluation_report.txt
    └── visualizations/
        ├── confusion_matrix_*.png (3 files)
        ├── model_comparison.png
        ├── feature_distributions.png
        └── [previous outputs]

After Stage 13:
  ml/outputs/
    ├── inference_pipeline.pkl
    ├── inference_config.json
    └── [all previous outputs]
```

---

## 🔧 Customization

### Modify window size
Edit `09_segment_signals.py`:
```python
WINDOW_SIZE = 512    # Change to 256, 512, 1024, etc.
OVERLAP = 0.5        # Change to 0.25, 0.5, 0.75
FS = 2000            # Sampling frequency
```

### Add/remove features
Edit `10_feature_extraction_real.py`:
```python
INCLUDE_FREQUENCY = True  # Set False for faster processing
```

### Tune ML models
Edit `11_train_real_model.py`:
```python
RandomForestClassifier(
    n_estimators=200,  # Increase for better accuracy
    max_depth=20,
    random_state=42
)
```

### Change preprocessing parameters
Edit `08_preprocess_real_emg.py`:
```python
data_clean = preprocessor.remove_outliers(threshold=2)  # 1.5-3.0 range
```

---

## ✅ Checklist

Before running:
- [ ] Python 3.8+ installed
- [ ] In `ml/` directory
- [ ] Raw data available at `datasets/ninapro_db1/Ninapro_DB1.csv`
- [ ] Enough disk space (5-10 GB for full pipeline)
- [ ] Enough RAM (8+ GB recommended)

---

## 🐛 Troubleshooting

### "Module not found" error
```bash
pip install -r requirements.txt
```

### "Out of memory" error
- Use stage 8 with chunking parameter
- Reduce sample size in visualization script
- Close other applications

### "File not found" error
- Make sure previous stages completed successfully
- Check file paths are correct
- Files should be in `ml/outputs/`

### "No EMG channels detected"
- Check input CSV has columns named `emg_0`, `emg_1`, etc.
- Verify dataset format matches NinaPro DB1

### Slow training
- Use KNN instead of SVM (faster)
- Reduce features: set `INCLUDE_FREQUENCY = False`
- Use smaller window size

---

## 📊 Verify Results

After running stage 11 (training), check:

1. **All models trained successfully**
   - Should see accuracy scores for Random Forest, SVM, KNN

2. **Best model selected**
   - Usually Random Forest performs best
   - F1-score should be > 0.80

3. **Files generated**
   - `ml/outputs/models/saved_models/` should have 3 .pkl files

After running stage 12 (evaluation):

1. **Visualizations created**
   - Should see confusion matrices, comparison chart, feature distributions

2. **Evaluation report generated**
   - Text file with detailed metrics
   - Check: `ml/outputs/evaluation_report.txt`

---

## 🎯 Next Steps

1. **Review outputs**: Check generated plots and report
2. **Assess performance**: Look at accuracy and F1-score
3. **Deploy model**: Use inference pipeline for ESP32
4. **Collect real data**: Retrain with actual user EMG
5. **Iterate**: Improve accuracy with better preprocessing

---

## 📚 Documentation

- **Complete guide**: `README.md` (1000+ lines)
- **Build summary**: `BUILD_SUMMARY.md` (comprehensive overview)
- **This file**: Quick reference guide

---

## 💬 Tips

- Monitor console output for progress
- Check `ml/outputs/` directory after each stage
- Read evaluation report for model performance details
- Visualizations are publication-quality (300 DPI)
- Use real-time inference pipeline output for ESP32 deployment

---

**Last Updated:** November 2024
**Status:** Production Ready ✅
