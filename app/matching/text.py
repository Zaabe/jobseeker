"""Normalizzazione del testo, tokenizzazione e similarita' lessicale.

Tutto e' bilingue italiano/inglese: i curriculum e gli annunci italiani mescolano
regolarmente le due lingue, e un motore che ne capisce una sola sbaglia i conti.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

from .. import paesi
from typing import Iterable

# Parole troppo comuni per dire qualcosa sul contenuto. Una lista curata batte
# una soglia automatica su corpus piccoli come il nostro.
STOPWORDS: frozenset[str] = frozenset("""
a ad agli ai al alla alle allo anche ancora avere aver avuto abbiamo ai al
c che chi ci co coi col come con contro cui
da dagli dai dal dalla dalle dallo degli dei del della delle dello di do dopo dove due
e ed egli ecco essere esso essa essi
fa fare fino fra
gli grande
ha hai hanno ho
i il in io
la le lei li lo loro lui
ma me mi mia mie mio miei molto
ne negli nei nel nella nelle nello no noi non nostro nostra
o od ogni oltre
per piu piu' po poco potere presso prima puo puo'
qual quale quali quando quanto quel quella quelle quelli quello questa queste questi questo qui
sara sarai saranno sara' se sei sia siamo siete solo sono sopra sotto sta stata stato stati sua sue sui sul sulla sulle sullo suo suoi
tra tre troppo tu tua tue tuo tuoi tutti tutto
un una uno
va vai verso vi via voi vostro vostra
about above after again against all also am an and any are aren as at
be because been before being below between both but by
can cannot could
did do does doing don down during
each else ever every
few for from further
had has have having he her here hers herself him himself his how however
i if in into is it its itself
just
me more most must my myself
no nor not now
of off on once only or other our ours ourselves out over own
same she should so some such
than that the their theirs them themselves then there these they this those through to too
under until up upon us
very
was we were what when where which while who whom why will with within would
you your yours yourself yourselves
will shall may might
role roles job jobs position positions work working works team teams company companies
opportunity opportunities candidate candidates applicant applicants
azienda aziende ruolo ruoli lavoro lavori posizione posizioni team gruppo
offerta offerte candidato candidati candidatura ricerchiamo cerchiamo cerca offriamo
""".split())

# Sequenze che compaiono in ogni annuncio e che non distinguono nulla.
BOILERPLATE = re.compile(
    r"\b(equal opportunity employer|pari opportunit|ai sensi del|d\.?lgs\.?|gdpr|"
    r"regolamento ue|informativa privacy|автор|reg\.? ue 2016/679)\b",
    re.IGNORECASE,
)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#.\-]*", re.IGNORECASE)


def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def normalize(text: str) -> str:
    """Minuscole, senza accenti, spaziatura compattata.

    Serve a far combaciare "Biotecnologie" con "biotecnologie" e "R&D" con "r&d"
    senza dover moltiplicare gli alias del dizionario.
    """
    if not text:
        return ""
    text = strip_accents(text.lower())
    text = text.replace("&", " and ")
    text = re.sub(r"[ ​]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# Le fonti scrivono le sedi in inglese ("Milan, Italy") mentre le ricerche si
# scrivono in italiano ("Milano, Italia"). Senza questa corrispondenza il filtro
# geografico scarta proprio le offerte che si stanno cercando.
_PLACE_PAIRS = [
    ("italia", "italy"), ("milano", "milan"), ("roma", "rome"), ("torino", "turin"),
    ("firenze", "florence"), ("venezia", "venice"), ("napoli", "naples"),
    ("genova", "genoa"), ("padova", "padua"), ("bologna", "bologna"),
    ("sardegna", "sardinia"), ("sicilia", "sicily"), ("toscana", "tuscany"),
    ("lombardia", "lombardy"), ("piemonte", "piedmont"), ("puglia", "apulia"),
    ("germania", "germany"), ("francia", "france"), ("spagna", "spain"),
    ("svizzera", "switzerland"), ("regno unito", "united kingdom"),
    ("paesi bassi", "netherlands"), ("belgio", "belgium"), ("austria", "austria"),
    ("grecia", "greece"), ("polonia", "poland"), ("portogallo", "portugal"),
    ("irlanda", "ireland"), ("danimarca", "denmark"), ("svezia", "sweden"),
]

_PLACE_ALIASES: dict[str, set[str]] = {}
for _a, _b in _PLACE_PAIRS:
    _PLACE_ALIASES.setdefault(_a, set()).update({_a, _b})
    _PLACE_ALIASES.setdefault(_b, set()).update({_a, _b})


# I nomi dei paesi stanno in `app/paesi.py`, perche' li leggono anche le fonti:
# servono a riconoscere una ricerca "a livello di paese", che va risolta sul
# campo paese dell'offerta e non sul testo della sede (molte fonti scrivono
# "Roma, Provincia di Roma" senza mai nominare l'Italia).
COUNTRY_NAMES = paesi.NOMI


def country_names(iso: str) -> set[str]:
    return set(COUNTRY_NAMES.get((iso or "").strip().lower(), ()))


def is_country_query(wanted: str, iso: str) -> bool:
    """Se la localita' cercata coincide con l'intero paese della ricerca."""
    return normalize(wanted).strip() in country_names(iso)


def job_in_country(job_country: str, iso: str) -> bool:
    """Se un'offerta dichiara di trovarsi nel paese indicato.

    Le fonti scrivono il paese in modi diversi: il codice ISO ("it"), il nome
    inglese ("Italy") o quello italiano. Qui vengono accettati tutti.
    """
    valore = normalize(job_country).strip()
    if not valore:
        return False
    iso = (iso or "").strip().lower()
    return valore == iso or valore in country_names(iso)


def place_variants(name: str) -> set[str]:
    """Le forme equivalenti di un nome di luogo, italiano e inglese."""
    key = normalize(name).strip()
    return _PLACE_ALIASES.get(key, {key}) if key else set()


def place_matches(wanted: str, haystack: str) -> bool:
    """Dice se una sede corrisponde alla localita' cercata.

    Confronta anche le varianti linguistiche: "Italia" deve riconoscere
    "Scoppito, Italy", altrimenti il filtro elimina le offerte giuste.
    """
    place = normalize(haystack)
    if not place:
        return False
    for part in re.split(r"[,;/|]+", wanted):
        for variant in place_variants(part):
            if variant and (variant in place or place in variant):
                return True
    return False


def normalize_lines(text: str) -> str:
    """Come `normalize`, ma conserva gli a capo.

    L'analisi a sezioni di un curriculum si regge sul fatto che le intestazioni
    stanno su una riga propria: appiattire il testo la renderebbe impossibile.
    """
    if not text:
        return ""
    text = strip_accents(text.lower())
    text = text.replace("&", " and ")
    text = re.sub(r"[ \t\r\f\v ​]+", " ", text)
    text = re.sub(r"\n[ ]*", "\n", text)
    return text.strip()


def tokenize(text: str, keep_stopwords: bool = False) -> list[str]:
    """Estrae i token significativi. Conserva forme come c++, .net, ms-excel."""
    tokens = []
    for match in _TOKEN_RE.finditer(normalize(text)):
        token = match.group(0).strip(".-")
        if len(token) < 2:
            continue
        if not keep_stopwords and token in STOPWORDS:
            continue
        if token.isdigit() and len(token) < 4:
            continue
        tokens.append(token)
    return tokens


def ngrams(tokens: list[str], n: int) -> list[str]:
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


# --------------------------------------------------------------------------
# Similarita'
# --------------------------------------------------------------------------

class IdfIndex:
    """Pesi IDF calcolati sul corpus degli annunci gia' raccolti.

    Serve a evitare che parole onnipresenti negli annunci ("esperienza",
    "team", "cliente") contino quanto un termine discriminante come "hplc".
    """

    def __init__(self, documents: Iterable[str] | None = None) -> None:
        self.doc_count = 0
        self.df: Counter[str] = Counter()
        if documents:
            self.build(documents)

    def build(self, documents: Iterable[str]) -> "IdfIndex":
        self.df.clear()
        self.doc_count = 0
        for doc in documents:
            self.doc_count += 1
            self.df.update(set(tokenize(doc)))
        return self

    def weight(self, term: str) -> float:
        if self.doc_count < 5:
            # Corpus troppo piccolo per una statistica sensata: si ripiega su
            # un peso neutro, leggermente favorevole ai termini lunghi (che in
            # pratica sono quelli tecnici).
            return 1.0 + min(len(term), 14) / 28.0
        df = self.df.get(term, 0)
        return math.log((self.doc_count + 1) / (df + 1)) + 1.0

    def vector(self, text: str) -> dict[str, float]:
        counts = Counter(tokenize(text))
        if not counts:
            return {}
        max_count = max(counts.values())
        return {
            term: (0.5 + 0.5 * count / max_count) * self.weight(term)
            for term, count in counts.items()
        }


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    """Coseno fra due vettori sparsi. Ritorna un valore in [0, 1]."""
    if not a or not b:
        return 0.0
    smaller, larger = (a, b) if len(a) <= len(b) else (b, a)
    dot = sum(value * larger.get(term, 0.0) for term, value in smaller.items())
    if dot == 0.0:
        return 0.0
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def coverage(needle: str, haystack: str, idf: IdfIndex) -> float:
    """Quanta parte del testo `needle` (l'annuncio) e' coperta da `haystack` (il CV).

    Il coseno da solo penalizza i curriculum brevi contro annunci lunghi; questa
    misura asimmetrica risponde alla domanda giusta: dei requisiti citati
    nell'annuncio, quanti compaiono nel curriculum?
    """
    needle_terms = set(tokenize(needle))
    if not needle_terms:
        return 0.0
    haystack_terms = set(tokenize(haystack))
    total = sum(idf.weight(t) for t in needle_terms)
    if total == 0:
        return 0.0
    hit = sum(idf.weight(t) for t in needle_terms & haystack_terms)
    return hit / total
