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

        def _update_d1():
            logger.info("  [D1] Actualizando datasets D1...")
            try:
                results = updater.update_all(bars_fetch=3)
                ok_c = sum(1 for r in results if r.get("ok"))
                logger.info(f"  [D1] {ok_c}/{len(results)} pares actualizados")
            except Exception as e:
                logger.error(f"  [D1] error: {e}")

        def _outcome_eval():
            """Evalúa predicciones pendientes cuando cierra la vela siguiente."""
            try:
                from forex.prediction.outcome_tracker import OutcomeTracker
                from forex.data.data_router import fetch_data
                def _price(pair: str):
                    df = fetch_data(pair, tf="H1", bars=1)
                    if df is not None and len(df) > 0:
                        return float(df["close"].iloc[-1])
                    return None
                tracker = OutcomeTracker()
                n = tracker.auto_evaluate(price_func=_price, max_age_hours=1)
                if n:
                    logger.info(f"  [OUTCOME] {n} predicciones evaluadas")
            except Exception as e:
                logger.warning(f"  [OUTCOME] skip: {e}")

        def _retrain_check():
            """Revisa reentrenamiento adaptativo por par."""
            try:
                from forex.prediction.retrain_manager import RetrainManager
                mgr = RetrainManager()
                for pair in ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"):
                    dec = mgr.check_retrain_needed(pair=pair)
                    if dec.needed:
                        logger.info(f"  [RETRAIN] {pair} → {dec.trigger.value}: {dec.reason}")
            except Exception as e:
                logger.warning(f"  [RETRAIN] skip: {e}")

        # Registrar tareas por timeframe + tareas adaptativas
        scheduler.add_job_seconds("update_h1",     interval_s=3600,  fn=_update_h1)
        scheduler.add_job_seconds("update_h4",     interval_s=14400, fn=_update_h4)
        scheduler.add_job_seconds("update_d1",     interval_s=86400, fn=_update_d1)
        scheduler.add_job_seconds("outcome_eval",  interval_s=1800,  fn=_outcome_eval)
        scheduler.add_job_seconds("retrain_check", interval_s=21600, fn=_retrain_check)

        logger.info("  ✅ Tareas registradas: update_h1/h4/d1 + outcome_eval + retrain_check")
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
