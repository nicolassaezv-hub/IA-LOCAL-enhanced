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
