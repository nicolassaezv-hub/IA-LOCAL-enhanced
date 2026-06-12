# main.py

from memory import init_db
from io_files import leer_pdf, leer_word, leer_excel, leer_csv, escribe_pdf, escribe_word, escribe_excel, escribe_csv
from ai_models import ask_openai, system_status, torch_demo, tensorflow_demo, keras_demo, sklearn_demo, calcular_integral, entrenar_modelo_sklearn
from web_tools import extrae_web, traducir, descargar_youtube, httpx_demo, aiohttp_demo, socketio_demo, fastapi_demo, flask_demo, subir_archivo_azure, consumir_api_grpc
from audio_video import voz_a_texto, texto_a_voz, analiza_audio, reproducir_audio, convertir_audio, descargar_audio_youtube
from visualization import grafica_csv, mostrar_tabla, mostrar_rich, crear_pdf, procesar_imagen_skimage, mostrar_gui_pyqt
from security import cifra_archivo, hash_password, verify_password, passlib_hash, passlib_verify, crear_jwt, verificar_jwt, paramiko_demo
from utils import system_status as utils_status, barra_progreso, tarea_programada, simular_tecla, simular_click, bloquear_archivo, iniciar_monitor, obtener_fecha_arrow, serializar_orjson
from progress_utils import (
    show_progress,
    progress_steps,
    progress_iterator
)
import subprocess
from colorama import Fore, Style
def start_redis():
    try:
        # Arranca Redis dentro de WSL
        subprocess.run(["wsl", "redis-server", "--daemonize", "yes"], check=True)
        print("Redis iniciado en WSL")
    except Exception as e:
        print("No se pudo iniciar Redis:", e)

# Llamar al inicio del programa
start_redis()

from modules_extra import comandos_extra
from tool_registry import TOOLS
from intent_router import classify_intent
from astra_agent import process_request

if __name__ == "__main__":
    init_db()
	print("Tool Registry cargado:", len(TOOLS), "herramientas")
    print(Fore.GREEN + "=== Astra modular final ===" + Style.RESET_ALL)
    while True:
        user_input = input(Fore.CYAN + "Tú: " + Style.RESET_ALL)

        if user_input.lower() in ["salir","exit","quit"]:
            break
        elif user_input.startswith("analiza codigo"):
            import ast
            partes = user_input.split(" ")[2:]  # lista de archivos
            archivos = partes if partes else ["main.py"]
            for archivo in archivos:
                try:
                    with open(archivo, "r", encoding="utf-8") as f:
                        code = f.read()
                    tree = ast.parse(code)
                    funciones = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
                    print(f"Funciones encontradas en {archivo}: {funciones}")
                    respuesta = ask_openai("Analiza este código y dame mejoras:\n" + code)
                    print(f"Copilot ({archivo}): {respuesta}")
                except Exception as e:
                    print(f"Error analizando {archivo}: {e}")

	     # === IO Files ===
        elif user_input.startswith("crea py"):
            partes = user_input.split(" ", 2)
            respuesta = crea_py(partes[1], partes[2])
        elif user_input == "integral":
            print(calcular_integral("x**2", "x", 0, 1))

        elif user_input == "sklearn":
            print(entrenar_modelo_sklearn())

        elif user_input == "azure":
            print(subir_archivo_azure("test.txt"))

        elif user_input == "grpc":
            print(consumir_api_grpc())

        elif user_input == "imagen":
            print(procesar_imagen_skimage())

        elif user_input == "gui":
            mostrar_gui_pyqt()

        elif user_input == "fecha":
            print(obtener_fecha_arrow())

        elif user_input == "json":
            print(serializar_orjson({"msg": "ok"}))
	
        elif user_input.startswith("lee pdf"):
            respuesta = leer_pdf(user_input.split(" ",2)[-1])
        elif user_input.startswith("lee word"):
            respuesta = leer_word(user_input.split(" ",2)[-1])
        elif user_input.startswith("lee excel"):
            respuesta = leer_excel(user_input.split(" ",2)[-1])
        elif user_input.startswith("lee csv"):
            respuesta = leer_csv(user_input.split(" ",2)[-1])
        elif user_input.startswith("analiza csv"):
            respuesta = leer_csv(user_input.split(" ",2)[-1], analizar=True)
        elif user_input.startswith("escribe pdf"):
            partes = user_input.split(" ",2)
            respuesta = escribe_pdf(partes[1], partes[2])
        elif user_input.startswith("escribe word"):
            partes = user_input.split(" ",2)
            respuesta = escribe_word(partes[1], partes[2])
        elif user_input.startswith("escribe excel"):
            partes = user_input.split(" ",2)
            respuesta = escribe_excel(partes[1], partes[2])
        elif user_input.startswith("escribe csv"):
            partes = user_input.split(" ",2)
            respuesta = escribe_csv(partes[1], partes[2])

        # === Visualization ===
        elif user_input.startswith("grafica csv"):
            respuesta = grafica_csv(user_input.split(" ",2)[-1])
        elif user_input.startswith("tabla"):
            import pandas as pd
            df = pd.read_csv(user_input.split(" ",2)[-1])
            respuesta = mostrar_tabla(df)
        elif user_input.startswith("rich"):
            respuesta = mostrar_rich(user_input.split(" ",2)[-1])
        elif user_input.startswith("crear pdf"):
            partes = user_input.split(" ",2)
            respuesta = crear_pdf(partes[1], partes[2])

        # === Web Tools ===
        elif user_input.startswith("extrae web"):
            respuesta = extrae_web(user_input.split(" ",2)[-1])
        elif user_input.startswith("traducir"):
            respuesta = traducir(user_input.split(" ",2)[-1])
        elif user_input.startswith("youtube"):
            respuesta = descargar_youtube(user_input.split(" ",2)[-1])
        elif user_input.startswith("httpx demo"):
            respuesta = httpx_demo()
        elif user_input.startswith("aiohttp demo"):
            import asyncio
            respuesta = asyncio.run(aiohttp_demo())
        elif user_input.startswith("socketio demo"):
            respuesta = socketio_demo()
        elif user_input.startswith("fastapi demo"):
            respuesta = fastapi_demo()
        elif user_input.startswith("flask demo"):
            respuesta = flask_demo()

        # === Audio/Video ===
        elif user_input.startswith("voz a texto"):
            respuesta = voz_a_texto()
        elif user_input.startswith("texto a voz"):
            respuesta = texto_a_voz(user_input.split(" ",2)[-1])
        elif user_input.startswith("analiza audio"):
            respuesta = analiza_audio(user_input.split(" ",2)[-1])
        elif user_input.startswith("reproducir audio"):
            respuesta = reproducir_audio(user_input.split(" ",2)[-1])
        elif user_input.startswith("convertir audio"):
            partes = user_input.split(" ",2)
            respuesta = convertir_audio(partes[1], partes[2] if len(partes) > 2 else "mp3")
        elif user_input.startswith("descargar audio youtube"):
            respuesta = descargar_audio_youtube(user_input.split(" ",2)[-1])

        # === Security ===
        elif user_input.startswith("cifra archivo"):
            respuesta = cifra_archivo(user_input.split(" ",2)[-1])
        elif user_input.startswith("hash pass"):
            respuesta = hash_password(user_input.split(" ",2)[-1])
        elif user_input.startswith("verify pass"):
            partes = user_input.split(" ",2)
            respuesta = verify_password(partes[1], partes[2])
        elif user_input.startswith("passlib hash"):
            respuesta = passlib_hash(user_input.split(" ",2)[-1])
        elif user_input.startswith("passlib verify"):
            partes = user_input.split(" ",2)
            respuesta = passlib_verify(partes[1], partes[2])
        elif user_input.startswith("crear jwt"):
            respuesta = crear_jwt({"user":"nico"})
        elif user_input.startswith("verificar jwt"):
            respuesta = verificar_jwt(user_input.split(" ",2)[-1])
        elif user_input.startswith("paramiko demo"):
            respuesta = paramiko_demo()

        # === Utils ===
        elif user_input.startswith("estado pc"):
            respuesta = utils_status()
        elif user_input.startswith("barra progreso"):
            respuesta = barra_progreso()
        elif user_input.startswith("tarea programada"):
            respuesta = tarea_programada()
        elif user_input.startswith("simular tecla"):
            respuesta = simular_tecla(user_input.split(" ",2)[-1])
        elif user_input.startswith("simular click"):
            respuesta = simular_click()
        elif user_input.startswith("bloquear archivo"):
            respuesta = bloquear_archivo(user_input.split(" ",2)[-1])
        elif user_input.startswith("monitor archivos"):
            respuesta = iniciar_monitor(user_input.split(" ",2)[-1])

        # === AI Models ===
        elif user_input.startswith("torch demo"):
            respuesta = torch_demo()
        elif user_input.startswith("tensorflow demo"):
            respuesta = tensorflow_demo()
        elif user_input.startswith("keras demo"):
            respuesta = keras_demo()
        elif user_input.startswith("sklearn demo"):
            respuesta = sklearn_demo()

        # === NUEVOS Módulos Extra ===
        elif user_input in comandos_extra:
            try:
                respuesta = comandos_extra[user_input]()
            except Exception as e:
                respuesta = f"Error ejecutando comando extra: {e}"

        # === Default: OpenAI ===
        else:
            respuesta = process_request(user_input)

        print(Fore.YELLOW + "Copilot: " + Style.RESET_ALL + str(respuesta))
