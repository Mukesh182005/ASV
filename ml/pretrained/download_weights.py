"""Download TinyMyo pretrained weights from HuggingFace.

Downloads the official model checkpoint to ml/models/pretrained/tinymyo/.
If the download fails or the model is gated, falls back to random init.
"""
import os
import logging
from pathlib import Path

from ml.pretrained.config import PRETRAINED_WEIGHTS_DIR, HF_REPO_ID

logger = logging.getLogger(__name__)


def download_weights(force: bool = False) -> Path:
    """Download TinyMyo pretrained weights.

    Returns the path to the downloaded checkpoint file,
    or None if download failed.
    """
    PRETRAINED_WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    # Check for any existing checkpoint in target dir or subdirs
    for path_candidate in [
        PRETRAINED_WEIGHTS_DIR / "pretraining" / "TinyMyo" / "TinyMyo.safetensors",
        PRETRAINED_WEIGHTS_DIR / "TinyMyo.safetensors",
    ]:
        if path_candidate.exists() and not force:
            logger.info(f"Using existing checkpoint: {path_candidate}")
            return path_candidate

    # Try HuggingFace hub download
    try:
        from huggingface_hub import hf_hub_download
        logger.info(f"Downloading TinyMyo weights from {HF_REPO_ID} ({HF_CHECKPOINT_FILENAME})...")

        try:
            path = hf_hub_download(
                repo_id=HF_REPO_ID,
                filename=HF_CHECKPOINT_FILENAME,
                local_dir=str(PRETRAINED_WEIGHTS_DIR),
            )
            # Also download config.json
            try:
                hf_hub_download(
                    repo_id=HF_REPO_ID,
                    filename=HF_CONFIG_FILENAME,
                    local_dir=str(PRETRAINED_WEIGHTS_DIR),
                )
            except Exception:
                pass

            logger.info(f"Downloaded checkpoint to: {path}")
            return Path(path)
        except Exception as e1:
            logger.error(f"Checkpoint download failed: {e1}")
            return None

    except ImportError:
        logger.warning("huggingface_hub not installed. pip install huggingface-hub")

    logger.warning(
        "Could not download pretrained weights. "
        "The model will use RANDOM INITIALIZATION. "
        "Results will reflect the architecture's capacity, not pretrained features."
    )
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = download_weights(force=True)
    if result:
        size_mb = os.path.getsize(result) / (1024 * 1024)
        print(f"✓ Checkpoint ready: {result} ({size_mb:.1f} MB)")
    else:
        print("✗ No checkpoint downloaded — model will use random init")
