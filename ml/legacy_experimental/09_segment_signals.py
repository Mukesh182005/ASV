"""
09_segment_signals.py
EMG Signal Segmentation Pipeline
Divides continuous EMG signals into fixed-length windows
"""

import pandas as pd
import numpy as np
import logging
import os
from pathlib import Path
import pickle

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SignalSegmenter:
    """
    Segments continuous EMG signals into fixed-length windows.
    Supports both sliding window and non-overlapping windows.
    """
    
    def __init__(self, window_size=512, overlap=0.5, fs=2000):
        """
        Initialize segmenter.
        
        Parameters:
        -----------
        window_size : int
            Size of each window in samples (default: 512 = 256 ms at 2000 Hz)
        overlap : float
            Overlap ratio (0-1). 0.5 = 50% overlap (default: 0.5)
        fs : float
            Sampling frequency in Hz
        """
        self.window_size = window_size
        self.overlap = overlap
        self.step_size = int(window_size * (1 - overlap))
        self.fs = fs
        
        logger.info(f"Segmenter initialized: window={window_size}, "
                   f"step={self.step_size}, overlap={overlap*100:.0f}%")
        print(f"Window configuration:")
        print(f"  - Window size: {window_size} samples ({window_size/fs*1000:.1f} ms)")
        print(f"  - Step size: {self.step_size} samples ({self.step_size/fs*1000:.1f} ms)")
        print(f"  - Overlap: {overlap*100:.0f}%")
    
    def segment_signal(self, signal, label=None):
        """
        Segment a single EMG signal into windows.
        
        Parameters:
        -----------
        signal : array-like
            Input signal (1D array)
        label : int, optional
            Label/class for this signal
        
        Returns:
        --------
        windows : ndarray
            Shape (n_windows, window_size)
        labels : ndarray
            Label for each window (if input label provided)
        """
        n_samples = len(signal)
        windows = []
        labels = []
        
        # Create sliding windows
        for start in range(0, n_samples - self.window_size + 1, self.step_size):
            end = start + self.window_size
            window = signal[start:end]
            
            if len(window) == self.window_size:  # Ensure full window
                windows.append(window)
                if label is not None:
                    labels.append(label)
        
        windows = np.array(windows)
        labels = np.array(labels) if labels else None
        
        return windows, labels
    
    def segment_multichannel(self, data, emg_channels, label_column='stimulus'):
        """
        Segment multi-channel EMG data into windows.
        
        Parameters:
        -----------
        data : pd.DataFrame
            Input data
        emg_channels : list
            Names of EMG channels
        label_column : str
            Name of label column
        
        Returns:
        --------
        windows : ndarray
            Shape (n_windows, window_size, n_channels)
        labels : ndarray
            Label for each window
        window_metadata : dict
            Metadata about windows
        """
        n_samples = len(data)
        n_channels = len(emg_channels)
        windows = []
        labels = []
        
        logger.info(f"Segmenting {n_samples} samples across {n_channels} channels")
        
        # Create sliding windows
        for start in range(0, n_samples - self.window_size + 1, self.step_size):
            end = start + self.window_size
            
            # Extract window from all channels
            window = data.iloc[start:end][emg_channels].values
            
            if window.shape[0] == self.window_size:  # Ensure full window
                windows.append(window)
                labels.append(data.iloc[start][label_column])
        
        windows = np.array(windows)
        labels = np.array(labels)
        
        # Create metadata
        metadata = {
            'n_windows': len(windows),
            'window_size': self.window_size,
            'n_channels': n_channels,
            'overlap_ratio': self.overlap,
            'n_samples_processed': n_samples,
            'unique_labels': np.unique(labels),
            'n_classes': len(np.unique(labels))
        }
        
        logger.info(f"Created {len(windows)} windows from {n_samples} samples")
        
        return windows, labels, metadata


def main():
    """
    Main signal segmentation pipeline.
    """
    print("\n" + "="*70)
    print("STEP 9: SIGNAL SEGMENTATION")
    print("="*70 + "\n")
    
    # Paths
    processed_data_path = "ml/outputs/processed_emg_data.pkl"
    output_dir = "ml/outputs"
    segmented_data_path = os.path.join(output_dir, "segmented_windows.pkl")
    metadata_path = os.path.join(output_dir, "segmentation_metadata.pkl")
    
    # Configuration
    WINDOW_SIZE = 512  # 256 ms at 2000 Hz
    OVERLAP = 0.5     # 50% overlap
    FS = 2000         # Sampling frequency
    
    try:
        # Load preprocessed data
        print("[1/3] Loading preprocessed data...")
        if not os.path.exists(processed_data_path):
            print(f"❌ Error: {processed_data_path} not found")
            print("Please run 08_preprocess_real_emg.py first")
            return
        
        with open(processed_data_path, 'rb') as f:
            data = pickle.load(f)
        
        print(f"✓ Loaded {len(data)} rows")
        logger.info(f"Loaded data shape: {data.shape}")
        
        # Detect EMG channels
        emg_channels = sorted([col for col in data.columns if col.startswith('emg_')])
        print(f"✓ EMG channels: {len(emg_channels)}")
        
        # Initialize segmenter
        print("\n[2/3] Initializing signal segmenter...")
        segmenter = SignalSegmenter(
            window_size=WINDOW_SIZE,
            overlap=OVERLAP,
            fs=FS
        )
        print(f"✓ Segmenter ready")
        
        # Segment data
        print("\n[3/3] Segmenting signals...")
        windows, labels, metadata = segmenter.segment_multichannel(
            data,
            emg_channels,
            label_column='stimulus'
        )
        
        print(f"✓ Created {len(windows)} windows")
        logger.info(f"Windows shape: {windows.shape}")
        logger.info(f"Labels shape: {labels.shape}")
        
        # Save segmented data
        print("\nSaving segmented data...")
        with open(segmented_data_path, 'wb') as f:
            pickle.dump({'windows': windows, 'labels': labels}, f)
        print(f"✓ Saved segmented windows: {segmented_data_path}")
        
        # Save metadata
        with open(metadata_path, 'wb') as f:
            pickle.dump(metadata, f)
        print(f"✓ Saved metadata: {metadata_path}")
        
        # Print segmentation summary
        print("\n" + "-"*70)
        print("SEGMENTATION SUMMARY")
        print("-"*70)
        print(f"Input samples: {metadata['n_samples_processed']}")
        print(f"Windows created: {metadata['n_windows']}")
        print(f"Window size: {metadata['window_size']} samples ({WINDOW_SIZE/FS*1000:.1f} ms)")
        print(f"Overlap ratio: {metadata['overlap_ratio']*100:.0f}%")
        print(f"Number of channels: {metadata['n_channels']}")
        print(f"Number of classes: {metadata['n_classes']}")
        print(f"Unique labels: {sorted(metadata['unique_labels'])}")
        
        print("\nClass distribution:")
        unique, counts = np.unique(labels, return_counts=True)
        for lbl, cnt in zip(unique, counts):
            pct = cnt / len(labels) * 100
            print(f"  Class {lbl:3d}: {cnt:6d} windows ({pct:5.1f}%)")
        
        print("\n" + "="*70)
        print("SEGMENTATION COMPLETE!")
        print("="*70)
        print(f"\nSegmented data saved to: {segmented_data_path}")
        print(f"Metadata saved to: {metadata_path}")
        logger.info("Segmentation pipeline completed successfully")
        
    except Exception as e:
        logger.error(f"Error in segmentation pipeline: {e}")
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
