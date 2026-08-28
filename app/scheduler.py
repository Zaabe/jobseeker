"""Pianificazione del controllo periodico delle offerte.

L'intervallo e' modificabile a caldo dalle impostazioni: cambiandolo si
riprogramma il lavoro senza riavviare l'applicazione.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from . import db
from .pipeline import pipeline

log = logging.getLogger("jobseeker.scheduler")

CYCLE_JOB_ID = "controllo-offerte"
CLEANUP_JOB_ID = "pulizia-archivio"

_scheduler: AsyncIOScheduler | None = None


async def _cycle() -> None:
    try:
        summary = await pipeline.run_cycle()
        if summary["providers_run"]:
            log.info(
                "ciclo completato: %d fonti, %d offerte, %d nuove, %d valutate",
                summary["providers_run"], summary["fetched"],
                summary["new_jobs"], summary["scored"],
            )
    except Exception:
        # Un ciclo fallito non deve fermare la pianificazione dei successivi.
        log.exception("ciclo di controllo fallito")


async def _cleanup() -> None:
    try:
        archived = pipeline.cleanup()
        if archived:
            log.info("archiviate %d offerte non piu' presenti nelle fonti", archived)
    except Exception:
        log.exception("pulizia dell'archivio fallita")


def start() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    interval = max(60, db.get_setting_int("poll_interval_sec", 180))
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        _cycle, IntervalTrigger(seconds=interval), id=CYCLE_JOB_ID,
        max_instances=1, coalesce=True, misfire_grace_time=120,
    )
    _scheduler.add_job(
        _cleanup, IntervalTrigger(hours=12), id=CLEANUP_JOB_ID,
        max_instances=1, coalesce=True,
    )
    _scheduler.start()
    log.info("scheduler avviato, controllo ogni %d secondi", interval)
    return _scheduler


def stop() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def reschedule(interval_sec: int) -> None:
    """Applica un nuovo intervallo di controllo senza riavviare."""
    if _scheduler is None:
        return
    interval = max(60, interval_sec)
    _scheduler.reschedule_job(CYCLE_JOB_ID, trigger=IntervalTrigger(seconds=interval))
    log.info("intervallo di controllo aggiornato a %d secondi", interval)


def status() -> dict[str, object]:
    if _scheduler is None:
        return {"running": False, "next_run": None, "interval_sec": None}
    job = _scheduler.get_job(CYCLE_JOB_ID)
    return {
        "running": _scheduler.running,
        "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
        "interval_sec": db.get_setting_int("poll_interval_sec", 180),
    }
