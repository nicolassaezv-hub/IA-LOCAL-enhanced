# Guía de Creación de CSV — ASTRA

## Estructura de carpetas

```
artifacts/astra/CSVs/
├── H1/          ← Velas de 1 hora
│   ├── EURUSD.csv
│   ├── GBPUSD.csv
│   └── ...
├── H4/          ← Velas de 4 horas
│   ├── EURUSD.csv
│   └── ...
└── D1/          ← Velas diarias
    ├── EURUSD.csv
    └── ...
```

## Columnas requeridas

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `timestamp` | datetime | Fecha y hora de apertura de la vela |
| `open` | float | Precio de apertura |
| `high` | float | Precio máximo |
| `low` | float | Precio mínimo |
| `close` | float | Precio de cierre |
| `volume` | float/int | Volumen (tick_volume es válido) |

**Columnas opcionales** (ASTRA las calcula si faltan):
`RSI_14`, `MACD`, `MACD_signal`, `MACD_hist`, `ATR_14`, `EMA20`, `EMA50`, `EMA200`, `BB_upper`, `BB_lower`, `returns`, `volatility_24h`, `session`, `spread`

## Convención de nombres

El archivo se llama igual que el par: `EURUSD.csv`, `GBPUSD.csv`, `XAUUSD.csv`.

**NO usar** guiones bajos ni barras: ~~EUR_USD.csv~~, ~~EUR/USD.csv~~

## Exportar desde MetaTrader 5 (MT5)

1. Abrir MT5 → ir al gráfico del par que quieres exportar
2. **View → Symbols** → seleccionar el par → **Export**
   - O en el terminal de comandos de MT5: usar **History Center**
3. Seleccionar timeframe: M1, H1, H4, D1 (según la carpeta destino)
4. Seleccionar el rango de fechas (mínimo 2 años para mejor ML)
5. Exportar como CSV
6. El archivo tendrá columnas: `Date`, `Time`, `Open`, `High`, `Low`, `Close`, `Volume`
7. ASTRA normaliza automáticamente estos nombres en la importación

## Alternativa: Descargar automáticamente con ASTRA

```
# En el asistente ASTRA:
descargar datos EURUSD H1 500      ← descarga 500 velas H1 de EURUSD
descargar datos BTCUSDT D1 1000    ← descarga 1000 velas D1 de Bitcoin
descargar datos XAUUSD H4          ← descarga velas H4 de Oro (500 por defecto)
```

Fuentes en orden de prioridad:
1. **MT5** — si está instalado y corriendo en Windows
2. **Yahoo Finance** — fallback automático (requiere `pip install yfinance`)
3. **Binance** — exclusivo para criptomonedas

## Migrar CSV existente al formato rolling

Si ya tienes un CSV de MT5 u otra fuente:

```
migrar csv CSVs/H1/EURUSD_raw.csv EURUSD H1
```

ASTRA normaliza los nombres de columnas, ajusta el tamaño a 2000 filas máximo y registra el par en el índice activo.

## Errores comunes

| Error | Causa | Solución |
|-------|-------|----------|
| `Columnas faltantes: {'timestamp'}` | El CSV tiene `Date` y `Time` separados | ASTRA los combina automáticamente |
| `Valores nulos en: ['close']` | Datos corruptos o fila vacía al final | Revisar el CSV con Excel |
| `No hay modelo entrenado` | Normal — el CSV está OK, solo falta entrenar | Ejecuta `full forex EURUSD.csv` |
| `Pair: EURUSD_test` | El nombre del archivo contiene sufijos | Renombrar a `EURUSD.csv` |

## Sistema Rolling Dataset (VI.6)

Una vez migrado el CSV, ASTRA mantiene el tamaño fijo (2000 filas) automáticamente:
- Al añadir una vela nueva, elimina la más antigua
- Recalcula y valida los indicadores técnicos obligatorios antes del reemplazo atómico
- Actualización automática con `auto update` o mediante el scheduler

```
rolling info EURUSD H1     ← ver estado del dataset rolling de EURUSD/H1
escanear csvs              ← registrar todos los CSVs en el índice
csvs activos               ← ver los pares registrados
```

## Comando: `generar csvs forex`

Genera en lote todos los CSVs Forex que ASTRA necesita.

- **Pares por defecto:** EURUSD GBPUSD USDJPY USDCHF AUDUSD NZDUSD USDCAD EURGBP EURJPY GBPJPY AUDJPY EURAUD XAUUSD XAGUSD
- **Timeframes por defecto:** H1 · H4 · D1
- **Fuente:** YahooProvider (real) con fallback automático a datos sintéticos.
- **Destino:** `CSVs/<TF>/<PAIR>.csv` (crea las carpetas si no existen).

Ejemplos:

```
generar csvs forex
generar csvs forex H1,H4 800
generar csvs forex EURUSD,GBPUSD,XAUUSD H1 300
generar csvs forex sinteticos            # sin descargar, todo sintético
generate forex csvs                       # alias inglés
```

Para usar la fuente real instala `yfinance`:

```
pip install yfinance
```
