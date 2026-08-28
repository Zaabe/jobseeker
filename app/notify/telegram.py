"""Invio delle notifiche tramite un bot Telegram.

E' il canale piu' pratico per il telefono: arriva anche ad applicazione chiusa,
non richiede un server di posta e la configurazione si esaurisce in due valori.

Come ottenerli:

1. Su Telegram cercare **@BotFather**, inviare `/newbot` e seguire le istruzioni.
   Alla fine BotFather restituisce un token del tipo `123456789:AA...`.
2. Aprire una conversazione con il bot appena creato e scrivergli qualcosa
   (un bot non puo' iniziare una conversazione da solo).
3. Il numero della chat si ricava da solo con `resolve_chat_id()`, che
   l'interfaccia richiama dal pulsante "Trova la chat".
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from ..config import SECRETS

log = logging.getLogger("jobseeker.telegram")

API = "https://api.telegram.org/bot{token}/{method}"
# Telegram rifiuta i messaggi oltre i 4096 caratteri.
MAX_MESSAGE = 4000


class TelegramError(RuntimeError):
    """Configurazione mancante o invio fallito."""


def config() -> dict[str, str]:
    return {
        "token": (SECRETS.get("telegram_token") or "").strip(),
        "chat_id": (SECRETS.get("telegram_chat_id") or "").strip(),
    }


def is_configured() -> bool:
    c = config()
    return bool(c["token"] and c["chat_id"])


def _call(method: str, token: str, **payload: Any) -> dict[str, Any]:
    try:
        response = httpx.post(API.format(token=token, method=method), json=payload, timeout=25)
    except httpx.HTTPError as exc:
        raise TelegramError(f"rete: {exc}") from exc
    try:
        data = response.json()
    except ValueError as exc:
        raise TelegramError(f"risposta non valida da Telegram ({response.status_code})") from exc
    if not data.get("ok"):
        descrizione = data.get("description", "errore sconosciuto")
        if response.status_code == 401:
            raise TelegramError("token del bot non valido: ricontrollalo su @BotFather")
        if "chat not found" in descrizione.lower():
            raise TelegramError(
                "chat non trovata: apri una conversazione con il bot e scrivigli un messaggio, "
                "poi premi «Trova la chat»"
            )
        raise TelegramError(f"Telegram ha rifiutato la richiesta: {descrizione}")
    return data


def resolve_chat_id() -> tuple[bool, str]:
    """Ricava il numero della chat dagli ultimi messaggi ricevuti dal bot.

    Evita all'utente di doverlo cercare a mano: basta che abbia scritto una
    volta al proprio bot.
    """
    token = config()["token"]
    if not token:
        return False, "TELEGRAM_TOKEN non impostato nel file .env"
    try:
        data = _call("getUpdates", token, limit=20)
    except TelegramError as exc:
        return False, str(exc)

    for update in reversed(data.get("result", [])):
        message = update.get("message") or update.get("channel_post") or {}
        chat = message.get("chat") or {}
        if chat.get("id"):
            nome = chat.get("first_name") or chat.get("title") or chat.get("username") or "chat"
            return True, (
                f"{chat['id']}|Trovata la conversazione con {nome}. "
                f"Scrivi {chat['id']} in TELEGRAM_CHAT_ID nel file .env e riavvia."
            )
    return False, (
        "nessun messaggio ricevuto dal bot: aprilo su Telegram, scrivigli qualcosa "
        "(anche solo «ciao») e riprova"
    )


def send_message(text: str) -> None:
    """Invia un messaggio. Solleva TelegramError con un motivo leggibile."""
    c = config()
    if not c["token"]:
        raise TelegramError("TELEGRAM_TOKEN non impostato nel file .env")
    if not c["chat_id"]:
        raise TelegramError("TELEGRAM_CHAT_ID non impostato nel file .env")
    _call(
        "sendMessage", c["token"],
        chat_id=c["chat_id"],
        text=text[:MAX_MESSAGE],
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


# --------------------------------------------------------------------------
# Composizione del messaggio
# --------------------------------------------------------------------------

def _esc(value: Any) -> str:
    return (
        str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def render(items: list[dict[str, Any]], threshold: int) -> str:
    """Compone il messaggio per un gruppo di offerte.

    Telegram accetta poco HTML: grassetto, corsivo e collegamenti. Niente
    tabelle, quindi il formato e' una riga per offerta con il link sul titolo.
    """
    count = len(items)
    testa = (
        f"<b>{count} nuova offerta compatibile</b>" if count == 1
        else f"<b>{count} nuove offerte compatibili</b>"
    )
    righe = [f"{testa}\nSopra la soglia del {threshold}% che hai impostato.\n"]

    for item in items:
        job, score = item["job"], item["score"]
        breakdown = item.get("breakdown") or {}
        sede = job.get("location") or job.get("city") or "sede non indicata"
        if job.get("remote"):
            sede += " · da remoto"
        titolo = _esc(job.get("title"))
        url = job.get("url") or ""
        riga = (
            f"\n<b>{score:.0f}%</b> — "
            + (f'<a href="{_esc(url)}">{titolo}</a>' if url else titolo)
            + f"\n<i>{_esc(job.get('company'))} · {_esc(sede)}</i>"
        )
        trovate = breakdown.get("matched_skills") or []
        mancanti = breakdown.get("missing_skills") or []
        if trovate:
            riga += f"\n✓ {_esc(', '.join(trovate[:5]))}"
        if mancanti:
            riga += f"\n✗ {_esc(', '.join(mancanti[:4]))}"
        righe.append(riga)

    messaggio = "\n".join(righe)
    if len(messaggio) > MAX_MESSAGE:
        messaggio = messaggio[:MAX_MESSAGE - 40].rsplit("\n", 1)[0] + "\n\n<i>…e altre.</i>"
    return messaggio


def send_test() -> tuple[bool, str]:
    """Prova la configurazione con un messaggio di esempio."""
    if not is_configured():
        c = config()
        manca = "TELEGRAM_TOKEN" if not c["token"] else "TELEGRAM_CHAT_ID"
        return False, f"{manca} non impostato nel file .env"
    esempio = [{
        "job": {
            "id": 0, "title": "Ricercatore Junior - Biologia Molecolare",
            "company": "Azienda di esempio", "location": "Milano, Italia",
            "url": "https://example.org/offerta", "remote": 0,
        },
        "score": 78.0,
        "breakdown": {
            "matched_skills": ["PCR", "Colture cellulari", "Western blot"],
            "missing_skills": ["HPLC"],
        },
    }]
    try:
        send_message("🧪 <b>Messaggio di prova da JobSeeker</b>\n\n" + render(esempio, 40))
    except TelegramError as exc:
        return False, str(exc)
    return True, "messaggio di prova inviato su Telegram"
