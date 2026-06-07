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
