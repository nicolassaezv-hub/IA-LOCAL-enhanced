# Copilot (IA-LOCAL)

## Informacion General

Esta IA esta hecha a partir de aportes de Nicolas Saez Valenzuela, ChatGPT y analisis activo de Copilot con tal de brindar una experiencia mas completa y complementada por modulos extensos con tal de concentrar una learning AI en base a un sistema local PC de las siguientes especificaciones

PROCESADOR:

Intel(R) Core (TM) I5-10300H CPU @2.5GHz

RAM:

16GB RAM

GPU:

NVIDIA 1650ti 8GB VRAM 

# API

Actualmente el funcionamiento de esta IA es gracias a la API de Open AI

name: copi

ID: key_3uC3DbwL1KZFUHJa

model="gpt-3.5-turbo"

# Estructura

Esta IA Local se compone de 10 codigos Python para asegurar eficiencia y rapidez en la ejecucion.
El programa puente (main.py) viene siendo la central de los comandos ingresados para ser rediregido a funciones/herramientas de utilidad.
Se incluyen dos codigos adicionales para verificar la integridad de los modulos presentes en cada codigo Python.

Notese que se necesita activar un entorno virtual (activate.bat) antes de ejecutar el main.

A continuacion se dan las caracteristicas y detalles del programa principal mas los anexos.

# Comandos y Programa Puente (main.py + iniciar_astra.bat)
### Comandos

El nucleo del esqueleto organiza las entradas del usuario y repone todo en una funcion general, en esta funcion principal estan seccionados los comandos 

<details>
<summary>Ver comandos</summary>

- `aiohttp demo`    
- `analiza audio [nombre_archivo]`
- `analiza codigo [archivos]`      
- `analiza csv [nombre_archivo] [directorio]`
- `azure`                                          
- `barra progreso`            
- `bloquear archivo <archivo>` 
- `cifra archivo [nombre_archivo]`
- `convertir audio [nombre_archivo] [formato_salida]`
- `crea py <archivo> <contenido>`                    
- `crear jwt [datos]`
- `crear pdf <archivo> <texto>`  
- `descargar audio youtube [URL]`
- `escribe csv [nombre_archivo] [contenido del archivo]`
- `escribe excel [nombre_archivo] [contenido del archivo]`
- `escribe pdf [nombre_archivo] [contenido del archivo]`
- `escribe word [nombre_archivo] [contenido del archivo]`
- `estado pc`                 
- `extrae web <url>` 
- `fastapi demo`     
- `fecha`                                      
- `flask demo`           
- `grafica csv [nombre_archivo] [directorio]`
- `grpc`                                             
- `gui`                                            
- `hash pass [contraseña]`
- `httpx demo`      
- `imagen`                                   
- `integral`                                  
- `json`                                      
- `keras demo`     
- `lee csv [nombre_archivo] [directorio]`
- `lee excel [nombre_archivo] [directorio]`
- `lee pdf [nombre_archivo] [directorio]`
- `lee word [nombre_archivo] [directorio]`
- `monitor archivos <ruta>`    
- `paramiko demo`                   
- `passlib hash <contraseña>`       
- `passlib verify <password> <hash>`                                  
- `reproducir audio [nombre_archivo]`
- `rich [nombre_archivo] [directorio]`
- `salir` / `exit` / `quit`                        
- `simular click`              
- `simular tecla <tecla>`     
- `sklearn demo`  
- `sklearn`                                        
- `socketio demo`    
- `tabla [nombre_archivo] [directorio]`
- `tarea programada`           
- `tensorflow demo` 
- `texto a voz [texto]`
- `torch demo`      
- `traducir <texto>` 
- `verificar jwt [token]`
- `verify pass [contraseña] [hash]`
- `voz a texto`
- `youtube <url>`    

</details>

- ### main.py

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

- ### iniciar_astra.bat

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


- ### memory.py

Una vez ejecutado el programa principal por primera instancia, automaticamente se creara el archivo memory.db, si no es el caso se modificara y añadira la conversacion con la IA Local. La base de datos guarda y carga en cada interaccion

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

[memory.db](memory.db)





# Conexion IA Externos (ai_models.py)

- ### ai_models.py
  Este codigo compone la interaccion chat entre usuario e IA como tambien la accesibilidad a librerias torch, scikit, tensorflow y Pytorch
<details>
<summary>Ver contenido de ai_models.py</summary>

```python

# ai_models.py
from openai import OpenAI
import psutil
from memory import cargar_memoria, guardar_memoria

# Librerías de IA/ML que ya tienes instaladas
import torch
import tensorflow as tf
import keras
import numpy as np
import sympy as sp
import torchvision.models as models
import torchaudio
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
# Inicializar cliente OpenAI
client = OpenAI()

# === Estado del sistema ===
def system_status():
    """Devuelve el estado actual de CPU y RAM."""
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    return f"CPU: {cpu}% | RAM: {ram}%"

# === Interacción con OpenAI ===
def ask_openai(user_message):
    """Envía un mensaje a OpenAI con memoria previa y estado del sistema."""
    memoria = cargar_memoria(limit=10)
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role":"system","content":"You are Copilot integrated in a local wrapper."},
                {"role":"user","content":f"Memoria previa:\n{memoria}\n\nNueva entrada:\n{user_message}\n\nEstado del PC: {system_status()}"}
            ]
        )
        reply = response.choices[0].message.content
        guardar_memoria(user_message, reply)
        return reply
    except Exception as e:
        return f"Error al consultar OpenAI: {e}"

# === Ejemplo de integración con Torch ===
def torch_demo():
    """Ejemplo simple con Torch: multiplicación de tensores."""
    try:
        a = torch.tensor([1, 2, 3])
        b = torch.tensor([4, 5, 6])
        return f"Torch demo: {a * b}"
    except Exception as e:
        return f"Error en Torch demo: {e}"

# === Ejemplo de integración con TensorFlow ===
def tensorflow_demo():
    """Ejemplo simple con TensorFlow: suma de tensores."""
    try:
        a = tf.constant([1, 2, 3])
        b = tf.constant([4, 5, 6])
        return f"TensorFlow demo: {tf.add(a, b).numpy()}"
    except Exception as e:
        return f"Error en TensorFlow demo: {e}"
def calcular_integral(expr, var, a, b):
    x = sp.Symbol(var)
    integral = sp.integrate(sp.sympify(expr), (x, a, b))
    return f"Integral de {expr} entre {a} y {b}: {integral}"

def entrenar_modelo_sklearn():
    X = np.array([[0,0],[1,1],[2,2],[3,3]])
    y = np.array([0,1,1,1])

    # Separar entrenamiento y prueba
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25)

    # Entrenar modelo
    model = LogisticRegression().fit(X_train, y_train)

    # Predicción de prueba
    pred = model.predict(X_test)
    score = model.score(X_test, y_test)
    return f"Predicciones: {pred}, Score: {score}"

def demo_torchvision():
    resnet = models.resnet18()
    return f"ResNet18 cargado, número de parámetros: {sum(p.numel() for p in resnet.parameters())}"

def demo_torchaudio():
    return f"Torchaudio versión: {torchaudio.__version__}"

# === Ejemplo de integración con Keras ===
def keras_demo():
    """Ejemplo simple con Keras: modelo secuencial."""
    try:
        model = keras.Sequential([
            keras.layers.Dense(10, activation="relu", input_shape=(5,)),
            keras.layers.Dense(1, activation="sigmoid")
        ])
        return "Modelo Keras creado correctamente."
    except Exception as e:
        return f"Error en Keras demo: {e}"

# === Ejemplo de integración con Scikit-learn ===
def sklearn_demo():
    """Ejemplo simple con Scikit-learn: división de dataset."""
    try:
        X = np.arange(10).reshape(-1, 1)
        y = np.arange(10)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
        return f"Train size: {len(X_train)}, Test size: {len(X_test)}"
    except Exception as e:
        return f"Error en Scikit-learn demo: {e}"
```

</details>

# Programa de Audio/Video (audio_video.py)

- ### audio_video.py
  
Este programa da paso a usar funciones de visualizacion creacion multimedia destacando:
- Captura voz y la convierte en texto.

- Convierte texto en voz.

- Analiza propiedades de un archivo de audio.

- Reproduce audio.

- Convierte formatos de audio.

- Descarga audio desde YouTube.

<details>
<summary>Ver contenido de audio_video.py</summary>

```python

# audio_video.py
import speech_recognition as sr
import pyttsx3
import librosa
import sounddevice as sd
import pydub
import numpy as np
import pytube

# === Voz a texto ===
def voz_a_texto():
    """Convierte voz en texto usando el micrófono y Google Speech Recognition."""
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Habla ahora...")
        audio = recognizer.listen(source)
    try:
        return recognizer.recognize_google(audio, language="es-ES")
    except Exception as e:
        return f"Error al reconocer voz: {e}"

# === Texto a voz ===
def texto_a_voz(texto):
    """Convierte texto en voz usando pyttsx3."""
    try:
        engine = pyttsx3.init()
        engine.say(texto)
        engine.runAndWait()
        return "Texto leído en voz alta."
    except Exception as e:
        return f"Error al convertir texto a voz: {e}"

# === Análisis de audio con Librosa ===
def analiza_audio(ruta_audio):
    """Analiza un archivo de audio con Librosa y devuelve duración y tempo estimado."""
    try:
        y, sr_lib = librosa.load(ruta_audio)
        duracion = librosa.get_duration(y=y, sr=sr_lib)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr_lib)
        return f"Duración: {duracion:.2f} segundos | Tempo estimado: {tempo} BPM"
    except Exception as e:
        return f"Error al analizar audio: {e}"

# === Reproducción de audio con SoundDevice ===
def reproducir_audio(ruta_audio):
    """Reproduce un archivo de audio usando SoundDevice."""
    try:
        y, sr_lib = librosa.load(ruta_audio, sr=None)
        sd.play(y, sr_lib)
        sd.wait()
        return "Audio reproducido correctamente."
    except Exception as e:
        return f"Error al reproducir audio: {e}"

# === Conversión de audio con Pydub ===
def convertir_audio(ruta_audio, formato="mp3"):
    """Convierte un archivo de audio a otro formato usando Pydub."""
    try:
        audio = pydub.AudioSegment.from_file(ruta_audio)
        salida = ruta_audio.rsplit(".", 1)[0] + f".{formato}"
        audio.export(salida, format=formato)
        return f"Audio convertido y guardado en {salida}"
    except Exception as e:
        return f"Error al convertir audio: {e}"

# === Descarga de YouTube (solo audio) ===
def descargar_audio_youtube(url):
    """Descarga solo el audio de un video de YouTube."""
    try:
        yt = pytube.YouTube(url)
        stream = yt.streams.filter(only_audio=True).first()
        stream.download()
        return f"Audio descargado: {yt.title}"
    except Exception as e:
        return f"Error al descargar audio de YouTube: {e}"


```
</details>

# Programa de Creacion/Lectura/Analisis de Archivos Word/Excel/CSV/Python/PDF (io_files.py)

- ### io_files.py

 El programa io_files brinda una conexion directa a la creacion/analisis de tipo:
 - DOCX
 - PDF
 - PYTHON (.py)
 - EXCEL
 - 
Tambien se compone de una funcion extra que es la creacion y/o lectura de base de datos CSV con la implementacion del modulo Pandas
<details>
<summary>Ver contenido de io_files.py</summary>

```python

# io_files.py
import PyPDF2
import docx
import openpyxl
import pandas as pd
import pdfplumber
from ai_models import ask_openai

def crea_py(ruta, tema):
    """Genera un archivo Python a partir de un tema."""
    try:
        # Pedir a OpenAI que genere código Python sobre el tema
        codigo = ask_openai(f"Genera un script en Python sobre: {tema}")
        
        # Guardar el código en un archivo .py
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(codigo)
        
        return f"Archivo Python creado en {ruta} con el tema: {tema}"
    except Exception as e:
        return f"Error creando archivo Python: {e}"

# === Lectura de archivos ===
def leer_pdf(ruta_pdf, usar_plumber=False):
    """Lee un archivo PDF y devuelve su texto (primeros 1000 caracteres)."""
    try:
        texto = ""
        if usar_plumber:
            with pdfplumber.open(ruta_pdf) as pdf:
                for pagina in pdf.pages:
                    texto += pagina.extract_text() or ""
        else:
            with open(ruta_pdf, "rb") as f:
                lector = PyPDF2.PdfReader(f)
                for pagina in lector.pages:
                    texto += pagina.extract_text() or ""
        return texto[:70000]
    except Exception as e:
        return f"Error al leer PDF: {e}"

def leer_word(ruta_docx):
    """Lee un archivo Word (.docx) y devuelve su texto."""
    try:
        doc = docx.Document(ruta_docx)
        texto = "\n".join([p.text for p in doc.paragraphs])
        return texto[:70000]
    except Exception as e:
        return f"Error al leer Word: {e}"

def leer_excel(ruta_xlsx):
    """Lee un archivo Excel y devuelve su contenido (primeros 1000 caracteres)."""
    try:
        wb = openpyxl.load_workbook(ruta_xlsx)
        hoja = wb.active
        texto = ""
        for fila in hoja.iter_rows(values_only=True):
            texto += " | ".join([str(c) for c in fila if c is not None]) + "\n"
        return texto[:70000]
    except Exception as e:
        return f"Error al leer Excel: {e}"


def leer_csv(ruta_csv, analizar=False):
    try:
        # Leer todo el CSV completo
        df = pd.read_csv(ruta_csv, sep=None, engine='python', on_bad_lines='skip')

        if analizar:
            resumen = f"Columnas: {list(df.columns)}\n"
            resumen += f"Filas totales: {len(df)}\n\n"
            resumen += "Estadísticas:\n"
            resumen += df.describe(include='all').to_string()
            return resumen
        else:
            # Mostrar solo una parte para no saturar la consola
            return df.head(50).to_string()
    except Exception as e:
        return f"Error al leer CSV: {e}"
# === Escritura de archivos ===
def escribe_pdf(ruta, texto):
    """Crea un PDF con texto simple."""
    from reportlab.pdfgen import canvas
    import reportlab.lib.pagesizes as psizes
    try:
        c = canvas.Canvas(ruta, pagesize=psizes.A4)
        c.drawString(100, 750, texto)
        c.save()
        return f"PDF creado en {ruta}"
    except Exception as e:
        return f"Error al crear PDF: {e}"

def escribe_word(ruta, texto):
    """Crea un archivo Word con texto simple."""
    try:
        doc = docx.Document()
        doc.add_paragraph(texto)
        doc.save(ruta)
        return f"Word creado en {ruta}"
    except Exception as e:
        return f"Error al crear Word: {e}"

def escribe_excel(ruta, datos):
    """Crea un archivo Excel a partir de datos separados por comas."""
    try:
        wb = openpyxl.Workbook()
        hoja = wb.active
        for fila in datos.split("\n"):
            hoja.append(fila.split(","))
        wb.save(ruta)
        return f"Excel creado en {ruta}"
    except Exception as e:
        return f"Error al crear Excel: {e}"

def escribe_csv(ruta, datos):
    """Crea un archivo CSV a partir de texto plano."""
    try:
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            f.write(datos)
        return f"CSV creado en {ruta}"
    except Exception as e:
        return f"Error al crear CSV: {e}"

```
</details>

### Comentarios sobre las limitaciones del programa (readme)

La visualizacion de un archivo analizado por el programa se limita a la cantidad de caracteres que permite el API de ChatGPT. Por tanto se hizo un cambio con tal que el "display" este limitado por 70000 tokens (~280.000 caracteres)

# Programa de Calculo Simbolico, Memoria Vectorial y Base De Datos con IA (modules_extra.py)

- ### modules_extra.py
El siguiente programa compprende en mayor parte la memoria en base de datos de Redis,Lllama y SQL para el guardado o indexacion de documentos

<details>
<summary>Ver contenido de modules_extra.py</summary>

```python

# modules_extra.py
import numpy as np
import faiss
from llama_index.core import Document, VectorStoreIndex
import sympy as sp
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker
import redis

# --- Faiss: memoria vectorial ---
class FaissMemory:
    def __init__(self, dim=128):
        self.index = faiss.IndexFlatL2(dim)
        self.vectors = []
        self.texts = []

    def add(self, vec, text):
        self.index.add(np.array([vec]).astype('float32'))
        self.vectors.append(vec)
        self.texts.append(text)

    def search(self, vec, k=3):
        D, I = self.index.search(np.array([vec]).astype('float32'), k)
        return [(self.texts[i], float(D[0][j])) for j, i in enumerate(I[0])]

# --- LlamaIndex: indexación de documentos ---
class LlamaMemory:
    def __init__(self):
        self.docs = []
        self.index = None

    def add_doc(self, text):
        doc = Document(text=text)
        self.docs.append(doc)
        self.index = VectorStoreIndex.from_documents(self.docs)

    def query(self, q):
        if not self.index:
            return "No hay documentos cargados."
        query_engine = self.index.as_query_engine()
        return str(query_engine.query(q))

# --- Sympy: cálculo simbólico ---
def calcular_integral(expr_str, var_str, a, b):
    var = sp.Symbol(var_str)
    expr = sp.sympify(expr_str)
    resultado = sp.integrate(expr, (var, a, b))
    return f"Integral de {expr_str} entre {a} y {b} = {resultado}"

# --- SQLAlchemy: base de datos ---
Base = declarative_base()

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True)
    nombre = Column(String)

def guardar_usuario(nombre):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    nuevo = Usuario(nombre=nombre)
    session.add(nuevo)
    session.commit()
    return f"Usuario guardado: {nuevo.nombre}"

# --- Redis: memoria clave-valor ---
def redis_set(clave, valor):
    r = redis.Redis(host='localhost', port=6379, db=0)
    r.set(clave, valor)
    return f"Guardado en Redis: {clave} -> {valor}"

def redis_get(clave):
    r = redis.Redis(host='localhost', port=6379, db=0)
    val = r.get(clave)
    return val.decode("utf-8") if val else "Clave no encontrada"

# --- Diccionario de comandos ---
comandos_extra = {
    "faiss add": lambda: "Usa FaissMemory.add(vec,text)",
    "faiss search": lambda: "Usa FaissMemory.search(vec,k)",
    "llama add": lambda: "Usa LlamaMemory.add_doc(text)",
    "llama query": lambda: "Usa LlamaMemory.query(q)",
    "sympy integral": lambda: calcular_integral("sin(x)", "x", 0, sp.pi),
    "sqlalchemy usuario": lambda: guardar_usuario("Nico"),
    "redis set": lambda: redis_set("clave", "Hola desde Redis"),
    "redis get": lambda: redis_get("clave"),
}

```
</details>

# Programa de Cifrado/Encriptacion de Archivos (security.py)

- ### security.py

Security.py encapsula modulos para encriptar archivos con contraseña

<details>
<summary>Ver contenido de security.py</summary>

```python

# security.py
from cryptography.fernet import Fernet
import bcrypt
import jwt
import paramiko
from passlib.context import CryptContext

# Configuración de Passlib para hashing de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# === Cifrado de archivos con Fernet ===
def cifra_archivo(ruta):
    """Cifra un archivo con Fernet y guarda la versión cifrada."""
    try:
        key = Fernet.generate_key()
        fernet = Fernet(key)
        with open(ruta, "rb") as f:
            data = f.read()
        cifrado = fernet.encrypt(data)
        salida = ruta + ".cifrado"
        with open(salida, "wb") as f:
            f.write(cifrado)
        return f"Archivo cifrado en {salida}\nClave: {key.decode()}"
    except Exception as e:
        return f"Error al cifrar archivo: {e}"

# === Hashing de contraseñas con bcrypt ===
def hash_password(password: str):
    """Genera un hash seguro de una contraseña usando bcrypt."""
    try:
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode(), salt)
        return hashed.decode()
    except Exception as e:
        return f"Error al generar hash: {e}"

def verify_password(password: str, hashed: str):
    """Verifica una contraseña contra su hash."""
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception as e:
        return f"Error al verificar contraseña: {e}"

# === Hashing con Passlib ===
def passlib_hash(password: str):
    """Genera un hash usando Passlib."""
    try:
        return pwd_context.hash(password)
    except Exception as e:
        return f"Error en Passlib hash: {e}"

def passlib_verify(password: str, hashed: str):
    """Verifica contraseña con Passlib."""
    try:
        return pwd_context.verify(password, hashed)
    except Exception as e:
        return f"Error en Passlib verify: {e}"

# === Tokens JWT ===
def crear_jwt(payload: dict, secret: str = "mi_clave_secreta"):
    """Crea un token JWT con un payload dado."""
    try:
        token = jwt.encode(payload, secret, algorithm="HS256")
        return token
    except Exception as e:
        return f"Error al crear JWT: {e}"

def verificar_jwt(token: str, secret: str = "mi_clave_secreta"):
    """Verifica y decodifica un token JWT."""
    try:
        decoded = jwt.decode(token, secret, algorithms=["HS256"])
        return decoded
    except Exception as e:
        return f"Error al verificar JWT: {e}"

# === Ejemplo con Paramiko (SSH) ===
def paramiko_demo(host="localhost", user="usuario", password="clave"):
    """Ejemplo simple de conexión SSH con Paramiko (no ejecuta comandos reales)."""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # No conectamos realmente, solo mostramos inicialización
        return "Cliente SSH inicializado con Paramiko."
    except Exception as e:
        return f"Error en Paramiko demo: {e}"

```

</details>

# Programa de Monitoreo del PC (utils.py)

- ### utils.py
La implementacion de utils.py ofrece monitoreo continuo del computador, respecto al uso del teclado, desplazamiento coordinado del mouse y monitoreo de archivos por comando

<details>
<summary>Ver contenido de utils.py</summary>

```python

# utils.py
import psutil
from tqdm import tqdm
import schedule
import time
import keyboard
import mouse
import arrow
import orjson
from filelock import FileLock
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

def obtener_fecha_arrow():
    return f"Fecha actual: {arrow.utcnow()}"
def serializar_orjson(data):
    return orjson.dumps(data).decode()
# === Estado del sistema ===
def system_status():
    """Devuelve el estado actual de CPU y RAM."""
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    return f"CPU: {cpu}% | RAM: {ram}%"

# === Barra de progreso con tqdm ===
def barra_progreso(iteraciones=10):
    """Muestra una barra de progreso simulada."""
    for i in tqdm(range(iteraciones), desc="Progreso"):
        time.sleep(0.2)
    return "Barra de progreso completada."

# === Tareas programadas con schedule ===
def tarea_programada():
    """Ejemplo de tarea programada que imprime un mensaje cada minuto."""
    schedule.every(1).minutes.do(lambda: print("Ejecutando tarea programada..."))
    return "Tarea programada cada minuto. Usa schedule.run_pending() en tu bucle principal."

# === Control de teclado y ratón ===
def simular_tecla(tecla="a"):
    """Simula la pulsación de una tecla."""
    try:
        keyboard.write(tecla)
        return f"Tecla '{tecla}' simulada."
    except Exception as e:
        return f"Error al simular tecla: {e}"

def simular_click():
    """Simula un clic del ratón."""
    try:
        mouse.click()
        return "Clic del ratón simulado."
    except Exception as e:
        return f"Error al simular clic: {e}"

# === Bloqueo de archivos con FileLock ===
def bloquear_archivo(ruta="archivo.txt"):
    """Bloquea un archivo para evitar acceso concurrente."""
    try:
        lock = FileLock(ruta + ".lock")
        with lock:
            print("Archivo bloqueado temporalmente.")
            time.sleep(2)
        return "Archivo desbloqueado."
    except Exception as e:
        return f"Error al bloquear archivo: {e}"

# === Monitoreo de archivos con Watchdog ===
class MonitorArchivos(FileSystemEventHandler):
    """Clase para monitorear cambios en archivos."""
    def on_modified(self, event):
        print(f"Archivo modificado: {event.src_path}")

def iniciar_monitor(ruta="."):
    """Inicia un monitor de archivos en la ruta indicada."""
    try:
        event_handler = MonitorArchivos()
        observer = Observer()
        observer.schedule(event_handler, ruta, recursive=True)
        observer.start()
        return f"Monitor iniciado en {ruta}"
    except Exception as e:
        return f"Error al iniciar monitor: {e}"

```
</details>

# Programa de Creacion de Grafico CSV y Tabla de DataFrame Pandas (visualization.py)

- ### visualization.py

Este programa en particular repasa CSV a forma en grafica tipo imagen .png y la tabulacion de datos

<details>
<summary>Ver contenido de visualization.py</summary>

```python

# visualization.py
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from reportlab.pdfgen import canvas
import reportlab.lib.pagesizes as psizes
from tabulate import tabulate
from rich.console import Console
from colorama import Fore, Style
from skimage import data, filters
from PyQt5 import QtWidgets
import sys
from PIL import Image
console = Console()

def procesar_imagen_skimage():
    image = data.coins()
    edges = filters.sobel(image)
    return f"Imagen procesada con sobel, shape: {edges.shape}"

def mostrar_gui_pyqt():
    app = QtWidgets.QApplication(sys.argv)
    window = QtWidgets.QWidget()
    window.setWindowTitle("Demo PyQt5")
    window.show()
    app.exec_()

# === Graficar CSV ===
def grafica_csv(ruta):
    """Genera un histograma del primer campo de un CSV y guarda como imagen."""
    try:
        df = pd.read_csv(ruta)
        plt.figure(figsize=(8,6))
        sns.histplot(df[df.columns[0]], kde=True)
        plt.savefig("grafico.png")
        return "Gráfico guardado como grafico.png"
    except Exception as e:
        return f"Error al graficar CSV: {e}"

# === Tabla bonita con Tabulate ===
def mostrar_tabla(df, max_filas=10):
    """Muestra un DataFrame como tabla con Tabulate."""
    try:
        tabla = tabulate(df.head(max_filas), headers="keys", tablefmt="grid")
        return tabla
    except Exception as e:
        return f"Error al mostrar tabla: {e}"

# === Mostrar con Rich ===
def mostrar_rich(texto):
    """Muestra texto con formato bonito usando Rich."""
    try:
        console.print(Fore.GREEN + texto + Style.RESET_ALL)
        return "Texto mostrado con Rich."
    except Exception as e:
        return f"Error al mostrar con Rich: {e}"

# === Crear PDF simple con ReportLab ===
def crear_pdf(ruta, texto):
    """Crea un PDF con texto usando ReportLab."""
    try:
        c = canvas.Canvas(ruta, pagesize=psizes.A4)
        c.drawString(100, 750, texto)
        c.save()
        return f"PDF creado en {ruta}"
    except Exception as e:
        return f"Error al crear PDF: {e}"

```
</details>

## Grafico de Ejemplo
## Tabla de Ejemplo

# Programa de Extraccion/Peticion de Informacion en Internet (web_tools.py)

- ### web_tools.py

El programa web_tools adhiere herramientas de internet, las mas tipicas siendo destacadas:

- Extraer informacion de URL
- Traduccion de Texto por Google Translate
- Descargar video de youtube
- Hacer peticion HTTPX
- Creacion de Aplicacion FastAPI

<details>
<summary>Ver contenido de web_tools.py</summary>

```python

# web_tools.py
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import pytube
import httpx
import aiohttp
import socketio
from fastapi import FastAPI
from flask import Flask
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
import grpc
import websockets

def subir_archivo_azure(nombre_archivo):
    return f"Función no implementada aún. Archivo: {nombre_archivo}"

def consumir_api_grpc():
    return "Función no implementada aún."

# === Scraping web ===
def extrae_web(url):
    """Extrae texto de una página web usando requests + BeautifulSoup."""
    try:
        r = requests.get(url)
        soup = BeautifulSoup(r.text, "html.parser")
        return soup.get_text()[:1000]
    except Exception as e:
        return f"Error al extraer web: {e}"

# === Traducción ===
def traducir(texto, destino="en"):
    """Traduce texto usando deep-translator."""
    try:
        return GoogleTranslator(source="auto", target=destino).translate(texto)
    except Exception as e:
        return f"Error al traducir: {e}"

# === Descarga de YouTube ===
def descargar_youtube(url):
    """Descarga un video de YouTube en la mejor resolución disponible."""
    try:
        yt = pytube.YouTube(url)
        stream = yt.streams.get_highest_resolution()
        stream.download()
        return f"Video descargado: {yt.title}"
    except Exception as e:
        return f"Error al descargar video: {e}"

# === Ejemplo con httpx ===
def httpx_demo(url="https://httpbin.org/get"):
    """Ejemplo simple de petición con httpx."""
    try:
        r = httpx.get(url)
        return f"HTTPX demo: {r.status_code}, {r.json()}"
    except Exception as e:
        return f"Error en httpx demo: {e}"

# === Ejemplo con aiohttp ===
async def aiohttp_demo(url="https://httpbin.org/get"):
    """Ejemplo simple de petición asíncrona con aiohttp."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                text = await resp.text()
                return f"AIOHTTP demo: {resp.status}, {text[:200]}"
    except Exception as e:
        return f"Error en aiohttp demo: {e}"

# === Ejemplo con Socket.IO ===
def socketio_demo():
    """Ejemplo simple de cliente Socket.IO."""
    try:
        sio = socketio.Client()
        # No conectamos a un servidor real, solo mostramos que se inicializa
        return "Cliente Socket.IO inicializado."
    except Exception as e:
        return f"Error en Socket.IO demo: {e}"

# === Ejemplo con FastAPI ===
def fastapi_demo():
    """Ejemplo simple de inicialización de FastAPI."""
    try:
        app = FastAPI()
        @app.get("/")
        def read_root():
            return {"mensaje": "Hola desde FastAPI"}
        return "Aplicación FastAPI creada."
    except Exception as e:
        return f"Error en FastAPI demo: {e}"

# === Ejemplo con Flask ===
def flask_demo():
    """Ejemplo simple de inicialización de Flask."""
    try:
        app = Flask(__name__)
        @app.route("/")
        def home():
            return "Hola desde Flask"
        return "Aplicación Flask creada."
    except Exception as e:
        return f"Error en Flask demo: {e}"

```
</details>

## Modulos (Instalados y/o Integrados)

Aqui el archivo con el listado de modulos Instalados e Integrados
 https://docs.google.com/spreadsheets/d/1I2JpcZ6_V_WUdXkkYkP7MZ1fgQcPW6y73xBbtZjOfHI/edit?usp=sharing

## Actualizacion de Modulos (Semanal)
## Ejemplos de Ejecucion con Dataset

