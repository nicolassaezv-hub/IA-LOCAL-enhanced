"""
Roadmap V Integration — Parche para IntegratedPipeline
=======================================================
Modulo de integracion que conecta V.3, V.4, V.5, V.6, V.8 y V.9 con el pipeline existente.

Fases integradas:
  V.5  — Quality Gate (antes de entrenar)
  V.6  — Feature Importance (despues de entrenar)
  V.9  — Backtesting Protocol (evaluacion estandar)
  V.4  — Regime Detection (contexto de mercado)
  V.3  — MTF Intelligence (coherencia multi-timeframe)
  V.8  — Reliability Score (indice de confiabilidad compuesto)

COMO APLICAR:
Importar este modulo al inicio de integrated_pipeline.py y llamar a las
funciones de integracion desde los metodos correspondientes:

    # En IntegratedPipeline.train(), al inicio:
    from forex.prediction.roadmap_v_integration import run_quality_gate
    approved, quality_report = run_quality_gate(df, pair=pair, timeframe=timeframe)
    if not approved:
        return {"ok": False, "error": "Quality gate rechazado", "quality_report": quality_report.to_dict()}

    # Despues de entrenar, antes de evaluar:
    from forex.prediction.roadmap_v_integration import run_feature_importance
    fi_report = run_feature_importance(model, X_train, y_train, X_test, y_test, ...)

    # Al evaluar el modelo:
    from forex.prediction.roadmap_v_integration import run_backtest_protocol
    bt_report = run_backtest_protocol(model, X_test, y_test, returns=returns, ...)

    # En IntegratedPipeline.predict(), antes de la predicción:
    from forex.prediction.roadmap_v_integration import run_regime_detection, run_mtf_coherence
    regime = run_regime_detection(df, pair=pair, timeframe=timeframe)
    mtf = run_mtf_coherence(d1_df=d1, h4_df=h4, h1_df=h1, pair=pair)

    # Despues de predecir, calcular el Reliability Score:
    from forex.prediction.roadmap_v_integration import run_reliability_score
    reliability = run_reliability_score(
        model_confidence=confidence,
        ensemble_predictions=predictions,
        mtf_coherence_score=mtf.coherence_score,
        regime_primary=regime.primary,
        signal=signal,
    )

Estas funciones tambien pueden usarse standalone desde CLI o Workspace.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Any

from forex.prediction.quality_analyzer import QualityAnalyzer, QualityReport, cmd_quality_report, quality_gate
from forex.prediction.quality_report import QualityIssue
from forex.prediction.backtest_protocol import (
    BacktestProtocol,
    BacktestReport,
    BacktestMetrics,
    evaluate_model,
    compare_models,
    walk_forward_validation,
    monte_carlo_simulation,
    generate_html_report,
    cmd_backtest_report,
    cmd_model_comparison,
)
from forex.prediction.feature_importance import (
    FeatureImportanceAnalyzer,
    FeatureImportanceReport,
    cmd_feature_importance_report,
    filter_features,
    get_optimal_feature_names,
)
from forex.prediction.regime_detector import (
    RegimeDetector,
    RegimeAssessment,
    cmd_regime_report,
    store_regime,
    get_regime_history,
)
from forex.prediction.mtf_coherence import (
    MTFIntelligence,
    MTFCoherenceResult,
    cmd_mtf_report,
)
from forex.prediction.reliability_score import (
    ReliabilityScorer,
    ReliabilityReport,
    cmd_reliability_report,
)
from forex.prediction.model_selector import (
    ModelSelectionEngine,
    ModelSelectionResult,
    ModelRegistry,
    cmd_model_selection_report,
)
from forex.prediction.decision_engine import (
    DecisionEngine,
    DecisionResult,
    cmd_decision_report,
)
from forex.prediction.risk_engine import (
    RiskEngine,
    RiskAssessment,
    cmd_risk_report,
)
from forex.data.dataset_updater import (
    DatasetUpdater,
    UpdateResult,
    cmd_dataset_update,
)
from forex.scheduler.task_manager import (
    TaskManager,
    Task,
    TaskResult,
    cmd_scheduler_status,
)
from forex.prediction.retrain_manager import (
    RetrainManager,
    RetrainDecision,
    RetrainRecord,
    cmd_retrain_check,
    cmd_retrain_history,
)
from forex.market_sentinel import (
    MarketSentinel,
    SentinelSignal,
    cmd_sentinel_status,
    cmd_sentinel_signals,
)
from forex.prediction.outcome_tracker import (
    OutcomeTracker,
    PredictionRecord,
    OutcomeStats,
    cmd_outcome_stats,
    cmd_outcome_history,
)
from notifications.notifier import (
    Notifier,
    NotificationMessage,
    NotificationResult,
    cmd_notify_test,
    cmd_notify_log,
)
from forex.portfolio.portfolio_ranker import (
    PortfolioRanker,
    PortfolioOpportunity,
    PortfolioRanking,
    cmd_portfolio_ranking,
    cmd_portfolio_export,
)


# ──────────────────────────────────────────────────────
# V.5 — Quality Gate Integration
# ──────────────────────────────────────────────────────

def run_quality_gate(
    df: pd.DataFrame,
    config: dict | None = None,
    pair: str = "",
    timeframe: str = "",
    verbose: bool = True,
) -> tuple[bool, QualityReport]:
    """
    Ejecuta el gate de calidad antes del entrenamiento.
    Si approved == False, el entrenamiento debe bloquearse.
    """
    approved, report = quality_gate(df, config=config, pair=pair, timeframe=timeframe)
    if verbose:
        print(cmd_quality_report(report))
    return approved, report


def quality_gate_decision(report: QualityReport) -> dict:
    """Retorna la decision del gate en formato dict para API/Workspace."""
    return {
        "approved": report.approved,
        "score": report.global_score,
        "critical": report.critical_count,
        "warnings": report.warning_count,
        "info": report.info_count,
        "recommendation": report.recommendation,
        "issues": [
            {
                "severity": i.severity,
                "category": i.category,
                "column": i.column,
                "description": i.description,
                "suggestion": i.suggestion,
            }
            for i in report.issues
        ],
    }


# ──────────────────────────────────────────────────────
# V.9 — Backtesting Protocol Integration
# ──────────────────────────────────────────────────────

def run_backtest_protocol(
    model: Any,
    X_test: np.ndarray,
    y_test: np.ndarray,
    returns: np.ndarray | None = None,
    model_name: str = "",
    pair: str = "",
    timeframe: str = "",
    rr_ratio: float = 1.0,
    run_monte_carlo: bool = False,
    mc_iterations: int = 1000,
    verbose: bool = True,
) -> BacktestReport:
    """
    Evalua un modelo con el protocolo estandar V.9.
    """
    report = evaluate_model(
        model, X_test, y_test,
        returns=returns,
        model_name=model_name,
        pair=pair,
        timeframe=timeframe,
        rr_ratio=rr_ratio,
        run_monte_carlo=run_monte_carlo,
        mc_iterations=mc_iterations,
    )
    if verbose:
        print(cmd_backtest_report(report))
    return report


def run_walk_forward(
    model_factory,
    X: np.ndarray,
    y: np.ndarray,
    returns: np.ndarray | None = None,
    n_folds: int = 5,
    rr_ratio: float = 1.0,
) -> list:
    """Ejecuta Walk-Forward Validation."""
    return walk_forward_validation(model_factory, X, y, returns=returns, n_folds=n_folds, rr_ratio=rr_ratio)


def run_model_comparison(
    models: dict[str, Any],
    X_test: np.ndarray,
    y_test: np.ndarray,
    returns: np.ndarray | None = None,
    rr_ratio: float = 1.0,
    verbose: bool = True,
) -> dict[str, BacktestReport]:
    """Compara multiples modelos bajo el mismo protocolo."""
    reports = compare_models(models, X_test, y_test, returns=returns, rr_ratio=rr_ratio)
    if verbose:
        print(cmd_model_comparison(reports))
    return reports


# ──────────────────────────────────────────────────────
# V.6 — Feature Importance Integration
# ──────────────────────────────────────────────────────

def run_feature_importance(
    model: Any,
    X_train: pd.DataFrame | np.ndarray,
    y_train: np.ndarray,
    X_test: pd.DataFrame | np.ndarray | None = None,
    y_test: np.ndarray | None = None,
    feature_names: list[str] | None = None,
    pair: str = "",
    timeframe: str = "",
    model_name: str = "",
    mtf_columns: list[str] | None = None,
    use_shap: bool = True,
    use_permutation: bool = True,
    verbose: bool = True,
) -> FeatureImportanceReport:
    """
    Analiza la importancia de features del modelo.
    """
    analyzer = FeatureImportanceAnalyzer(use_shap=use_shap, use_permutation=use_permutation)
    report = analyzer.analyze(
        model, X_train, y_train,
        X_test=X_test,
        y_test=y_test,
        feature_names=feature_names,
        pair=pair,
        timeframe=timeframe,
        model_name=model_name,
        mtf_columns=mtf_columns,
    )
    if verbose:
        print(cmd_feature_importance_report(report))
    return report


def apply_feature_filter(
    X: pd.DataFrame,
    fi_report: FeatureImportanceReport,
    keep_mtf: bool = True,
) -> pd.DataFrame:
    """Filtra features segun el reporte de importancia."""
    return filter_features(X, fi_report, keep_mtf=keep_mtf)


# ──────────────────────────────────────────────────────
# V.4 — Regime Detection Integration
# ──────────────────────────────────────────────────────

def run_regime_detection(
    df: pd.DataFrame,
    news_active: bool = False,
    news_sentiment: str = "",
    pair: str = "",
    timeframe: str = "",
    config: dict | None = None,
    verbose: bool = True,
) -> RegimeAssessment:
    """Detecta el regimen de mercado actual."""
    detector = RegimeDetector(config=config)
    assessment = detector.detect(df, news_active=news_active, news_sentiment=news_sentiment, pair=pair, timeframe=timeframe)
    if verbose:
        print(cmd_regime_report(assessment, pair=pair, timeframe=timeframe))
    return assessment


# ──────────────────────────────────────────────────────
# V.3 — MTF Intelligence Integration
# ──────────────────────────────────────────────────────

def run_mtf_coherence(
    d1_df: pd.DataFrame | None = None,
    h4_df: pd.DataFrame | None = None,
    h1_df: pd.DataFrame | None = None,
    pair: str = "",
    config: dict | None = None,
    verbose: bool = True,
) -> MTFCoherenceResult:
    """Analiza la coherencia multi-timeframe."""
    mtf = MTFIntelligence(config=config)
    result = mtf.analyze(d1_df=d1_df, h4_df=h4_df, h1_df=h1_df, pair=pair)
    if verbose:
        print(cmd_mtf_report(result, pair=pair))
    return result


# ──────────────────────────────────────────────────────
# V.8 — Reliability Score Integration
# ──────────────────────────────────────────────────────

def run_reliability_score(
    model_confidence: float,
    ensemble_predictions: list[str] | None = None,
    mtf_coherence_score: float | None = None,
    regime_primary: str = "",
    regime_confidence: float = 0.0,
    news_active: bool = False,
    news_sentiment: str = "",
    volatility_level: str = "normal",
    model_win_rate: float | None = None,
    model_recent_predictions: int = 0,
    signal: str = "HOLD",
    weights: dict | None = None,
    thresholds: dict | None = None,
    verbose: bool = True,
) -> ReliabilityReport:
    """Calcula el Reliability Score compuesto."""
    scorer = ReliabilityScorer(weights=weights, thresholds=thresholds)
    report = scorer.compute(
        model_confidence=model_confidence,
        ensemble_predictions=ensemble_predictions,
        mtf_coherence_score=mtf_coherence_score,
        regime_primary=regime_primary,
        regime_confidence=regime_confidence,
        news_active=news_active,
        news_sentiment=news_sentiment,
        volatility_level=volatility_level,
        model_win_rate=model_win_rate,
        model_recent_predictions=model_recent_predictions,
        signal=signal,
    )
    if verbose:
        print(cmd_reliability_report(report))
    return report


# ──────────────────────────────────────────────────────
# V.7 — Model Selection Engine Integration
# ──────────────────────────────────────────────────────

def run_model_selection(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    returns: np.ndarray | None = None,
    candidates: dict | None = None,
    regime: str = "",
    pair: str = "",
    timeframe: str = "",
    feature_names: list[str] | None = None,
    config: dict | None = None,
    verbose: bool = True,
) -> ModelSelectionResult:
    """Compara modelos y selecciona el mejor."""
    engine = ModelSelectionEngine(config=config)
    result = engine.select(
        X_train, y_train, X_test, y_test,
        returns=returns, candidates=candidates,
        regime=regime, pair=pair, timeframe=timeframe,
        feature_names=feature_names,
    )
    if verbose:
        print(cmd_model_selection_report(result))
    return result


# ──────────────────────────────────────────────────────
# V.1 — Decision Engine Integration
# ──────────────────────────────────────────────────────

def run_decision_engine(
    ensemble_signal: str = "HOLD",
    model_confidence: float = 0.0,
    ensemble_predictions: list[str] | None = None,
    regime: RegimeAssessment | None = None,
    mtf: MTFCoherenceResult | None = None,
    circuit_breaker_active: bool = False,
    news_active: bool = False,
    news_sentiment: str = "",
    volatility_level: str = "normal",
    atr_percentile: float = 50.0,
    model_win_rate: float | None = None,
    model_recent_predictions: int = 0,
    risk_info: dict | None = None,
    pair: str = "",
    timeframe: str = "",
    config: dict | None = None,
    verbose: bool = True,
) -> DecisionResult:
    """Ejecuta el Decision Engine y produce una decision final."""
    engine = DecisionEngine(config=config)
    result = engine.decide(
        ensemble_signal=ensemble_signal,
        model_confidence=model_confidence,
        ensemble_predictions=ensemble_predictions,
        regime=regime,
        mtf=mtf,
        circuit_breaker_active=circuit_breaker_active,
        news_active=news_active,
        news_sentiment=news_sentiment,
        volatility_level=volatility_level,
        atr_percentile=atr_percentile,
        model_win_rate=model_win_rate,
        model_recent_predictions=model_recent_predictions,
        risk_info=risk_info,
        pair=pair,
        timeframe=timeframe,
    )
    if verbose:
        print(cmd_decision_report(result))
    return result


# ──────────────────────────────────────────────────────
# V.2 — Risk Engine Integration
# ──────────────────────────────────────────────────────

def run_risk_engine(
    decision: str = "BUY",
    entry_price: float = 0.0,
    atr: float = 0.0,
    reliability_score: float = 0.0,
    model_win_rate: float = 0.5,
    regime: str = "",
    pair: str = "",
    timeframe: str = "",
    capital: float | None = None,
    rr_ratio: float | None = None,
    config: dict | None = None,
    verbose: bool = True,
) -> RiskAssessment:
    """Calcula el analisis de riesgo para una señal."""
    engine = RiskEngine(config=config)
    risk = engine.assess(
        decision=decision,
        entry_price=entry_price,
        atr=atr,
        reliability_score=reliability_score,
        model_win_rate=model_win_rate,
        regime=regime,
        pair=pair,
        timeframe=timeframe,
        capital=capital,
        rr_ratio=rr_ratio,
    )
    if verbose:
        print(cmd_risk_report(risk))
    return risk


# ──────────────────────────────────────────────────────
# Full V.1+V.2+V.3+V.4+V.5+V.6+V.7+V.8+V.9 pipeline
# ──────────────────────────────────────────────────────

def run_full_roadmap_v_evaluation(
    df: pd.DataFrame,
    model: Any,
    X_train: pd.DataFrame | np.ndarray,
    y_train: np.ndarray,
    X_test: pd.DataFrame | np.ndarray,
    y_test: np.ndarray,
    returns: np.ndarray | None = None,
    feature_names: list[str] | None = None,
    pair: str = "",
    timeframe: str = "",
    model_name: str = "",
    rr_ratio: float = 1.0,
    run_mc: bool = False,
    quality_config: dict | None = None,
    d1_df: pd.DataFrame | None = None,
    h4_df: pd.DataFrame | None = None,
    h1_df: pd.DataFrame | None = None,
    news_active: bool = False,
    news_sentiment: str = "",
    model_confidence: float = 0.0,
    ensemble_predictions: list[str] | None = None,
    model_win_rate: float | None = None,
    model_recent_predictions: int = 0,
    signal: str = "HOLD",
) -> dict:
    """
    Ejecuta el ciclo completo: Quality Gate -> Regime Detection -> MTF Coherence ->
    Feature Importance -> Backtest Protocol -> Reliability Score.
    Retorna un dict combinado con todos los reportes.
    """
    result: dict = {"ok": True, "pair": pair, "timeframe": timeframe}

    # V.5 — Quality Gate
    approved, q_report = run_quality_gate(df, config=quality_config, pair=pair, timeframe=timeframe, verbose=False)
    result["quality"] = quality_gate_decision(q_report)
    if not approved:
        result["ok"] = False
        result["error"] = "Quality gate rechazado — entrenamiento bloqueado"
        return result

    # V.4 — Regime Detection
    regime = run_regime_detection(df, news_active=news_active, news_sentiment=news_sentiment,
                                  pair=pair, timeframe=timeframe, verbose=False)
    result["regime"] = regime.to_dict()

    # V.3 — MTF Coherence
    if d1_df is not None or h4_df is not None or h1_df is not None:
        mtf = run_mtf_coherence(d1_df=d1_df, h4_df=h4_df, h1_df=h1_df, pair=pair, verbose=False)
        result["mtf_coherence"] = mtf.to_dict()
        mtf_score = mtf.coherence_score
    else:
        mtf_score = None

    # V.6 — Feature Importance
    fi_report = run_feature_importance(
        model, X_train, y_train, X_test, y_test,
        feature_names=feature_names,
        pair=pair, timeframe=timeframe, model_name=model_name,
        verbose=False,
    )
    result["feature_importance"] = fi_report.to_dict()

    # V.9 — Backtest Protocol
    bt_report = run_backtest_protocol(
        model, X_test, y_test,
        returns=returns,
        model_name=model_name,
        pair=pair, timeframe=timeframe,
        rr_ratio=rr_ratio,
        run_monte_carlo=run_mc,
        verbose=False,
    )
    result["backtest"] = bt_report.to_dict()

    # V.8 — Reliability Score
    reliability = run_reliability_score(
        model_confidence=model_confidence,
        ensemble_predictions=ensemble_predictions,
        mtf_coherence_score=mtf_score,
        regime_primary=regime.primary,
        regime_confidence=regime.confidence,
        news_active=news_active,
        news_sentiment=news_sentiment,
        volatility_level=regime.volatility_level,
        model_win_rate=model_win_rate,
        model_recent_predictions=model_recent_predictions,
        signal=signal,
        verbose=False,
    )
    result["reliability"] = reliability.to_dict()

    # V.1 — Decision Engine
    decision = run_decision_engine(
        ensemble_signal=signal,
        model_confidence=model_confidence,
        ensemble_predictions=ensemble_predictions,
        regime=regime,
        mtf=MTFCoherenceResult(
            coherence_score=mtf_score or 0,
            coherent=(mtf_score or 0) >= 65,
            forced_hold=(mtf_score or 0) < 65,
        ) if mtf_score is not None else None,
        news_active=news_active,
        news_sentiment=news_sentiment,
        volatility_level=regime.volatility_level,
        model_win_rate=model_win_rate,
        model_recent_predictions=model_recent_predictions,
        pair=pair,
        timeframe=timeframe,
        verbose=False,
    )
    result["decision"] = decision.to_dict()

    # V.2 — Risk Engine
    if decision.decision in ("BUY", "SELL"):
        entry_price = float(df["close"].iloc[-1]) if "close" in df.columns else 0.0
        atr_val = float(df["atr_14"].iloc[-1]) if "atr_14" in df.columns else 0.0
        risk = run_risk_engine(
            decision=decision.decision,
            entry_price=entry_price,
            atr=atr_val,
            reliability_score=reliability.reliability_score,
            model_win_rate=model_win_rate or 0.5,
            regime=regime.primary,
            pair=pair,
            timeframe=timeframe,
            verbose=False,
        )
        result["risk"] = risk.to_dict()

    return result


# ──────────────────────────────────────────────────────
# CLI commands for main.py integration
# ──────────────────────────────────────────────────────

def cmd_quality(args: str = "") -> str:
    """Comando CLI: quality <csv_path> [pair] [timeframe]"""
    parts = args.strip().split()
    if not parts:
        return "Uso: quality <csv_path> [pair] [timeframe]"
    filepath = parts[0]
    pair = parts[1] if len(parts) > 1 else ""
    timeframe = parts[2] if len(parts) > 2 else ""

    analyzer = QualityAnalyzer()
    report = analyzer.analyze_csv(filepath, pair=pair, timeframe=timeframe)
    return cmd_quality_report(report)


def cmd_backtest(args: str = "") -> str:
    """Comando CLI: backtest <model_name> <csv_path> [pair] [timeframe]"""
    parts = args.strip().split()
    if len(parts) < 2:
        return "Uso: backtest <model_name> <csv_path> [pair] [timeframe]"
    return f"Backtest protocol: usar desde el pipeline de entrenamiento. Modelo={parts[0]}, CSV={parts[1]}"


def cmd_feature_importance(args: str = "") -> str:
    """Comando CLI: feature_importance <model_name> <csv_path> [pair]"""
    parts = args.strip().split()
    if len(parts) < 2:
        return "Uso: feature_importance <model_name> <csv_path> [pair]"
    return f"Feature importance: usar desde el pipeline de entrenamiento. Modelo={parts[0]}, CSV={parts[1]}"


def cmd_regime(args: str = "") -> str:
    """Comando CLI: regime <csv_path> [pair] [timeframe]"""
    parts = args.strip().split()
    if not parts:
        return "Uso: regime <csv_path> [pair] [timeframe]"
    filepath = parts[0]
    pair = parts[1] if len(parts) > 1 else ""
    timeframe = parts[2] if len(parts) > 2 else ""
    try:
        df = pd.read_csv(filepath)
        assessment = run_regime_detection(df, pair=pair, timeframe=timeframe, verbose=False)
        return cmd_regime_report(assessment, pair=pair, timeframe=timeframe)
    except Exception as e:
        return f"Error: {e}"


def cmd_mtf(args: str = "") -> str:
    """Comando CLI: mtf <d1_csv> <h4_csv> <h1_csv> [pair]"""
    parts = args.strip().split()
    if len(parts) < 3:
        return "Uso: mtf <d1_csv> <h4_csv> <h1_csv> [pair]"
    pair = parts[3] if len(parts) > 3 else ""
    try:
        d1 = pd.read_csv(parts[0])
        h4 = pd.read_csv(parts[1])
        h1 = pd.read_csv(parts[2])
        result = run_mtf_coherence(d1_df=d1, h4_df=h4, h1_df=h1, pair=pair, verbose=False)
        return cmd_mtf_report(result, pair=pair)
    except Exception as e:
        return f"Error: {e}"


def cmd_reliability(args: str = "") -> str:
    """Comando CLI: reliability <confidence> [signal] [mtf_score] [regime]"""
    parts = args.strip().split()
    if not parts:
        return "Uso: reliability <confidence> [signal=BUY] [mtf_score=50] [regime=ranging]"
    try:
        confidence = float(parts[0])
        signal = parts[1] if len(parts) > 1 else "BUY"
        mtf_score = float(parts[2]) if len(parts) > 2 else 50.0
        regime = parts[3] if len(parts) > 3 else "ranging"
        report = run_reliability_score(
            model_confidence=confidence,
            mtf_coherence_score=mtf_score,
            regime_primary=regime,
            signal=signal,
            verbose=False,
        )
        return cmd_reliability_report(report)
    except Exception as e:
        return f"Error: {e}"


def cmd_decision(args: str = "") -> str:
    """Comando CLI: decision <signal> <confidence> [regime] [mtf_score]"""
    parts = args.strip().split()
    if len(parts) < 2:
        return "Uso: decision <signal> <confidence> [regime=trending_bullish] [mtf_score=70]"
    try:
        signal = parts[0].upper()
        confidence = float(parts[1])
        regime_str = parts[2] if len(parts) > 2 else "ranging"
        mtf_score = float(parts[3]) if len(parts) > 3 else 50.0
        regime = RegimeAssessment(primary=regime_str, confidence=70.0, volatility_level="normal")
        mtf = MTFCoherenceResult(coherence_score=mtf_score, coherent=mtf_score >= 65, forced_hold=mtf_score < 65)
        result = run_decision_engine(
            ensemble_signal=signal,
            model_confidence=confidence,
            regime=regime,
            mtf=mtf,
            pair="CLI",
            timeframe="H1",
            verbose=False,
        )
        return cmd_decision_report(result)
    except Exception as e:
        return f"Error: {e}"


def cmd_risk(args: str = "") -> str:
    """Comando CLI: risk <decision> <entry_price> <atr> [reliability] [regime] [pair]"""
    parts = args.strip().split()
    if len(parts) < 3:
        return "Uso: risk <BUY|SELL> <entry_price> <atr> [reliability=70] [regime=trending_bullish] [pair=EURUSD]"
    try:
        decision = parts[0].upper()
        entry = float(parts[1])
        atr = float(parts[2])
        reliability = float(parts[3]) if len(parts) > 3 else 70.0
        regime = parts[4] if len(parts) > 4 else "trending_bullish"
        pair = parts[5] if len(parts) > 5 else "EURUSD"
        risk = run_risk_engine(
            decision=decision,
            entry_price=entry,
            atr=atr,
            reliability_score=reliability,
            regime=regime,
            pair=pair,
            timeframe="H1",
            verbose=False,
        )
        return cmd_risk_report(risk)
    except Exception as e:
        return f"Error: {e}"


# ──────────────────────────────────────────────────────
# V.11 — Dataset Update Integration
# ──────────────────────────────────────────────────────

def run_dataset_update(
    pair: str,
    timeframe: str = "H1",
    data_dir: str = "data/forex",
    force_full: bool = False,
    verbose: bool = True,
) -> dict:
    """Ejecuta V.11 Dataset Updater."""
    updater = DatasetUpdater(data_dir=data_dir)
    result = updater.update_pair(pair, timeframe, force_full=force_full)
    if verbose:
        print(f"\n  [V.11] Dataset Update — {pair} {timeframe}")
        print(f"    Rows: {result.rows_before} → {result.rows_after} (+{result.new_rows})")
        print(f"    Last: {result.last_timestamp}")
        print(f"    Duration: {result.duration_sec:.2f}s")
        if result.error:
            print(f"    Error: {result.error}")
    return result.to_dict()


# ──────────────────────────────────────────────────────
# V.12 — Scheduler Integration
# ──────────────────────────────────────────────────────

def run_scheduler_status(verbose: bool = True) -> dict:
    """Obtiene estado del V.12 Scheduler."""
    mgr = TaskManager()
    status = mgr.get_status()
    if verbose:
        print(f"\n  [V.12] Scheduler — running={status['running']}, tasks={status['task_count']}")
        for name, t in status["tasks"].items():
            print(f"    {name}: {t['last_status']} (runs={t['run_count']}, errors={t['error_count']})")
    return status


# ──────────────────────────────────────────────────────
# V.13 — Adaptive Retrain Integration
# ──────────────────────────────────────────────────────

def run_retrain_check(
    pair: str,
    current_win_rate: float | None = None,
    model_name: str = "",
    current_accuracy: float | None = None,
    new_rows_count: int = 0,
    last_regime: str = "",
    current_regime: str = "",
    verbose: bool = True,
) -> dict:
    """Ejecuta V.13 Retrain Manager check."""
    mgr = RetrainManager()
    decision = mgr.check_retrain_needed(
        pair=pair,
        current_win_rate=current_win_rate,
        model_name=model_name,
        current_accuracy=current_accuracy,
        new_rows_count=new_rows_count,
        last_regime=last_regime,
        current_regime=current_regime,
    )
    if verbose:
        print(f"\n  [V.13] Retrain Check — {pair}")
        print(f"    Needed: {decision.needed}")
        print(f"    Trigger: {decision.trigger.value}")
        print(f"    Reason: {decision.reason}")
    return decision.to_dict()


# ──────────────────────────────────────────────────────
# V.10 — Market Sentinel Integration
# ──────────────────────────────────────────────────────

def run_sentinel_status(verbose: bool = True) -> dict:
    """Obtiene estado del V.10 Market Sentinel."""
    sentinel = MarketSentinel()
    status = sentinel.get_status()
    if verbose:
        print(f"\n  [V.10] Market Sentinel — state={status['state']}")
        print(f"    Assets: {status['assets_monitored']}")
        print(f"    Total scans: {status['total_scans']}")
        print(f"    Circuit breaker: {status['circuit_breaker_active']}")
    return status


# ──────────────────────────────────────────────────────
# V.14 — Outcome Tracker Integration
# ──────────────────────────────────────────────────────

def run_outcome_stats(pair: str = "", verbose: bool = True) -> dict:
    """Obtiene estadisticas del V.14 Outcome Tracker."""
    tracker = OutcomeTracker()
    stats = tracker.get_stats(pair=pair)
    if verbose:
        print(f"\n  [V.14] Outcome Stats — {pair or 'ALL'}")
        print(f"    Total: {stats.total_predictions}")
        print(f"    Evaluated: {stats.evaluated}")
        print(f"    Win rate: {stats.win_rate:.1%}")
        print(f"    Avg reliability: {stats.avg_reliability:.1f}")
    return stats.to_dict()


# ──────────────────────────────────────────────────────
# V.15 — Notifications Integration
# ──────────────────────────────────────────────────────

def run_notification(
    pair: str,
    signal: str,
    reliability_score: float,
    explanation: str = "",
    stop_loss: float = 0.0,
    take_profit: float = 0.0,
    regime: str = "",
    risk_level: str = "",
    factors_for: list[str] | None = None,
    factors_against: list[str] | None = None,
    enabled_channels: list[str] | None = None,
    verbose: bool = True,
) -> list[dict]:
    """Ejecuta V.15 Notifier."""
    config = {"enabled_channels": enabled_channels or ["console"], "reliability_threshold": 0}
    notifier = Notifier(config=config)
    results = notifier.send(
        pair=pair,
        signal=signal,
        reliability_score=reliability_score,
        explanation=explanation,
        stop_loss=stop_loss,
        take_profit=take_profit,
        regime=regime,
        risk_level=risk_level,
        factors_for=factors_for or [],
        factors_against=factors_against or [],
        force=True,
    )
    if verbose:
        print(f"\n  [V.15] Notification — {pair} {signal} R={reliability_score}")
        for r in results:
            print(f"    {r.channel}: {'OK' if r.success else 'FAIL — ' + r.error}")
    return [r.to_dict() for r in results]


# ──────────────────────────────────────────────────────
# V.18 — Portfolio Intelligence Integration
# ──────────────────────────────────────────────────────

def run_portfolio_ranking(
    opportunities: list[dict],
    filter_signal: str = "",
    min_reliability: float = 0.0,
    top_n: int = 10,
    verbose: bool = True,
) -> dict:
    """Ejecuta V.18 Portfolio Ranker."""
    ranker = PortfolioRanker()
    ranking = ranker.rank(
        opportunities=opportunities,
        filter_signal=filter_signal,
        min_reliability=min_reliability,
        top_n=top_n,
    )
    if verbose:
        print(f"\n  [V.18] Portfolio Ranking — {ranking.active_signals} active signals")
        for o in ranking.ranking:
            print(f"    #{o.rank} {o.pair} {o.signal} R={o.reliability_score:.1f} Score={o.composite_score:.1f} ({o.regime})")
    return ranking.to_dict()


# ──────────────────────────────────────────────────────
# Self-test
# ──────────────────────────────────────────────────────

if __name__ == "__main__":
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split

    np.random.seed(42)
    n = 500
    dates = pd.date_range("2024-01-01", periods=n, freq="h")
    df = pd.DataFrame({
        "timestamp": dates,
        "open": np.random.randn(n) * 0.01 + 1.0,
        "high": np.random.randn(n) * 0.01 + 1.01,
        "low": np.random.randn(n) * 0.01 + 0.99,
        "close": np.random.randn(n) * 0.01 + 1.0,
        "volume": np.random.randint(100, 10000, n),
        "rsi_14": np.random.uniform(0, 100, n),
        "macd": np.random.randn(n) * 0.001,
        "macd_signal": np.random.randn(n) * 0.001,
        "macd_histogram": np.random.randn(n) * 0.001,
        "atr_14": np.abs(np.random.randn(n)) * 0.005,
        "ema_20": np.random.randn(n) * 0.01 + 1.0,
        "ema_50": np.random.randn(n) * 0.01 + 1.0,
        "ema_150": np.random.randn(n) * 0.01 + 1.0,
    })

    feature_cols = [c for c in df.columns if c != "timestamp"]
    X = df[feature_cols].values
    y = np.random.choice([0, 1, 2], n, p=[0.4, 0.35, 0.25])
    returns = np.random.randn(n) * 0.02

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
    ret_test = returns[len(X_train):]

    model = RandomForestClassifier(n_estimators=50, random_state=42)
    model.fit(X_train, y_train)

    result = run_full_roadmap_v_evaluation(
        df=df,
        model=model,
        X_train=df[feature_cols].iloc[:len(X_train)],
        y_train=y_train,
        X_test=df[feature_cols].iloc[len(X_train):],
        y_test=y_test,
        returns=ret_test,
        feature_names=feature_cols,
        pair="EURUSD",
        timeframe="H1",
        model_name="RandomForest",
        run_mc=True,
    )

    print(f"\n  Result: ok={result['ok']}")
    print(f"  Quality: score={result['quality']['score']}, approved={result['quality']['approved']}")
    print(f"  Features: optimal={result['feature_importance']['optimal_count']}/{result['feature_importance']['total_features']}")
    print(f"  Backtest: accuracy={result['backtest']['metrics']['accuracy']:.4f}, win_rate={result['backtest']['metrics']['win_rate']:.2%}")
    if result['backtest'].get('monte_carlo'):
        print(f"  Monte Carlo: prob_profit={result['backtest']['monte_carlo']['prob_profit']:.1%}")
    print("\n  Integration test passed.")
