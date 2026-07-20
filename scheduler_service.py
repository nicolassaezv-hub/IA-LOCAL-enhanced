"""
ASTRA Scheduler Service
Punto de entrada para el scheduler como servicio independiente.
Uso: python scheduler_service.py
Para Oracle Cloud: systemd service unit.
"""
from __future__ import annotations
import sys, os, time, signal, logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("astra.scheduler_service")


def run_service():
    """Inicia el scheduler autónomo + API como servicio."""
    logger.info("═" * 50)
    logger.info("  ASTRA Scheduler Service iniciando...")
    logger.info("═" * 50)

    # Iniciar ASTRA API en background
    try:
        from astra_api import start_api_server, _PORT
        ok = start_api_server(port=_PORT, daemon=True)
        if ok:
            logger.info(f"  ✅ ASTRA API iniciada en puerto {_PORT}")
        else:
            logger.warning("  ⚠️ ASTRA API ya está corriendo o falló")
    except Exception as e:
        logger.warning(f"  ⚠️ ASTRA API no pudo iniciarse: {e}")

    # Iniciar Scheduler con tareas configuradas
    try:
        from forex.scheduler.autonomous_scheduler import get_scheduler
        from forex.scheduler.auto_updater import get_auto_updater

        scheduler = get_scheduler()
        updater   = get_auto_updater()

        def _update_h1():
            logger.info("  [H1] Actualizando datasets H1...")
            results = updater.update_all(bars_fetch=10)
            ok_c = sum(1 for r in results if r.get("ok"))
            logger.info(f"  [H1] {ok_c}/{len(results)} pares actualizados")

        def _update_h4():
            logger.info("  [H4] Actualizando datasets H4...")
            results = updater.update_all(bars_fetch=5)
            ok_c = sum(1 for r in results if r.get("ok"))
            logger.info(f"  [H4] {ok_c}/{len(results)} pares actualizados")

        # Registrar tareas por timeframe
        scheduler.add_job_seconds("update_h1", interval_s=3600,  fn=_update_h1)
        scheduler.add_job_seconds("update_h4", interval_s=14400, fn=_update_h4)

        logger.info("  ✅ Tareas registradas: update_h1 (1h), update_h4 (4h)")
        logger.info("  Iniciando bucle del scheduler...")

        scheduler.start(daemon=False)

    except Exception as e:
        logger.error(f"  ❌ Error iniciando scheduler: {e}")
        raise

    # Bucle principal (el scheduler corre en su propio hilo si daemon=True)
    def _handle_sigterm(*_):
        logger.info("  SIGTERM recibido — deteniendo...")
        try:
            scheduler.stop()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigterm)

    try:
        while True:
            time.sleep(30)
            logger.debug("  [heartbeat] Scheduler activo")
    except SystemExit:
        pass


if __name__ == "__main__":
    run_service()
