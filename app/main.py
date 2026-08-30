"""Applicazione web: API REST e servizio dell'interfaccia.

L'interfaccia e' una pagina statica servita da qui, installabile come
applicazione grazie al manifest PWA. Nessun passaggio di compilazione: si apre
il browser e funziona.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import Body, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi import Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db, notify, scheduler
from .config import AUTH_PASSWORD, AUTH_USER, CV_DIR, SECRETS, STATIC_DIR
from .matching import CVParseError, build_profile, extract_text, feedback, llm
from .matching.cv_parser import extract_person_name
from .matching.engine import JobView, score_job
from .matching.skills import resolve_skill, skill_catalogue
from .pipeline import pipeline
from .providers import BY_KIND, catalogue, detect_from_url

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("jobseeker")

MAX_CV_BYTES = 10 * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    scheduler.start()
    # Dentro un contenitore l'indirizzo utile e' quello del reverse proxy, non
    # 127.0.0.1: scriverlo qui manderebbe fuori strada chi legge i log.
    log.info("JobSeeker pronto%s", " (accesso protetto da password)" if AUTH_PASSWORD else "")
    try:
        yield
    finally:
        scheduler.stop()


app = FastAPI(title="JobSeeker", version="1.0.0", lifespan=lifespan)


# --------------------------------------------------------------------------
# Modelli di richiesta
# --------------------------------------------------------------------------

class SearchIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    keywords: list[str] = []
    exclude: list[str] = []
    location: str = ""
    country: str = "it"
    remote_ok: bool = True
    location_filter: bool = True
    min_match: int | None = None
    enabled: bool = True


class ProviderIn(BaseModel):
    url: str = ""
    kind: str = ""
    label: str = ""
    config: dict[str, Any] = {}
    min_interval_sec: int | None = None
    enabled: bool = True


class ProviderPatch(BaseModel):
    label: str | None = None
    enabled: bool | None = None
    min_interval_sec: int | None = None
    config: dict[str, Any] | None = None


class ApplicationIn(BaseModel):
    status: str = "saved"
    notes: str = ""
    # Perche' l'offerta e' stata scartata. Ha senso solo per gli stati
    # negativi, ma non viene rifiutato altrove: e' un'annotazione, non un
    # vincolo.
    reasons: list[str] = []


class CVPatch(BaseModel):
    name: str | None = None
    # Elenco unico di etichette: il server separa quelle note dalle libere.
    tags: list[str] | None = None
    languages: list[str] | None = None
    years_experience: float | None = None
    education_level: int | None = Field(default=None, ge=0, le=5)
    education_label: str | None = None
    education_fields: list[str] | None = None


class ManualProfileIn(BaseModel):
    name: str = "Profilo manuale"
    tags: list[str] = []
    languages: list[str] = []
    years_experience: float = 0.0
    education_level: int = Field(default=0, ge=0, le=5)
    education_label: str = ""
    education_fields: list[str] = []


class AnalyzeIn(BaseModel):
    title: str = ""
    description: str
    location: str = ""


VALID_STATUSES = ("saved", "applied", "interview", "offer", "rejected", "discarded")


# --------------------------------------------------------------------------
# Stato generale
# --------------------------------------------------------------------------

@app.get("/api/status")
def get_status() -> dict[str, Any]:
    counts = db.query_one(
        "SELECT (SELECT COUNT(*) FROM job WHERE is_archived = 0) AS jobs,"
        "       (SELECT COUNT(*) FROM provider WHERE enabled = 1) AS providers,"
        "       (SELECT COUNT(*) FROM search WHERE enabled = 1) AS searches,"
        "       (SELECT COUNT(*) FROM application) AS applications,"
        "       (SELECT COUNT(*) FROM cv) AS cvs"
    )
    cv = db.query_one("SELECT id, name, uploaded_at FROM cv WHERE is_active = 1")
    threshold = db.get_setting_int("min_match_notify", 40)
    above = db.query_one(
        "SELECT COUNT(*) AS n FROM match m JOIN job j ON j.id = m.job_id "
        "WHERE m.score >= ? AND j.is_archived = 0", (threshold,)
    )
    # Il pannello raggruppa per offerta, perche' la stessa offerta genera una
    # riga per canale (desktop, email, Telegram). Contare le righe faceva
    # annunciare al badge il doppio o il triplo delle voci poi elencate.
    unseen = db.query_one(
        "SELECT COUNT(DISTINCT n.job_id) AS n FROM notification n "
        "JOIN job j ON j.id = n.job_id WHERE n.seen = 0 AND n.ok = 1")
    return {
        "counts": dict(counts),
        "active_cv": db.row_to_dict(cv),
        "threshold": threshold,
        "above_threshold": above["n"],
        "unseen_notifications": unseen["n"],
        "scheduler": scheduler.status(),
        "last_run": pipeline.last_summary,
        "smtp_configured": notify.is_configured(),
        "email_enabled": db.get_setting_bool("notify_email_enabled"),
    }


@app.post("/api/run")
async def run_now(provider_id: int | None = None) -> dict[str, Any]:
    """Esegue subito un ciclo di controllo, ignorando gli intervalli."""
    ids = [provider_id] if provider_id else None
    return await pipeline.run_cycle(provider_ids=ids, force=True)


@app.post("/api/rescore")
def rescore() -> dict[str, Any]:
    """Ricalcola tutti i punteggi (dopo un cambio di curriculum o di pesi)."""
    pipeline.invalidate()
    if pipeline.active_cv() is None:
        raise HTTPException(400, "nessun curriculum attivo: caricane uno prima di ricalcolare")
    scored = pipeline.score_jobs(force=True)
    return {"rescored": len(scored)}


# --------------------------------------------------------------------------
# Ricerche
# --------------------------------------------------------------------------

@app.get("/api/searches")
def list_searches() -> list[dict[str, Any]]:
    return db.rows_to_dicts(db.query("SELECT * FROM search ORDER BY id"))


@app.post("/api/searches", status_code=201)
def create_search(payload: SearchIn) -> dict[str, Any]:
    cursor = db.execute(
        "INSERT INTO search(name, keywords_json, exclude_json, location, country, remote_ok, "
        "location_filter, min_match, enabled, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (payload.name, json.dumps(payload.keywords), json.dumps(payload.exclude),
         payload.location, payload.country, int(payload.remote_ok), int(payload.location_filter),
         payload.min_match, int(payload.enabled), db.utcnow()),
    )
    return db.row_to_dict(db.query_one("SELECT * FROM search WHERE id = ?", (cursor.lastrowid,)))


@app.put("/api/searches/{search_id}")
def update_search(search_id: int, payload: SearchIn) -> dict[str, Any]:
    if db.query_one("SELECT 1 FROM search WHERE id = ?", (search_id,)) is None:
        raise HTTPException(404, "ricerca non trovata")
    db.execute(
        "UPDATE search SET name=?, keywords_json=?, exclude_json=?, location=?, country=?, "
        "remote_ok=?, location_filter=?, min_match=?, enabled=? WHERE id=?",
        (payload.name, json.dumps(payload.keywords), json.dumps(payload.exclude),
         payload.location, payload.country, int(payload.remote_ok), int(payload.location_filter),
         payload.min_match, int(payload.enabled), search_id),
    )
    return db.row_to_dict(db.query_one("SELECT * FROM search WHERE id = ?", (search_id,)))


@app.delete("/api/searches/{search_id}")
def delete_search(search_id: int) -> dict[str, str]:
    db.execute("DELETE FROM search WHERE id = ?", (search_id,))
    return {"status": "eliminata"}


# --------------------------------------------------------------------------
# Provider
# --------------------------------------------------------------------------

@app.get("/api/providers/catalogue")
def provider_catalogue() -> list[dict[str, Any]]:
    return catalogue()


@app.post("/api/providers/detect")
def detect_provider(url: str = Body(..., embed=True)) -> dict[str, Any]:
    """Anteprima: dice a quale API corrisponde un URL, prima di salvarlo."""
    hit = detect_from_url(url)
    if hit is None:
        supported = ", ".join(sorted({p["label"] for p in catalogue()}))
        return {
            "recognised": False,
            "message": (
                "Questo indirizzo non corrisponde a nessuna API supportata. "
                f"Le fonti riconosciute sono: {supported}. "
                "Se l'azienda pubblica le posizioni su uno di questi sistemi, incolla "
                "l'indirizzo della sua pagina 'lavora con noi'."
            ),
        }
    cls, config = hit
    return {
        "recognised": True,
        "kind": cls.kind,
        "label": cls.suggested_label(config),
        "config": config,
        "description": cls.description,
        "needs_credentials": cls.needs_credentials,
        "default_interval": cls.default_interval,
    }


@app.get("/api/providers")
def list_providers() -> list[dict[str, Any]]:
    rows = db.rows_to_dicts(db.query("SELECT * FROM provider ORDER BY id"))
    for row in rows:
        row["health"] = _provider_health(row)
    return rows


def _provider_health(row: dict[str, Any]) -> dict[str, Any]:
    """Traduce i contatori in un giudizio leggibile sullo stato della fonte."""
    if not row["enabled"]:
        return {"level": "off", "message": "disattivata"}
    if row["consecutive_failures"] >= 3:
        return {"level": "error",
                "message": f"{row['consecutive_failures']} errori consecutivi: {row['last_error'][:120]}"}
    if row["consecutive_failures"] > 0:
        return {"level": "warn", "message": f"ultimo tentativo fallito: {row['last_error'][:120]}"}
    if row["consecutive_empty"] >= 3:
        return {"level": "warn",
                "message": f"nessun risultato da {row['consecutive_empty']} controlli: "
                           "verifica le parole chiave della ricerca o il token della board"}
    if not row["last_run_at"]:
        return {"level": "idle", "message": "mai eseguita"}
    return {"level": "ok", "message": f"ultimo controllo: {row['last_count']} offerte pertinenti"}


@app.post("/api/providers", status_code=201)
def create_provider(payload: ProviderIn) -> dict[str, Any]:
    kind, config, label = payload.kind, dict(payload.config), payload.label

    if payload.url and not kind:
        hit = detect_from_url(payload.url)
        if hit is None:
            raise HTTPException(
                400,
                "Indirizzo non riconosciuto. Incolla il link di una board Greenhouse, Ashby, "
                "SmartRecruiters, Workable o Recruitee, oppure scegli la fonte dall'elenco.",
            )
        cls, detected = hit
        kind = cls.kind
        config = {**detected, **config}
        label = label or cls.suggested_label(config)

    cls = BY_KIND.get(kind)
    if cls is None:
        raise HTTPException(400, f"fonte sconosciuta: {kind}")
    label = label or cls.suggested_label(config)
    interval = payload.min_interval_sec or cls.default_interval

    existing = db.query_one(
        "SELECT id FROM provider WHERE kind = ? AND config_json = ?",
        (kind, json.dumps(config, sort_keys=True)),
    )
    if existing:
        raise HTTPException(409, "questa fonte e' gia' presente")

    cursor = db.execute(
        "INSERT INTO provider(kind, label, source_url, config_json, enabled, min_interval_sec, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (kind, label, payload.url, json.dumps(config, sort_keys=True),
         int(payload.enabled), max(60, interval), db.utcnow()),
    )
    row = db.row_to_dict(db.query_one("SELECT * FROM provider WHERE id = ?", (cursor.lastrowid,)))
    row["health"] = _provider_health(row)
    return row


@app.patch("/api/providers/{provider_id}")
def patch_provider(provider_id: int, payload: ProviderPatch) -> dict[str, Any]:
    row = db.query_one("SELECT * FROM provider WHERE id = ?", (provider_id,))
    if row is None:
        raise HTTPException(404, "fonte non trovata")
    updates, params = [], []
    if payload.label is not None:
        updates.append("label = ?"); params.append(payload.label)
    if payload.enabled is not None:
        updates.append("enabled = ?"); params.append(int(payload.enabled))
        if payload.enabled:
            updates.append("consecutive_failures = 0")
    if payload.min_interval_sec is not None:
        updates.append("min_interval_sec = ?"); params.append(max(60, payload.min_interval_sec))
    if payload.config is not None:
        updates.append("config_json = ?"); params.append(json.dumps(payload.config, sort_keys=True))
    if updates:
        params.append(provider_id)
        db.execute(f"UPDATE provider SET {', '.join(updates)} WHERE id = ?", params)
    updated = db.row_to_dict(db.query_one("SELECT * FROM provider WHERE id = ?", (provider_id,)))
    updated["health"] = _provider_health(updated)
    return updated


@app.delete("/api/providers/{provider_id}")
def delete_provider(provider_id: int) -> dict[str, str]:
    db.execute("DELETE FROM provider WHERE id = ?", (provider_id,))
    return {"status": "eliminata"}


async def _probe(kind: str, config: dict[str, Any]) -> dict[str, Any]:
    """Interroga una fonte senza salvare nulla e riassume cosa restituisce.

    Serve sia per collaudare una fonte gia' configurata sia per provarne una
    nuova prima di aggiungerla, cosi' non si salvano fonti che non funzionano.
    """
    from .providers import ProviderError, build

    specs = pipeline.search_specs()
    headers = {"User-Agent": db.get_setting("user_agent", "JobSeeker/1.0"),
               "Accept": "application/json, */*;q=0.8"}
    async with httpx.AsyncClient(timeout=45, follow_redirects=True, headers=headers) as http:
        try:
            provider = build(kind, config, http)
            provider.detail_budget = 3
            postings = await provider.fetch(specs)
        except ProviderError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}

    relevant, by_location, by_keywords = [], [], []
    for posting in postings:
        if not specs or any(pipeline.matches_search(posting, s) for s in specs):
            relevant.append(posting)
        elif pipeline.rejection_reason(posting, specs) == "sede":
            by_location.append(posting)
        else:
            by_keywords.append(posting)

    # Anche in prova le descrizioni si scaricano solo per i primi risultati
    # pertinenti: serve a mostrare un campione, non a fare un giro completo.
    if relevant:
        async with httpx.AsyncClient(timeout=45, follow_redirects=True, headers=headers) as http2:
            anteprima = build(kind, config, http2)
            anteprima.detail_budget = 3
            try:
                await anteprima.enrich(relevant[:3])
            except Exception:
                pass

    return {
        "ok": True,
        "total": len(postings),
        "relevant": len(relevant),
        "rejected_location": len(by_location),
        "rejected_keywords": len(by_keywords),
        # Esempi di cio' che il filtro sulla sede ha scartato: e' il caso in cui
        # e' piu' facile aver impostato una localita' piu' stretta del voluto.
        "location_examples": [
            {"title": p.title, "location": p.location} for p in by_location[:4]
        ],
        "sample": [
            {"title": p.title, "company": p.company, "location": p.location,
             "url": p.url, "has_description": len(p.description) > 100}
            for p in (relevant or postings)[:5]
        ],
    }


@app.post("/api/providers/{provider_id}/test")
async def test_provider(provider_id: int) -> dict[str, Any]:
    """Collauda una fonte gia' configurata."""
    row = db.query_one("SELECT * FROM provider WHERE id = ?", (provider_id,))
    if row is None:
        raise HTTPException(404, "fonte non trovata")
    return await _probe(row["kind"], json.loads(row["config_json"] or "{}"))


@app.post("/api/providers/workday/discover")
async def discover_workday(name: str = Body(..., embed=True)) -> dict[str, Any]:
    """Trova il portale Workday di un'azienda partendo dal nome.

    Serve quando l'azienda mette davanti a Workday un sito con marchio proprio
    (e' il caso di Thermo Fisher): l'indirizzo Workday non compare da nessuna
    parte, quindi va cercato.
    """
    from .providers.ats import WorkdayProvider

    headers = {"User-Agent": db.get_setting("user_agent", "JobSeeker/1.0"),
               "Accept": "application/json, */*;q=0.8"}
    async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=headers) as http:
        trovati = await WorkdayProvider.discover(name, http)

    trovati.sort(key=lambda t: -(t.get("total") or 0))
    if not trovati:
        return {
            "ok": False,
            "message": (
                f"Nessun portale Workday trovato per «{name}». Controlla il nome "
                "(di solito e' l'azienda tutta minuscola e senza spazi), oppure incolla "
                "direttamente un indirizzo myworkdayjobs.com se lo conosci."
            ),
        }
    return {"ok": True, "results": trovati[:5]}


@app.post("/api/providers/preview")
async def preview_provider(payload: ProviderIn) -> dict[str, Any]:
    """Prova una configurazione prima di salvarla."""
    if payload.kind not in BY_KIND:
        raise HTTPException(400, f"fonte sconosciuta: {payload.kind}")
    config = {k: v for k, v in (payload.config or {}).items() if str(v).strip()}
    missing = [
        f["label"] for f in BY_KIND[payload.kind].config_fields
        if f.get("required") and not config.get(f["name"])
    ]
    if missing:
        return {"ok": False, "error": "campi obbligatori mancanti: " + ", ".join(missing)}
    return await _probe(payload.kind, config)


# --------------------------------------------------------------------------
# Offerte
# --------------------------------------------------------------------------

@app.get("/api/jobs")
def list_jobs(
    min_score: float = Query(0, ge=0, le=100),
    provider_id: int | None = None,
    search_id: int | None = None,
    q: str = "",
    location: str = "",
    status: str = "",
    sort: str = Query("score", pattern="^(score|date|company)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    cv = db.query_one("SELECT id FROM cv WHERE is_active = 1")
    cv_id = cv["id"] if cv else -1

    where = ["j.is_archived = 0"]
    params: list[Any] = [cv_id]
    if min_score > 0:
        where.append("COALESCE(m.score, 0) >= ?"); params.append(min_score)
    if provider_id:
        where.append("j.provider_id = ?"); params.append(provider_id)
    if search_id:
        where.append("m.search_id = ?"); params.append(search_id)
    if q:
        where.append("(j.title LIKE ? OR j.company LIKE ? OR j.description LIKE ?)")
        params.extend([f"%{q}%"] * 3)
    if location:
        # Le fonti scrivono la sede in modi diversi ("Milano", "Milan, Italy",
        # "Lombardy"), quindi si cerca in tutti e tre i campi. Le posizioni da
        # remoto restano incluse: sono disponibili qualunque citta' si cerchi.
        where.append("(j.location LIKE ? OR j.city LIKE ? OR j.region LIKE ? OR j.remote = 1)")
        params.extend([f"%{location}%"] * 3)
    if status:
        if status == "none":
            where.append("a.id IS NULL")
        else:
            where.append("a.status = ?"); params.append(status)

    order = {
        "score": "COALESCE(m.score, 0) DESC, j.first_seen_at DESC",
        "date": "COALESCE(j.posted_at, j.first_seen_at) DESC",
        "company": "j.company COLLATE NOCASE ASC, COALESCE(m.score,0) DESC",
    }[sort]

    base = (
        "FROM job j "
        "LEFT JOIN match m ON m.job_id = j.id AND m.cv_id = ? "
        "LEFT JOIN application a ON a.job_id = j.id "
        "LEFT JOIN provider p ON p.id = j.provider_id "
        f"WHERE {' AND '.join(where)}"
    )
    total = db.query_one(f"SELECT COUNT(*) AS n {base}", params)["n"]
    rows = db.query(
        "SELECT j.*, m.score, m.breakdown_json, m.search_id, a.status AS app_status, "
        f"a.notes AS app_notes, a.reasons_json AS app_reasons, a.applied_at, p.label AS provider_label {base} "
        f"ORDER BY {order} LIMIT ? OFFSET ?",
        params + [limit, offset],
    )
    return {"total": total, "limit": limit, "offset": offset, "items": db.rows_to_dicts(rows)}


@app.get("/api/cities")
def list_cities(limit: int = Query(60, ge=1, le=300)) -> list[dict[str, Any]]:
    """Citta' presenti in archivio, per il completamento automatico del filtro.

    Si usa `city` quando la fonte lo fornisce separato, altrimenti si ripiega
    sul primo pezzo di `location` (le fonti scrivono "Milan, Italy" o
    "Pavia, Lombardy, Italy" a seconda dei casi).
    """
    rows = db.query(
        "SELECT TRIM(CASE WHEN city <> '' THEN city "
        "            ELSE SUBSTR(location, 1, CASE WHEN INSTR(location, ',') > 0 "
        "                                          THEN INSTR(location, ',') - 1 "
        "                                          ELSE LENGTH(location) END) END) AS name, "
        "       COUNT(*) AS n "
        "FROM job WHERE is_archived = 0 AND (city <> '' OR location <> '') "
        "GROUP BY LOWER(name) HAVING name <> '' ORDER BY n DESC, name LIMIT ?",
        (limit,),
    )
    return [{"name": r["name"], "count": r["n"]} for r in rows]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: int) -> dict[str, Any]:
    cv = db.query_one("SELECT id FROM cv WHERE is_active = 1")
    row = db.query_one(
        "SELECT j.*, m.score, m.breakdown_json, a.status AS app_status, a.notes AS app_notes, a.reasons_json AS app_reasons, "
        "a.applied_at, p.label AS provider_label FROM job j "
        "LEFT JOIN match m ON m.job_id = j.id AND m.cv_id = ? "
        "LEFT JOIN application a ON a.job_id = j.id "
        "LEFT JOIN provider p ON p.id = j.provider_id WHERE j.id = ?",
        (cv["id"] if cv else -1, job_id),
    )
    if row is None:
        raise HTTPException(404, "offerta non trovata")
    return db.row_to_dict(row)


# --------------------------------------------------------------------------
# Storico candidature
# --------------------------------------------------------------------------

@app.put("/api/jobs/{job_id}/application")
def set_application(job_id: int, payload: ApplicationIn) -> dict[str, Any]:
    if payload.status not in VALID_STATUSES:
        raise HTTPException(400, f"stato non valido. Ammessi: {', '.join(VALID_STATUSES)}")
    if db.query_one("SELECT 1 FROM job WHERE id = ?", (job_id,)) is None:
        raise HTTPException(404, "offerta non trovata")
    ignoti = [r for r in payload.reasons if r not in feedback.REASONS]
    if ignoti:
        raise HTTPException(400, f"motivo non valido: {', '.join(ignoti)}")
    now = db.utcnow()
    applied_at = now if payload.status == "applied" else None
    db.execute(
        "INSERT INTO application(job_id, status, notes, reasons_json, applied_at, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET "
        "status = excluded.status, notes = excluded.notes, reasons_json = excluded.reasons_json, "
        "updated_at = excluded.updated_at, "
        "applied_at = COALESCE(application.applied_at, excluded.applied_at)",
        (job_id, payload.status, payload.notes, json.dumps(payload.reasons, ensure_ascii=False),
         applied_at, now, now),
    )
    return db.row_to_dict(db.query_one("SELECT * FROM application WHERE job_id = ?", (job_id,)))


class ExcludedTrait(BaseModel):
    key: str
    remove: bool = False


@app.post("/api/feedback/excluded")
def toggle_excluded(payload: ExcludedTrait) -> dict[str, Any]:
    """Toglie (o rimette) un tratto fra quelli imparati dagli scarti.

    Serve quando il conteggio deduce qualcosa che l'utente sa essere falso:
    correggerlo a mano e' piu' onesto che affinare all'infinito l'euristica.
    """
    chiave = payload.key.strip()
    if not chiave:
        raise HTTPException(400, "tratto mancante")
    attuali = [x.strip() for x in db.get_setting("feedback_excluded", "").split(",") if x.strip()]
    if payload.remove:
        attuali = [x for x in attuali if x != chiave]
    elif chiave not in attuali:
        attuali.append(chiave)
    db.set_setting("feedback_excluded", ",".join(attuali))
    return read_feedback()


@app.get("/api/feedback")
def read_feedback() -> dict[str, Any]:
    """Cosa l'applicazione ha imparato dalle offerte gia' giudicate."""
    profilo = pipeline.feedback_profile()
    dati = profilo.to_dict()
    dati["available_reasons"] = [
        {"key": k, "label": v["label"], "component": v["component"]}
        for k, v in feedback.REASONS.items()
    ]
    dati["excluded"] = [x.strip() for x in db.get_setting("feedback_excluded", "").split(",") if x.strip()]
    return dati


@app.delete("/api/jobs/{job_id}/application")
def delete_application(job_id: int) -> dict[str, str]:
    db.execute("DELETE FROM application WHERE job_id = ?", (job_id,))
    return {"status": "rimossa"}


@app.get("/api/applications")
def list_applications(status: str = "") -> dict[str, Any]:
    where = "WHERE a.status = ?" if status else ""
    params = [status] if status else []
    cv = db.query_one("SELECT id FROM cv WHERE is_active = 1")
    rows = db.query(
        "SELECT a.*, j.title, j.company, j.location, j.url, j.remote, m.score, p.label AS provider_label "
        "FROM application a JOIN job j ON j.id = a.job_id "
        "LEFT JOIN match m ON m.job_id = j.id AND m.cv_id = ? "
        "LEFT JOIN provider p ON p.id = j.provider_id "
        f"{where} ORDER BY a.updated_at DESC",
        [cv["id"] if cv else -1] + params,
    )
    counts = {r["status"]: r["n"] for r in db.query(
        "SELECT status, COUNT(*) AS n FROM application GROUP BY status")}
    return {"items": db.rows_to_dicts(rows), "counts": counts}


# --------------------------------------------------------------------------
# Curriculum
# --------------------------------------------------------------------------

@app.get("/api/cv")
def list_cvs() -> list[dict[str, Any]]:
    rows = db.query(
        "SELECT id, name, filename, mime, skills_json, education_json, titles_json, "
        "languages_json, extra_tags_json, manual_tags_json, parse_json, years_experience, "
        "is_active, is_manual, uploaded_at, LENGTH(raw_text) AS text_length "
        "FROM cv ORDER BY uploaded_at DESC"
    )
    return db.rows_to_dicts(rows)


@app.post("/api/cv", status_code=201)
async def upload_cv(file: UploadFile = File(...), name: str = "") -> dict[str, Any]:
    data = await file.read()
    if not data:
        raise HTTPException(400, "il file e' vuoto")
    if len(data) > MAX_CV_BYTES:
        raise HTTPException(400, f"file troppo grande (massimo {MAX_CV_BYTES // 1024 // 1024} MB)")
    filename = file.filename or "curriculum"
    try:
        text = extract_text(data, filename)
    except CVParseError as exc:
        raise HTTPException(400, str(exc)) from exc

    profile = build_profile(text)
    # Seconda lettura, se il livello semantico e' configurato: il dizionario da
    # solo vede quello che gia' conosce, e su un curriculum fuori dal suo ambito
    # riconosce pochissimo. Senza chiave non succede niente e resta la prima.
    note = await pipeline.leggi_curriculum(text, profile)
    stored = profile.to_storage()
    # Il nome della persona letto dal documento e' un'etichetta molto migliore
    # del nome del file, che di solito e' lungo e pieno di date. Se il
    # curriculum non lo rende riconoscibile si ricade sul nome del file.
    etichetta = name.strip() or extract_person_name(text) or filename
    # Copia del file originale, cosi' resta consultabile dall'interfaccia.
    safe_name = "".join(c for c in filename if c.isalnum() or c in "._- ")[:80] or "curriculum"
    target = CV_DIR / f"{int(datetime.now(timezone.utc).timestamp())}_{safe_name}"
    target.write_bytes(data)

    cursor = db.execute(
        "INSERT INTO cv(name, filename, mime, raw_text, skills_json, education_json, titles_json, "
        "languages_json, extra_tags_json, parse_json, years_experience, is_active, uploaded_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (etichetta, target.name, file.content_type, text,
         json.dumps(stored["skills"], ensure_ascii=False),
         json.dumps(stored["education"], ensure_ascii=False),
         json.dumps(stored["titles"], ensure_ascii=False),
         json.dumps(stored["languages"], ensure_ascii=False),
         json.dumps(note.get("extra_tags", []), ensure_ascii=False),
         json.dumps(note, ensure_ascii=False),
         stored["years_experience"], 0, db.utcnow()),
    )
    activate_cv(cursor.lastrowid)
    row = db.row_to_dict(db.query_one(
        "SELECT id, name, filename, skills_json, education_json, titles_json, languages_json, "
        "extra_tags_json, manual_tags_json, parse_json, years_experience, is_active, uploaded_at "
        "FROM cv WHERE id = ?", (cursor.lastrowid,)))
    row["rescored"] = len(pipeline.score_jobs(force=True))
    return row


@app.get("/api/skills")
def skill_catalogue_endpoint() -> list[dict[str, Any]]:
    """Competenze riconosciute dal motore, per il completamento automatico."""
    return skill_catalogue()


@app.post("/api/skills/resolve")
def resolve_skill_endpoint(text: str = Body(..., embed=True)) -> dict[str, Any]:
    """Riconduce un'etichetta scritta a mano al suo nome canonico.

    Serve all'interfaccia per mostrare subito il colore giusto: chi scrive
    "real time pcr" o "spettrometria di massa" in minuscolo deve vedere
    riconosciuta la competenza mentre digita, non dopo aver salvato.
    """
    canonico = resolve_skill(text)
    return {"input": text, "canonical": canonico, "known": canonico is not None}


@app.post("/api/cv/manual", status_code=201)
def create_manual_profile(payload: ManualProfileIn) -> dict[str, Any]:
    """Crea un profilo compilato a mano, senza curriculum.

    Utile per provare subito il sistema, o per chi preferisce dichiarare le
    proprie competenze invece di farle dedurre da un file.
    """
    skills, extra = _split_tags(payload.tags)
    cursor = db.execute(
        "INSERT INTO cv(name, filename, mime, raw_text, skills_json, education_json, "
        "titles_json, languages_json, extra_tags_json, manual_tags_json, years_experience, "
        "is_active, is_manual, uploaded_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (payload.name or "Profilo manuale", "", "", "",
         json.dumps(skills, ensure_ascii=False),
         json.dumps({"level": payload.education_level, "label": payload.education_label,
                     "fields": payload.education_fields}, ensure_ascii=False),
         json.dumps([], ensure_ascii=False),
         json.dumps(payload.languages, ensure_ascii=False),
         json.dumps(extra, ensure_ascii=False),
         json.dumps(skills + extra, ensure_ascii=False),
         payload.years_experience, 0, 1, db.utcnow()),
    )
    activate_cv(cursor.lastrowid)
    pipeline.invalidate()
    return {"id": cursor.lastrowid, "skills": skills, "extra_tags": extra,
            "rescored": len(pipeline.score_jobs(force=True))}


def _etichette_a_mano(riga: Any, adesso: list[str]) -> list[str]:
    """Quali fra le etichette attuali sono state aggiunte a mano.

    Si ricava per differenza: quello che c'e' ora e prima non c'era l'ha scritto
    l'utente. Le etichette tolte escono anche da qui, altrimenti l'elenco
    crescerebbe per sempre con nomi che non esistono piu'.
    """
    def leggi(colonna: str) -> set[str]:
        try:
            return set(json.loads(riga[colonna] or "[]"))
        except (ValueError, TypeError):
            return set()

    precedenti = leggi("skills_json") | leggi("extra_tags_json")
    a_mano = leggi("manual_tags_json") | (set(adesso) - precedenti)
    return [t for t in adesso if t in a_mano]


def _split_tags(tags: list[str]) -> tuple[list[str], list[str]]:
    """Separa le etichette riconosciute dal dizionario da quelle libere."""
    skills: list[str] = []
    extra: list[str] = []
    for tag in tags:
        pulito = (tag or "").strip()
        if not pulito:
            continue
        canonico = resolve_skill(pulito)
        if canonico:
            if canonico not in skills:
                skills.append(canonico)
        elif pulito not in extra:
            extra.append(pulito)
    return skills, extra


@app.patch("/api/cv/{cv_id}")
def update_cv(cv_id: int, payload: CVPatch) -> dict[str, Any]:
    """Modifica un profilo: nome, competenze, studi, anni di esperienza.

    Le competenze arrivano come un unico elenco di etichette; qui vengono
    divise fra quelle riconosciute dal dizionario e quelle libere.
    """
    row = db.query_one("SELECT * FROM cv WHERE id = ?", (cv_id,))
    if row is None:
        raise HTTPException(404, "curriculum non trovato")

    updates, params = [], []
    if payload.name is not None:
        updates.append("name = ?"); params.append(payload.name.strip() or row["name"])
    if payload.tags is not None:
        skills, extra = _split_tags(payload.tags)
        updates.append("skills_json = ?"); params.append(json.dumps(skills, ensure_ascii=False))
        updates.append("extra_tags_json = ?"); params.append(json.dumps(extra, ensure_ascii=False))
        updates.append("manual_tags_json = ?")
        params.append(json.dumps(_etichette_a_mano(row, skills + extra), ensure_ascii=False))
    if payload.years_experience is not None:
        updates.append("years_experience = ?"); params.append(max(0.0, payload.years_experience))
    if payload.languages is not None:
        updates.append("languages_json = ?")
        params.append(json.dumps(payload.languages, ensure_ascii=False))
    if payload.education_level is not None or payload.education_fields is not None:
        corrente = json.loads(row["education_json"] or "{}")
        if payload.education_level is not None:
            corrente["level"] = payload.education_level
            corrente["label"] = payload.education_label or corrente.get("label", "")
        if payload.education_fields is not None:
            corrente["fields"] = payload.education_fields
        updates.append("education_json = ?"); params.append(json.dumps(corrente, ensure_ascii=False))

    if updates:
        params.append(cv_id)
        db.execute(f"UPDATE cv SET {', '.join(updates)} WHERE id = ?", params)
    pipeline.invalidate()

    aggiornato = db.row_to_dict(db.query_one(
        "SELECT id, name, skills_json, education_json, languages_json, extra_tags_json, "
        "manual_tags_json, parse_json, years_experience, is_active, is_manual "
        "FROM cv WHERE id = ?", (cv_id,)))
    # Il ricalcolo serve subito: cambiare le competenze cambia tutti i punteggi.
    aggiornato["rescored"] = len(pipeline.score_jobs(force=True)) if row["is_active"] else 0
    return aggiornato


@app.post("/api/cv/{cv_id}/activate")
def activate_cv(cv_id: int) -> dict[str, Any]:
    if db.query_one("SELECT 1 FROM cv WHERE id = ?", (cv_id,)) is None:
        raise HTTPException(404, "curriculum non trovato")
    db.execute("UPDATE cv SET is_active = CASE WHEN id = ? THEN 1 ELSE 0 END", (cv_id,))
    pipeline.invalidate()
    return {"status": "attivato", "id": cv_id}


def _rimuovi_file_curriculum(filename: str) -> None:
    """Cancella il file di un curriculum, se ce n'e' davvero uno.

    Non solleva mai: la riga nel database e' gia' stata rimossa, e un file
    residuo non deve far fallire l'operazione agli occhi di chi la chiede.
    """
    if not (filename or "").strip():
        return
    percorso = CV_DIR / filename
    try:
        if percorso.is_file():
            percorso.unlink()
    except OSError as exc:
        log.warning("file del curriculum non rimosso (%s): %s", percorso.name, exc)


@app.delete("/api/cv/{cv_id}")
def delete_cv(cv_id: int) -> dict[str, str]:
    row = db.query_one("SELECT filename, is_active FROM cv WHERE id = ?", (cv_id,))
    if row is None:
        raise HTTPException(404, "curriculum non trovato")
    db.execute("DELETE FROM cv WHERE id = ?", (cv_id,))
    # Un profilo compilato a mano non ha un file di partenza, e `filename` e'
    # vuoto. `CV_DIR / ""` non e' un file inesistente: e' la cartella stessa,
    # che `exists()` conferma e `unlink()` rifiuta con IsADirectoryError. La
    # riga era gia' stata cancellata, quindi l'errore lasciava il profilo
    # sparito ma la richiesta in errore, senza riattivare nessun altro
    # curriculum e senza invalidare la cache.
    _rimuovi_file_curriculum(row["filename"])
    if row["is_active"]:
        remaining = db.query_one("SELECT id FROM cv ORDER BY uploaded_at DESC LIMIT 1")
        if remaining:
            db.execute("UPDATE cv SET is_active = 1 WHERE id = ?", (remaining["id"],))
    pipeline.invalidate()
    return {"status": "eliminato"}


@app.get("/api/cv/{cv_id}/file")
def download_cv(cv_id: int) -> FileResponse:
    row = db.query_one("SELECT filename, name FROM cv WHERE id = ?", (cv_id,))
    if row is None:
        raise HTTPException(404, "curriculum non trovato")
    # Stesso motivo di `_rimuovi_file_curriculum`: senza questo controllo un
    # profilo manuale restituirebbe la cartella invece di un file.
    if not (row["filename"] or "").strip():
        raise HTTPException(404, "questo profilo non ha un file: e' stato compilato a mano")
    path = CV_DIR / row["filename"]
    if not path.is_file():
        raise HTTPException(404, "file non piu' presente su disco")
    return FileResponse(path, filename=row["name"])


@app.post("/api/analyze")
def analyze(payload: AnalyzeIn) -> dict[str, Any]:
    """Confronta il curriculum attivo con un annuncio incollato a mano.

    Utile per capire come ragiona il punteggio prima di fidarsene, e per
    valutare un'offerta trovata fuori dall'applicazione.
    """
    cv = pipeline.active_cv()
    if cv is None:
        raise HTTPException(400, "nessun curriculum attivo: caricane uno per usare questa funzione")
    specs = pipeline.search_specs()
    keywords = [k for spec in specs for k in spec.keywords]
    view = JobView(title=payload.title, description=payload.description, location=payload.location)
    result = score_job(
        view, cv, pipeline.idf(),
        keywords=keywords,
        wanted_location=payload.location or (specs[0].location if specs else ""),
    )
    return result.to_dict()


# --------------------------------------------------------------------------
# Notifiche
# --------------------------------------------------------------------------

@app.get("/api/notifications")
def list_notifications(unseen_only: bool = False, limit: int = Query(30, ge=1, le=200)) -> list[dict[str, Any]]:
    where = "WHERE n.ok = 1" + (" AND n.seen = 0" if unseen_only else "")
    cv = db.query_one("SELECT id FROM cv WHERE is_active = 1")
    rows = db.query(
        "SELECT n.*, j.title, j.company, j.url, j.location FROM notification n "
        "JOIN job j ON j.id = n.job_id "
        f"{where} GROUP BY n.job_id ORDER BY n.sent_at DESC LIMIT ?",
        (limit,),
    )
    return db.rows_to_dicts(rows)


@app.delete("/api/notifications")
def clear_notifications() -> dict[str, int]:
    """Svuota lo storico delle notifiche.

    Cancella solo il registro degli avvisi: le offerte e lo storico delle
    candidature non vengono toccati. Serve a ripulire un elenco lungo, non a
    dimenticare le offerte.

    Nota: cancellare un avviso rende l'offerta di nuovo notificabile, perche'
    il controllo anti-ripetizione si basa proprio su queste righe.
    """
    cursor = db.execute("DELETE FROM notification")
    return {"deleted": cursor.rowcount}


@app.delete("/api/notifications/{job_id}")
def clear_notification(job_id: int) -> dict[str, int]:
    """Toglie dall'elenco gli avvisi di una singola offerta.

    Cancella tutte le righe di quell'offerta, non una: l'elenco raggruppa per
    offerta mentre il database tiene una riga per canale (desktop, email,
    Telegram), e cancellarne una sola lascerebbe la voce dov'era, arrivata
    dagli altri canali.

    Come per lo svuotamento totale, l'offerta torna notificabile: il controllo
    anti-ripetizione si basa proprio su queste righe.
    """
    cursor = db.execute("DELETE FROM notification WHERE job_id = ?", (job_id,))
    return {"deleted": cursor.rowcount}


@app.post("/api/notifications/seen")
def mark_seen(ids: list[int] | None = Body(None, embed=True)) -> dict[str, int]:
    if ids:
        placeholders = ",".join("?" * len(ids))
        cursor = db.execute(f"UPDATE notification SET seen = 1 WHERE id IN ({placeholders})", ids)
    else:
        cursor = db.execute("UPDATE notification SET seen = 1 WHERE seen = 0")
    return {"updated": cursor.rowcount}


@app.post("/api/notifications/test-email")
def test_email() -> dict[str, Any]:
    ok, message = notify.send_test_email()
    return {"ok": ok, "message": message}


@app.post("/api/notifications/test-telegram")
def test_telegram() -> dict[str, Any]:
    ok, message = notify.telegram.send_test()
    return {"ok": ok, "message": message}


@app.post("/api/notifications/telegram-chat")
def find_telegram_chat() -> dict[str, Any]:
    """Ricava il numero della chat dagli ultimi messaggi ricevuti dal bot."""
    ok, message = notify.telegram.resolve_chat_id()
    chat_id, _, testo = message.partition("|") if ok else ("", "", message)
    return {"ok": ok, "chat_id": chat_id, "message": testo or message}


# --------------------------------------------------------------------------
# Impostazioni e diagnostica
# --------------------------------------------------------------------------

@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    chosen = db.get_setting("llm_provider", llm.DEFAULT_PROVIDER)
    llm_available, llm_reason = llm.is_available(chosen)
    return {
        "settings": db.all_settings(),
        "smtp": {
            "configured": notify.is_configured(),
            "host": SECRETS.get("smtp_host", ""),
            "from": SECRETS.get("smtp_from") or SECRETS.get("smtp_user", ""),
        },
        "telegram": {
            "configured": notify.telegram.is_configured(),
            "has_token": bool(SECRETS.get("telegram_token")),
            "has_chat": bool(SECRETS.get("telegram_chat_id")),
        },
        "adzuna_configured": bool(SECRETS.get("adzuna_app_id") and SECRETS.get("adzuna_app_key")),
        # Serve all'interfaccia per decidere se ha senso mostrare "Esci":
        # senza password non c'e' nessuna sessione da chiudere.
        "auth": bool(AUTH_PASSWORD),
        "llm": {
            "provider": chosen,
            "available": llm_available,
            # Quante offerte sopra soglia il modello deve ancora leggere: e'
            # l'unico modo di vedere da fuori se sta lavorando.
            "pending": pipeline.in_attesa_di_giudizio(),
            "reason": llm_reason,
            "model": db.get_setting("llm_model", "") or llm.provider_info(chosen)["model"],
            "default_model": llm.provider_info(chosen)["model"],
            "catalogue": llm.catalogue(),
        },
    }


@app.put("/api/settings")
def update_settings(values: dict[str, Any] = Body(...)) -> dict[str, Any]:
    known = set(db.all_settings())
    for key, value in values.items():
        if key in known:
            db.set_setting(key, value)
    if "poll_interval_sec" in values:
        scheduler.reschedule(db.get_setting_int("poll_interval_sec", 180))
    if any(k.startswith("weight_") for k in values):
        pipeline.invalidate()
    return {"settings": db.all_settings()}


@app.get("/api/llm/models")
def llm_models(provider: str = "") -> dict[str, Any]:
    """Modelli disponibili con la chiave configurata, per la pagina Impostazioni."""
    scelto = provider or db.get_setting("llm_provider", llm.DEFAULT_PROVIDER)
    modelli = llm.available_models(scelto)
    return {
        "provider": scelto,
        "models": modelli,
        "default": llm.provider_info(scelto)["model"],
        "current": db.get_setting("llm_model", "") or llm.provider_info(scelto)["model"],
    }


@app.get("/api/diagnostics")
def diagnostics(limit: int = Query(40, ge=1, le=200)) -> dict[str, Any]:
    runs = db.query(
        "SELECT r.*, p.label FROM run_log r LEFT JOIN provider p ON p.id = r.provider_id "
        "ORDER BY r.started_at DESC LIMIT ?", (limit,)
    )
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(timespec="seconds")
    per_provider = db.query(
        "SELECT p.id, p.label, p.kind, p.last_status, p.consecutive_failures, p.consecutive_empty, "
        "COUNT(j.id) AS jobs FROM provider p LEFT JOIN job j ON j.provider_id = p.id "
        "GROUP BY p.id ORDER BY jobs DESC"
    )
    recent_notifications = db.query(
        "SELECT channel, ok, COUNT(*) AS n FROM notification WHERE sent_at >= ? GROUP BY channel, ok",
        (since,),
    )
    return {
        "runs": db.rows_to_dicts(runs),
        "providers": db.rows_to_dicts(per_provider),
        "notifications_7d": db.rows_to_dicts(recent_notifications),
        "scheduler": scheduler.status(),
    }


# --------------------------------------------------------------------------
# Interfaccia
# --------------------------------------------------------------------------

@app.get("/manifest.json", include_in_schema=False)
def manifest() -> FileResponse:
    return FileResponse(STATIC_DIR / "manifest.json", media_type="application/manifest+json")


@app.get("/sw.js", include_in_schema=False)
def service_worker() -> FileResponse:
    # Il service worker deve essere servito dalla radice per controllare
    # l'intero sito, altrimenti il suo ambito resterebbe limitato a /static.
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    """Sonda per Docker: deve restare fuori dall'autenticazione."""
    return {"status": "ok"}


# --------------------------------------------------------------------------
# Accesso
# --------------------------------------------------------------------------
# La sessione sta in un cookie firmato, non in HTTP Basic. Non e' una
# questione estetica: la finestra di Basic la disegna il browser, non si puo'
# uscire se non chiudendo tutto, e chi preme "Annulla" resta su una pagina di
# errore da cui il browser non ripropone piu' le credenziali. Con un service
# worker installato non le ripropone proprio: una risposta che passa da lui
# non fa comparire la finestra di sistema, e l'unico modo di rientrare
# diventava disinstallare l'applicazione.
#
# Nel cookie c'e' solo la scadenza e la sua firma. Non contiene la password,
# non c'e' niente da leggere e niente da riutilizzare altrove.

COOKIE_SESSIONE = "jobseeker_sessione"
DURATA_SESSIONE = 30 * 24 * 3600          # secondi
# Attesa dopo un tentativo sbagliato: rende poco pratico provare password a
# raffica, e a chi la sa costa una frazione di secondo una volta sola.
ATTESA_TENTATIVO_FALLITO = 0.6
# Raggiungibili senza aver fatto l'accesso. Il foglio di stile serve alla
# pagina di login stessa: e' presentazione, non contiene dati.
PERCORSI_LIBERI = frozenset({"/healthz", "/login", "/logout", "/static/style.css"})

_chiave_firma: bytes | None = None


def _chiave() -> bytes:
    """Chiave con cui si firmano i cookie di sessione.

    Il seme casuale vive nel database, cosi' un riavvio non butta fuori chi ha
    gia' fatto l'accesso. La password entra nella chiave di proposito:
    cambiandola, tutte le sessioni aperte smettono di valere.
    """
    global _chiave_firma
    if _chiave_firma is None:
        seme = db.get_setting("session_secret", "")
        if not seme:
            # `INSERT OR IGNORE` e poi rilettura, non una scrittura secca: al
            # primo avvio due richieste in parallelo genererebbero due semi
            # diversi, e chi si tiene quello sovrascritto firmerebbe cookie che
            # gli altri thread rifiutano. Cosi' vince il primo e tutti leggono
            # lo stesso.
            db.execute("INSERT OR IGNORE INTO setting(key, value) VALUES ('session_secret', ?)",
                       (secrets.token_urlsafe(32),))
            seme = db.get_setting("session_secret", "")
        _chiave_firma = hashlib.sha256(f"{seme}:{AUTH_PASSWORD}".encode("utf-8")).digest()
    return _chiave_firma


def _firma(scadenza: int) -> str:
    return hmac.new(_chiave(), str(scadenza).encode("ascii"), hashlib.sha256).hexdigest()


def _sessione_valida(valore: str) -> bool:
    scadenza, _, firma = (valore or "").partition(".")
    if not scadenza.isdigit() or not firma:
        return False
    if int(scadenza) <= int(time.time()):
        return False
    return secrets.compare_digest(firma, _firma(int(scadenza)))


def _credenziali_giuste(utente: str, parola: str) -> bool:
    """Confronto a tempo costante.

    `compare_digest` e non `==` perche' un confronto fra stringhe esce al primo
    carattere diverso, e i tempi di risposta rivelerebbero la password un
    carattere alla volta. Utente vuoto in configurazione significa "qualunque
    utente": conta solo la password.
    """
    utente_ok = secrets.compare_digest(utente, AUTH_USER or utente)
    return utente_ok and secrets.compare_digest(parola, AUTH_PASSWORD)


def _percorso_interno(destinazione: str) -> str:
    """Filtra la destinazione dopo l'accesso.

    Solo percorsi interni: `//altrosito` e' un indirizzo assoluto, e accettarlo
    trasformerebbe la pagina di accesso in un trampolino verso qualunque sito.
    """
    if destinazione.startswith("/") and not destinazione.startswith("//"):
        return destinazione
    return "/"


def _connessione_cifrata(request: Request) -> bool:
    # Dietro il reverse proxy lo schema che conta e' quello dichiarato da lui:
    # verso l'applicazione la connessione e' comunque HTTP.
    return (request.headers.get("x-forwarded-proto", "").split(",")[0].strip() == "https"
            or request.url.scheme == "https")


@app.get("/login", include_in_schema=False)
def login_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "login.html")


@app.post("/login", include_in_schema=False)
async def login(request: Request, utente: str = Form(""), password: str = Form(""),
                destinazione: str = Form("/", alias="next")) -> Response:
    if not AUTH_PASSWORD or not _credenziali_giuste(utente, password):
        await asyncio.sleep(ATTESA_TENTATIVO_FALLITO)
        return RedirectResponse("/login?errore=1", status_code=303)

    scadenza = int(time.time()) + DURATA_SESSIONE
    risposta = RedirectResponse(_percorso_interno(destinazione), status_code=303)
    risposta.set_cookie(
        COOKIE_SESSIONE, f"{scadenza}.{_firma(scadenza)}",
        max_age=DURATA_SESSIONE, httponly=True, samesite="lax", path="/",
        # `secure` solo dove la connessione lo e' davvero: imporlo sempre
        # renderebbe impossibile l'accesso in HTTP sulla rete di casa, perche'
        # il browser scarterebbe il cookie senza dire niente.
        secure=_connessione_cifrata(request),
    )
    return risposta


@app.post("/logout", include_in_schema=False)
def logout() -> Response:
    risposta = RedirectResponse("/login", status_code=303)
    risposta.delete_cookie(COOKIE_SESSIONE, path="/")
    return risposta


@app.middleware("http")
async def richiedi_accesso(request, call_next):
    """Protegge tutto quando c'e' una password.

    Vale anche per i file statici e per il service worker: proteggere le sole
    API lascerebbe comunque leggere l'interfaccia, e non serve a niente.

    Attenzione: il cookie di sessione viaggia in chiaro come qualunque altra
    intestazione. Ha senso solo dietro HTTPS: vedi il Caddyfile allegato.
    """
    if not AUTH_PASSWORD or request.url.path in PERCORSI_LIBERI:
        return await call_next(request)
    if _sessione_valida(request.cookies.get(COOKIE_SESSIONE, "")):
        return await call_next(request)

    # All'interfaccia serve una risposta che il suo codice sappia riconoscere;
    # a chi sta navigando serve la pagina di accesso, con l'indirizzo di
    # partenza in coda per ritrovarsi dov'era.
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": "Accesso richiesto"}, status_code=401)
    partenza = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    return RedirectResponse(f"/login?next={quote(partenza, safe='')}", status_code=303)


@app.middleware("http")
async def no_stale_assets(request, call_next):
    """Obbliga il browser a rivalidare i file dell'interfaccia.

    Senza questo, dopo un aggiornamento il browser continua a servire dalla
    propria cache il vecchio style.css o app.js, e le modifiche sembrano non
    essere state applicate. `no-cache` non impedisce la cache: impone di
    chiedere al server se il file e' cambiato, e con ETag la risposta e' un
    304 vuoto quando non lo e'. Costa nulla e toglie una fonte di confusione.
    """
    response = await call_next(request)
    percorso = request.url.path
    if percorso.startswith("/static/") or percorso in ("/", "/login", "/sw.js", "/manifest.json"):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.exception_handler(HTTPException)
async def http_error(request, exc: HTTPException) -> JSONResponse:
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)
