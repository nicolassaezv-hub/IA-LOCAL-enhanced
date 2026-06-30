"""
model_storage.py — Guarda y carga modelos entrenados con joblib.

FIX #2: Cada par tiene su propio archivo de modelo.
  - save_model(model, pair="EURUSD") → models/forex/latest_EURUSD.pkl
  - load_model(pair="EURUSD")        → carga el modelo correcto
  - load_latest() sigue disponible como fallback si pair=None
"""

import os
import joblib
from datetime import datetime


class ModelStorage:

    def __init__(self, base_dir: str = "models/forex"):
        self.base_dir    = base_dir
        self.latest_path = os.path.join(base_dir, "latest_model.pkl")   # fallback legacy
        os.makedirs(base_dir, exist_ok=True)

    # ─────────────────────────────────────────────────────────
    # GUARDAR — siempre crea versión timestamped + actualiza latest_{PAIR}
    # ─────────────────────────────────────────────────────────
    def save_model(self, model, name: str = "ensemble_forex",
                   pair: str = None, version: str = None,
                   feature_names: list = None) -> str:
        if version is None:
            version = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Empaquetar modelo + columnas para evitar feature mismatch
        bundle = {"model": model, "feature_names": feature_names}

        filename = f"{name}_{version}.pkl"
        path     = os.path.join(self.base_dir, filename)
        joblib.dump(bundle, path)

        # latest genérico (compatibilidad legacy)
        joblib.dump(bundle, self.latest_path)

        # latest por par
        if pair:
            clean  = _clean_pair(pair)
            p_path = os.path.join(self.base_dir, f"latest_{clean}.pkl")
            joblib.dump(bundle, p_path)
            print(f"[ModelStorage] Guardado → {path}")
            print(f"[ModelStorage] Latest par → {p_path}")
        else:
            print(f"[ModelStorage] Guardado → {path}")

        return path

    # ─────────────────────────────────────────────────────────
    # CARGAR — por par primero, luego fallback genérico
    # ─────────────────────────────────────────────────────────
    def load_model(self, pair: str = None):
        if pair:
            clean  = _clean_pair(pair)
            p_path = os.path.join(self.base_dir, f"latest_{clean}.pkl")
            if os.path.exists(p_path):
                bundle = joblib.load(p_path)
                print(f"[ModelStorage] Modelo cargado para {clean}: {p_path}")
                return self._unwrap(bundle)
            print(f"[ModelStorage] ⚠ No hay modelo para {clean}, usando latest genérico.")
        return self.load_latest()

    def load_model_with_features(self, pair: str = None):
        """Carga modelo Y lista de feature_names. Usar en predict para alinear columnas."""
        if pair:
            clean  = _clean_pair(pair)
            p_path = os.path.join(self.base_dir, f"latest_{clean}.pkl")
            if os.path.exists(p_path):
                bundle = joblib.load(p_path)
                if isinstance(bundle, dict):
                    return bundle["model"], bundle.get("feature_names")
                return bundle, None   # modelo legacy sin bundle
        bundle = joblib.load(self.latest_path) if os.path.exists(self.latest_path) else None
        if bundle is None:
            raise FileNotFoundError("No hay modelo entrenado.")
        if isinstance(bundle, dict):
            return bundle["model"], bundle.get("feature_names")
        return bundle, None

    @staticmethod
    def _unwrap(bundle):
        """Extrae el modelo del bundle dict o devuelve el objeto directamente (legacy)."""
        if isinstance(bundle, dict) and "model" in bundle:
            return bundle["model"]
        return bundle   # compatibilidad con modelos guardados antes de este fix

    def load_latest(self):
        if not os.path.exists(self.latest_path):
            raise FileNotFoundError(
                "No hay modelo entrenado. Ejecuta primero: pipeline.train('archivo.csv')"
            )
        bundle = joblib.load(self.latest_path)
        print("[ModelStorage] Modelo latest (genérico) cargado.")
        return self._unwrap(bundle)

    def load_version(self, filename: str):
        path = os.path.join(self.base_dir, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Modelo no encontrado: {filename}")
        bundle = joblib.load(path)
        return self._unwrap(bundle)

    def list_models(self) -> list:
        return sorted(f for f in os.listdir(self.base_dir) if f.endswith(".pkl"))

    def latest_exists(self, pair: str = None) -> bool:
        if pair:
            clean = _clean_pair(pair)
            p_path = os.path.join(self.base_dir, f"latest_{clean}.pkl")
            if os.path.exists(p_path):
                return True
        return os.path.exists(self.latest_path)


def _clean_pair(pair: str) -> str:
    return pair.upper().replace("/", "").replace("_", "").replace("-", "")
