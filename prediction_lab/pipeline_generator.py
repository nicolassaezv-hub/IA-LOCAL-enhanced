"""
prediction_lab/pipeline_generator.py — Fase 5.5 (Prediction Lab)

Convierte un ModelPlan (5.4) en un sklearn Pipeline ejecutable de verdad,
más el código Python equivalente para que Nicolas pueda copiarlo/adaptarlo
fuera del CLI.

No entrena el modelo — solo construye el objeto Pipeline (preprocesamiento
+ estimador) listo para `.fit()`. El entrenamiento real y su validación
quedan para Validation Engine (5.6).

Decisiones de diseño (vs. el draft de referencia revisado):
  - Si xgboost/lightgbm no están instalados, el fallback a un sklearn
    equivalente se hace respetando el tipo de problema (nunca se sustituye
    un regresor por un clasificador o viceversa) y queda registrado en
    `notes` — nunca en silencio.
  - Soporta clustering (KMeans) explícitamente, no solo classification/regression.
  - Usa ColumnTransformer real: numéricas -> impute mediana, categóricas
    (to_encode del FeaturePlan) -> impute + OneHotEncoder. El draft de
    referencia solo consideraba columnas numéricas.
  - Ensemble (VotingClassifier/VotingRegressor) solo cuando el plan trae
    'ensemble_member' — si no, un único estimador 'primary'.
  - Las features de dominio sugeridas (`feature_plan.to_create`, ej. RSI/MACD
    para forex) NO se generan aquí — son señaladas como paso previo manual,
    y si el dominio es forex/business se recuerda que ya existen módulos
    propios de feature engineering (evita duplicar lógica ya construida).

Patrón "graceful fail": si el ModelPlan no es válido/viable, o el CSV no
trae las columnas planeadas, se degrada con `ok=False` + `error` en vez de
lanzar una excepción.

API pública:
  generate_pipeline(model_plan, df=None) -> GeneratedPipeline
  generate_pipeline_from_csv(model_plan, csv_path) -> GeneratedPipeline
  cmd_lab_genera(csv_path, idea)          -> str
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any

from .model_planner import ModelPlan, AlgorithmConfig, plan_model


@dataclass
class GeneratedPipeline:
    ok:              bool = True
    error:           Optional[str] = None

    pipeline:        Any = None
    feature_names:   List[str] = field(default_factory=list)
    target_variable: Optional[str] = None
    problem_type:    str = "unknown"
    code_snippet:    str = ""
    notes:           List[str] = field(default_factory=list)
    meta:            Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        if not self.ok:
            return f"[PIPELINE GENERATOR] Error: {self.error}"

        lines = [
            "═" * 62,
            " PIPELINE GENERATOR — Pipeline construido",
            "═" * 62,
            f" Target       : {self.target_variable}   ({self.problem_type})",
            f" Features     : {len(self.feature_names)}  {self.feature_names[:10]}"
            + (" ..." if len(self.feature_names) > 10 else ""),
            f" Estimador    : {self.meta.get('estimator_repr', '?')}",
        ]
        if self.notes:
            lines.append("")
            lines.append(" Notas:")
            for n in self.notes:
                lines.append(f"   * {n}")
        lines.append("")
        lines.append(" ── Código equivalente (para usar fuera del CLI) ──")
        lines.append(self.code_snippet)
        lines.append("═" * 62)
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════
#  CONSTRUCCIÓN DE ESTIMADORES
# ══════════════════════════════════════════════════════════

def _sklearn_fallback(class_name: str, regression: bool):
    """
    Sustituto sklearn cuando xgboost/lightgbm no están instalados.
    Respeta SIEMPRE el tipo de problema (nunca regresor <-> clasificador).
    """
    if regression:
        from sklearn.ensemble import GradientBoostingRegressor
        return GradientBoostingRegressor(random_state=42), "GradientBoostingRegressor"
    from sklearn.ensemble import GradientBoostingClassifier
    return GradientBoostingClassifier(random_state=42), "GradientBoostingClassifier"


def _build_estimator(cfg: AlgorithmConfig, notes: List[str]):
    """Devuelve (estimador, nombre_clase_real_usada). Nunca lanza — cae a sklearn si falta la lib."""
    regression = "Regressor" in cfg.class_name

    if cfg.library == "xgboost":
        try:
            import xgboost as xgb
            return getattr(xgb, cfg.class_name)(**cfg.params), cfg.class_name
        except ImportError:
            est, real_name = _sklearn_fallback(cfg.class_name, regression)
            notes.append(f"xgboost no está instalado — {cfg.name} sustituido por {real_name} (mismo tipo de problema).")
            return est, real_name

    if cfg.library == "lightgbm":
        try:
            import lightgbm as lgb
            return getattr(lgb, cfg.class_name)(**cfg.params), cfg.class_name
        except ImportError:
            est, real_name = _sklearn_fallback(cfg.class_name, regression)
            notes.append(f"lightgbm no está instalado — {cfg.name} sustituido por {real_name} (mismo tipo de problema).")
            return est, real_name

    # library == "sklearn"
    if cfg.class_name == "KMeans":
        from sklearn.cluster import KMeans
        return KMeans(**cfg.params), "KMeans"
    if cfg.class_name == "RandomForestClassifier":
        from sklearn.ensemble import RandomForestClassifier
        return RandomForestClassifier(**cfg.params), cfg.class_name
    if cfg.class_name == "RandomForestRegressor":
        from sklearn.ensemble import RandomForestRegressor
        return RandomForestRegressor(**cfg.params), cfg.class_name
    if cfg.class_name == "LogisticRegression":
        from sklearn.linear_model import LogisticRegression
        return LogisticRegression(**cfg.params), cfg.class_name
    if cfg.class_name == "LinearRegression":
        from sklearn.linear_model import LinearRegression
        return LinearRegression(**cfg.params), cfg.class_name

    # Clase sklearn desconocida: fallback conservador según tipo de problema
    est, real_name = _sklearn_fallback(cfg.class_name, regression)
    notes.append(f"Clase '{cfg.class_name}' no reconocida — sustituida por {real_name}.")
    return est, real_name


def _build_ensemble(algorithms: List[AlgorithmConfig], problem_type: str, notes: List[str]):
    """Combina primary + ensemble_member(s) vía voting. Si solo hay uno, lo devuelve directo."""
    primaries = [a for a in algorithms if a.role == "primary"] or algorithms[:1]
    members = [a for a in algorithms if a.role == "ensemble_member"]
    primary = primaries[0]

    if not members:
        est, real_name = _build_estimator(primary, notes)
        return est, real_name

    built = [(primary.name, _build_estimator(primary, notes)[0])]
    built += [(m.name, _build_estimator(m, notes)[0]) for m in members]

    if problem_type == "regression":
        from sklearn.ensemble import VotingRegressor
        return VotingRegressor(estimators=built), "VotingRegressor"
    from sklearn.ensemble import VotingClassifier
    return VotingClassifier(estimators=built, voting="soft"), "VotingClassifier"


# ══════════════════════════════════════════════════════════
#  CONSTRUCCIÓN DEL PIPELINE
# ══════════════════════════════════════════════════════════

def _resolve_features(plan: ModelPlan, available_columns: Optional[List[str]]):
    """
    Determina qué columnas numéricas/categóricas entran al pipeline,
    validando contra las columnas reales del CSV si se proveen.
    """
    fp = plan.feature_plan
    numeric = [c for c in (fp.keep_as_is + fp.to_impute) if c != plan.target_variable]
    categorical = [c for c in fp.to_encode if c != plan.target_variable]

    notes = []
    if available_columns is not None:
        avail = set(available_columns)
        missing_num = [c for c in numeric if c not in avail]
        missing_cat = [c for c in categorical if c not in avail]
        if missing_num or missing_cat:
            notes.append(
                f"Columnas planeadas ausentes en el CSV real, se descartan: "
                f"{', '.join(missing_num + missing_cat)}"
            )
        numeric = [c for c in numeric if c in avail]
        categorical = [c for c in categorical if c in avail]

    return numeric, categorical, notes


def generate_pipeline(model_plan: ModelPlan, df=None) -> GeneratedPipeline:
    """
    Genera el sklearn Pipeline a partir de un ModelPlan ya calculado.
    `df` es opcional — si se pasa, se validan las columnas planeadas contra
    las columnas reales del DataFrame.
    """
    if not model_plan.ok:
        return GeneratedPipeline(ok=False, error=model_plan.error)

    if not model_plan.algorithms or model_plan.validation is None:
        return GeneratedPipeline(
            ok=False,
            error="El ModelPlan no trae algoritmos/validación (viabilidad insuficiente) — nada que generar.",
        )

    available_columns = list(df.columns) if df is not None else None
    numeric_cols, categorical_cols, feat_notes = _resolve_features(model_plan, available_columns)

    if not numeric_cols and not categorical_cols:
        return GeneratedPipeline(ok=False, error="No quedaron features válidas para construir el pipeline.")

    notes: List[str] = list(feat_notes)

    from sklearn.pipeline import Pipeline
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import OneHotEncoder
    from sklearn.feature_selection import VarianceThreshold

    transformers = []
    if numeric_cols:
        transformers.append(("num", SimpleImputer(strategy="median"), numeric_cols))
    if categorical_cols:
        cat_pipeline = Pipeline([
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ])
        transformers.append(("cat", cat_pipeline, categorical_cols))

    preprocessor = ColumnTransformer(transformers=transformers, remainder="drop")

    estimator, estimator_repr = _build_ensemble(model_plan.algorithms, model_plan.problem_type, notes)

    steps = [("preprocessor", preprocessor)]
    # VarianceThreshold solo aplica de forma segura sobre matrices ya densas y sin
    # categóricas one-hot mezcladas de forma ambigua — se omite si hay categóricas
    # para no arriesgar romper el fit por dtype/sparse mismatches.
    if not categorical_cols:
        steps.append(("variance", VarianceThreshold(threshold=0.01)))
    steps.append(("estimator", estimator))

    pipeline = Pipeline(steps)

    if model_plan.domain in ("forex", "business") and model_plan.feature_plan.to_create:
        notes.append(
            "Este pipeline NO genera las features de dominio sugeridas "
            f"({'; '.join(model_plan.feature_plan.to_create)}) — agrégalas al DataFrame antes de "
            "entrenar, o mejor: reutiliza el módulo ya existente "
            f"({model_plan.reuse_existing or 'forex/prediction o forex/business'})."
        )
    elif model_plan.feature_plan.to_create:
        notes.append(f"Features sugeridas (no auto-generadas): {'; '.join(model_plan.feature_plan.to_create)}")

    code = _generate_code(model_plan, numeric_cols, categorical_cols, estimator_repr)

    return GeneratedPipeline(
        ok=True,
        pipeline=pipeline,
        feature_names=numeric_cols + categorical_cols,
        target_variable=model_plan.target_variable,
        problem_type=model_plan.problem_type,
        code_snippet=code,
        notes=notes,
        meta={
            "estimator_repr": estimator_repr,
            "n_numeric": len(numeric_cols),
            "n_categorical": len(categorical_cols),
            "n_steps": len(steps),
        },
    )


def generate_pipeline_from_csv(model_plan: ModelPlan, csv_path: str) -> GeneratedPipeline:
    """Conveniencia: lee el CSV solo para validar columnas disponibles (no entrena)."""
    import os
    if not csv_path or not os.path.exists(csv_path):
        return GeneratedPipeline(ok=False, error=f"Archivo no encontrado: {csv_path}")
    try:
        import pandas as pd
        df = pd.read_csv(csv_path, nrows=5)   # solo para conocer columnas, no carga todo
    except Exception as e:
        return GeneratedPipeline(ok=False, error=f"No se pudo leer el CSV: {e}")
    return generate_pipeline(model_plan, df)


def _generate_code(plan: ModelPlan, numeric_cols: List[str], categorical_cols: List[str],
                    estimator_repr: str) -> str:
    val = plan.validation
    lines = [
        "# generado por ASTRA Prediction Lab (Fase 5.5 — Pipeline Generator)",
        "import pandas as pd",
        "from sklearn.pipeline import Pipeline",
        "from sklearn.compose import ColumnTransformer",
        "from sklearn.impute import SimpleImputer",
        "from sklearn.preprocessing import OneHotEncoder",
        "from sklearn.model_selection import train_test_split",
        "",
        f"NUMERIC_FEATURES = {numeric_cols}",
        f"CATEGORICAL_FEATURES = {categorical_cols}",
        f"TARGET = '{plan.target_variable}'",
        "",
        "df = pd.read_csv('tu_dataset.csv')",
        "X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]",
        "y = df[TARGET]",
        "",
        f"# Estimador: {estimator_repr}  |  Validación: {val.method}, métrica={val.metric}",
        f"# SMOTE recomendado: {'sí' if val.use_smote else 'no'}"
        + (" -> from imblearn.over_sampling import SMOTE (aplicar sobre X_train/y_train antes de fit)" if val.use_smote else ""),
        "X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42)",
        "# pipeline.fit(X_train, y_train)",
        "# pipeline.score(X_test, y_test)",
    ]
    return "\n".join(lines)


def cmd_lab_genera(csv_path: str, idea: str, target_variable=None) -> str:
    """Comando CLI: 'lab genera <csv> \"<idea>\" [target]' — para wiring en main.py."""
    if not csv_path or not idea:
        return 'Uso: lab genera <archivo.csv> "<describe tu idea>" [columna_target]'

    plan = plan_model(csv_path, idea, target_variable=target_variable)
    if not plan.ok or not plan.algorithms or plan.validation is None:
        reason = plan.error or "viabilidad insuficiente — revisa 'lab planea' primero."
        return f"[PIPELINE GENERATOR] No se generó pipeline: {reason}"

    import os
    try:
        import pandas as pd
        df = pd.read_csv(csv_path) if os.path.exists(csv_path) else None
    except Exception:
        df = None

    generated = generate_pipeline(plan, df)
    return generated.summary()
