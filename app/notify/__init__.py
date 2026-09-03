"""Decide quali offerte meritano un avviso e su quali canali mandarlo."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from .. import db
from . import telegram
from .mailer import MailError, is_configured, render_digest, send_email

log = logging.getLogger("jobseeker.notify")


def _already_notified(job_id: int, channel: str, cooldown_hours: int) -> bool:
    """Evita di riproporre la stessa offerta a ogni ciclo di controllo."""
    if cooldown_hours <= 0:
        limit = "1970-01-01T00:00:00+00:00"
    else:
        limit = (datetime.now(timezone.utc) - timedelta(hours=cooldown_hours)).isoformat(timespec="seconds")
    row = db.query_one(
        "SELECT 1 FROM notification WHERE job_id = ? AND channel = ? AND ok = 1 AND sent_at >= ? LIMIT 1",
        (job_id, channel, limit),
    )
    return row is not None


def _record(job_id: int, channel: str, score: float, ok: bool, error: str = "") -> None:
    db.execute(
        "INSERT INTO notification(job_id, channel, score, ok, error, sent_at) VALUES (?, ?, ?, ?, ?, ?)",
        (job_id, channel, score, 1 if ok else 0, error[:400], db.utcnow()),
    )


def dispatch(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Notifica le offerte che superano la soglia.

    `candidates` contiene dizionari con le chiavi `job`, `score` e `breakdown`.
    Restituisce un riepilogo di cosa e' stato inviato, usato dal registro
    esecuzioni e dalla diagnostica dell'interfaccia.
    """
    threshold = db.get_setting_int("min_match_notify", 40)
    cooldown = db.get_setting_int("notify_cooldown_hours", 24)
    cap = max(1, db.get_setting_int("notify_max_per_cycle", 10))
    email_on = db.get_setting_bool("notify_email_enabled", False)
    desktop_on = db.get_setting_bool("notify_desktop_enabled", True)

    # Ogni ricerca puo' avere la sua soglia. Chi prepara i candidati l'ha gia'
    # calcolata - dipende da quali ricerche prendono quell'offerta, e quello lo
    # sa la pipeline - e la scrive in `soglia`.
    #
    # Il ripiego su `search_id` resta per chi chiama questa funzione senza,
    # e vale la soglia della ricerca a cui l'offerta e' attribuita.
    per_ricerca = {
        r["id"]: r["min_match"]
        for r in db.query("SELECT id, min_match FROM search WHERE min_match IS NOT NULL")
    }

    def soglia(candidato: dict[str, Any]) -> int:
        propria = candidato.get("soglia")
        if propria is None:
            propria = per_ricerca.get(candidato.get("search_id"))
        return threshold if propria is None else int(propria)

    eligible = sorted(
        (c for c in candidates if c["score"] >= soglia(c)),
        key=lambda c: c["score"],
        reverse=True,
    )
    summary: dict[str, Any] = {
        "threshold": threshold,
        "eligible": len(eligible),
        "email_sent": 0,
        "telegram_sent": 0,
        "desktop_queued": 0,
        "skipped_duplicates": 0,
        # Un canale che fallisce non deve impedire agli altri di funzionare:
        # gli errori si accumulano invece di sovrascriversi.
        "errors": [],
    }
    if not eligible:
        return summary

    # Canale in-app: alimenta il campanello dell'interfaccia e la notifica di
    # sistema del browser. Non ha costi, quindi lo si registra sempre per primo.
    if desktop_on:
        for candidate in eligible[:cap]:
            job_id = candidate["job"]["id"]
            if _already_notified(job_id, "desktop", cooldown):
                summary["skipped_duplicates"] += 1
                continue
            _record(job_id, "desktop", candidate["score"], ok=True)
            summary["desktop_queued"] += 1

    # -- Telegram ----------------------------------------------------------
    if db.get_setting_bool("notify_telegram_enabled", False):
        if not telegram.is_configured():
            summary["errors"].append(
                "notifiche Telegram attive ma token o chat non configurati nel file .env"
            )
        else:
            to_send = [
                c for c in eligible
                if not _already_notified(c["job"]["id"], "telegram", cooldown)
            ][:cap]
            if to_send:
                try:
                    telegram.send_message(telegram.render(to_send, threshold))
                except telegram.TelegramError as exc:
                    summary["errors"].append(f"Telegram: {exc}")
                    log.error("invio Telegram fallito: %s", exc)
                    for candidate in to_send:
                        _record(candidate["job"]["id"], "telegram", candidate["score"],
                                ok=False, error=str(exc))
                else:
                    for candidate in to_send:
                        _record(candidate["job"]["id"], "telegram", candidate["score"], ok=True)
                    summary["telegram_sent"] = len(to_send)
                    log.info("inviato messaggio Telegram con %d offerte", len(to_send))

    # -- Email -------------------------------------------------------------
    if not email_on:
        return summary
    if not is_configured():
        summary["errors"].append("notifiche email attive ma SMTP non configurato nel file .env")
        log.warning(summary["errors"][-1])
        return summary

    to_send = [c for c in eligible if not _already_notified(c["job"]["id"], "email", cooldown)][:cap]
    if not to_send:
        return summary

    recipient = db.get_setting("notify_email_to").strip()
    subject, html, text = render_digest(to_send, threshold)
    try:
        send_email(recipient, subject, html, text)
    except MailError as exc:
        summary["errors"].append(f"Email: {exc}")
        log.error("invio email fallito: %s", exc)
        for candidate in to_send:
            _record(candidate["job"]["id"], "email", candidate["score"], ok=False, error=str(exc))
        return summary

    for candidate in to_send:
        _record(candidate["job"]["id"], "email", candidate["score"], ok=True)
    summary["email_sent"] = len(to_send)
    log.info("inviata email con %d offerte a %s", len(to_send), recipient)
    return summary


def send_test_email() -> tuple[bool, str]:
    """Prova la configurazione SMTP con un messaggio di esempio."""
    recipient = db.get_setting("notify_email_to").strip()
    if not recipient:
        return False, "nessun destinatario impostato nelle impostazioni"
    if not is_configured():
        return False, "SMTP non configurato: compila SMTP_HOST e SMTP_FROM nel file .env"

    example = [{
        "job": {
            "id": 0,
            "title": "Ricercatore Junior - Biologia Molecolare",
            "company": "Azienda di esempio",
            "location": "Milano, Italia",
            "url": "https://example.org/offerta",
            "remote": 0,
            "salary_min": 28000,
            "salary_max": 34000,
            "currency": "EUR",
        },
        "score": 78.0,
        "breakdown": {
            "matched_skills": ["PCR", "Colture cellulari", "Western blot"],
            "missing_skills": ["HPLC"],
        },
    }]
    subject, html, text = render_digest(example, db.get_setting_int("min_match_notify", 40))
    try:
        send_email(recipient, "[Prova] " + subject, html, text)
    except MailError as exc:
        return False, str(exc)
    return True, f"email di prova inviata a {recipient}"


__all__ = ["dispatch", "send_test_email", "is_configured", "MailError", "telegram"]
