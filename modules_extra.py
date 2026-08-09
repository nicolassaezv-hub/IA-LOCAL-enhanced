import numpy as np
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker

try:
    import faiss
    HAS_FAISS = True
except Exception:
    faiss = None
    HAS_FAISS = False

try:
    from llama_index.core import Document, VectorStoreIndex
    HAS_LLAMA = True
except Exception:
    Document = None
    VectorStoreIndex = None
    HAS_LLAMA = False

try:
    import sympy as sp
    HAS_SYMPY = True
except ImportError:
    sp = None
    HAS_SYMPY = False

try:
    import redis as redis_lib
    HAS_REDIS = True
except ImportError:
    redis_lib = None
    HAS_REDIS = False


class FaissMemory:
    def __init__(self, dim=128):
        if HAS_FAISS:
            self.index = faiss.IndexFlatL2(dim)
        else:
            self.index = None
        self.vectors = []
        self.texts = []

    def add(self, vec, text):
        if not HAS_FAISS:
            return "FAISS no disponible en este sistema."
        self.index.add(np.array([vec]).astype('float32'))
        self.vectors.append(vec)
        self.texts.append(text)

    def search(self, vec, k=3):
        if not HAS_FAISS or not self.texts:
            return []
        D, I = self.index.search(np.array([vec]).astype('float32'), k)
        return [(self.texts[i], float(D[0][j])) for j, i in enumerate(I[0]) if i < len(self.texts)]


class LlamaMemory:
    def __init__(self):
        self.docs = []
        self.index = None

    def add_doc(self, text):
        if not HAS_LLAMA:
            return "LlamaIndex no disponible en este sistema."
        doc = Document(text=text)
        self.docs.append(doc)
        self.index = VectorStoreIndex.from_documents(self.docs)

    def query(self, q):
        if not HAS_LLAMA:
            return "LlamaIndex no disponible en este sistema."
        if not self.index:
            return "No hay documentos cargados."
        query_engine = self.index.as_query_engine()
        return str(query_engine.query(q))


def calcular_integral(expr_str, var_str, a, b):
    if not HAS_SYMPY:
        return "sympy no disponible en este sistema."
    var = sp.Symbol(var_str)
    expr = sp.sympify(expr_str)
    resultado = sp.integrate(expr, (var, a, b))
    return f"Integral de {expr_str} entre {a} y {b} = {resultado}"


Base = declarative_base()

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True)
    nombre = Column(String)

def guardar_usuario(nombre):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    nuevo = Usuario(nombre=nombre)
    session.add(nuevo)
    session.commit()
    return f"Usuario guardado: {nuevo.nombre}"


def redis_set(clave, valor):
    if not HAS_REDIS:
        return "Redis no disponible en este sistema."
    try:
        r = redis_lib.Redis(host='localhost', port=6379, db=0)
        r.set(clave, valor)
        return f"Guardado en Redis: {clave} -> {valor}"
    except Exception as e:
        return f"Redis no disponible: {e}"

def redis_get(clave):
    if not HAS_REDIS:
        return "Redis no disponible en este sistema."
    try:
        r = redis_lib.Redis(host='localhost', port=6379, db=0)
        val = r.get(clave)
        return val.decode("utf-8") if val else "Clave no encontrada"
    except Exception as e:
        return f"Redis no disponible: {e}"

def redis_delete(clave):
    if not HAS_REDIS:
        return "Redis no disponible en este sistema."
    try:
        r = redis_lib.Redis(host='localhost', port=6379, db=0)
        r.delete(clave)
        return f"Clave eliminada: {clave}"
    except Exception as e:
        return f"Redis no disponible: {e}"


comandos_extra = {
    "faiss add":          lambda: "Usa FaissMemory.add(vec,text)",
    "faiss search":       lambda: "Usa FaissMemory.search(vec,k)",
    "llama add":          lambda: "Usa LlamaMemory.add_doc(text)",
    "llama query":        lambda: "Usa LlamaMemory.query(q)",
    "sympy integral":     lambda: calcular_integral("sin(x)", "x", 0, 3.14159265),
    "sqlalchemy usuario": lambda: guardar_usuario("Nico"),
    "redis set":          lambda: redis_set("clave", "Hola desde Redis"),
    "redis get":          lambda: redis_get("clave"),
}
