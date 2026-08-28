"""Orchestrazione: interroga le fonti, archivia le offerte, calcola i punteggi
e decide le notifiche.

E' il cuore operativo dell'applicazione. Viene chiamato sia dallo scheduler,
a intervalli regolari, sia a mano dall'interfaccia con il pulsante "Controlla ora".
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

import httpx

from . import db, notify
from .matching import CVProfile, IdfIndex, JobView, llm, score_job
from .matching import feedback as fb
from .matching.cv_parser import CVProfile as Profile
from .matching.text import is_country_query, job_in_country, normalize, place_matches
from .providers import ProviderError, SearchSpec, build

log = logging.getLogger("jobseeker.pipeline")

# Oltre questo numero di errori consecutivi l'attesa fra due tentativi non
# cresce piu': serve a non allontanare all'infinito un provider temporaneamente
# irraggiungibile.
MAX_BACKOFF_STEPS = 5


class Pipeline:
    """Stato condiviso fra le esecuzioni: indice IDF e profilo del curriculum."""

    def __init__(self) -> None:
        self._idf: IdfIndex | None = None
        self._idf_docs = 0
        self._cv_id: int | None = None
        self._cv_profile: CVProfile | None = None
        self._feedback: fb.FeedbackProfile | None = None
        self._feedback_key: tuple[int, str] | None = None
        self._lock = asyncio.Lock()
        self.last_summary: dict[str, Any] = {}
        # Ultimo problema del livello semantico, riportato nel riepilogo del
        # ciclo: senza, un modello che non risponde fallisce senza dirlo.
        self.last_llm_error: str = ""

    # -- risorse derivate --------------------------------------------------

    def idf(self, force: bool = False) -> IdfIndex:
        """Indice IDF costruito sugli annunci raccolti finora.

        Viene ricostruito quando l'archivio e' cresciuto in modo sensibile:
        rifarlo a ogni punteggio sarebbe sprecato, non rifarlo mai lo
        renderebbe via via meno rappresentativo.
        """
        total = db.query_one("SELECT COUNT(*) AS n FROM job")["n"]
        stale = self._idf is None or force or total > self._idf_docs * 1.25 + 20
        if stale:
            rows = db.query(
                "SELECT title, description FROM job ORDER BY first_seen_at DESC LIMIT 4000"
            )
            self._idf = IdfIndex(f"{r['title']}\n{r['description']}" for r in rows)
            self._idf_docs = total
            log.debug("indice IDF ricostruito su %d annunci", self._idf.doc_count)
        return self._idf  # type: ignore[return-value]

    def feedback_profile(self, force: bool = False) -> fb.FeedbackProfile:
        """Cosa si e' imparato dalle offerte gia' scartate o tenute.

        Ricostruito solo quando cambia il numero di giudizi: e' una lettura di
        tutta la tabella, non va rifatta a ogni punteggio.
        """
        firma = db.query_one(
            "SELECT COUNT(*) AS n, COALESCE(MAX(updated_at), '') AS t FROM application")
        esclusi = db.get_setting("feedback_excluded", "")
        chiave = (firma["n"], firma["t"], esclusi, self._cv_id or 0)
        if not force and self._feedback is not None and self._feedback_key == chiave:
            return self._feedback

        righe = db.query(
            "SELECT a.status, a.notes, a.reasons_json, j.title, j.company, j.description "
            "FROM application a JOIN job j ON j.id = a.job_id"
        )
        scarti, tenute = [], []
        for r in righe:
            voce = {"title": r["title"] or "", "company": r["company"] or "",
                    "text": r["description"] or ""}
            if r["status"] in fb.NEGATIVE_STATUSES:
                voce["notes"] = r["notes"] or ""
                try:
                    voce["reasons"] = json.loads(r["reasons_json"] or "[]")
                except (ValueError, TypeError):
                    voce["reasons"] = []
                scarti.append(voce)
            elif r["status"] in fb.POSITIVE_STATUSES:
                tenute.append(voce)

        # Cio' che si cerca e cio' che si sa fare non puo' diventare un motivo
        # di scarto: e' scritto a mano, e batte qualunque deduzione su una
        # dozzina di esempi.
        cv = self.active_cv()
        parole = [k for r in db.query("SELECT keywords_json FROM search WHERE enabled = 1")
                  for k in json.loads(r["keywords_json"] or "[]")]
        protetti = fb.protected_traits(
            skills=cv.skills if cv else (),
            roles=cv.roles if cv else (),
            fields=cv.education_fields if cv else (),
            keywords=parole,
        )
        self._feedback = fb.build_profile(
            scarti, tenute, protetti,
            [x.strip() for x in esclusi.split(",") if x.strip()])
        self._feedback_key = chiave
        return self._feedback

    def active_cv(self, force: bool = False) -> CVProfile | None:
        """Profilo del curriculum attivo, tenuto in memoria fra le esecuzioni."""
        row = db.query_one("SELECT * FROM cv WHERE is_active = 1 ORDER BY uploaded_at DESC LIMIT 1")
        if row is None:
            self._cv_id, self._cv_profile = None, None
            return None
        if force or self._cv_profile is None or self._cv_id != row["id"]:
            education = json.loads(row["education_json"] or "{}")
            extra = json.loads(row["extra_tags_json"] or "[]")
            # Le etichette libere non stanno nel dizionario delle competenze,
            # quindi non possono partecipare al confronto per competenze. Vengono
            # pero' aggiunte al testo del profilo, cosi' contribuiscono
            # all'affinita' complessiva: chi scrive "spettroscopia Raman" vede
            # comunque salire le offerte che ne parlano.
            self._cv_profile = Profile(
                raw_text="\n".join(filter(None, [row["raw_text"], " ".join(extra)])),
                skills=json.loads(row["skills_json"] or "[]"),
                education_fields=education.get("fields", []),
                education_level=education.get("level", 0),
                education_label=education.get("label", ""),
                languages=json.loads(row["languages_json"] or "[]"),
                roles=json.loads(row["titles_json"] or "[]"),
                years_experience=row["years_experience"],
            )
            self._cv_id = row["id"]
        return self._cv_profile

    def invalidate(self) -> None:
        """Da chiamare quando cambiano curriculum, pesi o impostazioni."""
        self._cv_profile = None
        self._cv_id = None
        self._idf = None

    # -- criteri di ricerca ------------------------------------------------

    @staticmethod
    def search_specs(only_enabled: bool = True) -> list[SearchSpec]:
        sql = "SELECT * FROM search"
        if only_enabled:
            sql += " WHERE enabled = 1"
        return [
            SearchSpec(
                id=r["id"],
                name=r["name"],
                keywords=json.loads(r["keywords_json"] or "[]"),
                exclude=json.loads(r["exclude_json"] or "[]"),
                location=r["location"],
                country=r["country"],
                remote_ok=bool(r["remote_ok"]),
                location_filter=bool(r["location_filter"]),
            )
            for r in db.query(sql + " ORDER BY id")
        ]

    @staticmethod
    def rejection_reason(posting: Any, specs: list[SearchSpec]) -> str:
        """Perche' un'offerta non rientra in nessuna ricerca.

        Serve alla diagnostica: senza questa distinzione un provider che
        restituisce centinaia di offerte tutte scartate sembra rotto, mentre
        di solito e' solo un filtro impostato in modo piu' stretto del previsto.
        """
        if not specs:
            return ""
        haystack = normalize(posting.searchable_text())
        for spec in specs:
            if spec.exclude and any(normalize(t) in haystack for t in spec.exclude if t):
                continue
            if spec.keywords and not any(normalize(t) in haystack for t in spec.keywords if t):
                continue
            # Le parole chiave passano: se l'offerta e' comunque fuori, e' la sede.
            return "sede"
        return "parole chiave"

    @staticmethod
    def matches_search(posting: Any, spec: SearchSpec) -> bool:
        """Verifica se un'offerta rientra in una ricerca salvata.

        Il filtro sulle parole chiave e' necessario perche' le board aziendali
        restituiscono tutte le posizioni dell'azienda, non solo quelle attinenti.
        """
        haystack = normalize(posting.searchable_text())
        if spec.exclude and any(normalize(term) in haystack for term in spec.exclude if term):
            return False
        if spec.keywords:
            if not any(normalize(term) in haystack for term in spec.keywords if term):
                return False
        if spec.location_filter and spec.location:
            if posting.remote and spec.remote_ok:
                return True
            place = " ".join(p for p in (posting.location, posting.city, posting.region,
                                         posting.country) if p)
            # Cercare "Italia" e' una ricerca sull'intero paese, e va risolta sul
            # campo paese dell'offerta: molte fonti scrivono la sede come
            # "Roma, Provincia di Roma" senza mai nominare l'Italia, e un
            # confronto puramente testuale le scarterebbe tutte.
            if is_country_query(spec.location, spec.country):
                if job_in_country(posting.country, spec.country):
                    return True
                return not place or place_matches(spec.location, place)
            # Altrimenti si confronta il testo, con le varianti linguistiche:
            # le fonti scrivono "Milan, Italy", la ricerca dice "Milano".
            if place and not place_matches(spec.location, place):
                return False
        return True

    # -- archiviazione -----------------------------------------------------

    @staticmethod
    def store(provider_id: int, postings: Iterable[Any]) -> tuple[list[int], int]:
        """Salva le offerte nuove e aggiorna quelle gia' viste.

        Restituisce gli id delle offerte inserite per la prima volta e il
        numero totale di righe toccate.
        """
        now = db.utcnow()
        new_ids: list[int] = []
        touched = 0
        for posting in postings:
            touched += 1
            existing = db.query_one(
                "SELECT id FROM job WHERE provider_id = ? AND external_id = ?",
                (provider_id, posting.external_id),
            )
            if existing:
                db.execute(
                    "UPDATE job SET last_seen_at = ?, title = ?, location = ?, "
                    "description = CASE WHEN ? <> '' THEN ? ELSE description END, "
                    "url = CASE WHEN ? <> '' THEN ? ELSE url END, is_archived = 0 WHERE id = ?",
                    (now, posting.title, posting.location, posting.description, posting.description,
                     posting.url, posting.url, existing["id"]),
                )
                continue
            cursor = db.execute(
                """INSERT INTO job(provider_id, external_id, title, company, location, city, region,
                                   country, remote, url, apply_url, description, employment_type,
                                   department, salary_min, salary_max, currency, posted_at,
                                   first_seen_at, last_seen_at, raw_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    provider_id, posting.external_id, posting.title, posting.company,
                    posting.location, posting.city, posting.region, posting.country,
                    1 if posting.remote else 0, posting.url, posting.apply_url,
                    posting.description, posting.employment_type, posting.department,
                    posting.salary_min, posting.salary_max, posting.currency,
                    posting.posted_at, now, now, json.dumps(posting.raw, ensure_ascii=False)[:60000],
                ),
            )
            new_ids.append(cursor.lastrowid)
        return new_ids, touched

    # -- punteggi ----------------------------------------------------------

    def score_jobs(self, job_ids: list[int] | None = None, force: bool = False) -> list[dict[str, Any]]:
        """Calcola i punteggi per le offerte indicate (o per quelle non ancora valutate).

        Ogni offerta viene confrontata con tutte le ricerche attive e conserva
        il punteggio migliore, insieme alla ricerca che lo ha prodotto.
        """
        cv = self.active_cv()
        if cv is None:
            return []
        cv_id = self._cv_id
        idf = self.idf()
        profilo = self.feedback_profile()
        specs = self.search_specs() or [SearchSpec(name="tutte le offerte")]

        if job_ids is not None:
            if not job_ids:
                return []
            placeholders = ",".join("?" * len(job_ids))
            rows = db.query(f"SELECT * FROM job WHERE id IN ({placeholders})", job_ids)
        elif force:
            rows = db.query("SELECT * FROM job WHERE is_archived = 0")
        else:
            rows = db.query(
                "SELECT j.* FROM job j LEFT JOIN match m ON m.job_id = j.id AND m.cv_id = ? "
                "WHERE m.id IS NULL AND j.is_archived = 0",
                (cv_id,),
            )

        weights = {
            "skills": db.get_setting_float("weight_skills", 40),
            "similarity": db.get_setting_float("weight_similarity", 25),
            "title": db.get_setting_float("weight_title", 15),
            "education": db.get_setting_float("weight_education", 10),
            "experience": db.get_setting_float("weight_experience", 5),
            "location": db.get_setting_float("weight_location", 5),
        }

        scored: list[dict[str, Any]] = []
        for row in rows:
            view = JobView(
                title=row["title"], company=row["company"], description=row["description"],
                location=row["location"], city=row["city"], country=row["country"],
                remote=bool(row["remote"]), department=row["department"],
            )
            best = None
            best_spec: SearchSpec | None = None
            for spec in specs:
                result = score_job(
                    view, cv, idf,
                    keywords=spec.keywords,
                    wanted_location=spec.location,
                    remote_ok=spec.remote_ok,
                    weights=weights,
                    profile=profilo,
                )
                if best is None or result.score > best.score:
                    best, best_spec = result, spec
            if best is None:
                continue
            breakdown = best.to_dict()
            db.execute(
                "INSERT INTO match(job_id, cv_id, search_id, score, breakdown_json, computed_at) "
                "VALUES (?,?,?,?,?,?) ON CONFLICT(job_id, cv_id) DO UPDATE SET "
                "score = excluded.score, breakdown_json = excluded.breakdown_json, "
                "search_id = excluded.search_id, computed_at = excluded.computed_at",
                (row["id"], cv_id, best_spec.id if best_spec else None, best.score,
                 json.dumps(breakdown, ensure_ascii=False), db.utcnow()),
            )
            scored.append({"job": db.row_to_dict(row), "score": best.score, "breakdown": breakdown})
        return scored

    # -- esecuzione --------------------------------------------------------

    @staticmethod
    def _is_due(row: Any, now: datetime) -> bool:
        if not row["enabled"]:
            return False
        if not row["last_run_at"]:
            return True
        try:
            last = datetime.fromisoformat(row["last_run_at"])
        except ValueError:
            return True
        # Dopo un errore l'attesa raddoppia a ogni tentativo fallito: un provider
        # in difficolta' non viene martellato di richieste.
        backoff = 2 ** min(row["consecutive_failures"], MAX_BACKOFF_STEPS)
        interval = max(row["min_interval_sec"], 60) * backoff
        return now >= last + timedelta(seconds=interval)

    async def _run_provider(self, row: Any, specs: list[SearchSpec], http: httpx.AsyncClient) -> dict[str, Any]:
        started = db.utcnow()
        provider_id = row["id"]
        config = json.loads(row["config_json"] or "{}")
        outcome: dict[str, Any] = {
            "provider_id": provider_id, "label": row["label"], "kind": row["kind"],
            "fetched": 0, "new": 0, "ok": False, "error": "",
        }
        try:
            provider = build(row["kind"], config, http)
            provider.known_ids = {
                r["external_id"] for r in db.query(
                    "SELECT external_id FROM job WHERE provider_id = ?", (provider_id,)
                )
            }
            postings = await provider.fetch(specs)
        except ProviderError as exc:
            outcome["error"] = str(exc)
        except Exception as exc:  # difensivo: un adapter rotto non ferma il ciclo
            outcome["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
            log.exception("provider %s in errore", row["label"])
        else:
            kept = [
                p for p in postings
                if not specs or any(self.matches_search(p, s) for s in specs)
            ]
            # Le descrizioni si scaricano solo adesso, sulle offerte che hanno
            # superato il filtro. Farlo prima significava spendere decine di
            # richieste per annunci che venivano poi scartati tutti.
            if kept:
                try:
                    await provider.enrich(kept)
                except ProviderError as exc:
                    log.warning("%s: dettagli non scaricabili: %s", row["label"], exc)
            new_ids, touched = self.store(provider_id, kept)
            outcome.update(ok=True, fetched=len(kept), new=len(new_ids), new_ids=new_ids)
            log.info("%s: %d offerte pertinenti su %d elencate, %d nuove",
                     row["label"], len(kept), len(postings), len(new_ids))

        finished = db.utcnow()
        if outcome["ok"]:
            db.execute(
                "UPDATE provider SET last_run_at = ?, last_status = 'ok', last_error = '', "
                "last_count = ?, consecutive_failures = 0, "
                "consecutive_empty = CASE WHEN ? = 0 THEN consecutive_empty + 1 ELSE 0 END, "
                "total_jobs = total_jobs + ? WHERE id = ?",
                (finished, outcome["fetched"], outcome["fetched"], outcome["new"], provider_id),
            )
        else:
            db.execute(
                "UPDATE provider SET last_run_at = ?, last_status = 'errore', last_error = ?, "
                "consecutive_failures = consecutive_failures + 1 WHERE id = ?",
                (finished, outcome["error"][:400], provider_id),
            )
        db.execute(
            "INSERT INTO run_log(provider_id, started_at, finished_at, ok, fetched, new_jobs, error) "
            "VALUES (?,?,?,?,?,?,?)",
            (provider_id, started, finished, 1 if outcome["ok"] else 0,
             outcome["fetched"], outcome["new"], outcome["error"][:400]),
        )
        return outcome

    async def run_cycle(self, provider_ids: list[int] | None = None, force: bool = False) -> dict[str, Any]:
        """Un giro completo: scarica, archivia, valuta, notifica."""
        async with self._lock:
            now = datetime.now(timezone.utc)
            sql = "SELECT * FROM provider"
            params: list[Any] = []
            if provider_ids:
                sql += f" WHERE id IN ({','.join('?' * len(provider_ids))})"
                params = list(provider_ids)
            rows = db.query(sql + " ORDER BY id", params)
            due = [r for r in rows if force or provider_ids or self._is_due(r, now)]

            summary: dict[str, Any] = {
                "started_at": db.utcnow(), "providers_total": len(rows),
                "providers_run": len(due), "fetched": 0, "new_jobs": 0,
                "scored": 0, "results": [], "notify": {}, "errors": [],
            }
            if not due:
                summary["finished_at"] = db.utcnow()
                self.last_summary = summary
                return summary

            specs = self.search_specs()
            headers = {
                "User-Agent": db.get_setting("user_agent", "JobSeeker/1.0"),
                "Accept": "application/json, text/plain;q=0.9, */*;q=0.8",
            }
            async with httpx.AsyncClient(timeout=45, follow_redirects=True, headers=headers) as http:
                new_ids: list[int] = []
                for row in due:
                    outcome = await self._run_provider(row, specs, http)
                    summary["results"].append(outcome)
                    summary["fetched"] += outcome["fetched"]
                    summary["new_jobs"] += outcome["new"]
                    if outcome["error"]:
                        summary["errors"].append(f"{row['label']}: {outcome['error']}")
                    new_ids.extend(outcome.get("new_ids", []))
                    # Piccola pausa fra provider diversi: le API pubbliche
                    # gradiscono un ritmo umano piu' di una raffica.
                    if len(due) > 1:
                        await asyncio.sleep(random.uniform(0.3, 0.9))

            # I punteggi si calcolano fuori dal contesto di rete: e' lavoro locale.
            scored = self.score_jobs(job_ids=new_ids or None)
            summary["scored"] = len(scored)
            # L'eventuale affinamento semantico avviene prima delle notifiche,
            # cosi' la soglia viene applicata al punteggio definitivo.
            summary["llm_refined"] = await self.refine_with_llm(scored)
            if self.last_llm_error:
                summary["errors"].append(self.last_llm_error)
            if scored:
                summary["notify"] = notify.dispatch(scored)
            summary["finished_at"] = db.utcnow()
            self.last_summary = summary
            return summary

    # -- livello semantico opzionale ---------------------------------------

    async def refine_with_llm(self, scored: list[dict[str, Any]]) -> int:
        """Affina con Claude i punteggi delle offerte piu' promettenti.

        Interviene solo se il livello semantico e' attivo e configurato. Il
        punteggio lessicale resta la base: quello del modello lo corregge in
        proporzione al peso impostato, e il suo giudizio viene conservato nel
        dettaglio dell'offerta.
        """
        if not db.get_setting_bool("llm_enabled", False) or not scored:
            return 0
        provider = db.get_setting("llm_provider", llm.DEFAULT_PROVIDER)
        available, reason = llm.is_available(provider)
        if not available:
            log.warning("livello semantico attivo ma non utilizzabile (%s): %s", provider, reason)
            return 0

        cv = self.active_cv()
        if cv is None:
            return 0
        floor = db.get_setting_float("llm_min_lexical", 30)
        cap = db.get_setting_int("llm_max_per_cycle", 15)
        weight = db.get_setting_float("llm_weight", 50)
        model = db.get_setting("llm_model", "")

        candidates = sorted(
            (c for c in scored if c["score"] >= floor), key=lambda c: -c["score"]
        )[:cap]
        refined = 0
        falliti = 0
        for candidate in candidates:
            job = candidate["job"]
            view = JobView(
                title=job["title"], company=job["company"], description=job["description"],
                location=job["location"], city=job["city"], country=job["country"],
                remote=bool(job["remote"]), department=job["department"],
            )
            # I client dei fornitori sono sincroni: girarli su un thread evita
            # di bloccare il ciclo di eventi mentre attendono la risposta.
            verdict = await asyncio.to_thread(
                llm.evaluate, view, cv, provider, model, self.feedback_profile().summary())
            if verdict is None:
                falliti += 1
                # Se il modello non risponde mai non ha senso insistere per
                # tutto il ciclo: si esce e si segnala, invece di fallire in
                # silenzio venti volte di fila.
                if falliti >= 3 and refined == 0:
                    log.warning(
                        "livello semantico interrotto: %s non risponde (modello %s)",
                        provider, model or llm.provider_info(provider)["model"])
                    break
                continue
            lexical = candidate["score"]
            final = llm.blend(lexical, verdict, weight)
            breakdown = candidate["breakdown"]
            breakdown["llm"] = {
                "provider": llm.provider_info(provider)["label"],
                "score": verdict.score,
                "lexical_score": round(lexical, 1),
                "weight": weight,
                "reasoning": verdict.reasoning,
                "key_matches": verdict.key_matches,
                "key_gaps": verdict.key_gaps,
                "seniority_fit": verdict.seniority_fit,
            }
            candidate["score"] = final
            db.execute(
                "UPDATE match SET score = ?, breakdown_json = ?, computed_at = ? "
                "WHERE job_id = ? AND cv_id = ?",
                (final, json.dumps(breakdown, ensure_ascii=False), db.utcnow(),
                 job["id"], self._cv_id),
            )
            refined += 1
        if refined:
            log.info("livello semantico: %d offerte rivalutate da %s", refined,
                     llm.provider_info(provider)["label"])
        if falliti:
            etichetta = llm.provider_info(provider)["label"]
            modello = model or llm.provider_info(provider)["model"]
            self.last_llm_error = (
                f"{etichetta} non ha risposto per {falliti} offerte (modello {modello}). "
                "Se si ripete, prova un altro modello dalle impostazioni."
            )
        else:
            self.last_llm_error = ""
        return refined

    # -- manutenzione ------------------------------------------------------

    @staticmethod
    def cleanup() -> int:
        """Archivia le offerte vecchie, tenendo quelle salvate nello storico."""
        days = db.get_setting_int("retention_days", 90)
        if days <= 0:
            return 0
        limit = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
        cursor = db.execute(
            "UPDATE job SET is_archived = 1 WHERE last_seen_at < ? AND is_archived = 0 "
            "AND id NOT IN (SELECT job_id FROM application)",
            (limit,),
        )
        return cursor.rowcount


pipeline = Pipeline()
