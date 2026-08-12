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


def run_closed_loop_job(database=None) -> list[dict]:
    """Run canonical H1 maintenance for every configured symbol."""
    from infra.db.database import get_database
    from scheduler.autonomous_scheduler import run_closed_loop_maintenance

    db = database or get_database()
    return [
        {
            "symbol": symbol["symbol_code"],
            **run_closed_loop_maintenance(db, symbol["symbol_code"], "H1"),
        }
        for symbol in db.get_supported_symbols()
    ]


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

        def _update_d1():
            logger.info("  [D1] Actualizando datasets D1...")
            try:
                results = updater.update_all(bars_fetch=3)
                ok_c = sum(1 for r in results if r.get("ok"))
                logger.info(f"  [D1] {ok_c}/{len(results)} pares actualizados")
            except Exception as e:
                logger.error(f"  [D1] error: {e}")

        def _closed_loop_maintenance():
            """Delega outcomes y elegibilidad a la implementación canónica."""
            try:
                results = run_closed_loop_job()
                finalized = sum(
                    int(result.get("outcomes_finalized", 0)) for result in results
                )
                pending = sum(
                    result.get("retrain_run_id") is not None for result in results
                )
                errors = sum(result.get("action") == "error" for result in results)
                logger.info(
                    "  [CLOSED LOOP] outcomes=%s retrain_runs=%s errors=%s",
                    finalized,
                    pending,
                    errors,
                )
            except Exception as e:
                logger.warning(f"  [CLOSED LOOP] skip: {e}")

        # Registrar tareas por timeframe + tareas adaptativas
        scheduler.add_job_seconds("update_h1",     interval_s=3600,  fn=_update_h1)
        scheduler.add_job_seconds("update_h4",     interval_s=14400, fn=_update_h4)
        scheduler.add_job_seconds("update_d1",     interval_s=86400, fn=_update_d1)
        scheduler.add_job_seconds(
            "closed_loop_maintenance", interval_s=1800, fn=_closed_loop_maintenance
        )

        logger.info("  ✅ Tareas registradas: update_h1/h4/d1 + closed_loop_maintenance")
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
