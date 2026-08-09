"""
cognitive_center.py — ASTRA Roadmap IV, Sección 7: Cognitive Center

"Ventana exclusiva para la memoria" — agrega y expone, en un solo lugar,
todo lo que ASTRA ya sabe y ya guarda en otros módulos (no inventa
almacenamiento nuevo, no duplica fuentes de verdad):

  7.1 Exploración de memoria
      - Conversaciones          -> memory.py (tabla `memoria`)
      - Proyectos / modelos / tareas -> project_memory.py
      - Herramientas usadas     -> memory.py (tabla `command_log`)
      - Preferencias aprendidas -> feedback/adaptive_thresholds.py +
                                    feedback/contextual_memory.py
      - Timeline unificado      -> fusión cronológica de todo lo anterior
      - Knowledge Graph         -> vista relacional ligera (pares↔categorías↔
                                    proyectos), derivada 100% de datos reales

  7.2 Búsqueda en lenguaje natural
      - `search_memory(query)`: intenta un plan de búsqueda vía LLM
        (Groq/Llama, qué fuentes consultar + keywords relevantes) con
        fallback heurístico por keywords si no hay API key o falla el LLM
        — mismo patrón graceful-fail que prediction_lab/prompt_analyzer.py.

Todo real, sin datos simulados. Si una fuente falla (DB bloqueada, tabla
vacía, módulo opcional ausente) se degrada devolviendo listas vacías en vez
de romper el resto del Cognitive Center.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from memory import DB_PATH as _DB_PATH
import project_memory as _pm

try:
    from feedback.contextual_memory import _memory as _ctx_memory
except Exception:
    _ctx_memory = None

try:
    from feedback.adaptive_thresholds import _thresholds as _adaptive
except Exception:
    _adaptive = None


# ══════════════════════════════════════════════════════════════════
# Timestamps mixtos entre módulos — normaliza para poder ordenar:
#   memoria / command_log   -> time.ctime()            "Mon Jul  6 02:32:10 2026"
#   project_memory          -> "%Y-%m-%d %H:%M:%S"
#   contextual_memory/adaptive_thresholds -> datetime.isoformat()
# ══════════════════════════════════════════════════════════════════
_TS_FORMATS = ("%a %b %d %H:%M:%S %Y", "%Y-%m-%d %H:%M:%S")


def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    ts = str(ts).strip()
    for fmt in _TS_FORMATS:
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _sort_key(ts: Optional[str]) -> datetime:
    return _parse_ts(ts) or datetime.min


# ══════════════════════════════════════════════════════════════════
# 7.1a — Conversaciones (memoria.py, tabla `memoria`)
# ══════════════════════════════════════════════════════════════════

def get_conversations(limit: int = 50) -> List[Dict[str, Any]]:
    """Últimas `limit` conversaciones reales, con id y timestamp (para timeline/búsqueda)."""
    try:
        conn = sqlite3.connect(_DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT id, user_input, ai_response, timestamp FROM memoria ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = c.fetchall()
        conn.close()
    except Exception:
        return []
    return [
        {"id": r[0], "user_input": r[1], "ai_response": r[2], "timestamp": r[3]}
        for r in rows
    ]


# ══════════════════════════════════════════════════════════════════
# 7.1b — Proyectos, modelos y tareas (project_memory.py)
# ══════════════════════════════════════════════════════════════════

def get_projects_overview() -> Dict[str, List[Dict[str, Any]]]:
    try:
        projects = _pm.list_projects()
    except Exception:
        projects = []
    try:
        models = _pm.list_models()
    except Exception:
        models = []
    try:
        tasks = _pm.get_all_tasks()
    except Exception:
        tasks = []
    return {"projects": projects, "models": models, "tasks": tasks}


# ══════════════════════════════════════════════════════════════════
# 7.1c — Herramientas usadas (command_log, memory.py)
# ══════════════════════════════════════════════════════════════════

def get_tools_usage(limit: int = 200) -> Dict[str, Any]:
    """Agrega el uso real de comandos/herramientas: por categoría, por par y top comandos."""
    try:
        from memory import get_command_log
        entries = get_command_log(limit=limit)
    except Exception:
        entries = []

    by_category: Dict[str, int] = {}
    by_command: Dict[str, int] = {}
    by_pair: Dict[str, int] = {}
    for e in entries:
        cat = e.get("category") or "general"
        by_category[cat] = by_category.get(cat, 0) + 1
        cmd_key = " ".join((e.get("command") or "").strip().split(" ")[:2]) or "?"
        by_command[cmd_key] = by_command.get(cmd_key, 0) + 1
        if e.get("pair"):
            by_pair[e["pair"]] = by_pair.get(e["pair"], 0) + 1

    top_commands = sorted(by_command.items(), key=lambda x: -x[1])[:15]
    return {
        "total_logged": len(entries),
        "by_category": by_category,
        "by_pair": by_pair,
        "top_commands": [{"command": c, "count": n} for c, n in top_commands],
        "recent": list(reversed(entries[-20:])),
    }


# ══════════════════════════════════════════════════════════════════
# 7.1d — Preferencias aprendidas (adaptive_thresholds + contextual_memory)
# ══════════════════════════════════════════════════════════════════

def get_learned_preferences() -> Dict[str, Any]:
    thresholds: Dict[str, Any] = {}
    if _adaptive is not None:
        try:
            thresholds = _adaptive.get_all()
        except Exception:
            thresholds = {}
    top_contexts: List[Dict[str, Any]] = []
    if _ctx_memory is not None:
        try:
            top_contexts = _ctx_memory.top_contexts(10)
        except Exception:
            top_contexts = []
    return {
        "adaptive_thresholds": thresholds,  # por par: confidence/adx aprendidos vs. default
        "default_confidence": 0.65,
        "default_adx": 22.0,
        "top_contexts": top_contexts,       # patrones de mercado con mejor tasa de éxito
    }


# ══════════════════════════════════════════════════════════════════
# 7.1e — Timeline unificado
# ══════════════════════════════════════════════════════════════════

def get_timeline(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Fusiona cronológicamente eventos reales: conversaciones, comandos
    ejecutados, modelos entrenados/actualizados, proyectos creados y
    tareas creadas/completadas. Cada evento viene de una tabla real —
    sin datos simulados.
    """
    events: List[Dict[str, Any]] = []

    for conv in get_conversations(limit=limit):
        events.append({
            "kind": "conversation",
            "timestamp": conv["timestamp"],
            "title": (conv["user_input"] or "")[:80],
            "detail": (conv["ai_response"] or "")[:160],
        })

    try:
        from memory import get_command_log
        for cmd in get_command_log(limit=limit):
            events.append({
                "kind": "command",
                "timestamp": cmd["executed_at"],
                "title": cmd["command"],
                "detail": cmd["summary"],
                "category": cmd.get("category"),
                "pair": cmd.get("pair"),
            })
    except Exception:
        pass

    overview = get_projects_overview()
    for m in overview["models"]:
        events.append({
            "kind": "model",
            "timestamp": m.get("trained_at"),
            "title": f"Modelo entrenado: {m.get('pair')}",
            "detail": f"accuracy={m.get('accuracy')}  precision={m.get('precision')}",
        })
        if m.get("updated_at") and m.get("updated_at") != m.get("trained_at"):
            events.append({
                "kind": "model_update",
                "timestamp": m.get("updated_at"),
                "title": f"Modelo actualizado: {m.get('pair')}",
                "detail": f"wfv_score={m.get('wfv_score')}",
            })
    for p in overview["projects"]:
        events.append({
            "kind": "project",
            "timestamp": p.get("created_at"),
            "title": f"Proyecto creado: {p.get('name')}",
            "detail": p.get("description") or "",
        })
    for t in overview["tasks"]:
        events.append({
            "kind": "task",
            "timestamp": t.get("completed_at") or t.get("created_at"),
            "title": f"Tarea {'completada' if t.get('done') else 'creada'}: {t.get('description')}",
            "detail": t.get("project_name") or "",
        })

    events.sort(key=lambda e: _sort_key(e.get("timestamp")), reverse=True)
    return events[:limit]


# ══════════════════════════════════════════════════════════════════
# 7.1f — Knowledge Graph ligero (vista relacional, no semántico/embeddings)
# ══════════════════════════════════════════════════════════════════

def build_knowledge_graph() -> Dict[str, Any]:
    """
    Grafo simple pero 100% derivado de relaciones reales:
      nodos  -> pares (con modelo entrenado), proyectos, categorías de comando
      aristas -> par↔categoría (cuántos comandos de esa categoría tocaron ese par)
    No es un grafo semántico — es una vista honesta de lo que ASTRA relaciona,
    consistente con el resto del proyecto (no se simula una capacidad que no existe).
    """
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    seen: set = set()

    def add_node(node_id: str, label: str, group: str, **extra):
        if node_id in seen:
            return
        seen.add(node_id)
        nodes.append({"id": node_id, "label": label, "group": group, **extra})

    overview = get_projects_overview()

    for m in overview["models"]:
        pair = m.get("pair")
        if pair:
            add_node(f"pair::{pair}", pair, "pair", accuracy=m.get("accuracy"), precision=m.get("precision"))

    for p in overview["projects"]:
        name = p.get("name")
        if name:
            add_node(f"project::{name}", name, "project", status=p.get("status"))

    task_counts: Dict[str, int] = {}
    for t in overview["tasks"]:
        proj = t.get("project_name")
        if proj:
            task_counts[proj] = task_counts.get(proj, 0) + 1
    for n in nodes:
        if n["group"] == "project":
            n["task_count"] = task_counts.get(n["label"], 0)

    try:
        from memory import get_command_log
        raw = get_command_log(limit=500)
    except Exception:
        raw = []

    tools = get_tools_usage(limit=500)
    for cat in tools["by_category"]:
        add_node(f"category::{cat}", cat, "category", count=tools["by_category"][cat])

    pair_cat_counts: Dict[tuple, int] = {}
    for e in raw:
        if e.get("pair") and e.get("category"):
            key = (e["pair"], e["category"])
            pair_cat_counts[key] = pair_cat_counts.get(key, 0) + 1
    for (pair, cat), n in pair_cat_counts.items():
        pid, cid = f"pair::{pair}", f"category::{cat}"
        if pid not in seen:
            add_node(pid, pair, "pair")
        if cid not in seen:
            add_node(cid, cat, "category", count=n)
        edges.append({"source": pid, "target": cid, "weight": n, "type": "used_in"})

    return {"nodes": nodes, "edges": edges}


# ══════════════════════════════════════════════════════════════════
# 7.2 — Búsqueda en lenguaje natural sobre la memoria
# ══════════════════════════════════════════════════════════════════

_SEARCH_SYSTEM_PROMPT = """Eres el planificador de búsqueda del Cognitive Center de ASTRA.
Dado un mensaje del usuario en lenguaje natural, decide:
  1. "keywords": palabras clave relevantes para buscar (en minúsculas, sin stopwords).
  2. "sources": subconjunto de ["conversations","projects","models","tasks","commands","preferences"]
     que probablemente contienen la respuesta.
Responde SOLO un JSON válido, sin texto adicional:
{"keywords": ["..."], "sources": ["..."], "intent": "breve descripción"}
"""


def _try_llm_query_plan(query: str) -> Optional[dict]:
    try:
        from ai_models import _get_client, _active_model
    except Exception:
        return None
    try:
        client = _get_client()
        model = _active_model()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SEARCH_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            temperature=0.1,
            max_tokens=300,
        )
        raw = response.choices[0].message.content.strip()
        match = re.search(r"\{.*\}", raw, re.S)
        if not match:
            return None
        return json.loads(match.group(0))
    except Exception:
        return None


_STOPWORDS = {
    "para", "como", "cuando", "donde", "sobre", "desde", "hasta", "tiene",
    "fueron", "estan", "están", "cuales", "cuáles", "esta", "está", "todos",
    "todas", "algun", "algún", "alguna", "que", "cual", "cuál", "quien", "quién",
}


# Palabras "gatillo" que solo indican DE QUÉ FUENTE hablar (intent), no texto
# a buscar dentro de los registros — si se dejan como keyword de filtrado,
# una pregunta genérica tipo "qué modelos he entrenado" no matchea nada
# porque ningún registro real contiene literalmente la palabra "modelos".
# Se usan para clasificar la fuente y LUEGO se excluyen de los keywords.
_TRIGGER_WORDS = {
    "conversations": ("habl", "dije", "convers", "chat", "pregunt"),
    "projects_tasks": ("proyecto", "tarea", "pendiente"),
    "models": ("modelo", "entren", "accuracy", "precision", "par "),
    "commands": ("comando", "hice", "ejecut", "herramienta", "tool"),
    "preferences": ("prefer", "umbral", "threshold", "ajust"),
}


def _heuristic_query_plan(query: str) -> dict:
    q = query.lower()
    sources: List[str] = []
    trigger_stems: List[str] = []

    if any(w in q for w in _TRIGGER_WORDS["conversations"]):
        sources.append("conversations")
        trigger_stems += _TRIGGER_WORDS["conversations"]
    if any(w in q for w in _TRIGGER_WORDS["projects_tasks"]):
        sources += ["projects", "tasks"]
        trigger_stems += _TRIGGER_WORDS["projects_tasks"]
    if any(w in q for w in _TRIGGER_WORDS["models"]):
        sources.append("models")
        trigger_stems += _TRIGGER_WORDS["models"]
    if any(w in q for w in _TRIGGER_WORDS["commands"]):
        sources.append("commands")
        trigger_stems += _TRIGGER_WORDS["commands"]
    if any(w in q for w in _TRIGGER_WORDS["preferences"]):
        sources.append("preferences")
        trigger_stems += _TRIGGER_WORDS["preferences"]
    if not sources:
        sources = ["conversations", "projects", "models", "tasks", "commands"]

    raw_keywords = [w for w in re.findall(r"[a-záéíóúñ0-9]+", q) if len(w) >= 4 and w not in _STOPWORDS]
    # descarta palabras que son (o contienen) un stem gatillo: son intención, no contenido a buscar
    keywords = [w for w in raw_keywords if not any(stem.strip() and stem.strip() in w for stem in trigger_stems)]

    return {"keywords": keywords, "sources": sorted(set(sources)), "intent": "heuristic_keyword_search"}


def search_memory(query: str, limit: int = 20) -> Dict[str, Any]:
    """
    7.2 — Búsqueda en lenguaje natural sobre toda la memoria de ASTRA.
    Plan vía LLM (qué fuentes + keywords) con fallback heurístico si no hay
    API key o falla el LLM — graceful fail, mismo patrón que prompt_analyzer.py.
    """
    if not query or not query.strip():
        return {"ok": False, "error": "Query vacía.", "results": {}}

    plan = _try_llm_query_plan(query)
    used_llm = plan is not None
    if plan is None:
        plan = _heuristic_query_plan(query)

    keywords = [k.lower() for k in (plan.get("keywords") or []) if k]
    sources = plan.get("sources") or ["conversations", "projects", "models", "tasks", "commands"]

    def _matches(text: Optional[str]) -> bool:
        if not keywords:
            return True
        text = (text or "").lower()
        return any(k in text for k in keywords)

    results: Dict[str, Any] = {}
    overview: Optional[Dict[str, Any]] = None
    needs_overview = any(s in sources for s in ("projects", "tasks", "models"))
    if needs_overview:
        overview = get_projects_overview()

    if "conversations" in sources:
        results["conversations"] = [
            c for c in get_conversations(limit=200)
            if _matches(c["user_input"]) or _matches(c["ai_response"])
        ][:limit]

    if "projects" in sources and overview is not None:
        results["projects"] = [
            p for p in overview["projects"]
            if _matches(p.get("name")) or _matches(p.get("description"))
        ][:limit]

    if "tasks" in sources and overview is not None:
        results["tasks"] = [
            t for t in overview["tasks"]
            if _matches(t.get("description")) or _matches(t.get("project_name"))
        ][:limit]

    if "models" in sources and overview is not None:
        results["models"] = [
            m for m in overview["models"]
            if _matches(m.get("pair")) or _matches(m.get("csv_path"))
        ][:limit]

    if "commands" in sources:
        try:
            from memory import get_command_log
            entries = get_command_log(limit=300)
        except Exception:
            entries = []
        results["commands"] = [
            e for e in entries
            if _matches(e.get("command")) or _matches(e.get("summary")) or _matches(e.get("pair"))
        ][:limit]

    if "preferences" in sources:
        prefs = get_learned_preferences()
        if keywords:
            prefs = {
                **prefs,
                "adaptive_thresholds": {
                    p: v for p, v in prefs["adaptive_thresholds"].items() if _matches(p)
                },
            }
        results["preferences"] = prefs

    total_hits = sum(len(v) for v in results.values() if isinstance(v, list))

    # Fallback honesto: si había keywords y el filtrado dejó todo vacío
    # (típico de preguntas genéricas tipo "qué modelos he entrenado" donde
    # ninguna keyword aparece literalmente en los registros), no devolvemos
    # un "sin resultados" inútil — mostramos los más recientes de cada
    # fuente consultada, marcado explícitamente como fallback sin filtrar.
    used_fallback = False
    list_results = {k: v for k, v in results.items() if isinstance(v, list)}
    if keywords and list_results and total_hits == 0:
        used_fallback = True
        if "conversations" in results:
            results["conversations"] = get_conversations(limit=limit)
        if "projects" in results and overview is not None:
            results["projects"] = overview["projects"][:limit]
        if "tasks" in results and overview is not None:
            results["tasks"] = overview["tasks"][:limit]
        if "models" in results and overview is not None:
            results["models"] = overview["models"][:limit]
        if "commands" in results:
            try:
                from memory import get_command_log
                results["commands"] = list(reversed(get_command_log(limit=limit)))
            except Exception:
                results["commands"] = []
        total_hits = sum(len(v) for v in results.values() if isinstance(v, list))

    return {
        "ok": True,
        "query": query,
        "used_llm": used_llm,
        "keywords": keywords,
        "sources_searched": sources,
        "total_hits": total_hits,
        "used_fallback_unfiltered": used_fallback,
        "results": results,
    }


# ══════════════════════════════════════════════════════════════════
# Comandos CLI (consistentes con el resto de ASTRA — `main.py`)
# ══════════════════════════════════════════════════════════════════

def cmd_memoria_explorar() -> str:
    """Resumen legible del Cognitive Center para la consola."""
    from memory import contar_entradas
    overview = get_projects_overview()
    tools = get_tools_usage()
    prefs = get_learned_preferences()

    lines = [
        f"{'═'*60}",
        "  ASTRA — Cognitive Center",
        f"{'═'*60}",
        f"  Conversaciones totales       : {contar_entradas()}",
        f"  Proyectos                    : {len(overview['projects'])}",
        f"  Modelos entrenados           : {len(overview['models'])}",
        f"  Tareas (pend./total)         : "
        f"{sum(1 for t in overview['tasks'] if not t.get('done'))}/{len(overview['tasks'])}",
        f"  Comandos registrados         : {tools['total_logged']}",
        f"  Pares con umbrales propios    : {len(prefs['adaptive_thresholds'])}",
        "",
        "  Top comandos:",
    ]
    for c in tools["top_commands"][:5]:
        lines.append(f"    {c['command']:<28} x{c['count']}")
    lines.append(f"{'═'*60}")
    return "\n".join(lines)


def cmd_memoria_buscar(query: str) -> str:
    """Comando CLI: `memoria buscar <consulta en lenguaje natural>`."""
    r = search_memory(query)
    if not r.get("ok"):
        return f"[Cognitive Center] {r.get('error', 'Error desconocido en la búsqueda.')}"

    lines = [
        f"{'═'*60}",
        f"  ASTRA — Búsqueda en memoria: \"{r['query']}\"",
        f"  (motor: {'LLM' if r['used_llm'] else 'heurístico'} | "
        f"fuentes: {', '.join(r['sources_searched'])} | hits: {r['total_hits']})",
        f"{'═'*60}",
    ]
    if r.get("used_fallback_unfiltered"):
        lines.append("  (sin coincidencia exacta de texto — mostrando lo más reciente de esas fuentes)")
    results = r["results"]
    if "conversations" in results:
        lines.append(f"\n  Conversaciones ({len(results['conversations'])}):")
        for c in results["conversations"][:5]:
            lines.append(f"    [{c['timestamp']}] Tú: {(c['user_input'] or '')[:70]}")
    if "commands" in results:
        lines.append(f"\n  Comandos ({len(results['commands'])}):")
        for cmd in results["commands"][:5]:
            lines.append(f"    [{cmd['executed_at']}] {cmd['command']} → {(cmd['summary'] or '')[:60]}")
    if "models" in results:
        lines.append(f"\n  Modelos ({len(results['models'])}):")
        for m in results["models"][:5]:
            lines.append(f"    {m.get('pair')}: accuracy={m.get('accuracy')} precision={m.get('precision')}")
    if "projects" in results:
        lines.append(f"\n  Proyectos ({len(results['projects'])}):")
        for p in results["projects"][:5]:
            lines.append(f"    {p.get('name')} [{p.get('status')}]")
    if "tasks" in results:
        lines.append(f"\n  Tareas ({len(results['tasks'])}):")
        for t in results["tasks"][:5]:
            lines.append(f"    {'✓' if t.get('done') else '○'} {t.get('description')} ({t.get('project_name')})")
    if "preferences" in results:
        prefs = results["preferences"]
        lines.append(f"\n  Preferencias aprendidas ({len(prefs['adaptive_thresholds'])} pares con ajuste):")
        for pair, v in list(prefs["adaptive_thresholds"].items())[:5]:
            lines.append(f"    {pair}: confidence={v.get('confidence')} adx={v.get('adx')}")
    if r["total_hits"] == 0 and not results.get("preferences"):
        lines.append("\n  Sin resultados para esta consulta.")
    lines.append(f"\n{'═'*60}")
    return "\n".join(lines)
