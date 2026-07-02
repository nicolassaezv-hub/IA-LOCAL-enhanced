# future_phases_draft/ — NO conectado a main.py

Este código vino en el ZIP de Bolt.new (1 jul 2026). Implementa una versión
completa (pero **no probada ni integrada**) de las Fases 6-9 del roadmap,
más una reescritura paralela de 5.4-5.7:

- `prediction_lab_5.4_to_5.7_bolt_draft/` — Model Planner, Pipeline Generator,
  Validation Engine, Report Generator (Fase 5.4-5.7), + su propia versión de
  5.1-5.3 (`*_bolt_variant.py`) con clases distintas a las nuestras
  (`DatasetAnalysis`/`ColumnProfile` en vez de `DatasetReport`). Como
  `prediction_lab/` real del proyecto ya tiene 5.1-5.3 probados y wireados
  con nuestras propias clases, estos archivos NO se pueden enchufar tal
  cual — habría que adaptarlos a `ProblemSpec`/`DatasetReport` o decidir
  migrar todo el módulo a las clases de Bolt. Pendiente de decisión.
- `evolution/` (Fase 7), `feedback/` (Fase 6), `constitution/` (Fase 8),
  `evolutionary_cycle.py` (Fase 9) — completos en apariencia, con
  docstrings y estructura razonable, pero:
    - Ningún archivo aquí es importado por `main.py` — cero wiring real.
    - No hay evidencia de que se hayan ejecutado ni probado.
    - Se construyeron TODOS de una sola vez, saltándose el orden que pediste
      seguir (F5 completo → F6 → F7 → F8 → F9, un módulo a la vez).

**Recomendación:** no tocar ni conectar nada de esta carpeta todavía. Cuando
lleguemos a Fase 6 en el roadmap, lo revisamos módulo por módulo como venimos
haciendo con Fase 5 — puede servir de punto de partida/inspiración, pero
necesita el mismo nivel de auditoría y testing que le dimos a Fase 5.
