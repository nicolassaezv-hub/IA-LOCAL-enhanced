import requests
from bs4 import BeautifulSoup

try:
    from deep_translator import GoogleTranslator
    HAS_DEEP_TRANSLATOR = True
except ImportError:
    GoogleTranslator = None
    HAS_DEEP_TRANSLATOR = False

try:
    import pytube
    HAS_PYTUBE = True
except ImportError:
    pytube = None
    HAS_PYTUBE = False

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    httpx = None
    HAS_HTTPX = False

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    aiohttp = None
    HAS_AIOHTTP = False

try:
    import socketio
    HAS_SOCKETIO = True
except ImportError:
    socketio = None
    HAS_SOCKETIO = False

try:
    from fastapi import FastAPI
    HAS_FASTAPI = True
except ImportError:
    FastAPI = None
    HAS_FASTAPI = False

try:
    from flask import Flask
    HAS_FLASK = True
except ImportError:
    Flask = None
    HAS_FLASK = False

try:
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient
    HAS_AZURE = True
except ImportError:
    DefaultAzureCredential = None
    BlobServiceClient = None
    HAS_AZURE = False

try:
    import grpc
    HAS_GRPC = True
except ImportError:
    grpc = None
    HAS_GRPC = False

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    websockets = None
    HAS_WEBSOCKETS = False


def subir_archivo_azure(nombre_archivo):
    if not HAS_AZURE:
        return "Azure SDK no disponible. Instale: pip install azure-storage-blob azure-identity"
    return f"Función no implementada aún. Archivo: {nombre_archivo}"


def consumir_api_grpc():
    if not HAS_GRPC:
        return "grpcio no disponible. Instale: pip install grpcio"
    return "Función no implementada aún."


def extrae_web(url):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        return soup.get_text()[:1000]
    except Exception as e:
        return f"Error al extraer web: {e}"


def traducir(texto, destino="en"):
    if not HAS_DEEP_TRANSLATOR:
        return "deep-translator no disponible. Instale: pip install deep-translator"
    try:
        return GoogleTranslator(source="auto", target=destino).translate(texto)
    except Exception as e:
        return f"Error al traducir: {e}"


def descargar_youtube(url):
    if not HAS_PYTUBE:
        return "pytube no disponible. Instale: pip install pytube"
    try:
        yt = pytube.YouTube(url)
        stream = yt.streams.get_highest_resolution()
        stream.download()
        return f"Video descargado: {yt.title}"
    except Exception as e:
        return f"Error al descargar video: {e}"


def httpx_demo(url="https://httpbin.org/get"):
    if not HAS_HTTPX:
        return "httpx no disponible. Instale: pip install httpx"
    try:
        r = httpx.get(url)
        return f"HTTPX demo: {r.status_code}, {r.json()}"
    except Exception as e:
        return f"Error en httpx demo: {e}"


async def aiohttp_demo(url="https://httpbin.org/get"):
    if not HAS_AIOHTTP:
        return "aiohttp no disponible. Instale: pip install aiohttp"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                text = await resp.text()
                return f"AIOHTTP demo: {resp.status}, {text[:200]}"
    except Exception as e:
        return f"Error en aiohttp demo: {e}"


def socketio_demo():
    if not HAS_SOCKETIO:
        return "python-socketio no disponible. Instale: pip install python-socketio"
    try:
        sio = socketio.Client()
        return "Cliente Socket.IO inicializado."
    except Exception as e:
        return f"Error en Socket.IO demo: {e}"


def fastapi_demo():
    if not HAS_FASTAPI:
        return "FastAPI no disponible. Instale: pip install fastapi"
    try:
        app = FastAPI()

        @app.get("/")
        def read_root():
            return {"mensaje": "Hola desde FastAPI"}
        return "Aplicación FastAPI creada."
    except Exception as e:
        return f"Error en FastAPI demo: {e}"


def flask_demo():
    if not HAS_FLASK:
        return "Flask no disponible. Instale: pip install flask"
    try:
        app = Flask(__name__)

        @app.route("/")
        def home():
            return "Hola desde Flask"
        return "Aplicación Flask creada."
    except Exception as e:
        return f"Error en Flask demo: {e}"
