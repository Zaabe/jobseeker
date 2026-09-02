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

from . import db, notify, paesi
from .matching import CVProfile, IdfIndex, JobView, cv_parser, llm, score_job
from .matching import skills
from .matching import feedback as fb
from .matching.cv_parser import CVProfile as Profile
from .matching.text import is_country_query, job_in_country, normalize, place_matches
from .providers import ProviderError, SearchSpec, build

log = logging.getLogger("jobseeker.pipeline")

# Oltre questo numero di errori consecutivi l'attesa fra due tentativi non
# cresce piu': serve a non allontanare all'infinito un provider temporaneamente
# irraggiungibile.
MAX_BACKOFF_STEPS = 5

# Quanti punteggi scrivere in una sola transazione.
#
# Una transazione per offerta significava, su un archivio da 1300 annunci,
# 1300 acquisizioni del lock di scrittura una dopo l'altra. SQLite non mette
# in coda chi aspetta con equita': una richiesta web che vuole scrivere nel
# frattempo resta ferma per tutta la durata del ricalcolo, e se supera
# l'attesa concessa riceve "database is locked". A lotti il ricalcolo e' circa
# trenta volte piu' rapido e lascia dei varchi a chi deve scrivere.
#
# Non un lotto unico: una transazione da 1300 righe terrebbe il lock tutta
# insieme, spostando il problema invece di risolverlo.
LOTTO_PUNTEGGI = 200

SQL_PUNTEGGIO = (
    "INSERT INTO match(job_id, cv_id, search_id, score, breakdown_json, computed_at) "
    "VALUES (?,?,?,?,?,?) ON CONFLICT(job_id, cv_id) DO UPDATE SET "
    "score = excluded.score, breakdown_json = excluded.breakdown_json, "
    "search_id = excluded.search_id, computed_at = excluded.computed_at"
)


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
        # A che punto e' il giro in corso, o None se non ce n'e' uno. Serve
        # all'interfaccia, che ci disegna la barra al posto del pulsante: senza
        # un dato sul server la barra vivrebbe solo nella pagina che ha premuto
        # il pulsante, e sparirebbe ricaricando o guardando da un altro
        # dispositivo.
        self.corsa: dict[str, Any] | None = None
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
        # Le parole dei dizionari collegati si sommano a quelle scritte nei
        # campi della ricerca. Si leggono tutti in una volta: sono pochi, e
        # farlo per ogni ricerca vorrebbe dire una query per riga.
        dizionari = {
            r["id"]: json.loads(r["words_json"] or "[]")
            for r in db.query("SELECT id, words_json FROM dictionary")
        }

        def unisci(scritte: list[str], id_dizionario: Any) -> list[str]:
            parole = list(scritte)
            # Il confronto ignora le maiuscole: nel campo si scrive come viene,
            # e "Analista" nella ricerca con "analista" nel dizionario sono la
            # stessa parola cercata due volte.
            viste = {p.casefold() for p in parole}
            for voce in dizionari.get(id_dizionario, []):
                if voce.casefold() not in viste:
                    parole.append(voce)
                    viste.add(voce.casefold())
            return parole

        return [
            SearchSpec(
                id=r["id"],
                name=r["name"],
                keywords=unisci(json.loads(r["keywords_json"] or "[]"), r["dict_keywords_id"]),
                exclude=unisci(json.loads(r["exclude_json"] or "[]"), r["dict_exclude_id"]),
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
    def _parola_gia_cercata(posting: Any, spec: SearchSpec) -> bool:
        """Se l'offerta arriva da una ricerca fatta con una parola di `spec`.

        Le fonti che interrogano un portale scrivono in `raw["query"]` la parola
        che hanno usato. Vale solo finche' la descrizione non c'e': appena
        arriva, il testo dell'annuncio e' l'informazione migliore e si torna a
        guardare quello.
        """
        if (getattr(posting, "description", "") or "").strip():
            return False
        parola = normalize(str((getattr(posting, "raw", None) or {}).get("query", "")))
        if not parola:
            return False
        return any(normalize(term) == parola for term in spec.keywords if term)

    @staticmethod
    def _luogo_gia_cercato(posting: Any, spec: SearchSpec) -> bool:
        """Se la fonte ha già cercato in questo luogo, e nello stesso paese.

        Le schede di LinkedIn scrivono spesso solo la citta' - "Milano" - senza
        mai nominare il paese. Una ricerca "in Italia" non ha modo di
        riconoscerle: il testo non dice Italia, il campo paese e' vuoto, e le
        scartava tutte. Ma la richiesta a LinkedIn conteneva "Italy", quindi
        quel filtro e' gia' stato applicato da chi ha l'anagrafica dei luoghi.

        Vale solo per la ricerca che ha chiesto *quel* luogo: le fonti mandano
        una sola richiesta per tutte le ricerche, e un annuncio milanese non
        diventa pertinente per una ricerca su Roma.
        """
        chiesto = str((getattr(posting, "raw", None) or {}).get("query_luogo", ""))
        if not chiesto:
            return False
        if normalize(paesi.senza_paese(chiesto)) != normalize(paesi.senza_paese(spec.location)):
            return False
        paese_chiesto = paesi.codice_dalla_sede(chiesto)
        atteso = (spec.country or "").strip().lower()
        return not atteso or not paese_chiesto or paese_chiesto == atteso

    @staticmethod
    def matches_search(posting: Any, spec: SearchSpec) -> bool:
        """Verifica se un'offerta rientra in una ricerca salvata.

        Il filtro sulle parole chiave e' necessario perche' le board aziendali
        restituiscono tutte le posizioni dell'azienda, non solo quelle attinenti.
        """
        haystack = normalize(posting.searchable_text())
        if spec.exclude and any(normalize(term) in haystack for term in spec.exclude if term):
            return False
        # Le parole chiave si cercano nel testo dell'offerta. Con una
        # eccezione: se questa offerta e' il risultato di una ricerca fatta
        # dalla fonte con una parola di *questa* ricerca, la selezione e' gia'
        # stata fatta, e da chi aveva piu' informazioni di noi.
        #
        # Il caso vero: LinkedIn cerca la parola anche nei requisiti, noi in
        # questo momento abbiamo solo il titolo, perche' le descrizioni si
        # scaricano dopo il filtro. Su 165 annunci elencati da LinkedIn per
        # "react" ne restavano zero: nessun titolo dice "react". La fonte
        # lavorava e il risultato veniva buttato via tutto.
        #
        # Non e' un liberi tutti: conta solo la parola con cui l'offerta e'
        # stata effettivamente trovata, e solo se e' fra quelle di questa
        # ricerca. Un annuncio pescato con la parola di un'altra ricerca resta
        # da giudicare sul testo, come prima.
        if spec.keywords and not Pipeline._parola_gia_cercata(posting, spec):
            if not any(normalize(term) in haystack for term in spec.keywords if term):
                return False
        if spec.location_filter:
            sede = " ".join(p for p in (posting.location, posting.city, posting.region) if p)
            # Il paese dell'offerta: quello dichiarato o, se non c'e', quello
            # nominato nella sede. Le offerte da remoto spesso lasciano vuoto il
            # campo e scrivono "Remote - United States", che nessun campo
            # strutturato racconta.
            paese_offerta = posting.country or paesi.paese_nel_testo(sede)
            # Il paese vale da solo, e vale anche per il remoto. Prima il
            # remoto passava qui sopra, prima di qualunque controllo: bastava
            # che un annuncio fosse "da remoto" perche' il filtro sulla
            # localita' non lo guardasse piu', e arrivavano offerte da remoto
            # degli Stati Uniti a una ricerca in Italia. Lavorare da casa non
            # sposta il fuso orario, ne' il permesso di lavoro: il remoto
            # esonera dalla citta', non dal paese.
            #
            # Prima ancora, tutto questo blocco partiva solo se la ricerca aveva
            # scritto anche una localita': chi metteva solo il paese si
            # ritrovava le offerte estere in mezzo alle altre. Le offerte che il
            # paese non lo dicono da nessuna parte passano e vengono giudicate
            # sul testo della sede: meglio una in piu' da scartare a mano che
            # una buona buttata via su un'informazione assente.
            if (spec.country and paese_offerta
                    and not job_in_country(paese_offerta, spec.country)):
                return False
            if posting.remote and spec.remote_ok:
                return True
            if not spec.location:
                return True
            # Il luogo l'ha già ristretto la fonte, con l'anagrafica dei luoghi
            # che noi non abbiamo: qui non si può fare di meglio che rifiutare
            # una scheda scritta "Milano" perché non dice "Italia".
            if Pipeline._luogo_gia_cercato(posting, spec):
                return True
            # I luoghi da cercare, senza il paese: quello e' gia' stato
            # controllato qui sopra, e lasciarlo in mezzo agli altri lo
            # trasformerebbe in un'alternativa. "Milano, Italia" chiede Milano;
            # se valesse anche "Italia" il filtro terrebbe tutto il paese, ed e'
            # esattamente cio' che si voleva escludere accendendolo.
            luoghi = paesi.senza_paese(spec.location)
            place = " ".join(p for p in (sede, posting.country) if p)
            # Cercare "Italia" e' una ricerca sull'intero paese, e va risolta sul
            # campo paese dell'offerta: molte fonti scrivono la sede come
            # "Roma, Provincia di Roma" senza mai nominare l'Italia, e un
            # confronto puramente testuale le scarterebbe tutte.
            if not luoghi or is_country_query(spec.location, spec.country):
                if job_in_country(paese_offerta, spec.country):
                    return True
                return not place or place_matches(spec.location, place)
            # Altrimenti si confronta il testo, con le varianti linguistiche:
            # le fonti scrivono "Milan, Italy", la ricerca dice "Milano".
            if place and not place_matches(luoghi, place):
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

        # I giudizi del modello sopravvivono al ricalcolo. Costano una chiamata a
        # pagamento ciascuno, e riguardano l'offerta rispetto al profilo: il
        # punteggio lessicale si rifa' da zero, quel giudizio no. Prima veniva
        # buttato via insieme al resto del dettaglio, e "Ricalcola i punteggi"
        # cancellava senza dirlo centinaia di letture gia' pagate.
        #
        # Si leggono con `json_extract`, cosi' tornano solo le poche righe che
        # ne hanno una invece dell'intero archivio da interpretare.
        giudizi: dict[int, dict[str, Any]] = {}
        for riga in db.query(
                "SELECT job_id, json_extract(breakdown_json, '$.llm') AS giudizio "
                "FROM match WHERE cv_id = ? AND json_valid(breakdown_json) "
                "  AND json_extract(breakdown_json, '$.llm') IS NOT NULL", (cv_id,)):
            try:
                giudizi[riga["job_id"]] = json.loads(riga["giudizio"])
            except (ValueError, TypeError):
                continue

        scored: list[dict[str, Any]] = []
        da_scrivere: list[tuple[Any, ...]] = []
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
            punteggio = best.score
            giudizio = giudizi.get(row["id"])
            if giudizio:
                # Il giudizio torna nel dettaglio, e il punteggio finale si
                # rimescola: la parte lessicale e' cambiata, quella del modello
                # no. `lexical_score` si aggiorna, altrimenti la scheda
                # dell'offerta mostrerebbe la base di prima.
                giudizio = dict(giudizio, lexical_score=round(best.score, 1))
                breakdown["llm"] = giudizio
                punteggio = llm.mescola(best.score, giudizio.get("score"),
                                        giudizio.get("weight",
                                                     db.get_setting_float("llm_weight", 50)))
            da_scrivere.append((
                row["id"], cv_id, best_spec.id if best_spec else None, punteggio,
                json.dumps(breakdown, ensure_ascii=False), db.utcnow(),
            ))
            scored.append({"job": db.row_to_dict(row), "score": punteggio,
                           "breakdown": breakdown,
                           # Quale ricerca ha prodotto il punteggio: serve alle
                           # notifiche, perche' ogni ricerca puo' avere la sua
                           # soglia.
                           "search_id": best_spec.id if best_spec else None})
            if len(da_scrivere) >= LOTTO_PUNTEGGI:
                db.executemany(SQL_PUNTEGGIO, da_scrivere)
                da_scrivere.clear()

        if da_scrivere:
            db.executemany(SQL_PUNTEGGIO, da_scrivere)
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
        provider = None
        try:
            provider = build(row["kind"], config, http)
            # Due domande diverse, una lettura sola. `known_ids` sono le
            # offerte di cui l'archivio ha gia' la descrizione, e sono quelle
            # che gli adapter saltano quando scaricano i dettagli: prima qui
            # finivano tutte le offerte salvate, descrizione o no, e quelle
            # rimaste fuori dal tetto di un ciclo non venivano piu' completate
            # mai. `id_in_archivio` sono tutte quante, e servono a chi sfoglia
            # un elenco a pagine per sapere quando ha smesso di trovare novita'.
            righe = db.query(
                "SELECT external_id, COALESCE(description, '') <> '' AS con_testo "
                "FROM job WHERE provider_id = ?", (provider_id,))
            provider.id_in_archivio = {r["external_id"] for r in righe}
            provider.known_ids = {r["external_id"] for r in righe if r["con_testo"]}
            try:
                provider.stato = json.loads(row["stato_json"] or "{}")
            except (ValueError, IndexError, KeyError):
                provider.stato = {}
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

        # Il foglietto della fonte si riscrive anche quando il giro e' andato
        # male: chi sfoglia un elenco puo' essere sceso di qualche pagina prima
        # di trovare la porta chiusa, e quel progresso non va perso.
        if provider is not None and provider.stato:
            try:
                db.execute("UPDATE provider SET stato_json = ? WHERE id = ?",
                           (json.dumps(provider.stato, ensure_ascii=False)[:4000], provider_id))
            except Exception as exc:
                log.warning("%s: stato della fonte non salvato (%s)", row["label"], exc)

        # Le offerte sono gia' state archiviate: quello che resta e' la
        # contabilita' del provider. Se fallisce, si perde una riga di
        # diario, non il lavoro fatto. Prima un errore qui interrompeva
        # l'intero ciclo e le fonti successive non venivano nemmeno provate.
        try:
            self._registra_esito(provider_id, started, outcome)
        except Exception as exc:
            log.warning("%s: esito non registrato (%s: %s)",
                        row["label"], type(exc).__name__, str(exc)[:120])
        return outcome

    def _registra_esito(self, provider_id: int, started: str, outcome: dict[str, Any]) -> None:
        """Aggiorna stato e diario del provider dopo un giro."""
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

    def _fase(self, fase: str, **campi: Any) -> None:
        """Aggiorna il punto in cui si trova il giro. Se non e' in corso, tace."""
        if self.corsa is not None:
            self.corsa.update(fase=fase, **campi)

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
            # Una fonte spenta resta spenta anche premendo "Controlla ora":
            # `force` salta il controllo sugli intervalli, non la volonta' di chi
            # l'ha disattivata. Se invece la si chiede per id - il pulsante
            # "Esegui" sulla sua scheda - allora e' una richiesta esplicita.
            due = [r for r in rows
                   if (r["enabled"] or provider_ids)
                   and (force or provider_ids or self._is_due(r, now))]

            summary: dict[str, Any] = {
                "started_at": db.utcnow(), "providers_total": len(rows),
                "providers_run": len(due), "fetched": 0, "new_jobs": 0,
                "scored": 0, "results": [], "notify": {}, "errors": [],
            }
            if not due:
                summary["finished_at"] = db.utcnow()
                self.last_summary = summary
                return summary

            # Da qui parte il lavoro vero, e l'interfaccia puo' seguirlo. Le
            # fonti sono quelle lette un attimo fa: una aggiunta adesso non
            # entra in questo giro - viene interrogata al successivo, che e'
            # anche quello che si aspetta chi la sta aggiungendo.
            self.corsa = {"iniziata": db.utcnow(), "fase": "fonti", "fatte": 0,
                          "totale": len(due), "fonte": "", "manuale": bool(force)}
            try:
                return await self._giro(due, summary)
            finally:
                self.corsa = None

    async def _giro(self, due: list[Any], summary: dict[str, Any]) -> dict[str, Any]:
        """Il corpo di un giro, con `self.corsa` gia' aperta."""
        specs = self.search_specs()
        headers = {
            "User-Agent": db.get_setting("user_agent", "JobSeeker/1.0"),
            "Accept": "application/json, text/plain;q=0.9, */*;q=0.8",
        }
        async with httpx.AsyncClient(timeout=45, follow_redirects=True, headers=headers) as http:
            new_ids: list[int] = []
            for row in due:
                self._fase("fonti", fonte=row["label"])
                try:
                    outcome = await self._run_provider(row, specs, http)
                except Exception as exc:
                    # Una fonte che fallisce in modo imprevisto non deve
                    # far saltare le altre: il ciclo prosegue e l'errore
                    # finisce nel riepilogo.
                    log.exception("fonte %s: giro interrotto", row["label"])
                    outcome = {"provider_id": row["id"], "label": row["label"],
                               "kind": row["kind"], "fetched": 0, "new": 0, "ok": False,
                               "error": f"{type(exc).__name__}: {exc}"[:400]}
                self._fase("fonti", fatte=self.corsa["fatte"] + 1 if self.corsa else 0)
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
        self._fase("punteggi", fonte="")
        scored = self.score_jobs(job_ids=new_ids or None)
        summary["scored"] = len(scored)
        # L'eventuale affinamento semantico avviene prima delle notifiche,
        # cosi' la soglia viene applicata al punteggio definitivo.
        # Anche a mani vuote: se non e' arrivato niente di nuovo, il
        # modello usa il giro per smaltire l'arretrato.
        self._fase("ia")
        summary["llm_refined"] = await self.refine_with_llm(scored)
        if self.last_llm_error:
            summary["errors"].append(self.last_llm_error)
        # Agli avvisi non vanno solo le offerte di questo giro, ma anche
        # quelle che in archivio non ne hanno mai prodotto uno: senza,
        # abbassare la soglia non avrebbe effetto su quello che c'e' gia',
        # e chi la porta a zero aspettando gli avvisi non vedrebbe arrivare
        # niente.
        self._fase("notifiche")
        candidati = scored + self.mai_annunciate({c["job"]["id"] for c in scored})
        if candidati:
            summary["notify"] = notify.dispatch(candidati)
        summary["finished_at"] = db.utcnow()
        self.last_summary = summary
        return summary

    # Quante offerte gia' in archivio guardare a ogni giro. E' un tetto di
    # lettura, non di invii: quanti avvisi partono davvero lo decide
    # `notify_max_per_cycle`.
    MAI_ANNUNCIATE = 200

    @staticmethod
    def finestra_arretrato() -> str:
        """Da quando in poi un'offerta mai annunciata merita ancora un avviso."""
        giorni = max(0, db.get_setting_int("notify_backlog_days", 7))
        return (datetime.now(timezone.utc) - timedelta(days=giorni)).isoformat(timespec="seconds")

    def mai_annunciate(self, escludi: set[int]) -> list[dict[str, Any]]:
        """Le offerte arrivate di recente che non hanno mai prodotto un avviso.

        Serve a far valere un cambio di soglia su quello che c'e' gia': senza,
        un'offerta arrivata quando la soglia era alta resterebbe muta per
        sempre, anche dopo averla abbassata. Le offerte gia' annunciate restano
        fuori anche se l'avviso e' stato tolto dall'elenco, perche' la riga
        rimane come memoria.

        La finestra temporale non e' un dettaglio, e' la differenza fra un
        recupero e un rubinetto aperto: senza, con la soglia bassa questa
        funzione restituiva l'intero archivio e ne partivano dieci per ciclo -
        duecento avvisi all'ora - finche' non era esaurito, comprese offerte di
        un mese prima. Un annuncio di tre settimane fa non e' una novita': se
        interessa lo si trova nell'elenco delle offerte.
        """
        if self.active_cv() is None:
            return []
        righe = db.query(
            "SELECT j.*, m.score, m.breakdown_json, m.search_id FROM match m "
            "JOIN job j ON j.id = m.job_id "
            "WHERE m.cv_id = ? AND j.is_archived = 0 "
            "  AND j.first_seen_at >= ? "
            "  AND NOT EXISTS (SELECT 1 FROM notification n WHERE n.job_id = j.id) "
            "ORDER BY m.score DESC LIMIT ?",
            (self._cv_id, self.finestra_arretrato(), self.MAI_ANNUNCIATE),
        )
        arretrato = []
        for riga in righe:
            if riga["id"] in escludi:
                continue
            try:
                breakdown = json.loads(riga["breakdown_json"] or "{}")
            except ValueError:
                breakdown = {}
            arretrato.append({"job": db.row_to_dict(riga), "score": riga["score"],
                              "breakdown": breakdown, "search_id": riga["search_id"]})
        return arretrato

    # -- livello semantico opzionale ---------------------------------------

    # Offerte che aspettano un giudizio: sopra soglia e senza `llm` nel
    # dettaglio. Sta qui una volta sola perche' la usano sia il ciclo che il
    # conteggio mostrato nelle impostazioni.
    # Chi aspetta il modello: sopra soglia, senza un giudizio e senza il segno
    # di chi ha svuotato la coda a mano. Il segno sta dentro il dettaglio del
    # punteggio e non e' un giudizio finto: un giudizio finto finirebbe nella
    # scheda dell'offerta e nei conti, questo no.
    SENZA_GIUDIZIO = (
        "  AND json_extract(m.breakdown_json, '$.llm') IS NULL "
        "  AND json_extract(m.breakdown_json, '$.llm_saltata') IS NULL "
    )

    SQL_SENZA_GIUDIZIO = (
        "SELECT j.id, j.title, j.company, j.description, j.location, j.city, "
        "       j.country, j.remote, j.department, m.score, m.breakdown_json "
        "FROM match m JOIN job j ON j.id = m.job_id "
        "WHERE m.cv_id = ? AND j.is_archived = 0 AND m.score >= ? " + SENZA_GIUDIZIO
    )

    # Pausa fra una valutazione e l'altra. Non e' prudenza generica: le chiavi
    # gratuite concedono una manciata di richieste al minuto, e partire a
    # raffica significa ricevere errori di quota invece che giudizi.
    PAUSA_FRA_VALUTAZIONI = 4.0

    def da_valutare(self, soglia: float, quanti: int,
                    prima: list[int] | None = None) -> list[Any]:
        """Le offerte da sottoporre al modello, le piu' promettenti per prime.

        Pesca da tutto l'archivio, non solo dalle offerte appena raccolte.
        Prima lo faceva, e con un archivio da millesettecento annunci gia' in
        casa il livello semantico restava acceso senza produrre niente: le
        uniche offerte che poteva vedere erano le poche nuove di quel giro.

        `prima` sono le offerte appena raccolte. Vanno in testa perche' sono
        quelle su cui sta per partire una notifica, e la soglia di notifica va
        applicata al punteggio definitivo, non a quello provvisorio.
        """
        scelte: list[Any] = []
        visti: set[int] = set()
        if prima:
            segnaposto = ",".join("?" * len(prima))
            for riga in db.query(
                    self.SQL_SENZA_GIUDIZIO + f"AND j.id IN ({segnaposto}) "
                    "ORDER BY m.score DESC LIMIT ?",
                    (self._cv_id, soglia, *prima, quanti)):
                scelte.append(riga)
                visti.add(riga["id"])
        if len(scelte) < quanti:
            for riga in db.query(self.SQL_SENZA_GIUDIZIO + "ORDER BY m.score DESC LIMIT ?",
                                 (self._cv_id, soglia, quanti + len(visti))):
                if riga["id"] in visti:
                    continue
                scelte.append(riga)
                if len(scelte) >= quanti:
                    break
        return scelte

    async def leggi_curriculum(self, testo: str, profilo: Any) -> dict[str, Any]:
        """Fa rileggere il curriculum al modello, se e' configurato.

        Senza chiave, o con il livello semantico spento, non succede nulla e il
        profilo resta quello delle euristiche: e' una strada completa, non un
        ripiego. Con la chiave, le due letture vengono fuse e i disaccordi
        restano scritti nel profilo.
        """
        if not db.get_setting_bool("llm_enabled", False):
            return cv_parser.apply_reading(profilo, None)
        provider = db.get_setting("llm_provider", llm.DEFAULT_PROVIDER)
        if not llm.is_available(provider)[0]:
            return cv_parser.apply_reading(profilo, None)
        lettura = await asyncio.to_thread(
            llm.read_cv, testo, provider, db.get_setting("llm_model", ""),
            skills.EDUCATION_LABELS)
        if lettura is None:
            note = cv_parser.apply_reading(profilo, None)
            note["avviso"] = ("il modello non ha risposto: il profilo viene dalla sola "
                              "lettura automatica del testo")
            return note
        return cv_parser.apply_reading(profilo, lettura)

    def in_attesa_di_giudizio(self) -> int:
        """Quante offerte sopra soglia aspettano ancora il modello.

        Serve alle impostazioni: senza, l'unico modo di sapere se il livello
        semantico stia lavorando era guardare i log del contenitore.
        """
        if not db.get_setting_bool("llm_enabled", False) or self.active_cv() is None:
            return 0
        riga = db.query_one(
            "SELECT COUNT(*) AS n FROM match m JOIN job j ON j.id = m.job_id "
            "WHERE m.cv_id = ? AND j.is_archived = 0 AND m.score >= ? " + self.SENZA_GIUDIZIO,
            (self._cv_id, db.get_setting_float("llm_min_lexical", 50)),
        )
        return riga["n"] if riga else 0

    def svuota_coda_llm(self) -> int:
        """Toglie dalla coda del modello le offerte che la stanno aspettando.

        Non cancella niente e non inventa giudizi: mette un segno nel dettaglio
        del punteggio, e chi pesca dalla coda salta le offerte che lo portano.
        Serve quando la coda e' lunga come l'archivio - millesettecento offerte
        a quattro secondi l'una sono giorni di richieste - e quello che si vuole
        e' ripartire da qui in avanti.

        Un ricalcolo dei punteggi riscrive il dettaglio da zero, quindi rimette
        in coda quello che si e' saltato: e' anche il modo di tornare indietro.
        """
        if self.active_cv() is None:
            return 0
        cursore = db.execute(
            "UPDATE match SET breakdown_json = "
            "  json_set(breakdown_json, '$.llm_saltata', json('true')) "
            "WHERE cv_id = ? AND json_valid(breakdown_json) "
            "  AND job_id IN (SELECT id FROM job WHERE is_archived = 0) "
            "  AND score >= ? "
            "  AND json_extract(breakdown_json, '$.llm') IS NULL "
            "  AND json_extract(breakdown_json, '$.llm_saltata') IS NULL",
            (self._cv_id, db.get_setting_float("llm_min_lexical", 50)),
        )
        quante = cursore.rowcount
        if quante:
            log.info("coda del livello semantico svuotata: %d offerte non verranno lette", quante)
        return quante

    async def refine_with_llm(self, scored: list[dict[str, Any]] | None = None) -> int:
        """Fa rileggere dal modello le offerte piu' promettenti.

        Interviene solo se il livello semantico e' attivo e configurato. Il
        punteggio lessicale resta la base: quello del modello lo corregge in
        proporzione al peso impostato, e la spiegazione viene conservata nel
        dettaglio dell'offerta, dove l'interfaccia la mostra.
        """
        # L'errore parla dell'ultimo tentativo, quindi si azzera prima di
        # tentare. Prima restava scritto: spegnendo la valutazione semantica la
        # funzione uscira' subito qui sotto senza toccarlo, e il riepilogo di
        # ogni giro continuava a riportare un guasto di un modello che nessuno
        # stava piu' chiamando.
        self.last_llm_error = ""
        if not db.get_setting_bool("llm_enabled", False):
            return 0
        provider = db.get_setting("llm_provider", llm.DEFAULT_PROVIDER)
        available, reason = llm.is_available(provider)
        if not available:
            # Attiva ma inutilizzabile: dirlo, perche' il silenzio somiglia
            # troppo al funzionare.
            log.warning("livello semantico attivo ma non utilizzabile (%s): %s", provider, reason)
            self.last_llm_error = f"valutazione semantica attiva ma non utilizzabile: {reason}"
            return 0

        cv = self.active_cv()
        if cv is None:
            return 0
        floor = db.get_setting_float("llm_min_lexical", 50)
        cap = db.get_setting_int("llm_max_per_cycle", 20)
        weight = db.get_setting_float("llm_weight", 50)
        model = db.get_setting("llm_model", "")
        if cap <= 0:
            return 0

        candidati = self.da_valutare(floor, cap, [c["job"]["id"] for c in (scored or [])])
        if not candidati:
            self.last_llm_error = ""
            return 0

        # Il profilo si legge una volta per ciclo, non una per offerta: e' lo
        # stesso testo per tutte, e ricostruirlo ogni volta sarebbe una lettura
        # dell'intera tabella delle candidature a ogni chiamata.
        profilo = self.feedback_profile()
        memoria, preferenze = profilo.summary(), profilo.preferences()
        per_id = {c["job"]["id"]: c for c in (scored or [])}

        refined = falliti = di_fila = 0
        for indice, riga in enumerate(candidati):
            if indice:
                await asyncio.sleep(self.PAUSA_FRA_VALUTAZIONI)
            view = JobView(
                title=riga["title"], company=riga["company"], description=riga["description"],
                location=riga["location"], city=riga["city"], country=riga["country"],
                remote=bool(riga["remote"]), department=riga["department"],
            )
            # I client dei fornitori sono sincroni: girarli su un thread evita
            # di bloccare il ciclo di eventi mentre attendono la risposta.
            verdict = await asyncio.to_thread(
                llm.evaluate, view, cv, provider, model, memoria, preferenze)
            if verdict is None:
                falliti += 1
                di_fila += 1
                # Tre errori di fila non sono sfortuna: e' la quota al minuto,
                # o la chiave, o il modello. Insistere per tutto il ciclo
                # produce solo altri errori, quindi si esce e lo si segnala.
                if di_fila >= 3:
                    log.warning(
                        "livello semantico interrotto: %s non risponde (modello %s)",
                        provider, model or llm.provider_info(provider)["model"])
                    break
                continue
            di_fila = 0
            # Senza `llm` nel dettaglio il punteggio salvato e' ancora quello
            # puramente lessicale: e' la base su cui applicare il giudizio.
            lessicale = float(riga["score"])
            finale = llm.blend(lessicale, verdict, weight)
            try:
                breakdown = json.loads(riga["breakdown_json"] or "{}")
            except (ValueError, TypeError):
                breakdown = {}
            breakdown["llm"] = {
                "provider": llm.provider_info(provider)["label"],
                "score": verdict.score,
                "lexical_score": round(lessicale, 1),
                "weight": weight,
                "reasoning": verdict.reasoning,
                "key_matches": verdict.key_matches,
                "key_gaps": verdict.key_gaps,
                "experience_note": verdict.experience_note,
                "concerns": verdict.concerns,
                "recommendation": verdict.recommendation,
                "seniority_fit": verdict.seniority_fit,
                "at": db.utcnow(),
            }
            db.execute(
                "UPDATE match SET score = ?, breakdown_json = ?, computed_at = ? "
                "WHERE job_id = ? AND cv_id = ?",
                (finale, json.dumps(breakdown, ensure_ascii=False), db.utcnow(),
                 riga["id"], self._cv_id),
            )
            # Se l'offerta e' fra quelle appena raccolte, la notifica che parte
            # subito dopo deve vedere il punteggio definitivo.
            voce = per_id.get(riga["id"])
            if voce is not None:
                voce["score"] = finale
                voce["breakdown"] = breakdown
            refined += 1
        if refined:
            log.info("livello semantico: %d offerte valutate da %s, ne restano %d",
                     refined, llm.provider_info(provider)["label"],
                     max(0, self.in_attesa_di_giudizio()))
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
