"""Adapter per LinkedIn, letto dalle pagine pubbliche.

E' l'unica fonte del sistema che non parla con un'API dichiarata: LinkedIn non
ne apre una, quindi qui si leggono le pagine che il sito serve a chi non ha un
account. Tre cose vanno dette prima del codice.

1. Le condizioni d'uso di LinkedIn non ammettono la raccolta automatica dei
   contenuti. Questa fonte esiste perche' e' stata chiesta, si disattiva come
   tutte le altre, non usa le credenziali di nessuno e non tocca account.
2. L'HTML cambia senza preavviso: prima o poi questa fonte smettera' di
   restituire risultati, mentre le altre continueranno. Per questo la lettura
   e' difensiva - piu' selettori per ogni campo, e una scheda malformata viene
   saltata invece di far cadere il giro.
3. LinkedIn conta le richieste per indirizzo IP e risponde `999` a chi esagera.
   Il ritmo qui e' volutamente basso: mezz'ora di intervallo minimo, qualche
   secondo di pausa fra due richieste, e le pagine dell'elenco si sfogliano
   finche' portano offerte mai viste, con un tetto di quattro. Le descrizioni si
   scaricano solo per le offerte che hanno superato il filtro di pertinenza,
   come per SmartRecruiters e Workday.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from .. import paesi
from ..paesi import codice_dalla_sede
from .base import (
    BaseProvider,
    JobPosting,
    ProviderError,
    SearchSpec,
    html_to_text,
    looks_remote,
    parse_date,
    unique_terms,
)

try:
    # Serve solo a questo adapter: se manca, manca la fonte LinkedIn, non
    # l'applicazione. L'errore chiaro arriva quando la si prova a usare.
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - dipende dall'installazione
    BeautifulSoup = None  # type: ignore[assignment]


log = logging.getLogger("jobseeker.providers")


# Il ritmo. Sono i numeri che tengono questa fonte sotto la soglia di
# attenzione di LinkedIn: non piu' di sei parole chiave, una pausa fra due
# richieste, un tetto di pagine per parola chiave.
#
# Quante pagine leggere per parola chiave a ogni giro, e come spenderle. Le
# prime `PAGINE_IN_CIMA` guardano la testa dell'elenco, dove compaiono gli
# annunci nuovi; quelle che avanzano scendono piu' in basso, riprendendo da dove
# si era arrivati il giro prima (vedi `_sfoglia`).
#
# La divisione non e' un dettaglio: senza, una fonte che trova sempre qualcosa
# in cima spenderebbe li' tutto il budget e non scenderebbe mai. E "trovare
# qualcosa in cima" e' piu' facile di quanto sembri, perche' le offerte che il
# filtro di pertinenza scarta non finiscono in archivio e quindi risultano nuove
# a ogni giro.
#
# Quattro pagine per parola chiave sono quaranta offerte a giro e ventiquattro
# richieste nel caso peggiore, ogni mezz'ora.
MAX_TERMINI = 6
# Il valore predefinito e il tetto. Il numero si puo' alzare dalla scheda della
# fonte: piu' pagine per giro vuol dire percorrere l'elenco piu' in fretta e
# fare piu' richieste: e' il compromesso di chi la usa, non una costante di
# questo file. Oltre il tetto non si va, perche' oltre c'e' il blocco.
PAGINE_PREDEFINITE = 4
MAX_PAGINE = 20
PAGINE_IN_CIMA = 2
MAX_DETTAGLI = 15
PAUSA = 4.0

# Finestra temporale predefinita. Serve allo stesso scopo: senza filtro di data
# l'elenco di una parola chiave e' lungo migliaia di annunci e non finisce mai,
# mentre gli ultimi sette giorni sono un insieme che si esaurisce - le pagine
# finiscono davvero, e il giro successivo si ferma quasi subito. Chi vuole
# scendere piu' indietro mette un numero di giorni piu' grande, o 0 per togliere
# il limite.
GIORNI_PREDEFINITI = 7

# LinkedIn risponde 999 a chi si presenta come un programma. Presentarsi come
# un browser e' l'unico modo per ottenere le stesse pagine che il sito mostra a
# chiunque, ed e' anche il punto in cui questa fonte si allontana dalle altre.
INTESTAZIONI = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}

_VALUTE = {"€": "EUR", "$": "USD", "£": "GBP"}


class _Bloccato(ProviderError):
    """LinkedIn ha chiuso la porta: inutile insistere in questo giro."""


# --------------------------------------------------------------------------
# Lettura difensiva dell'HTML
# --------------------------------------------------------------------------

def _pulisci(valore: str) -> str:
    """Spazi normalizzati: l'HTML di LinkedIn e' pieno di rientri e a capo."""
    return re.sub(r"\s+", " ", valore or "").strip()


def _testo(nodo: Any, *selettori: str) -> str:
    """Il primo selettore che trova qualcosa, ripulito.

    I nomi delle classi di LinkedIn cambiano nel tempo: tenerne piu' di uno per
    campo costa una riga e fa la differenza fra una fonte che perde un dato e
    una che smette di funzionare.
    """
    if nodo is None:
        return ""
    for selettore in selettori:
        try:
            trovato = nodo.select_one(selettore)
        except Exception:  # selettore non valido su questa versione di bs4
            continue
        if trovato is not None:
            valore = _pulisci(trovato.get_text(" ", strip=True))
            if valore:
                return valore
    return ""


def _muro_di_accesso(pagina: str) -> bool:
    """Riconosce la pagina di accesso servita al posto dei risultati."""
    inizio = pagina[:4000].lower()
    return ("authwall" in inizio
            or "sign in to continue" in inizio
            or "accedi per continuare" in inizio
            or "join linkedin" in inizio)


def _id_offerta(scheda: Any, href: str) -> str:
    """Il numero dell'annuncio, dall'urn della scheda o dal suo link."""
    urn = scheda.get("data-entity-urn") or ""
    if not urn:
        interno = scheda.find(attrs={"data-entity-urn": True})
        urn = interno.get("data-entity-urn", "") if interno else ""
    trovato = re.search(r"jobPosting:(\d+)", urn)
    if trovato:
        return trovato.group(1)
    # Il link finisce con "-<numero>": e' lo stesso identificativo.
    trovato = re.search(r"(\d{6,})", urlparse(href).path)
    return trovato.group(1) if trovato else ""


def _url_annuncio(href: str, identificativo: str) -> str:
    """Il link dell'annuncio senza la coda di tracciamento.

    Gli href dell'elenco portano `refId`, `trackingId` e `position`, che
    cambiano a ogni richiesta: tenerli dentro l'indirizzo significa mostrare
    ogni volta un link diverso per la stessa offerta.
    """
    if href.startswith("/"):
        href = "https://www.linkedin.com" + href
    if href.startswith("http"):
        pezzi = urlparse(href)
        return f"{pezzi.scheme}://{pezzi.netloc}{pezzi.path}"
    return f"https://www.linkedin.com/jobs/view/{identificativo}"


def _numero(token: str) -> float | None:
    """Legge un numero scritto all'italiana o all'inglese.

    "30.000,00" e "30,000.00" sono lo stesso importo: l'ultimo separatore e'
    decimale solo se ha una o due cifre dopo di se', perche' le migliaia ne
    hanno sempre tre.
    """
    token = token.strip()
    if not re.fullmatch(r"\d[\d.,]*", token):
        return None
    ultimo = max(token.rfind("."), token.rfind(","))
    if ultimo >= 0 and len(token) - ultimo - 1 in (1, 2) and token.count(token[ultimo]) == 1:
        return float(re.sub(r"[.,]", "", token[:ultimo]) + "." + token[ultimo + 1:])
    return float(re.sub(r"[.,]", "", token))


def _stipendio(testo: str) -> tuple[float | None, float | None, str]:
    """La fascia di stipendio dichiarata nella scheda, quando c'e'.

    Si tengono solo gli importi da mille in su: sotto quella soglia si trovano
    paghe orarie e numeri di contorno, e la scheda non dice a quale periodo si
    riferiscono, quindi salvarli darebbe un dato falso invece di un dato assente.
    """
    if not testo:
        return None, None, ""
    valuta = next((codice for simbolo, codice in _VALUTE.items() if simbolo in testo), "")
    if not valuta:
        trovato = re.search(r"\b(EUR|USD|GBP|CHF)\b", testo.upper())
        valuta = trovato.group(1) if trovato else ""
    importi = sorted({n for n in (_numero(t) for t in re.findall(r"\d[\d.,]*", testo))
                      if n and n >= 1000})
    if not importi:
        return None, None, valuta
    return importi[0], (importi[-1] if len(importi) > 1 else None), valuta


def _sede(testo: str) -> tuple[str, str]:
    """Citta' e regione da "Milano, Lombardia, Italia"."""
    pezzi = [p.strip() for p in (testo or "").split(",") if p.strip()]
    if len(pezzi) < 2:
        return "", ""
    return pezzi[0], pezzi[1]


def _primo(valore: Any) -> str:
    """Il JSON-LD alterna stringhe e liste per lo stesso campo."""
    if isinstance(valore, list):
        valore = valore[0] if valore else ""
    return _pulisci(str(valore or ""))


def _decimale(valore: Any) -> float | None:
    try:
        return float(valore)
    except (TypeError, ValueError):
        return None


def _indirizzo(valore: Any) -> dict[str, Any]:
    """L'indirizzo dentro `jobLocation`, che a volte e' una lista."""
    if isinstance(valore, list):
        valore = valore[0] if valore else None
    if isinstance(valore, dict):
        dentro = valore.get("address")
        return dentro if isinstance(dentro, dict) else valore
    return {}


# --------------------------------------------------------------------------
# LinkedIn
# --------------------------------------------------------------------------

class LinkedInProvider(BaseProvider):
    kind = "linkedin"
    label = "LinkedIn"
    description = (
        "Ricerca pubblica di LinkedIn, letta come la vede un visitatore senza account. "
        "Non e' un'API: il ritmo e' basso di proposito (mezz'ora fra un giro e l'altro, "
        "ultimi sette giorni, quattro pagine per parola chiave, tutti valori che si "
        "possono cambiare) e la fonte e' meno affidabile delle altre, "
        "perche' LinkedIn puo' cambiare le pagine o rifiutare le richieste."
    )
    needs_credentials = False
    supports_query = True
    # Mezz'ora: LinkedIn conta le richieste per indirizzo IP e non perdona.
    default_interval = 1800
    url_example = "https://www.linkedin.com/jobs/search/?keywords=laboratorio&location=Italia"
    config_fields = [
        {"name": "location", "label": "Dove cercare", "placeholder": "Italia", "required": False,
         "help": "Vuoto significa usare la stessa zona delle ricerche salvate."},
        {"name": "keywords", "label": "Parole chiave", "placeholder": "tecnico di laboratorio",
         "required": False,
         "help": "Vuoto significa usare le parole chiave delle ricerche salvate, "
                 "una richiesta per parola."},
        {"name": "pages", "label": "Pagine per parola chiave a ogni giro",
         "placeholder": "4", "required": False,
         "help": "Dieci offerte per pagina. Vuoto significa 4 pagine: due in cima "
                 "all'elenco, dove compaiono le novita', e due piu' in basso, che "
                 "riprendono da dove era arrivato il giro prima. Alzarlo fa percorrere "
                 "l'elenco piu' in fretta, ma sono piu' richieste a LinkedIn nello "
                 "stesso giro, e LinkedIn le conta."},
        {"name": "days", "label": "Solo gli ultimi giorni", "placeholder": "7", "required": False,
         "help": "Vuoto significa gli ultimi 7 giorni. Un numero piu' grande scende piu' "
                 "indietro nel tempo; 0 toglie il limite, ma allunga di molto ogni giro."},
    ]

    RICERCA = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    DETTAGLIO = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    ANNUNCIO = "https://www.linkedin.com/jobs/view/{job_id}"

    @classmethod
    def detect(cls, url: str) -> dict[str, Any] | None:
        pezzi = urlparse(url)
        if "linkedin.com" not in pezzi.netloc.lower() or "/jobs" not in pezzi.path:
            return None
        # Da un indirizzo di ricerca si recuperano i filtri gia' impostati: chi
        # incolla quel link vuole quella ricerca, non una simile.
        query = parse_qs(pezzi.query)
        config: dict[str, Any] = {}
        for campo in ("keywords", "location"):
            valore = _pulisci((query.get(campo) or [""])[0])
            if valore:
                config[campo] = valore
        periodo = re.search(r"r(\d+)", (query.get("f_TPR") or [""])[0])
        if periodo:
            config["days"] = str(max(1, int(periodo.group(1)) // 86400))
        if (query.get("f_WT") or [""])[0].strip() == "2":
            config["remote"] = "1"
        return config

    @classmethod
    def suggested_label(cls, config: dict[str, Any]) -> str:
        dettaglio = _pulisci(config.get("keywords") or config.get("location") or "")
        return f"LinkedIn - {dettaglio}" if dettaglio else "LinkedIn"

    # -- richieste ---------------------------------------------------------

    def _zuppa(self, pagina: str) -> Any:
        if BeautifulSoup is None:
            raise ProviderError(
                "libreria beautifulsoup4 mancante: installa le dipendenze con "
                "pip install -r requirements.txt per usare la fonte LinkedIn")
        return BeautifulSoup(pagina, "html.parser")

    async def _pausa(self) -> None:
        """Il respiro fra due richieste.

        Nel giro automatico non ha fretta nessuno, e questa pausa e' una delle
        cose che tengono la fonte fuori dai guai. In anteprima invece le
        richieste sono quattro in tutto e c'e' qualcuno che guarda lo schermo.
        """
        if not self.anteprima:
            await asyncio.sleep(PAUSA)

    async def _pagina(self, url: str, params: dict[str, Any] | None = None) -> str:
        """GET di una pagina HTML, con gli errori tipici di LinkedIn tradotti."""
        try:
            risposta = await self.http.get(url, params=params, headers=INTESTAZIONI)
        except httpx.HTTPError as exc:
            raise ProviderError(f"rete: {exc}") from exc

        codice = risposta.status_code
        if codice == 999:
            # Il codice che LinkedIn si e' inventato per dire "so cosa sei".
            raise _Bloccato(
                "LinkedIn ha rifiutato la richiesta (999): sta limitando questo "
                "indirizzo. Alza l'intervallo della fonte o riprova piu' tardi.")
        if codice == 429:
            raise _Bloccato("troppe richieste (429): alza l'intervallo di questa fonte")
        if codice in (401, 403):
            raise _Bloccato(
                f"LinkedIn chiede di accedere (HTTP {codice}): in questo momento la "
                "ricerca pubblica non e' raggiungibile.")
        if codice == 404:
            raise ProviderError("annuncio non piu' disponibile (404)")
        if codice >= 400:
            raise ProviderError(f"HTTP {codice}: {risposta.text[:180]}")

        pagina = risposta.text
        if _muro_di_accesso(pagina):
            raise _Bloccato(
                "LinkedIn ha risposto con la pagina di accesso invece dei risultati: "
                "riprova piu' tardi o alza l'intervallo della fonte.")
        return pagina

    # -- elenco ------------------------------------------------------------

    def _termini(self, searches: list[SearchSpec]) -> list[str]:
        """Le parole chiave da inviare, una per richiesta.

        Il tetto qui e' piu' severo di quello generale: ogni termine e' una
        richiesta a LinkedIn, e le richieste sono la cosa da spendere con
        attenzione su questa fonte.
        """
        proprie = _pulisci(str(self.config.get("keywords", "")))
        if proprie:
            return [proprie]
        termini = unique_terms(searches)
        if self.anteprima:
            # "Prova senza salvare": una parola chiave basta a dire se la fonte
            # risponde e cosa restituisce, e chi ha premuto il pulsante non deve
            # aspettare mezzo minuto di pause per saperlo.
            return termini[:1]
        if len(termini) > MAX_TERMINI:
            log.info("LinkedIn: %d parole chiave nelle ricerche, uso le prime %d "
                     "per non moltiplicare le richieste", len(termini), MAX_TERMINI)
        return termini[:MAX_TERMINI]

    def _luogo(self, searches: list[SearchSpec]) -> str:
        """Il luogo da mandare a LinkedIn, con il paese scritto in inglese.

        LinkedIn non geocodifica "Italia" e non lo dice: risponde 200 con dieci
        annunci di New York. Anche una citta' da sola - "Milano" - finisce
        cosi'. Con "Milano, Italy" o "Italy" i risultati sono quelli giusti,
        quindi il paese si traduce e, se manca, si aggiunge prendendolo dalla
        ricerca.
        """
        proprio = _pulisci(str(self.config.get("location", "")))
        paese = next((s.country for s in searches or [] if s.country), "")
        if proprio:
            return paesi.in_inglese(proprio, paese)
        scritto = next((s.location for s in searches or [] if s.location), "")
        if scritto:
            return paesi.in_inglese(scritto, paese)
        # Nessuna localita' scritta da nessuna parte: resta il paese, che e'
        # comunque meglio del default di LinkedIn.
        return paesi.INGLESE.get(paese.lower(), "").title() if paese else ""

    def _giorni(self) -> int:
        """La finestra di date da chiedere a LinkedIn, in giorni.

        Campo vuoto significa il valore predefinito, non "nessun limite": senza
        limite l'elenco non si esaurisce mai. Per togliere il limite si scrive 0.
        """
        scritto = _pulisci(str(self.config.get("days", "")))
        if not scritto:
            return GIORNI_PREDEFINITI
        try:
            return max(0, int(scritto))
        except ValueError:
            return GIORNI_PREDEFINITI

    def _pagine(self) -> int:
        """Quante pagine leggere per parola chiave a ogni giro."""
        scritto = _pulisci(str(self.config.get("pages", "")))
        if not scritto:
            return PAGINE_PREDEFINITE
        try:
            return max(1, min(MAX_PAGINE, int(scritto)))
        except ValueError:
            return PAGINE_PREDEFINITE

    async def fetch(self, searches: list[SearchSpec]) -> list[JobPosting]:
        if BeautifulSoup is None:
            raise ProviderError(
                "libreria beautifulsoup4 mancante: installa le dipendenze con "
                "pip install -r requirements.txt per usare la fonte LinkedIn")

        luogo = self._luogo(searches)
        giorni = self._giorni()
        remoto = _pulisci(str(self.config.get("remote", ""))).lower() in ("1", "si", "true", "yes")

        trovate: dict[str, JobPosting] = {}
        for indice, termine in enumerate(self._termini(searches)):
            # La pausa sta fra una richiesta e l'altra, non prima della prima:
            # un giro con una sola parola chiave non deve aspettare per niente.
            if indice:
                await self._pausa()
            try:
                await self._sfoglia(termine, luogo, giorni, remoto, trovate)
            except _Bloccato:
                # Quello che era gia' stato letto vale comunque: buttarlo via
                # non renderebbe la fonte piu' sana, e il blocco si ripresenta
                # al giro dopo alla prima richiesta, dove viene registrato.
                if not trovate:
                    raise
                log.warning("LinkedIn: bloccato a meta' raccolta, tengo le %d offerte gia' lette",
                            len(trovate))
                break
            except ProviderError as exc:
                if not trovate:
                    raise
                log.info("LinkedIn: %r interrotta (%s), proseguo con le altre parole chiave",
                         termine or "(senza parole chiave)", exc)
        return list(trovate.values())

    async def _sfoglia(self, termine: str, luogo: str, giorni: int, remoto: bool,
                       trovate: dict[str, JobPosting]) -> None:
        """Sfoglia i risultati di una parola chiave, in due passate.

        LinkedIn restituisce dieci offerte per volta, non venticinque: chiedere
        solo la prima pagina significava vedere dieci offerte per parola chiave
        e, al giro dopo, rileggere quelle stesse dieci.

        Ma nemmeno scendere finche' arrivano novita' basta, ed e' un errore che
        questa fonte ha gia' fatto: dopo il primo giro la cima dell'elenco e'
        tutta in archivio, la discesa si ferma subito, e quello che sta sotto
        non viene raggiunto mai piu'. La fonte sembra viva - una richiesta,
        dieci offerte, zero nuove - e invece e' ferma.

        Quindi due passate, con due scopi diversi:

        * **in cima**, sempre: e' li' che compaiono gli annunci nuovi, e si
          scende finche' ne arrivano;
        * **piu' giu'**, quando in cima non c'era niente di nuovo: si riprende
          da dove si era arrivati il giro prima e si legge un altro pezzo di
          elenco. Il segnaposto sta in `self.stato` e sopravvive al giro; quando
          l'elenco finisce si torna in cima e si ricomincia.

        Cosi' ogni giro costa lo stesso - poche pagine - ma nel corso di qualche
        giro l'elenco viene percorso tutto.
        """
        cursori = self.stato.setdefault("cursori", {})
        chiave = termine or "*"
        pagine_giro = self._pagine()
        # La cima non si mangia tutto il budget: con una pagina sola in totale
        # si guarda solo la cima, che e' dove stanno le novita'.
        in_cima = min(PAGINE_IN_CIMA, pagine_giro)

        # In anteprima una pagina sola: c'e' qualcuno che aspetta la risposta, e
        # una pagina basta a dire se la fonte risponde e cosa restituisce.
        cima = await self._passata(termine, luogo, giorni, remoto, trovate, inizio=0,
                                   pagine=1 if self.anteprima else in_cima,
                                   fino_a_novita=True)
        if self.anteprima:
            return
        if cima["esaurito"]:
            # L'elenco finisce dentro le prime pagine: sotto non c'e' niente da
            # esplorare e il segnaposto torna in cima.
            cursori[chiave] = 0
            return

        restanti = pagine_giro - cima["pagine"]
        if restanti <= 0:
            return
        # Mai sotto quello che si e' appena letto: la passata in profondita'
        # riprende da dopo la cima, non ripete il lavoro di due secondi fa.
        partenza = max(cursori.get(chiave, 0), cima["fine"])
        await self._pausa()
        giu = await self._passata(termine, luogo, giorni, remoto, trovate,
                                  inizio=partenza, pagine=restanti, fino_a_novita=False)
        # Elenco finito: il giro prossimo ricomincia da sotto la cima.
        cursori[chiave] = 0 if giu["esaurito"] else giu["fine"]
        log.info("LinkedIn: %r, letto anche il tratto da %d a %d (%d mai viste)",
                 termine or "(senza parole chiave)", partenza, giu["fine"], giu["nuove"])

    async def _passata(self, termine: str, luogo: str, giorni: int, remoto: bool,
                       trovate: dict[str, JobPosting], inizio: int, pagine: int,
                       fino_a_novita: bool) -> dict[str, Any]:
        """Legge un tratto di elenco a partire da `inizio`.

        Con `fino_a_novita` si ferma alla prima pagina che non porta offerte
        mai viste; senza, legge il numero di pagine che gli e' stato dato. In
        entrambi i casi si ferma se l'elenco finisce o se LinkedIn ripete la
        stessa pagina.
        """
        esito = {"fine": inizio, "nuove": 0, "pagine": 0, "esaurito": False}
        precedente: set[str] = set()
        for pagina in range(max(0, pagine)):
            if pagina:
                await self._pausa()
            params: dict[str, Any] = {"start": esito["fine"], "sortBy": "DD"}
            if termine:
                params["keywords"] = termine
            if luogo:
                params["location"] = luogo
            if giorni:
                params["f_TPR"] = f"r{giorni * 86400}"
            if remoto:
                params["f_WT"] = "2"

            offerte = self._leggi_elenco(await self._pagina(self.RICERCA, params))
            esito["pagine"] += 1
            if not offerte:
                esito["esaurito"] = True
                if not pagina and not inizio:
                    log.info("LinkedIn: nessun risultato per %r",
                             termine or "(senza parole chiave)")
                return esito

            identificativi = {o.external_id for o in offerte}
            if identificativi == precedente:
                # Stessa identica pagina della volta prima: `start` non e' stato
                # ascoltato. Insistere vorrebbe dire rifare la stessa richiesta.
                log.info("LinkedIn: %r restituisce sempre la stessa pagina, mi fermo",
                         termine or "(senza parole chiave)")
                esito["esaurito"] = True
                return esito
            precedente = identificativi

            nuove = 0
            for offerta in offerte:
                if offerta.external_id not in self.id_in_archivio:
                    nuove += 1
                # Con che parola e' stata trovata. Serve al filtro di
                # pertinenza: la descrizione arriva solo dopo, e senza sapere
                # che questo annuncio e' il risultato di una ricerca su quella
                # parola il filtro lo giudicherebbe sul solo titolo.
                if termine:
                    offerta.raw["query"] = termine
                # E in che luogo. Le schede di LinkedIn spesso scrivono solo la
                # citta' - "Milano" - senza mai nominare il paese: il filtro di
                # pertinenza non avrebbe modo di sapere che quella ricerca era
                # gia' ristretta all'Italia, e le scarterebbe tutte.
                if luogo:
                    offerta.raw["query_luogo"] = luogo
                trovate.setdefault(offerta.external_id, offerta)
            esito["nuove"] += nuove

            # `start` avanza del numero di schede ricevute, non di un passo
            # fisso: se LinkedIn cambia la dimensione della pagina il conto
            # resta giusto, e non si salta ne' si ripete niente.
            esito["fine"] += len(offerte)
            if fino_a_novita and not nuove:
                return esito
        return esito

    def _leggi_elenco(self, pagina: str) -> list[JobPosting]:
        """Le schede della pagina dei risultati, saltando quelle illeggibili."""
        zuppa = self._zuppa(pagina)
        schede = (zuppa.select("li div.base-card")
                  or zuppa.select("div.base-card")
                  or zuppa.select("li"))
        offerte: list[JobPosting] = []
        for scheda in schede:
            try:
                offerta = self._leggi_scheda(scheda)
            except Exception as exc:  # una scheda rotta non deve portarsi via le altre
                log.debug("LinkedIn: scheda illeggibile (%s: %s)", type(exc).__name__, exc)
                continue
            if offerta is not None:
                offerte.append(offerta)
        return offerte

    def _leggi_scheda(self, scheda: Any) -> JobPosting | None:
        link = (scheda.select_one("a.base-card__full-link[href]")
                or scheda.select_one("a[href*='/jobs/view/']")
                or scheda.select_one("a[href]"))
        href = (link.get("href") if link else "") or ""
        identificativo = _id_offerta(scheda, href)
        titolo = _testo(scheda, "h3.base-search-card__title", "[class*='_title']", "h3")
        if not identificativo or not titolo:
            return None

        azienda = _testo(scheda, "h4.base-search-card__subtitle a",
                         "h4.base-search-card__subtitle", "[class*='_subtitle']", "h4")
        sede = _testo(scheda, "span.job-search-card__location", "[class*='location']")
        paga = _testo(scheda, "[class*='salary']")
        minimo, massimo, valuta = _stipendio(paga)
        citta, regione = _sede(sede)
        quando = scheda.select_one("time[datetime]")
        url = _url_annuncio(href, identificativo)

        return JobPosting(
            external_id=identificativo,
            title=titolo,
            company=azienda,
            location=sede,
            city=citta,
            region=regione,
            # Il paese si ricava dall'ultimo pezzo della sede, che e' dove
            # LinkedIn lo scrive. Serve al filtro di pertinenza: senza, una
            # ricerca "tutta Italia" non ha modo di sapere che "Madrid,
            # Comunidad de Madrid, Spagna" e' fuori.
            country=codice_dalla_sede(sede),
            remote=looks_remote(titolo, sede),
            url=url,
            apply_url=url,
            # La descrizione non sta nell'elenco: la scarica `enrich`, dopo il
            # filtro di pertinenza.
            description="",
            salary_min=minimo,
            salary_max=massimo,
            currency=valuta,
            posted_at=parse_date(quando.get("datetime") if quando else None),
            raw={"sede": sede, "stipendio": paga},
        )

    # -- descrizioni -------------------------------------------------------

    async def enrich(self, postings: list[JobPosting]) -> None:
        if BeautifulSoup is None:
            return
        rimaste = [p for p in postings
                   if not p.description and p.external_id not in self.known_ids]
        budget = min(self.detail_budget, MAX_DETTAGLI)
        if len(rimaste) > budget:
            log.info("LinkedIn: %d offerte da completare, ne scarico %d in questo giro "
                     "(le altre alla prossima passata)", len(rimaste), budget)

        for indice, offerta in enumerate(rimaste[:budget]):
            if indice:
                await self._pausa()
            try:
                await self._completa(offerta)
            except _Bloccato as exc:
                # Se LinkedIn ha chiuso la porta, le richieste successive la
                # troverebbero chiusa uguale: meglio fermarsi che insistere.
                log.warning("LinkedIn: descrizioni interrotte, %s", exc)
                break
            except ProviderError as exc:
                log.info("LinkedIn: descrizione di %s non disponibile (%s)",
                         offerta.external_id, exc)

    async def _completa(self, offerta: JobPosting) -> None:
        """Scarica la descrizione di un singolo annuncio.

        Due strade. Prima il frammento che LinkedIn serve ai visitatori: e'
        leggero e non passa dal muro del login. Se non da' niente, la pagina
        completa dell'annuncio, dove c'e' un blocco JSON-LD - piu' stabile dei
        `div`, perche' e' quello che LinkedIn pubblica apposta per i motori di
        ricerca e quindi cambia molto piu' di rado.
        """
        self._applica_frammento(
            offerta, await self._pagina(self.DETTAGLIO.format(job_id=offerta.external_id)))
        if offerta.description:
            return
        await self._pausa()
        self._applica_json_ld(
            offerta, await self._pagina(self.ANNUNCIO.format(job_id=offerta.external_id)))

    def _applica_frammento(self, offerta: JobPosting, pagina: str) -> None:
        zuppa = self._zuppa(pagina)
        corpo = (zuppa.select_one("div.show-more-less-html__markup")
                 or zuppa.select_one("div.description__text")
                 or zuppa.select_one("[class*='description__text']"))
        if corpo is not None:
            offerta.description = html_to_text(str(corpo))

        # Il riquadro con i dati dell'offerta: tipo di contratto, funzione,
        # settore. Le etichette cambiano lingua, quindi si riconoscono da una
        # parola sola.
        for voce in zuppa.select("li.description__job-criteria-item, [class*='criteria-item']"):
            etichetta = _testo(voce, "h3", "[class*='subheader']").lower()
            valore = _testo(voce, "span.description__job-criteria-text", "span")
            if not valore:
                continue
            if "impiego" in etichetta or "employment" in etichetta or "contratto" in etichetta:
                offerta.employment_type = offerta.employment_type or valore
            elif "funzione" in etichetta or "function" in etichetta:
                offerta.department = offerta.department or valore

        # Per le candidature esterne LinkedIn tiene l'indirizzo vero dentro un
        # commento HTML, che BeautifulSoup non restituisce come testo.
        esterna = re.search(r'id="applyUrl"[^>]*>[\s<!-]*"?(https?://[^"\'<\s]+)', pagina)
        if esterna:
            offerta.apply_url = esterna.group(1).replace("&amp;", "&")

    def _applica_json_ld(self, offerta: JobPosting, pagina: str) -> None:
        """Legge il blocco JSON-LD della pagina pubblica dell'annuncio."""
        dati: dict[str, Any] | None = None
        for blocco in self._zuppa(pagina).select('script[type="application/ld+json"]'):
            try:
                contenuto = json.loads(blocco.string or blocco.get_text() or "{}")
            except ValueError:
                continue
            for voce in contenuto if isinstance(contenuto, list) else [contenuto]:
                if isinstance(voce, dict) and voce.get("@type") == "JobPosting":
                    dati = voce
                    break
            if dati:
                break
        if not dati:
            return

        offerta.description = html_to_text(dati.get("description", "")) or offerta.description
        offerta.employment_type = offerta.employment_type or _primo(dati.get("employmentType"))
        offerta.posted_at = offerta.posted_at or parse_date(dati.get("datePosted"))
        # Il lavoro da remoto qui e' dichiarato, non dedotto dal testo: cercare
        # "remoto" dentro la descrizione trasformerebbe un "non e' previsto lo
        # smart working" in un'offerta da remoto, e il filtro sulla sede
        # lascerebbe passare mezza Europa.
        if _primo(dati.get("jobLocationType")).upper() == "TELECOMMUTE":
            offerta.remote = True
        azienda = dati.get("hiringOrganization")
        if isinstance(azienda, dict):
            offerta.company = offerta.company or _pulisci(azienda.get("name", ""))

        indirizzo = _indirizzo(dati.get("jobLocation"))
        if indirizzo:
            offerta.city = offerta.city or _pulisci(str(indirizzo.get("addressLocality") or ""))
            offerta.region = offerta.region or _pulisci(str(indirizzo.get("addressRegion") or ""))
            paese = indirizzo.get("addressCountry")
            if isinstance(paese, dict):
                paese = paese.get("name", "")
            paese = _pulisci(str(paese or ""))
            # Qui il codice a due lettere lo dichiara LinkedIn: e' proprio
            # quello che si aspetta il filtro sul paese, e non va indovinato.
            if len(paese) == 2:
                offerta.country = offerta.country or paese.lower()

        paga = dati.get("baseSalary")
        valore = paga.get("value") if isinstance(paga, dict) else None
        if isinstance(valore, dict):
            minimo = valore.get("minValue")
            offerta.salary_min = offerta.salary_min or _decimale(
                minimo if minimo is not None else valore.get("value"))
            offerta.salary_max = offerta.salary_max or _decimale(valore.get("maxValue"))
            offerta.currency = offerta.currency or _pulisci(str(paga.get("currency") or ""))
