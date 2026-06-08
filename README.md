# Copilot (IA-LOCAL)
## Informacion General
Esta IA esta hecha a partir de aportes de Nicolas Saez Valenzuela, ChatGPT y analisis activo de Copilot con tal de brindar una experiencia mas completa y complementada por modulos extensos con tal de concentrar una learning AI en base a un sistema local PC de las siguientes especificaciones

PROCESADOR:

Intel(R) Core (TM) I5-10300H CPU @2.5GHz

RAM:

16GB RAM

GPU:

NVIDIA 1650ti 8GB VRAM 

## API
Actualmente el funcionamiento de esta IA es gracias a la API de Open AI

name: copi

ID: key_3uC3DbwL1KZFUHJa

model="gpt-3.5-turbo"

## Estructura
Esta IA Local se compone de 10 codigos Python para asegurar eficiencia y rapidez en la ejecucion.
El programa puente (main.py) viene siendo la central de los comandos ingresados para ser rediregido a funciones/herramientas de utilidad.
Se incluyen dos codigos adicionales para verificar la integridad de los modulos presentes en cada codigo Python.

Notese que se necesita activar un entorno virtual (activate.bat) antes de ejecutar el main.

A continuacion se dan las caracteristicas y detalles del programa principal mas los anexos.


# Programa Puente (main.py + iniciar_astra.bat)

- ### Main.py

El nucleo del esqueleto organiza las entradas del usuario y repone todo en una funcion general, en esta funcion principal estan seccionados los comandos 

<details>
<summary>Ver comandos</summary>
	
- `lee pdf [nombre_archivo] [directorio]`
- `lee word [nombre_archivo] [directorio]`
- `lee excel [nombre_archivo] [directorio]`
- `lee csv [nombre_archivo] [directorio]`
- `analiza csv [nombre_archivo] [directorio]`
- `escribe pdf [nombre_archivo] [contenido del archivo]`
- `escribe word [nombre_archivo] [contenido del archivo]`
- `escribe excel [nombre_archivo] [contenido del archivo]`
- `escribe csv [nombre_archivo] [contenido del archivo]`
- `grafica csv [nombre_archivo] [directorio]`
- `tabla [nombre_archivo] [directorio]`
- `rich [nombre_archivo] [directorio]`
- `voz a texto`
- `texto a voz [texto]`
- `analiza audio [nombre_archivo]`
- `reproducir audio [nombre_archivo]`
- `convertir audio [nombre_archivo] [formato_salida]`
- `descargar audio youtube [URL]`
- `cifra archivo [nombre_archivo]`
- `hash pass [contraseña]`
- `verify pass [contraseña] [hash]`
- `crear jwt [datos]`
- `verificar jwt [token]`

</details>

<details>
<summary>Ver contenido de main.py</summary>

```python
# main.py

from memory import init_db
from io_files import leer_pdf, leer_word, leer_excel, leer_csv, escribe_pdf, escribe_word, escribe_excel, escribe_csv
from ai_models import ask_openai, system_status, torch_demo, tensorflow_demo, keras_demo, sklearn_demo, calcular_integral, entrenar_modelo_sklearn
from web_tools import extrae_web, traducir, descargar_youtube, httpx_demo, aiohttp_demo, socketio_demo, fastapi_demo, flask_demo, subir_archivo_azure, consumir_api_grpc
from audio_video import voz_a_texto, texto_a_voz, analiza_audio, reproducir_audio, convertir_audio, descargar_audio_youtube
from visualization import grafica_csv, mostrar_tabla, mostrar_rich, crear_pdf, procesar_imagen_skimage, mostrar_gui_pyqt
from security import cifra_archivo, hash_password, verify_password, passlib_hash, passlib_verify, crear_jwt, verificar_jwt, paramiko_demo
from utils import system_status as utils_status, barra_progreso, tarea_programada, simular_tecla, simular_click, bloquear_archivo, iniciar_monitor, obtener_fecha_arrow, serializar_orjson
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

if __name__ == "__main__":
    init_db()
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
            respuesta = ask_openai(user_input)

        print(Fore.YELLOW + "Copilot: " + Style.RESET_ALL + str(respuesta))
```

</details>

<details>
<summary>Ver contenido de iniciar_astra.bat</summary>

```bat
@echo off
cd C:\Users\nicol\copilot_wrapper\venv\Scripts
call activate.bat
cd ..\astra
python main.py
pause
```

</details>


# Memoria de la IA (memory.py + memory.db)

<details>
<summary>Ver contenido de memory.py</summary>

```python

# memory.py

import sqlite3
import time

def init_db():
    """Inicializa la base de datos SQLite para guardar memoria de la IA."""
    conn = sqlite3.connect("../memoria.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS memoria (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_input TEXT,
                    ai_response TEXT,
                    timestamp TEXT
                )""")
    conn.commit()
    conn.close()

def guardar_memoria(user_input, ai_response):
    """Guarda una interacción en la base de datos."""
    conn = sqlite3.connect("../memoria.db")
    c = conn.cursor()
    c.execute("INSERT INTO memoria (user_input, ai_response, timestamp) VALUES (?, ?, ?)",
              (user_input, ai_response, time.ctime()))
    conn.commit()
    conn.close()

def cargar_memoria(limit=10):
    """Carga las últimas interacciones guardadas en memoria."""
    conn = sqlite3.connect("../memoria.db")
    c = conn.cursor()
    c.execute("SELECT user_input, ai_response FROM memoria ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    memoria = ""
    for u, a in rows[::-1]:
        memoria += f"Tú: {u}\nCopilot: {a}\n"
    return memoria

```

</details>

- ### Memory.db

Una vez ejecutado el programa principal por primera instancia, automaticamente se creara el archivo memory.db, si no es el caso se modificara y añadira la conversacion con la IA Local.




### Conexion IA Externos (ai_models.py)

<details>
<summary>Ver contenido de ai_models.py</summary>

```python
# ai_models.py
def main():
    print("Hola desde el main!")

if __name__ == "__main__":
    main()
```
</details>

### Programa de Audio/Video (audio_video.py)

<details>
<summary>Ver contenido de audio_video.py</summary>

```python
# audio_video.py
def main():
    print("Hola desde el main!")

if __name__ == "__main__":
    main()
```
</details>

### Programa de Creacion/Lectura/Analisis de Archivos Word/Excel/CSV/Python/PDF (io_files.py)

<details>
<summary>Ver contenido de io_files.py</summary>

```python
# io_files.py
def main():
    print("Hola desde el main!")

if __name__ == "__main__":
    main()
```
</details>

### Comentarios sobre las limitaciones del programa (readme)
### Programa de Calculo Simbolico, Memoria Vectorial y Base De Datos con IA (modules_extra.py)

<details>
<summary>Ver contenido de modules_extra.py</summary>

```python
# modules_extra.py
def main():
    print("Hola desde el main!")

if __name__ == "__main__":
    main()
```
</details>

### Programa de Cifrado/Encriptacion de Archivos (security.py)

<details>
<summary>Ver contenido de security.py</summary>

```python
# security.py
def main():
    print("Hola desde el main!")

if __name__ == "__main__":
    main()
```
</details>

### Programa de Monitoreo del PC (utils.py)

<details>
<summary>Ver contenido de utils.py</summary>

```python
# utils.py
def main():
    print("Hola desde el main!")

if __name__ == "__main__":
    main()
```
</details>

### Programa de Creacion de Grafico CSV y Tabla de DataFrame Pandas (visualization.py)

<details>
<summary>Ver contenido de visualization.py</summary>

```python
# visualization.py
def main():
    print("Hola desde el main!")

if __name__ == "__main__":
    main()
```
</details>

### Grafico de Ejemplo
### Tabla de Ejemplo
### Programa de Extraccion/Peticion de Informacion en Internet (web_tools.py)

<details>
<summary>Ver contenido de web_tools.py</summary>

```python
# web_tools.py
def main():
    print("Hola desde el main!")

if __name__ == "__main__":
    main()
```
</details>

## Modulos (Instalados y/o Integrados)
Aqui el archivo con el listado de modulos Instalados e Integrados
 https://docs.google.com/spreadsheets/d/1I2JpcZ6_V_WUdXkkYkP7MZ1fgQcPW6y73xBbtZjOfHI/edit?usp=sharing

## Actualizacion de Modulos (Semanal)
## Ejemplos de Ejecucion con Dataset

