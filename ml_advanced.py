# ml_advanced.py
# Advanced Machine Learning module - Hyperparameter optimization, model testing, and ensemble methods
# Integrates scikit-learn, hypothesis, and model evaluation tools

from typing import Any, Dict, List, Tuple, Optional
import numpy as np
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report, roc_auc_score
)
import warnings

warnings.filterwarnings('ignore')


class HyperparameterOptimizer:
    """Advanced hyperparameter optimization using grid and random search"""
    
    def __init__(self, model: Any, param_grid: Dict[str, List]):
        self.model = model
        self.param_grid = param_grid
        self.best_model = None
        self.best_params = None
    
    def grid_search(self, X_train: np.ndarray, y_train: np.ndarray, cv: int = 5) -> Dict:
        """Exhaustive grid search over parameter combinations"""
        print("🔍 Starting Grid Search...")
        
        grid_search = GridSearchCV(
            self.model,
            self.param_grid,
            cv=cv,
            scoring='accuracy',
            n_jobs=-1,
            verbose=1
        )
        
        grid_search.fit(X_train, y_train)
        
        self.best_model = grid_search.best_estimator_
        self.best_params = grid_search.best_params_
        
        print(f"✅ Best parameters: {self.best_params}")
        print(f"✅ Best score: {grid_search.best_score_:.4f}")
        
        return {
            'best_params': grid_search.best_params_,
            'best_score': grid_search.best_score_,
            'cv_results': grid_search.cv_results_
        }
    
    def random_search(self, X_train: np.ndarray, y_train: np.ndarray, 
                     n_iter: int = 20, cv: int = 5) -> Dict:
        """Random search over parameter combinations"""
        print("🔍 Starting Random Search...")
        
        random_search = RandomizedSearchCV(
            self.model,
            self.param_grid,
            n_iter=n_iter,
            cv=cv,
            scoring='accuracy',
            n_jobs=-1,
            verbose=1
        )
        
        random_search.fit(X_train, y_train)
        
        self.best_model = random_search.best_estimator_
        self.best_params = random_search.best_params_
        
        print(f"✅ Best parameters: {self.best_params}")
        print(f"✅ Best score: {random_search.best_score_:.4f}")
        
        return {
            'best_params': random_search.best_params_,
            'best_score': random_search.best_score_,
            'cv_results': random_search.cv_results_
        }


class ModelValidator:
    """Comprehensive model validation and testing"""
    
    def __init__(self, model: Any):
        self.model = model
        self.predictions = None
        self.metrics = {}
    
    def evaluate(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict:
        """Comprehensive model evaluation"""
        self.predictions = self.model.predict(X_test)
        
        metrics = {
            'accuracy': accuracy_score(y_test, self.predictions),
            'precision': precision_score(y_test, self.predictions, average='weighted', zero_division=0),
            'recall': recall_score(y_test, self.predictions, average='weighted', zero_division=0),
            'f1': f1_score(y_test, self.predictions, average='weighted', zero_division=0),
            'confusion_matrix': confusion_matrix(y_test, self.predictions),
            'classification_report': classification_report(y_test, self.predictions, zero_division=0)
        }
        
        self.metrics = metrics
        return metrics
    
    def print_report(self):
        """Print evaluation report"""
        print("\n" + "="*70)
        print("MODEL EVALUATION REPORT".center(70))
        print("="*70 + "\n")
        
        print(f"Accuracy:  {self.metrics.get('accuracy', 0):.4f}")
        print(f"Precision: {self.metrics.get('precision', 0):.4f}")
        print(f"Recall:    {self.metrics.get('recall', 0):.4f}")
        print(f"F1 Score:  {self.metrics.get('f1', 0):.4f}")
        
        print("\n" + "="*70 + "\n")


class EnsembleModels:
    """Ensemble methods combining multiple models"""
    
    def __init__(self, models: List[Tuple[str, Any]]):
        self.models = models
        self.trained_models = []
    
    def fit(self, X_train: np.ndarray, y_train: np.ndarray):
        """Train all models in ensemble"""
        print("🤖 Training ensemble models...")
        
        for name, model in self.models:
            print(f"  Training {name}...")
            model.fit(X_train, y_train)
            self.trained_models.append((name, model))
        
        print("✅ Ensemble training complete!")
    
    def predict_voting(self, X_test: np.ndarray, voting: str = 'hard') -> np.ndarray:
        """Predict using voting ensemble"""
        if voting == 'hard':
            predictions = np.array([model.predict(X_test) for _, model in self.trained_models])
            return np.apply_along_axis(lambda x: np.bincount(x.astype(int)).argmax(), axis=0, arr=predictions)
        else:
            predictions = []
            for _, model in self.trained_models:
                try:
                    pred_proba = model.predict_proba(X_test)
                    predictions.append(pred_proba)
                except:
                    pred = model.predict(X_test)
                    pred_proba = np.eye(len(np.unique(pred)))[pred]
                    predictions.append(pred_proba)
            
            avg_predictions = np.mean(predictions, axis=0)
            return np.argmax(avg_predictions, axis=1)


# ===== TESTING =====

if __name__ == "__main__":
    print("\n" + "🤖 ADVANCED ML TEST SUITE 🤖".center(70))
    print("="*70 + "\n")
    
    from sklearn.datasets import load_iris
    from sklearn.model_selection import train_test_split
    from sklearn.ensemble import RandomForestClassifier
    
    # Load data
    iris = load_iris()
    X_train, X_test, y_train, y_test = train_test_split(
        iris.data, iris.target, test_size=0.3, random_state=42
    )
    
    # Test model validation
    print("Test: Model Validation")
    print("-" * 70)
    rf = RandomForestClassifier(n_estimators=10, random_state=42)
    rf.fit(X_train, y_train)
    validator = ModelValidator(rf)
    metrics = validator.evaluate(X_test, y_test)
    print(f"Accuracy: {metrics['accuracy']:.4f}")
    print()
    
    print("="*70)
    print("✅ TESTS COMPLETED".center(70))
    print("="*70 + "\n")
