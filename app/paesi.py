"""Nomi dei paesi e codice a due lettere.

Sta in un modulo suo, e non dentro il motore di confronto o dentro un adapter,
perche' lo usano entrambi: le fonti per capire in che paese si trova un'offerta
a partire da come e' scritta la sede, il filtro di pertinenza per riconoscere
una ricerca "su tutta l'Italia". Due tabelle separate sarebbero divergite alla
prima aggiunta, e questo modulo non importa niente, quindi puo' essere letto da
chiunque senza tirarsi dietro mezza applicazione.
"""
from __future__ import annotations

import re
import unicodedata

# Codice ISO a due lettere -> nomi del paese, in italiano e in inglese.
NOMI: dict[str, tuple[str, ...]] = {
    # Il primo nome e' quello italiano, il secondo quello inglese: e' l'inglese
    # che si manda ai portali (vedi `in_inglese`).
    "it": ("italia", "italy"), "fr": ("francia", "france"),
    "de": ("germania", "germany"), "es": ("spagna", "spain"),
    "pt": ("portogallo", "portugal"), "ch": ("svizzera", "switzerland"),
    "at": ("austria", "austria"), "be": ("belgio", "belgium"),
    "nl": ("paesi bassi", "netherlands", "olanda", "holland"),
    "ie": ("irlanda", "ireland"),
    "gb": ("regno unito", "united kingdom", "uk", "gran bretagna", "great britain",
           "inghilterra", "england", "scozia", "scotland", "galles", "wales"),
    "us": ("stati uniti", "united states", "usa", "stati uniti d america",
           "united states of america", "u s a", "america"),
    "dk": ("danimarca", "denmark"), "se": ("svezia", "sweden"),
    "no": ("norvegia", "norway"), "fi": ("finlandia", "finland"),
    "pl": ("polonia", "poland"), "gr": ("grecia", "greece"),
    "cz": ("repubblica ceca", "czech republic", "czechia"),
    "hu": ("ungheria", "hungary"), "ro": ("romania", "romania"),
    # Il resto d'Europa e i paesi che compaiono piu' spesso negli annunci da
    # remoto. Non servono a cercare: servono a riconoscere che un'offerta e'
    # fuori dal paese che si sta cercando.
    "lu": ("lussemburgo", "luxembourg"), "mt": ("malta", "malta"),
    "cy": ("cipro", "cyprus"), "hr": ("croazia", "croatia"),
    "si": ("slovenia", "slovenia"), "sk": ("slovacchia", "slovakia"),
    "bg": ("bulgaria", "bulgaria"), "ee": ("estonia", "estonia"),
    "lv": ("lettonia", "latvia"), "lt": ("lituania", "lithuania"),
    "is": ("islanda", "iceland"), "rs": ("serbia", "serbia"),
    "ua": ("ucraina", "ukraine"), "tr": ("turchia", "turkey"),
    "ru": ("russia", "russia"), "al": ("albania", "albania"),
    "ba": ("bosnia ed erzegovina", "bosnia and herzegovina"),
    "mk": ("macedonia del nord", "north macedonia"),
    "md": ("moldavia", "moldova"), "by": ("bielorussia", "belarus"),
    "ca": ("canada", "canada"), "mx": ("messico", "mexico"),
    "br": ("brasile", "brazil"), "ar": ("argentina", "argentina"),
    "cl": ("cile", "chile"), "co": ("colombia", "colombia"),
    "pe": ("peru", "peru"), "uy": ("uruguay", "uruguay"),
    "in": ("india", "india"), "cn": ("cina", "china"),
    "jp": ("giappone", "japan"), "kr": ("corea del sud", "south korea"),
    "sg": ("singapore", "singapore"), "hk": ("hong kong", "hong kong"),
    "ph": ("filippine", "philippines"), "id": ("indonesia", "indonesia"),
    "my": ("malesia", "malaysia"), "th": ("tailandia", "thailand"),
    "vn": ("vietnam", "vietnam"), "pk": ("pakistan", "pakistan"),
    "bd": ("bangladesh", "bangladesh"), "il": ("israele", "israel"),
    "ae": ("emirati arabi uniti", "united arab emirates"),
    "sa": ("arabia saudita", "saudi arabia"), "qa": ("qatar", "qatar"),
    "eg": ("egitto", "egypt"), "ma": ("marocco", "morocco"),
    "tn": ("tunisia", "tunisia"), "ng": ("nigeria", "nigeria"),
    "ke": ("kenya", "kenya"), "za": ("sudafrica", "south africa"),
    "au": ("australia", "australia"), "nz": ("nuova zelanda", "new zealand"),
}

# Codice a due lettere -> codice a tre lettere. Serve a leggere le sedi dei
# portali che scrivono il paese in codice invece che per nome: MSD, su Workday,
# chiama le proprie sedi "ITA - Lazio - Roma", e in quella stringa la parola
# "Italy" non compare da nessuna parte.
ISO3: dict[str, str] = {
    "it": "ita", "fr": "fra", "de": "deu", "es": "esp", "pt": "prt",
    "ch": "che", "at": "aut", "be": "bel", "nl": "nld", "ie": "irl",
    "gb": "gbr", "us": "usa", "dk": "dnk", "se": "swe", "no": "nor",
    "fi": "fin", "pl": "pol", "gr": "grc", "cz": "cze", "hu": "hun",
    "ro": "rou", "lu": "lux", "mt": "mlt", "cy": "cyp", "hr": "hrv",
    "si": "svn", "sk": "svk", "bg": "bgr", "ee": "est", "lv": "lva",
    "lt": "ltu", "is": "isl", "rs": "srb", "ua": "ukr", "tr": "tur",
    "ru": "rus", "al": "alb", "ba": "bih", "mk": "mkd", "md": "mda",
    "by": "blr", "ca": "can", "mx": "mex", "br": "bra", "ar": "arg",
    "cl": "chl", "co": "col", "pe": "per", "uy": "ury", "in": "ind",
    "cn": "chn", "jp": "jpn", "kr": "kor", "sg": "sgp", "hk": "hkg",
    "ph": "phl", "id": "idn", "my": "mys", "th": "tha", "vn": "vnm",
    "pk": "pak", "bd": "bgd", "il": "isr", "ae": "are", "sa": "sau",
    "qa": "qat", "eg": "egy", "ma": "mar", "tn": "tun", "ng": "nga",
    "ke": "ken", "za": "zaf", "au": "aus", "nz": "nzl",
}

# Nome -> codice, costruita una volta sola all'importazione.
_DA_NOME = {nome: iso for iso, nomi in NOMI.items() for nome in nomi}

# Sigla a tre lettere -> codice a due.
_DA_ISO3 = {tre: due for due, tre in ISO3.items()}

# Codice -> nome inglese. E' il nome da mandare ai portali: LinkedIn non
# geocodifica "Italia" e, invece di dirlo, cerca da un'altra parte.
INGLESE = {iso: (nomi[1] if len(nomi) > 1 else nomi[0]) for iso, nomi in NOMI.items()}


def _appiattisci(nome: str) -> str:
    """Minuscole, senza accenti, senza apostrofi, spazi singoli.

    Serve perche' i portali scrivono i nomi come vengono: "Stati Uniti
    d'America" e' lo stesso paese di "stati uniti d america".
    """
    senza = unicodedata.normalize("NFD", (nome or "").lower())
    senza = "".join(c for c in senza if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", senza)).strip()


def codice(nome: str) -> str:
    """Il codice di un paese scritto per esteso, o "" se non lo riconosciamo."""
    return _DA_NOME.get(_appiattisci(nome), "")


# Tutti i nomi in una sola espressione, i piu' lunghi per primi, cosi' "united
# kingdom" vince su un eventuale pezzo piu' corto. Si costruisce una volta.
_UN_NOME = re.compile(
    r"(?<![a-z])(" + "|".join(
        re.escape(n) for n in sorted(_DA_NOME, key=len, reverse=True)) + r")(?![a-z])")


def _piatto(testo: str) -> str:
    """Minuscole, senza accenti e con la punteggiatura ridotta a spazi."""
    senza = unicodedata.normalize("NFD", (testo or "").lower())
    senza = "".join(c for c in senza if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", senza).strip()


def paese_nel_testo(testo: str) -> str:
    """Il paese nominato in una sede scritta in liberta', o "" se non e' chiaro.

    "Remote - United States" -> "us". Serve alle offerte da remoto, che spesso
    non compilano il campo del paese e lo scrivono soltanto nella sede, in un
    formato che `codice_dalla_sede` non puo' indovinare perche' non c'e' una
    virgola a separare i pezzi.

    Se ne compaiono due - "Remote (Italia o Germania)" - si preferisce non
    saperlo: scegliere il primo sarebbe una moneta lanciata, e su questo dato si
    decide se buttare via un annuncio.
    """
    trovati = {_DA_NOME[m.group(1)] for m in _UN_NOME.finditer(_piatto(testo))}
    return trovati.pop() if len(trovati) == 1 else ""


def _senza_parentesi(pezzo: str) -> str:
    return re.sub(r"\s*\(.*\)\s*$", "", pezzo or "").strip()


def _paese_del_pezzo(pezzo: str) -> str:
    """Il paese scritto in un pezzo di sede, dentro o fuori la parentesi.

    "Italia" -> it. "Milano (MI)" -> "" perche' la parentesi e' la provincia.
    "Lugano (Svizzera)" -> ch, perche' a volte la parentesi e' il paese. Si
    guardano entrambe le forme e vince quella che si riconosce.
    """
    dentro = re.search(r"\(([^)]*)\)\s*$", pezzo or "")
    return codice(_senza_parentesi(pezzo)) or (
        codice(dentro.group(1)) if dentro else "")


def in_inglese(sede: str, iso: str = "") -> str:
    """La sede da mandare a un portale: il paese scritto in inglese.

    "Milano, Italia" -> "Milano, Italy". Se la sede non nomina un paese lo
    aggiunge, prendendolo da `iso`: senza paese LinkedIn non capisce di che
    Milano si tratti e cerca negli Stati Uniti. La citta' resta come e'
    scritta - "Milano, Italy" e "Milan, Italy" danno gli stessi risultati.
    """
    pezzi = [p.strip() for p in (sede or "").split(",") if p.strip()]
    if pezzi:
        suo = _paese_del_pezzo(pezzi[-1])
        if suo:
            # Il paese c'e' gia': si riscrive in inglese. Se stava dentro una
            # parentesi - "Lugano (Svizzera)" - quello che c'era davanti e' il
            # luogo, e va tenuto.
            resto = pezzi[:-1]
            davanti = _senza_parentesi(pezzi[-1])
            if davanti and not codice(davanti):
                resto = resto + [davanti]
            return ", ".join(resto + [INGLESE[suo].title()])
    nome = INGLESE.get((iso or "").strip().lower(), "")
    if not nome:
        return ", ".join(pezzi)
    return ", ".join(pezzi + [nome.title()])


def senza_paese(sede: str) -> str:
    """La sede senza il paese in coda: "Milano, Italia" -> "Milano".

    Serve a chi confronta i nomi di luogo. Le virgole, in una localita' scritta
    a mano, sono alternative - "Milano, Pavia" vuol dire in una delle due - e
    finche' il paese si scriveva in un campo suo la cosa funzionava. Adesso il
    paese si scrive nella localita', e "Milano, Italia" diventava "a Milano
    oppure in Italia", cioe' in qualunque posto d'Italia: il filtro sembrava
    attivo e non filtrava niente. Il paese ha il suo controllo, qui va togliuto.

    Se la localita' e' soltanto un paese resta la stringa vuota: e' una ricerca
    su tutto il paese, e chi chiama la riconosce da questo.
    """
    pezzi = [p.strip() for p in (sede or "").split(",") if p.strip()]
    if pezzi and _paese_del_pezzo(pezzi[-1]):
        davanti = _senza_parentesi(pezzi[-1])
        pezzi = pezzi[:-1] + ([davanti] if davanti and not codice(davanti) else [])
    return ", ".join(pezzi)


# Virgole e trattini separano i pezzi di una sede. Il trattino vuole lo spazio
# intorno: senza quel vincolo "Aix-en-Provence" e "Boxmeer-Noord" si
# spezzerebbero in pezzi che non sono nomi di luogo.
_PEZZI = re.compile(r"\s*[,;/|]\s*|\s+[-–—]\s+")


def segmenti(sede: str) -> list[str]:
    """I pezzi di cui una sede e' composta, dal piu' generale al piu' preciso.

    "ITA - Lazio - Roma" -> ["ITA", "Lazio", "Roma"]
    "Milano - Lombardia, Italia" -> ["Milano", "Lombardia", "Italia"]

    Serve a chi deve riconoscere un luogo dentro una sede senza sapere in che
    ordine quel portale la scrive: il paese sta in testa per certi tenant e in
    coda per altri, e cercarlo con un confronto sull'intera stringa vuol dire
    indovinare l'ordine. Gli incisi fra parentesi si buttano: nelle sedi sono
    codici interni, come in "Milan, Italy (ITALY01, 40)".
    """
    ripulito = re.sub(r"\s*\([^)]*\)", " ", sede or "")
    return [p.strip() for p in _PEZZI.split(ripulito) if p and p.strip()]


def codice_o_sigla(pezzo: str) -> str:
    """Il paese di un pezzo di sede, per nome o per sigla a tre lettere.

    Sta separata da `codice` di proposito. Qui si accetta anche "ITA", che
    dentro la sede di un portale e' certamente un paese; in una localita'
    scritta a mano sarebbe un azzardo, perche' "Bra" e' un comune del Piemonte
    e non il Brasile, e le localita' le scrivono le persone.
    """
    piatto = _appiattisci(pezzo)
    return _DA_NOME.get(piatto, "") or _DA_ISO3.get(piatto, "")


def pezzo_e_paese(pezzo: str, iso: str) -> bool:
    """Se un pezzo di sede nomina quel paese: "Italia", "Italy", "ITA", "it".

    Il pezzo deve corrispondere per intero. E' il vincolo che distingue il
    filtrare dal sembrare di filtrare: "Italy Office" e' un ufficio che si
    chiama cosi', e sta in Svizzera.
    """
    iso = (iso or "").strip().lower()
    if not iso:
        return False
    piatto = _appiattisci(pezzo)
    if not piatto:
        return False
    return piatto == iso or piatto == ISO3.get(iso, "") or piatto in NOMI.get(iso, ())


def codice_dalla_sede(sede: str) -> str:
    """Il paese di una sede scritta come la scrivono i portali.

    "Milano, Lombardia, Italia" -> "it". Si guarda solo l'ultimo pezzo, che e'
    dove finisce il paese, ripulito da un eventuale inciso fra parentesi
    ("Italia (Da remoto)"). Se quel pezzo non e' un nome che conosciamo si
    preferisce non saperlo: un paese indovinato male farebbe sparire offerte
    buone, mentre un paese assente le lascia passare al vaglio successivo.
    """
    pezzi = [p.strip() for p in (sede or "").split(",") if p.strip()]
    if not pezzi:
        return ""
    return _paese_del_pezzo(pezzi[-1])
