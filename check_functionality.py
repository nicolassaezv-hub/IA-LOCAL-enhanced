# check_functionality.py
import importlib

def test_module(name, test_func):
    try:
        mod = importlib.import_module(name)
        print(f"[OK] {name} importado correctamente")
        test_func(mod)
    except Exception as e:
        print(f"[ERROR] {name}: {e}")

# --- Pruebas específicas ---

def test_faiss(mod):
    import numpy as np
    dim = 4
    index = mod.IndexFlatL2(dim)
    vecs = np.random.rand(5, dim).astype('float32')
    index.add(vecs)
    D, I = index.search(vecs[:1], 2)
    print("Faiss búsqueda:", D, I)

def test_llama(mod):
    try:
        from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
        docs = [mod.core.Document(text="Hola mundo desde LlamaIndex")]
        index = VectorStoreIndex.from_documents(docs)
        query_engine = index.as_query_engine()
        print("LlamaIndex respuesta:", query_engine.query("¿Qué dice el documento?"))
    except Exception as e:
        print("LlamaIndex prueba falló:", e)

def test_sympy(mod):
    x = mod.Symbol('x')
    expr = mod.integrate(mod.sin(x), (x, 0, mod.pi))
    print("Sympy integral:", expr)

def test_sqlalchemy(mod):
    from sqlalchemy import create_engine
    engine = create_engine("sqlite:///:memory:")
    print("SQLAlchemy motor creado:", engine)

def test_redis(mod):
    r = mod.Redis(host='localhost', port=6379, db=0)
    try:
        r.set("test", "funciona")
        print("Redis valor:", r.get("test"))
    except Exception as e:
        print("Redis no disponible:", e)

# --- Ejecutar pruebas ---
if __name__ == "__main__":
    test_module("faiss", test_faiss)
    test_module("llama_index", test_llama)
    test_module("sympy", test_sympy)
    test_module("sqlalchemy", test_sqlalchemy)
    test_module("redis", test_redis)
