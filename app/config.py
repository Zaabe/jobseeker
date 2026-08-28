"""Configurazione applicativa.

I valori arrivano da tre fonti, in ordine di precedenza:
  1. tabella `setting` del database (modificabile dall'interfaccia web)
  2. variabili d'ambiente / file .env
  3. default definiti qui sotto

Le credenziali (SMTP, chiavi API) restano preferibilmente nel .env; tutto il
resto è pensato per essere cambiato a caldo dalla pagina Impostazioni.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CV_DIR = DATA_DIR / "cv"
DB_PATH = DATA_DIR / "jobseeker.db"
STATIC_DIR = Path(__file__).resolve().parent / "static"

DATA_DIR.mkdir(exist_ok=True)
CV_DIR.mkdir(exist_ok=True)


def _load_dotenv() -> None:
    """Carica .env senza dipendenze esterne (python-dotenv non è richiesto)."""
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        # Le variabili d'ambiente reali hanno la precedenza sul file.
        os.environ.setdefault(key, value)


_load_dotenv()

# --------------------------------------------------------------------------
# Accesso
# --------------------------------------------------------------------------
# L'applicazione nasce per girare sul portatile di chi la usa, dove non serve
# alcuna autenticazione. Su un server raggiungibile da internet serve eccome:
# senza, chiunque conosca l'indirizzo legge il curriculum, lo storico delle
# candidature e puo' spendere le chiavi API altrui.
#
# La protezione si attiva da sola quando c'e' una password. `REQUIRE_AUTH`
# esiste per il caso peggiore: un contenitore esposto in rete con la password
# dimenticata vuota. In quel caso l'avvio fallisce invece di partire aperto.
AUTH_USER = os.getenv("JOBSEEKER_USER", "").strip()
AUTH_PASSWORD = os.getenv("JOBSEEKER_PASSWORD", "").strip()
REQUIRE_AUTH = os.getenv("JOBSEEKER_REQUIRE_AUTH", "").strip().lower() in ("1", "true", "yes", "si")

if REQUIRE_AUTH and not AUTH_PASSWORD:
    raise SystemExit(
        "JOBSEEKER_REQUIRE_AUTH e' attivo ma JOBSEEKER_PASSWORD e' vuota. "
        "Imposta utente e password nel file .env prima di avviare il contenitore."
    )


# Valori di default per le impostazioni memorizzate su database.
DEFAULT_SETTINGS: dict[str, str] = {
    # Ogni quanto il ciclo di polling controlla i provider (secondi).
    "poll_interval_sec": "180",
    # Soglia di match oltre la quale scatta la notifica (0-100).
    "min_match_notify": "40",
    # Canali di notifica attivi.
    "notify_email_enabled": "false",
    "notify_desktop_enabled": "true",
    "notify_telegram_enabled": "false",
    # Destinatario delle email.
    "notify_email_to": os.environ.get("NOTIFY_EMAIL_TO", ""),
    # Non notificare più di N offerte per ciclo (evita valanghe al primo avvio).
    "notify_max_per_cycle": "10",
    # Intervallo minimo fra due notifiche per la stessa offerta (ore).
    "notify_cooldown_hours": "24",
    # Motore semantico opzionale (richiede una chiave del fornitore scelto).
    "llm_enabled": "false",
    # Quale fornitore usare: "gemini" oppure "claude".
    "llm_provider": "gemini",
    # Modello da usare. Vuoto = quello predefinito del fornitore. Si puo'
    # cambiare senza toccare il codice: i nomi dei modelli cambiano spesso.
    "llm_model": "",
    # Quota del punteggio finale assegnata al giudizio del modello (0-100).
    "llm_weight": "50",
    # Il modello viene interpellato solo sopra questo punteggio lessicale:
    # sulle offerte palesemente fuori bersaglio sarebbe spesa inutile.
    "llm_min_lexical": "30",
    # Tetto di valutazioni semantiche per ciclo, per tenere il costo prevedibile.
    "llm_max_per_cycle": "15",
    # Pesi del punteggio di match (somma consigliata: 100).
    "weight_skills": "40",
    "weight_similarity": "25",
    "weight_title": "15",
    "weight_education": "10",
    "weight_experience": "5",
    "weight_location": "5",
    # Tratti che l'utente ha tolto a mano da quelli imparati sugli scarti,
    # separati da virgola. Un elenco corto e correggibile vale piu' di una
    # euristica che indovina meglio.
    "feedback_excluded": "",
    # Quante offerte conservare per provider prima della pulizia automatica.
    "retention_days": "90",
    # User-Agent usato nelle chiamate alle API.
    "user_agent": "JobSeeker/1.0 (+personal job search tool)",
}

# Credenziali e segreti: solo da ambiente.
SECRETS = {
    "adzuna_app_id": os.environ.get("ADZUNA_APP_ID", ""),
    "adzuna_app_key": os.environ.get("ADZUNA_APP_KEY", ""),
    "smtp_host": os.environ.get("SMTP_HOST", ""),
    "smtp_port": os.environ.get("SMTP_PORT", "587"),
    "smtp_user": os.environ.get("SMTP_USER", ""),
    "smtp_password": os.environ.get("SMTP_PASSWORD", ""),
    "smtp_from": os.environ.get("SMTP_FROM", ""),
    "smtp_use_tls": os.environ.get("SMTP_USE_TLS", "true"),
    "telegram_token": os.environ.get("TELEGRAM_TOKEN", ""),
    "telegram_chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
    "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
    "gemini_api_key": os.environ.get("GEMINI_API_KEY", ""),
}

PORT = int(os.environ.get("JOBSEEKER_PORT", "8000"))
