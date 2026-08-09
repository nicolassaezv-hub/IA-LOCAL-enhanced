import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from colorama import Fore, Style

try:
    import seaborn as sns
    HAS_SNS = True
except ImportError:
    sns = None
    HAS_SNS = False

try:
    from reportlab.pdfgen import canvas as rl_canvas
    import reportlab.lib.pagesizes as psizes
    HAS_REPORTLAB = True
except ImportError:
    rl_canvas = None
    psizes = None
    HAS_REPORTLAB = False

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    tabulate = None
    HAS_TABULATE = False

try:
    from rich.console import Console
    _console = Console()
    HAS_RICH = True
except ImportError:
    _console = None
    HAS_RICH = False

try:
    from skimage import data, filters
    HAS_SKIMAGE = True
except (ImportError, AttributeError, Exception):
    data = None
    filters = None
    HAS_SKIMAGE = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    Image = None
    HAS_PIL = False

try:
    from PyQt5 import QtWidgets
    HAS_PYQT5 = True
except Exception:
    HAS_PYQT5 = False


def procesar_imagen_skimage():
    if not HAS_SKIMAGE:
        return "scikit-image no disponible en este sistema."
    try:
        image = data.coins()
        edges = filters.sobel(image)
        return f"Imagen procesada con sobel, shape: {edges.shape}"
    except Exception as e:
        return f"Error al procesar imagen: {e}"


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
    try:
        df = pd.read_csv(ruta)
        plt.figure(figsize=(8, 6))
        if HAS_SNS:
            sns.histplot(df[df.columns[0]], kde=True)
        else:
            plt.hist(df[df.columns[0]].dropna())
        plt.savefig("grafico.png")
        plt.close()
        return "Gráfico guardado como grafico.png"
    except Exception as e:
        return f"Error al graficar CSV: {e}"


def mostrar_tabla(df, max_filas=10):
    try:
        if HAS_TABULATE:
            return tabulate(df.head(max_filas), headers="keys", tablefmt="grid")
        else:
            return df.head(max_filas).to_string()
    except Exception as e:
        return f"Error al mostrar tabla: {e}"


def mostrar_rich(texto):
    try:
        if HAS_RICH:
            _console.print(Fore.GREEN + texto + Style.RESET_ALL)
        else:
            print(Fore.GREEN + texto + Style.RESET_ALL)
        return "Texto mostrado."
    except Exception as e:
        return f"Error al mostrar texto: {e}"


def crear_pdf(ruta, texto):
    if not HAS_REPORTLAB:
        return "ReportLab no disponible en este sistema. Instale: pip install reportlab"
    try:
        c = rl_canvas.Canvas(ruta, pagesize=psizes.A4)
        c.drawString(100, 750, texto)
        c.save()
        return f"PDF creado en {ruta}"
    except Exception as e:
        return f"Error al crear PDF: {e}"
