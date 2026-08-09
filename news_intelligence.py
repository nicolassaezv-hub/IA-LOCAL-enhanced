# news_intelligence.py
"""
ASTRA — News Intelligence (Fase 4)

Obtiene noticias de un par Forex, analiza el sentimiento
con Llama-3.3-70B (Groq, ya integrado en ai_models.py) y
combina el score con la señal técnica del predictor.

Fuentes de noticias (sin API key, scraping libre):
  1. Investing.com/news  — por par (EURUSD, XAUUSD, etc.)
  2. FXStreet.com        — feed de noticias
  3. Yahoo Finance       — noticias del ticker correspondiente

Pipeline:
  fetch_news(pair)         → list[dict]  (title, summary, url, source, ts)
  analyze_sentiment(news)  → dict        (score, label, reasoning)
  combined_score(pair, csv) → dict       (technical + news → final recommendation)
  cmd_news(pair)           → str         (para _print_result en main.py)
  cmd_news_predict(pair, csv) → str      (señal técnica + sentimiento)

Score combinado:
  final_score = 0.70 * technical_confidence + 0.30 * news_score
  Si los dos coinciden en dirección → señal REFORZADA
  Si discrepan → señal REDUCIDA o HOLD
"""

import re
import time
import os
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

from colorama import Fore, Style


# ══════════════════════════════════════════════════════════
#  MAPA PAR → TICKERS / URLS
# ══════════════════════════════════════════════════════════

_PAIR_CONFIG = {
    # Forex majors
    "EURUSD": {"yf_ticker": "EURUSD=X",  "name": "Euro / US Dollar",     "keywords": ["EUR", "USD", "euro", "dollar", "fed", "ecb"]},
    "GBPUSD": {"yf_ticker": "GBPUSD=X",  "name": "British Pound / USD",  "keywords": ["GBP", "USD", "pound", "sterling", "boe"]},
    "USDJPY": {"yf_ticker": "USDJPY=X",  "name": "USD / Japanese Yen",   "keywords": ["JPY", "USD", "yen", "boj"]},
    "USDCHF": {"yf_ticker": "USDCHF=X",  "name": "USD / Swiss Franc",    "keywords": ["CHF", "USD", "franc", "snb"]},
    "AUDUSD": {"yf_ticker": "AUDUSD=X",  "name": "Australian Dollar",    "keywords": ["AUD", "USD", "aussie", "rba"]},
    "USDCAD": {"yf_ticker": "USDCAD=X",  "name": "USD / Canadian Dollar","keywords": ["CAD", "USD", "loonie", "boc"]},
    "NZDUSD": {"yf_ticker": "NZDUSD=X",  "name": "NZ Dollar / USD",      "keywords": ["NZD", "USD", "kiwi", "rbnz"]},
    # Commodities
    "XAUUSD": {"yf_ticker": "GC=F",      "name": "Gold / US Dollar",     "keywords": ["gold", "XAU", "bullion", "safe haven"]},
    "XAGUSD": {"yf_ticker": "SI=F",      "name": "Silver / US Dollar",   "keywords": ["silver", "XAG"]},
    "USOIL":  {"yf_ticker": "CL=F",      "name": "Crude Oil WTI",        "keywords": ["oil", "crude", "WTI", "opec"]},
    "UKOIL":  {"yf_ticker": "BZ=F",      "name": "Brent Crude Oil",      "keywords": ["brent", "oil", "crude", "opec"]},
}

_DEFAULT_CONFIG = {"yf_ticker": None, "name": "", "keywords": []}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def _clean(pair: str) -> str:
    return pair.upper().replace("/", "").replace("_", "").replace("-", "")


def _pair_cfg(pair: str) -> dict:
    return _PAIR_CONFIG.get(_clean(pair), _DEFAULT_CONFIG)


# ══════════════════════════════════════════════════════════
#  FETCH NOTICIAS
# ══════════════════════════════════════════════════════════

def _fetch_yahoo_finance(pair: str, max_items: int = 8) -> List[dict]:
    """Scraping de noticias de Yahoo Finance para el ticker del par."""
    cfg    = _pair_cfg(pair)
    ticker = cfg.get("yf_ticker")
    if not ticker:
        return []

    url = f"https://finance.yahoo.com/quote/{ticker}/news/"
    items = []

    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")

        # Yahoo Finance estructura sus noticias en elementos <h3> o <li>
        articles = soup.find_all("h3", limit=max_items)
        for art in articles:
            title = art.get_text(strip=True)
            link  = ""
            a_tag = art.find("a")
            if a_tag and a_tag.get("href"):
                href = a_tag["href"]
                link = href if href.startswith("http") else f"https://finance.yahoo.com{href}"
            if title:
                items.append({
                    "title":   title,
                    "summary": "",
                    "url":     link,
                    "source":  "Yahoo Finance",
                    "ts":      time.strftime("%Y-%m-%d %H:%M"),
                })
    except Exception:
        pass

    return items[:max_items]


def _fetch_fxstreet(pair: str, max_items: int = 6) -> List[dict]:
    """Scraping de FXStreet news para el par."""
    clean   = _clean(pair)
    base_p  = clean[:3].lower()   # EUR, GBP, XAU, etc.
    url     = f"https://www.fxstreet.com/news/{base_p}-news"
    items   = []

    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")

        for art in soup.find_all("article", limit=max_items):
            title_tag = art.find(["h2", "h3", "h4"])
            title     = title_tag.get_text(strip=True) if title_tag else ""
            a_tag     = art.find("a")
            link      = ""
            if a_tag and a_tag.get("href"):
                href = a_tag["href"]
                link = href if href.startswith("http") else f"https://www.fxstreet.com{href}"
            summary_tag = art.find("p")
            summary     = summary_tag.get_text(strip=True)[:200] if summary_tag else ""
            if title:
                items.append({
                    "title":   title,
                    "summary": summary,
                    "url":     link,
                    "source":  "FXStreet",
                    "ts":      time.strftime("%Y-%m-%d %H:%M"),
                })
    except Exception:
        pass

    return items[:max_items]


def fetch_news(pair: str, max_total: int = 10) -> List[dict]:
    """
    Obtiene noticias del par de múltiples fuentes.
    Devuelve lista de dicts con keys: title, summary, url, source, ts.
    """
    news = []

    # Fuente 1: Yahoo Finance
    try:
        yf_news = _fetch_yahoo_finance(pair, max_items=6)
        news.extend(yf_news)
    except Exception:
        pass

    # Fuente 2: FXStreet
    if len(news) < max_total:
        try:
            fx_news = _fetch_fxstreet(pair, max_items=6)
            news.extend(fx_news)
        except Exception:
            pass

    # Deduplicar por título
    seen   = set()
    unique = []
    for n in news:
        key = n["title"][:60].lower()
        if key not in seen:
            seen.add(key)
            unique.append(n)

    return unique[:max_total]


# ══════════════════════════════════════════════════════════
#  ANÁLISIS DE SENTIMIENTO VÍA LLAMA
# ══════════════════════════════════════════════════════════

def analyze_sentiment(news: List[dict], pair: str) -> dict:
    """
    Analiza el sentimiento de las noticias usando Llama-3.3-70B (Groq).
    Devuelve:
      score     float  [-1.0, +1.0]  (−1 muy bearish, +1 muy bullish)
      label     str    "bullish" | "bearish" | "neutral"
      confidence float [0.0, 1.0]
      reasoning str    explicación breve de Llama
    """
    if not news:
        return {"score": 0.0, "label": "neutral", "confidence": 0.3, "reasoning": "Sin noticias disponibles."}

    cfg  = _pair_cfg(pair)
    name = cfg.get("name") or pair.upper()

    # Construir texto de noticias para el prompt
    news_text = "\n".join([
        f"- [{n['source']}] {n['title']}" +
        (f": {n['summary']}" if n.get("summary") else "")
        for n in news[:8]
    ])

    prompt = f"""Analiza el sentimiento de mercado para {name} ({pair.upper()}) basándote en estas noticias recientes.

NOTICIAS:
{news_text}

INSTRUCCIONES:
1. Determina si el sentimiento es BULLISH (alcista), BEARISH (bajista) o NEUTRAL para {pair.upper()}.
2. Asigna un score numérico de -1.0 (muy bearish) a +1.0 (muy bullish).
3. Estima tu nivel de confianza en el análisis (0.0 a 1.0).

Responde SOLO en este formato JSON exacto:
{{
  "score": 0.0,
  "label": "neutral",
  "confidence": 0.5,
  "reasoning": "Explicación breve en español (máx 100 palabras)"
}}"""

    try:
        from ai_models import ask_openai as ask_llama
        raw = ask_llama(prompt)

        # Parsear JSON de la respuesta
        match = re.search(r'\{[^}]+\}', raw, re.DOTALL)
        if match:
            import json
            data = json.loads(match.group())
            score      = float(max(-1.0, min(1.0, data.get("score", 0.0))))
            label      = data.get("label", "neutral").lower()
            confidence = float(max(0.0, min(1.0, data.get("confidence", 0.5))))
            reasoning  = data.get("reasoning", "")

            if label not in ("bullish", "bearish", "neutral"):
                label = "bullish" if score > 0.1 else "bearish" if score < -0.1 else "neutral"

            return {
                "score":      round(score, 3),
                "label":      label,
                "confidence": round(confidence, 3),
                "reasoning":  reasoning,
                "news_count": len(news),
            }

    except Exception as e:
        pass

    # Fallback heurístico si Llama falla
    return _heuristic_sentiment(news, pair)


def _heuristic_sentiment(news: List[dict], pair: str) -> dict:
    """Fallback: análisis por keywords cuando Llama no está disponible."""
    BULLISH_KW = ["rise", "rally", "gain", "jump", "surge", "boost", "strong",
                  "sube", "suba", "alza", "alcista", "positivo", "bullish"]
    BEARISH_KW = ["fall", "drop", "decline", "plunge", "weak", "loss", "risk",
                  "baja", "cae", "bajista", "negativo", "bearish", "sell-off"]

    bull = 0
    bear = 0

    all_text = " ".join([
        (n.get("title", "") + " " + n.get("summary", "")).lower()
        for n in news
    ])

    for kw in BULLISH_KW:
        bull += all_text.count(kw)
    for kw in BEARISH_KW:
        bear += all_text.count(kw)

    total = bull + bear
    if total == 0:
        score, label = 0.0, "neutral"
    else:
        score = (bull - bear) / total
        label = "bullish" if score > 0.1 else "bearish" if score < -0.1 else "neutral"

    return {
        "score":      round(score, 3),
        "label":      label,
        "confidence": 0.4,
        "reasoning":  f"Análisis heurístico — {bull} señales alcistas, {bear} bajistas en {len(news)} noticias.",
        "news_count": len(news),
    }


# ══════════════════════════════════════════════════════════
#  SCORE COMBINADO TÉCNICO + SENTIMIENTO
# ══════════════════════════════════════════════════════════

def combined_score(
    pair:     str,
    csv_path: str,
    w_tech:   float = 0.70,
    w_news:   float = 0.30,
) -> dict:
    """
    Combina señal técnica (integrated_pipeline) con sentimiento de noticias.

    Pesos por defecto:
      70% técnico  (confidence del predictor)
      30% noticias (score de sentimiento)

    Devuelve dict completo con:
      action, final_score, technical, sentiment, recommendation
    """
    result = {
        "pair":      _clean(pair),
        "csv_path":  csv_path,
        "technical": {},
        "sentiment": {},
        "final_score":     0.0,
        "action":          "HOLD",
        "recommendation":  "",
    }

    # ── 1. Señal técnica ──────────────────────────────────
    try:
        from forex.prediction.integrated_pipeline import ForexIntegratedPipeline
        pipeline = ForexIntegratedPipeline()
        tech     = pipeline.predict(csv_path, pair=pair)
        result["technical"] = tech
    except Exception as e:
        result["technical"] = {"error": str(e)}
        tech = {}

    # ── 2. Sentimiento noticias ───────────────────────────
    news      = fetch_news(pair)
    sentiment = analyze_sentiment(news, pair)
    result["sentiment"] = sentiment

    # ── 3. Score combinado ────────────────────────────────
    tech_action = tech.get("action", "HOLD")
    tech_conf   = tech.get("confidence", 0.0)
    sent_score  = sentiment.get("score", 0.0)
    sent_label  = sentiment.get("label", "neutral")

    # Convertir confianza técnica a score direccional [-1, +1]
    tech_direction = tech.get("direction", "")
    if tech_action == "BUY":
        tech_signed = tech_conf
    elif tech_action == "SELL":
        tech_signed = -tech_conf
    else:
        tech_signed = 0.0

    # Score final ponderado
    final = (w_tech * tech_signed) + (w_news * sent_score)
    result["final_score"] = round(final, 4)

    # ── 4. Decisión final ─────────────────────────────────
    THRESHOLD = 0.40   # umbral para señal activa (equivalente a 0.57 confidence puro)

    if tech_action not in ("BUY", "SELL"):
        # Señal técnica HOLD → mantener HOLD aunque noticias sean buenas
        action = "HOLD"
        recom  = f"Señal técnica HOLD — noticias: {sent_label.upper()} ({sent_score:+.2f}). Esperar setup técnico."

    elif abs(final) < THRESHOLD:
        # Score final bajo
        action = "HOLD"
        recom  = (
            f"Score combinado bajo ({final:+.3f}). "
            f"Técnico: {tech_action} ({tech_conf:.2%}) | "
            f"Noticias: {sent_label.upper()} ({sent_score:+.2f}). "
            f"Dirección discrepante — evitar entrada."
        )

    elif final > 0:
        action = "BUY"
        if sent_label == "bullish" and tech_action == "BUY":
            recom = f"Senyal BUY REFORZADA — técnico y noticias alineados. Score: {final:+.3f}"
        else:
            recom = f"Senyal BUY (técnico domina). Score: {final:+.3f}. Noticias: {sent_label}"

    else:
        action = "SELL"
        if sent_label == "bearish" and tech_action == "SELL":
            recom = f"Senyal SELL REFORZADA — técnico y noticias alineados. Score: {final:+.3f}"
        else:
            recom = f"Senyal SELL (técnico domina). Score: {final:+.3f}. Noticias: {sent_label}"

    result["action"]         = action
    result["recommendation"] = recom
    result["news_items"]     = news

    # Auto-guardar señal combinada en signal_tracker
    try:
        from signal_tracker import save_signal
        save_signal({**tech, "pair": pair, "action": action}, csv_path)
    except Exception:
        pass

    return result


# ══════════════════════════════════════════════════════════
#  COMANDOS CLI
# ══════════════════════════════════════════════════════════

def cmd_news(pair: str) -> str:
    """Comando: 'noticias <par>' — fetch + sentimiento sin señal técnica"""
    clean = _clean(pair)
    cfg   = _pair_cfg(pair)
    name  = cfg.get("name") or clean

    print(Fore.CYAN + f"[NEWS] Buscando noticias para {name}..." + Style.RESET_ALL)

    news = fetch_news(pair)
    if not news:
        return (
            f"No se encontraron noticias para {clean}.\n"
            f"  Asegúrate de tener conexión a internet."
        )

    sentiment = analyze_sentiment(news, pair)

    SENT_COLOR = {
        "bullish": Fore.GREEN,
        "bearish": Fore.RED,
        "neutral": Fore.YELLOW,
    }
    label  = sentiment.get("label", "neutral")
    score  = sentiment.get("score", 0.0)
    conf   = sentiment.get("confidence", 0.0)
    reason = sentiment.get("reasoning", "")
    color  = SENT_COLOR.get(label, Fore.WHITE)

    lines = [
        Fore.GREEN + f"{'─'*64}" + Style.RESET_ALL,
        Fore.GREEN + f"  NOTICIAS — {clean}  ({len(news)} artículos)" + Style.RESET_ALL,
        Fore.GREEN + f"{'─'*64}" + Style.RESET_ALL,
    ]

    for n in news[:7]:
        src   = (n.get("source") or "")[:12]
        title = (n.get("title")  or "")[:70]
        lines.append(f"  [{src:<12}] {title}")
        if n.get("summary"):
            lines.append(f"              {n['summary'][:80]}")

    lines += [
        "",
        Fore.GREEN + f"  {'─'*50}" + Style.RESET_ALL,
        f"  SENTIMIENTO  : {color}{label.upper()}{Style.RESET_ALL}  "
        f"score={score:+.2f}  confianza={conf:.0%}",
        f"  Análisis     : {reason}",
        Fore.GREEN + f"{'─'*64}" + Style.RESET_ALL,
    ]

    return "\n".join(lines)


def cmd_news_predict(pair: str, csv_path: str) -> str:
    """Comando: 'noticias predice <par> <csv>' — señal técnica + sentimiento"""
    clean = _clean(pair)

    print(Fore.CYAN + f"[NEWS-PREDICT] Analizando {clean} — técnico + noticias..." + Style.RESET_ALL)

    result = combined_score(pair, csv_path)

    tech     = result.get("technical", {})
    sent     = result.get("sentiment", {})
    action   = result.get("action", "HOLD")
    final_s  = result.get("final_score", 0.0)
    recom    = result.get("recommendation", "")

    ACTION_COLOR = {"BUY": Fore.GREEN, "SELL": Fore.RED, "HOLD": Fore.YELLOW}
    ACTION_ICON  = {"BUY": "▲", "SELL": "▼", "HOLD": "─"}
    color = ACTION_COLOR.get(action, Fore.WHITE)
    icon  = ACTION_ICON.get(action, "─")

    tech_action = tech.get("action", "?")
    tech_conf   = tech.get("confidence", 0)
    tech_adx    = tech.get("adx", 0)
    tech_regime = tech.get("regime", "")
    sent_label  = sent.get("label", "neutral")
    sent_score  = sent.get("score", 0.0)
    sent_reason = sent.get("reasoning", "")

    lines = [
        f"\n{color}{'═'*62}{Style.RESET_ALL}",
        f"  {color}{icon}  ANÁLISIS COMBINADO — {clean}{Style.RESET_ALL}",
        f"{'═'*62}",
        "",
        f"  SEÑAL TÉCNICA   : {tech_action:<5}  conf={tech_conf:.2%}  adx={tech_adx:.1f}  ({tech_regime})",
        f"  SENTIMIENTO     : {sent_label.upper():<8}  score={sent_score:+.2f}  confianza={sent.get('confidence',0):.0%}",
        f"  SCORE COMBINADO : {final_s:+.4f}  (70% técnico + 30% noticias)",
        "",
        f"  {color}DECISIÓN: {action}{Style.RESET_ALL}",
        f"  {recom}",
        "",
        f"  Análisis noticias: {sent_reason}",
        f"\n{color}{'═'*62}{Style.RESET_ALL}",
    ]

    if result.get("news_items"):
        lines.append(f"\n  Noticias ({len(result['news_items'])}):")
        for n in result["news_items"][:4]:
            lines.append(f"    [{n['source']:<12}] {n['title'][:65]}")

    return "\n".join(lines)
