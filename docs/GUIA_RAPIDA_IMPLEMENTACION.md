# ⚡ GUÍA RÁPIDA DE IMPLEMENTACIÓN

> **Guía histórica.** Los outputs y conteos de tests son ejemplos de una etapa
> anterior, no resultados permanentes. Usa las validaciones actuales del repo.

**Tiempo estimado**: 15-30 minutos  
**Complejidad**: Media

---

## 📋 CHECKLIST RÁPIDO

```
□ Backup del proyecto original
□ Copiar 3 archivos corregidos
□ Copiar 2 archivos nuevos
□ Ejecutar verificación
□ Ejecutar tests
□ ✅ Listo
```

---

## 🔧 PASO 1: PREPARACIÓN

### En Windows PowerShell o CMD:

```bash
# Ir a la carpeta del proyecto
cd C:\ruta\a\IA-LOCAL-enhanced

# Crear backup
cp -r . ..\IA-LOCAL-enhanced-BACKUP

# Crear carpeta para archivos descargados
mkdir fixes
# (O descargar los archivos en esta carpeta)
```

---

## 📂 PASO 2: COPIAR ARCHIVOS CORREGIDOS

### Opción A: Manual (Drag & Drop)

```
Descargar estos 5 archivos:

1. creando.py.CORREGIDO
   → Renombrar a: creando.py
   → Pegar en: IA-LOCAL-enhanced/

2. indicators.py.CORREGIDO
   → Renombrar a: indicators.py
   → Pegar en: IA-LOCAL-enhanced/forex/

3. predictor.py.CORREGIDO
   → Renombrar a: predictor.py
   → Pegar en: IA-LOCAL-enhanced/forex/prediction/

4. test_complete_pipeline.py
   → Pegar en: IA-LOCAL-enhanced/

5. setup_windows.py
   → Pegar en: IA-LOCAL-enhanced/
```

### Opción B: PowerShell Script

```powershell
# Reemplazar C:\ruta con la ruta correcta
$dest = "C:\ruta\a\IA-LOCAL-enhanced"
$fix_dir = "C:\ruta\a\fixes"

# Copiar archivos corregidos
cp "$fix_dir\creando.py.CORREGIDO" "$dest\creando.py" -Force
cp "$fix_dir\indicators.py.CORREGIDO" "$dest\forex\indicators.py" -Force
cp "$fix_dir\predictor.py.CORREGIDO" "$dest\forex\prediction\predictor.py" -Force
cp "$fix_dir\test_complete_pipeline.py" "$dest\test_complete_pipeline.py" -Force
cp "$fix_dir\setup_windows.py" "$dest\setup_windows.py" -Force

Write-Host "✅ Archivos copiados exitosamente"
```

---

## ✅ PASO 3: VERIFICACIÓN

### Test de Verificación (5 minutos)

```bash
cd C:\ruta\a\IA-LOCAL-enhanced

# Verificar instalación
python setup_windows.py verify
```

**Output esperado**:
```
✓ Python 3.10.2
✓ pip 22.0.2
  ✓ pandas
  ✓ numpy
  ✓ sklearn
  ✓ xgboost
  ✓ lightgbm
✓ forex/
✓ forex/prediction/
✓ forex/business/
✓ attached_assets/
✓ USD_JPY_H1_YTD_2026_(1)_1781885306995.csv

✅ Setup is complete!
```

### Si hay errores:

```bash
# Instalar dependencias que falten
python setup_windows.py install

# O manualmente:
pip install -r requirements.txt
```

---

## 🧪 PASO 4: EJECUTAR TESTS (15 minutos)

```bash
python test_complete_pipeline.py
```

**Esto probará**:
- ✅ CSV loading
- ✅ Technical analysis
- ✅ ADX calculation
- ✅ Model training
- ✅ Predictions

**Output esperado**:
```
╔════════════════════════════════════════════════════════════╗
║  ASTRA Forex Analytics — Complete Pipeline Test           ║
║  (No MetaTrader5 Required)                                ║
╚════════════════════════════════════════════════════════════╝

TEST 1: CSV Loading ✅
✓ CSV loaded successfully
  • Rows: 3720
  • Columns: 24

TEST 2: Technical Analysis ✅
✓ RSI: OK
✓ MACD: OK
✓ Trend: OK
✓ ADX: OK

TEST 3: ADX Calculation ✅
✓ ADX calculated
  • Mean: 31.15
  • Current: 31.25

TEST 4: Model Training ✅
✓ Model trained successfully
  • Accuracy: 58.3%
  • Precision: 59.1%

TEST 5: Prediction & Signals ✅
✓ Prediction generated
  • Action: BUY
  • Confidence: 68.5%
  • Regime: moderate trend

Result: 5/5 tests passed

🎉 All tests passed!
```

---

## 🎯 PASO 5: PRIMEROS PASOS

### Opción A: Análisis Básico

```bash
python

from forex_analytics import analyze_market_file

# Analizar USD/JPY
report = analyze_market_file(
    "attached_assets/USD_JPY_H1_YTD_2026_(1)_1781885306995.csv",
    "USD/JPY"
)

print(report)
```

### Opción B: Generar Señal

```bash
python

from forex.prediction.integrated_pipeline import ForexIntegratedPipeline

pipeline = ForexIntegratedPipeline()

# Generar predicción
signal = pipeline.predict(
    "attached_assets/USD_JPY_H1_YTD_2026_(1)_1781885306995.csv"
)

print(f"Action: {signal['action']}")
print(f"Confidence: {signal['confidence']:.2%}")
print(f"Regime: {signal['regime']}")
print(f"ADX: {signal['adx']:.2f}")
```

### Opción C: Interface Gráfica

```bash
python main.py

# En el prompt, escribir:
# > analizar forex USD/JPY attached_assets/USD_JPY_H1_YTD_2026_(1)_1781885306995.csv
# > predecir forex attached_assets/USD_JPY_H1_YTD_2026_(1)_1781885306995.csv
```

---

## 🔍 VERIFICACIÓN DE CAMBIOS

### Ver qué se cambió en creando.py:

```bash
# Abrir en editor
code creando.py

# Buscar estas líneas nuevas:
# try/except para MT5
# "HAS_MT5 = True"
# compute_adx import
```

### Ver qué se cambió en indicators.py:

```bash
# Debe tener función compute_adx()
# ~220 líneas agregadas al final

grep -n "def compute_adx" forex\indicators.py
# Debe mostrar número de línea ~222
```

### Ver qué se cambió en predictor.py:

```bash
# Debe calcular ADX si falta
grep -n "if \"ADX_14\" not in df.columns" forex\prediction\predictor.py
# Debe encontrar la línea
```

---

## ⚠️ TROUBLESHOOTING

### Error: "No module named 'MetaTrader5'"

✅ **Esperado y normal** - el código tiene fallback  
**No acción requerida**

### Error: "test_complete_pipeline.py not found"

```bash
# Verificar que está en la carpeta correcta
ls test_complete_pipeline.py

# Si no está, copiar de nuevo desde fixes/
cp fixes/test_complete_pipeline.py .
```

### Error: "ADX calculation failed"

```bash
# Muy raro, pero si pasa:
# Asegurar que csv tiene columnas correctas

import pandas as pd
df = pd.read_csv("attached_assets/USD_JPY_H1_YTD_2026_(1)_1781885306995.csv")
print(df.columns.tolist())

# Debe incluir: high, low, close
```

### Error: "Model training too slow"

✅ Normal - el training toma 1-2 minutos  
**Esperar pacientemente**

```
Training Progress:
████░░░░░░░░░░░░░░░░  25%  (XGBoost)
████████░░░░░░░░░░░░  50%  (LightGBM)
████████████░░░░░░░░  75%  (RandomForest)
██████████████████░░  95%  (Validation)
████████████████████ 100%  (Done!)
```

---

## 📊 VALIDACIÓN VISUAL

### Después de completar, deberías ver:

#### En terminal después de `setup_windows.py verify`:
```
✓ Python 3.9+
✓ pip
✓ Critical packages: pandas, numpy, sklearn, xgboost, lightgbm
✓ Folders: forex/, forex/prediction/, forex/business/, attached_assets/
✓ CSV: USD_JPY_H1_YTD_2026.csv (1.4 MB)
```

#### En terminal después de `test_complete_pipeline.py`:
```
TEST 1: CSV Loading ✅
TEST 2: Technical Analysis ✅
TEST 3: ADX Calculation ✅
TEST 4: Model Training ✅
TEST 5: Prediction & Signals ✅

Result: 5/5 tests passed ✅
```

---

## 🎉 ¡COMPLETADO!

Cuando veas `5/5 tests passed`, has completado exitosamente la implementación de los arreglos.

### Ahora puedes:

1. ✅ Analizar datos de Forex
2. ✅ Generar señales de trading
3. ✅ Entrenar modelos ML
4. ✅ Usar en Windows sin MT5
5. ✅ Correr tests automáticos

### Próximo paso:

Leer `EVALUACION_COMPLETA_IA_LOCAL.md` para entender:
- Qué se evaluó
- Qué se encontró
- Qué falta para producción

---

## 📱 REFERENCIAS RÁPIDAS

### Comandos Importantes

```bash
# Verificar instalación
python setup_windows.py verify

# Instalar dependencias faltantes
python setup_windows.py install

# Ver instrucciones de MetaTrader5
python setup_windows.py mt5

# Ejecutar tests completos
python test_complete_pipeline.py

# Ejecutar interfaz principal
python main.py
```

### Rutas Importantes

```
Proyecto root: C:\...\IA-LOCAL-enhanced\

Archivos corregidos:
  creando.py
  forex/indicators.py
  forex/prediction/predictor.py

Archivos nuevos:
  test_complete_pipeline.py
  setup_windows.py

Datos de ejemplo:
  attached_assets/USD_JPY_H1_YTD_2026_(1)_1781885306995.csv

Documentación:
  EVALUACION_COMPLETA_IA_LOCAL.md
  CORRECCIONES_APLICADAS.md
  00_RESUMEN_FINAL.md
```

---

**Versión**: 1.0 Guía Rápida  
**Tiempo estimado**: 30 minutos  
**Complejidad**: Media  
**Requiere**: Python 3.9+, pip, 4GB RAM
