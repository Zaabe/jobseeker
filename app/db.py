"""Accesso a SQLite: schema, connessione e helper di query.

Niente ORM: lo schema e' piccolo e stabile, e restare su sqlite3 puro tiene
l'installazione senza dipendenze aggiuntive.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from .config import DB_PATH, DEFAULT_SETTINGS

log = logging.getLogger("jobseeker.db")

_local = threading.local()

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS setting (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Curriculum caricati dall'utente. Se ne puo' tenere piu' d'uno; quello con
-- is_active=1 e' il profilo usato per calcolare i match.
CREATE TABLE IF NOT EXISTS cv (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    filename      TEXT NOT NULL,
    mime          TEXT,
    raw_text      TEXT NOT NULL,
    skills_json   TEXT NOT NULL DEFAULT '[]',
    education_json TEXT NOT NULL DEFAULT '[]',
    titles_json   TEXT NOT NULL DEFAULT '[]',
    languages_json TEXT NOT NULL DEFAULT '[]',
    years_experience REAL NOT NULL DEFAULT 0,
    is_active     INTEGER NOT NULL DEFAULT 0,
    uploaded_at   TEXT NOT NULL
);

-- Ricerche salvate: l'insieme di parole chiave + localita' che definisce
-- il lavoro che si sta cercando.
CREATE TABLE IF NOT EXISTS search (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    keywords_json TEXT NOT NULL DEFAULT '[]',
    exclude_json  TEXT NOT NULL DEFAULT '[]',
    location      TEXT NOT NULL DEFAULT '',
    country       TEXT NOT NULL DEFAULT 'it',
    remote_ok     INTEGER NOT NULL DEFAULT 1,
    min_match     INTEGER,
    enabled       INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL
);

-- Dizionari: liste di parole con un nome, da riusare su piu' ricerche.
-- `kind` dice a cosa serve la lista - 'keywords' o 'exclude' - perche' le due
-- cose non si mescolano: una lista di linguaggi che non si vogliono non ha
-- senso come elenco di cose da cercare.
CREATE TABLE IF NOT EXISTS dictionary (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    kind          TEXT NOT NULL DEFAULT 'exclude',
    words_json    TEXT NOT NULL DEFAULT '[]',
    created_at    TEXT NOT NULL,
    UNIQUE(name, kind)
);

-- Fonti di offerte. `kind` identifica l'adapter, `config_json` i suoi parametri
-- (es. il token della board aziendale).
CREATE TABLE IF NOT EXISTS provider (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    kind          TEXT NOT NULL,
    label         TEXT NOT NULL,
    source_url    TEXT NOT NULL DEFAULT '',
    config_json   TEXT NOT NULL DEFAULT '{}',
    enabled       INTEGER NOT NULL DEFAULT 1,
    min_interval_sec INTEGER NOT NULL DEFAULT 180,
    last_run_at   TEXT,
    last_status   TEXT,
    last_error    TEXT,
    last_count    INTEGER NOT NULL DEFAULT 0,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    consecutive_empty    INTEGER NOT NULL DEFAULT 0,
    total_jobs    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    UNIQUE(kind, source_url, config_json)
);

-- Offerte normalizzate.
CREATE TABLE IF NOT EXISTS job (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id   INTEGER NOT NULL REFERENCES provider(id) ON DELETE CASCADE,
    external_id   TEXT NOT NULL,
    title         TEXT NOT NULL,
    company       TEXT NOT NULL DEFAULT '',
    location      TEXT NOT NULL DEFAULT '',
    city          TEXT NOT NULL DEFAULT '',
    region        TEXT NOT NULL DEFAULT '',
    country       TEXT NOT NULL DEFAULT '',
    remote        INTEGER NOT NULL DEFAULT 0,
    url           TEXT NOT NULL DEFAULT '',
    apply_url     TEXT NOT NULL DEFAULT '',
    description   TEXT NOT NULL DEFAULT '',
    employment_type TEXT NOT NULL DEFAULT '',
    department    TEXT NOT NULL DEFAULT '',
    salary_min    REAL,
    salary_max    REAL,
    currency      TEXT NOT NULL DEFAULT '',
    posted_at     TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at  TEXT NOT NULL,
    is_archived   INTEGER NOT NULL DEFAULT 0,
    raw_json      TEXT NOT NULL DEFAULT '{}',
    UNIQUE(provider_id, external_id)
);
CREATE INDEX IF NOT EXISTS idx_job_seen    ON job(first_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_job_company ON job(company);

-- Punteggio di compatibilita' fra un'offerta e un curriculum.
CREATE TABLE IF NOT EXISTS match (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id        INTEGER NOT NULL REFERENCES job(id) ON DELETE CASCADE,
    cv_id         INTEGER NOT NULL REFERENCES cv(id) ON DELETE CASCADE,
    search_id     INTEGER REFERENCES search(id) ON DELETE SET NULL,
    score         REAL NOT NULL,
    breakdown_json TEXT NOT NULL DEFAULT '{}',
    computed_at   TEXT NOT NULL,
    UNIQUE(job_id, cv_id)
);
CREATE INDEX IF NOT EXISTS idx_match_score ON match(score DESC);
-- La cancellazione di un curriculum propaga su `match`: senza un indice su
-- cv_id ogni cancellazione scandisce l'intera tabella riga per riga, tenendo
-- il lock di scrittura per tutto il tempo.
CREATE INDEX IF NOT EXISTS idx_match_cv ON match(cv_id);

-- Storico candidature: lo stato in cui si trova ogni offerta salvata.
CREATE TABLE IF NOT EXISTS application (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id        INTEGER NOT NULL UNIQUE REFERENCES job(id) ON DELETE CASCADE,
    status        TEXT NOT NULL DEFAULT 'saved',
    notes         TEXT NOT NULL DEFAULT '',
    applied_at    TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_app_status ON application(status);

-- Notifiche inviate (serve anche a non ripetere lo stesso avviso).
CREATE TABLE IF NOT EXISTS notification (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id        INTEGER NOT NULL REFERENCES job(id) ON DELETE CASCADE,
    channel       TEXT NOT NULL,
    score         REAL NOT NULL DEFAULT 0,
    ok            INTEGER NOT NULL DEFAULT 1,
    error         TEXT NOT NULL DEFAULT '',
    seen          INTEGER NOT NULL DEFAULT 0,
    sent_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notif_sent ON notification(sent_at DESC);

-- Diario delle esecuzioni: alimenta la diagnostica "questo provider e' morto".
CREATE TABLE IF NOT EXISTS run_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id   INTEGER REFERENCES provider(id) ON DELETE CASCADE,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    ok            INTEGER NOT NULL DEFAULT 0,
    fetched       INTEGER NOT NULL DEFAULT 0,
    new_jobs      INTEGER NOT NULL DEFAULT 0,
    error         TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_runlog_started ON run_log(started_at DESC);
"""


def utcnow() -> str:
    """Timestamp ISO-8601 in UTC, il formato usato ovunque nel database."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_conn() -> sqlite3.Connection:
    """Connessione per-thread (APScheduler e FastAPI girano su thread diversi)."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        # Esplicito, per non dipendere solo dal `timeout` del costruttore:
        # e' l'attesa che SQLite concede a chi trova il database occupato.
        conn.execute("PRAGMA busy_timeout=30000")
        _local.conn = conn
    return conn


# Colonne aggiunte dopo il primo rilascio. `init_db` le applica a un database
# gia' esistente senza perdere i dati: CREATE TABLE IF NOT EXISTS da solo non
# aggiorna le tabelle create da una versione precedente.
MIGRATIONS: list[tuple[str, str, str]] = [
    ("search", "location_filter", "INTEGER NOT NULL DEFAULT 1"),
    # Etichette aggiunte a mano che non corrispondono a una competenza del
    # dizionario: non partecipano al confronto per competenze, ma arricchiscono
    # il testo del profilo usato per l'affinita' complessiva.
    ("cv", "extra_tags_json", "TEXT NOT NULL DEFAULT '[]'"),
    # Un profilo compilato a mano non ha un file di partenza.
    ("cv", "is_manual", "INTEGER NOT NULL DEFAULT 0"),
    # Perche' un'offerta e' stata scartata: alimenta `matching/feedback.py`.
    ("application", "reasons_json", "TEXT NOT NULL DEFAULT '[]'"),
    # Le etichette aggiunte a mano, distinte da quelle lette dal curriculum:
    # il colore da solo non bastava a dire da dove venisse un'etichetta.
    ("cv", "manual_tags_json", "TEXT NOT NULL DEFAULT '[]'"),
    # Come e' stato letto il curriculum e su cosa le due letture non erano
    # d'accordo. Serve a non far passare per certo un dato che certo non e'.
    ("cv", "parse_json", "TEXT NOT NULL DEFAULT '{}'"),
    # Avviso tolto dall'elenco dall'utente. Prima la X cancellava la riga, e
    # la riga e' anche la memoria di "questa offerta l'ho gia' annunciata":
    # cancellarla rendeva l'offerta di nuovo annunciabile, quindi scartare un
    # avviso lo avrebbe fatto tornare al giro dopo. Ora la riga resta e sparisce
    # solo dall'elenco.
    ("notification", "dismissed", "INTEGER NOT NULL DEFAULT 0"),
    # I due dizionari collegati a una ricerca, uno per tipo. Le parole del
    # dizionario si sommano a quelle scritte nei campi: il campo resta il posto
    # dove si mette qualcosa che vale solo per quella ricerca, il dizionario
    # quello dove sta cio' che vale per tutte.
    ("search", "dict_keywords_id", "INTEGER REFERENCES dictionary(id) ON DELETE SET NULL"),
    ("search", "dict_exclude_id", "INTEGER REFERENCES dictionary(id) ON DELETE SET NULL"),
    # Un foglietto che la fonte si lascia da un giro all'altro. Serve a chi
    # sfoglia un elenco a pagine e deve ricordarsi dov'era arrivato: senza,
    # ogni giro ricomincerebbe dalla prima pagina e il fondo dell'elenco non
    # verrebbe letto mai. Il contenuto lo decide l'adapter, il runner lo
    # trasporta e basta.
    ("provider", "stato_json", "TEXT NOT NULL DEFAULT '{}'"),
]


def _apply_migrations(conn: sqlite3.Connection) -> None:
    for table, column, definition in MIGRATIONS:
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> None:
    conn = get_conn()
    conn.executescript(SCHEMA)
    _apply_migrations(conn)
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute("INSERT OR IGNORE INTO setting(key, value) VALUES (?, ?)", (key, value))
    conn.commit()


# --------------------------------------------------------------------------
# Helper di query
# --------------------------------------------------------------------------

def query(sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    return get_conn().execute(sql, tuple(params)).fetchall()


def query_one(sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
    return get_conn().execute(sql, tuple(params)).fetchone()


# Quante volte riprovare una scrittura respinta perche' il database e'
# occupato, e quanto aspettare fra un tentativo e l'altro.
#
# `timeout` sulla connessione copre gia' l'attesa normale fra due scrittori.
# Questo serve ai casi che quel meccanismo non copre: uno snapshot di lettura
# diventato obsoleto (SQLITE_BUSY_SNAPSHOT, che non si risolve aspettando ma
# solo riprovando), o un blocco esterno momentaneo, per esempio un backup che
# tiene il file. Senza riprovare, un istante di indisponibilita' fa fallire
# l'intero ciclo di controllo e le offerte di quel giro vanno perse.
TENTATIVI_SCRITTURA = 4
ATTESA_FRA_TENTATIVI = 0.4   # secondi, raddoppiati a ogni tentativo


def _e_occupato(exc: sqlite3.OperationalError) -> bool:
    testo = str(exc).lower()
    return "locked" in testo or "busy" in testo


def _scrivi(azione: Callable[[sqlite3.Connection], Any]) -> Any:
    """Esegue una scrittura, riprovando se il database risulta occupato."""
    attesa = ATTESA_FRA_TENTATIVI
    for tentativo in range(1, TENTATIVI_SCRITTURA + 1):
        conn = get_conn()
        try:
            risultato = azione(conn)
            conn.commit()
            return risultato
        except sqlite3.OperationalError as exc:
            if not _e_occupato(exc) or tentativo == TENTATIVI_SCRITTURA:
                raise
            # La transazione va chiusa prima di riprovare: lasciarla aperta
            # terrebbe la connessione ancorata allo snapshot che ha fallito,
            # e ogni tentativo successivo fallirebbe allo stesso modo.
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
            log.warning("database occupato, ritento fra %.1fs (tentativo %d di %d): %s",
                        attesa, tentativo, TENTATIVI_SCRITTURA, exc)
            time.sleep(attesa)
            attesa *= 2
        except Exception:
            # Qualunque altro errore: un vincolo violato (due dizionari con lo
            # stesso nome), un tipo sbagliato, un bug qui dentro. Non si
            # riprova - riproverebbe a sbagliare - ma la transazione va chiusa
            # comunque: lasciarla aperta lascia il lucchetto di scrittura in
            # mano a questa connessione, e da quel momento ogni altra scrittura
            # aspetta il timeout e fallisce. Un nome duplicato bloccava il
            # database fino al riavvio.
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
            raise


def execute(sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
    return _scrivi(lambda conn: conn.execute(sql, tuple(params)))


def executemany(sql: str, seq: Iterable[Iterable[Any]]) -> None:
    righe = [tuple(s) for s in seq]
    _scrivi(lambda conn: conn.executemany(sql, righe))


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    d = dict(row)
    # Espande automaticamente le colonne *_json in strutture Python.
    for key in list(d):
        if key.endswith("_json") and isinstance(d[key], str):
            try:
                d[key[:-5]] = json.loads(d[key])
            except (ValueError, TypeError):
                d[key[:-5]] = None
    return d


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [row_to_dict(r) for r in rows]


# --------------------------------------------------------------------------
# Impostazioni
# --------------------------------------------------------------------------

def get_setting(key: str, default: str | None = None) -> str:
    row = query_one("SELECT value FROM setting WHERE key = ?", (key,))
    if row is not None:
        return row["value"]
    return default if default is not None else DEFAULT_SETTINGS.get(key, "")


def get_setting_int(key: str, default: int = 0) -> int:
    try:
        return int(float(get_setting(key)))
    except (TypeError, ValueError):
        return default


def get_setting_float(key: str, default: float = 0.0) -> float:
    try:
        return float(get_setting(key))
    except (TypeError, ValueError):
        return default


def get_setting_bool(key: str, default: bool = False) -> bool:
    value = get_setting(key).strip().lower()
    if value in ("true", "1", "yes", "on"):
        return True
    if value in ("false", "0", "no", "off"):
        return False
    return default


def set_setting(key: str, value: Any) -> None:
    if isinstance(value, bool):
        value = "true" if value else "false"
    execute(
        "INSERT INTO setting(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )


# Chiavi che non escono mai insieme alle impostazioni: le credenziali, i
# segreti e il seme con cui si firmano i cookie. `all_settings` alimenta la
# pagina delle impostazioni e fa da elenco di cio' che si puo' scrivere da li':
# niente di tutto questo ha motivo di viaggiare fino al browser insieme ai pesi
# del punteggio, ne' di essere modificabile dalla stessa richiesta.
RISERVATE = ("auth_user", "auth_password", "session_secret", "setup_done")


def riservata(chiave: str) -> bool:
    return chiave.startswith("secret_") or chiave in RISERVATE


# L'ordine conta: le chiavi esterne hanno ON DELETE CASCADE, ma cancellare
# prima i figli rende l'operazione prevedibile invece di dipendere dalle
# cascate, e tiene il lock di scrittura per meno tempo su ciascun passaggio.
TABELLE_DATI = ("notification", "application", "match", "job", "run_log",
                "cv", "search", "provider")


def svuota_dati() -> dict[str, int]:
    """Cancella tutto quello che l'applicazione ha raccolto o imparato.

    Non tocca la tabella delle impostazioni: le credenziali, le chiavi dei
    servizi e la password vivono la' dentro, e chi svuota l'archivio non vuole
    rifare la configurazione da capo.
    """
    quante = {}
    for tabella in TABELLE_DATI:
        quante[tabella] = execute(f"DELETE FROM {tabella}").rowcount
    return quante


def azzera_tutto() -> None:
    """Riporta il database allo stato di un'installazione appena creata.

    Anche le impostazioni: credenziali, chiavi, preferenze. Al riavvio
    successivo l'applicazione si ritrova senza il segno di configurazione e
    ripropone la procedura di primo avvio.
    """
    svuota_dati()
    execute("DELETE FROM setting")
    init_db()


def all_settings() -> dict[str, str]:
    return {r["key"]: r["value"] for r in query("SELECT key, value FROM setting")
            if not riservata(r["key"])}
