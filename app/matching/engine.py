"""Calcolo della compatibilita' fra un curriculum e un'offerta.

Il punteggio finale e' una media pesata di sei componenti. La regola importante
e' che una componente non valutabile viene esclusa e i pesi vengono
rinormalizzati: se un annuncio non dichiara il titolo di studio richiesto, il
candidato non deve essere penalizzato per una richiesta che non esiste.

Ogni componente resta visibile nel dettaglio del risultato, cosi' il punteggio
si puo' sempre spiegare invece di essere un numero calato dall'alto.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from rapidfuzz import fuzz

from . import feedback
from .cv_parser import CVProfile
from .feedback import FeedbackProfile
from .skills import (
    ROLE_FAMILIES,
    domain_families,
    extract_education_fields,
    extract_education_level,
    extract_experience_requirement,
    extract_roles,
    extract_skills,
    fields_related,
    skill_group,
    skill_weight,
)
from .text import IdfIndex, coverage, cosine, normalize, place_matches, tokenize

DEFAULT_WEIGHTS = {
    "skills": 40.0,
    "similarity": 25.0,
    "title": 15.0,
    "education": 10.0,
    "experience": 5.0,
    "location": 5.0,
    # Non entra nella media: corregge il totale a posteriori (vedi
    # AMPIEZZA_FEEDBACK). Un criterio con neutro a 50 dentro una media che per
    # gli annunci fuori bersaglio vale 18 li farebbe salire, non scendere.
    "feedback": 0.0,
}

# Correzione per scarsita' di evidenza. Gli aggregatori restituiscono
# descrizioni troncate a poche righe: su quei testi il motore riconosce una o
# due competenze e qualunque corrispondenza risulta "perfetta". Questi due
# valori attirano il punteggio verso un valore neutro quando l'annuncio dice
# troppo poco, e lo lasciano intatto quando la descrizione e' completa.
EVIDENCE_PRIOR = 0.25   # rapporto tipico di copertura, usato come valore neutro
EVIDENCE_K = 4.0        # "competenze fantasma" aggiunte al denominatore
# Quota di peso che competenze e affinita' conservano anche sull'annuncio piu'
# scarno: sotto questa soglia smetterebbero del tutto di contare.
EVIDENCE_MIN_WEIGHT = 0.35
# Sotto questa lunghezza la descrizione non offre materiale sufficiente
# perche' la somiglianza testuale significhi qualcosa.
MIN_DESCRIPTION_CHARS = 900
# Quando l'annuncio pretende un'esperienza che il curriculum non ha, il
# criterio conta il doppio: e' uno sbarramento dichiarato, non un dettaglio.
_ENFASI_ESPERIENZA = 2.0
# Di quanto le offerte gia' scartate possono correggere il totale, in piu' o in
# meno. E' una correzione proporzionale, non un criterio a se': dice "questo
# assomiglia a cio' che hai rifiutato", non "vale 39 su 100".
AMPIEZZA_FEEDBACK = 0.25

LABELS = {
    "skills": "Competenze",
    "similarity": "Affinita' complessiva",
    "title": "Ruolo",
    "education": "Titolo di studio",
    "experience": "Esperienza",
    "location": "Sede",
    "feedback": "Tue preferenze",
}


@dataclass
class Component:
    key: str
    label: str
    score: float
    weight: float
    detail: str
    evaluated: bool = True
    # Alcune componenti pesano piu' del loro valore di listino a seconda di
    # cosa hanno trovato: un requisito esplicito e non soddisfatto conta piu'
    # di un criterio soddisfatto per caso.
    weight_multiplier: float = 1.0


@dataclass
class MatchResult:
    score: float
    components: list[Component] = field(default_factory=list)
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    bonus_skills: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 1),
            "components": [asdict(c) for c in self.components],
            "matched_skills": self.matched_skills,
            "missing_skills": self.missing_skills,
            "bonus_skills": self.bonus_skills,
            "reasons": self.reasons,
        }


@dataclass
class JobView:
    """La parte di un'offerta che interessa al punteggio."""

    title: str = ""
    company: str = ""
    description: str = ""
    location: str = ""
    city: str = ""
    country: str = ""
    remote: bool = False
    department: str = ""

    @property
    def text(self) -> str:
        return "\n".join(p for p in (self.title, self.department, self.description) if p)


# --------------------------------------------------------------------------
# Componenti
# --------------------------------------------------------------------------

def _score_skills(job: JobView, cv: CVProfile) -> tuple[Component, list[str], list[str], list[str]]:
    """Quanta parte delle competenze richieste dall'annuncio e' nel curriculum."""
    required = extract_skills(job.text)
    owned = set(cv.skills)
    if not required:
        return (
            Component("skills", LABELS["skills"], 0.0, DEFAULT_WEIGHTS["skills"],
                      "L'annuncio non cita competenze tecniche riconoscibili", evaluated=False),
            [], [], sorted(owned),
        )

    # Ordinate per peso: l'interfaccia mostra solo le prime, e deve mostrare
    # "HPLC" o "GMP" prima di "problem solving", che non distingue nessuno.
    by_weight = lambda s: -skill_weight(s)
    matched = sorted((s for s in required if s in owned), key=by_weight)
    missing = sorted((s for s in required if s not in owned), key=by_weight)
    total_weight = sum(skill_weight(s) for s in required)
    hit_weight = sum(skill_weight(s) for s in matched)
    ratio = hit_weight / total_weight if total_weight else 0.0

    # Le competenze del CV nello stesso ambito di quelle richieste valgono come
    # bonus: un profilo affine ma non identico non deve crollare a zero.
    required_groups = {skill_group(s) for s in required if skill_group(s)}
    bonus = [s for s in owned if s not in required and skill_group(s) in required_groups]
    if bonus and ratio < 1.0:
        ratio = min(1.0, ratio + 0.06 * min(len(bonus), 4))

    # Una corrispondenza su una competenza non vale quanto otto su nove: gli
    # aggregatori troncano le descrizioni, e su un testo breve il motore ne
    # riconosce una sola. Senza questa correzione un annuncio da due righe che
    # cita "sicurezza sul lavoro" superava un vero ruolo di laboratorio.
    # Il rapporto viene quindi attirato verso un valore neutro tanto piu'
    # quanto piu' scarso e' il campione (media bayesiana con prior EVIDENCE_PRIOR).
    shrunk = (hit_weight + EVIDENCE_PRIOR * EVIDENCE_K) / (total_weight + EVIDENCE_K)
    ratio = min(ratio, shrunk) if len(required) < 4 else max(ratio * 0.9, shrunk)

    detail = f"{len(matched)} competenze richieste su {len(required)} presenti nel curriculum"
    if len(required) < 3:
        detail += " — l'annuncio ne cita troppo poche per una valutazione solida"
    return (
        Component("skills", LABELS["skills"], ratio * 100, DEFAULT_WEIGHTS["skills"], detail),
        matched, missing, sorted(bonus),
    )


def _score_similarity(job: JobView, cv: CVProfile, idf: IdfIndex) -> Component:
    """Somiglianza lessicale complessiva fra i due testi.

    Si combinano coseno (simmetrico) e copertura (asimmetrica, dal punto di
    vista dell'annuncio): il primo premia i profili affini, la seconda misura
    quanto dei requisiti e' effettivamente coperto.
    """
    job_text, cv_text = job.text, cv.raw_text
    if not job_text.strip() or not cv_text.strip():
        return Component("similarity", LABELS["similarity"], 0.0, DEFAULT_WEIGHTS["similarity"],
                         "Testo insufficiente per il confronto", evaluated=False)

    cos = cosine(idf.vector(job_text), idf.vector(cv_text))
    cov = coverage(job_text, cv_text, idf)
    # La copertura pesa di piu': e' la domanda che conta davvero.
    raw = 0.35 * cos + 0.65 * cov
    # I valori grezzi di coseno su testi lunghi restano bassi; questa curva li
    # riporta su una scala leggibile senza alterare l'ordinamento. Il fattore e'
    # volutamente prudente: il 100 pieno deve restare difficile da raggiungere.
    scaled = min(1.0, raw * 1.6) ** 0.85

    # Su una descrizione troncata la copertura e' alta per costruzione: pochi
    # termini, quindi facili da coprire tutti. Il punteggio viene riportato
    # verso il valore neutro in proporzione a quanto testo manca.
    evidence = min(1.0, len(job_text) / MIN_DESCRIPTION_CHARS)
    scaled = scaled * evidence + EVIDENCE_PRIOR * (1 - evidence)

    detail = f"copertura dei termini dell'annuncio {cov * 100:.0f}%, affinita' generale {cos * 100:.0f}%"
    if evidence < 1.0:
        detail += f" — descrizione breve ({len(job_text)} caratteri), attendibilita' ridotta"
    return Component("similarity", LABELS["similarity"], scaled * 100, DEFAULT_WEIGHTS["similarity"], detail)


def _role_families(text: str) -> set[str]:
    return domain_families(extract_roles(text))


def _tokens_match(a: str, b: str) -> bool:
    """Uguaglianza fra token, tollerante ai prefissi.

    Serve perche' le parole chiave si scrivono spesso troncate ("biotecnolog",
    "chimic") apposta per coprire maschile, femminile e plurale.
    """
    if a == b:
        return True
    return len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a))


def title_affinity(title: str, candidate: str) -> float:
    """Quanto un'espressione descrive il titolo di un annuncio, da 0 a 100.

    Non si puo' usare `token_set_ratio`: restituisce 100 quando i token di una
    stringa sono un sottoinsieme dell'altra, quindi la parola chiave "stage"
    contro "Stage Magazziniere Ifo San Gallicano" dava una corrispondenza
    perfetta, e ogni tirocinio d'Italia risultava il lavoro ideale.

    Qui si usa la media armonica fra quanto del titolo e' spiegato dal
    candidato e quanto del candidato compare nel titolo: una parola su cinque
    resta una parola su cinque.
    """
    # Nessun filtro sulla lunghezza: gli acronimi di due lettere (QC, QA, HR)
    # sono fra i termini di ricerca piu' usati e non vanno scartati. Il
    # confronto per prefisso resta invece riservato ai token lunghi, cosi'
    # "qc" non finisce per somigliare a "qualcosa".
    title_tokens = tokenize(title)
    cand_tokens = tokenize(candidate)
    if not title_tokens or not cand_tokens:
        return 0.0

    hits = sum(1 for c in cand_tokens if any(_tokens_match(c, t) for t in title_tokens))
    if hits:
        precision = hits / len(cand_tokens)
        recall = sum(
            1 for t in title_tokens if any(_tokens_match(c, t) for c in cand_tokens)
        ) / len(title_tokens)
        return 100.0 * 2 * precision * recall / (precision + recall)

    # Nessun token in comune: resta solo una somiglianza ortografica, che vale
    # poco e viene compressa per non regalare punti al rumore.
    return float(fuzz.token_sort_ratio(normalize(title), normalize(candidate))) * 0.35


def _score_title(job: JobView, cv: CVProfile, keywords: Iterable[str]) -> Component:
    """Vicinanza fra il ruolo dell'annuncio e i ruoli del candidato."""
    title = normalize(job.title)
    if not title:
        return Component("title", LABELS["title"], 0.0, DEFAULT_WEIGHTS["title"],
                         "Titolo dell'annuncio assente", evaluated=False)

    # Solo dal titolo: cercare le aree professionali dentro la descrizione
    # faceva risultare "Electronic Design" affine alla produzione farmaceutica
    # perche' l'annuncio nominava di sfuggita la parola "produzione".
    job_families = _role_families(job.title)
    cv_families = domain_families(cv.roles)
    family_score = 0.0
    shared: set[str] = set()
    if job_families and cv_families:
        shared = job_families & cv_families
        family_score = 100.0 * len(shared) / len(job_families) if shared else 0.0

    candidates = [k for k in keywords if k]
    for family in cv_families:
        candidates.extend(ROLE_FAMILIES.get(family, [])[:6])
    lexical = max((title_affinity(job.title, c) for c in candidates), default=0.0)

    score = max(family_score, lexical)
    if shared:
        detail = f"stessa area professionale: {', '.join(sorted(shared))}"
    elif lexical >= 55:
        detail = "il titolo dell'annuncio richiama le parole chiave della ricerca"
    else:
        detail = "ruolo distante da quelli presenti nel curriculum"
    return Component("title", LABELS["title"], score, DEFAULT_WEIGHTS["title"], detail)


def _score_education(job: JobView, cv: CVProfile) -> Component:
    """Confronto fra titolo di studio richiesto e posseduto."""
    required_level, required_label = extract_education_level(job.text)
    required_fields = set(extract_education_fields(job.text))
    if not required_level and not required_fields:
        return Component("education", LABELS["education"], 0.0, DEFAULT_WEIGHTS["education"],
                         "L'annuncio non indica un titolo di studio", evaluated=False)

    parts: list[str] = []
    level_score = 100.0
    if required_level:
        if cv.education_level >= required_level:
            level_score = 100.0
            parts.append(f"livello richiesto ({required_label}) soddisfatto")
        elif cv.education_level == 0:
            level_score = 30.0
            parts.append(f"richiesto {required_label}, nessun titolo riconosciuto nel curriculum")
        else:
            gap = required_level - cv.education_level
            level_score = max(20.0, 100.0 - 30.0 * gap)
            parts.append(f"richiesto {required_label}, nel curriculum {cv.education_label}")

    field_score = 100.0
    if required_fields:
        owned = set(cv.education_fields)
        shared = required_fields & owned
        related = fields_related(required_fields, owned)
        if shared:
            field_score = 100.0
            parts.append(f"ambito coerente: {', '.join(sorted(shared))}")
        elif related:
            # Percorsi diversi ma della stessa area: parentela riconosciuta.
            field_score = 75.0
            parts.append(
                f"ambito affine ({', '.join(sorted(related))}): richiesto "
                f"{', '.join(sorted(required_fields))}, nel curriculum {', '.join(sorted(owned))}"
            )
        elif owned:
            field_score = 40.0
            parts.append(
                f"ambito richiesto {', '.join(sorted(required_fields))}, nel curriculum {', '.join(sorted(owned))}"
            )
        else:
            field_score = 35.0
            parts.append(f"ambito richiesto {', '.join(sorted(required_fields))}, non rilevato nel curriculum")

    score = (level_score + field_score) / 2 if (required_level and required_fields) else (
        level_score if required_level else field_score
    )
    return Component("education", LABELS["education"], score, DEFAULT_WEIGHTS["education"], "; ".join(parts))


def _esperienza_muta(motivo: str) -> Component:
    """Criterio presente ma senza valore informativo: resta fuori dalla media."""
    return Component("experience", LABELS["experience"], 0.0,
                     DEFAULT_WEIGHTS["experience"], motivo, evaluated=False)


def _score_experience(job: JobView, cv: CVProfile) -> Component:
    """Confronta l'esperienza chiesta con quella del curriculum.

    Gli annunci quantificano gli anni una volta su sei: le altre cinque
    scrivono "esperienza pregressa nel ruolo" e basta. Considerare solo la
    prima forma faceva sparire il criterio proprio dagli annunci che
    pretendevano esperienza, e il loro punteggio saliva invece di scendere.
    """
    req = extract_experience_requirement(job.text)
    if not req.required:
        return Component("experience", LABELS["experience"], 0.0, DEFAULT_WEIGHTS["experience"],
                         "L'annuncio non chiede esperienza specifica", evaluated=False)

    have = cv.years_experience
    citazione = f" — «{req.evidence[:90].strip()}»" if req.evidence else ""

    if req.years is not None:
        quanto = f"{req.years:.0f} anni" if req.years >= 1 else f"{req.years * 12:.0f} mesi"
        copertura = min(1.0, have / req.years) if req.years > 0 else 1.0
        if not req.hard and copertura < 1:
            # Una preferenza non soddisfatta non e' un'informazione: premiarla
            # farebbe salire annunci che non c'entrano nulla.
            return _esperienza_muta(f"{quanto} graditi ma non richiesti")
        coda = f"stimati {have:.1f} nel curriculum" if have > 0 else "il curriculum non ne riporta"
        if req.hard:
            # Un requisito non soddisfatto deve pesare, ma senza azzerare il
            # punteggio: nessun singolo criterio decide da solo l'esito.
            return Component("experience", LABELS["experience"], max(15.0, 100.0 * copertura),
                             DEFAULT_WEIGHTS["experience"],
                             f"richiesti {quanto}, {coda}{citazione}",
                             weight_multiplier=_ENFASI_ESPERIENZA if copertura < 1 else 1.0)
        return Component("experience", LABELS["experience"], 100.0,
                         DEFAULT_WEIGHTS["experience"], f"graditi {quanto}, {coda}{citazione}")

    # Esperienza chiesta senza dire quanta.
    if have > 0:
        return Component("experience", LABELS["experience"], 100.0,
                         DEFAULT_WEIGHTS["experience"],
                         f"esperienza richiesta, {have:.1f} anni nel curriculum{citazione}")
    if req.hard:
        # Stesso pavimento del caso quantificato: un requisito dichiarato e non
        # soddisfatto vale zero, non "mezzo". Un valore intermedio finiva per
        # alzare la media degli annunci che non c'entravano nulla.
        return Component("experience", LABELS["experience"], 15.0,
                         DEFAULT_WEIGHTS["experience"],
                         f"esperienza pregressa richiesta, il curriculum non ne riporta{citazione}",
                         weight_multiplier=_ENFASI_ESPERIENZA)
    return _esperienza_muta("esperienza gradita ma non richiesta")


def _score_location(job: JobView, wanted_location: str, remote_ok: bool) -> Component:
    wanted = normalize(wanted_location)
    if not wanted:
        return Component("location", LABELS["location"], 0.0, DEFAULT_WEIGHTS["location"],
                         "Nessuna localita' indicata nella ricerca", evaluated=False)
    haystack = normalize(" ".join(p for p in (job.location, job.city, job.country) if p))
    if job.remote and remote_ok:
        return Component("location", LABELS["location"], 100.0, DEFAULT_WEIGHTS["location"],
                         "posizione da remoto")
    if not haystack:
        return Component("location", LABELS["location"], 50.0, DEFAULT_WEIGHTS["location"],
                         "sede non indicata nell'annuncio")
    # Anche qui il confronto passa dalle varianti linguistiche, altrimenti una
    # ricerca su "Italia" non riconoscerebbe una sede scritta "Milan, Italy".
    if place_matches(wanted_location, haystack):
        return Component("location", LABELS["location"], 100.0, DEFAULT_WEIGHTS["location"],
                         f"sede corrispondente ({job.location or job.city})")
    ratio = fuzz.partial_ratio(wanted, haystack)
    score = float(ratio) if ratio >= 70 else max(10.0, ratio * 0.5)
    return Component("location", LABELS["location"], score, DEFAULT_WEIGHTS["location"],
                     f"sede dell'annuncio: {job.location or job.city or 'non indicata'}")


# --------------------------------------------------------------------------
# Punteggio complessivo
# --------------------------------------------------------------------------

def _score_feedback(job: JobView, profile: "FeedbackProfile | None") -> Component:
    """Confronta l'annuncio con quelli gia' scartati e con quelli tenuti.

    Resta fuori dal punteggio finche' gli scarti non sono abbastanza da
    distinguere una preferenza da una coincidenza.
    """
    if profile is None:
        return Component("feedback", LABELS["feedback"], 0.0, DEFAULT_WEIGHTS["feedback"],
                         "Nessuna offerta scartata da cui imparare", evaluated=False)
    esito = feedback.evaluate(job.title, job.text, profile)
    if esito is None:
        mancanti = max(0, feedback.MIN_SCARTI - profile.discarded)
        motivo = (f"servono ancora {mancanti} offerte scartate per imparare"
                  if mancanti else "non somiglia in modo netto ne' alle offerte tenute ne' a quelle scartate")
        return Component("feedback", LABELS["feedback"], 0.0, DEFAULT_WEIGHTS["feedback"],
                         motivo.capitalize(), evaluated=False)
    punteggio, decisivi = esito
    if punteggio < 45 and decisivi:
        dettaglio = "ricorda le offerte che hai scartato: " + ", ".join(decisivi)
    elif punteggio < 45:
        dettaglio = "somiglia alle offerte che hai scartato"
    elif punteggio > 55:
        dettaglio = "in linea con le offerte che hai tenuto"
    else:
        dettaglio = "nessuna somiglianza netta con le offerte gia' giudicate"
    return Component("feedback", LABELS["feedback"], punteggio,
                     DEFAULT_WEIGHTS["feedback"],
                     f"{dettaglio} (su {profile.discarded} scarti)")


def score_job(
    job: JobView,
    cv: CVProfile,
    idf: IdfIndex,
    *,
    keywords: Iterable[str] = (),
    wanted_location: str = "",
    remote_ok: bool = True,
    weights: dict[str, float] | None = None,
    profile: FeedbackProfile | None = None,
) -> MatchResult:
    """Calcola il punteggio 0-100 fra un'offerta e un curriculum."""
    active_weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    # I motivi degli scarti dicono quale criterio guardare per primo: chi
    # scarta sempre per "chiede troppa esperienza" vuole che quel criterio
    # conti di piu' di quanto conti per tutti gli altri.
    enfasi = profile.emphasis() if profile else {}

    skills_component, matched, missing, bonus = _score_skills(job, cv)
    components = [
        skills_component,
        _score_similarity(job, cv, idf),
        _score_title(job, cv, keywords),
        _score_education(job, cv),
        _score_experience(job, cv),
        _score_location(job, wanted_location, remote_ok),
        _score_feedback(job, profile),
    ]
    for component in components:
        component.weight = active_weights.get(component.key, component.weight)
        component.weight *= component.weight_multiplier * enfasi.get(component.key, 1.0)

    # Quanto materiale offre l'annuncio. Gli aggregatori troncano le descrizioni
    # a poche righe: su quei testi competenze e affinita' sono inaffidabili.
    # Il peso che perdono non va disperso, ma trasferito al ruolo: in un
    # annuncio di due righe il titolo e' l'unico segnale che si legge davvero,
    # ed e' quello che distingue "Tecnico di Laboratorio" da "Magazziniere".
    # Un annuncio completo non viene toccato.
    evidence = min(1.0, len(job.text) / MIN_DESCRIPTION_CHARS)
    if evidence < 1.0:
        factor = max(EVIDENCE_MIN_WEIGHT, evidence)
        for component in components:
            if component.key in ("skills", "similarity"):
                component.weight *= factor
        # Il ruolo riceve parte del peso liberato, ma non piu' del doppio del
        # suo valore di partenza: una sola componente non deve mai arrivare a
        # decidere da sola l'esito, perche' un suo errore diventerebbe l'errore
        # dell'intero punteggio.
        base_title = active_weights.get("title", DEFAULT_WEIGHTS["title"])
        for component in components:
            if component.key == "title":
                component.weight = min(base_title * 2, base_title / max(factor, 0.2))
                component.detail += " — descrizione breve, il ruolo pesa di piu'"

    # Solo le componenti valutabili entrano nella media, con i pesi rinormalizzati.
    evaluated = [c for c in components if c.evaluated and c.weight > 0]
    total_weight = sum(c.weight for c in evaluated)
    score = sum(c.score * c.weight for c in evaluated) / total_weight if total_weight else 0.0

    # Le offerte gia' scartate correggono il risultato in proporzione, senza
    # mediarsi con gli altri criteri.
    preferenze = next(c for c in components if c.key == "feedback")
    if preferenze.evaluated:
        correzione = AMPIEZZA_FEEDBACK * (preferenze.score / 100.0 - 0.5) * 2
        score *= 1 + correzione
        preferenze.detail += f" — punteggio corretto del {correzione * 100:+.0f}%"

    reasons: list[str] = []
    if matched:
        reasons.append("Competenze in comune: " + ", ".join(matched[:8]))
    if missing:
        reasons.append("Richieste ma non rilevate: " + ", ".join(missing[:8]))
    for component in components:
        if not component.evaluated:
            reasons.append(f"{component.label}: non valutabile - {component.detail.lower()}")

    return MatchResult(
        score=max(0.0, min(100.0, score)),
        components=components,
        matched_skills=matched,
        missing_skills=missing,
        bonus_skills=bonus,
        reasons=reasons,
    )
