"""Main experiment runner for pretrained EMG model evaluation.

Runs the complete experiment pipeline:
1. Load real HELLO/REST data
2. Attempt to load TinyMyo pretrained weights
3. Experiment 1: Linear probe on frozen backbone features
4. Experiment 2A: Frozen backbone + MLP head
5. Experiment 2B: Full fine-tuning
6. Compare all results against the conventional 91.6% baseline

All experiments use GroupKFold CV with trial-level splits.
"""
import sys
import json
import time
import logging
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import defaultdict

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Subset
from sklearn.model_selection import GroupKFold
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, precision_recall_fscore_support,
    confusion_matrix, classification_report,
    balanced_accuracy_score,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ml.pretrained.config import (
    RAW_DATA_DIR,
    PRETRAINED_WEIGHTS_DIR,
    FINETUNED_MODEL_DIR,
    LABEL_MAP,
    NUM_CLASSES,
    CV_N_SPLITS,
    BATCH_SIZE,
    LEARNING_RATE_HEAD,
    LEARNING_RATE_FINETUNE,
    WEIGHT_DECAY,
    NUM_EPOCHS_HEAD,
    NUM_EPOCHS_FINETUNE,
    PATIENCE,
    RANDOM_STATE,
)
from ml.pretrained.dataset import PretrainedEMGDataset
from ml.pretrained.tinymyo_model import (
    TinyMyoEncoder,
    TinyMyoClassifier,
    load_pretrained_weights,
)
from ml.pretrained.download_weights import download_weights

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

INVERSE_LABEL_MAP = {v: k for k, v in LABEL_MAP.items()}


# ---------------------------------------------------------------------------
# Experiment 1: Linear Probe on Frozen Backbone
# ---------------------------------------------------------------------------
def run_linear_probe(dataset, encoder, device):
    """Extract backbone features and train a logistic regression.

    This tests whether the pretrained representations contain
    useful information for our HELLO vs REST task.
    """
    logger.info("=" * 60)
    logger.info("EXPERIMENT 1: Linear Probe on Frozen Backbone")
    logger.info("=" * 60)

    encoder.eval()
    encoder.to(device)

    # Extract all features
    all_features = []
    all_labels = []
    with torch.no_grad():
        loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=False)
        for batch_x, batch_y, _ in loader:
            batch_x = batch_x.to(device)
            features = encoder(batch_x)  # (B, embed_dim)
            all_features.append(features.cpu().numpy())
            all_labels.append(np.array(batch_y))

    X = np.concatenate(all_features, axis=0)
    y = np.concatenate(all_labels, axis=0)
    groups = dataset.get_groups()

    logger.info(f"Feature matrix: {X.shape}, Labels: {y.shape}")
    logger.info(f"Feature stats: mean={X.mean():.4f}, std={X.std():.4f}")

    # GroupKFold cross-validation
    n_unique_groups = len(np.unique(groups))
    n_splits = min(CV_N_SPLITS, n_unique_groups)
    if n_splits < 2:
        logger.error("Not enough groups for cross-validation")
        return None

    gkf = GroupKFold(n_splits=n_splits)
    y_true_all, y_pred_all = [], []

    for fold, (train_idx, test_idx) in enumerate(gkf.split(X, y, groups)):
        clf = LogisticRegression(
            max_iter=1000, random_state=RANDOM_STATE, C=1.0
        )
        clf.fit(X[train_idx], y[train_idx])
        preds = clf.predict(X[test_idx])
        y_true_all.extend(y[test_idx])
        y_pred_all.extend(preds)
        fold_acc = accuracy_score(y[test_idx], preds)
        logger.info(f"  Fold {fold+1}/{n_splits}: accuracy={fold_acc:.4f}")

    return _compute_metrics(y_true_all, y_pred_all, "Linear Probe")


# ---------------------------------------------------------------------------
# Training loop for neural network experiments
# ---------------------------------------------------------------------------
def _train_one_epoch(model, loader, criterion, optimizer, device):
    """Train one epoch, return average loss."""
    model.train()
    total_loss = 0.0
    n_batches = 0
    for batch_x, batch_y, _ in loader:
        batch_x = batch_x.to(device)
        batch_y = batch_y.clone().detach().long().to(device)
        optimizer.zero_grad()
        logits = model(batch_x)
        loss = criterion(logits, batch_y)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
        n_batches += 1
    return total_loss / max(n_batches, 1)


def _evaluate(model, loader, device):
    """Evaluate model, return predictions and true labels."""
    model.eval()
    all_preds, all_labels = [], []
    with torch.no_grad():
        for batch_x, batch_y, _ in loader:
            batch_x = batch_x.to(device)
            logits = model(batch_x)
            preds = torch.argmax(logits, dim=1).cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(batch_y)
    return np.array(all_labels), np.array(all_preds)


def _train_and_eval_fold(
    model, train_loader, test_loader, device,
    lr, num_epochs, patience_limit, fold_num
):
    """Train model on one fold with early stopping, return test metrics."""
    criterion = nn.CrossEntropyLoss()

    # Only optimize parameters that require grad
    trainable_params = [p for p in model.parameters() if p.requires_grad]
    optimizer = optim.AdamW(trainable_params, lr=lr, weight_decay=WEIGHT_DECAY)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=num_epochs)

    best_loss = float("inf")
    patience_counter = 0
    best_state = None

    for epoch in range(num_epochs):
        train_loss = _train_one_epoch(model, train_loader, criterion, optimizer, device)
        scheduler.step()

        # Quick eval for early stopping
        model.eval()
        val_loss = 0.0
        n = 0
        with torch.no_grad():
            for batch_x, batch_y, _ in test_loader:
                batch_x = batch_x.to(device)
                batch_y = batch_y.clone().detach().long().to(device)
                logits = model(batch_x)
                val_loss += criterion(logits, batch_y).item()
                n += 1
        val_loss /= max(n, 1)

        if val_loss < best_loss:
            best_loss = val_loss
            patience_counter = 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            patience_counter += 1

        if patience_counter >= patience_limit:
            logger.info(f"    Fold {fold_num}: early stopping at epoch {epoch+1}")
            break

    # Restore best model
    if best_state is not None:
        model.load_state_dict(best_state)

    y_true, y_pred = _evaluate(model, test_loader, device)
    return y_true, y_pred


# ---------------------------------------------------------------------------
# Experiment 2A: Frozen Backbone + MLP Head
# ---------------------------------------------------------------------------
def run_frozen_backbone_mlp(dataset, checkpoint_path, device):
    """Train MLP head on frozen TinyMyo backbone features."""
    logger.info("=" * 60)
    logger.info("EXPERIMENT 2A: Frozen Backbone + MLP Head")
    logger.info("=" * 60)

    groups = dataset.get_groups()
    labels = dataset.get_labels()
    n_splits = min(CV_N_SPLITS, len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)

    y_true_all, y_pred_all = [], []

    for fold, (train_idx, test_idx) in enumerate(gkf.split(
        np.zeros(len(dataset)), labels, groups
    )):
        # Fresh model each fold
        model = TinyMyoClassifier(
            num_classes=NUM_CLASSES,
            head_type="mlp",
            freeze_backbone=True,
        )
        # Load pretrained weights into backbone
        if checkpoint_path:
            load_pretrained_weights(model.encoder, str(checkpoint_path))
        model.to(device)

        params = model.count_parameters()
        if fold == 0:
            logger.info(f"  Model params: {params}")

        train_subset = Subset(dataset, train_idx.tolist())
        test_subset = Subset(dataset, test_idx.tolist())
        train_loader = DataLoader(train_subset, batch_size=BATCH_SIZE, shuffle=True)
        test_loader = DataLoader(test_subset, batch_size=BATCH_SIZE, shuffle=False)

        y_true, y_pred = _train_and_eval_fold(
            model, train_loader, test_loader, device,
            lr=LEARNING_RATE_HEAD,
            num_epochs=NUM_EPOCHS_HEAD,
            patience_limit=PATIENCE,
            fold_num=fold + 1,
        )
        y_true_all.extend(y_true)
        y_pred_all.extend(y_pred)

        fold_acc = accuracy_score(y_true, y_pred)
        logger.info(f"  Fold {fold+1}/{n_splits}: accuracy={fold_acc:.4f}")

    return _compute_metrics(y_true_all, y_pred_all, "Frozen Backbone + MLP")


# ---------------------------------------------------------------------------
# Experiment 2B: Full Fine-Tuning
# ---------------------------------------------------------------------------
def run_full_finetune(dataset, checkpoint_path, device):
    """Fine-tune entire TinyMyo model end-to-end."""
    logger.info("=" * 60)
    logger.info("EXPERIMENT 2B: Full Fine-Tuning")
    logger.info("=" * 60)

    groups = dataset.get_groups()
    labels = dataset.get_labels()
    n_splits = min(CV_N_SPLITS, len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)

    y_true_all, y_pred_all = [], []

    for fold, (train_idx, test_idx) in enumerate(gkf.split(
        np.zeros(len(dataset)), labels, groups
    )):
        model = TinyMyoClassifier(
            num_classes=NUM_CLASSES,
            head_type="mlp",
            freeze_backbone=False,  # Full fine-tuning
        )
        if checkpoint_path:
            load_pretrained_weights(model.encoder, str(checkpoint_path))
        model.to(device)

        params = model.count_parameters()
        if fold == 0:
            logger.info(f"  Model params: {params}")

        train_subset = Subset(dataset, train_idx.tolist())
        test_subset = Subset(dataset, test_idx.tolist())
        train_loader = DataLoader(train_subset, batch_size=BATCH_SIZE, shuffle=True)
        test_loader = DataLoader(test_subset, batch_size=BATCH_SIZE, shuffle=False)

        y_true, y_pred = _train_and_eval_fold(
            model, train_loader, test_loader, device,
            lr=LEARNING_RATE_FINETUNE,
            num_epochs=NUM_EPOCHS_FINETUNE,
            patience_limit=PATIENCE,
            fold_num=fold + 1,
        )
        y_true_all.extend(y_true)
        y_pred_all.extend(y_pred)

        fold_acc = accuracy_score(y_true, y_pred)
        logger.info(f"  Fold {fold+1}/{n_splits}: accuracy={fold_acc:.4f}")

    return _compute_metrics(y_true_all, y_pred_all, "Full Fine-Tuning")


# ---------------------------------------------------------------------------
# Experiment 3: Architecture-only (no pretrained weights, random init)
# ---------------------------------------------------------------------------
def run_random_init(dataset, device):
    """Train TinyMyo architecture from scratch (random init).

    This serves as an important control: if pretrained weights help,
    this should perform worse than Experiment 2A/2B.
    """
    logger.info("=" * 60)
    logger.info("EXPERIMENT 3: Random Init (Architecture Only, No Pretraining)")
    logger.info("=" * 60)

    groups = dataset.get_groups()
    labels = dataset.get_labels()
    n_splits = min(CV_N_SPLITS, len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)

    y_true_all, y_pred_all = [], []

    for fold, (train_idx, test_idx) in enumerate(gkf.split(
        np.zeros(len(dataset)), labels, groups
    )):
        model = TinyMyoClassifier(
            num_classes=NUM_CLASSES,
            head_type="mlp",
            freeze_backbone=False,
        )
        # NO pretrained weights loaded — random initialization
        model.to(device)

        train_subset = Subset(dataset, train_idx.tolist())
        test_subset = Subset(dataset, test_idx.tolist())
        train_loader = DataLoader(train_subset, batch_size=BATCH_SIZE, shuffle=True)
        test_loader = DataLoader(test_subset, batch_size=BATCH_SIZE, shuffle=False)

        y_true, y_pred = _train_and_eval_fold(
            model, train_loader, test_loader, device,
            lr=LEARNING_RATE_FINETUNE,
            num_epochs=NUM_EPOCHS_FINETUNE,
            patience_limit=PATIENCE,
            fold_num=fold + 1,
        )
        y_true_all.extend(y_true)
        y_pred_all.extend(y_pred)

        fold_acc = accuracy_score(y_true, y_pred)
        logger.info(f"  Fold {fold+1}/{n_splits}: accuracy={fold_acc:.4f}")

    return _compute_metrics(y_true_all, y_pred_all, "Random Init (No Pretraining)")


# ---------------------------------------------------------------------------
# Metrics helper
# ---------------------------------------------------------------------------
def _compute_metrics(y_true, y_pred, experiment_name):
    """Compute and log all metrics."""
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)

    acc = accuracy_score(y_true, y_pred)
    bal_acc = balanced_accuracy_score(y_true, y_pred)
    prec, rec, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    cm = confusion_matrix(y_true, y_pred)

    # Per-class report
    target_names = [INVERSE_LABEL_MAP.get(i, str(i)) for i in sorted(LABEL_MAP.values())]
    report = classification_report(
        y_true, y_pred, target_names=target_names, output_dict=True, zero_division=0
    )

    results = {
        "experiment": experiment_name,
        "accuracy": round(float(acc), 4),
        "balanced_accuracy": round(float(bal_acc), 4),
        "precision": round(float(prec), 4),
        "recall": round(float(rec), 4),
        "f1": round(float(f1), 4),
        "confusion_matrix": cm.tolist(),
        "per_class": report,
    }

    logger.info(f"\n{'='*50}")
    logger.info(f"RESULTS: {experiment_name}")
    logger.info(f"{'='*50}")
    logger.info(f"  Accuracy:          {acc:.4f}")
    logger.info(f"  Balanced Accuracy: {bal_acc:.4f}")
    logger.info(f"  Precision:         {prec:.4f}")
    logger.info(f"  Recall:            {rec:.4f}")
    logger.info(f"  F1:                {f1:.4f}")
    logger.info(f"  Confusion Matrix:")
    logger.info(f"    {cm}")

    return results


# ---------------------------------------------------------------------------
# Inference latency measurement
# ---------------------------------------------------------------------------
def measure_inference_latency(model, device, n_runs=100):
    """Measure average inference time for a single window."""
    model.eval()
    model.to(device)

    # Single 1-channel, 1000-sample window
    dummy = torch.randn(1, 1, 1000).to(device)

    # Warmup
    with torch.no_grad():
        for _ in range(10):
            model(dummy)

    times = []
    with torch.no_grad():
        for _ in range(n_runs):
            start = time.perf_counter()
            model(dummy)
            end = time.perf_counter()
            times.append(end - start)

    avg_ms = np.mean(times) * 1000
    std_ms = np.std(times) * 1000
    return {"avg_ms": round(avg_ms, 2), "std_ms": round(std_ms, 2)}


# ---------------------------------------------------------------------------
# Main experiment orchestrator
# ---------------------------------------------------------------------------
def main():
    """Run all pretrained model experiments."""
    logger.info("=" * 70)
    logger.info("ASV PRETRAINED EMG MODEL EXPERIMENT")
    logger.info("Model: TinyMyo (arXiv:2512.15729)")
    logger.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 70)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Device: {device}")

    # Step 1: Load dataset
    logger.info("\n--- Loading Dataset ---")
    dataset = PretrainedEMGDataset(data_dir=RAW_DATA_DIR)
    summary = dataset.get_summary()
    logger.info(f"Dataset summary: {json.dumps(summary, indent=2)}")

    if summary["n_windows"] == 0:
        logger.error("No data loaded! Check RAW_DATA_DIR.")
        return

    # Step 2: Download pretrained weights
    logger.info("\n--- Downloading Pretrained Weights ---")
    checkpoint_path = download_weights()
    pretrained_available = checkpoint_path is not None

    if pretrained_available:
        import os
        size_mb = os.path.getsize(checkpoint_path) / (1024 * 1024)
        logger.info(f"Checkpoint: {checkpoint_path} ({size_mb:.1f} MB)")
    else:
        logger.warning(
            "NO PRETRAINED WEIGHTS AVAILABLE. "
            "All 'pretrained' experiments will use random initialization. "
            "This means we are testing the ARCHITECTURE only, not transfer learning."
        )

    # Step 3: Test weight loading (dry run)
    encoder = TinyMyoEncoder()
    if pretrained_available:
        success, msg = load_pretrained_weights(encoder, str(checkpoint_path))
        logger.info(f"Weight loading: success={success}, message={msg}")
        if not success:
            logger.warning(
                "Pretrained weights could not be loaded (key mismatch). "
                "Proceeding with random initialization for all experiments."
            )
            pretrained_available = False

    # Step 4: Run experiments
    all_results = {}

    # Experiment 1: Linear probe
    try:
        encoder_for_probe = TinyMyoEncoder()
        if pretrained_available:
            load_pretrained_weights(encoder_for_probe, str(checkpoint_path))
        result = run_linear_probe(dataset, encoder_for_probe, device)
        if result:
            all_results["linear_probe"] = result
    except Exception as e:
        logger.error(f"Linear probe failed: {e}", exc_info=True)

    # Experiment 2A: Frozen backbone + MLP
    try:
        result = run_frozen_backbone_mlp(
            dataset, checkpoint_path if pretrained_available else None, device
        )
        if result:
            all_results["frozen_backbone_mlp"] = result
    except Exception as e:
        logger.error(f"Frozen backbone MLP failed: {e}", exc_info=True)

    # Experiment 2B: Full fine-tuning
    try:
        result = run_full_finetune(
            dataset, checkpoint_path if pretrained_available else None, device
        )
        if result:
            all_results["full_finetune"] = result
    except Exception as e:
        logger.error(f"Full fine-tuning failed: {e}", exc_info=True)

    # Experiment 3: Random init (control)
    try:
        result = run_random_init(dataset, device)
        if result:
            all_results["random_init"] = result
    except Exception as e:
        logger.error(f"Random init failed: {e}", exc_info=True)

    # Step 5: Measure inference latency
    logger.info("\n--- Inference Latency ---")
    model_for_latency = TinyMyoClassifier(
        num_classes=NUM_CLASSES, head_type="mlp", freeze_backbone=False
    )
    latency = measure_inference_latency(model_for_latency, device)
    logger.info(f"Single window inference: {latency['avg_ms']:.2f} ± {latency['std_ms']:.2f} ms")

    # Step 6: Model size
    param_count = model_for_latency.count_parameters()
    model_size_mb = sum(
        p.numel() * p.element_size() for p in model_for_latency.parameters()
    ) / (1024 * 1024)

    # Step 7: Compile final report
    logger.info("\n" + "=" * 70)
    logger.info("FINAL COMPARISON")
    logger.info("=" * 70)

    baseline = {
        "experiment": "Conventional ML Baseline (RF/SVM)",
        "accuracy": 0.9160,
        "precision": 0.8685,
        "recall": 0.9654,
        "f1": 0.9144,
        "note": "GroupKFold CV, handcrafted features, RandomForest"
    }

    logger.info(f"\n{'Experiment':<40} {'Acc':>8} {'Prec':>8} {'Rec':>8} {'F1':>8}")
    logger.info("-" * 72)
    logger.info(
        f"{'Baseline (RF/SVM)':<40} "
        f"{baseline['accuracy']:>8.4f} "
        f"{baseline['precision']:>8.4f} "
        f"{baseline['recall']:>8.4f} "
        f"{baseline['f1']:>8.4f}"
    )
    for name, result in all_results.items():
        logger.info(
            f"{result['experiment']:<40} "
            f"{result['accuracy']:>8.4f} "
            f"{result['precision']:>8.4f} "
            f"{result['recall']:>8.4f} "
            f"{result['f1']:>8.4f}"
        )

    # Save complete report
    report = {
        "timestamp": datetime.now().isoformat(),
        "model": "TinyMyo",
        "paper": "arXiv:2512.15729",
        "pretrained_weights_loaded": pretrained_available,
        "device": str(device),
        "dataset": summary,
        "baseline": baseline,
        "experiments": all_results,
        "inference_latency": latency,
        "model_parameters": param_count,
        "model_size_mb": round(model_size_mb, 2),
        "cv_method": "GroupKFold",
        "cv_splits": min(CV_N_SPLITS, summary.get("n_trials", 0) // 2),
        "leakage_prevention": "Trial-level splits — all windows from one trial in same fold",
        "compatibility_notes": {
            "sampling_rate": "Resampled 475 Hz → 2000 Hz (interpolation, no new information)",
            "channels": "1 channel (model designed for 16, channel-independent tokenization allows 1)",
            "window_size": "1000 samples at 2kHz = 500ms",
            "limitation": "Single channel means no cross-channel spatial information available",
        },
    }

    FINETUNED_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    report_path = FINETUNED_MODEL_DIR / "experiment_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"\nFull report saved to: {report_path}")

    return report


if __name__ == "__main__":
    main()
