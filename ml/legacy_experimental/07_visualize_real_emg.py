"""
07_visualize_real_emg.py
Professional EMG Signal Visualization
Visualizes raw EMG channels from NinaPro DB1 dataset
"""

import pandas as pd
import numpy as np
import logging
import os
from pathlib import Path

# Import visualization utilities
from ml.utils.visualization import (
    plot_raw_emg_channels,
    plot_signal_spectrum
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """
    Main visualization pipeline for real EMG data.
    """
    print("\n" + "="*70)
    print("STEP 7: REAL EMG SIGNAL VISUALIZATION")
    print("="*70 + "\n")
    
    # Paths
    data_path = "datasets/ninapro_db1/Ninapro_DB1.csv"
    output_dir = "ml/outputs/visualizations"
    
    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")
    
    try:
        # Load data in chunks to handle large dataset
        print("[1/4] Loading NinaPro DB1 dataset...")
        logger.info(f"Reading {data_path}...")
        
        # Read first part for visualization
        df_sample = pd.read_csv(data_path, nrows=50000, low_memory=False)
        logger.info(f"Loaded sample: {df_sample.shape}")
        print(f"✓ Loaded {len(df_sample)} rows")
        
        # Detect EMG channels
        emg_channels = sorted([col for col in df_sample.columns if col.startswith('emg_')])
        n_channels = len(emg_channels)
        print(f"✓ Detected {n_channels} EMG channels: {emg_channels}")
        logger.info(f"EMG channels: {emg_channels}")
        
        # Extract EMG data
        emg_data = df_sample[emg_channels].values
        fs = 2000  # Sampling frequency (Hz)
        duration = len(emg_data) / fs
        print(f"✓ Signal duration: {duration:.2f} seconds")
        
        # Visualization 1: Raw EMG channels (full sample)
        print("\n[2/4] Plotting raw EMG channels...")
        fig_path_1 = os.path.join(output_dir, "01_raw_emg_channels.png")
        plot_raw_emg_channels(
            emg_data,
            fs=fs,
            title="Raw EMG Signals - NinaPro DB1",
            save_path=fig_path_1,
            duration=10  # Show first 10 seconds
        )
        print(f"✓ Saved: {fig_path_1}")
        logger.info(f"Saved visualization: {fig_path_1}")
        
        # Visualization 2: EMG channels with longer duration
        print("\n[3/4] Plotting EMG channels (extended view)...")
        fig_path_2 = os.path.join(output_dir, "02_raw_emg_extended.png")
        plot_raw_emg_channels(
            emg_data,
            fs=fs,
            title="Raw EMG Signals - Extended View (First 30 seconds)",
            save_path=fig_path_2,
            duration=30
        )
        print(f"✓ Saved: {fig_path_2}")
        logger.info(f"Saved visualization: {fig_path_2}")
        
        # Visualization 3: Signal spectrum for each channel
        print("\n[4/4] Plotting frequency spectrum...")
        output_spectrum_dir = os.path.join(output_dir, "spectrum")
        Path(output_spectrum_dir).mkdir(parents=True, exist_ok=True)
        
        for ch_idx, ch_name in enumerate(emg_channels[:3]):  # Show first 3 channels
            channel_data = emg_data[:10000, ch_idx]  # Use first 10000 samples
            fig_path_spectrum = os.path.join(output_spectrum_dir, f"channel_{ch_idx}_spectrum.png")
            
            plot_signal_spectrum(
                channel_data,
                fs=fs,
                title=f"Frequency Spectrum - {ch_name}",
                save_path=fig_path_spectrum
            )
            print(f"  ✓ Saved spectrum for {ch_name}")
        
        logger.info(f"Saved spectrum plots to {output_spectrum_dir}")
        
        # Print data statistics
        print("\n" + "-"*70)
        print("DATA STATISTICS")
        print("-"*70)
        print(f"Dataset shape: {df_sample.shape}")
        print(f"EMG channels: {n_channels}")
        print(f"Sampling frequency: {fs} Hz")
        print(f"Total duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
        print(f"Labels (stimulus): {df_sample['stimulus'].unique()}")
        print(f"Number of unique movements: {df_sample['stimulus'].nunique()}")
        
        # EMG statistics per channel
        print("\nEMG Signal Statistics (first 50,000 samples):")
        print("-"*70)
        for ch_name in emg_channels:
            ch_data = df_sample[ch_name].values
            print(f"{ch_name:10s}: "
                  f"Mean={ch_data.mean():8.2f}, "
                  f"Std={ch_data.std():8.2f}, "
                  f"Min={ch_data.min():8.2f}, "
                  f"Max={ch_data.max():8.2f}")
        
        print("\n" + "="*70)
        print("VISUALIZATION COMPLETE!")
        print("="*70)
        print(f"\nOutput files saved to: {output_dir}/")
        logger.info("Visualization pipeline completed successfully")
        
    except Exception as e:
        logger.error(f"Error in visualization pipeline: {e}")
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
