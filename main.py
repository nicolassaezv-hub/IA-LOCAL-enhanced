# main.py

import os
import subprocess
import json
from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)

# ── Lazy imports to keep startup fast ──────────────────────
from memory import init_db, log_command, guardar_memoria
from project_memory import (
    init_project_db, session_summary, auto_register_forex_model,
    cmd_list_models, cmd_list_projects, cmd_list_tasks,
    save_project, update_project_status, add_task, complete_task,
    get_pending_tasks, list_models, get_model
)
from signal_tracker import (
    init_signal_db, save_signal, cmd_signal_history, cmd_signal_stats
)
from forex_watcher import (
    cmd_watch_start, cmd_watch_stop, cmd_watch_status, cmd_watch_check
)
from active_engine import (
    cmd_schedule_forex, cmd_schedule_stop, cmd_schedule_status, cmd_schedule_run
)
from news_intelligence import (
    cmd_news, cmd_news_predict
)

from prediction_lab.prompt_analyzer import cmd_lab_analiza
from prediction_lab.dataset_analyzer import cmd_lab_dataset
from prediction_lab.feasibility_engine import cmd_lab_viabilidad
from prediction_lab.model_planner import cmd_lab_planea
from prediction_lab.pipeline_generator import cmd_lab_genera
from prediction_lab.validation_engine import cmd_lab_valida
from prediction_lab.report_generator import cmd_lab_reporte, cmd_lab_proyectos, cmd_lab_info_proyecto
from feedback import (
    cmd_feedback_votar, cmd_feedback_ver, cmd_feedback_analisis, cmd_feedback_dashboard,
    cmd_thresholds_ver, cmd_contextual_memory, cmd_evolution_history,
)
from evolution import (
    cmd_monitor_snapshot, cmd_monitor_historial,
    cmd_mejoras_detectar, cmd_evolucionar,
    cmd_proposals_ver, cmd_aplicar_propuesta,
)
# Fase 8 (Constitucion): reemplaza el aprobar/rechazar "ciego" de Fase 7 por un
# flujo que valida contra reglas constitucionales y crea un rollback point real
# antes de aprobar. cmd_aprobar_propuesta/cmd_rechazar_propuesta de evolution/
# quedan sin usar (se conservan ahi por compatibilidad de imports internos).
from constitution import (
    cmd_aprobar_propuesta, cmd_rechazar_propuesta,
    cmd_reglas_ver, cmd_validar_propuesta, cmd_audit_log,
    cmd_rollback_ver, cmd_rollback_aplicar,
)
# Fase 9 (Ciclo Evolutivo): orquesta monitor->detector->proposer->constitucion->
# aprobacion->feedback->audit en un solo comando ('evolucionar ciclo').
from evolutionary_cycle import cmd_ciclo_evolutivo, cmd_health_report
# ── Roadmap V — Forex Lab Avanzado ─────────────────────────────────
from forex.prediction.roadmap_v_integration import (
    cmd_quality, cmd_backtest, cmd_feature_importance,
    cmd_regime, cmd_mtf, cmd_reliability, cmd_decision, cmd_risk,
    cmd_dataset_update, cmd_scheduler_status,
    cmd_retrain_check, cmd_retrain_history,
    cmd_sentinel_status, cmd_sentinel_signals,
    cmd_outcome_stats, cmd_outcome_history,
    cmd_notify_test, cmd_notify_log,
    cmd_portfolio_ranking, cmd_portfolio_export,
)
_HAS_ROADMAP_V = True

# ── Roadmap VI — Autonomización & Data Intelligence ─────────────────
from forex.prediction.hyperparameter_cache import get_cache as _get_hparam_cache
from forex.prediction.adaptive_trainer import get_adaptive_trainer as _get_adaptive_trainer
from forex.prediction.model_cache import get_model_cache as _get_model_cache
from forex.prediction.model_quality_history import get_quality_history as _get_quality_history
from forex.prediction.candlestick_patterns import get_detector as _get_candle_detector, detect_patterns
from forex.portfolio.opportunity_score import get_ranker as _get_op_ranker, SignalInput
from forex.data.data_router import DataRouter, fetch_data
from forex.data.csv_migrator import migrate_csv, list_active_csvs, scan_csv_directory
from forex.data.rolling_dataset import get_rolling_dataset
from forex.data.yahoo_provider import get_yahoo_provider
from forex.data.binance_provider import get_binance_provider
from forex.scheduler.autonomous_scheduler import get_scheduler as _get_scheduler
from forex.scheduler.auto_updater import get_auto_updater as _get_auto_updater
from check_system import run_self_test as _run_self_test
_HAS_ROADMAP_VI = True

# ── Doctor, API interna, Dev Log ────────────────────────────────────
try:
    from astra_doctor import run_doctor as _run_doctor
    _HAS_DOCTOR = True
except ImportError:
    _HAS_DOCTOR = False

try:
    from astra_api import start_api_server as _start_api, stop_api_server as _stop_api
    from astra_api import is_api_running as _api_running, api_status as _api_status_str
    from astra_api import _PORT as _ASTRA_API_PORT
    _HAS_API = True
except ImportError:
    _HAS_API = False

try:
    from dev_log import cmd_dev_log as _cmd_dev_log
    _HAS_DEV_LOG = True
except ImportError:
    _HAS_DEV_LOG = False

import re as _re_lab
from datetime import datetime

_ANSI_STRIP_RE = _re_lab.compile(r'\x1b\[[0-9;]*m')


def _parse_lab_args(rest: str):
    """Parsea 'lab <sub> <csv> "<idea>" [target_col]' -> (csv_path, idea, target_variable|None).
    El target es opcional: cuando el dataset no permite inferir la columna
    objetivo por heurística de nombres, se puede pasar explícito al final."""
    rest = rest.strip()
    m = _re_lab.match(r'^(\S+)\s+["\'](.+?)["\'](?:\s+(\S+))?\s*$', rest)
    if not m:
        return None, None, None
    csv_path, idea, target = m.group(1), m.group(2), m.group(3)
    return csv_path, idea, target



from io_files import leer_pdf, leer_word, leer_excel, leer_csv, escribe_pdf, escribe_word, escribe_excel, escribe_csv
from ai_models import ask_openai, system_status, torch_demo, tensorflow_demo, keras_demo, sklearn_demo, calcular_integral, entrenar_modelo_sklearn
from web_tools import extrae_web, traducir, descargar_youtube, httpx_demo, aiohttp_demo, socketio_demo, fastapi_demo, flask_demo, subir_archivo_azure, consumir_api_grpc
from audio_video import voz_a_texto, texto_a_voz, analiza_audio, reproducir_audio, convertir_audio, descargar_audio_youtube
from visualization import grafica_csv, mostrar_tabla, mostrar_rich, crear_pdf, procesar_imagen_skimage, mostrar_gui_pyqt
from security import cifra_archivo, hash_password, verify_password, passlib_hash, passlib_verify, crear_jwt, verificar_jwt, paramiko_demo
from utils import system_status as utils_status, barra_progreso, tarea_programada, simular_tecla, simular_click, bloquear_archivo, iniciar_monitor, obtener_fecha_arrow, serializar_orjson
from progress_utils import show_progress, progress_steps, progress_iterator
from modules_extra import comandos_extra
from tool_registry import TOOLS
from intent_router import classify_intent
from astra_agent import process_request

# ── Forex imports ───────────────────────────────────────────
from forex.market_universe import (
    get_all_forex_pairs, get_all_commodities,
    normalize_symbol, is_supported_market, get_market_type
)
from forex_analytics import analyze_market_file, market_history, compare_market_history
from forex.forex_memory import list_saved_markets, save_analysis
from forex.forex_report import ForexReport

# ── Business Intelligence imports ───────────────────────────
from forex.business.business_pipeline import BusinessPipeline

# Risk management
try:
    from forex.prediction.circuit_breaker import get_circuit_breaker, cmd_circuit_status, cmd_circuit_reset
    from forex.prediction.position_sizing import PositionSizer, cmd_position_size as _cmd_position_size
    _HAS_RISK = True
except ImportError:
    _HAS_RISK = False


def _print_banner():
    print(Fore.GREEN + "╔══════════════════════════════════════════╗")
    print(Fore.GREEN + "║        ASTRA  —  Modular AI System       ║")
    print(Fore.GREEN + "║  Forex · ML · Security · Documents · Web ║")
    print(Fore.GREEN + "╚══════════════════════════════════════════╝")
    print(Fore.CYAN  + f"  {len(TOOLS)} tools loaded  |  type 'ayuda' for commands\n")


# ─────────────────────────────────────────────────────────
# HELPER: extraer par del input del usuario
# ─────────────────────────────────────────────────────────
def _extract_pair(user_input: str) -> str | None:
    """Intenta extraer el par del comando (ej: 'full forex EURUSD.csv' → 'EURUSD')."""
    import re
    parts = user_input.upper().split()
    # Buscar patrón de par (6 letras tipo EURUSD, GBPJPY, AUDCAD)
    for p in parts:
        clean = re.sub(r"[^A-Z]", "", p)
        if len(clean) == 6 and clean.isalpha():
            return clean
    # Buscar dentro del nombre de archivo
    for p in parts:
        m = re.search(r"([A-Z]{6})", re.sub(r"[^A-Z]", "", p))
        if m:
            return m.group(1)
    return None


def _category_from_cmd(user_input: str) -> str:
    """Clasifica el tipo de comando."""
    u = user_input.lower()
    if any(k in u for k in ["forex", "train", "tune", "full", "scan", "predict", "backtest", "señal"]):
        return "forex"
    if any(k in u for k in ["circuit", "position size", "sizing", "risk"]):
        return "risk"
    if any(k in u for k in ["modelo", "model", "mis model"]):
        return "model"
    if any(k in u for k in ["schedule", "watch", "schedule"]):
        return "schedule"
    return "general"


def _summarize_result(respuesta) -> str:
    """Extrae un resumen de máx 400 chars del resultado de un comando."""
    import re
    if respuesta is None:
        return "(sin resultado)"
    text = json.dumps(respuesta, ensure_ascii=False) if isinstance(respuesta, dict) else str(respuesta)
    # Quitar códigos ANSI
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    text = re.sub(r'\[\d+[mA-Z]', '', text)
    # Quitar líneas de barras decorativas
    lines = [l.strip() for l in text.splitlines() if l.strip() and not re.match(r"^[═─╔╗╚╝╠╣╦╩╪│┼]+$", l.strip())]
    summary = " | ".join(lines[:6])
    return summary[:400]


def _print_result(respuesta):
    if isinstance(respuesta, dict):
        print(Fore.YELLOW + "ASTRA: " + Style.RESET_ALL)
        print(json.dumps(respuesta, indent=2, default=str, ensure_ascii=False))
    else:
        print(Fore.YELLOW + "ASTRA: " + Style.RESET_ALL + str(respuesta))


# ═══════════════════════════════════════════════════════════
#  FOREX HELPERS
# ═══════════════════════════════════════════════════════════

def _forex_train(csv_path: str):
    """Train ensemble model (XGBoost + LightGBM + RandomForest) on a CSV dataset."""
    from forex.prediction.integrated_pipeline import ForexIntegratedPipeline
    print(Fore.CYAN + f"\n[ASTRA] Training Ensemble Model on: {csv_path}" + Style.RESET_ALL)
    pipeline = ForexIntegratedPipeline()
    result = pipeline.train(csv_path)
    if isinstance(result, dict):
        # Registrar modelo en project_memory
        try:
            auto_register_forex_model(result, csv_path)
        except Exception:
            pass
        pair = result.get("pair", "?")
        acc  = result.get("accuracy", 0)
        prec = result.get("precision", 0)
        rows = result.get("rows_trained", 0)
        out  = (
            f"\n{Fore.GREEN}╔══ TRAINING COMPLETE ══╗{Style.RESET_ALL}\n"
            f"  Pair       : {pair}\n"
            f"  Rows used  : {rows}\n"
            f"  Accuracy   : {acc:.2%}\n"
            f"  Precision  : {prec:.2%}\n"
        )
        print(out)
        return ""
    return result


def _forex_predict(csv_path: str):
    """Run prediction using trained ensemble model on a CSV."""
    from forex.prediction.integrated_pipeline import ForexIntegratedPipeline
    show_progress("Running Forex Prediction", 2)
    pipeline = ForexIntegratedPipeline()
    result = pipeline.predict(csv_path)
    if isinstance(result, dict) and "error" not in result:
        try:
            save_signal(result, csv_path)
        except Exception:
            pass
        return _format_signal(result)
    return result


_REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prediction", "reports")


def _save_prediction_report(pair: str, csv_path: str, formatted_signal: str) -> str:
    """
    Guarda el reporte de una predicción individual como archivo de texto en
    prediction/reports/, nombrado por par + fecha + hora. Si el nombre ya
    existe (ej. mismo par analizado dos veces en el mismo segundo), agrega
    un sufijo numérico para no pisar reportes anteriores.
    """
    os.makedirs(_REPORTS_DIR, exist_ok=True)
    pair_clean = _re_lab.sub(r"[^A-Za-z0-9_]", "", (pair or "UNKNOWN").upper().replace("/", "_"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{pair_clean}_{stamp}"
    filename = f"{base_name}.txt"
    path = os.path.join(_REPORTS_DIR, filename)
    counter = 2
    while os.path.exists(path):
        filename = f"{base_name}_{counter}.txt"
        path = os.path.join(_REPORTS_DIR, filename)
        counter += 1

    header = (
        f"ASTRA — Reporte de Predicción Forex\n"
        f"Par/Commodity : {pair_clean}\n"
        f"Archivo CSV   : {csv_path}\n"
        f"Generado      : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"{'=' * 60}\n"
    )
    # Quita códigos ANSI de color para que el archivo de texto quede limpio.
    clean_signal = _ANSI_STRIP_RE.sub("", formatted_signal)
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + clean_signal + "\n")

    return path


def _forex_predict_multi(csv_paths: list):
    """
    Predicción sobre MÚLTIPLES CSVs en un solo comando. A diferencia de
    _forex_predict() (un archivo, solo se muestra en pantalla), aquí cada
    resultado se guarda ADEMÁS como un reporte de texto individual en
    prediction/reports/, nombrado por par + fecha + hora — para poder
    revisar/comparar después sin tener que re-correr el comando.
    """
    from forex.prediction.integrated_pipeline import ForexIntegratedPipeline

    pipeline = ForexIntegratedPipeline()
    lines = [Fore.CYAN + f"\n[ASTRA] ══ PREDICCIÓN MÚLTIPLE ({len(csv_paths)} archivos) ══" + Style.RESET_ALL]
    saved_paths = []
    errores = []

    for i, csv_path in enumerate(csv_paths, start=1):
        csv_path = csv_path.strip()
        if not csv_path:
            continue
        print(Fore.YELLOW + f"\n[{i}/{len(csv_paths)}] Prediciendo: {csv_path}..." + Style.RESET_ALL)
        try:
            result = pipeline.predict(csv_path)
        except Exception as e:
            errores.append(f"{csv_path}: {e}")
            lines.append(f"\n  ✗ {csv_path} → ERROR: {e}")
            continue

        if isinstance(result, dict) and "error" not in result:
            try:
                save_signal(result, csv_path)
            except Exception:
                pass
            pair = result.get("pair", os.path.splitext(os.path.basename(csv_path))[0])
            formatted = _format_signal(result)
            print(formatted)
            report_path = _save_prediction_report(pair, csv_path, formatted)
            saved_paths.append(report_path)
            action = result.get("action", "HOLD")
            conf = float(result.get("confidence", 0) or 0)
            lines.append(f"\n  ✓ {pair:<12} → {action:<5} (confianza {conf:.2f})  |  reporte: {os.path.relpath(report_path, os.path.dirname(os.path.abspath(__file__)))}")
        else:
            errores.append(f"{csv_path}: {result}")
            lines.append(f"\n  ✗ {csv_path} → {result}")

    lines.append(f"\n{'-' * 60}")
    lines.append(f"  Reportes guardados: {len(saved_paths)}/{len(csv_paths)}  en prediction/reports/")
    if errores:
        lines.append(f"  Errores: {len(errores)}")

    return "\n".join(lines)


def _forex_tune(csv_path: str):
    """Run Optuna hyperparameter search (~50 trials) then auto-train."""
    from forex.prediction.integrated_pipeline import ForexIntegratedPipeline
    print(Fore.CYAN + f"\n[ASTRA] Optuna Hyperparameter Search on: {csv_path}" + Style.RESET_ALL)
    print(Fore.YELLOW + "  This takes 5–15 min. Best params will be saved and auto-loaded next train." + Style.RESET_ALL)
    pipeline = ForexIntegratedPipeline()
    result = pipeline.tune(csv_path)
    if isinstance(result, dict):
        pair   = result.get("pair", "?")
        trials = result.get("best_trial", "?")
        score  = result.get("best_score", 0)
        out    = (
            f"\n{Fore.GREEN}╔══ TUNING COMPLETE ══╗{Style.RESET_ALL}\n"
            f"  Pair        : {pair}\n"
            f"  Best trial  : {trials}\n"
            f"  Best score  : {score:.4f}\n"
            f"  Params saved: models/forex/params/best_params_{pair}.json\n"
        )
        print(out)
        return ""
    return result


def _forex_multi(csv_path: str):
    """Consensus signal across multiple horizons (5/10/20 candles)."""
    from forex.prediction.integrated_pipeline import ForexIntegratedPipeline
    show_progress("Multi-Horizon Prediction", 3)
    pipeline = ForexIntegratedPipeline()
    result = pipeline.run(csv_path, mode="multi_horizon")
    if isinstance(result, dict):
        return _format_signal(result.get("consensus", result))
    return result


def _forex_scan(folder_or_files: str):
    """Scan all CSVs in a folder and rank BUY/SELL/HOLD signals."""
    from forex.prediction.multi_pair_scanner import MultiPairScanner
    show_progress("Scanning All Pairs", 2)
    scanner = MultiPairScanner()
    paths   = [p.strip() for p in folder_or_files.split(",") if p.strip()]
    if len(paths) == 1 and not paths[0].lower().endswith(".csv"):
        report = scanner.scan_folder(paths[0])
    else:
        report = scanner.scan(paths)
    scanner.print_report(report)
    return scanner.astra_summary(report)


def _format_signal(result: dict) -> str:
    """Pretty-print a BUY/SELL/HOLD signal dict."""
    action   = result.get("action",         "HOLD")
    pair     = result.get("pair",           "?")
    conf     = result.get("confidence",     0)
    strength = result.get("signal_strength",0)
    regime   = result.get("regime",         "unknown")
    adx      = result.get("adx",            0)
    rows     = result.get("rows_processed", 0)
    reason   = result.get("hold_reason",    "")

    _COLOR = {"BUY": Fore.GREEN, "SELL": Fore.RED, "HOLD": Fore.YELLOW}
    _ICON  = {"BUY": "▲ BUY",  "SELL": "▼ SELL", "HOLD": "─ HOLD"}
    color  = _COLOR.get(action, Fore.WHITE)
    icon   = _ICON.get(action, action)

    bar_filled = int(strength / 10)
    bar        = "█" * bar_filled + "░" * (10 - bar_filled)

    lines = [
        f"\n{color}╔══ ASTRA FOREX SIGNAL ══╗{Style.RESET_ALL}",
        f"  Signal     : {color}{icon}{Style.RESET_ALL}",
        f"  Pair       : {pair}",
        f"  Confidence : {conf:.2f}",
        f"  Strength   : [{bar}] {strength:.1f}/100",
        f"  ADX        : {adx:.1f}",
        f"  Regime     : {regime}",
        f"  Rows       : {rows}",
    ]
    if reason:
        lines.append(f"  Hold reason: {reason}")
    lines.append("")
    return "\n".join(lines)


def _forex_backtest(csv_path: str):
    """Run backtester on held-out test portion of CSV."""
    from forex.prediction.integrated_pipeline import ForexIntegratedPipeline
    show_progress("Running Backtest", 3)
    pipeline = ForexIntegratedPipeline()
    return pipeline.backtest(csv_path)


def _resolve_mtf_paths(csv_h1: str):
    """
    Dado un CSV H1 (ej. CSVs/H1/EURUSD.csv) busca automaticamente
    H4 y D1 del mismo par en carpetas hermanas (CSVs/H4/, CSVs/D1/).
    Retorna (path_h4, path_d1) — None si no existen.
    """
    import os
    basename = os.path.basename(csv_h1)
    parent   = os.path.dirname(os.path.dirname(os.path.abspath(csv_h1)))
    path_h4, path_d1 = None, None
    for folder in os.listdir(parent):
        full = os.path.join(parent, folder, basename)
        if folder.upper() in ("H4", "4H", "M240") and os.path.exists(full):
            path_h4 = full
        elif folder.upper() in ("D1", "D", "1D", "DAILY") and os.path.exists(full):
            path_d1 = full
    return path_h4, path_d1


def _register_analyzed_market(pair: str, train_r: dict, pred_r: dict, back_r: dict) -> None:
    """
    Registra el par/commodity en 'mercados analizados' (forex_memory) usando
    UNICAMENTE datos reales ya calculados por el pipeline (nada inventado).
    Se llama automaticamente al final de 'full forex' para que CUALQUIER
    par/commodity de market_universe quede registrado tras su primer analisis.
    """
    try:
        action   = pred_r.get("action", "HOLD") if isinstance(pred_r, dict) else "HOLD"
        trend    = {"BUY": "alcista", "SELL": "bajista", "HOLD": "neutral"}.get(action, "neutral")
        conf     = float(pred_r.get("confidence", 0) or 0) if isinstance(pred_r, dict) else 0.0
        adx      = pred_r.get("adx", 0) if isinstance(pred_r, dict) else 0
        regime   = pred_r.get("regime", "unknown") if isinstance(pred_r, dict) else "unknown"
        strength = pred_r.get("signal_strength", 0) if isinstance(pred_r, dict) else 0

        acc  = train_r.get("accuracy", 0) if isinstance(train_r, dict) else 0
        prec = train_r.get("precision", 0) if isinstance(train_r, dict) else 0
        rows = train_r.get("rows", 0) if isinstance(train_r, dict) else 0
        wfv  = train_r.get("wfv", {}) if isinstance(train_r, dict) else {}

        trades = back_r.get("total_trades", 0) if isinstance(back_r, dict) else 0
        wr     = back_r.get("win_rate", 0) if isinstance(back_r, dict) else 0
        pf     = back_r.get("profit_factor", 0) if isinstance(back_r, dict) else 0

        technical = (f"ADX={adx:.1f}  Regimen={regime}  Fuerza señal={strength:.1f}/100  "
                     f"Filas entrenamiento={rows}")
        summary = (f"Modelo entrenado con accuracy={acc:.2%}, precision={prec:.2%} "
                   f"(WFV avg={wfv.get('avg_precision', 0):.2%}). "
                   f"Backtest: {trades} trades, win rate={wr:.1%}, profit factor={pf:.2f}. "
                   f"Última señal: {action} (confianza {conf:.2f}).")

        report = ForexReport(
            symbol=pair,
            market_type=get_market_type(pair),
            trend=trend,
            confidence=conf,
            technical_analysis=technical,
            ai_summary=summary,
            source="full_forex_pipeline",
            metadata={"accuracy": acc, "precision": prec, "rows": rows,
                      "wfv_avg_precision": wfv.get("avg_precision", 0),
                      "backtest_trades": trades, "backtest_win_rate": wr,
                      "backtest_profit_factor": pf},
        )
        save_analysis(report)
    except Exception:
        pass


def _forex_full(csv_path: str):
    """Pipeline completo con benchmark automatico."""
    import time as _bench_time
    _bench_start = _bench_time.time()
    _bench_pair = _extract_pair(csv_path) or "UNKNOWN"
    try:
        from robustness.pipeline_benchmark import get_benchmark
        _bench = get_benchmark()
    except Exception:
        _bench = None
    """
    Pipeline completo: tune -> train -> predict -> backtest.
    Detecta automaticamente H4 y D1 si existen en carpetas hermanas.
    """
    from forex.prediction.integrated_pipeline import (
        ForexIntegratedPipeline,
        PREDICTION_TIMEFRAME,
    )

    path_h4, path_d1 = _resolve_mtf_paths(csv_path)

    mtf_parts = []
    if path_h4: mtf_parts.append(f"H4: {path_h4}")
    if path_d1: mtf_parts.append(f"D1: {path_d1}")
    mtf_str = ("  MTF: " + " | ".join(mtf_parts)) if mtf_parts else "  MTF: no encontrado (solo H1)"

    print(Fore.CYAN + "\n[ASTRA] ══ FULL FOREX PIPELINE ══" + Style.RESET_ALL)
    print(f"  H1 : {csv_path}")
    print(mtf_str)
    print()

    pipeline = ForexIntegratedPipeline()

    # ── 1/4 TUNE ──────────────────────────────────────────────
    print(Fore.YELLOW + "[1/4] Optimizando hiperparametros (Optuna)..." + Style.RESET_ALL)
    tune_r = pipeline.tune(csv_path, path_h4=path_h4, path_d1=path_d1)
    if isinstance(tune_r, dict) and "error" not in tune_r:
        print(Fore.GREEN + f"     Tune OK  precision: {tune_r.get('precision',0):.2%}" + Style.RESET_ALL)
    else:
        print(Fore.YELLOW + "     Tune omitido o fallo  continuando con defaults" + Style.RESET_ALL)

    # ── 2/4 TRAIN ─────────────────────────────────────────────
    print(Fore.YELLOW + "\n[2/4] Entrenando ensemble (XGB + LGB + RF)..." + Style.RESET_ALL)
    train_r = pipeline.train(csv_path, path_h4=path_h4, path_d1=path_d1)
    # Registrar modelo en project_memory automáticamente
    try:
        auto_register_forex_model(train_r, csv_path)
    except Exception:
        pass
    if isinstance(train_r, dict):
        pair   = train_r.get("pair",        "?")
        acc    = train_r.get("accuracy",     0)
        prec   = train_r.get("precision",    0)
        rows   = train_r.get("rows",         0)
        valid  = train_r.get("model_valid",  False)
        mtf_f  = train_r.get("mtf_features", 0)
        wfv    = train_r.get("wfv",          {})
        wfv_p  = wfv.get("avg_precision",    0)
        wfv_m  = wfv.get("median_precision", 0)
        wfv_ok = wfv.get("wfv_passed",       False)
        col    = Fore.GREEN if valid else Fore.RED
        print(f"     Par      : {pair}")
        print(f"     Filas    : {rows}  |  Features: {train_r.get('features',0)} ({mtf_f} MTF)")
        print(f"     Accuracy : {acc:.2%}  |  Precision: {prec:.2%}  [{col}{'VALIDO' if valid else 'INVALIDO < 65%'}{Style.RESET_ALL}]")
        print(f"     WFV avg  : {wfv_p:.2%}  median: {wfv_m:.2%}  [{'OK' if wfv_ok else 'BAJO'}]")

        # BUGFIX: si el WFV reprueba, train_with_wfv() ya no guarda el modelo
        # (ver xgb_trainer.py). Sin esto, predict() caía al modelo "latest
        # genérico" de OTRO par y mostraba una señal real pero con el modelo
        # equivocado, sin avisar. Ahora se bloquea explícitamente aquí.
        if wfv.get("model_deployed") is False:
            print(Fore.RED + f"\n[BLOQUEADO] El modelo de {pair} reprobó Walk-Forward "
                  f"Validation y NO fue guardado." + Style.RESET_ALL)
            print(Fore.RED + f"            No se genera señal ni backtest — evita usar "
                  f"por error el modelo genérico de otro par." + Style.RESET_ALL)
            print(Fore.YELLOW + f"            Sugerencia: 'tune forex {csv_path}' para "
                  f"optimizar hiperparámetros y reintenta 'full forex'." + Style.RESET_ALL)
            return ""
    else:
        print(Fore.RED + f"     Entrenamiento fallo: {train_r}" + Style.RESET_ALL)
        return ""

    # ── 3/4 PREDICT ───────────────────────────────────────────
    print(Fore.YELLOW + "\n[3/4] Generando senal de la ultima vela..." + Style.RESET_ALL)
    pred_r = pipeline.predict(csv_path, path_h4=path_h4, path_d1=path_d1)
    signal_id = None
    if isinstance(pred_r, dict) and "error" not in pred_r:
        try:
            # BUGFIX: el id real de la señal (fila de forex_signals) se
            # descartaba silenciosamente — sin él el usuario no tenía forma
            # de referenciar esta señal específica para votar feedback después.
            signal_id = save_signal(pred_r, csv_path)
        except Exception:
            pass
        print(_format_signal(pred_r))
        if signal_id is not None:
            pair_clean = (pred_r.get("pair") or "UNKNOWN").upper().replace("/", "").replace("_", "")
            fb_target = f"{pair_clean}_{signal_id}"
            print(f"  Signal ID  : {fb_target}   (usa 'feedback votar {fb_target} 1|-1' para calificarla)")
    else:
        print(pred_r)

    # ── 4/4 BACKTEST ──────────────────────────────────────────
    print(Fore.YELLOW + "[4/4] Backtesting sobre datos historicos..." + Style.RESET_ALL)
    back_r = pipeline.backtest(csv_path, path_h4=path_h4, path_d1=path_d1)
    if isinstance(back_r, dict) and "error" not in back_r:
        trades = back_r.get("total_trades",   0)
        wr     = back_r.get("win_rate",        0)
        pf     = back_r.get("profit_factor",   0)
        er     = back_r.get("expected_return", 0)
        print(f"     Trades: {trades}  |  Win Rate: {wr:.1%}  |  PF: {pf:.2f}  |  E[R]: {er:.4f}")
    elif isinstance(back_r, dict):
        print(Fore.YELLOW + f"     Backtest: {back_r.get('error','?')}" + Style.RESET_ALL)
    else:
        print(back_r)

    # Registrar el mercado en 'mercados analizados' con datos reales del pipeline
    pair_for_registry = (train_r.get("pair") if isinstance(train_r, dict) else None) or csv_path
    _register_analyzed_market(pair_for_registry, train_r if isinstance(train_r, dict) else {},
                               pred_r if isinstance(pred_r, dict) else {},
                               back_r if isinstance(back_r, dict) else {})

    print()
    print(Fore.GREEN + "[ASTRA] ══ FULL PIPELINE COMPLETADO ══" + Style.RESET_ALL)
    # Record pipeline benchmark before returning so the advertised evidence exists.
    if _bench:
        try:
            _total = _bench_time.time() - _bench_start
            _bench.record_stage(
                "total_pipeline",
                _total,
                _bench_pair,
                PREDICTION_TIMEFRAME,
                {"source": "full_forex"},
            )
        except Exception as exc:
            print(Fore.YELLOW + f"[WARN] Benchmark no registrado: {exc}" + Style.RESET_ALL)
    return ""

def _forex_analiza(csv_path: str, symbol: str):
    """Technical analytics report (RSI, MACD, EMA, volatility, etc.)."""
    show_progress("Running Technical Analysis", 3)
    return analyze_market_file(csv_path, symbol)


def _forex_lista():
    """List all supported Forex pairs and commodities."""
    pairs = get_all_forex_pairs()
    commodities = get_all_commodities()
    out  = Fore.GREEN + "\n═══ SUPPORTED FOREX PAIRS ═══\n" + Style.RESET_ALL
    out += "  " + "  |  ".join(pairs) + "\n"
    out += Fore.YELLOW + "\n═══ SUPPORTED COMMODITIES ═══\n" + Style.RESET_ALL
    out += "  " + "  |  ".join(commodities)
    print(out)
    return f"\nTotal: {len(pairs)} Forex pairs + {len(commodities)} commodities"


def _forex_historial(symbol: str):
    """Show past analyses saved for a symbol."""
    show_progress("Loading History", 1)
    sym = normalize_symbol(symbol)
    return market_history(sym)


def _forex_compara(symbol: str):
    """Compare last 5 analyses of a symbol."""
    show_progress("Comparing Reports", 1)
    sym = normalize_symbol(symbol)
    return compare_market_history(sym)


def _forex_mercados():
    """List all markets that have been analyzed."""
    return list_saved_markets()


# ═══════════════════════════════════════════════════════════
#  BUSINESS INTELLIGENCE HELPERS
# ═══════════════════════════════════════════════════════════

def _bi_analiza(csv_path: str):
    """KPI analysis: health score, financials, alerts — no ML needed."""
    show_progress("Running Business KPI Analysis", 3)
    pipeline = BusinessPipeline()
    return pipeline.analyze(csv_path)


def _bi_consulta(csv_path: str):
    """Full PYME consultant: KPIs + ML signal + recommendations."""
    print(Fore.CYAN + f"\n[ASTRA-BI] Business Consultant: {csv_path}" + Style.RESET_ALL)
    pipeline = BusinessPipeline()
    result   = pipeline.consult(csv_path)
    if isinstance(result, dict) and "error" not in result:
        return ""
    return result


def _bi_predice(csv_path: str):
    """ML forecast: will next period grow or decline?"""
    show_progress("Business Forecast", 2)
    pipeline = BusinessPipeline()
    result   = pipeline.predict(csv_path)
    if isinstance(result, dict) and "error" not in result:
        action = result.get("action",     "STABLE")
        conf   = result.get("confidence", 0)
        health = result.get("health_score", 50)
        risk   = result.get("risk_level", "MEDIUM")
        return (
            f"Forecast: {action}  |  Confidence: {conf:.2f}  |  "
            f"Health: {health}/100  |  Risk: {risk}"
        )
    return result


def _bi_forecast(csv_path: str, months: int = 6):
    """Revenue projection (optimistic/expected/conservative) N months ahead."""
    show_progress("Business Forecast Projection", 2)
    from sme_consultant import sme_forecast
    return sme_forecast(csv_path, months)


def _bi_entrena(csv_path: str):
    """Train ML model on business dataset."""
    print(Fore.CYAN + f"\n[ASTRA-BI] Training Business Model: {csv_path}" + Style.RESET_ALL)
    pipeline = BusinessPipeline()
    result   = pipeline.train(csv_path)
    if isinstance(result, dict):
        btype = result.get("business_type", "?")
        rows  = result.get("rows_trained",  0)
        acc   = result.get("accuracy",      0)
        prec  = result.get("precision",     0)
        out   = (
            f"\n{Fore.GREEN}╔══ BUSINESS MODEL TRAINED ══╗{Style.RESET_ALL}\n"
            f"  Type       : {btype}\n"
            f"  Rows used  : {rows}\n"
            f"  Accuracy   : {acc:.2%}\n"
            f"  Precision  : {prec:.2%}\n"
        )
        print(out)
        return ""
    return result


def _ayuda():
    help_text = f"""
{Fore.GREEN}╔══════════════════════════════════════════════════════════════╗
║                   ASTRA — COMMAND REFERENCE                   ║
╚══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}

{Fore.CYAN}── FOREX ──────────────────────────────────────────────────────{Style.RESET_ALL}
  tune forex <csv>               Hyperparameter search (Optuna, 5-15 min) then train
  train forex <csv>              Train ensemble model (XGB + LGBM + RF) on CSV
  predict forex <csv>            Predict BUY/SELL/HOLD signal from trained model
  predict forex <csv1>,<csv2>,... Predict multiple CSVs at once -> saves each report
                                  as .txt in prediction/reports/ (pair_fecha_hora.txt)
  multi forex <csv>              Consensus signal across 3 horizons (5/10/20 candles)
  backtest forex <csv>           Backtest model on held-out data
  full forex <csv>               Train + Predict + Backtest in one shot
  scan forex <folder>            Scan all CSVs in folder, rank signals by strength
  generar csvs forex [tf] [n]    Genera en lote CSVs Forex (Yahoo real -> sintético
                                  fallback). Ej: generar csvs forex H1,H4 800
                                  Alias: generate forex csvs / generar csvs forex sinteticos
  analiza forex <csv> <symbol>   Full technical report (RSI/MACD/EMA...)
  lista mercados                 Show all supported pairs & commodities
  historial forex <symbol>       View saved analysis history
  compara forex <symbol>         Compare last 5 analyses of a pair
  mercados analizados            List all markets ever analyzed

{Fore.CYAN}── BUSINESS INTELLIGENCE (PYME) ───────────────────────────────{Style.RESET_ALL}
  consulta negocio <csv>         Full consultant: KPIs + forecast + recommendations
  analiza negocio <csv>          KPI report + health score + alerts (no ML needed)
  predice negocio <csv>          ML forecast: will next period grow or decline?
  entrena negocio <csv>          Train ML model on your business dataset
  (alias: consultar negocio, analizar negocio, predecir negocio)

{Fore.CYAN}── CONSULTOR PYME AVANZADO (Branch 4) ─────────────────────────{Style.RESET_ALL}
  diagnóstico pyme <csv>         Scorecard multidimensional: Financiero + Crecimiento + Riesgo
  forecast negocio <csv>         Proyección 6 meses: optimista / esperado / conservador
  forecast negocio <csv> 12      Proyección a N meses (reemplaza 12 por el plazo deseado)
  plan de accion <csv>           Plan estratégico: 5 recomendaciones priorizadas (Llama)
  que pasa si <escenario> <csv>  Simulación what-if: tabla antes/después con Δ en KPIs
  si aumento ventas <csv> 20%    Simulación de crecimiento de ingresos
  si reduzco costos <csv> 15%    Simulación de reducción de costos

{Fore.CYAN}── DOCUMENTS ──────────────────────────────────────────────────{Style.RESET_ALL}
  lee pdf <path>                 Read a PDF file
  lee word <path>                Read a Word (.docx) file
  lee excel <path>               Read an Excel (.xlsx) file
  lee csv <path>                 Read a CSV file (first 50 rows)
  analiza csv <path>             Full stats of a CSV file
  escribe pdf <path> <text>      Create a PDF with text
  escribe word <path> <text>     Create a Word file
  escribe excel <path> <data>    Create an Excel file
  escribe csv <path> <data>      Create a CSV file

{Fore.CYAN}── WEB ────────────────────────────────────────────────────────{Style.RESET_ALL}
  extrae web <url>               Scrape text from a webpage
  traducir <text>                Translate text to English
  youtube <url>                  Download YouTube video
  httpx demo                     HTTP client demo
  aiohttp demo                   Async HTTP client demo
  socketio demo                  Socket.IO demo
  fastapi demo                   FastAPI initialization demo
  flask demo                     Flask initialization demo

{Fore.CYAN}── AI / MACHINE LEARNING ──────────────────────────────────────{Style.RESET_ALL}
  torch demo                     PyTorch tensor demo
  tensorflow demo                TensorFlow tensor demo
  keras demo                     Keras sequential model demo
  sklearn demo                   Scikit-learn train/test demo
  integral                       Symbolic math integration demo
  analiza codigo [file...]       Analyze Python file with GPT

{Fore.CYAN}── SECURITY ───────────────────────────────────────────────────{Style.RESET_ALL}
  hash pass <text>               Bcrypt hash a password
  verify pass <hash> <text>      Verify password against hash
  passlib hash <text>            Hash with Passlib
  passlib verify <hash> <text>   Verify with Passlib
  crear jwt                      Create JWT token
  verificar jwt <token>          Decode and verify a JWT
  cifra archivo <path>           Encrypt a file with Fernet
  paramiko demo                  SSH client demo

{Fore.CYAN}── PREDICTION LAB (FASE 5) ────────────────────────────────────{Style.RESET_ALL}
  lab analiza "<idea>"           Extrae ProblemSpec de una idea en lenguaje natural
  lab dataset <csv> [target]     Analiza un CSV en profundidad (calidad, señal, VIF)
  lab viabilidad <csv> "<idea>"  Índice de Viabilidad 0-100 (¿vale la pena construir esto?)
  lab planea <csv> "<idea>"      Plan de modelo: algoritmos, features, validación
  lab genera <csv> "<idea>"      Construye el sklearn Pipeline ejecutable + código
  lab valida <csv> "<idea>"      Entrena y valida (holdout/kfold/WFV) — score real
  lab reporte <csv> "<idea>"     Corre TODO 5.1->5.6 y compila+guarda el reporte final
  lab proyectos                  Lista todos los reportes del Lab guardados
  lab info proyecto <n|nombre>   Detalle completo de un reporte guardado

{Fore.CYAN}── FEEDBACK Y APRENDIZAJE (FASE 6) ────────────────────────────{Style.RESET_ALL}
  feedback votar <id> <1|-1> [comentario]   Vota si una señal/predicción fue correcta
  feedback ver <id>               Ver todo el feedback registrado para un target
  feedback analisis                Patrones agregados: aprobación, tendencia, insights
  feedback dashboard               Panel completo: feedback + umbrales + contextos + evolución
  thresholds ver                   Umbrales adaptativos de confianza/ADX por par
  contextual memoria                Tasa de éxito por contexto de mercado guardado
  evolucion historial [n]          Historial de eventos de auto-ajuste del sistema

{Fore.CYAN}── MOTOR DE EVOLUCIÓN (FASE 7) ─────────────────────────────────{Style.RESET_ALL}
  monitor snapshot                 Toma una foto del rendimiento actual del sistema
  monitor historial [n]            Historial de snapshots + tendencia general
  mejoras detectar                 Detecta oportunidades de mejora (retrain, umbrales, etc.)
  evolucionar                      Detecta mejoras y genera propuestas concretas
  evolucionar ciclo                Ciclo completo: monitor->detecta->propone->constitucion->feedback->audit
  evolucionar ciclo auto           Igual, pero auto-aprueba ajustes menores de umbral
  salud sistema                    Reporte de salud: snapshot + propuestas + audit log
  propuestas ver [status]           Lista propuestas (pending/approved/applied/rejected)
  propuesta aprobar <id>            Valida contra la constitucion y aprueba (crea rollback point)
  propuesta rechazar <id>           Rechaza una propuesta pendiente
  propuesta aplicar <id>            Aplica una propuesta aprobada (auto o instrucción manual)

{Fore.CYAN}── CONSTITUCION (FASE 8) ───────────────────────────────────────{Style.RESET_ALL}
  reglas ver                        Lista las reglas constitucionales (limites duros del sistema)
  propuesta validar <id>            Vista previa: valida una propuesta contra la constitucion
  audit ver [n]                     Historial de decisiones (aprobaciones, rechazos, bloqueos)
  rollback ver                      Lista los puntos de rollback disponibles
  rollback aplicar <id>             Restaura umbrales de un par a un rollback point anterior

{Fore.CYAN}── COGNITIVE CENTER (ROADMAP IV, SECCION 7) ────────────────────{Style.RESET_ALL}
  memoria explorar                  Resumen: conversaciones, proyectos, modelos, herramientas, preferencias
  memoria buscar <consulta>         Busca en toda la memoria con lenguaje natural (LLM + fallback heuristico)

{Fore.CYAN}── SYSTEM & UTILS ─────────────────────────────────────────────{Style.RESET_ALL}
  estado pc                      CPU + RAM usage
  barra progreso                 Animated progress bar demo
  fecha                          Current date/time (UTC)
  json                           JSON serialization demo
  bloquear archivo <path>        File lock demo
  monitor archivos <path>        File system monitor demo

{Fore.CYAN}── VISUALIZATION ──────────────────────────────────────────────{Style.RESET_ALL}
  grafica csv <path>             Histogram of CSV first column
  tabla <path>                   Pretty-print CSV as table
  rich <text>                    Rich-formatted text output
  crear pdf <path> <text>        Create PDF via ReportLab
  imagen                         Scikit-image edge detection demo


{Fore.CYAN}── DEPLOYMENT REPORTS ─────────────────────────────────────────{Style.RESET_ALL}
  deploy check                     Ejecuta los 3 informes: Pipeline + Deployment + Readiness
  deploy readiness                 Solo Production Readiness Report (entorno + infraestructura)
  deploy reports                   Lista todos los informes de despliegue disponibles

{Fore.CYAN}── ROBUSTNESS ────────────────────────────────────────────{Style.RESET_ALL}
  robustness check                 Valida dependencias (Python, paquetes, system)
  robustness data                  Verifica integridad de CSVs (rows, gaps, dupes)
  robustness models                Verifica modelos ML (carga, features, edad)
  robustness recovery              Historial de eventos de recuperacion
  robustness provider              Verifica el proveedor cloud detectado
  robustness benchmark             Estadisticas de rendimiento del pipeline
  robustness wizard                First Run Wizard (setup inicial guiado)
  robustness all                   Ejecuta todos los checks de robustez

{Fore.CYAN}── ROADMAP V — FOREX LAB AVANZADO ─────────────────────────{Style.RESET_ALL}
  quality <csv> [par] [tf]         V.5  Gate de calidad del dataset
  regime <csv> [par] [tf]          V.4  Detección de régimen de mercado
  mtf <d1.csv> <h4.csv> <h1.csv>  V.3  Coherencia Multi-Timeframe D1→H4→H1
  reliability <conf> [signal]      V.8  Reliability Score (7 factores, 0-100)
  decision <signal> <conf>         V.1  Motor de decisión final (BUY/SELL/HOLD)
  risk <BUY|SELL> <entry> <atr>    V.2  SL/TP + position sizing Kelly
  backtest <modelo> <csv> [par]    V.9  Backtesting (20+ métricas, Walk-Forward)
  feature_importance <m> <csv>     V.6  Importancia de features (SHAP)
  dataset_update <par> [tf]        V.11 Actualización incremental CSV
  scheduler_status                 V.12 Estado del scheduler inteligente
  retrain_check <par>              V.13 Check de reentrenamiento adaptativo
  sentinel_status                  V.10 Market Sentinel ⭐⭐⭐⭐⭐
  sentinel_signals [par] [n]       V.10 Historial de señales del sentinel
  outcome_stats [par]              V.14 Estadísticas de resultados reales
  notify_test <par> <signal> <r>   V.15 Prueba de notificación multi-canal
  portfolio_ranking [signal] [min] V.18 Ranking de oportunidades multi-activo

{Fore.CYAN}── DIAGNÓSTICO & API ────────────────────────────────────────{Style.RESET_ALL}
  astra doctor                     Diagnóstico completo: 10 categorías + informe
  self-test                        VI.2 Diagnóstico del sistema (semáforo)
  api start                        Inicia la API REST interna (puerto 8766)
  api stop                         Detiene la API REST interna
  api status                       Estado de la API REST interna
  dev log                          Ver historial de desarrollo
  dev log add [tipo] title | desc  Añadir entrada al dev log
  dev log release <ver>            Release notes de una versión

{Fore.CYAN}── ROADMAP VI — AUTONOMIZACIÓN & DATA INTELLIGENCE ─────────{Style.RESET_ALL}
  descargar datos <par> [tf] [n]   VI.7 Descarga datos Forex/Crypto (Yahoo/Binance/MT5)
  migrar csv <path> [par] [tf]     VI.6 Migra CSV existente al formato rolling
  escanear csvs                    VI.6 Escanea y registra todos los CSVs en CSVs/
  csvs activos                     VI.6 Lista el índice de CSVs activos
  rolling info <par> [tf]          VI.6 Estado del RollingDataset de un par
  candlestick <csv>                VI.5 Detecta patrones de vela japonesa
  hparam cache                     VI.1 Estado del caché de hiperparámetros
  hparam invalidar <par>           VI.1 Fuerza re-tune en próximo entrenamiento
  model cache                      VI.1 Estado del Model Cache Manager
  adaptive budget <par>            VI.1 Historial de budgets adaptativos
  quality history                  VI.8 Historial de precisión verificada por modelo
  scheduler start                  VI.5 Inicia el scheduler autónomo en background
  scheduler stop                   VI.5 Detiene el scheduler
  scheduler info                   VI.5 Estado y tareas del scheduler
  auto update                      VI.5 Actualiza todos los CSVs activos ahora
  opportunity ranking [n]          VI.8 Top N BUY/SELL por Opportunity Score

{Fore.CYAN}── RISK MANAGEMENT ────────────────────────────────────────{Style.RESET_ALL}
  circuit status                 Estado del circuit breaker (pérdida diaria/semanal/drawdown)
  circuit reset                  Resetear manualmente el circuit breaker
  position size <par> <balance>  Calcular position sizing con equity explícito (ej: position size EURUSD 10000)
{Fore.CYAN}── FOREX WATCHER Y SEÑALES (FASE 2) ──────────────────────{Style.RESET_ALL}
  watch forex <par> <csv> [seg]  Monitoreo continuo de un par (thread background)
  watch stop <par>               Detener monitoreo de un par
  watch stop all                 Detener todos los watchers
  watch status                   Ver pares activos en monitoreo
  watch check <par>              Forzar evaluación inmediata
  señales <par>                  Historial de señales BUY/SELL/HOLD del par
  señales                        Historial global (todos los pares)
  stats señales [par]            Estadísticas de señales (ratio BUY/SELL/HOLD)

{Fore.CYAN}── PROYECTOS Y MODELOS (FASE 1) ───────────────────────────────{Style.RESET_ALL}
  mis modelos                    Lista todos los modelos Forex entrenados
  info modelo <par>              Detalles de un modelo (ej: info modelo EURUSD)
  mis proyectos                  Lista todos los proyectos registrados
  nuevo proyecto <nombre> <desc> Crea un proyecto nuevo
  cerrar proyecto <nombre>       Marca un proyecto como completado
  pausar proyecto <nombre>       Pausa un proyecto activo
  tareas                         Lista todas las tareas pendientes
  tareas <proyecto>              Tareas pendientes de un proyecto específico
  nueva tarea <proj> | <desc>    Agrega una tarea a un proyecto
  completar tarea <id>           Marca una tarea como completada

{Fore.CYAN}── MEMORY / DATABASE ──────────────────────────────────────────{Style.RESET_ALL}
  redis set                      Store a key-value in Redis
  redis get                      Retrieve a key from Redis
  sympy integral                 Symbolic integral demo (sin)
  sqlalchemy usuario             SQLAlchemy DB insert demo
  faiss add / faiss search       Vector memory demo
  llama add / llama query        LlamaIndex document demo

{Fore.CYAN}── SYSTEM ─────────────────────────────────────────────────────{Style.RESET_ALL}
  ayuda                          Show this help menu
  salir / exit / quit            Exit ASTRA
  <anything else>                Enviado a Llama-3.3-70B (Groq) — chat libre con contexto
"""
    print(help_text)
    return ""


# ═══════════════════════════════════════════════════════════
#  MAIN LOOP
# ═══════════════════════════════════════════════════════════

def dispatch_command(user_input: str) -> str:
    """
    Motor de despacho central de ASTRA — el mismo dispatcher estricto que
    usa el loop interactivo de consola (__main__), extraído a función
    reutilizable para que el backend del Workspace (workspace/server.py)
    pueda ejecutar los mismos comandos reales (full forex, monitor snapshot,
    reglas ver, feedback votar, etc.) — no solo el fallback de chat.

    No maneja "salir/exit/quit" — eso es responsabilidad de quien llama
    (el loop de consola sigue interceptándolo antes de invocar esta función).
    Siempre devuelve un string (nunca None): si ningún comando estricto
    calza, cae al fallback de process_request() (intent_router + chat).
    """
    respuesta = None
    try:
        # ── HELP ─────────────────────────────────────────
        if user_input.lower() in ["ayuda", "help", "?"]:
            respuesta = _ayuda()

        # ── FOREX: TUNE (Optuna) ─────────────────────────
        elif user_input.startswith("tune forex "):
            csv_path = user_input[len("tune forex "):].strip()
            respuesta = _forex_tune(csv_path)

        elif user_input.startswith("afinar forex "):
            csv_path = user_input[len("afinar forex "):].strip()
            respuesta = _forex_tune(csv_path)

        # ── FOREX: TRAINING ──────────────────────────────
        elif user_input.startswith("train forex "):
            csv_path = user_input[len("train forex "):].strip()
            respuesta = _forex_train(csv_path)

        elif user_input.startswith("entrenar forex "):
            csv_path = user_input[len("entrenar forex "):].strip()
            respuesta = _forex_train(csv_path)

        # ── FOREX: PREDICT (soporta multiples CSVs separados por coma) ──
        elif user_input.startswith("predict forex "):
            arg = user_input[len("predict forex "):].strip()
            paths = [p.strip() for p in arg.split(",") if p.strip()]
            respuesta = _forex_predict(paths[0]) if len(paths) <= 1 else _forex_predict_multi(paths)

        elif user_input.startswith("predecir forex "):
            arg = user_input[len("predecir forex "):].strip()
            paths = [p.strip() for p in arg.split(",") if p.strip()]
            respuesta = _forex_predict(paths[0]) if len(paths) <= 1 else _forex_predict_multi(paths)

        # ── FOREX: MULTI-HORIZON ─────────────────────────
        elif user_input.startswith("multi forex "):
            csv_path = user_input[len("multi forex "):].strip()
            respuesta = _forex_multi(csv_path)

        elif user_input.startswith("multihorizonte forex "):
            csv_path = user_input[len("multihorizonte forex "):].strip()
            respuesta = _forex_multi(csv_path)

        # ── FOREX: SCAN FOLDER ───────────────────────────
        elif user_input.startswith("scan forex "):
            target = user_input[len("scan forex "):].strip()
            respuesta = _forex_scan(target)

        elif user_input.startswith("escanear forex "):
            target = user_input[len("escanear forex "):].strip()
            respuesta = _forex_scan(target)

        # ── FOREX: GENERAR TODOS LOS CSVs ─────────────────
        elif (
            user_input.lower().startswith("generar csvs forex")
            or user_input.lower().startswith("generate forex csvs")
            or user_input.lower().startswith("generar todos los csvs forex")
        ):
            try:
                from forex.data.csv_bulk_generator import cmd_generate_all_csvs
                # extraer lo que venga después del comando
                _low = user_input.lower()
                for _prefix in ("generar todos los csvs forex",
                                "generar csvs forex",
                                "generate forex csvs"):
                    if _low.startswith(_prefix):
                        _rest = user_input[len(_prefix):].strip()
                        break
                else:
                    _rest = ""
                respuesta = cmd_generate_all_csvs(_rest)
            except Exception as ex:
                respuesta = f"Error generando CSVs Forex: {ex}"

        # ── FOREX: BACKTEST ──────────────────────────────
        elif user_input.startswith("backtest forex "):
            csv_path = user_input[len("backtest forex "):].strip()
            respuesta = _forex_backtest(csv_path)

        # ── FOREX: FULL PIPELINE ─────────────────────────
        elif user_input.startswith("full forex "):
            csv_path = user_input[len("full forex "):].strip()
            respuesta = _forex_full(csv_path)

        elif user_input.startswith("completo forex "):
            csv_path = user_input[len("completo forex "):].strip()
            respuesta = _forex_full(csv_path)

        # ── FOREX: TECHNICAL ANALYTICS ───────────────────
        elif user_input.startswith("analiza forex "):
            # Accept both orderings:  "analiza forex eurusd datos.csv"
            #                     and "analiza forex datos.csv eurusd"
            from argument_parser import extract_market_symbol as _ems
            _rest  = user_input[len("analiza forex "):].strip()
            _parts = _rest.split()
            _filepath, _sym = None, None
            for _p in _parts:
                if _p.lower().endswith((".csv", ".xlsx", ".xls")):
                    _filepath = _p
                else:
                    _candidate = _ems(_p)
                    if _candidate:
                        _sym = _candidate
            if _filepath and _sym:
                respuesta = _forex_analiza(_filepath, _sym)
            elif _sym:
                respuesta = analyze_market_file(None, _sym)
            elif _filepath:
                respuesta = _forex_analiza(_filepath, "")
            else:
                respuesta = "Uso: analiza forex <symbol> [csv_path]  ej: analiza forex eurusd datos.csv"

        # ── FOREX: LIST MARKETS ──────────────────────────
        elif user_input.lower() in ["lista mercados", "list markets", "forex pares"]:
            respuesta = _forex_lista()

        elif user_input.lower() in ["mercados analizados", "saved markets"]:
            respuesta = _forex_mercados()

        # ── FOREX: HISTORY ───────────────────────────────
        elif user_input.startswith("historial forex "):
            symbol = user_input[len("historial forex "):].strip()
            respuesta = _forex_historial(symbol)

        elif user_input.startswith("forex history "):
            symbol = user_input[len("forex history "):].strip()
            respuesta = _forex_historial(symbol)

        # ── FOREX: COMPARE ───────────────────────────────
        elif user_input.startswith("compara forex "):
            symbol = user_input[len("compara forex "):].strip()
            respuesta = _forex_compara(symbol)

        # ── MEMORIA DE COMANDOS ──────────────────────────────
        elif user_input.lower() in ["que hice", "historial comandos", "mis acciones", "log"]:
            try:
                from memory import get_command_log
                entries = get_command_log(limit=10)
                if not entries:
                    respuesta = "No hay comandos registrados aún."
                else:
                    lines = ["\n Últimos comandos ejecutados:\n"]
                    for e in entries:
                        pair_tag = f" [{e['pair']}]" if e["pair"] else ""
                        lines.append(f"  [{e['executed_at']}]{pair_tag}  {e['command']}")
                        lines.append(f"       → {e['summary'][:120]}")
                    respuesta = "\n".join(lines)
            except Exception as ex:
                respuesta = f"Error al leer historial: {ex}"

        elif user_input.lower().startswith("que hice con ") or user_input.lower().startswith("historial "):
            try:
                from memory import get_command_log
                parts_h  = user_input.strip().split()
                pair_h   = parts_h[-1].upper() if len(parts_h) > 2 else None
                entries  = get_command_log(limit=10, pair=pair_h)
                if not entries:
                    respuesta = f"Sin registros para {pair_h or 'ese par'}."
                else:
                    lines = [f"\n Historial para {pair_h or 'todos'}:\n"]
                    for e in entries:
                        lines.append(f"  [{e['executed_at']}]  {e['command']}")
                        lines.append(f"       → {e['summary'][:120]}")
                    respuesta = "\n".join(lines)
            except Exception as ex:
                respuesta = f"Error: {ex}"

        # ── COGNITIVE CENTER (Roadmap IV, Sección 7) ─────────
        elif user_input.lower().strip() in ["memoria explorar", "cognitive center", "explorar memoria"]:
            try:
                from cognitive_center import cmd_memoria_explorar
                respuesta = cmd_memoria_explorar()
            except Exception as ex:
                respuesta = f"Error en Cognitive Center: {ex}"

        elif user_input.lower().startswith("memoria buscar "):
            _query_mem = user_input[len("memoria buscar "):].strip()
            try:
                from cognitive_center import cmd_memoria_buscar
                respuesta = cmd_memoria_buscar(_query_mem) if _query_mem else "Uso: memoria buscar <consulta en lenguaje natural>"
            except Exception as ex:
                respuesta = f"Error en búsqueda de memoria: {ex}"

        # ── RISK MANAGEMENT ──────────────────────────────────
        elif user_input.lower() in ["circuit status", "estado circuit", "circuit breaker"]:
            respuesta = cmd_circuit_status() if _HAS_RISK else "Módulo risk no disponible."
        elif user_input.lower() in ["circuit reset", "resetear circuit"]:
            respuesta = cmd_circuit_reset() if _HAS_RISK else "Módulo risk no disponible."
        elif user_input.lower().startswith("position size ") or user_input.lower().startswith("sizing "):
            # uso: position size <par> <balance>
            parts = user_input.strip().split()
            pair_ps  = parts[2] if len(parts) > 2 else "EURUSD"
            if len(parts) <= 3:
                respuesta = "Uso: position size <par> <balance>"
            else:
                bal_ps = float(parts[3])
                respuesta = _cmd_position_size(pair_ps, bal_ps) if _HAS_RISK else "Módulo risk no disponible."
        # ── BUSINESS INTELLIGENCE ─────────────────────────
        elif user_input.startswith("consulta negocio ") or user_input.startswith("consultar negocio "):
            csv_path = user_input.split(" ", 2)[-1].strip()
            respuesta = _bi_consulta(csv_path)

        elif user_input.startswith("analiza negocio ") or user_input.startswith("analizar negocio "):
            csv_path = user_input.split(" ", 2)[-1].strip()
            respuesta = _bi_analiza(csv_path)

        elif user_input.startswith("predice negocio ") or user_input.startswith("predecir negocio "):
            csv_path = user_input.split(" ", 2)[-1].strip()
            respuesta = _bi_predice(csv_path)

        elif user_input.startswith("entrena negocio ") or user_input.startswith("entrenar negocio "):
            csv_path = user_input.split(" ", 2)[-1].strip()
            respuesta = _bi_entrena(csv_path)

        elif user_input.startswith("forecast negocio "):
            rest = user_input[len("forecast negocio "):].strip().split()
            csv_path = rest[0] if rest else ""
            months = int(rest[1]) if len(rest) > 1 and rest[1].isdigit() else 6
            respuesta = _bi_forecast(csv_path, months)

        # ── IO FILES ─────────────────────────────────────
        elif user_input.startswith("analiza codigo"):
            import ast
            archivos = user_input.split()[2:] or ["main.py"]
            for archivo in archivos:
                try:
                    with open(archivo, "r", encoding="utf-8") as f:
                        code = f.read()
                    tree = ast.parse(code)
                    funciones = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
                    print(f"Funciones en {archivo}: {funciones}")
                    respuesta = ask_openai("Analiza este código y dame mejoras:\n" + code)
                    print(f"ASTRA ({archivo}): {respuesta}")
                except Exception as e:
                    print(f"Error analizando {archivo}: {e}")
            return ""

        elif user_input.startswith("crea py "):
            partes = user_input.split(" ", 2)
            from io_files import crea_py
            respuesta = crea_py(partes[1], partes[2] if len(partes) > 2 else "")

        elif user_input.startswith("lee pdf "):
            show_progress("Reading PDF", 1)
            respuesta = leer_pdf(user_input[8:].strip())

        elif user_input.startswith("lee word "):
            respuesta = leer_word(user_input[9:].strip())

        elif user_input.startswith("lee excel "):
            show_progress("Reading Excel", 2)
            respuesta = leer_excel(user_input[10:].strip())

        elif user_input.startswith("lee csv "):
            show_progress("Reading CSV", 1)
            respuesta = leer_csv(user_input[8:].strip())

        elif user_input.startswith("analiza csv "):
            show_progress("Analyzing CSV", 2)
            respuesta = leer_csv(user_input[12:].strip(), analizar=True)

        elif user_input.startswith("escribe pdf "):
            partes = user_input.split(" ", 3)
            respuesta = escribe_pdf(partes[2], partes[3] if len(partes) > 3 else "")

        elif user_input.startswith("escribe word "):
            partes = user_input.split(" ", 3)
            respuesta = escribe_word(partes[2], partes[3] if len(partes) > 3 else "")

        elif user_input.startswith("escribe excel "):
            partes = user_input.split(" ", 3)
            respuesta = escribe_excel(partes[2], partes[3] if len(partes) > 3 else "")

        elif user_input.startswith("escribe csv "):
            partes = user_input.split(" ", 3)
            respuesta = escribe_csv(partes[2], partes[3] if len(partes) > 3 else "")

        # ── VISUALIZATION ────────────────────────────────
        elif user_input.startswith("grafica csv "):
            respuesta = grafica_csv(user_input[12:].strip())

        elif user_input.startswith("tabla "):
            import pandas as pd
            df = pd.read_csv(user_input[6:].strip())
            respuesta = mostrar_tabla(df)

        elif user_input.startswith("rich "):
            respuesta = mostrar_rich(user_input[5:].strip())

        elif user_input.startswith("crear pdf "):
            partes = user_input.split(" ", 3)
            respuesta = crear_pdf(partes[2], partes[3] if len(partes) > 3 else "")

        elif user_input == "imagen":
            respuesta = procesar_imagen_skimage()

        elif user_input == "gui":
            respuesta = mostrar_gui_pyqt()

        # ── WEB ──────────────────────────────────────────
        elif user_input.startswith("extrae web "):
            show_progress("Extracting Web Content", 3)
            respuesta = extrae_web(user_input[11:].strip())

        elif user_input.startswith("traducir "):
            show_progress("Translating", 2)
            respuesta = traducir(user_input[9:].strip())

        elif user_input.startswith("youtube "):
            respuesta = descargar_youtube(user_input[8:].strip())

        elif user_input == "httpx demo":
            respuesta = httpx_demo()

        elif user_input == "aiohttp demo":
            import asyncio
            respuesta = asyncio.run(aiohttp_demo())

        elif user_input == "socketio demo":
            respuesta = socketio_demo()

        elif user_input == "fastapi demo":
            respuesta = fastapi_demo()

        elif user_input == "flask demo":
            respuesta = flask_demo()

        # ── AUDIO / VIDEO ────────────────────────────────
        elif user_input.startswith("voz a texto"):
            respuesta = voz_a_texto()

        elif user_input.startswith("texto a voz "):
            respuesta = texto_a_voz(user_input[12:].strip())

        elif user_input.startswith("analiza audio "):
            respuesta = analiza_audio(user_input[14:].strip())

        elif user_input.startswith("reproducir audio "):
            respuesta = reproducir_audio(user_input[17:].strip())

        elif user_input.startswith("convertir audio "):
            partes = user_input.split(" ", 3)
            respuesta = convertir_audio(partes[2], partes[3] if len(partes) > 3 else "mp3")

        elif user_input.startswith("descargar audio youtube "):
            respuesta = descargar_audio_youtube(user_input[24:].strip())

        # ── SECURITY ─────────────────────────────────────
        elif user_input.startswith("cifra archivo "):
            respuesta = cifra_archivo(user_input[14:].strip())

        elif user_input.startswith("hash pass "):
            respuesta = hash_password(user_input[10:].strip())

        elif user_input.startswith("verify pass "):
            partes = user_input.split(" ", 3)
            respuesta = verify_password(partes[2], partes[3] if len(partes) > 3 else "")

        elif user_input.startswith("passlib hash "):
            respuesta = passlib_hash(user_input[13:].strip())

        elif user_input.startswith("passlib verify "):
            partes = user_input.split(" ", 3)
            respuesta = passlib_verify(partes[2], partes[3] if len(partes) > 3 else "")

        elif user_input.startswith("crear jwt"):
            respuesta = crear_jwt({"user": "astra", "role": "admin"})

        elif user_input.startswith("verificar jwt "):
            respuesta = verificar_jwt(user_input[14:].strip())

        elif user_input == "paramiko demo":
            respuesta = paramiko_demo()

        # ── UTILS ────────────────────────────────────────
        elif user_input.startswith("estado pc"):
            respuesta = utils_status()

        elif user_input == "barra progreso":
            respuesta = barra_progreso()

        elif user_input == "tarea programada":
            respuesta = tarea_programada()

        elif user_input.startswith("simular tecla "):
            respuesta = simular_tecla(user_input[14:].strip())

        elif user_input == "simular click":
            respuesta = simular_click()

        elif user_input.startswith("bloquear archivo "):
            respuesta = bloquear_archivo(user_input[17:].strip())

        elif user_input.startswith("monitor archivos "):
            respuesta = iniciar_monitor(user_input[17:].strip())

        elif user_input == "fecha":
            respuesta = obtener_fecha_arrow()

        elif user_input == "json":
            respuesta = serializar_orjson({"msg": "ok", "sistema": "ASTRA"})

        # ── AI MODELS ────────────────────────────────────
        elif user_input == "torch demo":
            respuesta = torch_demo()

        elif user_input == "tensorflow demo":
            respuesta = tensorflow_demo()

        elif user_input == "keras demo":
            respuesta = keras_demo()

        elif user_input in ("sklearn demo", "sklearn"):
            respuesta = sklearn_demo()

        elif user_input == "integral":
            show_progress("Symbolic Integration", 1)
            respuesta = calcular_integral("x**2", "x", 0, 1)


        # ── PROYECTOS Y MODELOS (FASE 1) ─────────────────────
        elif user_input.lower() in ["mis modelos", "list models", "modelos entrenados"]:
            respuesta = cmd_list_models()

        elif user_input.lower() in ["mis proyectos", "list projects", "proyectos"]:
            respuesta = cmd_list_projects()

        elif user_input.lower() in ["tareas", "mis tareas", "pendientes"]:
            respuesta = cmd_list_tasks()

        elif user_input.lower().startswith("tareas "):
            respuesta = cmd_list_tasks(user_input[7:].strip())

        elif user_input.lower().startswith("nuevo proyecto "):
            parts = user_input[15:].strip().split(" ", 1)
            name  = parts[0]
            desc  = parts[1] if len(parts) > 1 else ""
            pid   = save_project(name, desc)
            respuesta = f"Proyecto '{name}' guardado (id={pid})"

        elif user_input.lower().startswith("cerrar proyecto "):
            name = user_input[16:].strip()
            ok   = update_project_status(name, "done")
            respuesta = f"Proyecto '{name}' completado." if ok else f"No encontré el proyecto '{name}'."

        elif user_input.lower().startswith("pausar proyecto "):
            name = user_input[16:].strip()
            ok   = update_project_status(name, "paused")
            respuesta = f"Proyecto '{name}' pausado." if ok else f"No encontré el proyecto '{name}'."

        elif user_input.lower().startswith("nueva tarea "):
            rest = user_input[12:].strip()
            if "|" in rest:
                proj, desc = rest.split("|", 1)
                tid = add_task(proj.strip(), desc.strip())
                respuesta = f"Tarea [{tid}] agregada al proyecto '{proj.strip()}'."
            else:
                respuesta = "Uso: nueva tarea <proyecto> | <descripción>"

        elif user_input.lower().startswith("completar tarea "):
            try:
                tid = int(user_input[16:].strip())
                ok  = complete_task(tid)
                respuesta = f"Tarea [{tid}] completada." if ok else f"No encontré la tarea [{tid}]."
            except ValueError:
                respuesta = "Uso: completar tarea <id>  (ej: completar tarea 3)"

        elif user_input.lower().startswith("info modelo "):
            pair  = user_input[12:].strip()
            model = get_model(pair)
            if model:
                prec = model.get("precision")
                acc  = model.get("accuracy")
                rows = model.get("rows_trained")
                date = (model.get("updated_at") or "")[:16]
                out  = [f"  Modelo: {model['pair']}"]
                if prec: out.append(f"  Precision  : {prec:.2%}")
                if acc:  out.append(f"  Accuracy   : {acc:.2%}")
                if rows: out.append(f"  Filas      : {rows:,}")
                out.append(f"  Actualizado: {date}")
                respuesta = "\n".join(out)
            else:
                respuesta = f"No hay modelo para '{pair}'. Usa: train forex <csv>"

        # ── PREDICTION LAB (FASE 5) ───────────────────────────
        elif user_input.lower().startswith("lab analiza "):
            _idea = user_input[12:].strip().strip('"').strip("'")
            respuesta = cmd_lab_analiza(_idea)

        elif user_input.lower().startswith("lab dataset "):
            _parts_ds = user_input[12:].strip().split()
            if len(_parts_ds) >= 2:
                respuesta = cmd_lab_dataset(_parts_ds[0], _parts_ds[1])
            elif len(_parts_ds) == 1:
                respuesta = cmd_lab_dataset(_parts_ds[0])
            else:
                respuesta = "Uso: lab dataset <archivo.csv> [target_variable]"

        elif user_input.lower().startswith("lab viabilidad "):
            _csv_v, _idea_v, _tgt_v = _parse_lab_args(user_input[15:])
            if _csv_v:
                respuesta = cmd_lab_viabilidad(_csv_v, _idea_v, target_variable=_tgt_v)
            else:
                respuesta = 'Uso: lab viabilidad <archivo.csv> "<describe tu idea>" [columna_target]'

        elif user_input.lower().startswith("lab planea "):
            _csv_p, _idea_p, _tgt_p = _parse_lab_args(user_input[11:])
            if _csv_p:
                respuesta = cmd_lab_planea(_csv_p, _idea_p, target_variable=_tgt_p)
            else:
                respuesta = 'Uso: lab planea <archivo.csv> "<describe tu idea>" [columna_target]'

        elif user_input.lower().startswith("lab genera "):
            _csv_g, _idea_g, _tgt_g = _parse_lab_args(user_input[11:])
            if _csv_g:
                respuesta = cmd_lab_genera(_csv_g, _idea_g, target_variable=_tgt_g)
            else:
                respuesta = 'Uso: lab genera <archivo.csv> "<describe tu idea>" [columna_target]'

        elif user_input.lower().startswith("lab valida "):
            _csv_val, _idea_val, _tgt_val = _parse_lab_args(user_input[11:])
            if _csv_val:
                respuesta = cmd_lab_valida(_csv_val, _idea_val, target_variable=_tgt_val)
            else:
                respuesta = 'Uso: lab valida <archivo.csv> "<describe tu idea>" [columna_target]'

        elif user_input.lower().startswith("lab reporte "):
            _csv_r, _idea_r, _tgt_r = _parse_lab_args(user_input[12:])
            if _csv_r:
                respuesta = cmd_lab_reporte(_csv_r, _idea_r, target_variable=_tgt_r)
            else:
                respuesta = 'Uso: lab reporte <archivo.csv> "<describe tu idea>" [columna_target]'

        elif user_input.lower().strip() == "lab proyectos":
            respuesta = cmd_lab_proyectos()

        elif user_input.lower().startswith("lab info proyecto "):
            _ident = user_input[19:].strip()
            respuesta = cmd_lab_info_proyecto(_ident) if _ident else "Uso: lab info proyecto <numero|nombre>"

        elif user_input.lower().startswith("feedback votar "):
            _rest_fv = user_input[15:].strip().split(None, 2)
            if len(_rest_fv) >= 2:
                _tid, _vote = _rest_fv[0], _rest_fv[1]
                _comment = _rest_fv[2].strip().strip('"').strip("'") if len(_rest_fv) == 3 else ""
                respuesta = cmd_feedback_votar(_tid, _vote, _comment)
            else:
                respuesta = 'Uso: feedback votar <id> <1|-1> ["comentario"]'

        elif user_input.lower().startswith("feedback ver "):
            _tid_v = user_input[13:].strip()
            respuesta = cmd_feedback_ver(_tid_v) if _tid_v else "Uso: feedback ver <id>"

        elif user_input.lower().strip() == "feedback analisis":
            respuesta = cmd_feedback_analisis()

        elif user_input.lower().strip() == "feedback dashboard":
            respuesta = cmd_feedback_dashboard()

        elif user_input.lower().strip() == "thresholds ver":
            respuesta = cmd_thresholds_ver()

        elif user_input.lower().strip() == "contextual memoria":
            respuesta = cmd_contextual_memory()

        elif user_input.lower().startswith("evolucion historial"):
            _rest_eh = user_input[20:].strip()
            _limit_eh = int(_rest_eh) if _rest_eh.isdigit() else 10
            respuesta = cmd_evolution_history(_limit_eh)

        elif user_input.lower().strip() == "monitor snapshot":
            respuesta = cmd_monitor_snapshot()

        elif user_input.lower().startswith("monitor historial"):
            _rest_mh = user_input[18:].strip()
            _limit_mh = int(_rest_mh) if _rest_mh.isdigit() else 10
            respuesta = cmd_monitor_historial(_limit_mh)

        elif user_input.lower().strip() == "mejoras detectar":
            respuesta = cmd_mejoras_detectar()

        elif user_input.lower().strip() == "evolucionar":
            respuesta = cmd_evolucionar(False)

        elif user_input.lower().strip() == "evolucionar ciclo":
            respuesta = cmd_ciclo_evolutivo(auto_approve=False)

        elif user_input.lower().strip() == "evolucionar ciclo auto":
            respuesta = cmd_ciclo_evolutivo(auto_approve=True)

        elif user_input.lower().strip() == "salud sistema":
            respuesta = cmd_health_report()

        elif user_input.lower().startswith("propuestas ver"):
            _rest_pv = user_input[14:].strip()
            respuesta = cmd_proposals_ver(_rest_pv if _rest_pv else None)

        elif user_input.lower().startswith("propuesta aprobar "):
            _pid_ap = user_input[18:].strip()
            respuesta = cmd_aprobar_propuesta(_pid_ap) if _pid_ap else "Uso: propuesta aprobar <id>"

        elif user_input.lower().startswith("propuesta rechazar "):
            _pid_rj = user_input[19:].strip()
            respuesta = cmd_rechazar_propuesta(_pid_rj) if _pid_rj else "Uso: propuesta rechazar <id>"

        elif user_input.lower().startswith("propuesta aplicar "):
            _pid_apl = user_input[18:].strip()
            respuesta = cmd_aplicar_propuesta(_pid_apl) if _pid_apl else "Uso: propuesta aplicar <id>"

        elif user_input.lower().strip() == "reglas ver":
            respuesta = cmd_reglas_ver()

        elif user_input.lower().startswith("propuesta validar "):
            _pid_val = user_input[18:].strip()
            respuesta = cmd_validar_propuesta(_pid_val) if _pid_val else "Uso: propuesta validar <id>"

        elif user_input.lower().startswith("audit ver"):
            _rest_av = user_input[9:].strip()
            _limit_av = int(_rest_av) if _rest_av.isdigit() else 20
            respuesta = cmd_audit_log(_limit_av)

        elif user_input.lower().strip() == "rollback ver":
            respuesta = cmd_rollback_ver()

        elif user_input.lower().startswith("rollback aplicar "):
            _pid_rb = user_input[17:].strip()
            respuesta = cmd_rollback_aplicar(_pid_rb) if _pid_rb else "Uso: rollback aplicar <id>"

        # ── NEWS INTELLIGENCE (FASE 4) ───────────────────────
        elif user_input.lower().startswith("noticias predice "):
            parts = user_input[17:].strip().split()
            if len(parts) >= 2:
                respuesta = cmd_news_predict(parts[0], parts[1])
            else:
                respuesta = "Uso: noticias predice <par> <csv>  ej: noticias predice EURUSD CSVs/H1/EURUSD.csv"

        elif user_input.lower().startswith("noticias "):
            respuesta = cmd_news(user_input[9:].strip())

        elif user_input.lower().startswith("news "):
            respuesta = cmd_news(user_input[5:].strip())

        # ── ACTIVE ENGINE SCHEDULER (FASE 3) ─────────────────
        elif user_input.lower().startswith("schedule forex "):
            # uso: schedule forex <par> <csv> [minutos]
            parts = user_input[15:].strip().split()
            if len(parts) >= 2:
                _pair = parts[0]
                _csv  = parts[1]
                _min  = int(parts[2]) if len(parts) > 2 else 60
                respuesta = cmd_schedule_forex(_pair, _csv, _min)
            else:
                respuesta = "Uso: schedule forex <par> <csv> [minutos]  ej: schedule forex EURUSD CSVs/H1/EURUSD.csv 60"

        elif user_input.lower().startswith("schedule stop "):
            respuesta = cmd_schedule_stop(user_input[14:].strip())

        elif user_input.lower() == "schedule stop":
            respuesta = cmd_schedule_stop("all")

        elif user_input.lower() in ["schedule status", "schedule"]:
            respuesta = cmd_schedule_status()

        elif user_input.lower().startswith("schedule run "):
            respuesta = cmd_schedule_run(user_input[13:].strip())

        # ── FOREX WATCHER (FASE 2) ────────────────────────────
        elif user_input.lower().startswith("watch forex "):
            # uso: watch forex <par> <csv> [intervalo_segundos]
            parts = user_input[12:].strip().split()
            if len(parts) >= 2:
                _pair  = parts[0]
                _csv   = parts[1]
                _intv  = int(parts[2]) if len(parts) > 2 else 60
                respuesta = cmd_watch_start(_pair, _csv, _intv)
            else:
                respuesta = "Uso: watch forex <par> <csv> [intervalo]  ej: watch forex EURUSD CSVs/H1/EURUSD.csv 60"

        elif user_input.lower().startswith("watch stop "):
            respuesta = cmd_watch_stop(user_input[11:].strip())

        elif user_input.lower() == "watch stop":
            respuesta = cmd_watch_stop("all")

        elif user_input.lower() in ["watch status", "watch"]:
            respuesta = cmd_watch_status()

        elif user_input.lower().startswith("watch check "):
            respuesta = cmd_watch_check(user_input[12:].strip())

        # ── HISTORIAL DE SEÑALES (FASE 2) ────────────────────
        elif user_input.lower().startswith("señales "):
            respuesta = cmd_signal_history(user_input[8:].strip())

        elif user_input.lower().startswith("signals "):
            respuesta = cmd_signal_history(user_input[8:].strip())

        elif user_input.lower() in ["señales", "signals", "historial señales"]:
            respuesta = cmd_signal_history()

        elif user_input.lower().startswith("stats señales"):
            parts = user_input.split()
            pair_arg = parts[2] if len(parts) > 2 else None
            respuesta = cmd_signal_stats(pair_arg)

        # ── ROADMAP V — FOREX LAB AVANZADO ────────────────────────
        elif _HAS_ROADMAP_V and user_input.lower().startswith("quality "):
            parts = user_input[8:].strip().split()
            csv_path = parts[0] if parts else ""
            pair_arg = parts[1] if len(parts) > 1 else "UNKNOWN"
            tf_arg   = parts[2] if len(parts) > 2 else "H1"
            respuesta = cmd_quality(f"{csv_path} {pair_arg} {tf_arg}")

        elif _HAS_ROADMAP_V and user_input.lower().startswith("regime "):
            parts = user_input[7:].strip().split()
            csv_path = parts[0] if parts else ""
            pair_arg = parts[1] if len(parts) > 1 else "UNKNOWN"
            tf_arg   = parts[2] if len(parts) > 2 else "H1"
            respuesta = cmd_regime(f"{csv_path} {pair_arg} {tf_arg}")

        elif _HAS_ROADMAP_V and user_input.lower().startswith("mtf "):
            respuesta = cmd_mtf(user_input[4:].strip())

        elif _HAS_ROADMAP_V and user_input.lower().startswith("reliability "):
            respuesta = cmd_reliability(user_input[12:].strip())

        elif _HAS_ROADMAP_V and user_input.lower().startswith("decision "):
            respuesta = cmd_decision(user_input[9:].strip())

        elif _HAS_ROADMAP_V and user_input.lower().startswith("risk "):
            parts = user_input[5:].strip().split()
            respuesta = cmd_risk(" ".join(parts))

        elif _HAS_ROADMAP_V and user_input.lower().startswith("backtest "):
            respuesta = cmd_backtest(user_input[9:].strip())

        elif _HAS_ROADMAP_V and user_input.lower().startswith("feature_importance "):
            respuesta = cmd_feature_importance(user_input[19:].strip())

        elif _HAS_ROADMAP_V and user_input.lower().startswith("dataset_update "):
            respuesta = cmd_dataset_update(user_input[15:].strip())

        elif _HAS_ROADMAP_V and user_input.lower() in ["scheduler_status", "scheduler status"]:
            respuesta = cmd_scheduler_status("")

        elif _HAS_ROADMAP_V and user_input.lower().startswith("retrain_check "):
            respuesta = cmd_retrain_check(user_input[14:].strip())

        elif _HAS_ROADMAP_V and user_input.lower().startswith("retrain_history"):
            respuesta = cmd_retrain_history(user_input[15:].strip())

        elif _HAS_ROADMAP_V and user_input.lower() in ["sentinel_status", "sentinel status"]:
            respuesta = cmd_sentinel_status("")

        elif _HAS_ROADMAP_V and user_input.lower().startswith("sentinel_signals"):
            respuesta = cmd_sentinel_signals(user_input[16:].strip())

        elif _HAS_ROADMAP_V and user_input.lower().startswith("outcome_stats"):
            respuesta = cmd_outcome_stats(user_input[13:].strip())

        elif _HAS_ROADMAP_V and user_input.lower().startswith("outcome_history"):
            respuesta = cmd_outcome_history(user_input[15:].strip())

        elif _HAS_ROADMAP_V and user_input.lower().startswith("notify_test "):
            respuesta = cmd_notify_test(user_input[12:].strip())

        elif _HAS_ROADMAP_V and user_input.lower().startswith("notify_log"):
            respuesta = cmd_notify_log(user_input[10:].strip())

        elif _HAS_ROADMAP_V and user_input.lower().startswith("portfolio_ranking"):
            respuesta = cmd_portfolio_ranking(user_input[17:].strip())

        elif _HAS_ROADMAP_V and user_input.lower().startswith("portfolio_export"):
            respuesta = cmd_portfolio_export(user_input[16:].strip())

        # ── ROADMAP VI — Autonomización & Data Intelligence ──────────
        elif _HAS_ROADMAP_VI and user_input.lower() in ["self-test", "self test", "diagnóstico sistema", "diagnostico sistema"]:
            _run_self_test(verbose=True)
            respuesta = ""

        elif _HAS_ROADMAP_VI and user_input.lower().startswith("hparam cache"):
            respuesta = _get_hparam_cache().status()

        elif _HAS_ROADMAP_VI and user_input.lower().startswith("hparam invalidar "):
            pair_arg = user_input[17:].strip().split()[0]
            _get_hparam_cache().invalidate(pair_arg)
            respuesta = f"Caché de hiperparámetros invalidado para {pair_arg.upper()}."

        elif _HAS_ROADMAP_VI and user_input.lower().startswith("model cache"):
            mc_obj = _get_model_cache()
            respuesta = mc_obj.status() if hasattr(mc_obj, 'status') else str(mc_obj)

        elif _HAS_ROADMAP_VI and user_input.lower().startswith("adaptive budget"):
            rest_ab = user_input[15:].strip()
            pair_ab = rest_ab.split()[0] if rest_ab else "EURUSD"
            at_obj = _get_adaptive_trainer()
            respuesta = at_obj.status(pair_ab) if hasattr(at_obj, 'status') else str(at_obj)

        elif _HAS_ROADMAP_VI and user_input.lower().startswith("quality history"):
            respuesta = _get_quality_history().status()

        elif _HAS_ROADMAP_VI and user_input.lower().startswith("candlestick "):
            # candlestick <csv_path> [par] [tf]
            parts_cs = user_input[12:].strip().split()
            csv_cs = parts_cs[0] if parts_cs else ""
            try:
                import pandas as pd
                df_cs = pd.read_csv(csv_cs)
                result_cs = _get_candle_detector().detect(df_cs)
                respuesta = _get_candle_detector().format_result(result_cs)
                if result_cs["patterns"]:
                    respuesta += f"\n  Patrones: {', '.join(result_cs['pattern_names'])}"
            except Exception as e_cs:
                respuesta = f"Error leyendo CSV para candlestick: {e_cs}"

        elif _HAS_ROADMAP_VI and user_input.lower().startswith("descargar datos "):
            # descargar datos <par> [tf] [bars]
            parts_dd = user_input[16:].strip().split()
            pair_dd = parts_dd[0].upper() if parts_dd else "EURUSD"
            tf_dd   = parts_dd[1].upper() if len(parts_dd) > 1 else "H1"
            bars_dd = int(parts_dd[2]) if len(parts_dd) > 2 else 500
            try:
                router_dd = DataRouter(pair_dd, tf_dd)
                df_dd = router_dd.fetch(bars=bars_dd, save_csv=True)
                if df_dd is not None:
                    respuesta = (f"✅ {pair_dd}/{tf_dd}: {len(df_dd)} filas descargadas "
                                 f"via {router_dd.source_used}.\n"
                                 f"  Guardado en CSVs/{tf_dd}/{pair_dd}.csv")
                else:
                    respuesta = f"❌ No se pudieron obtener datos para {pair_dd}/{tf_dd}."
            except Exception as e_dd:
                respuesta = f"Error descargando datos: {e_dd}"

        elif _HAS_ROADMAP_VI and user_input.lower().startswith("migrar csv "):
            # migrar csv <path> [par] [tf]
            parts_mc = user_input[11:].strip().split()
            csv_mc  = parts_mc[0] if parts_mc else ""
            pair_mc = parts_mc[1].upper() if len(parts_mc) > 1 else None
            tf_mc   = parts_mc[2].upper() if len(parts_mc) > 2 else None
            result_mc = migrate_csv(csv_mc, pair=pair_mc, tf=tf_mc)
            if result_mc["ok"]:
                respuesta = (f"✅ CSV migrado: {result_mc['pair']}/{result_mc['tf']}\n"
                             f"  {result_mc['original_rows']} → {result_mc['final_rows']} filas\n"
                             f"  Guardado: {result_mc['output_path']}")
            else:
                respuesta = f"❌ Error migrando CSV: {result_mc['error']}"

        elif _HAS_ROADMAP_VI and user_input.lower() in ["escanear csvs", "scan csvs", "listar csvs"]:
            found = scan_csv_directory()
            if found:
                lines_sc = [f"  CSVs encontrados ({len(found)}):"]
                for f_sc in found:
                    lines_sc.append(f"    {f_sc['pair']}/{f_sc['tf']} — {f_sc['rows']} filas — {f_sc['path']}")
                respuesta = "\n".join(lines_sc)
            else:
                respuesta = "Sin CSVs en el directorio CSVs/."

        elif _HAS_ROADMAP_VI and user_input.lower() in ["csvs activos", "active csvs"]:
            csvs_act = list_active_csvs()
            if csvs_act:
                lines_ca = [f"  Índice de CSVs activos ({len(csvs_act)}):"]
                for c_ca in csvs_act:
                    lines_ca.append(f"    {c_ca['pair']}/{c_ca['tf']} — {c_ca.get('rows','?')} filas")
                respuesta = "\n".join(lines_ca)
            else:
                respuesta = "Índice vacío. Usa 'escanear csvs' o 'migrar csv'."

        elif _HAS_ROADMAP_VI and user_input.lower().startswith("rolling info "):
            # rolling info <par> [tf]
            parts_ri = user_input[13:].strip().split()
            pair_ri = parts_ri[0].upper() if parts_ri else "EURUSD"
            tf_ri   = parts_ri[1].upper() if len(parts_ri) > 1 else "H1"
            rd_ri = get_rolling_dataset(pair_ri, tf_ri)
            rd_ri.load()
            respuesta = rd_ri.info() if hasattr(rd_ri, 'info') else str(rd_ri.validate())

        elif _HAS_ROADMAP_VI and user_input.lower() in ["scheduler start", "iniciar scheduler"]:
            sched_s = _get_scheduler()
            if not sched_s.is_running:
                sched_s.start(daemon=True)
                respuesta = "✅ Scheduler iniciado en background."
            else:
                respuesta = "⚠️ Scheduler ya está activo."

        elif _HAS_ROADMAP_VI and user_input.lower() in ["scheduler stop", "detener scheduler"]:
            sched_st = _get_scheduler()
            sched_st.stop()
            respuesta = "🔴 Scheduler detenido."

        elif _HAS_ROADMAP_VI and user_input.lower() in ["scheduler info", "estado scheduler vi"]:
            respuesta = _get_scheduler().status()

        elif _HAS_ROADMAP_VI and user_input.lower() in ["auto update", "actualizar datos"]:
            updater_au = _get_auto_updater()
            results_au = updater_au.update_all()
            if results_au:
                ok_au = sum(1 for r in results_au if r["ok"])
                respuesta = f"✅ Actualización completa: {ok_au}/{len(results_au)} pares OK.\n"
                respuesta += updater_au.status()
            else:
                respuesta = "Sin pares en el índice. Usa 'migrar csv' o 'descargar datos' primero."

        elif _HAS_ROADMAP_VI and user_input.lower().startswith("opportunity ranking"):
            # opportunity ranking [n]
            parts_or = user_input[19:].strip().split()
            top_n_or = int(parts_or[0]) if parts_or and parts_or[0].isdigit() else 10
            try:
                from forex.scheduler.auto_updater import get_auto_updater as _get_upd
                active_pairs = _get_upd()._load_active_pairs()
                if not active_pairs:
                    respuesta = (
                        f"  ℹ️ Sin pares activos en el índice. "
                        f"Usa 'migrar csv' o 'descargar datos' primero.\n"
                        f"  El ranking Top-{top_n_or} BUY/SELL se genera automáticamente "
                        f"una vez que el scheduler tiene señales activas."
                    )
                else:
                    ranker_op = _get_op_ranker(top_n=top_n_or)
                    # Construir señales dummy desde los pares activos (sin predicción viva)
                    dummy_signals = []
                    for ap in active_pairs[:20]:
                        dummy_signals.append(SignalInput(
                            pair=ap.get('pair','?'),
                            direction='BUY',
                            reliability_score=0.0,
                            win_rate_pct=0.0,
                            regime='unknown',
                        ))
                    ranking_op = ranker_op.rank(dummy_signals)
                    buy_n  = len(ranking_op.get('top_buy', []))
                    sell_n = len(ranking_op.get('top_sell', []))
                    respuesta = (
                        f"{ranker_op.format_ranking(ranking_op)}\n"
                        f"  (Señales live: {buy_n} BUY + {sell_n} SELL elegibles)\n"
                        f"  Para señales reales inicia el scheduler: 'scheduler start'"
                    )
            except Exception as e_or:
                respuesta = f"  Error generando ranking: {e_or}"

        # ── DOCTOR ───────────────────────────────────────
        elif user_input.lower() in ["astra doctor", "doctor", "diagnostico", "diagnóstico"]:
            if _HAS_DOCTOR:
                _run_doctor(verbose=True)
                respuesta = ""
            else:
                respuesta = "astra_doctor.py no disponible."

        # ── DEPLOYMENT REPORTS (First Deployment Experience) ────────
        elif user_input.lower().startswith("deploy check") or user_input.lower().startswith("deploy verify"):
            from deployment.first_run_validator import run_first_deployment_check
            result = run_first_deployment_check(force=True)
            respuesta = f"Deployment: {result['deployment_status']}\nReadiness: {result['readiness_status']}\n\nSimbolos: {result['symbols_passed']} OK / {result['symbols_failed']} FAIL / {result['symbols_partial']} PARTIAL\nReadiness: {result['readiness_passed']} OK / {result['readiness_failed']} FAIL / {result['readiness_warned']} WARN\n\nInformes guardados en reports/deployment/"

        elif user_input.lower() == "deploy readiness" or user_input.lower() == "deploy readiness check":
            from deployment.production_readiness import run_production_readiness
            from deployment.report_manager import ReportManager
            report = run_production_readiness()
            mgr = ReportManager()
            path = mgr.save_report("readiness", report.to_markdown(), metadata={
                "global_status": report.global_status,
                "passed": report.passed, "failed": report.failed, "warned": report.warned,
            })
            respuesta = f"Production Readiness: {report.global_status}\n{report.passed} OK / {report.failed} FAIL / {report.warned} WARN\n\nInforme guardado: {path}"

        elif user_input.lower() == "deploy reports" or user_input.lower() == "deploy history":
            from deployment.report_manager import ReportManager
            mgr = ReportManager()
            reports = mgr.list_reports()
            if not reports:
                respuesta = "No hay informes de despliegue. Ejecuta 'deploy check' para generarlos."
            else:
                lines = ["Informes de despliegue disponibles:", ""]
                for r in reports[:20]:
                    lines.append(f"  [{r.get('type', '?'):10s}] {r.get('timestamp', '?')} | {r.get('summary', '-')}")
                respuesta = "\n".join(lines)

        # ── ROBUSTNESS ──────────────────────────────────────────────────
        elif user_input.lower().startswith("robustness check") or user_input.lower().startswith("robustez check"):
            from robustness.dependency_validator import run_dependency_validation
            r = run_dependency_validation()
            lines = ["\n[ASTRA] DEPENDENCY VALIDATION", ""]
            for c in r.get("checks", []):
                icon = "OK" if c["status"] == "pass" else ("!!" if c["status"] == "fail" else "~~")
                lines.append(f"  [{icon}] {c['category']}/{c['name']}: {c['detail']}")
                if c.get("recommendation"):
                    lines.append(f"       -> {c['recommendation']}")
            lines.append(f"\n  Ready: {r['ready']} | Blocking: {r['blocking_count']} | Warnings: {r['warning_count']}")
            respuesta = "\n".join(lines)

        elif user_input.lower().startswith("robustness data") or user_input.lower().startswith("robustez data"):
            from robustness.data_integrity_checker import run_data_integrity_check
            report = run_data_integrity_check("CSVs")
            lines = ["\n[ASTRA] DATA INTEGRITY CHECK", ""]
            for r in report.results:
                icon = "OK" if r.status == "ok" else ("!!" if r.status == "error" else "~~")
                lines.append(f"  [{icon}] {r.pair} {r.timeframe}: {r.rows} rows, {len(r.issues)} issues")
                for issue in r.issues:
                    lines.append(f"       {issue.severity.upper()}: {issue.detail}")
            lines.append(f"\n  Files: {report.total_files} | OK: {report.ok_count} | Warnings: {report.warning_count} | Errors: {report.error_count}")
            respuesta = "\n".join(lines)

        elif user_input.lower().startswith("robustness models") or user_input.lower().startswith("robustez modelos"):
            from robustness.model_integrity_checker import run_model_integrity_check
            report = run_model_integrity_check(auto_recover=False)
            lines = ["\n[ASTRA] MODEL INTEGRITY CHECK", ""]
            for c in report.checks:
                icon = "OK" if c.status == "ok" else ("!!" if c.status == "blocked" else "++")
                lines.append(f"  [{icon}] {c.symbol}: {c.status}")
                for issue in c.issues:
                    lines.append(f"       - {issue}")
                if c.recovery_action:
                    lines.append(f"       Recovery: {c.recovery_action}")
            lines.append(f"\n  Models: {report.total_models} | OK: {report.ok_count} | Recovered: {report.recovered_count} | Blocked: {report.blocked_count}")
            respuesta = "\n".join(lines)

        elif user_input.lower().startswith("robustness recovery") or user_input.lower().startswith("robustez recovery"):
            from robustness.auto_recovery_history import get_recovery_history
            hist = get_recovery_history()
            events = hist.get_recent_events(20)
            lines = ["\n[ASTRA] RECOVERY HISTORY", ""]
            if not events:
                lines.append("  No recovery events recorded.")
            for e in events:
                lines.append(f"  [{e.timestamp}] {e.component}: {e.incident_type} -> {e.recovery_status} ({e.downtime_seconds}s)")
            stats = hist.get_stats()
            lines.append(f"\n  Total events: {stats.get('total_events', 0)}")
            respuesta = "\n".join(lines)

        elif user_input.lower().startswith("robustness provider") or user_input.lower().startswith("robustez provider"):
            from robustness.provider_verification import run_provider_verification
            report = run_provider_verification()
            lines = [f"\n[ASTRA] PROVIDER VERIFICATION", f"  Provider: {report.provider_name}", ""]
            for c in report.checks:
                icon = "OK" if c.status == "pass" else ("!!" if c.status == "fail" else "~~")
                lines.append(f"  [{icon}] {c.check_name}: {c.detail}")
                if c.recommendation:
                    lines.append(f"       -> {c.recommendation}")
            lines.append(f"\n  Status: {report.status}")
            respuesta = "\n".join(lines)

        elif user_input.lower().startswith("robustness benchmark") or user_input.lower().startswith("robustez benchmark"):
            from robustness.pipeline_benchmark import cmd_benchmark
            command_parts = user_input.split(maxsplit=2)
            benchmark_args = command_parts[2] if len(command_parts) == 3 else ""
            respuesta = cmd_benchmark(benchmark_args)

        elif user_input.lower().startswith("robustness wizard") or user_input.lower().startswith("robustez wizard"):
            from robustness.first_run_wizard import run_wizard
            result = run_wizard(auto_continue=True)
            lines = ["\n[ASTRA] FIRST RUN WIZARD", ""]
            for step in result.get("steps", []):
                icon = "OK" if step["status"] == "PASS" else "!!"
                lines.append(f"  [{icon}] {step['name']}: {step['detail']}")
            lines.append(f"\n  All passed: {result.get('all_passed', False)}")
            respuesta = "\n".join(lines)

        elif user_input.lower().startswith("robustness all") or user_input.lower().startswith("robustez all"):
            lines = ["\n[ASTRA] FULL ROBUSTNESS CHECK"]
            from robustness.dependency_validator import run_dependency_validation
            r = run_dependency_validation()
            lines.append(f"\n1. Dependencies: ready={r['ready']} blocking={r['blocking_count']} warnings={r['warning_count']}")
            from robustness.data_integrity_checker import run_data_integrity_check
            dr = run_data_integrity_check("CSVs")
            lines.append(f"2. Data Integrity: files={dr.total_files} ok={dr.ok_count} warn={dr.warning_count} err={dr.error_count}")
            from robustness.model_integrity_checker import run_model_integrity_check
            mr = run_model_integrity_check(auto_recover=False)
            lines.append(f"3. Models: total={mr.total_models} ok={mr.ok_count} blocked={mr.blocked_count}")
            from robustness.provider_verification import run_provider_verification
            pv = run_provider_verification()
            lines.append(f"4. Provider: {pv.provider_name} status={pv.status}")
            from robustness.auto_recovery_history import get_recovery_history
            hist = get_recovery_history()
            lines.append(f"5. Recovery events: {hist.get_stats().get('total_events', 0)}")
            from robustness.pipeline_benchmark import get_benchmark_evidence
            benchmark = get_benchmark_evidence(limit=1)
            lines.append(
                f"6. Benchmark: {benchmark['status']} "
                f"stages={len(benchmark.get('stats', {}))}"
            )
            respuesta = "\n".join(lines)

        # ── API INTERNA ───────────────────────────────
        elif user_input.lower() in ["api start", "iniciar api"]:
            if _HAS_API:
                if _api_running():
                    respuesta = f"⚠️  API ya activa en puerto {_ASTRA_API_PORT}."
                else:
                    ok = _start_api(daemon=True)
                    respuesta = f"✅ API iniciada en http://localhost:{_ASTRA_API_PORT}" if ok else "❌ Error iniciando API."
            else:
                respuesta = "astra_api.py no disponible."

        elif user_input.lower() in ["api stop", "detener api"]:
            if _HAS_API:
                _stop_api()
                respuesta = "🔴 API detenida."
            else:
                respuesta = "astra_api.py no disponible."

        elif user_input.lower() in ["api status", "estado api"]:
            if _HAS_API:
                respuesta = _api_status_str()
            else:
                respuesta = "astra_api.py no disponible."

        # ── DEV LOG ──────────────────────────────────
        elif user_input.lower().startswith("dev log"):
            if _HAS_DEV_LOG:
                respuesta = _cmd_dev_log(user_input[7:].strip())
            else:
                respuesta = "dev_log.py no disponible."

        # ── EXTRA MODULES ────────────────────────────────
        elif user_input in comandos_extra:
            respuesta = comandos_extra[user_input]()

        # ── GPT FALLBACK ─────────────────────────────────
        else:
            respuesta = process_request(user_input)

    except Exception as e:
        respuesta = f"{Fore.RED}Error: {e}{Style.RESET_ALL}"
    return respuesta


if __name__ == "__main__":
    init_db()
    init_project_db()
    init_signal_db()
    _print_banner()
    _session_summary = session_summary()
    if _session_summary.strip():
        print(_session_summary)

    while True:
        try:
            user_input = input(Fore.CYAN + "Tú: " + Style.RESET_ALL).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSaliendo de ASTRA...")
            break

        if not user_input:
            continue

        respuesta = None

        if user_input.lower() in ["salir", "exit", "quit"]:
            print(Fore.GREEN + "¡Hasta luego!")
            break

        respuesta = dispatch_command(user_input)


        if respuesta is not None and respuesta != "":
            _print_result(respuesta)
            # ── Guardar en memoria para que el LLM sepa qué ejecutaste ──
            try:
                if user_input and not user_input.lower() in ["ayuda", "help", "?", "salir", "exit", "quit"]:
                    # Solo registrar comandos no triviales
                    _cat   = _category_from_cmd(user_input)
                    _pair  = _extract_pair(user_input)
                    _summ  = _summarize_result(respuesta)
                    if _summ and len(_summ) > 10:
                        log_command(user_input, _summ, pair=_pair, category=_cat)
                        guardar_memoria(user_input, _summ)
            except Exception:
                pass
