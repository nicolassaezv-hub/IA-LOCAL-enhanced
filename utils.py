import time
from tqdm import tqdm

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    psutil = None
    HAS_PSUTIL = False

try:
    import schedule
    HAS_SCHEDULE = True
except ImportError:
    schedule = None
    HAS_SCHEDULE = False

try:
    import arrow
    HAS_ARROW = True
except ImportError:
    arrow = None
    HAS_ARROW = False

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    orjson = None
    HAS_ORJSON = False

try:
    from filelock import FileLock
    HAS_FILELOCK = True
except ImportError:
    FileLock = None
    HAS_FILELOCK = False

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    Observer = None
    FileSystemEventHandler = object
    HAS_WATCHDOG = False

try:
    import keyboard
    HAS_KEYBOARD = True
except Exception:
    keyboard = None
    HAS_KEYBOARD = False

try:
    import mouse
    HAS_MOUSE = True
except Exception:
    mouse = None
    HAS_MOUSE = False


def obtener_fecha_arrow():
    if not HAS_ARROW:
        import datetime
        return f"Fecha actual: {datetime.datetime.utcnow().isoformat()}Z"
    return f"Fecha actual: {arrow.utcnow()}"


def serializar_orjson(data):
    if not HAS_ORJSON:
        import json
        return json.dumps(data, default=str, ensure_ascii=False)
    return orjson.dumps(data).decode()


def system_status():
    if not HAS_PSUTIL:
        return "Estado del sistema no disponible (psutil no instalado)."
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    return f"CPU: {cpu}% | RAM: {ram}%"


def barra_progreso(iteraciones=10):
    for i in tqdm(range(iteraciones), desc="Progreso"):
        time.sleep(0.2)
    return "Barra de progreso completada."


def tarea_programada():
    if not HAS_SCHEDULE:
        return "schedule no disponible en este sistema."
    schedule.every(1).minutes.do(lambda: print("Ejecutando tarea programada..."))
    return "Tarea programada cada minuto. Usa schedule.run_pending() en tu bucle principal."


def simular_tecla(tecla="a"):
    if not HAS_KEYBOARD:
        return "Simulación de teclado no disponible en este sistema."
    try:
        keyboard.write(tecla)
        return f"Tecla '{tecla}' simulada."
    except Exception as e:
        return f"Error al simular tecla: {e}"


def simular_click():
    if not HAS_MOUSE:
        return "Simulación de ratón no disponible en este sistema."
    try:
        mouse.click()
        return "Clic del ratón simulado."
    except Exception as e:
        return f"Error al simular clic: {e}"


def bloquear_archivo(ruta="archivo.txt"):
    if not HAS_FILELOCK:
        return "filelock no disponible en este sistema."
    try:
        lock = FileLock(ruta + ".lock")
        with lock:
            print("Archivo bloqueado temporalmente.")
            time.sleep(2)
        return "Archivo desbloqueado."
    except Exception as e:
        return f"Error al bloquear archivo: {e}"


class MonitorArchivos(FileSystemEventHandler):
    def on_modified(self, event):
        print(f"Archivo modificado: {event.src_path}")


def iniciar_monitor(ruta="."):
    if not HAS_WATCHDOG:
        return "watchdog no disponible en este sistema."
    try:
        event_handler = MonitorArchivos()
        observer = Observer()
        observer.schedule(event_handler, ruta, recursive=True)
        observer.start()
        return f"Monitor iniciado en {ruta}"
    except Exception as e:
        return f"Error al iniciar monitor: {e}"
