# Guía de Interpretación de Resultados — ASTRA

> ⚠️ **Aviso**: ASTRA es una herramienta de análisis cuantitativo. Sus señales son **indicativas**, no recomendaciones de inversión. El trading implica riesgo de pérdida. Siempre aplica tu propio criterio.

---

## Reliability Score (0–100)

| Rango | Significado | Acción sugerida |
|-------|-------------|-----------------|
| **85–100** | Confianza muy alta — 7/7 factores favorables | Señal de máxima calidad |
| **70–84** | Confianza alta — mayoría de factores favorables | Señal de buena calidad |
| **55–69** | Confianza media — factores mixtos | Señal débil — extremar precaución |
| **< 55** | Confianza baja | Decision Engine emite HOLD o NO OPERAR |

**7 factores del Reliability Score:**
1. Confianza del modelo ML (XGB+LGBM+RF ensemble)
2. Coherencia Multi-Timeframe (D1+H4+H1 alineados)
3. Régimen de mercado favorable
4. Win rate histórico verificado
5. Calidad del dataset (Quality Gate)
6. Spread relativo (bajo = mejor)
7. Volatilidad ATR (dentro de rango normal)

---

## Opportunity Score (0–100) — Roadmap VI.8

```
OpScore = (reliability_score × 0.35) + (win_rate_pct × 0.30) + (Régimen × 0.20) + (MTF × 0.15)
```

**Campos de entrada para el OpScore (`SignalInput`):**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `pair` | str | Par Forex, e.g. `"EURUSD"` |
| `direction` | str | `"BUY"`, `"SELL"` o `"HOLD"` |
| `reliability_score` | float 0–100 | Score compuesto del ReliabilityScorer (V.8) |
| `win_rate_pct` | float 0–100 | Win rate histórico verificado del modelo |
| `regime` | str | Del RegimeDetector (V.4) |
| `mtf_coherent` | bool | True si D1+H4+H1 están alineados (V.3) |
| `candlestick_confirm` | bool | True si hay patrón de vela confirmatorio (VI.5.D) |
| `data_fresh` | bool | False si los datos tienen >2h de antigüedad |
| `current_price` | float | Precio actual del par |

**El ranking devuelve `top_buy` y `top_sell`** (no `buy`/`sell`) — listas ordenadas de `OpportunityResult`.

**Umbrales para entrar al ranking Top 10:**
- OpScore ≥ **60**
- Reliability ≥ **70**
- Dirección: solo BUY o SELL (no HOLD)

**Bonificaciones:**
- `+10` — Patrón de vela confirmatorio (`candlestick_confirm=True`)
- `+15` — Régimen favorable (`trending_bullish`, `trending_bearish`, `breakout`)

**Penalizaciones:**
- `-10` — Sin coherencia MTF (`mtf_coherent=False`)
- `-15` — Régimen adverso (`high_volatility`, `news_risk`, `ranging_choppy`)
- `-20` — Datos desactualizados (`data_fresh=False`)

---

## Regímenes de mercado

| Régimen | Descripción | Estrategia recomendada |
|---------|-------------|----------------------|
| `trending_bullish` | Tendencia alcista clara — EMAs alineadas | Seguir la tendencia — preferir BUY |
| `trending_bearish` | Tendencia bajista clara | Seguir la tendencia — preferir SELL |
| `ranging` | Mercado lateral — sin dirección clara | Estrategias de reversión |
| `ranging_choppy` | Lateral con mucho ruido | Evitar operar |
| `breakout` | Ruptura de nivel clave reciente | Alta oportunidad — pero verificar dirección |
| `high_volatility` | Volatilidad extrema — posible evento de noticias | Spreads altos — ASTRA emite HOLD |
| `news_risk` | Noticia de alto impacto detectada | NO OPERAR |
| `unknown` | Insuficientes datos para determinar régimen | Precaución |

---

## Señales de Decisión

| Señal | Significado |
|-------|-------------|
| **BUY** ✅ | Todos los filtros favorables — dirección larga |
| **SELL** ✅ | Todos los filtros favorables — dirección corta |
| **HOLD** ⏸️ | Señal ML presente pero algún filtro en contra |
| **NO OPERAR** 🚫 | Régimen adverso o Reliability < 55 — abstenerse |

---

## SL/TP y Position Sizing (Risk Engine V.2)

**Stop Loss** = Calculado como múltiplo del ATR (volatilidad media de las últimas 14 velas)
- BUY: SL = entrada − (ATR × multiplicador)
- SELL: SL = entrada + (ATR × multiplicador)

**Take Profit** = SL × R/R ratio mínimo (1.5 por defecto)
- Un R/R de 2.0 significa: arriesgas 1 para ganar 2

**Position Size** = Calculado con el criterio de Kelly:
```
fracción = (WinRate × R/R − (1 − WinRate)) / R/R
```
Nunca supera el 5% del capital — protección ante rachas negativas.

> Los valores de SL/TP son **analíticos** y se basan en la volatilidad histórica. El precio exacto depende de tu plataforma de trading (spread, slippage, etc.).

---

## Coherencia MTF (V.3)

| Score MTF | Interpretación |
|-----------|----------------|
| **80–100** | D1 + H4 + H1 perfectamente alineados — señal más robusta |
| **60–79** | 2 de 3 timeframes alineados — señal aceptable |
| **< 60** | Timeframes contradictorios — HOLD forzado automáticamente |

---

## Patrones de vela — interpretación

Un patrón de vela **no es una señal por sí solo** — es evidencia adicional:
- Si el patrón **confirma** la señal del modelo ML → OpScore +10 pts
- Si el patrón **contradice** la señal → no penaliza (el modelo pondera más)
- Sin patrón → neutral (ni bono ni penalización)

**Patrones alcistas:** Hammer, Bullish Engulfing, Bullish Harami, Morning Star
**Patrones bajistas:** Shooting Star, Bearish Engulfing, Bearish Harami, Evening Star
**Neutral:** Doji (siempre cautela, independiente de dirección)

---

## ¿Cuándo actuar vs ignorar una señal?

**Actuar (con validación propia):**
- Reliability ≥ 70 **Y** Decisión = BUY o SELL
- OpScore ≥ 70 (señal en el Top 10)
- MTF coherente (score > 75)
- Régimen favorable (trending_* o breakout)
- Patrón de vela confirmatorio

**Ignorar / esperar:**
- Decisión = HOLD o NO OPERAR
- Reliability < 60
- Régimen = high_volatility o news_risk
- MTF score < 60 (timeframes contradictorios)
- OpScore < 60

**Regla de oro:** ASTRA filtra automáticamente las peores señales. Si el sistema dice HOLD, confía en el filtro — no hay apuro.
