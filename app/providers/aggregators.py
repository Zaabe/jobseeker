"""Adapter per gli aggregatori multi-azienda.

A differenza degli ATS, che coprono una singola azienda, queste fonti cercano
su tutto il mercato. Adzuna e' quella con la copertura italiana migliore ed e'
l'unica che richiede una chiave (gratuita).
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from ..config import SECRETS
from .base import (
    BaseProvider,
    JobPosting,
    ProviderError,
    SearchSpec,
    coppie_ricerca_termine,
    html_to_text,
    looks_remote,
    parse_date,
    unique_terms,
)


# --------------------------------------------------------------------------
# Adzuna
# --------------------------------------------------------------------------

class AdzunaProvider(BaseProvider):
    kind = "adzuna"
    label = "Adzuna"
    description = (
        "Aggregatore generalista con buona copertura italiana. Richiede due chiavi "
        "gratuite da developer.adzuna.com, da mettere nel file .env."
    )
    needs_credentials = True
    supports_query = True
    default_interval = 300
    url_example = "https://www.adzuna.it/"
    config_fields = [
        {"name": "country", "label": "Paese", "placeholder": "it", "required": False,
         "help": "Codice a due lettere del mercato Adzuna: it, fr, de, es, gb..."},
    ]

    API = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
    MAX_PAGES = 3
    PER_PAGE = 50

    @classmethod
    def detect(cls, url: str) -> dict[str, Any] | None:
        host = urlparse(url).netloc.lower()
        if "adzuna." not in host:
            return None
        # adzuna.it -> paese "it", adzuna.co.uk -> "gb"
        suffix = host.rsplit(".", 1)[-1]
        country = {"uk": "gb", "com": "gb"}.get(suffix, suffix)
        return {"country": country}

    def _credentials(self) -> tuple[str, str]:
        app_id = self.config.get("app_id") or SECRETS.get("adzuna_app_id", "")
        app_key = self.config.get("app_key") or SECRETS.get("adzuna_app_key", "")
        if not app_id or not app_key:
            raise ProviderError(
                "chiavi Adzuna mancanti: registrati gratis su developer.adzuna.com e "
                "compila ADZUNA_APP_ID e ADZUNA_APP_KEY nel file .env"
            )
        return app_id, app_key

    async def fetch(self, searches: list[SearchSpec]) -> list[JobPosting]:
        app_id, app_key = self._credentials()
        default_country = self.config.get("country", "it")
        if not searches:
            return []

        collected: dict[str, JobPosting] = {}
        # Una richiesta per parola chiave: `what` con troppi termini restringe
        # il risultato fino a svuotarlo. Le coppie arrivano col tetto gia'
        # applicato: qui la stessa parola in due ricerche non e' un doppione,
        # perche' `where` e `what_exclude` sono quelli della singola ricerca.
        for spec, term in coppie_ricerca_termine(searches):
            country = (spec.country or default_country or "it").lower()
            base_params = {
                "app_id": app_id,
                "app_key": app_key,
                "results_per_page": self.PER_PAGE,
                "content-type": "application/json",
                "sort_by": "date",
                # Solo annunci recenti: il resto e' gia' in archivio.
                "max_days_old": self.config.get("max_days_old", 30),
            }
            if term:
                base_params["what"] = term
            if spec.location:
                base_params["where"] = spec.location
            if spec.exclude:
                base_params["what_exclude"] = " ".join(spec.exclude)

            for page in range(1, self.MAX_PAGES + 1):
                data = await self.get_json(
                    self.API.format(country=country, page=page), params=base_params
                )
                results = data.get("results", [])
                if not results:
                    break
                for job in results:
                    job_id = str(job.get("id"))
                    if job_id in collected:
                        continue
                    location = job.get("location") or {}
                    area = location.get("area") or []
                    collected[job_id] = JobPosting(
                        external_id=job_id,
                        title=job.get("title", "").strip(),
                        company=(job.get("company") or {}).get("display_name", ""),
                        location=location.get("display_name", ""),
                        city=area[-1] if area else "",
                        region=area[1] if len(area) > 1 else "",
                        country=country,
                        remote=looks_remote(location.get("display_name"), job.get("title")),
                        url=job.get("redirect_url", ""),
                        apply_url=job.get("redirect_url", ""),
                        description=html_to_text(job.get("description")),
                        employment_type=" ".join(
                            p for p in (job.get("contract_time"), job.get("contract_type")) if p
                        ),
                        department=(job.get("category") or {}).get("label", ""),
                        salary_min=job.get("salary_min"),
                        salary_max=job.get("salary_max"),
                        currency="EUR" if country == "it" else "",
                        posted_at=parse_date(job.get("created")),
                        raw=job,
                    )
                if len(results) < self.PER_PAGE:
                    break
        return list(collected.values())


# --------------------------------------------------------------------------
# The Muse
# --------------------------------------------------------------------------

class TheMuseProvider(BaseProvider):
    kind = "themuse"
    label = "The Muse"
    description = (
        "Aggregatore senza chiave con molte multinazionali. Il filtro geografico "
        "lato server e' impreciso, quindi la localita' viene ricontrollata in locale."
    )
    supports_query = True
    default_interval = 600
    url_example = "https://www.themuse.com/"

    API = "https://www.themuse.com/api/public/jobs"
    MAX_PAGES = 3

    @classmethod
    def detect(cls, url: str) -> dict[str, Any] | None:
        return {} if "themuse.com" in urlparse(url).netloc.lower() else None

    async def fetch(self, searches: list[SearchSpec]) -> list[JobPosting]:
        collected: dict[str, JobPosting] = {}
        specs = searches or [SearchSpec()]
        for spec in specs:
            params: dict[str, Any] = {"page": 1, "descending": "true"}
            if spec.location:
                params["location"] = spec.location
            for page in range(0, self.MAX_PAGES):
                params["page"] = page
                data = await self.get_json(self.API, params=params)
                results = data.get("results", [])
                if not results:
                    break
                for job in results:
                    job_id = str(job.get("id"))
                    if job_id in collected:
                        continue
                    locations = [l.get("name", "") for l in job.get("locations", [])]
                    location = "; ".join(locations)
                    categories = ", ".join(c.get("name", "") for c in job.get("categories", []))
                    collected[job_id] = JobPosting(
                        external_id=job_id,
                        title=job.get("name", "").strip(),
                        company=(job.get("company") or {}).get("name", ""),
                        location=location,
                        remote=looks_remote(location),
                        url=(job.get("refs") or {}).get("landing_page", ""),
                        apply_url=(job.get("refs") or {}).get("landing_page", ""),
                        description=html_to_text(job.get("contents")),
                        department=categories,
                        employment_type=job.get("type", "") or "",
                        posted_at=parse_date(job.get("publication_date")),
                        raw=job,
                    )
                if page + 1 >= data.get("page_count", 1):
                    break
        return list(collected.values())


# --------------------------------------------------------------------------
# Board di lavoro da remoto (nessuna chiave richiesta)
# --------------------------------------------------------------------------

class ArbeitnowProvider(BaseProvider):
    kind = "arbeitnow"
    label = "Arbeitnow"
    description = "Board europea, molte posizioni in Germania e da remoto. Nessuna chiave."
    default_interval = 600
    url_example = "https://www.arbeitnow.com/"

    API = "https://www.arbeitnow.com/api/job-board-api"

    @classmethod
    def detect(cls, url: str) -> dict[str, Any] | None:
        return {} if "arbeitnow.com" in urlparse(url).netloc.lower() else None

    async def fetch(self, searches: list[SearchSpec]) -> list[JobPosting]:
        data = await self.get_json(self.API)
        postings = []
        for job in data.get("data", []):
            postings.append(
                JobPosting(
                    external_id=str(job.get("slug")),
                    title=job.get("title", "").strip(),
                    company=job.get("company_name", ""),
                    location=job.get("location", "") or "",
                    remote=bool(job.get("remote")),
                    url=job.get("url", ""),
                    apply_url=job.get("url", ""),
                    description=html_to_text(job.get("description")),
                    employment_type=", ".join(job.get("job_types") or []),
                    department=", ".join(job.get("tags") or []),
                    posted_at=parse_date(job.get("created_at")),
                    raw=job,
                )
            )
        return postings


class RemotiveProvider(BaseProvider):
    kind = "remotive"
    label = "Remotive"
    description = "Board di sole posizioni da remoto. Nessuna chiave."
    supports_query = True
    default_interval = 600
    url_example = "https://remotive.com/"

    API = "https://remotive.com/api/remote-jobs"

    @classmethod
    def detect(cls, url: str) -> dict[str, Any] | None:
        host = urlparse(url).netloc.lower()
        return {} if "remotive.com" in host or "remotive.io" in host else None

    async def fetch(self, searches: list[SearchSpec]) -> list[JobPosting]:
        collected: dict[str, JobPosting] = {}
        specs = searches or [SearchSpec()]
        # Anche qui una richiesta per termine: il parametro `search` di Remotive
        # cerca la frase intera, non i singoli termini.
        #
        # Sull'insieme unico di tutte le ricerche, non una passata per ricerca:
        # la richiesta non dipende da nient'altro che dal termine, quindi due
        # ricerche che condividono una parola chiave facevano due volte la
        # stessa identica richiesta. E' anche il punto in cui si applica il
        # tetto contato in totale.
        for term in unique_terms(specs):
            params: dict[str, Any] = {"limit": 100}
            if term:
                params["search"] = term
            data = await self.get_json(self.API, params=params)
            for job in data.get("jobs", []):
                job_id = str(job.get("id"))
                if job_id in collected:
                    continue
                collected[job_id] = JobPosting(
                    external_id=job_id,
                    title=job.get("title", "").strip(),
                    company=job.get("company_name", ""),
                    location=job.get("candidate_required_location", "") or "",
                    remote=True,
                    url=job.get("url", ""),
                    apply_url=job.get("url", ""),
                    description=html_to_text(job.get("description")),
                    employment_type=job.get("job_type", "") or "",
                    department=job.get("category", "") or "",
                    posted_at=parse_date(job.get("publication_date")),
                    raw=job,
                )
        return list(collected.values())


class RemoteOkProvider(BaseProvider):
    kind = "remoteok"
    label = "RemoteOK"
    description = (
        "Board di posizioni da remoto, prevalentemente tecnologiche. Nessuna chiave; "
        "i termini della fonte richiedono di mantenere il link all'annuncio originale."
    )
    default_interval = 900
    url_example = "https://remoteok.com/"

    API = "https://remoteok.com/api"

    @classmethod
    def detect(cls, url: str) -> dict[str, Any] | None:
        host = urlparse(url).netloc.lower()
        return {} if "remoteok.com" in host or "remoteok.io" in host else None

    async def fetch(self, searches: list[SearchSpec]) -> list[JobPosting]:
        data = await self.get_json(self.API)
        postings = []
        for job in data:
            # Il primo elemento della risposta e' l'avviso legale, non un annuncio.
            if not isinstance(job, dict) or not job.get("id") or job.get("legal"):
                continue
            postings.append(
                JobPosting(
                    external_id=str(job.get("id")),
                    title=(job.get("position") or "").strip(),
                    company=job.get("company", ""),
                    location=job.get("location", "") or "Remote",
                    remote=True,
                    url=job.get("url", ""),
                    apply_url=job.get("apply_url") or job.get("url", ""),
                    description=html_to_text(job.get("description")),
                    department=", ".join(job.get("tags") or []),
                    salary_min=job.get("salary_min"),
                    salary_max=job.get("salary_max"),
                    currency="USD",
                    posted_at=parse_date(job.get("date") or job.get("epoch")),
                    raw=job,
                )
            )
        return postings


class JobicyProvider(BaseProvider):
    kind = "jobicy"
    label = "Jobicy"
    description = "Board di posizioni da remoto con filtro per area geografica. Nessuna chiave."
    default_interval = 900
    url_example = "https://jobicy.com/"

    API = "https://jobicy.com/api/v2/remote-jobs"

    @classmethod
    def detect(cls, url: str) -> dict[str, Any] | None:
        return {} if "jobicy.com" in urlparse(url).netloc.lower() else None

    async def fetch(self, searches: list[SearchSpec]) -> list[JobPosting]:
        params: dict[str, Any] = {"count": 50}
        if self.config.get("geo"):
            params["geo"] = self.config["geo"]
        data = await self.get_json(self.API, params=params)
        postings = []
        for job in data.get("jobs", []):
            postings.append(
                JobPosting(
                    external_id=str(job.get("id")),
                    title=(job.get("jobTitle") or "").strip(),
                    company=job.get("companyName", ""),
                    location=job.get("jobGeo", "") or "Remote",
                    remote=True,
                    url=job.get("url", ""),
                    apply_url=job.get("url", ""),
                    description=html_to_text(job.get("jobDescription") or job.get("jobExcerpt")),
                    employment_type=", ".join(job.get("jobType") or []) if isinstance(job.get("jobType"), list) else (job.get("jobType") or ""),
                    department=", ".join(job.get("jobIndustry") or []) if isinstance(job.get("jobIndustry"), list) else (job.get("jobIndustry") or ""),
                    salary_min=job.get("annualSalaryMin"),
                    salary_max=job.get("annualSalaryMax"),
                    currency=job.get("salaryCurrency", "") or "",
                    posted_at=parse_date(job.get("pubDate")),
                    raw=job,
                )
            )
        return postings
