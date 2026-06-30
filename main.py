# main.py

import os
import subprocess
import json
from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)

# ── Lazy imports to keep startup fast ──────────────────────
from memory import init_db
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
from forex.forex_memory import list_saved_markets

# ── Business Intelligence imports ───────────────────────────
from forex.business.business_pipeline import BusinessPipeline


def _print_banner():
    print(Fore.GREEN + "╔══════════════════════════════════════════╗")
    print(Fore.GREEN + "║        ASTRA  —  Modular AI System       ║")
    print(Fore.GREEN + "║  Forex · ML · Security · Documents · Web ║")
    print(Fore.GREEN + "╚══════════════════════════════════════════╝")
    print(Fore.CYAN  + f"  {len(TOOLS)} tools loaded  |  type 'ayuda' for commands\n")


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


def _forex_full(csv_path: str):
    """
    Pipeline completo: tune -> train -> predict -> backtest.
    Detecta automaticamente H4 y D1 si existen en carpetas hermanas.
    """
    from forex.prediction.integrated_pipeline import ForexIntegratedPipeline

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
    else:
        print(Fore.RED + f"     Entrenamiento fallo: {train_r}" + Style.RESET_ALL)
        return ""

    # ── 3/4 PREDICT ───────────────────────────────────────────
    print(Fore.YELLOW + "\n[3/4] Generando senal de la ultima vela..." + Style.RESET_ALL)
    pred_r = pipeline.predict(csv_path, path_h4=path_h4, path_d1=path_d1)
    if isinstance(pred_r, dict) and "error" not in pred_r:
        try:
            save_signal(pred_r, csv_path)
        except Exception:
            pass
        print(_format_signal(pred_r))
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

    print()
    print(Fore.GREEN + "[ASTRA] ══ FULL PIPELINE COMPLETADO ══" + Style.RESET_ALL)
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
  multi forex <csv>              Consensus signal across 3 horizons (5/10/20 candles)
  backtest forex <csv>           Backtest model on held-out data
  full forex <csv>               Train + Predict + Backtest in one shot
  scan forex <folder>            Scan all CSVs in folder, rank signals by strength
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

        try:
            # ── EXIT ────────────────────────────────────────
            if user_input.lower() in ["salir", "exit", "quit"]:
                print(Fore.GREEN + "¡Hasta luego!")
                break

            # ── HELP ─────────────────────────────────────────
            elif user_input.lower() in ["ayuda", "help", "?"]:
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

            # ── FOREX: PREDICT ───────────────────────────────
            elif user_input.startswith("predict forex "):
                csv_path = user_input[len("predict forex "):].strip()
                respuesta = _forex_predict(csv_path)

            elif user_input.startswith("predecir forex "):
                csv_path = user_input[len("predecir forex "):].strip()
                respuesta = _forex_predict(csv_path)

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
                continue

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

            # ── EXTRA MODULES ────────────────────────────────
            elif user_input in comandos_extra:
                respuesta = comandos_extra[user_input]()

            # ── GPT FALLBACK ─────────────────────────────────
            else:
                respuesta = process_request(user_input)

        except Exception as e:
            respuesta = f"{Fore.RED}Error: {e}{Style.RESET_ALL}"

        if respuesta is not None and respuesta != "":
            _print_result(respuesta)
