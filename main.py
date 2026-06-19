# main.py

import os
import subprocess
import json
from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)

# ── Lazy imports to keep startup fast ──────────────────────
from memory import init_db
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


def _print_banner():
    print(Fore.GREEN + "╔══════════════════════════════════════════╗")
    print(Fore.GREEN + "║        ASTRA  —  Modular AI System       ║")
    print(Fore.GREEN + "║  Forex · ML · Security · Documents · Web ║")
    print(Fore.GREEN + "╚══════════════════════════════════════════╝")
    print(Fore.CYAN  + f"  {len(TOOLS)} tools loaded  |  type 'ayuda' for commands\n")


def _print_result(respuesta):
    if isinstance(respuesta, dict):
        print(Fore.YELLOW + "Copilot: " + Style.RESET_ALL)
        print(json.dumps(respuesta, indent=2, default=str, ensure_ascii=False))
    else:
        print(Fore.YELLOW + "Copilot: " + Style.RESET_ALL + str(respuesta))


# ═══════════════════════════════════════════════════════════
#  FOREX HELPERS
# ═══════════════════════════════════════════════════════════

def _forex_train(csv_path: str):
    """Train XGBoost model on a CSV dataset."""
    from forex.prediction.integrated_pipeline import ForexIntegratedPipeline
    print(Fore.CYAN + f"\n[ASTRA] Training XGBoost on: {csv_path}")
    pipeline = ForexIntegratedPipeline()
    return pipeline.train(csv_path)


def _forex_predict(csv_path: str):
    """Run prediction using trained model on a CSV."""
    from forex.prediction.integrated_pipeline import ForexIntegratedPipeline
    show_progress("Running Forex Prediction", 2)
    pipeline = ForexIntegratedPipeline()
    return pipeline.predict(csv_path)


def _forex_backtest(csv_path: str):
    """Run backtester on held-out test portion of CSV."""
    from forex.prediction.integrated_pipeline import ForexIntegratedPipeline
    show_progress("Running Backtest", 3)
    pipeline = ForexIntegratedPipeline()
    return pipeline.backtest(csv_path)


def _forex_full(csv_path: str):
    """Train + predict + backtest all in one run."""
    from forex.prediction.integrated_pipeline import ForexIntegratedPipeline
    print(Fore.CYAN + f"\n[ASTRA] Full Forex Analysis Pipeline: {csv_path}")
    pipeline = ForexIntegratedPipeline()
    return pipeline.run(csv_path, mode="full")


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


def _ayuda():
    help_text = f"""
{Fore.GREEN}╔══════════════════════════════════════════════════════════════╗
║                   ASTRA — COMMAND REFERENCE                   ║
╚══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}

{Fore.CYAN}── FOREX ──────────────────────────────────────────────────────{Style.RESET_ALL}
  train forex <csv>              Train XGBoost model on your CSV
  predict forex <csv>            Predict direction from trained model
  backtest forex <csv>           Backtest model on held-out data
  full forex <csv>               Train + Predict + Backtest in one shot
  analiza forex <csv> <symbol>   Full technical report (RSI/MACD/EMA...)
  lista mercados                 Show all supported pairs & commodities
  historial forex <symbol>       View saved analysis history
  compara forex <symbol>         Compare last 5 analyses of a pair
  mercados analizados            List all markets ever analyzed

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
  <anything else>                Sent to GPT (requires OPENAI_API_KEY)
"""
    print(help_text)
    return ""


# ═══════════════════════════════════════════════════════════
#  MAIN LOOP
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    init_db()
    _print_banner()

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

            # ── FOREX: BACKTEST ──────────────────────────────
            elif user_input.startswith("backtest forex "):
                csv_path = user_input[len("backtest forex "):].strip()
                respuesta = _forex_backtest(csv_path)

            # ── FOREX: FULL PIPELINE ─────────────────────────
            elif user_input.startswith("full forex "):
                csv_path = user_input[len("full forex "):].strip()
                respuesta = _forex_full(csv_path)

            # ── FOREX: TECHNICAL ANALYTICS ───────────────────
            elif user_input.startswith("analiza forex "):
                parts = user_input[len("analiza forex "):].strip().split(" ", 1)
                if len(parts) == 2:
                    respuesta = _forex_analiza(parts[0], parts[1])
                elif len(parts) == 1:
                    respuesta = analyze_market_file(None, parts[0])
                else:
                    respuesta = "Uso: analiza forex <csv_path> <symbol>  ó  analiza forex <symbol>"

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
                        print(f"Copilot ({archivo}): {respuesta}")
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
