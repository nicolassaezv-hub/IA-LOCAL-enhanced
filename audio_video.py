import numpy as np

try:
    import speech_recognition as sr
    HAS_SR = True
except ImportError:
    sr = None
    HAS_SR = False

try:
    import pyttsx3
    HAS_PYTTSX3 = True
except ImportError:
    pyttsx3 = None
    HAS_PYTTSX3 = False

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    librosa = None
    HAS_LIBROSA = False

try:
    import sounddevice as sd
    HAS_SD = True
except (ImportError, OSError):
    sd = None
    HAS_SD = False

try:
    import pydub
    HAS_PYDUB = True
except ImportError:
    pydub = None
    HAS_PYDUB = False

try:
    import pytube
    HAS_PYTUBE = True
except ImportError:
    pytube = None
    HAS_PYTUBE = False


def voz_a_texto():
    if not HAS_SR:
        return "Reconocimiento de voz no disponible en este sistema (speech_recognition no instalado)."
    try:
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            print("Habla ahora...")
            audio = recognizer.listen(source)
        return recognizer.recognize_google(audio, language="es-ES")
    except Exception as e:
        return f"Error al reconocer voz: {e}"


def texto_a_voz(texto):
    if not HAS_PYTTSX3:
        return "Texto a voz no disponible en este sistema (pyttsx3 no instalado)."
    try:
        engine = pyttsx3.init()
        engine.say(texto)
        engine.runAndWait()
        return "Texto leído en voz alta."
    except Exception as e:
        return f"Error al convertir texto a voz: {e}"


def analiza_audio(ruta_audio):
    if not HAS_LIBROSA:
        return "Análisis de audio no disponible en este sistema (librosa no instalado)."
    try:
        y, sr_lib = librosa.load(ruta_audio)
        duracion = librosa.get_duration(y=y, sr=sr_lib)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr_lib)
        return f"Duración: {duracion:.2f} segundos | Tempo estimado: {tempo} BPM"
    except Exception as e:
        return f"Error al analizar audio: {e}"


def reproducir_audio(ruta_audio):
    if not HAS_LIBROSA or not HAS_SD:
        return "Reproducción de audio no disponible en este sistema."
    try:
        y, sr_lib = librosa.load(ruta_audio, sr=None)
        sd.play(y, sr_lib)
        sd.wait()
        return "Audio reproducido correctamente."
    except Exception as e:
        return f"Error al reproducir audio: {e}"


def convertir_audio(ruta_audio, formato="mp3"):
    if not HAS_PYDUB:
        return "Conversión de audio no disponible en este sistema (pydub no instalado)."
    try:
        audio = pydub.AudioSegment.from_file(ruta_audio)
        salida = ruta_audio.rsplit(".", 1)[0] + f".{formato}"
        audio.export(salida, format=formato)
        return f"Audio convertido y guardado en {salida}"
    except Exception as e:
        return f"Error al convertir audio: {e}"


def descargar_audio_youtube(url):
    if not HAS_PYTUBE:
        return "Descarga de YouTube no disponible en este sistema (pytube no instalado)."
    try:
        yt = pytube.YouTube(url)
        stream = yt.streams.filter(only_audio=True).first()
        stream.download()
        return f"Audio descargado: {yt.title}"
    except Exception as e:
        return f"Error al descargar audio de YouTube: {e}"
