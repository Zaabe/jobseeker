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
from collections.abc import Mapping
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
# La protezione si attiva da sola quando c'e' una password, presa dal file .env
# o scelta dall'interfaccia al primo avvio. `REQUIRE_AUTH` dice che senza
# password non si entra: in quel caso, finche' non ne esiste una,
# l'applicazione serve solo la pagina di configurazione (vedi `accesso.py`).
#
# Prima l'avvio falliva con un messaggio. E' sicuro, ma chi riceve
# l'applicazione si trova davanti a un contenitore che muore e a un file di
# testo da compilare al buio: la pagina di configurazione fa lo stesso lavoro
# senza chiedere di aprire niente.
AUTH_USER = os.getenv("JOBSEEKER_USER", "").strip()
AUTH_PASSWORD = os.getenv("JOBSEEKER_PASSWORD", "").strip()
REQUIRE_AUTH = os.getenv("JOBSEEKER_REQUIRE_AUTH", "").strip().lower() in ("1", "true", "yes", "si")


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
    # Il modello viene interpellato su ogni offerta sopra questo punteggio, e il
    # suo giudizio resta scritto nel dettaglio dell'offerta. Sotto la soglia
    # sarebbe spesa inutile: sono annunci gia' fuori bersaglio.
    "llm_min_lexical": "50",
    # Tetto di valutazioni per ciclo. Non e' solo questione di costo: le chiavi
    # gratuite hanno un limite di richieste al minuto, e superarlo fa rispondere
    # errori invece che giudizi. Con la pausa fra una chiamata e l'altra questo
    # tetto occupa poco piu' di un minuto per ciclo.
    "llm_max_per_cycle": "20",
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

# --------------------------------------------------------------------------
# Credenziali e segreti
# --------------------------------------------------------------------------
# Ogni voce ha la sua variabile d'ambiente e, quando serve, un valore
# predefinito. Il nome della variabile resta quello di sempre: chi ha gia' un
# .env non deve toccare niente.
SEGRETI: dict[str, tuple[str, str]] = {
    # chiave interna         variabile d'ambiente     valore predefinito
    "adzuna_app_id":        ("ADZUNA_APP_ID",        ""),
    "adzuna_app_key":       ("ADZUNA_APP_KEY",       ""),
    "smtp_host":            ("SMTP_HOST",            ""),
    "smtp_port":            ("SMTP_PORT",            "587"),
    "smtp_user":            ("SMTP_USER",            ""),
    "smtp_password":        ("SMTP_PASSWORD",        ""),
    "smtp_from":            ("SMTP_FROM",            ""),
    "smtp_use_tls":         ("SMTP_USE_TLS",         "true"),
    "telegram_token":       ("TELEGRAM_TOKEN",       ""),
    "telegram_chat_id":     ("TELEGRAM_CHAT_ID",     ""),
    "anthropic_api_key":    ("ANTHROPIC_API_KEY",    ""),
    "gemini_api_key":       ("GEMINI_API_KEY",       ""),
}

# Nel database le credenziali stanno fra le impostazioni, con questo prefisso.
# Serve anche a tenerle fuori da `all_settings()`, che alimenta la pagina delle
# impostazioni: una chiave API non deve viaggiare insieme al colore del tema.
PREFISSO_SEGRETO = "secret_"

_memoria: dict[str, str] = {}


def dimentica_segreti() -> None:
    """Svuota la copia in memoria: da chiamare dopo aver salvato un segreto."""
    _memoria.clear()


class _Segreti(Mapping):
    """Le credenziali, prima come le ha scritte l'utente e poi come le da' l'ambiente.

    Vince il database perche' e' l'unico posto che si puo' cambiare senza
    rifare il contenitore. L'ambiente resta il ripiego, e continua a funzionare
    da solo per chi ha gia' un .env compilato.

    L'importazione di `db` avviene qui dentro e non in cima al file: `db`
    importa a sua volta questo modulo, e le due cose insieme non starebbero in
    piedi.
    """

    def _salvato(self, chiave: str) -> str:
        if chiave in _memoria:
            return _memoria[chiave]
        try:
            from . import db

            valore = db.get_setting(PREFISSO_SEGRETO + chiave, "")
        except Exception:
            # Database non ancora pronto: si vive con l'ambiente.
            return ""
        _memoria[chiave] = valore
        return valore

    def __getitem__(self, chiave: str) -> str:
        if chiave not in SEGRETI:
            raise KeyError(chiave)
        variabile, predefinito = SEGRETI[chiave]
        return self._salvato(chiave) or os.environ.get(variabile, "") or predefinito

    def __iter__(self):
        return iter(SEGRETI)

    def __len__(self) -> int:
        return len(SEGRETI)


SECRETS = _Segreti()

PORT = int(os.environ.get("JOBSEEKER_PORT", "8000"))
