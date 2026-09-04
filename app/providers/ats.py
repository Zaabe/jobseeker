"""Adapter per gli ATS aziendali (i sistemi con cui le aziende pubblicano le
proprie posizioni aperte).

Sono le fonti piu' affidabili del sistema: API pubbliche, documentate, dati
strutturati e nessun rischio di blocco. Sono anche il modo con cui si segue una
singola azienda interessante, incollandone l'URL della pagina "lavora con noi".
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from .. import paesi
# Le varianti linguistiche dei nomi di luogo ("Milano" / "Milan", "Lombardia" /
# "Lombardy") stanno nel motore di confronto. Si importa quella tabella invece
# di riscriverne una qui: due elenchi di alias divergono alla prima aggiunta, e
# a divergere sarebbe il filtro geografico.
from ..matching.text import normalize, place_variants
from .base import (
    BaseProvider,
    JobPosting,
    ProviderError,
    SearchSpec,
    html_to_text,
    looks_remote,
    luogo_cercato,
    parse_date,
    unique_terms,
)


log = logging.getLogger("jobseeker.providers")


def _token_from_path(url: str, index: int = 0) -> str | None:
    """Estrae il segmento di percorso indicato, ripulito dai parametri."""
    parts = [p for p in urlparse(url).path.split("/") if p]
    if len(parts) > index:
        return re.sub(r"[^A-Za-z0-9_.-]", "", parts[index]) or None
    return None


# --------------------------------------------------------------------------
# Greenhouse
# --------------------------------------------------------------------------

class GreenhouseProvider(BaseProvider):
    kind = "greenhouse"
    label = "Greenhouse"
    description = "Board aziendale Greenhouse. Restituisce tutte le posizioni aperte con descrizione integrale."
    default_interval = 600
    url_example = "https://boards.greenhouse.io/gitlab"
    config_fields = [
        {"name": "token", "label": "Nome della board", "placeholder": "gitlab", "required": True,
         "help": "Il segmento finale dell'indirizzo: in boards.greenhouse.io/gitlab e' \"gitlab\"."},
    ]

    API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"

    @classmethod
    def detect(cls, url: str) -> dict[str, Any] | None:
        host = urlparse(url).netloc.lower()
        if "greenhouse.io" not in host:
            return None
        token = _token_from_path(url)
        # boards-api.greenhouse.io/v1/boards/<token>/jobs
        if token in ("v1", "embed"):
            parts = [p for p in urlparse(url).path.split("/") if p]
            token = parts[2] if len(parts) > 2 else None
        return {"token": token} if token else None

    async def fetch(self, searches: list[SearchSpec]) -> list[JobPosting]:
        token = self.config.get("token")
        if not token:
            raise ProviderError("token della board Greenhouse mancante")
        data = await self.get_json(self.API.format(token=token), params={"content": "true"})
        postings = []
        for job in data.get("jobs", []):
            location = (job.get("location") or {}).get("name", "")
            offices = ", ".join(o.get("name", "") for o in job.get("offices", []) if o.get("name"))
            departments = ", ".join(d.get("name", "") for d in job.get("departments", []) if d.get("name"))
            postings.append(
                JobPosting(
                    external_id=str(job.get("id")),
                    title=job.get("title", "").strip(),
                    company=job.get("company_name") or self.config.get("company") or token,
                    location=location or offices,
                    country=self.config.get("country", ""),
                    remote=looks_remote(location, offices, job.get("title")),
                    url=job.get("absolute_url", ""),
                    apply_url=job.get("absolute_url", ""),
                    description=html_to_text(job.get("content")),
                    department=departments,
                    posted_at=parse_date(job.get("first_published") or job.get("updated_at")),
                    raw=job,
                )
            )
        return postings


# --------------------------------------------------------------------------
# Ashby
# --------------------------------------------------------------------------

class AshbyProvider(BaseProvider):
    kind = "ashby"
    label = "Ashby"
    description = "Board aziendale Ashby. Espone descrizione in testo semplice, sede e tipo di contratto."
    default_interval = 600
    url_example = "https://jobs.ashbyhq.com/satispay"
    config_fields = [
        {"name": "token", "label": "Nome della board", "placeholder": "satispay", "required": True,
         "help": "Il segmento finale dell'indirizzo: in jobs.ashbyhq.com/satispay e' \"satispay\"."},
        {"name": "company", "label": "Nome da mostrare", "placeholder": "Satispay", "required": False},
    ]

    API = "https://api.ashbyhq.com/posting-api/job-board/{token}"

    @classmethod
    def detect(cls, url: str) -> dict[str, Any] | None:
        host = urlparse(url).netloc.lower()
        if "ashbyhq.com" not in host:
            return None
        token = _token_from_path(url)
        if token in ("posting-api", "v1"):
            token = _token_from_path(url, 2)
        return {"token": token} if token else None

    async def fetch(self, searches: list[SearchSpec]) -> list[JobPosting]:
        token = self.config.get("token")
        if not token:
            raise ProviderError("token della board Ashby mancante")
        data = await self.get_json(self.API.format(token=token), params={"includeCompensation": "true"})
        postings = []
        for job in data.get("jobs", []):
            if job.get("isListed") is False:
                continue
            address = ((job.get("address") or {}).get("postalAddress")) or {}
            compensation = job.get("compensation") or {}
            summary = (compensation.get("summaryComponents") or [{}])[0]
            postings.append(
                JobPosting(
                    external_id=str(job.get("id")),
                    title=job.get("title", "").strip(),
                    company=self.config.get("company") or token,
                    location=job.get("location", ""),
                    city=address.get("addressLocality", ""),
                    region=address.get("addressRegion", ""),
                    country=address.get("addressCountry", ""),
                    remote=bool(job.get("isRemote")) or looks_remote(job.get("workplaceType"), job.get("location")),
                    url=job.get("jobUrl", ""),
                    apply_url=job.get("applyUrl") or job.get("jobUrl", ""),
                    # descriptionPlain arriva gia' pulito: nessun HTML da smontare.
                    description=job.get("descriptionPlain") or html_to_text(job.get("descriptionHtml")),
                    employment_type=job.get("employmentType", ""),
                    department=" / ".join(p for p in (job.get("department"), job.get("team")) if p),
                    salary_min=summary.get("minValue"),
                    salary_max=summary.get("maxValue"),
                    currency=summary.get("currencyCode", "") or "",
                    posted_at=parse_date(job.get("publishedAt")),
                    raw=job,
                )
            )
        return postings


# --------------------------------------------------------------------------
# SmartRecruiters
# --------------------------------------------------------------------------

class SmartRecruitersProvider(BaseProvider):
    kind = "smartrecruiters"
    label = "SmartRecruiters"
    description = (
        "Board aziendale SmartRecruiters. Filtra lato server per paese e parola chiave; "
        "la descrizione richiede una chiamata per annuncio, quindi vengono scaricate solo le novita'."
    )
    default_interval = 600
    supports_query = True
    url_example = "https://jobs.smartrecruiters.com/BoschGroup"
    config_fields = [
        {"name": "company", "label": "Identificativo azienda", "placeholder": "Eurofins",
         "required": True,
         "help": "Il segmento finale dell'indirizzo: in jobs.smartrecruiters.com/Eurofins e' "
                 "\"Eurofins\". Attenzione alle maiuscole."},
    ]

    LIST = "https://api.smartrecruiters.com/v1/companies/{company}/postings"
    DETAIL = "https://api.smartrecruiters.com/v1/companies/{company}/postings/{posting_id}"
    PAGE = 100
    # Tetto di risultati scaricati per singolo termine di ricerca: oltre questa
    # profondita' la pertinenza cala e si spendono solo richieste.
    MAX_RESULTS_PER_TERM = 300

    @classmethod
    def detect(cls, url: str) -> dict[str, Any] | None:
        host = urlparse(url).netloc.lower()
        if "smartrecruiters.com" not in host:
            return None
        company = _token_from_path(url)
        if company in ("v1", "companies"):
            company = _token_from_path(url, 2)
        return {"company": company} if company else None

    @classmethod
    def suggested_label(cls, config: dict[str, Any]) -> str:
        return f"SmartRecruiters - {config.get('company', '')}"

    async def _list_page(self, company: str, params: dict[str, Any]) -> dict[str, Any]:
        return await self.get_json(self.LIST.format(company=company), params=params)

    async def fetch(self, searches: list[SearchSpec]) -> list[JobPosting]:
        company = self.config.get("company")
        if not company:
            raise ProviderError("identificativo azienda SmartRecruiters mancante")

        # Una richiesta per parola chiave: vedi `SearchSpec.query_terms` per il
        # motivo. Il filtro per paese riduce gia' molto il campo, quindi le
        # richieste restano poche anche su aziende con migliaia di annunci.
        # Una richiesta per parola chiave distinta: piu' ricerche salvate
        # condividono spesso le stesse chiavi, e ripeterle sarebbe traffico
        # sprecato senza un solo risultato in piu'.
        # I paesi si leggono dalla localita' delle ricerche: il campo "Paese"
        # non esiste piu' nell'interfaccia, e finche' lo si cercava li' il
        # parametro non veniva mai inviato e si scaricava la bacheca intera.
        # Ordinati, perche' l'insieme non ha un ordine e le richieste devono
        # essere le stesse a ogni giro.
        isos, _ = luogo_cercato(searches)
        queries: list[tuple[str, dict[str, Any]]] = []
        for term in unique_terms(searches):
            # Una richiesta per paese: l'API ne accetta uno solo per volta, e
            # prendere il primo voleva dire non cercare affatto per le altre
            # ricerche. I paesi sono quasi sempre uno.
            for iso in sorted(isos) or [""]:
                params: dict[str, Any] = {"limit": self.PAGE, "offset": 0}
                if term:
                    params["q"] = term
                if iso:
                    params["country"] = iso
                queries.append((term, params))

        seen: dict[str, dict[str, Any]] = {}
        # Con quale parola chiave ogni offerta e' stata trovata: come per
        # Workday, serve al filtro di pertinenza (vedi la nota piu' sotto).
        trovata_con: dict[str, str] = {}
        for term, params in queries:
            offset, total = 0, None
            while total is None or offset < min(total, self.MAX_RESULTS_PER_TERM):
                page_params = dict(params, offset=offset)
                data = await self._list_page(company, page_params)
                total = data.get("totalFound", 0)
                items = data.get("content", [])
                if not items:
                    break
                for item in items:
                    chiave = str(item.get("id"))
                    if chiave not in seen:
                        seen[chiave] = item
                        trovata_con[chiave] = term
                offset += self.PAGE

        # Come per Workday, qui ci si ferma all'elenco. La descrizione costa una
        # richiesta per annuncio e la scarica `enrich`, dopo il filtro.
        postings: list[JobPosting] = []
        for posting_id, item in seen.items():
            location = item.get("location") or {}
            # Il link ricostruito cosi' viene rediretto da SmartRecruiters
            # sull'annuncio giusto anche senza chiamare il dettaglio.
            posting_url = (item.get("postingUrl")
                           or f"https://jobs.smartrecruiters.com/{company}/{posting_id}")
            # La parola con cui il portale ha trovato l'offerta. SmartRecruiters
            # la cerca nel testo completo dell'annuncio, che qui non c'e'
            # ancora: senza questa annotazione il filtro di pertinenza la
            # ricercava nel solo titolo e scartava offerte buone. Vale finche'
            # la descrizione non arriva (vedi `_parola_gia_cercata`).
            raw = dict(item)
            if trovata_con.get(posting_id):
                raw["query"] = trovata_con[posting_id]
            postings.append(
                JobPosting(
                    external_id=posting_id,
                    title=item.get("name", "").strip(),
                    company=(item.get("company") or {}).get("name", company),
                    location=location.get("fullLocation") or location.get("city", ""),
                    city=location.get("city", ""),
                    region=location.get("region", ""),
                    country=(location.get("country") or "").lower(),
                    remote=bool(location.get("remote")),
                    url=posting_url,
                    apply_url=item.get("applyUrl") or posting_url,
                    description="",
                    employment_type=(item.get("typeOfEmployment") or {}).get("label", ""),
                    department=(item.get("function") or {}).get("label", ""),
                    posted_at=parse_date(item.get("releasedDate")),
                    raw=raw,
                )
            )
        return postings

    async def enrich(self, postings: list[JobPosting]) -> None:
        company = self.config.get("company")
        if not company:
            return
        budget = self.detail_budget
        for posting in postings:
            if budget <= 0:
                break
            if posting.description or posting.external_id in self.known_ids:
                continue
            budget -= 1
            try:
                detail = await self.get_json(
                    self.DETAIL.format(company=company, posting_id=posting.external_id)
                )
            except ProviderError:
                continue
            sections = ((detail.get("jobAd") or {}).get("sections") or {})
            posting.description = "\n\n".join(
                html_to_text(sections.get(name, {}).get("text"))
                for name in ("jobDescription", "qualifications",
                             "companyDescription", "additionalInformation")
                if sections.get(name, {}).get("text")
            )
            posting.url = detail.get("postingUrl") or posting.url
            posting.apply_url = detail.get("applyUrl") or posting.apply_url


# --------------------------------------------------------------------------
# Workable
# --------------------------------------------------------------------------

class WorkableProvider(BaseProvider):
    kind = "workable"
    label = "Workable"
    description = "Board aziendale Workable, molto diffusa fra le aziende europee di media dimensione."
    default_interval = 600
    url_example = "https://apply.workable.com/nome-azienda/"
    config_fields = [
        {"name": "token", "label": "Nome della board", "placeholder": "nome-azienda",
         "required": True,
         "help": "Il segmento dopo apply.workable.com/, oppure il sottodominio in "
                 "nome-azienda.workable.com."},
    ]

    API = "https://apply.workable.com/api/v1/widget/accounts/{token}"

    @classmethod
    def detect(cls, url: str) -> dict[str, Any] | None:
        host = urlparse(url).netloc.lower()
        if "workable.com" not in host:
            return None
        # Due forme: apply.workable.com/<token>/ oppure <token>.workable.com
        token = _token_from_path(url)
        if not token and host.endswith(".workable.com"):
            candidate = host.split(".")[0]
            token = candidate if candidate not in ("apply", "www") else None
        if token in ("api", "j"):
            token = None
        return {"token": token} if token else None

    async def fetch(self, searches: list[SearchSpec]) -> list[JobPosting]:
        token = self.config.get("token")
        if not token:
            raise ProviderError("token della board Workable mancante")
        data = await self.get_json(self.API.format(token=token), params={"details": "true"})
        company = data.get("name") or token
        postings = []
        for job in data.get("jobs", []):
            if job.get("state") not in (None, "published", "open"):
                continue
            city = job.get("city", "") or ""
            country = job.get("country", "") or ""
            location = ", ".join(p for p in (city, job.get("state_code") or "", country) if p)
            body = "\n\n".join(
                html_to_text(job.get(f))
                for f in ("description", "requirements", "benefits")
                if job.get(f)
            )
            postings.append(
                JobPosting(
                    external_id=str(job.get("id") or job.get("shortcode")),
                    title=job.get("title", "").strip(),
                    company=company,
                    location=location,
                    city=city,
                    country=(job.get("country_code") or "").lower(),
                    remote=bool(job.get("telecommuting")) or looks_remote(location, job.get("title")),
                    url=job.get("url") or job.get("shortlink", ""),
                    apply_url=job.get("application_url") or job.get("url", ""),
                    description=body,
                    employment_type=job.get("employment_type", "") or "",
                    department=job.get("department", "") or "",
                    posted_at=parse_date(job.get("published_on") or job.get("created_at")),
                    raw=job,
                )
            )
        return postings


# --------------------------------------------------------------------------
# Workday
# --------------------------------------------------------------------------

_LOCALE_RE = re.compile(r"^[a-z]{2}-[A-Za-z]{2}$")


class WorkdayProvider(BaseProvider):
    kind = "workday"
    label = "Workday"
    description = (
        "Portale carriere Workday, la piattaforma delle grandi aziende farmaceutiche "
        "(Novartis, Sanofi, AstraZeneca, GSK). Filtra lato server per parola chiave e "
        "per la localita' della ricerca - paese, regione o citta' - e restituisce la "
        "descrizione integrale dell'annuncio."
    )
    supports_query = True
    default_interval = 900
    url_example = "https://novartis.wd3.myworkdayjobs.com/Novartis_Careers"
    config_fields = [
        {"name": "tenant", "label": "Azienda (tenant)", "placeholder": "sanofi", "required": True,
         "help": "Il primo pezzo dell'indirizzo: in sanofi.wd3.myworkdayjobs.com e' \"sanofi\"."},
        {"name": "datacenter", "label": "Data center", "placeholder": "wd3", "required": True,
         "help": "Il pezzo subito dopo: wd1, wd3, wd5, wd103... Va copiato esattamente."},
        {"name": "site", "label": "Nome del sito carriere", "placeholder": "SanofiCareers",
         "required": True,
         "help": "Il primo segmento dopo il dominio, senza la lingua: SanofiCareers, "
                 "Novartis_Careers, Careers. Attenzione alle maiuscole."},
        {"name": "company", "label": "Nome da mostrare", "placeholder": "Sanofi", "required": False,
         "help": "Facoltativo: come compare l'azienda nell'elenco delle offerte."},
    ]

    PAGE = 20
    MAX_PAGES = 5

    @classmethod
    def detect(cls, url: str) -> dict[str, Any] | None:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if "myworkdayjobs.com" not in host:
            return None
        # La forma dell'host e' <tenant>.<datacenter>.myworkdayjobs.com
        host_parts = host.split(".")
        if len(host_parts) < 4:
            return None
        tenant, datacenter = host_parts[0], host_parts[1]

        segments = [s for s in parsed.path.split("/") if s]
        # Se e' stato incollato direttamente l'indirizzo dell'API
        # (/wday/cxs/<tenant>/<sito>/jobs) il nome del sito e' il quarto pezzo.
        if segments[:2] == ["wday", "cxs"]:
            site = segments[3] if len(segments) > 3 else None
        else:
            # Altrimenti si scarta l'eventuale segmento di lingua (en-US, it-IT).
            segments = [s for s in segments if not _LOCALE_RE.match(s)]
            site = segments[0] if segments else None
        if not site:
            return None
        return {"tenant": tenant, "datacenter": datacenter, "site": site}

    @classmethod
    def suggested_label(cls, config: dict[str, Any]) -> str:
        tenant = config.get("company") or (config.get("tenant") or "").capitalize()
        return f"Workday - {tenant}" if tenant else "Workday"

    # Combinazioni con cui le aziende battezzano il proprio portale. Servono
    # alla ricerca automatica: molte aziende (Thermo Fisher fra queste) mettono
    # davanti a Workday un sito con marchio proprio che non lascia trapelare
    # l'indirizzo sottostante, quindi da soli quei valori non si trovano.
    DATACENTERS = ["wd1", "wd3", "wd5", "wd103", "wd12", "wd2", "wd10"]
    SITE_PATTERNS = [
        "{T}Careers", "Careers", "{T}_Careers", "{t}", "{T}", "External",
        "ExternalCareers", "External_Career_Site", "{T}JobSearch", "Search",
        "{t}careers", "{T}CareersSite", "CareerSite", "jobs",
    ]

    @classmethod
    async def discover(cls, name: str, http: httpx.AsyncClient) -> list[dict[str, Any]]:
        """Cerca il portale Workday di un'azienda partendo dal solo nome.

        Prima verifica quali data center rispondono per quel tenant, poi prova
        su quelli i nomi di sito piu' diffusi. Restituisce le combinazioni che
        funzionano davvero, con il numero di offerte trovate.
        """
        tenant = re.sub(r"[^a-z0-9-]", "", (name or "").strip().lower())
        if not tenant:
            return []
        titolo = tenant.capitalize()
        siti = []
        for pattern in cls.SITE_PATTERNS:
            candidato = pattern.format(t=tenant, T=titolo)
            if candidato not in siti:
                siti.append(candidato)

        async def raggiungibile(dc: str) -> str | None:
            try:
                r = await http.get(f"https://{tenant}.{dc}.myworkdayjobs.com/", timeout=12)
                return dc if r.status_code < 500 else None
            except httpx.HTTPError:
                return None

        attivi = [dc for dc in await asyncio.gather(*(raggiungibile(d) for d in cls.DATACENTERS)) if dc]
        if not attivi:
            return []

        async def prova(dc: str, site: str) -> dict[str, Any] | None:
            url = f"https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
            try:
                r = await http.post(url, json={"appliedFacets": {}, "limit": 1, "offset": 0,
                                               "searchText": ""}, timeout=15)
                if r.status_code != 200:
                    return None
                totale = r.json().get("total")
            except (httpx.HTTPError, ValueError):
                return None
            if totale is None:
                return None
            return {"tenant": tenant, "datacenter": dc, "site": site, "total": totale}

        esiti = await asyncio.gather(*(prova(dc, s) for dc in attivi for s in siti))
        return [e for e in esiti if e]

    def _base(self) -> str:
        c = self.config
        return (f"https://{c['tenant']}.{c['datacenter']}.myworkdayjobs.com"
                f"/wday/cxs/{c['tenant']}/{c['site']}")

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base()}/jobs"
        try:
            response = await self.http.post(url, json=payload, headers={"Accept": "application/json"})
        except httpx.HTTPError as exc:
            raise ProviderError(f"rete: {exc}") from exc
        if response.status_code in (404, 422):
            raise ProviderError(
                "portale Workday non trovato: controlla che l'indirizzo contenga il nome "
                "esatto del sito carriere, per esempio .../Novartis_Careers"
            )
        if response.status_code == 429:
            raise ProviderError("troppe richieste (429): allunga l'intervallo di questo provider")
        if response.status_code >= 400:
            raise ProviderError(f"HTTP {response.status_code}: {response.text[:180]}")
        try:
            return response.json()
        except ValueError as exc:
            raise ProviderError("risposta non JSON dal portale Workday") from exc

    # Nomi con cui i vari tenant battezzano la faccetta del paese. Workday non
    # li uniforma: Novartis usa "locationCountry" annidato, IQVIA un
    # "Location_Country" di primo livello, altri non ce l'hanno affatto.
    _COUNTRY_PARAMS = ("locationcountry", "country")

    @staticmethod
    def _facet_groups(payload: dict[str, Any]):
        """Scorre le faccette sia di primo livello sia annidate."""
        for facet in payload.get("facets", []):
            yield facet
            for value in facet.get("values", []):
                if isinstance(value, dict) and "values" in value:
                    yield value

    _SEDI_PARAMS = ("locations", "location")

    @staticmethod
    def _in_country(descriptor: str, iso: str) -> bool:
        """Se una sede appartiene al paese indicato, dato il suo codice ISO.

        I tenant scrivono il paese dove capita e in forme diverse: in coda
        ("Monza, Italy" - Thermo Fisher), in testa per nome ("Italy - Catania" -
        AstraZeneca) o in testa in codice ("ITA - Lazio - Roma" - MSD). Cercare
        una sottostringa dentro la sede intera vuol dire indovinare l'ordine e
        la forma: si guarda invece ogni pezzo, e ne basta uno che sia il paese.
        """
        return any(paesi.pezzo_e_paese(p, iso) for p in paesi.segmenti(descriptor))

    @staticmethod
    def _luogo_nel_pezzo(luogo: str, pezzo: str) -> bool:
        """Se un pezzo di sede nomina il luogo cercato, in una delle sue lingue.

        Il nome deve comparire per parola intera: la sede puo' portarsi dietro
        l'edificio ("Bengaluru Luxor North Tower", "Milan Office") e allora la
        citta' e' solo una parte del pezzo, ma dev'essere una parola sua.

        Il confronto va in una direzione sola, e non e' un dettaglio. Cercare
        anche il pezzo dentro il nome - come fa `place_matches`, che nasce per
        confrontare sedi intere - qui produce disastri silenziosi: le sigle
        degli stati americani sono lunghe due lettere, "MA" sta dentro "Roma",
        "AZ" dentro "Lazio" e "IL" dentro "Milano", e una ricerca su Roma
        tornava con le offerte di Boston.
        """
        piatto = normalize(pezzo)
        if not piatto:
            return False
        return any(
            variante and re.search(
                rf"(?<![a-z0-9]){re.escape(variante)}(?![a-z0-9])", piatto)
            for variante in place_variants(luogo)
        )

    @classmethod
    def _sede_cercata(cls, descriptor: str, isos: set[str], luoghi: list[str]) -> bool:
        """Se una sede del portale e' fra quelle che le ricerche chiedono.

        Il paese, quando lo si conosce, e' un vincolo: "Milano" non deve
        pescare la Milan del Tennessee. Il luogo si confronta pezzo per pezzo,
        con le varianti di lingua, perche' la ricerca dice "Lombardia" e il
        portale scrive "Lombardy".
        """
        if isos and not any(cls._in_country(descriptor, i) for i in isos):
            return False
        pezzi = paesi.segmenti(descriptor)
        return any(cls._luogo_nel_pezzo(luogo, pezzo)
                   for luogo in luoghi for pezzo in pezzi)

    @classmethod
    def _gruppo(cls, payload: dict[str, Any], nomi: tuple[str, ...]):
        """La faccetta che si chiama in uno dei modi dati, con i suoi valori.

        Il nome si confronta senza trattini bassi: la stessa faccetta e'
        "locationCountry" per Novartis e "Location_Country" per IQVIA.
        """
        for group in cls._facet_groups(payload):
            parametro = str(group.get("facetParameter") or "")
            if parametro.replace("_", "").lower() in nomi:
                return parametro, [v for v in group.get("values", []) if v.get("id")]
        return "", []

    @classmethod
    def _location_facets(cls, payload: dict[str, Any], isos: set[str],
                         luoghi: list[str]) -> dict[str, list[str]] | None:
        """Il filtro da applicare lato server per la localita' delle ricerche.

        Restituisce `{}` se quello che si cerca non esiste in questo portale,
        un dizionario di faccette se il filtro e' possibile, e `None` se la
        struttura di questo tenant non permette di filtrare.

        Gli identificativi non sono documentati da Workday ma compaiono nella
        risposta stessa: leggerli a ogni giro evita di scriverli a mano e
        regge i cambiamenti.
        """
        sedi_par, sedi_val = cls._gruppo(payload, cls._SEDI_PARAMS)
        paese_par, paese_val = cls._gruppo(payload, cls._COUNTRY_PARAMS)

        # 1. La ricerca nomina una citta' o una regione: l'elenco delle sedi e'
        #    il filtro piu' stretto che il portale sappia applicare.
        if luoghi and sedi_val:
            ids = [v["id"] for v in sedi_val
                   if cls._sede_cercata(v.get("descriptor", ""), isos, luoghi)]
            if ids:
                return {sedi_par: ids[:80]}
            # Nessuna sede con quel nome. Non vuol dire che non ci sia niente
            # da cercare: le sedi hanno nomi propri - "Italy - Rosia" e' in
            # Toscana - e chi scrive "Toscana" non li conosce. Si ripiega sul
            # paese, e la localita' la ricontrolla il filtro di pertinenza.

        if not isos:
            # Un luogo che il portale non conosce e nessun paese: non si sa
            # nemmeno in che parte del mondo guardare. Meglio dichiararlo che
            # scaricare il mondo intero.
            return None

        # 2. Faccetta dedicata al paese.
        if paese_val:
            ids = [v["id"] for v in paese_val
                   if any(paesi.pezzo_e_paese(v.get("descriptor", ""), i) for i in isos)]
            return {paese_par: ids} if ids else {}

        # 3. Nessuna faccetta paese: molti tenant (Thermo Fisher, AstraZeneca,
        #    MSD) espongono solo le singole sedi. Si prendono quelle del paese.
        if sedi_val:
            ids = [v["id"] for v in sedi_val
                   if any(cls._in_country(v.get("descriptor", ""), i) for i in isos)]
            return {sedi_par: ids[:80]} if ids else {}

        # 4. Struttura sconosciuta: non si puo' filtrare lato server.
        return None


    async def fetch(self, searches: list[SearchSpec]) -> list[JobPosting]:
        config = self.config
        if not all(config.get(k) for k in ("tenant", "datacenter", "site")):
            raise ProviderError("configurazione Workday incompleta (tenant, datacenter, sito)")

        specs = searches or [SearchSpec()]
        # Una prima chiamata a vuoto serve a leggere le faccette disponibili.
        probe = await self._post({"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""})

        isos, luoghi = luogo_cercato(specs)
        facets: dict[str, list[str]] = {}
        pagine = self.MAX_PAGES
        if isos or luoghi:
            trovato = self._location_facets(probe, isos, luoghi)
            if trovato is None:
                # Struttura non riconosciuta: si scarica comunque, ma poco, e
                # il filtro di pertinenza fara' il resto a valle.
                log.info("%s: filtro per localita' non disponibile, scarico ridotto",
                         config["tenant"])
                pagine = 2
            elif not trovato:
                # La localita' cercata non ha posizioni aperte. Proseguire
                # senza filtro scaricherebbe il mondo intero per poi buttarlo:
                # e' quello che accadeva con AstraZeneca, 306 offerte scaricate
                # e zero utili.
                log.info("%s: nessuna posizione in %s, niente da scaricare",
                         config["tenant"],
                         ", ".join(sorted(isos)) or ", ".join(luoghi))
                return []
            else:
                facets = trovato

        collected: dict[str, dict[str, Any]] = {}
        # Con quale parola chiave ogni offerta e' stata trovata. Serve al filtro
        # di pertinenza: vedi la nota dove viene scritta in `raw`.
        trovata_con: dict[str, str] = {}
        for term in unique_terms(specs):
            offset = 0
            for _ in range(pagine):
                data = await self._post({
                    "appliedFacets": facets,
                    "limit": self.PAGE,
                    "offset": offset,
                    "searchText": term,
                })
                postings = data.get("jobPostings", [])
                if not postings:
                    break
                prima = len(collected)
                for item in postings:
                    path = item.get("externalPath") or ""
                    if path and path not in collected:
                        collected[path] = item
                        trovata_con[path] = term
                # Termini diversi restituiscono in gran parte le stesse offerte:
                # se una pagina non porta nulla di nuovo, continuare a paginare
                # e' solo traffico sprecato.
                if len(collected) == prima:
                    break
                offset += self.PAGE
                if offset >= min(int(data.get("total") or 0), self.PAGE * pagine):
                    break

        site_url = (f"https://{config['tenant']}.{config['datacenter']}.myworkdayjobs.com"
                    f"/{config['site']}")
        company = config.get("company") or config["tenant"].replace("-", " ").title()

        # Il paese da attribuire a un'offerta che non lo dichiara: quello
        # cercato, ma solo se le ricerche ne chiedevano uno solo. Con due paesi
        # in ballo non si puo' sapere quale sia, e attribuirne uno a caso
        # farebbe scartare l'offerta dal filtro dell'altra ricerca.
        paese_unico = paesi.INGLESE.get(next(iter(isos)), "").title() if len(isos) == 1 else ""

        # Qui ci si ferma all'elenco: la descrizione costa una richiesta per
        # annuncio e viene scaricata da `enrich`, dopo il filtro di pertinenza.
        results: list[JobPosting] = []
        for path, item in collected.items():
            location = item.get("locationsText", "") or ""
            pezzi = paesi.segmenti(location)
            # La citta' e' il pezzo piu' preciso, cioe' l'ultimo che non sia il
            # paese: "ITA - Lazio - Roma" e' Roma, "Monza, Italy" e' Monza.
            # Prendere il primo pezzo dava "ITA" a tutte le offerte di MSD.
            citta = next((p for p in reversed(pezzi) if not paesi.codice_o_sigla(p)), "")
            # Il paese scritto nella sede, se si riconosce, vale piu' di quello
            # supposto: nei portali che elencano piu' sedi ("5 Locations") non
            # c'e', e li' l'unica informazione e' il filtro che l'ha trovata.
            iso_sede = next((c for c in map(paesi.codice_o_sigla, pezzi) if c), "")
            # La parola con cui il portale ha trovato questa offerta viaggia
            # dentro `raw`. Workday cerca nel testo integrale dell'annuncio; il
            # filtro di pertinenza, che gira prima di `enrich`, ha in mano
            # soltanto titolo, azienda e sede, e cercandovi la stessa parola
            # buttava via quasi tutto: "laboratorio" trova "QC chemical Lab
            # Internship", ma nel titolo quella parola non c'e'. Con questa
            # annotazione il filtro riconosce che la selezione l'ha gia' fatta
            # il portale, che sul testo aveva piu' informazioni di noi. Vale
            # solo finche' la descrizione non c'e': appena arriva, a decidere
            # torna il testo dell'annuncio (vedi `_parola_gia_cercata`).
            raw = dict(item)
            if trovata_con.get(path):
                raw["query"] = trovata_con[path]
            results.append(
                JobPosting(
                    external_id=path,
                    title=(item.get("title") or "").strip(),
                    company=company,
                    location=location,
                    city=citta,
                    country=paesi.INGLESE.get(iso_sede, "").title() or paese_unico,
                    remote=looks_remote(location, item.get("title")),
                    url=f"{site_url}{path}",
                    apply_url=f"{site_url}{path}",
                    description="",
                    employment_type=item.get("timeType", "") or "",
                    posted_at=None,
                    raw=raw,
                )
            )
        return results

    async def enrich(self, postings: list[JobPosting]) -> None:
        budget = self.detail_budget
        for posting in postings:
            if budget <= 0:
                break
            if posting.description or posting.external_id in self.known_ids:
                continue
            budget -= 1
            try:
                detail = await self.get_json(f"{self._base()}{posting.external_id}")
            except ProviderError:
                continue
            info = detail.get("jobPostingInfo", {})
            posting.description = html_to_text(info.get("jobDescription"))
            posting.posted_at = parse_date(info.get("startDate")) or posting.posted_at
            posting.employment_type = info.get("timeType") or posting.employment_type
            paese = info.get("country")
            if isinstance(paese, dict) and paese.get("descriptor"):
                posting.country = paese["descriptor"]
            # Quando un annuncio ha piu' sedi, l'elenco riporta un segnaposto
            # ("14 Locations") invece del luogo. Il dettaglio ha quello vero.
            sede = info.get("location")
            if sede and not str(sede).strip().lower().endswith("locations"):
                posting.location = str(sede)
                posting.city = str(sede).split(",")[0].strip()


# --------------------------------------------------------------------------
# Recruitee
# --------------------------------------------------------------------------

class RecruiteeProvider(BaseProvider):
    kind = "recruitee"
    label = "Recruitee"
    description = "Board aziendale Recruitee, sul sottodominio dell'azienda."
    default_interval = 600
    url_example = "https://nome-azienda.recruitee.com"
    config_fields = [
        {"name": "token", "label": "Sottodominio dell'azienda", "placeholder": "nome-azienda",
         "required": True,
         "help": "Il primo pezzo dell'indirizzo: in nome-azienda.recruitee.com e' \"nome-azienda\"."},
    ]

    API = "https://{token}.recruitee.com/api/offers/"

    @classmethod
    def detect(cls, url: str) -> dict[str, Any] | None:
        host = urlparse(url).netloc.lower()
        if not host.endswith("recruitee.com"):
            return None
        token = host.split(".")[0]
        return {"token": token} if token and token != "recruitee" else None

    async def fetch(self, searches: list[SearchSpec]) -> list[JobPosting]:
        token = self.config.get("token")
        if not token:
            raise ProviderError("sottodominio Recruitee mancante")
        data = await self.get_json(self.API.format(token=token))
        postings = []
        for job in data.get("offers", []):
            if job.get("status") not in (None, "published"):
                continue
            body = "\n\n".join(
                html_to_text(job.get(f)) for f in ("description", "requirements") if job.get(f)
            )
            postings.append(
                JobPosting(
                    external_id=str(job.get("id")),
                    title=job.get("title", "").strip(),
                    company=job.get("company_name") or self.config.get("company") or token,
                    location=job.get("location", "") or "",
                    city=job.get("city", "") or "",
                    country=(job.get("country_code") or "").lower(),
                    remote=bool(job.get("remote")) or looks_remote(job.get("location")),
                    url=job.get("careers_url") or job.get("url", ""),
                    apply_url=job.get("careers_apply_url") or job.get("careers_url", ""),
                    description=body,
                    employment_type=job.get("employment_type_code", "") or "",
                    department=job.get("department", "") or "",
                    posted_at=parse_date(job.get("published_at") or job.get("created_at")),
                    raw=job,
                )
            )
        return postings
