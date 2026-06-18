import os
import joblib
from datetime import datetime


class ModelStorage:

    def __init__(
        self,
        base_dir="models/forex"
    ):

        self.base_dir = base_dir

        os.makedirs(
            self.base_dir,
            exist_ok=True
        )

        self.latest_path = os.path.join(
            self.base_dir,
            "latest_model.pkl"
        )

    # -----------------------------
    # SAVE MODEL (VERSIONED)
    # -----------------------------
    def save_model(
        self,
        model,
        name="xgb_forex",
        version=None
    ):

        if version is None:

            version = datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )

        filename = f"{name}_{version}.pkl"

        path = os.path.join(
            self.base_dir,
            filename
        )

        joblib.dump(model, path)

        # Always update latest pointer
        joblib.dump(model, self.latest_path)

        print(
            f"[ModelStorage] Saved model → {path}"
        )

        return path

    # -----------------------------
    # LOAD LATEST MODEL
    # -----------------------------
    def load_latest(self):

        if not os.path.exists(self.latest_path):

            raise FileNotFoundError(
                "No latest model found. Train first."
            )

        model = joblib.load(self.latest_path)

        print(
            "[ModelStorage] Loaded latest model"
        )

        return model

    # -----------------------------
    # LOAD SPECIFIC VERSION
    # -----------------------------
    def load_version(self, filename):

        path = os.path.join(
            self.base_dir,
            filename
        )

        if not os.path.exists(path):

            raise FileNotFoundError(
                f"Model not found: {filename}"
            )

        model = joblib.load(path)

        print(
            f"[ModelStorage] Loaded model → {filename}"
        )

        return model

    # -----------------------------
    # LIST MODELS
    # -----------------------------
    def list_models(self):

        models = [
            f for f in os.listdir(self.base_dir)
            if f.endswith(".pkl")
        ]

        return sorted(models)
