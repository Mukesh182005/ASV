"""
10_feature_extraction_real.py
EMG Feature Extraction Pipeline
Extracts time and frequency domain features from segmented windows
"""

import pandas as pd
import numpy as np
import logging
import os
from pathlib import Path
import pickle

from ml.utils.features import EMGFeatureExtractor, extract_features_vectorized

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """
    Main feature extraction pipeline.
    """
    print("\n" + "="*70)
    print("STEP 10: EMG FEATURE EXTRACTION")
    print("="*70 + "\n")
    
    # Paths
    segmented_data_path = "ml/outputs/segmented_windows.pkl"
    metadata_path = "ml/outputs/segmentation_metadata.pkl"
    output_dir = "ml/outputs"
    features_path = os.path.join(output_dir, "extracted_features.pkl")
    features_csv_path = os.path.join(output_dir, "extracted_features.csv")
    feature_names_path = os.path.join(output_dir, "feature_names.pkl")
    
    # Configuration
    FS = 2000  # Sampling frequency
    INCLUDE_FREQUENCY = True  # Extract frequency-domain features
    
    try:
        # Load segmented data
        print("[1/5] Loading segmented data...")
        if not os.path.exists(segmented_data_path):
            print(f"❌ Error: {segmented_data_path} not found")
            print("Please run 09_segment_signals.py first")
            return
        
        with open(segmented_data_path, 'rb') as f:
            seg_data = pickle.load(f)
        
        windows = seg_data['windows']
        labels = seg_data['labels']
        
        print(f"✓ Loaded {len(windows)} windows")
        print(f"  Window shape: {windows.shape}")
        logger.info(f"Windows: {windows.shape}, Labels: {labels.shape}")
        
        # Load metadata
        with open(metadata_path, 'rb') as f:
            metadata = pickle.load(f)
        
        n_channels = metadata['n_channels']
        print(f"✓ Number of channels: {n_channels}")
        
        # Initialize feature extractor
        print("\n[2/5] Initializing feature extractor...")
        extractor = EMGFeatureExtractor(fs=FS)
        print(f"✓ Feature extractor ready")
        
        # Extract features from all windows
        print("\n[3/5] Extracting features from all windows...")
        print("This may take a while for large datasets...")
        
        features_array, feature_names = extract_features_vectorized(
            windows,
            fs=FS,
            include_frequency=INCLUDE_FREQUENCY
        )
        
        print(f"✓ Extracted features")
        print(f"  Features shape: {features_array.shape}")
        logger.info(f"Extracted features shape: {features_array.shape}")
        
        # Create features dataframe
        print("\n[4/5] Creating features dataframe...")
        
        # Expand feature names for multi-channel
        expanded_feature_names = []
        for ch in range(n_channels):
            for fname in feature_names:
                expanded_feature_names.append(f"{fname}_ch{ch}")
        
        df_features = pd.DataFrame(features_array, columns=expanded_feature_names)
        df_features['label'] = labels
        
        print(f"✓ Features dataframe created: {df_features.shape}")
        logger.info(f"Features dataframe shape: {df_features.shape}")
        
        # Save features
        print("\n[5/5] Saving extracted features...")
        
        # Save as pickle (for ML pipeline)
        with open(features_path, 'wb') as f:
            pickle.dump(df_features, f)
        print(f"✓ Saved pickle: {features_path}")
        
        # Save as CSV (for inspection)
        df_features.to_csv(features_csv_path, index=False)
        print(f"✓ Saved CSV: {features_csv_path}")
        
        # Save feature names
        with open(feature_names_path, 'wb') as f:
            pickle.dump(expanded_feature_names, f)
        print(f"✓ Saved feature names: {feature_names_path}")
        
        # Print feature extraction summary
        print("\n" + "-"*70)
        print("FEATURE EXTRACTION SUMMARY")
        print("-"*70)
        print(f"Total windows: {len(features_array)}")
        print(f"Number of features: {len(expanded_feature_names)}")
        print(f"Channels: {n_channels}")
        
        # List feature names
        print("\nFeature names (per channel):")
        base_features = set()
        for fname in feature_names:
            base_features.add(fname)
        print(f"  {', '.join(sorted(base_features))}")
        
        print(f"\nTotal unique features: {len(expanded_feature_names)}")
        
        # Feature statistics
        print("\nFeature statistics:")
        print("-"*70)
        print("Feature                Mean       Std        Min        Max")
        print("-"*70)
        
        for feature in expanded_feature_names[:10]:  # Show first 10
            data = df_features[feature].values
            print(f"{feature:20s} {data.mean():10.4f} {data.std():10.4f} "
                  f"{data.min():10.4f} {data.max():10.4f}")
        
        # Label distribution
        print("\nLabel distribution in features:")
        print("-"*70)
        for label in sorted(df_features['label'].unique()):
            count = (df_features['label'] == label).sum()
            pct = count / len(df_features) * 100
            print(f"  Class {label:3d}: {count:6d} samples ({pct:5.1f}%)")
        
        print("\n" + "="*70)
        print("FEATURE EXTRACTION COMPLETE!")
        print("="*70)
        print(f"\nFeatures saved to: {features_csv_path}")
        print(f"Total features extracted: {len(expanded_feature_names)}")
        logger.info("Feature extraction pipeline completed successfully")
        
    except Exception as e:
        logger.error(f"Error in feature extraction pipeline: {e}")
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
