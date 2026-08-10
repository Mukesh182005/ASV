"""
12_evaluate_model.py
Model Evaluation and Visualization Pipeline
Generates comprehensive evaluation metrics and visualizations
"""

import pandas as pd
import numpy as np
import logging
import os
from pathlib import Path
import pickle
import matplotlib.pyplot as plt

from sklearn.metrics import confusion_matrix

from ml.utils.visualization import (
    plot_confusion_matrix,
    plot_model_comparison,
    plot_features_distribution
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """
    Main model evaluation pipeline.
    """
    print("\n" + "="*70)
    print("STEP 12: MODEL EVALUATION & VISUALIZATION")
    print("="*70 + "\n")
    
    # Paths
    results_path = "ml/outputs/training_results.pkl"
    features_path = "ml/outputs/extracted_features.pkl"
    output_dir = "ml/outputs/visualizations"
    eval_report_path = "ml/outputs/evaluation_report.txt"
    
    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    try:
        # Load results
        print("[1/5] Loading training results...")
        if not os.path.exists(results_path):
            print(f"❌ Error: {results_path} not found")
            print("Please run 11_train_real_model.py first")
            return
        
        with open(results_path, 'rb') as f:
            results_data = pickle.load(f)
        
        results = results_data['results']
        best_model_name = results_data['best_model']
        X_test = results_data['X_test']
        y_test = results_data['y_test']
        
        print(f"✓ Loaded results for {len(results)} models")
        logger.info(f"Loaded training results: {list(results.keys())}")
        
        # Load features for distribution visualization
        print("\n[2/5] Loading feature distributions...")
        with open(features_path, 'rb') as f:
            df_features = pickle.load(f)
        
        print(f"✓ Loaded features: {df_features.shape}")
        
        # Generate confusion matrices for all models
        print("\n[3/5] Generating confusion matrices...")
        
        for model_name, result in results.items():
            cm = result['confusion_matrix']
            unique_labels = sorted(np.unique(y_test))
            
            # Create confusion matrix visualization
            fig_path = os.path.join(output_dir, f"confusion_matrix_{model_name.replace(' ', '_')}.png")
            
            plot_confusion_matrix(
                cm,
                class_names=[str(i) for i in unique_labels],
                save_path=fig_path,
                normalize=True
            )
            print(f"  ✓ Saved: {model_name}")
        
        # Generate model comparison chart
        print("\n[4/5] Generating model comparison chart...")
        
        models_data = {}
        for model_name, result in results.items():
            models_data[model_name] = {
                'accuracy': result['accuracy'],
                'precision': result['precision'],
                'recall': result['recall'],
                'f1': result['f1']
            }
        
        comparison_path = os.path.join(output_dir, "model_comparison.png")
        plot_model_comparison(models_data, save_path=comparison_path)
        print(f"✓ Saved: {comparison_path}")
        
        # Generate feature distributions
        print("\n[5/5] Generating feature distributions...")
        features_dist_path = os.path.join(output_dir, "feature_distributions.png")
        plot_features_distribution(df_features.drop('label', axis=1), 
                                  save_path=features_dist_path)
        print(f"✓ Saved: {features_dist_path}")
        
        # Generate detailed evaluation report
        print("\nGenerating evaluation report...")
        
        report_lines = []
        report_lines.append("="*70)
        report_lines.append("EMG CLASSIFICATION MODEL EVALUATION REPORT")
        report_lines.append("="*70)
        report_lines.append("")
        
        report_lines.append("1. DATASET INFORMATION")
        report_lines.append("-"*70)
        report_lines.append(f"Total samples: {len(df_features)}")
        report_lines.append(f"Training set: {len(X_test) / 0.2:.0f} samples")
        report_lines.append(f"Test set: {len(X_test)} samples")
        report_lines.append(f"Number of classes: {len(np.unique(y_test))}")
        report_lines.append(f"Number of features: {X_test.shape[1]}")
        report_lines.append("")
        
        report_lines.append("2. MODEL PERFORMANCE")
        report_lines.append("-"*70)
        report_lines.append(f"{'Model':<20s} {'Accuracy':<12s} {'Precision':<12s} "
                           f"{'Recall':<12s} {'F1-Score':<12s} {'Time (s)':<10s}")
        report_lines.append("-"*70)
        
        for model_name in sorted(results.keys()):
            r = results[model_name]
            report_lines.append(f"{model_name:<20s} {r['accuracy']:<12.4f} "
                              f"{r['precision']:<12.4f} {r['recall']:<12.4f} "
                              f"{r['f1']:<12.4f} {r['train_time']:<10.2f}")
        
        report_lines.append("")
        report_lines.append("3. BEST MODEL SUMMARY")
        report_lines.append("-"*70)
        best_result = results[best_model_name]
        report_lines.append(f"Model Name: {best_model_name}")
        report_lines.append(f"Test Accuracy: {best_result['accuracy']:.4f}")
        report_lines.append(f"Test Precision: {best_result['precision']:.4f}")
        report_lines.append(f"Test Recall: {best_result['recall']:.4f}")
        report_lines.append(f"Test F1-Score: {best_result['f1']:.4f}")
        report_lines.append(f"Training Time: {best_result['train_time']:.2f} seconds")
        report_lines.append("")
        
        report_lines.append("4. CLASSIFICATION REPORT (BEST MODEL)")
        report_lines.append("-"*70)
        report_lines.append(best_result['classification_report'])
        report_lines.append("")
        
        report_lines.append("5. CLASS DISTRIBUTION IN TEST SET")
        report_lines.append("-"*70)
        unique_labels = np.unique(y_test)
        for label in unique_labels:
            count = (y_test == label).sum()
            pct = count / len(y_test) * 100
            report_lines.append(f"Class {label}: {count:5d} samples ({pct:5.1f}%)")
        report_lines.append("")
        
        report_lines.append("6. CONFUSION MATRIX (BEST MODEL)")
        report_lines.append("-"*70)
        cm = best_result['confusion_matrix']
        report_lines.append("Rows = True labels, Columns = Predicted labels")
        report_lines.append("")
        
        # Format confusion matrix
        header = "       " + "  ".join(f"{i:5d}" for i in unique_labels)
        report_lines.append(header)
        for i, row in enumerate(cm):
            row_str = f"{unique_labels[i]:5d}  " + "  ".join(f"{val:5d}" for val in row)
            report_lines.append(row_str)
        
        report_lines.append("")
        report_lines.append("="*70)
        report_lines.append("END OF REPORT")
        report_lines.append("="*70)
        
        # Save report
        report_text = "\n".join(report_lines)
        with open(eval_report_path, 'w') as f:
            f.write(report_text)
        
        print(f"✓ Saved report: {eval_report_path}")
        logger.info(f"Evaluation report saved: {eval_report_path}")
        
        # Print summary
        print("\n" + "="*70)
        print("EVALUATION SUMMARY")
        print("="*70)
        print(f"\nBest Model: {best_model_name}")
        print(f"  - Accuracy: {best_result['accuracy']:.4f}")
        print(f"  - Precision: {best_result['precision']:.4f}")
        print(f"  - Recall: {best_result['recall']:.4f}")
        print(f"  - F1-Score: {best_result['f1']:.4f}")
        
        print(f"\nVisualizations saved to: {output_dir}/")
        print(f"Evaluation report: {eval_report_path}")
        
        print("\n" + "="*70)
        print("EVALUATION COMPLETE!")
        print("="*70)
        logger.info("Model evaluation pipeline completed successfully")
        
    except Exception as e:
        logger.error(f"Error in evaluation pipeline: {e}")
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
