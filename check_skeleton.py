import importlib

def test_module(name, test_func=None):
    try:
        mod = importlib.import_module(name)
        print(f"[OK] {name} importado correctamente")
        if test_func:
            test_func(mod)
    except Exception as e:
        print(f"[ERROR] {name}: {e}")

# --- Pruebas específicas ---

def test_io_files(mod):
    try:
        # Probar escritura y lectura básica
        ruta = "test.txt"
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("Hola IA local")
        with open(ruta, "r", encoding="utf-8") as f:
            contenido = f.read()
        print("io_files prueba lectura/escritura:", contenido)
    except Exception as e:
        print("io_files prueba falló:", e)

def test_ai_models(mod):
    try:
        # Probar que la función ask_openai existe
        if hasattr(mod, "ask_openai"):
            print("ai_models tiene ask_openai disponible")
        else:
            print("ai_models no tiene ask_openai")
    except Exception as e:
        print("ai_models prueba falló:", e)

def test_main(mod):
    try:
        # Verificar que main tiene un punto de entrada
        if hasattr(mod, "__name__"):
            print("main.py cargado correctamente")
    except Exception as e:
        print("main prueba falló:", e)

# --- Ejecutar pruebas ---
if __name__ == "__main__":
    test_module("io_files", test_io_files)
    test_module("ai_models", test_ai_models)
    test_module("main", test_main)
