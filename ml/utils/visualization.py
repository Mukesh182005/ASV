"""
EMG Signal Visualization Utilities
Creates professional biomedical-style plots for EMG data
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib import rcParams
import seaborn as sns
import logging

logger = logging.getLogger(__name__)

# Set professional plotting style
rcParams['figure.figsize'] = (14, 8)
rcParams['font.size'] = 10
rcParams['lines.linewidth'] = 1.5
rcParams['axes.linewidth'] = 1.5
sns.set_style("whitegrid")
sns.set_palette("husl")


def plot_raw_emg_channels(emg_data, fs=2000, title="Raw EMG Signals", 
                          save_path=None, duration=None):
    """
    Plot all EMG channels in a professional grid layout.
    
    Parameters:
    -----------
    emg_data : ndarray
        EMG data with shape (n_samples, n_channels)
    fs : float
        Sampling frequency (Hz, default: 2000)
    title : str
        Plot title
    save_path : str, optional
        Path to save figure
    duration : float, optional
        Duration of signal in seconds to display (None = all)
    
    Returns:
    --------
    fig : matplotlib.figure.Figure
        The figure object
    """
    try:
        if emg_data.ndim == 1:
            emg_data = emg_data.reshape(-1, 1)
        
        n_channels = emg_data.shape[1]
        
        # Limit data for display
        if duration is not None:
            max_samples = int(duration * fs)
            emg_data = emg_data[:max_samples, :]
        
        # Create time vector
        time = np.arange(emg_data.shape[0]) / fs
        
        # Create subplots
        n_rows = int(np.ceil(n_channels / 2))
        fig, axes = plt.subplots(n_rows, 2, figsize=(14, 3 * n_rows))
        
        if n_rows == 1 and n_channels == 1:
            axes = np.array([axes])
        elif n_rows == 1:
            axes = axes.reshape(1, -1)
        
        axes_flat = axes.flatten()
        
        # Plot each channel
        colors = sns.color_palette("husl", n_channels)
        for ch in range(n_channels):
            ax = axes_flat[ch]
            ax.plot(time, emg_data[:, ch], color=colors[ch], linewidth=1, alpha=0.8)
            ax.set_xlabel('Time (s)', fontsize=10)
            ax.set_ylabel(f'EMG Ch-{ch} (μV)', fontsize=10)
            ax.set_title(f'Channel {ch}', fontsize=11, fontweight='bold')
            ax.grid(True, alpha=0.3)
            ax.set_xlim([time[0], time[-1]])
        
        # Hide unused subplots
        for ch in range(n_channels, len(axes_flat)):
            axes_flat[ch].set_visible(False)
        
        fig.suptitle(title, fontsize=14, fontweight='bold', y=1.00)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Figure saved: {save_path}")
        
        return fig
        
    except Exception as e:
        logger.error(f"Error plotting EMG channels: {e}")
        raise


def plot_filtered_comparison(raw_signal, filtered_signal, fs=2000, 
                             channel_name="EMG Channel", save_path=None):
    """
    Plot raw vs filtered signal comparison.
    
    Parameters:
    -----------
    raw_signal : array-like
        Original signal
    filtered_signal : array-like
        Filtered signal
    fs : float
        Sampling frequency (Hz)
    channel_name : str
        Name of the channel
    save_path : str, optional
        Path to save figure
    
    Returns:
    --------
    fig : matplotlib.figure.Figure
        The figure object
    """
    try:
        fig, axes = plt.subplots(3, 1, figsize=(14, 10))
        
        time = np.arange(len(raw_signal)) / fs
        
        # Raw signal
        axes[0].plot(time, raw_signal, color='#e74c3c', linewidth=1, alpha=0.7)
        axes[0].set_ylabel('Amplitude (μV)', fontsize=10)
        axes[0].set_title(f'{channel_name} - Raw Signal', fontsize=11, fontweight='bold')
        axes[0].grid(True, alpha=0.3)
        
        # Filtered signal
        axes[1].plot(time, filtered_signal, color='#3498db', linewidth=1, alpha=0.7)
        axes[1].set_ylabel('Amplitude (μV)', fontsize=10)
        axes[1].set_title(f'{channel_name} - Filtered Signal', fontsize=11, fontweight='bold')
        axes[1].grid(True, alpha=0.3)
        
        # Difference
        diff = raw_signal - filtered_signal
        axes[2].plot(time, diff, color='#2ecc71', linewidth=1, alpha=0.7)
        axes[2].set_ylabel('Amplitude (μV)', fontsize=10)
        axes[2].set_xlabel('Time (s)', fontsize=10)
        axes[2].set_title(f'{channel_name} - Noise (Raw - Filtered)', fontsize=11, fontweight='bold')
        axes[2].grid(True, alpha=0.3)
        
        fig.suptitle('Raw vs Filtered Signal Comparison', fontsize=13, fontweight='bold')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Figure saved: {save_path}")
        
        return fig
        
    except Exception as e:
        logger.error(f"Error plotting comparison: {e}")
        raise


def plot_features_distribution(features_df, save_path=None):
    """
    Plot distribution of extracted features.
    
    Parameters:
    -----------
    features_df : pandas.DataFrame
        DataFrame with extracted features
    save_path : str, optional
        Path to save figure
    
    Returns:
    --------
    fig : matplotlib.figure.Figure
        The figure object
    """
    try:
        # Select only numeric columns
        numeric_cols = features_df.select_dtypes(include=[np.number]).columns
        n_features = len(numeric_cols)
        
        n_cols = 3
        n_rows = int(np.ceil(n_features / n_cols))
        
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(15, 4 * n_rows))
        axes_flat = axes.flatten()
        
        for idx, feature in enumerate(numeric_cols):
            ax = axes_flat[idx]
            
            # Plot histogram with KDE
            ax.hist(features_df[feature], bins=50, alpha=0.7, color='#3498db', edgecolor='black')
            ax.set_xlabel('Value', fontsize=10)
            ax.set_ylabel('Frequency', fontsize=10)
            ax.set_title(f'{feature} Distribution', fontsize=11, fontweight='bold')
            ax.grid(True, alpha=0.3, axis='y')
        
        # Hide unused subplots
        for idx in range(n_features, len(axes_flat)):
            axes_flat[idx].set_visible(False)
        
        fig.suptitle('Feature Distributions', fontsize=13, fontweight='bold')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Figure saved: {save_path}")
        
        return fig
        
    except Exception as e:
        logger.error(f"Error plotting feature distributions: {e}")
        raise


def plot_confusion_matrix(cm, class_names, save_path=None, normalize=True):
    """
    Plot confusion matrix as heatmap.
    
    Parameters:
    -----------
    cm : ndarray
        Confusion matrix
    class_names : list
        Names of classes
    save_path : str, optional
        Path to save figure
    normalize : bool
        Whether to normalize the matrix
    
    Returns:
    --------
    fig : matplotlib.figure.Figure
        The figure object
    """
    try:
        if normalize:
            cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
            title = 'Normalized Confusion Matrix'
        else:
            title = 'Confusion Matrix'
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        im = ax.imshow(cm, interpolation='nearest', cmap='Blues')
        
        # Add colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Count', rotation=270, labelpad=20)
        
        # Set ticks and labels
        tick_marks = np.arange(len(class_names))
        ax.set_xticks(tick_marks)
        ax.set_yticks(tick_marks)
        ax.set_xticklabels(class_names, rotation=45, ha='right')
        ax.set_yticklabels(class_names)
        
        # Add text annotations
        thresh = cm.max() / 2.
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                if normalize:
                    ax.text(j, i, f'{cm[i, j]:.2f}',
                           ha="center", va="center",
                           color="white" if cm[i, j] > thresh else "black",
                           fontsize=10, fontweight='bold')
                else:
                    ax.text(j, i, f'{int(cm[i, j])}',
                           ha="center", va="center",
                           color="white" if cm[i, j] > thresh else "black",
                           fontsize=10, fontweight='bold')
        
        ax.set_ylabel('True Label', fontsize=11, fontweight='bold')
        ax.set_xlabel('Predicted Label', fontsize=11, fontweight='bold')
        ax.set_title(title, fontsize=12, fontweight='bold', pad=20)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Figure saved: {save_path}")
        
        return fig
        
    except Exception as e:
        logger.error(f"Error plotting confusion matrix: {e}")
        raise


def plot_model_comparison(models_data, save_path=None):
    """
    Plot comparison of different models.
    
    Parameters:
    -----------
    models_data : dict
        Dictionary with model names as keys and metrics as values
        e.g., {'RF': {'accuracy': 0.95, 'precision': 0.94, ...}, ...}
    save_path : str, optional
        Path to save figure
    
    Returns:
    --------
    fig : matplotlib.figure.Figure
        The figure object
    """
    try:
        metrics = ['accuracy', 'precision', 'recall', 'f1']
        model_names = list(models_data.keys())
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        x = np.arange(len(model_names))
        width = 0.2
        
        for idx, metric in enumerate(metrics):
            values = [models_data[model].get(metric, 0) for model in model_names]
            ax.bar(x + idx * width, values, width, label=metric.capitalize())
        
        ax.set_xlabel('Models', fontsize=11, fontweight='bold')
        ax.set_ylabel('Score', fontsize=11, fontweight='bold')
        ax.set_title('Model Performance Comparison', fontsize=12, fontweight='bold')
        ax.set_xticks(x + width * 1.5)
        ax.set_xticklabels(model_names)
        ax.legend(loc='lower right')
        ax.grid(True, alpha=0.3, axis='y')
        ax.set_ylim([0, 1.05])
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Figure saved: {save_path}")
        
        return fig
        
    except Exception as e:
        logger.error(f"Error plotting model comparison: {e}")
        raise


def plot_signal_spectrum(signal_data, fs=2000, title="Signal Spectrum", 
                        save_path=None):
    """
    Plot signal power spectrum (FFT).
    
    Parameters:
    -----------
    signal_data : array-like
        Input signal
    fs : float
        Sampling frequency (Hz)
    title : str
        Plot title
    save_path : str, optional
        Path to save figure
    
    Returns:
    --------
    fig : matplotlib.figure.Figure
        The figure object
    """
    try:
        # Compute FFT
        fft_vals = np.abs(np.fft.fft(signal_data))
        freqs = np.fft.fftfreq(len(signal_data), 1 / fs)
        
        # Use only positive frequencies
        positive_freqs = freqs[:len(freqs) // 2]
        positive_fft = fft_vals[:len(fft_vals) // 2]
        
        fig, ax = plt.subplots(figsize=(12, 5))
        
        ax.semilogy(positive_freqs, positive_fft, color='#3498db', linewidth=1.5)
        ax.set_xlabel('Frequency (Hz)', fontsize=11, fontweight='bold')
        ax.set_ylabel('Power', fontsize=11, fontweight='bold')
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.set_xlim([0, min(500, positive_freqs[-1])])  # EMG typically up to 500 Hz
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Figure saved: {save_path}")
        
        return fig
        
    except Exception as e:
        logger.error(f"Error plotting spectrum: {e}")
        raise
