"""
11_train_real_model.py
ML Model Training Pipeline
Trains and compares multiple classification models
"""

import pandas as pd
import numpy as np
import logging
import os
from pathlib import Path
import pickle
import time

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import (accuracy_score, precision_score, recall_score, 
                            f1_score, confusion_matrix, classification_report)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def train_and_evaluate_model(name, model, X_train, X_test, y_train, y_test):
    """
    Train and evaluate a single model.
    
    Parameters:
    -----------
    name : str
        Model name
    model : sklearn model
        Model to train
    X_train, X_test : ndarray
        Training and test features
    y_train, y_test : ndarray
        Training and test labels
    
    Returns:
    --------
    results : dict
        Training results and metrics
    """
    print(f"\nTraining {name}...")
    logger.info(f"Training model: {name}")
    
    start_time = time.time()
    
    # Train
    model.fit(X_train, y_train)
    train_time = time.time() - start_time
    
    # Predict
    y_pred = model.predict(X_test)
    
    # Evaluate
    results = {
        'model': model,
        'name': name,
        'train_time': train_time,
        'accuracy': accuracy_score(y_test, y_pred),
        'precision': precision_score(y_test, y_pred, average='weighted', zero_division=0),
        'recall': recall_score(y_test, y_pred, average='weighted', zero_division=0),
        'f1': f1_score(y_test, y_pred, average='weighted', zero_division=0),
        'confusion_matrix': confusion_matrix(y_test, y_pred),
        'classification_report': classification_report(y_test, y_pred, zero_division=0),
        'y_pred': y_pred,
        'y_test': y_test
    }
    
    logger.info(f"{name} - Accuracy: {results['accuracy']:.4f}, "
               f"F1: {results['f1']:.4f}, Train time: {train_time:.2f}s")
    
    print(f"  ✓ Accuracy: {results['accuracy']:.4f}")
    print(f"  ✓ F1-score: {results['f1']:.4f}")
    print(f"  ✓ Training time: {train_time:.2f}s")
    
    return results


def main():
    """
    Main model training pipeline.
    """
    print("\n" + "="*70)
    print("STEP 11: MODEL TRAINING")
    print("="*70 + "\n")
    
    # Paths
    features_path = "ml/outputs/extracted_features.pkl"
    feature_names_path = "ml/outputs/feature_names.pkl"
    output_dir = "ml/outputs"
    models_dir = os.path.join(output_dir, "models/saved_models")
    results_path = os.path.join(output_dir, "training_results.pkl")
    
    # Create directories
    Path(models_dir).mkdir(parents=True, exist_ok=True)
    
    # Configuration
    TEST_SIZE = 0.2
    RANDOM_STATE = 42
    VERBOSE = 1
    
    try:
        # Load features
        print("[1/7] Loading extracted features...")
        if not os.path.exists(features_path):
            print(f"❌ Error: {features_path} not found")
            print("Please run 10_feature_extraction_real.py first")
            return
        
        with open(features_path, 'rb') as f:
            df_features = pickle.load(f)
        
        print(f"✓ Loaded features: {df_features.shape}")
        logger.info(f"Features shape: {df_features.shape}")
        
        # Load feature names
        with open(feature_names_path, 'rb') as f:
            feature_names = pickle.load(f)
        
        # Prepare data
        print("\n[2/7] Preparing training data...")
        
        X = df_features.drop('label', axis=1).values
        y = df_features['label'].values
        
        print(f"✓ Features shape: {X.shape}")
        print(f"✓ Labels shape: {y.shape}")
        print(f"✓ Number of classes: {len(np.unique(y))}")
        
        # Train-test split
        print("\n[3/7] Splitting data...")
        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=TEST_SIZE,
            random_state=RANDOM_STATE,
            stratify=y
        )
        
        print(f"✓ Train set: {X_train.shape}")
        print(f"✓ Test set: {X_test.shape}")
        print(f"✓ Train split: {len(X_train) / len(X) * 100:.1f}%")
        logger.info(f"Train-test split: {X_train.shape[0]} train, {X_test.shape[0]} test")
        
        # Initialize models
        print("\n[4/7] Initializing models...")
        
        models = {
            'Random Forest': RandomForestClassifier(
                n_estimators=100,
                max_depth=15,
                random_state=RANDOM_STATE,
                n_jobs=-1,
                verbose=VERBOSE
            ),
            'SVM': SVC(
                kernel='rbf',
                C=1.0,
                gamma='scale',
                random_state=RANDOM_STATE,
                verbose=VERBOSE
            ),
            'KNN': KNeighborsClassifier(
                n_neighbors=5,
                n_jobs=-1
            )
        }
        
        print(f"✓ Models ready: {list(models.keys())}")
        logger.info(f"Models initialized: {list(models.keys())}")
        
        # Train models
        print("\n[5/7] Training models...")
        print("-"*70)
        
        results = {}
        for model_name, model in models.items():
            result = train_and_evaluate_model(
                model_name,
                model,
                X_train, X_test, y_train, y_test
            )
            results[model_name] = result
        
        # Find best model
        print("\n[6/7] Evaluating best model...")
        best_model_name = max(results, key=lambda x: results[x]['f1'])
        best_result = results[best_model_name]
        
        print(f"✓ Best model: {best_model_name}")
        print(f"  - Accuracy: {best_result['accuracy']:.4f}")
        print(f"  - Precision: {best_result['precision']:.4f}")
        print(f"  - Recall: {best_result['recall']:.4f}")
        print(f"  - F1-score: {best_result['f1']:.4f}")
        
        logger.info(f"Best model: {best_model_name} with F1={best_result['f1']:.4f}")
        
        # Save models
        print("\n[7/7] Saving trained models...")
        
        for model_name, result in results.items():
            model_path = os.path.join(models_dir, f"{model_name.replace(' ', '_')}.pkl")
            with open(model_path, 'wb') as f:
                pickle.dump(result['model'], f)
            print(f"  ✓ Saved: {model_path}")
        
        # Save results
        results_to_save = {
            'results': results,
            'best_model': best_model_name,
            'X_test': X_test,
            'y_test': y_test,
            'feature_names': feature_names,
            'test_size': TEST_SIZE
        }
        
        with open(results_path, 'wb') as f:
            pickle.dump(results_to_save, f)
        print(f"  ✓ Saved results: {results_path}")
        
        # Print summary
        print("\n" + "="*70)
        print("TRAINING SUMMARY")
        print("="*70)
        
        print("\nModel Performance Comparison:")
        print("-"*70)
        print(f"{'Model':<20s} {'Accuracy':<12s} {'Precision':<12s} {'Recall':<12s} {'F1-Score':<12s}")
        print("-"*70)
        
        for model_name in sorted(results.keys()):
            r = results[model_name]
            print(f"{model_name:<20s} {r['accuracy']:<12.4f} {r['precision']:<12.4f} "
                  f"{r['recall']:<12.4f} {r['f1']:<12.4f}")
        
        print(f"\n✓ Best Model: {best_model_name}")
        print(f"  - Test Accuracy: {best_result['accuracy']:.4f}")
        print(f"  - Test F1-Score: {best_result['f1']:.4f}")
        
        print("\n" + "="*70)
        print("MODEL TRAINING COMPLETE!")
        print("="*70)
        print(f"\nModels saved to: {models_dir}/")
        print(f"Results saved to: {results_path}")
        logger.info("Model training pipeline completed successfully")
        
    except Exception as e:
        logger.error(f"Error in training pipeline: {e}")
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
