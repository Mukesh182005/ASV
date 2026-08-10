"""
EMG Data Preprocessing Utilities
Handles data loading, cleaning, and normalization
"""

import numpy as np
import pandas as pd
import logging
from sklearn.preprocessing import StandardScaler, MinMaxScaler
import os

logger = logging.getLogger(__name__)


class EMGPreprocessor:
    """
    Professional EMG data preprocessing class.
    Handles loading, cleaning, and normalization of EMG datasets.
    """
    
    def __init__(self, emg_channels=None, label_column='stimulus'):
        """
        Initialize preprocessor.
        
        Parameters:
        -----------
        emg_channels : list, optional
            List of EMG channel column names (default: auto-detect emg_0 to emg_9)
        label_column : str
            Name of the label column (default: 'stimulus')
        """
        self.emg_channels = emg_channels
        self.label_column = label_column
        self.scaler = None
        self.n_channels = None
        logger.info(f"EMGPreprocessor initialized with label_column='{label_column}'")
    
    def load_data(self, filepath, chunksize=None):
        """
        Load EMG data from CSV file.
        
        Parameters:
        -----------
        filepath : str
            Path to CSV file
        chunksize : int, optional
            If specified, load data in chunks for memory efficiency
        
        Returns:
        --------
        data : pd.DataFrame or iterator
            Loaded data
        """
        try:
            logger.info(f"Loading data from {filepath}...")
            
            if chunksize is None:
                data = pd.read_csv(filepath, low_memory=False)
                logger.info(f"Loaded {len(data)} rows, {len(data.columns)} columns")
            else:
                data = pd.read_csv(filepath, chunksize=chunksize, low_memory=False)
                logger.info(f"Created chunk iterator with chunksize={chunksize}")
            
            return data
            
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            raise
    
    def detect_emg_channels(self, data):
        """
        Auto-detect EMG channels in dataset.
        
        Looks for columns named 'emg_0', 'emg_1', etc.
        
        Parameters:
        -----------
        data : pd.DataFrame
            Input data
        
        Returns:
        --------
        emg_channels : list
            List of detected EMG channel names
        """
        try:
            detected = [col for col in data.columns if col.startswith('emg_')]
            detected.sort()
            
            if not detected:
                logger.warning("No EMG channels detected (emg_* pattern not found)")
                return []
            
            logger.info(f"Detected {len(detected)} EMG channels: {detected}")
            self.emg_channels = detected
            self.n_channels = len(detected)
            
            return detected
            
        except Exception as e:
            logger.error(f"Error detecting channels: {e}")
            raise
    
    def remove_unnecessary_columns(self, data, keep_columns=None):
        """
        Remove unnecessary columns, keeping only EMG and label data.
        
        Parameters:
        -----------
        data : pd.DataFrame
            Input data
        keep_columns : list, optional
            Additional columns to keep (e.g., subject, repetition)
        
        Returns:
        --------
        data_clean : pd.DataFrame
            Cleaned data
        """
        try:
            if self.emg_channels is None:
                self.detect_emg_channels(data)
            
            # Columns to keep
            columns_to_keep = self.emg_channels + [self.label_column]
            
            if keep_columns:
                columns_to_keep.extend(keep_columns)
            
            # Filter to keep only valid columns
            valid_columns = [col for col in columns_to_keep if col in data.columns]
            
            data_clean = data[valid_columns].copy()
            
            logger.info(f"Removed columns. Kept {len(valid_columns)} columns")
            
            return data_clean
            
        except Exception as e:
            logger.error(f"Error removing columns: {e}")
            raise
    
    def handle_missing_values(self, data, method='forward_fill'):
        """
        Handle missing values in data.
        
        Parameters:
        -----------
        data : pd.DataFrame
            Input data with possible NaN values
        method : str
            Method to handle missing values:
            - 'forward_fill': Forward fill
            - 'backward_fill': Backward fill
            - 'interpolate': Linear interpolation
            - 'drop': Drop rows with NaN
        
        Returns:
        --------
        data_clean : pd.DataFrame
            Data with missing values handled
        """
        try:
            n_missing = data.isna().sum().sum()
            
            if n_missing == 0:
                logger.info("No missing values found")
                return data
            
            logger.info(f"Found {n_missing} missing values")
            
            if method == 'forward_fill':
                data_clean = data.fillna(method='ffill')
            elif method == 'backward_fill':
                data_clean = data.fillna(method='bfill')
            elif method == 'interpolate':
                data_clean = data.interpolate(method='linear')
            elif method == 'drop':
                data_clean = data.dropna()
            else:
                raise ValueError(f"Unknown method: {method}")
            
            remaining_missing = data_clean.isna().sum().sum()
            logger.info(f"Handled missing values. Remaining: {remaining_missing}")
            
            return data_clean
            
        except Exception as e:
            logger.error(f"Error handling missing values: {e}")
            raise
    
    def normalize_signals(self, data, method='standard', fit=False):
        """
        Normalize EMG signals.
        
        Parameters:
        -----------
        data : pd.DataFrame or ndarray
            Input data (EMG channels only)
        method : str
            Normalization method:
            - 'standard': Standardization (z-score)
            - 'minmax': Min-Max scaling to [0, 1]
        fit : bool
            If True, fit the scaler on data. If False, use existing scaler.
        
        Returns:
        --------
        data_normalized : pd.DataFrame or ndarray
            Normalized data
        """
        try:
            is_dataframe = isinstance(data, pd.DataFrame)
            
            if is_dataframe:
                emg_data = data[self.emg_channels].values
                labels = data[[self.label_column]]
            else:
                emg_data = data
            
            if method == 'standard':
                if fit or self.scaler is None:
                    self.scaler = StandardScaler()
                    emg_normalized = self.scaler.fit_transform(emg_data)
                else:
                    emg_normalized = self.scaler.transform(emg_data)
            
            elif method == 'minmax':
                if fit or self.scaler is None:
                    self.scaler = MinMaxScaler()
                    emg_normalized = self.scaler.fit_transform(emg_data)
                else:
                    emg_normalized = self.scaler.transform(emg_data)
            else:
                raise ValueError(f"Unknown method: {method}")
            
            if is_dataframe:
                # Reconstruct dataframe
                data_normalized = pd.DataFrame(emg_normalized, columns=self.emg_channels)
                data_normalized[self.label_column] = labels.values
                return data_normalized
            else:
                return emg_normalized
                
        except Exception as e:
            logger.error(f"Error normalizing signals: {e}")
            raise
    
    def remove_outliers(self, data, method='iqr', threshold=3):
        """
        Remove outliers from EMG signals.
        
        Parameters:
        -----------
        data : pd.DataFrame
            Input data
        method : str
            Method to detect outliers:
            - 'iqr': Interquartile range
            - 'zscore': Z-score based
        threshold : float
            Threshold for outlier detection
        
        Returns:
        --------
        data_clean : pd.DataFrame
            Data with outliers removed
        """
        try:
            if method == 'iqr':
                Q1 = data[self.emg_channels].quantile(0.25)
                Q3 = data[self.emg_channels].quantile(0.75)
                IQR = Q3 - Q1
                
                mask = ~((data[self.emg_channels] < (Q1 - threshold * IQR)) |
                        (data[self.emg_channels] > (Q3 + threshold * IQR))).any(axis=1)
            
            elif method == 'zscore':
                from scipy import stats
                z_scores = np.abs(stats.zscore(data[self.emg_channels]))
                mask = (z_scores < threshold).all(axis=1)
            
            else:
                raise ValueError(f"Unknown method: {method}")
            
            data_clean = data[mask].copy()
            n_removed = len(data) - len(data_clean)
            logger.info(f"Removed {n_removed} outliers ({n_removed/len(data)*100:.2f}%)")
            
            return data_clean
            
        except Exception as e:
            logger.error(f"Error removing outliers: {e}")
            raise
    
    def prepare_data(self, filepath, remove_outliers_flag=False, 
                    normalize_flag=True, chunksize=None):
        """
        Complete preprocessing pipeline.
        
        Parameters:
        -----------
        filepath : str
            Path to raw data CSV
        remove_outliers_flag : bool
            Whether to remove outliers
        normalize_flag : bool
            Whether to normalize signals
        chunksize : int, optional
            Process data in chunks for memory efficiency
        
        Returns:
        --------
        data_processed : pd.DataFrame
            Processed data ready for feature extraction
        """
        try:
            logger.info("="*60)
            logger.info("Starting complete preprocessing pipeline...")
            logger.info("="*60)
            
            # Load data
            data = self.load_data(filepath, chunksize=chunksize)
            
            # If chunked, process each chunk and concatenate
            if chunksize is not None:
                chunks = []
                for idx, chunk in enumerate(data):
                    if idx % 10 == 0:
                        logger.info(f"Processing chunk {idx}...")
                    
                    # Detect channels on first chunk
                    if idx == 0:
                        self.detect_emg_channels(chunk)
                    
                    # Clean
                    chunk_clean = self.remove_unnecessary_columns(chunk)
                    chunk_clean = self.handle_missing_values(chunk_clean)
                    
                    # Remove outliers
                    if remove_outliers_flag:
                        chunk_clean = self.remove_outliers(chunk_clean)
                    
                    # Normalize
                    if normalize_flag:
                        chunk_clean = self.normalize_signals(chunk_clean, fit=(idx==0))
                    
                    chunks.append(chunk_clean)
                
                data_processed = pd.concat(chunks, ignore_index=True)
            else:
                # Detect channels
                self.detect_emg_channels(data)
                
                # Clean
                data_processed = self.remove_unnecessary_columns(data)
                data_processed = self.handle_missing_values(data_processed)
                
                # Remove outliers
                if remove_outliers_flag:
                    data_processed = self.remove_outliers(data_processed)
                
                # Normalize
                if normalize_flag:
                    data_processed = self.normalize_signals(data_processed, fit=True)
            
            logger.info("="*60)
            logger.info(f"Preprocessing complete! Final shape: {data_processed.shape}")
            logger.info("="*60)
            
            return data_processed
            
        except Exception as e:
            logger.error(f"Error in preprocessing pipeline: {e}")
            raise


def extract_emg_channels(data, emg_prefix='emg_'):
    """
    Extract EMG channels from dataframe.
    
    Parameters:
    -----------
    data : pd.DataFrame
        Input data
    emg_prefix : str
        Prefix of EMG channel names
    
    Returns:
    --------
    emg_data : ndarray
        EMG data with shape (n_samples, n_channels)
    channel_names : list
        Names of EMG channels
    """
    channel_names = sorted([col for col in data.columns if col.startswith(emg_prefix)])
    emg_data = data[channel_names].values
    return emg_data, channel_names
