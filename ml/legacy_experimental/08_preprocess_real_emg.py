"""
08_preprocess_real_emg.py
EMG Data Preprocessing Pipeline
Cleans, filters, and normalizes raw EMG signals
"""

import pandas as pd
import numpy as np
import logging
import os
from pathlib import Path
import pickle

from ml.utils.preprocessing import EMGPreprocessor
from ml.utils.filters import apply_standard_emg_filter
from ml.utils.visualization import plot_filtered_comparison

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """
    Main preprocessing pipeline for real EMG data.
    """
    print("\n" + "="*70)
    print("STEP 8: EMG PREPROCESSING PIPELINE")
    print("="*70 + "\n")
    
    # Paths
    data_path = "datasets/ninapro_db1/Ninapro_DB1.csv"
    output_dir = "ml/outputs"
    processed_data_path = os.path.join(output_dir, "processed_emg_data.pkl")
    scaler_path = os.path.join(output_dir, "scaler.pkl")
    
    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    try:
        # Initialize preprocessor
        print("[1/6] Initializing preprocessor...")
        preprocessor = EMGPreprocessor(label_column='stimulus')
        logger.info("Preprocessor initialized")
        
        # Load data (sample for demonstration, can process all data with chunking)
        print("[2/6] Loading EMG data...")
        print("Note: Loading sample (200,000 rows) for demonstration")
        print("To use full dataset, modify chunksize parameter")
        
        data = preprocessor.load_data(data_path)
        
        if isinstance(data, type(iter([]))):  # Check if it's an iterator
            # Process chunks
            chunks = []
            for idx, chunk in enumerate(data):
                if idx >= 20:  # Process 20 chunks (200,000 rows)
                    break
                if idx % 5 == 0:
                    print(f"  Processing chunk {idx}...")
                chunks.append(chunk)
            data = pd.concat(chunks, ignore_index=True)
        
        print(f"✓ Loaded {len(data)} rows, {len(data.columns)} columns")
        logger.info(f"Data shape: {data.shape}")
        
        # Detect EMG channels
        print("\n[3/6] Detecting EMG channels...")
        emg_channels = preprocessor.detect_emg_channels(data)
        print(f"✓ Found {len(emg_channels)} EMG channels")
        logger.info(f"EMG channels: {emg_channels}")
        
        # Clean data
        print("\n[4/6] Cleaning data...")
        data_clean = preprocessor.remove_unnecessary_columns(
            data,
            keep_columns=['subject', 'repetition']
        )
        data_clean = preprocessor.handle_missing_values(data_clean, method='forward_fill')
        print(f"✓ Data cleaned. Shape: {data_clean.shape}")
        
        # Remove outliers
        print("\n[5/6] Removing outliers...")
        data_clean = preprocessor.remove_outliers(data_clean, method='iqr', threshold=3)
        print(f"✓ Outliers removed. Final shape: {data_clean.shape}")
        
        # Normalize signals
        print("\n[6/6] Normalizing EMG signals...")
        data_normalized = preprocessor.normalize_signals(data_clean, method='standard', fit=True)
        print(f"✓ Signals normalized using standardization (z-score)")
        
        # Apply filtering to a sample for visualization
        print("\nApplying signal filtering (sample for visualization)...")
        fs = 2000  # Sampling frequency
        
        # Get raw and filtered samples
        raw_sample = data_clean[emg_channels[0]].values[:5000]
        filtered_sample = apply_standard_emg_filter(raw_sample, fs=fs)
        
        # Visualize filtering effect
        viz_path = os.path.join(output_dir, "visualizations")
        Path(viz_path).mkdir(parents=True, exist_ok=True)
        
        filter_viz_path = os.path.join(viz_path, "03_filtering_comparison.png")
        plot_filtered_comparison(
            raw_sample,
            filtered_sample,
            fs=fs,
            channel_name="EMG Channel 0",
            save_path=filter_viz_path
        )
        print(f"✓ Saved filtering comparison: {filter_viz_path}")
        
        # Save processed data
        print("\nSaving processed data...")
        with open(processed_data_path, 'wb') as f:
            pickle.dump(data_normalized, f)
        print(f"✓ Saved processed data: {processed_data_path}")
        logger.info(f"Processed data saved: {processed_data_path}")
        
        # Save preprocessor (with scaler)
        with open(scaler_path, 'wb') as f:
            pickle.dump(preprocessor.scaler, f)
        print(f"✓ Saved scaler: {scaler_path}")
        logger.info(f"Scaler saved: {scaler_path}")
        
        # Print summary statistics
        print("\n" + "-"*70)
        print("PREPROCESSING SUMMARY")
        print("-"*70)
        print(f"Original shape: {data.shape}")
        print(f"After cleaning: {data_clean.shape}")
        print(f"After normalization: {data_normalized.shape}")
        print(f"Rows removed: {len(data) - len(data_normalized)}")
        print(f"Removed percentage: {(len(data) - len(data_normalized)) / len(data) * 100:.2f}%")
        
        print("\nPreprocessed Data Statistics:")
        print("-"*70)
        for ch_name in emg_channels[:3]:  # Show first 3 channels
            ch_data = data_normalized[ch_name].values
            print(f"{ch_name:10s}: "
                  f"Mean={ch_data.mean():8.4f}, "
                  f"Std={ch_data.std():8.4f}, "
                  f"Min={ch_data.min():8.4f}, "
                  f"Max={ch_data.max():8.4f}")
        
        print("\n" + "="*70)
        print("PREPROCESSING COMPLETE!")
        print("="*70)
        print(f"\nPreprocessed data saved to: {processed_data_path}")
        print(f"Scaler saved to: {scaler_path}")
        logger.info("Preprocessing pipeline completed successfully")
        
    except Exception as e:
        logger.error(f"Error in preprocessing pipeline: {e}")
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
