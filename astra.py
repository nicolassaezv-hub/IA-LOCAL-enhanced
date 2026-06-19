# astra.py

import os
import logging

# Desactivar todos los logs de Kivy
os.environ["KIVY_NO_CONSOLELOG"] = "1"
logging.getLogger("kivy").disabled = True
logging.getLogger("kivy").setLevel(logging.CRITICAL)

import time
import sqlite3

import openai
import psutil
import PyPDF2
import docx
import openpyxl
import speech_recognition as sr
import pyttsx3
import pyautogui
import mss
import pytesseract
import pygetwindow as gw
from PIL import Image
import csv
import pandas as pd

# Nuevos módulos instalados
import reportlab.lib.pagesizes as psizes
from reportlab.pdfgen import canvas
import matplotlib.pyplot as plt
import seaborn as sns
import requests
from bs4 import BeautifulSoup
from cryptography.fernet import Fernet
import schedule
import pdfplumber
import pydub
import skimage
import imageio
import librosa
import sounddevice as sd
import torch
import tensorflow as tf
import keras
import httpx
import aiohttp
import websocket
import flask
import fastapi
import bcrypt
import paramiko
import jwt
import keyring
from colorama import Fore, Style
from rich.console import Console
from tabulate import tabulate
import json5
import yaml
import h5py
import PyQt5
import kivy
import dearpygui.dearpygui as dpg
import keyboard
import mouse
import pytube
from deep_translator import GoogleTranslator
# Configurar ruta de Tesseract si es necesario
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Cliente OpenAI con tu API key
openai.api_key = os.getenv("OPENAI_API_KEY")
# === Configuración de memoria con SQLite ===
def init_db():
    conn = sqlite3.connect("memoria.db")
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
    conn = sqlite3.connect("memoria.db")
    c = conn.cursor()
    c.execute("INSERT INTO memoria (user_input, ai_response, timestamp) VALUES (?, ?, ?)",
              (user_input, ai_response, time.ctime()))
    conn.commit()
    conn.close()

def cargar_memoria(limit=10):
    conn = sqlite3.connect("memoria.db")
    c = conn.cursor()
    c.execute("SELECT user_input, ai_response FROM memoria ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    memoria = ""
    for u, a in rows[::-1]:
        memoria += f"Tú: {u}\nCopilot: {a}\n"
    return memoria

# === Funciones auxiliares ===
def system_status():
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    return f"CPU: {cpu}% | RAM: {ram}%"

# === Lectura de archivos ===
def leer_pdf(ruta_pdf):
    try:
        with open(ruta_pdf, "rb") as f:
            lector = PyPDF2.PdfReader(f)
            texto = ""
            for pagina in lector.pages:
                texto += pagina.extract_text() + "\n"
            return texto[:1000]
    except Exception as e:
        return f"Error al leer PDF: {e}"

def leer_word(ruta_docx):
    try:
        doc = docx.Document(ruta_docx)
        texto = "\n".join([p.text for p in doc.paragraphs])
        return texto[:1000]
    except Exception as e:
        return f"Error al leer Word: {e}"

def leer_excel(ruta_xlsx):
    try:
        wb = openpyxl.load_workbook(ruta_xlsx)
        hoja = wb.active
        texto = ""
        for fila in hoja.iter_rows(values_only=True):
            texto += " | ".join([str(c) for c in fila if c is not None]) + "\n"
        return texto[:1000]
    except Exception as e:
        return f"Error al leer Excel: {e}"

def leer_csv(ruta_csv, analizar=False):
    try:
        df = pd.read_csv(ruta_csv)
        if analizar:
            resumen = f"Columnas: {list(df.columns)}\n"
            resumen += f"Filas totales: {len(df)}\n\n"
            resumen += "Estadísticas:\n"
            resumen += df.describe(include="all").to_string()
            return resumen[:1500]
        else:
            return df.head(10).to_string()
    except Exception as e:
        return f"Error al leer CSV: {e}"

# === Escritura de archivos ===
def escribe_pdf(ruta, texto):
    c = canvas.Canvas(ruta, pagesize=psizes.A4)
    c.drawString(100, 750, texto)
    c.save()
    return f"PDF creado en {ruta}"

def escribe_word(ruta, texto):
    doc = docx.Document()
    doc.add_paragraph(texto)
    doc.save(ruta)
    return f"Word creado en {ruta}"

def escribe_excel(ruta, datos):
    wb = openpyxl.Workbook()
    hoja = wb.active
    for fila in datos.split("\n"):
        hoja.append(fila.split(","))
    wb.save(ruta)
    return f"Excel creado en {ruta}"

def escribe_csv(ruta, datos):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        f.write(datos)
    return f"CSV creado en {ruta}"

# === Graficar CSV ===
def grafica_csv(ruta):
    df = pd.read_csv(ruta)
    plt.figure(figsize=(8,6))
    sns.histplot(df[df.columns[0]], kde=True)
    plt.savefig("grafico.png")
    return "Gráfico guardado como grafico.png"

# === Scraping web ===
def extrae_web(url):
    try:
        r = requests.get(url)
        soup = BeautifulSoup(r.text, "html.parser")
        return soup.get_text()[:1000]
    except Exception as e:
        return f"Error al extraer web: {e}"

# === Cifrado de archivos ===
def cifra_archivo(ruta):
    try:
        key = Fernet.generate_key()
        fernet = Fernet(key)
        with open(ruta, "rb") as f:
            data = f.read()
        cifrado = fernet.encrypt(data)
        with open(ruta + ".cifrado", "wb") as f:
            f.write(cifrado)
        return f"Archivo cifrado en {ruta}.cifrado\nClave: {key.decode()}"
    except Exception as e:
        return f"Error al cifrar archivo: {e}"

# === Conversación con IA con memoria ===
def ask_openai(user_message):
    memoria = cargar_memoria(limit=10)
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role":"system","content":"You are Copilot integrated in a local wrapper."},
            {"role":"user","content":f"Memoria previa:\n{memoria}\n\nNueva entrada:\n{user_message}\n\nEstado del PC: {system_status()}"}
        ]
    )
    reply = response.choices[0].message.content
    guardar_memoria(user_message, reply)
    return reply

# === Bucle principal ===
if __name__ == "__main__":
    init_db()
    print(Fore.GREEN + "=== Astra extendida con nuevas funciones ===" + Style.RESET_ALL)
    while True:
        user_input = input(Fore.CYAN + "Tú: " + Style.RESET_ALL)

        if user_input.lower() in ["salir","exit","quit"]:
            break

        elif user_input.startswith("lee pdf"):
            ruta = user_input.split(" ",2)[-1]
            respuesta = leer_pdf(ruta)
    
        elif user_input.startswith("lee word"):
            ruta = user_input.split(" ",2)[-1]
            respuesta = leer_word(ruta)

        elif user_input.startswith("lee excel"):
            ruta = user_input.split(" ",2)[-1]
            respuesta = leer_excel(ruta)

        elif user_input.startswith("lee csv"):
            ruta = user_input.split(" ",2)[-1]
            respuesta = leer_csv(ruta)

        elif user_input.startswith("analiza csv"):
            ruta = user_input.split(" ",2)[-1]
            respuesta = leer_csv(ruta, analizar=True)

        elif user_input.startswith("analiza codigo"):
            import ast
            try:
                with open("astra.py", "r", encoding="utf-8") as f:
                    code = f.read()

                tree = ast.parse(code)
                functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
                print("Funciones encontradas en astra.py:", functions)

                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Eres un asistente que revisa código Python y da recomendaciones de mejora."},
                        {"role": "user", "content": f"Analiza este código y dame sugerencias:\n{code}"}
                    ]
                )
                respuesta = response.choices[0].message.content
            except Exception as e:
                respuesta = f"Error al analizar el código: {e}"

        elif user_input.startswith("escribe pdf"):
            partes = user_input.split(" ",2)
            ruta, texto = partes[1], partes[2]
            respuesta = escribe_pdf(ruta, texto)

        elif user_input.startswith("escribe word"):
            partes = user_input.split(" ",2)
            ruta, texto = partes[1], partes[2]
            respuesta = escribe_word(ruta, texto)

        elif user_input.startswith("escribe excel"):
            partes = user_input.split(" ",2)
            ruta, datos = partes[1], partes[2]
            respuesta = escribe_excel(ruta, datos)

        elif user_input.startswith("escribe csv"):
            partes = user_input.split(" ",2)
            ruta, datos = partes[1], partes[2]
            respuesta = escribe_csv(ruta, datos)

        elif user_input.startswith("grafica csv"):
            ruta = user_input.split(" ",2)[-1]
            respuesta = grafica_csv(ruta)

        elif user_input.startswith("extrae web"):
            url = user_input.split(" ",2)[-1]
            respuesta = extrae_web(url)

        elif user_input.startswith("cifra archivo"):
            ruta = user_input.split(" ",2)[-1]
            respuesta = cifra_archivo(ruta)

        elif user_input.startswith("voz a texto"):
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                print("Habla ahora...")
                audio = recognizer.listen(source)
            try:
                respuesta = recognizer.recognize_google(audio, language="es-ES")
            except Exception as e:
                respuesta = f"Error al reconocer voz: {e}"

        elif user_input.startswith("texto a voz"):
            engine = pyttsx3.init()
            texto = user_input.split(" ",2)[-1]
            engine.say(texto)
            engine.runAndWait()
            respuesta = "Texto leído en voz alta."

        elif user_input.startswith("estado pc"):
            respuesta = system_status()

        elif user_input.startswith("traducir"):
            texto = user_input.split(" ",2)[-1]
            traductor = Translator()
            try:
                respuesta = traducir(
                    texto,
                    "en"
                )
            except Exception as e:
                respuesta = f"Error al traducir: {e}"

        elif user_input.startswith("youtube"):
            url = user_input.split(" ",2)[-1]
            try:
                yt = pytube.YouTube(url)
                stream = yt.streams.get_highest_resolution()
                stream.download()
                respuesta = f"Video descargado: {yt.title}"
            except Exception as e:
                respuesta = f"Error al descargar video: {e}"

        else:
            respuesta = ask_openai(user_input)

        print(Fore.YELLOW + "Copilot: " + Style.RESET_ALL + respuesta)
