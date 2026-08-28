"""Impara dalle offerte scartate.

Ogni volta che un'offerta viene messa fra gli scarti, con o senza una nota,
lascia un'indicazione su cosa non va. Questo modulo la raccoglie e la
restituisce in tre forme, perche' i tre consumatori sono diversi:

* un **peso lessicale** per termine, calcolato confrontando cosa compare negli
  annunci scartati e cosa in quelli tenuti. Serve al motore di punteggio.
* una **enfasi sui criteri**: se gli scarti citano quasi sempre l'esperienza,
  quel criterio deve contare di piu' nel punteggio di tutti gli annunci.
* un **riassunto in prosa** delle note, che finisce nel prompt del modello
  linguistico. E' l'unica delle tre che funziona gia' col primo scarto.

Il punto delicato e' la scarsita': con cinque scarti qualunque parola sembra
decisiva. Per questo il segnale lessicale resta spento sotto una soglia minima
e, appena sopra, viene attenuato in proporzione a quanti esempi esistono
davvero. Meglio non dire nulla che dire una cosa a caso.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

from typing import Iterable

from .skills import extract_roles, extract_skills
from .text import tokenize

# Motivi proposti quando si scarta un'offerta. La chiave finisce nel database,
# l'etichetta e' quella che si legge. `component` collega il motivo al criterio
# del punteggio che quel motivo mette in discussione: e' cosi' che una serie di
# scarti per "troppa esperienza" fa pesare di piu' il criterio Esperienza.
REASONS: dict[str, dict[str, str]] = {
    "esperienza": {"label": "Chiede troppa esperienza", "component": "experience"},
    "ruolo": {"label": "Ruolo diverso da quello che cerco", "component": "title"},
    "settore": {"label": "Settore che non mi interessa", "component": "skills"},
    "requisiti": {"label": "Requisiti che non ho", "component": "skills"},
    "sede": {"label": "Sede scomoda", "component": "location"},
    "studi": {"label": "Titolo di studio non pertinente", "component": "education"},
    "contratto": {"label": "Contratto o condizioni non adatti", "component": ""},
    "altro": {"label": "Altro", "component": ""},
}

POSITIVE_STATUSES = ("saved", "applied", "interview", "offer")
NEGATIVE_STATUSES = ("discarded", "rejected")

# Solo questi motivi dicono qualcosa sul *contenuto* dell'offerta, e solo loro
# possono insegnare quali tratti segnalano un'offerta da scartare.
#
# Chi scarta un'offerta di controllo qualita' perche' chiede tre anni di
# esperienza non sta dicendo che il controllo qualita' non gli interessa: sta
# dicendo il contrario, che gli interessava ma non poteva candidarsi. Trattare
# quello scarto come un giudizio sul mestiere insegnava esattamente l'opposto
# di quello che era stato detto, e faceva scendere le offerte piu' desiderate.
#
# Gli scarti per esperienza, sede o contratto restano pienamente validi: fanno
# pesare di piu' il criterio corrispondente (vedi `emphasis`) e finiscono nel
# riassunto per il modello linguistico. Semplicemente non toccano il vocabolario.
MOTIVI_SUL_CONTENUTO = frozenset({"ruolo", "settore", "requisiti", "studi"})

# Sotto questa soglia il segnale lessicale resta spento: con pochi esempi
# distinguerebbe le abitudini di scrittura di due annunci, non i motivi veri.
MIN_SCARTI = 5
# Attenuazione bayesiana: con 5 scarti il segnale vale la meta', con 20 quasi
# tutto. Evita che i primi esempi decidano da soli.
FIDUCIA_K = 5.0
# Un termine conta solo se e' apparso almeno in tanti documenti...
MIN_DOCUMENTI = 2
# ...e presso almeno due aziende diverse. Senza questo vincolo il modello
# impara la boilerplate di chi scrive gli annunci invece del mestiere: tre
# offerte della stessa azienda bastavano a far sembrare decisive parole come
# "decentralised" o "portfolio".
MIN_AZIENDE = 2
# Quanti termini tenere: oltre si entra nel rumore.
MAX_TERMINI = 120
# Un tratto deve ricorrere in una quota consistente degli scarti, non in due o
# tre. Con tredici scarti, un tratto presente in due non distingue nulla: e'
# la frequenza con cui capita qualsiasi parola in un mucchietto di annunci.
MIN_QUOTA_SCARTI = 0.20
MIN_SCARTI_PER_TRATTO = 3
# Somma di log-odds oltre la quale il giudizio e' considerato netto.
SCALA_EVIDENZA = 4.0
# Sotto questa evidenza il criterio non ha un'opinione e resta fuori dalla
# media. Un valore "neutro" partecipante varrebbe piu' dei criteri veri sugli
# annunci che non c'entrano nulla, e li farebbe salire invece che scendere.
SOGLIA_NETTA = 0.18
# Nessun termine puo' decidere da solo: con pochi esempi una parola presente in
# due scarti e in nessuna offerta tenuta sembrerebbe una prova schiacciante.
PESO_MASSIMO = 1.5
# Quanti termini di un annuncio possono contribuire: un testo lungo accumula
# altrimenti decine di piccoli indizi fino a un totale che nessuno ha voluto.
MAX_CONTRIBUTI = 20
# Quanto puo' crescere il peso di un criterio citato spesso negli scarti.
MAX_ENFASI = 1.6
# Sotto questa quota di scarti un motivo non muove i pesi.
QUOTA_MINIMA_MOTIVO = 0.3

_ALPHA = 0.5   # smoothing di Laplace


def protected_traits(skills: Iterable[str] = (), roles: Iterable[str] = (),
                     fields: Iterable[str] = (), keywords: Iterable[str] = ()) -> set[str]:
    """Tratti che non possono mai diventare un segnale di scarto.

    Sono quelli che l'utente ha dichiarato di volere: le parole delle sue
    ricerche, le competenze e i ruoli del suo curriculum, i suoi ambiti di
    studio. Un'inferenza statistica su una dozzina di esempi non puo'
    contraddire una preferenza scritta a mano.

    Serve perche' chi cerca "Quality control" scarta soprattutto offerte di
    controllo qualita': sono le uniche che gli vengono mostrate. Il conteggio
    grezzo ne concludeva che il controllo qualita' fosse il problema.
    """
    protetti: set[str] = set()
    for competenza in skills:
        protetti.add(f"c:{competenza}")
        protetti.update(f"t:{x}" for x in tokenize(competenza) if len(x) > 2)
    for ruolo in roles:
        protetti.add(f"r:{ruolo}")
        protetti.update(f"t:{x}" for x in tokenize(ruolo) if len(x) > 2)
    for testo in (*fields, *keywords):
        protetti.update(f"t:{x}" for x in tokenize(testo) if len(x) > 2)
        for competenza in extract_skills(testo):
            protetti.add(f"c:{competenza}")
        for ruolo in extract_roles(testo):
            protetti.add(f"r:{ruolo}")
    return protetti


@dataclass
class DiscardedExample:
    """Un'offerta scartata, come la vede il modello linguistico."""

    title: str = ""
    company: str = ""
    reasons: list[str] = field(default_factory=list)
    note: str = ""

    def describe(self) -> str:
        motivi = ", ".join(REASONS.get(r, {}).get("label", r).lower() for r in self.reasons)
        pezzi = [p for p in (f"«{self.title}»" if self.title else "", self.company) if p]
        testa = " presso ".join(pezzi) if len(pezzi) == 2 else (pezzi[0] if pezzi else "un'offerta")
        coda = "; ".join(p for p in (motivi, self.note.strip()) if p)
        return f"- {testa}: {coda}" if coda else f"- {testa}"


@dataclass
class FeedbackProfile:
    """Cosa si e' imparato finora dalle scelte fatte sulle offerte."""

    discarded: int = 0
    kept: int = 0
    # Quanti scarti riguardano il contenuto: sono gli unici che alimentano il
    # vocabolario. Gli altri contano per i motivi, non per la somiglianza.
    topical: int = 0
    reasons: dict[str, int] = field(default_factory=dict)
    examples: list[DiscardedExample] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)
    # Su quanti scarti poggia ciascun tratto: si mostra accanto al tratto,
    # perche' "in 4 scarti su 13" e' un'informazione che l'utente sa leggere
    # meglio di un log-odds.
    support: dict[str, int] = field(default_factory=dict)

    @property
    def ready(self) -> bool:
        """Il segnale lessicale ha abbastanza esempi per dire qualcosa."""
        return self.topical >= MIN_SCARTI and bool(self.weights)

    @property
    def confidence(self) -> float:
        """Quanto fidarsi, fra 0 e 1, del segnale lessicale."""
        return self.topical / (self.topical + FIDUCIA_K) if self.topical else 0.0

    def emphasis(self) -> dict[str, float]:
        """Moltiplicatori di peso per i criteri citati spesso negli scarti.

        Non serve la soglia degli esempi: dieci scarti su dieci motivati con
        "chiede troppa esperienza" sono un'indicazione chiara anche se il
        vocabolario non ha ancora nulla da dire.
        """
        totale = sum(self.reasons.values())
        if totale < 3:
            return {}
        pesi: dict[str, float] = {}
        for motivo, conteggio in self.reasons.items():
            componente = REASONS.get(motivo, {}).get("component", "")
            quota = conteggio / totale
            if not componente or quota < QUOTA_MINIMA_MOTIVO:
                continue
            # Da 1.0 (quota minima) fino a MAX_ENFASI (tutti gli scarti).
            crescita = (quota - QUOTA_MINIMA_MOTIVO) / (1 - QUOTA_MINIMA_MOTIVO)
            pesi[componente] = max(pesi.get(componente, 1.0), 1.0 + crescita * (MAX_ENFASI - 1))
        return pesi

    def summary(self) -> str:
        """Le note e i motivi, pronti per il prompt del modello linguistico."""
        if not self.examples:
            return ""
        righe = [e.describe() for e in self.examples if e.describe()]
        return "\n".join(righe)

    def top_terms(self, limit: int = 12) -> list[tuple[str, str, int]]:
        """I tratti piu' indicativi di uno scarto, per mostrarli all'utente.

        Restituisce (chiave, etichetta, quanti scarti lo sostengono).
        """
        ordinati = sorted(self.weights.items(), key=lambda kv: -kv[1])[:limit]
        return [(t, _etichetta(t), self.support.get(t, 0)) for t, w in ordinati if w > 0]

    def to_dict(self) -> dict:
        return {
            "discarded": self.discarded,
            "topical": self.topical,
            "kept": self.kept,
            "ready": self.ready,
            "confidence": round(self.confidence, 2),
            "min_discarded": MIN_SCARTI,
            "reasons": [
                {"key": k, "label": REASONS.get(k, {}).get("label", k), "count": v}
                for k, v in sorted(self.reasons.items(), key=lambda kv: -kv[1])
            ],
            "emphasis": {k: round(v, 2) for k, v in self.emphasis().items()},
            "terms": [{"key": k, "term": etichetta, "support": n}
                      for k, etichetta, n in self.top_terms()],
            "topical_min": MIN_SCARTI_PER_TRATTO,
        }


def _documento(title: str, text: str) -> set[str]:
    """I tratti di un annuncio su cui ha senso generalizzare.

    Non il testo intero: con una manciata di esempi le parole del corpo
    dell'annuncio descrivono chi lo ha scritto piu' di che lavoro sia. Il
    titolo e le competenze riconosciute dall'ontologia dicono molto di piu'
    per esempio.
    """
    tratti = {f"t:{t}" for t in tokenize(title or "") if len(t) > 2}
    tratti |= {f"c:{s}" for s in extract_skills(text or "")}
    tratti |= {f"r:{r}" for r in extract_roles(text or "")}
    return tratti


def _etichetta(tratto: str) -> str:
    """Come mostrare un tratto all'utente."""
    prefisso, _, resto = tratto.partition(":")
    return {"c": resto, "r": f"ruolo {resto}"}.get(prefisso, resto)


def build_profile(discarded: list[dict], kept: list[dict],
                  protected: Iterable[str] = (), excluded: Iterable[str] = ()) -> FeedbackProfile:
    """Costruisce il profilo dalle offerte gia' giudicate.

    Ogni voce e' un dizionario con `text`, e per gli scarti anche `title`,
    `company`, `reasons` e `notes`.

    `protected` sono i tratti che l'utente ha dichiarato di volere e che quindi
    non possono diventare segnali di scarto; `excluded` quelli che ha tolto a
    mano dopo averli visti sbagliati.
    """
    vietati = set(protected) | {f"t:{x}" for e in excluded for x in tokenize(e)} | set(excluded)
    profilo = FeedbackProfile(discarded=len(discarded), kept=len(kept))

    motivi: Counter[str] = Counter()
    for voce in discarded:
        motivi.update(voce.get("reasons") or [])
        profilo.examples.append(DiscardedExample(
            title=(voce.get("title") or "")[:90],
            company=(voce.get("company") or "")[:60],
            reasons=list(voce.get("reasons") or []),
            note=(voce.get("notes") or "")[:220],
        ))
    profilo.reasons = dict(motivi)

    # Un'offerta insegna quali contenuti evitare solo se e' stata scartata per
    # un motivo che parla del contenuto. Senza motivo indicato non si puo' che
    # leggerla come un giudizio sull'offerta intera, e quindi vale.
    sul_contenuto = [v for v in discarded
                     if not (v.get("reasons") or [])
                     or (set(v.get("reasons") or []) & MOTIVI_SUL_CONTENUTO)]
    profilo.topical = len(sul_contenuto)

    if profilo.topical < MIN_SCARTI:
        return profilo

    df_scarto: Counter[str] = Counter()
    df_tenuto: Counter[str] = Counter()
    aziende: dict[str, set[str]] = {}
    for voci, contatore in ((sul_contenuto, df_scarto), (kept, df_tenuto)):
        for voce in voci:
            tratti = _documento(voce.get("title") or "", voce.get("text") or "")
            contatore.update(tratti)
            azienda = (voce.get("company") or "?").strip().lower()
            for tratto in tratti:
                aziende.setdefault(tratto, set()).add(azienda)

    n_scarto, n_tenuto = len(sul_contenuto), len(kept)
    soglia = max(MIN_SCARTI_PER_TRATTO, round(MIN_QUOTA_SCARTI * n_scarto))
    pesi: dict[str, float] = {}
    for termine in set(df_scarto) | set(df_tenuto):
        presenze = df_scarto[termine] + df_tenuto[termine]
        if presenze < MIN_DOCUMENTI or len(aziende.get(termine, ())) < MIN_AZIENDE:
            continue
        # Un tratto diventa segnale di scarto solo se ricorre davvero fra gli
        # scarti e se l'utente non ha dichiarato di volerlo.
        if df_scarto[termine] and (termine in vietati or df_scarto[termine] < soglia):
            continue
        p_scarto = (df_scarto[termine] + _ALPHA) / (n_scarto + 2 * _ALPHA)
        p_tenuto = (df_tenuto[termine] + _ALPHA) / (n_tenuto + 2 * _ALPHA)
        peso = math.log(p_scarto / p_tenuto)
        if abs(peso) < 0.2:
            continue
        pesi[termine] = max(-PESO_MASSIMO, min(PESO_MASSIMO, peso))

    # Si tengono i piu' netti da entrambe le parti: i termini che segnalano uno
    # scarto e quelli che segnalano un'offerta buona.
    ordinati = sorted(pesi.items(), key=lambda kv: -abs(kv[1]))[:MAX_TERMINI]
    profilo.weights = dict(ordinati)
    profilo.support = {t: df_scarto[t] for t, _ in ordinati}
    return profilo


def evaluate(title: str, text: str, profile: FeedbackProfile) -> tuple[float, list[str]] | None:
    """Quanto un annuncio somiglia a quelli scartati.

    Restituisce un punteggio 0-100 (100 = somiglia a quelli tenuti) e i tratti
    che hanno pesato di piu'. None quando non c'e' materiale per rispondere.
    """
    if not profile.ready or not (title or text):
        return None
    termini = _documento(title, text)
    contributi = [(t, profile.weights[t]) for t in termini if t in profile.weights]
    if not contributi:
        return None

    decisivi = sorted(contributi, key=lambda kv: -abs(kv[1]))[:MAX_CONTRIBUTI]
    evidenza = sum(w for _, w in decisivi)
    # Attenuazione: con pochi scarti il giudizio resta vicino al neutro.
    normalizzata = max(-1.0, min(1.0, evidenza / SCALA_EVIDENZA)) * profile.confidence
    if abs(normalizzata) < SOGLIA_NETTA:
        return None
    return 50.0 - 50.0 * normalizzata, [_etichetta(t) for t, w in decisivi[:4] if w > 0]
