# memory_router.py

"""
Router unificado de memoria ASTRA
"""

from memory import (
    guardar_memoria,
    cargar_memoria
)

from modules_extra import (
    FaissMemory,
    LlamaMemory,
    redis_set,
    redis_get
)


# ==========================================
# INSTANCIAS GLOBALES
# ==========================================

faiss_memory = FaissMemory()
llama_memory = LlamaMemory()


# ==========================================
# SQLITE
# ==========================================

def save_chat(user_text, assistant_text):

    try:

        guardar_memoria(
            user_text,
            assistant_text
        )

        return True

    except Exception:

        return False


def get_recent_chat(limit=10):

    try:

        return cargar_memoria(limit)

    except Exception:

        return []


# ==========================================
# REDIS
# ==========================================

def save_temp(key, value):

    try:

        redis_set(key, value)
        return True

    except Exception:

        return False


def get_temp(key):

    try:

        return redis_get(key)

    except Exception:

        return None


def delete_temp(key):

    try:

        from modules_extra import redis_delete
        redis_delete(key)
        return True

    except Exception:

        return False


# ==========================================
# FAISS
# ==========================================

def save_vector(vector, text):

    try:

        faiss_memory.add(
            vector,
            text
        )

        return True

    except Exception:

        return False


def search_vector(vector, k=5):

    try:

        return faiss_memory.search(
            vector,
            k
        )

    except Exception:

        return []


# ==========================================
# LLAMAINDEX
# ==========================================

def add_document(text):

    try:

        llama_memory.add_doc(text)

        return True

    except Exception:

        return False


def query_document(question):

    try:

        return llama_memory.query(question)

    except Exception as e:

        return str(e)


def search_memory(query, k=5):

    try:

        results = query_document(query)

        return results

    except Exception:

        return []


# ==========================================
# CONTEXTO GENERAL
# ==========================================

def get_context(limit=10):

    context = {}

    try:

        context["recent_chat"] = (
            get_recent_chat(limit)
        )

    except Exception:

        context["recent_chat"] = []

    context["memory_timestamp"] = None

    return context


# ==========================================
# ESTADO
# ==========================================

def memory_status():

    return {

        "sqlite": True,

        "faiss": faiss_memory is not None,

        "llamaindex": llama_memory is not None
    }
