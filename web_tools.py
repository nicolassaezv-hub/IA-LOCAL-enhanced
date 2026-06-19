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
