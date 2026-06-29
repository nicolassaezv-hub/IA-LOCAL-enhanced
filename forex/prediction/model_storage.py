"""
model_storage.py — Guarda y carga modelos entrenados con joblib.
Soporta cualquier objeto serializable (SoftVotingEnsemble, IsotonicCalibrator, etc.)
"""

import os
import joblib
from datetime import datetime


class ModelStorage:

    def __init__(self, base_dir: str = "models/forex"):
        self.base_dir    = base_dir
        self.latest_path = os.path.join(base_dir, "latest_model.pkl")
        os.makedirs(base_dir, exist_ok=True)

    def save_model(self, model, name: str = "ensemble_forex", version: str = None) -> str:
        if version is None:
            version = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{version}.pkl"
        path = os.path.join(self.base_dir, filename)
        joblib.dump(model, path)
        joblib.dump(model, self.latest_path)   # siempre actualiza "latest"
        print(f"[ModelStorage] Guardado → {path}")
        return path

    def load_latest(self):
        if not os.path.exists(self.latest_path):
            raise FileNotFoundError(
                "No hay modelo entrenado. Ejecuta primero: pipeline.train('archivo.csv')"
            )
        model = joblib.load(self.latest_path)
        print("[ModelStorage] Modelo latest cargado.")
        return model

    def load_version(self, filename: str):
        path = os.path.join(self.base_dir, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Modelo no encontrado: {filename}")
        return joblib.load(path)

    def list_models(self) -> list:
        return sorted(f for f in os.listdir(self.base_dir) if f.endswith(".pkl"))

    def latest_exists(self) -> bool:
        return os.path.exists(self.latest_path)
