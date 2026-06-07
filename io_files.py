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
