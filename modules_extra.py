# modules_extra.py
import numpy as np
import faiss
from llama_index.core import Document, VectorStoreIndex
import sympy as sp
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker
import redis

# --- Faiss: memoria vectorial ---
class FaissMemory:
    def __init__(self, dim=128):
        self.index = faiss.IndexFlatL2(dim)
        self.vectors = []
        self.texts = []

    def add(self, vec, text):
        self.index.add(np.array([vec]).astype('float32'))
        self.vectors.append(vec)
        self.texts.append(text)

    def search(self, vec, k=3):
        D, I = self.index.search(np.array([vec]).astype('float32'), k)
        return [(self.texts[i], float(D[0][j])) for j, i in enumerate(I[0])]

# --- LlamaIndex: indexación de documentos ---
class LlamaMemory:
    def __init__(self):
        self.docs = []
        self.index = None

    def add_doc(self, text):
        doc = Document(text=text)
        self.docs.append(doc)
        self.index = VectorStoreIndex.from_documents(self.docs)

    def query(self, q):
        if not self.index:
            return "No hay documentos cargados."
        query_engine = self.index.as_query_engine()
        return str(query_engine.query(q))

# --- Sympy: cálculo simbólico ---
def calcular_integral(expr_str, var_str, a, b):
    var = sp.Symbol(var_str)
    expr = sp.sympify(expr_str)
    resultado = sp.integrate(expr, (var, a, b))
    return f"Integral de {expr_str} entre {a} y {b} = {resultado}"

# --- SQLAlchemy: base de datos ---
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

# --- Redis: memoria clave-valor ---
def redis_set(clave, valor):
    r = redis.Redis(host='localhost', port=6379, db=0)
    r.set(clave, valor)
    return f"Guardado en Redis: {clave} -> {valor}"

def redis_get(clave):
    r = redis.Redis(host='localhost', port=6379, db=0)
    val = r.get(clave)
    return val.decode("utf-8") if val else "Clave no encontrada"

# --- Diccionario de comandos ---
comandos_extra = {
    "faiss add": lambda: "Usa FaissMemory.add(vec,text)",
    "faiss search": lambda: "Usa FaissMemory.search(vec,k)",
    "llama add": lambda: "Usa LlamaMemory.add_doc(text)",
    "llama query": lambda: "Usa LlamaMemory.query(q)",
    "sympy integral": lambda: calcular_integral("sin(x)", "x", 0, sp.pi),
    "sqlalchemy usuario": lambda: guardar_usuario("Nico"),
    "redis set": lambda: redis_set("clave", "Hola desde Redis"),
    "redis get": lambda: redis_get("clave"),
}
