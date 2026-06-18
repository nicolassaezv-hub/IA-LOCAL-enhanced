# ai_models.py
from openai import OpenAI
import psutil
from memory import cargar_memoria, guardar_memoria

# Librerías de IA/ML que ya tienes instaladass wow
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
