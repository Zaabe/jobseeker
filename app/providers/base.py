"""Modello normalizzato delle offerte e classe base dei provider.

Ogni adapter traduce la risposta di una API nella stessa struttura `JobPosting`,
cosi' il resto dell'applicazione (matching, storico, notifiche) non sa nulla
della fonte da cui l'offerta arriva.
"""
from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, ClassVar

import httpx

from .. import paesi


log = logging.getLogger("jobseeker.providers")


# --------------------------------------------------------------------------
# Utilita' di testo
# --------------------------------------------------------------------------

class _TextExtractor(HTMLParser):
    """Converte HTML in testo semplice mantenendo la struttura a paragrafi."""

    _BLOCK = {
        "p", "div", "br", "li", "ul", "ol", "tr", "table", "section", "article",
        "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in ("script", "style"):
            self._skip += 1
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


def html_to_text(raw: str | None) -> str:
    """Ripulisce una descrizione HTML riducendola a testo leggibile.

    Le API restituiscono le descrizioni in HTML (a volte doppiamente
    codificato, come Arbeitnow), quindi la de-escape va applicata due volte.
    """
    if not raw:
        return ""
    text = html.unescape(html.unescape(raw))
    if "<" in text and ">" in text:
        parser = _TextExtractor()
        try:
            parser.feed(text)
            parser.close()
            text = parser.text()
        except Exception:
            text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def parse_date(value: Any) -> str | None:
    """Normalizza in ISO-8601 UTC le date nei molti formati usati dalle API."""
    if not value:
        return None
    if isinstance(value, (int, float)):
        # Timestamp Unix, in secondi o millisecondi.
        seconds = value / 1000 if value > 1e11 else value
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat(timespec="seconds")
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    for candidate in (text, text.split(".")[0], text[:19], text[:10]):
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat(timespec="seconds")
        except ValueError:
            continue
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat(timespec="seconds")
        except ValueError:
            continue
    return None


_REMOTE_HINTS = (
    "remote", "remoto", "da remoto", "smart working", "telelavoro",
    "work from home", "fully remote", "anywhere",
)


def looks_remote(*fields: Any) -> bool:
    blob = " ".join(str(f) for f in fields if f).lower()
    return any(hint in blob for hint in _REMOTE_HINTS)


# --------------------------------------------------------------------------
# Modelli
# --------------------------------------------------------------------------

@dataclass
class JobPosting:
    """Un'offerta di lavoro, nella forma normalizzata usata da tutta l'app."""

    external_id: str
    title: str
    company: str = ""
    location: str = ""
    city: str = ""
    region: str = ""
    country: str = ""
    remote: bool = False
    url: str = ""
    apply_url: str = ""
    description: str = ""
    employment_type: str = ""
    department: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    currency: str = ""
    posted_at: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def searchable_text(self) -> str:
        return " \n".join(
            p for p in (self.title, self.company, self.department, self.location, self.description) if p
        )


# Quante parole chiave inoltrare al massimo alle API che filtrano lato server.
# Ogni termine costa almeno una richiesta, quindi un tetto ci vuole: senza, un
# dizionario da trecento voci diventa trecento richieste per fonte a ogni giro.
#
# Il tetto si conta sull'insieme unico di tutte le ricerche, non su ciascuna:
# lo applica `unique_terms`. Prima era per ricerca, e la conseguenza era che lo
# stesso gruppo di parole costava sei richieste se stava in una ricerca sola e
# trenta se era diviso in cinque - il traffico dipendeva da come le parole
# erano raggruppate, che non e' una cosa che chi le scrive abbia in mente.
MAX_QUERY_TERMS = 40


@dataclass
class SearchSpec:
    """I criteri di una ricerca salvata, passati ai provider che sanno filtrare."""

    id: int | None = None
    name: str = ""
    keywords: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    location: str = ""
    country: str = "it"
    remote_ok: bool = True
    # Se scartare le offerte fuori dalla localita' indicata. E' una scelta della
    # singola ricerca: applicarla a tutte perche' una la richiede farebbe
    # sparire i risultati delle altre.
    location_filter: bool = True
    # La soglia di avviso di questa ricerca, o None per quella generale. Le
    # fonti non la guardano - non filtrano per punteggio - ma sta qui perche' e'
    # una proprieta' della ricerca, e chi decide gli avvisi ha gia' le specs in
    # mano.
    min_match: int | None = None

    @property
    def query(self) -> str:
        return " ".join(self.keywords).strip()

    @property
    def query_terms(self) -> list[str]:
        """Le parole chiave da inviare **una per richiesta**.

        Concatenarle in un'unica stringa non funziona: i motori di ricerca dei
        portali le trattano come una congiunzione, e piu' termini si aggiungono
        piu' il risultato si svuota (con otto parole SmartRecruiters restituisce
        zero offerte, con "laboratorio" da sola ventidue). Una richiesta per
        termine, e i risultati si uniscono a valle.

        La lista vuota diventa `[""]`, cioe' una passata senza filtro testuale.

        Qui non si taglia niente: il tetto lo applicano `unique_terms` e
        `coppie_ricerca_termine`, che sono i due modi in cui le fonti
        consumano i termini. Tagliare anche qui sembrava prudenza e invece era
        un tranello: con tutte le parole in una ricerca sola il taglio avveniva
        qui, cioe' prima di arrivare al punto che lo segnala nei log, e chi
        aveva scritto sessanta parole chiave non vedeva niente.
        """
        terms = [k.strip() for k in self.keywords if k and k.strip()]
        return terms or [""]


def unique_terms(searches: list[SearchSpec]) -> list[str]:
    """I termini di ricerca da inviare, senza ripetizioni fra le ricerche.

    Piu' ricerche salvate condividono spesso le stesse parole chiave: senza
    questa deduplica la stessa identica query verrebbe inviata una volta per
    ricerca, moltiplicando il traffico senza aggiungere un solo risultato.
    """
    termini: list[str] = []
    for spec in searches or [SearchSpec()]:
        for term in spec.query_terms:
            if term not in termini:
                termini.append(term)
    return _col_tetto(termini) or [""]


def _col_tetto(voci: list[Any]) -> list[Any]:
    """Applica il tetto, e lo dice.

    Restare zitti significa che chi ha scritto sessanta parole chiave crede
    che vengano cercate tutte.
    """
    if len(voci) <= MAX_QUERY_TERMS:
        return voci
    log.info("%d parole chiave nelle ricerche, uso le prime %d: oltre quel "
             "numero le richieste crescono piu' dei risultati",
             len(voci), MAX_QUERY_TERMS)
    return voci[:MAX_QUERY_TERMS]


def coppie_ricerca_termine(searches: list[SearchSpec]) -> list[tuple[SearchSpec, str]]:
    """Le coppie (ricerca, termine) da interrogare, col tetto contato in totale.

    Serve a chi non puo' lavorare sull'insieme unico dei termini, perche' ogni
    ricerca porta anche parametri suoi: Adzuna manda la localita' e le
    esclusioni della singola ricerca, quindi la stessa parola chiave in due
    ricerche diverse e' davvero una richiesta diversa e non un doppione.

    Il tetto e' lo stesso di `unique_terms`, cosi' il numero di richieste per
    giro non dipende da quale fonte lo sta consumando.
    """
    coppie: list[tuple[SearchSpec, str]] = []
    for spec in searches or [SearchSpec()]:
        for term in spec.query_terms:
            coppie.append((spec, term))
    return _col_tetto(coppie)


def luogo_cercato(searches: list[SearchSpec]) -> tuple[set[str], list[str]]:
    """I paesi e i luoghi chiesti dalle ricerche, letti dalla localita'.

    La localita' e' testo libero e puo' essere un paese ("Italia"), una regione
    ("Lombardia"), una citta' ("Roma") o una combinazione di questi ("Milano -
    Lombardia, Italia"). Il paese, quando c'e', si restituisce a parte: e' il
    solo filtro che tutti i portali sappiano applicare, e quasi tutti lo
    vogliono come codice a due lettere.

    Prima ogni adapter leggeva `spec.country` per conto proprio, e cioe' due
    cose sbagliate. La prima: quel campo non esiste piu' nell'interfaccia,
    quindi una ricerca su "Milano" non aveva alcun paese e il portale veniva
    interrogato senza filtro geografico - si scaricavano offerte da tutto il
    mondo per poi buttarle a valle. La seconda: si prendeva il paese della
    *prima* ricerca che ne avesse uno, e le altre non contavano niente.
    """
    isos: set[str] = set()
    luoghi: list[str] = []
    for spec in searches or []:
        sede = (spec.location or "").strip()
        # Il campo scritto ha la precedenza, per le ricerche salvate quando
        # esisteva; poi si guarda la coda della localita' ("Milano, Italia") e
        # infine un paese nominato in mezzo al testo.
        iso = ((spec.country or "").strip().lower()
               or paesi.codice_dalla_sede(sede)
               or paesi.paese_nel_testo(sede))
        if iso:
            isos.add(iso)
        for pezzo in paesi.segmenti(sede):
            # Il paese l'ha gia' preso la riga qui sopra: lasciarlo anche fra i
            # luoghi lo trasformerebbe in una sede da cercare.
            if paesi.codice(pezzo) or pezzo in luoghi:
                continue
            luoghi.append(pezzo)
    return isos, luoghi


class ProviderError(RuntimeError):
    """Errore recuperabile di un provider: viene registrato, non fa cadere il ciclo."""


# --------------------------------------------------------------------------
# Classe base
# --------------------------------------------------------------------------

class BaseProvider:
    """Interfaccia comune a tutti gli adapter.

    Un adapter deve dichiarare `kind` e `label`, implementare `fetch()` e,
    se puo' essere aggiunto incollando un URL, il metodo di classe `detect()`.
    """

    kind: ClassVar[str] = ""
    label: ClassVar[str] = ""
    # Descrizione mostrata nell'interfaccia quando si aggiunge la fonte.
    description: ClassVar[str] = ""
    # True se servono chiavi API configurate nel file .env.
    needs_credentials: ClassVar[bool] = False
    # True se l'API filtra lato server per parole chiave/localita'.
    supports_query: ClassVar[bool] = False
    # Intervallo minimo consigliato fra due interrogazioni, in secondi.
    default_interval: ClassVar[int] = 300
    # Esempio di URL accettato, mostrato come suggerimento nell'interfaccia.
    url_example: ClassVar[str] = ""
    # Campi di configurazione da compilare a mano quando non si vuole (o non si
    # puo') incollare un URL. L'interfaccia costruisce il modulo da qui, quindi
    # un provider nuovo ottiene il suo modulo senza toccare il frontend.
    # Ogni voce: name, label, placeholder, required, help.
    config_fields: ClassVar[list[dict[str, Any]]] = []

    def __init__(self, config: dict[str, Any], http: httpx.AsyncClient) -> None:
        self.config = config or {}
        self.http = http
        # Popolato dal runner con gli external_id delle offerte di cui
        # l'archivio ha gia' la descrizione. Serve agli adapter che devono fare
        # una chiamata di dettaglio per ogni offerta (SmartRecruiters, Workday,
        # LinkedIn): per quelle non c'e' niente da riscaricare.
        self.known_ids: set[str] = set()
        # Tutte le offerte gia' in archivio, con o senza descrizione. E' una
        # domanda diversa da quella di sopra e serve a chi sfoglia un elenco a
        # pagine: quando una pagina non porta piu' niente di nuovo, sotto c'e'
        # solo roba gia' vista e si puo' smettere di scaricare.
        self.id_in_archivio: set[str] = set()
        # Un foglietto che sopravvive al singolo giro: il runner lo rilegge
        # dalla riga della fonte prima di `fetch` e lo riscrive dopo. Contiene
        # quello che l'adapter ci mette (LinkedIn: a che punto dell'elenco era
        # arrivato a scendere) e dev'essere convertibile in JSON.
        self.stato: dict[str, Any] = {}
        # Tetto di chiamate di dettaglio per singolo ciclo, per non trasformare
        # un provider con migliaia di annunci in centinaia di richieste.
        self.detail_budget: int = 40
        # True quando la fonte viene interrogata da "Prova senza salvare".
        # Davanti allo schermo c'e' qualcuno che aspetta, quindi gli adapter che
        # per prudenza lavorano piano (LinkedIn: una richiesta per parola chiave
        # e pause in mezzo) possono ridursi a un solo giro.
        self.anteprima: bool = False

    # -- da implementare negli adapter ------------------------------------

    async def fetch(self, searches: list[SearchSpec]) -> list[JobPosting]:
        """Elenca le offerte. Deve restare economico: una richiesta per pagina.

        Gli adapter che per la descrizione hanno bisogno di una chiamata per
        singolo annuncio NON devono farla qui: quel lavoro va in `enrich`.
        """
        raise NotImplementedError

    async def enrich(self, postings: list[JobPosting]) -> None:
        """Completa le offerte indicate con la descrizione integrale.

        Viene chiamato **dopo** il filtro di pertinenza, e solo sulle offerte
        sopravvissute. E' la differenza fra scaricare quaranta descrizioni per
        poi buttarle tutte e scaricarne tre che servono davvero.

        Modifica gli oggetti sul posto. Chi non ha nulla da aggiungere lascia
        l'implementazione vuota.
        """
        return None

    @classmethod
    def detect(cls, url: str) -> dict[str, Any] | None:
        """Se l'URL appartiene a questo provider, restituisce la sua config."""
        return None

    @classmethod
    def suggested_label(cls, config: dict[str, Any]) -> str:
        token = config.get("token") or config.get("company") or ""
        return f"{cls.label} - {token}" if token else cls.label

    # -- helper condivisi --------------------------------------------------

    async def get_json(self, url: str, **kwargs: Any) -> Any:
        """GET con gestione uniforme degli errori HTTP."""
        try:
            response = await self.http.get(url, **kwargs)
        except httpx.HTTPError as exc:
            raise ProviderError(f"rete: {exc}") from exc
        if response.status_code == 404:
            raise ProviderError("risorsa non trovata (404): controlla il token della board")
        if response.status_code == 429:
            raise ProviderError("troppe richieste (429): rallenta l'intervallo di questo provider")
        if response.status_code >= 400:
            raise ProviderError(f"HTTP {response.status_code}: {response.text[:180]}")
        try:
            return response.json()
        except ValueError as exc:
            raise ProviderError(f"risposta non JSON: {response.text[:180]}") from exc
