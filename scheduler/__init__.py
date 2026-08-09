"""scheduler — Scheduler de producción (systemd/cron) para VMs Linux.

Ejecuta ciclos H1/H4/D1 sin dependencias externas:
    python scheduler/autonomous_scheduler.py --timeframe H1
"""

__all__ = ["autonomous_scheduler"]
