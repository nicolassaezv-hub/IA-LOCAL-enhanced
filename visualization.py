# visualization.py
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from reportlab.pdfgen import canvas
import reportlab.lib.pagesizes as psizes
from tabulate import tabulate
from rich.console import Console
from colorama import Fore, Style
from skimage import data, filters
import sys

try:
    from PyQt5 import QtWidgets
    HAS_PYQT5 = True
except Exception:
    HAS_PYQT5 = False

from PIL import Image
console = Console()

def procesar_imagen_skimage():
    image = data.coins()
    edges = filters.sobel(image)
    return f"Imagen procesada con sobel, shape: {edges.shape}"

def mostrar_gui_pyqt():
    if not HAS_PYQT5:
        return "PyQt5 GUI no disponible en este sistema."
    try:
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        window = QtWidgets.QWidget()
        window.setWindowTitle("Demo PyQt5")
        window.show()
        app.exec_()
    except Exception as e:
        return f"Error al mostrar GUI: {e}"

def grafica_csv(ruta):
    """Genera un histograma del primer campo de un CSV y guarda como imagen."""
    try:
        df = pd.read_csv(ruta)
        plt.figure(figsize=(8,6))
        sns.histplot(df[df.columns[0]], kde=True)
        plt.savefig("grafico.png")
        plt.close()
        return "Gráfico guardado como grafico.png"
    except Exception as e:
        return f"Error al graficar CSV: {e}"

def mostrar_tabla(df, max_filas=10):
    """Muestra un DataFrame como tabla con Tabulate."""
    try:
        tabla = tabulate(df.head(max_filas), headers="keys", tablefmt="grid")
        return tabla
    except Exception as e:
        return f"Error al mostrar tabla: {e}"

def mostrar_rich(texto):
    """Muestra texto con formato bonito usando Rich."""
    try:
        console.print(Fore.GREEN + texto + Style.RESET_ALL)
        return "Texto mostrado con Rich."
    except Exception as e:
        return f"Error al mostrar con Rich: {e}"

def crear_pdf(ruta, texto):
    """Crea un PDF con texto usando ReportLab."""
    try:
        c = canvas.Canvas(ruta, pagesize=psizes.A4)
        c.drawString(100, 750, texto)
        c.save()
        return f"PDF creado en {ruta}"
    except Exception as e:
        return f"Error al crear PDF: {e}"
