"""Livello semantico opzionale, indipendente dal fornitore.

Disattivato per impostazione predefinita: senza chiave l'applicazione funziona
interamente con il motore lessicale, che non costa nulla e non richiede
connessione.

Sono supportati due fornitori, scelti dalle impostazioni:

* **Gemini** (Google AI Studio) - chiave gratuita con un normale account Google,
  senza carta di credito. E' l'opzione piu' accessibile.
* **Claude** (Console Anthropic) - richiede un'organizzazione Console con
  fatturazione, che e' un servizio separato dall'abbonamento Claude.

Quando e' attivo, il modello non sostituisce il punteggio lessicale ma lo
affianca: la percentuale finale e' una media pesata dei due, e il giudizio resta
visibile nel dettaglio dell'offerta. Serve a cogliere le affinita' che il
confronto per parole non vede - per esempio che chi ha lavorato su colture
cellulari e saggi di vitalita' e' un candidato sensato per un ruolo di
tossicologia in vitro, anche senza una parola in comune.

Per contenere la spesa il modello viene interpellato solo sulle offerte che il
motore lessicale ha gia' giudicato promettenti.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from pydantic import BaseModel, Field

from ..config import SECRETS

log = logging.getLogger("jobseeker.llm")

# Limite di caratteri inviati per ciascun testo: gli annunci lunghi ripetono le
# stesse informazioni e non serve pagarne (o attenderne) la coda.
MAX_JOB_CHARS = 6000
MAX_CV_CHARS = 6000
# Le offerte scartate si accumulano: se ne manda un estratto, non l'elenco.
MAX_FEEDBACK_CHARS = 2000

SYSTEM = """Sei un selezionatore esperto del mercato del lavoro italiano.
Valuti quanto un curriculum sia adatto a un'offerta di lavoro, e spieghi al
candidato perche' l'offerta fa o non fa per lui.

Criteri:
- Conta la sostanza delle competenze, non le parole esatte: tecniche equivalenti
  o trasferibili valgono quanto una corrispondenza letterale.
- Considera se il candidato potrebbe realisticamente superare una prima
  selezione per quella posizione.
- Un profilo molto piu' qualificato del richiesto non e' un match perfetto:
  segnala il disallineamento di seniority.
- Sii severo: 90 o piu' significa candidato ideale, 70 candidato solido,
  50 candidatura sensata ma incerta, sotto 30 fuori bersaglio.
- Rispondi sempre in italiano.

Come scrivere la spiegazione:
- Cita i requisiti con le parole dell'annuncio, non in astratto. «Chiede tre
  anni su linee GMP, nel curriculum non compaiono» e' utile; «esperienza non
  del tutto allineata» non lo e'.
- Fra i requisiti non coperti metti solo cose che l'annuncio chiede davvero e
  che nel curriculum non ci sono. Se non ne trovi, lascia l'elenco vuoto:
  inventarne uno per riempire lo spazio fa perdere fiducia a tutto il resto.
- Sull'esperienza sii esplicito: quanti anni chiede l'annuncio, quanti ne ha il
  candidato, e se la distanza e' un ostacolo o no.
- Se il candidato ha gia' scartato offerte per un motivo che ricorre anche qui,
  dillo fra i motivi di dubbio e tienine conto nel punteggio."""


class LlmVerdict(BaseModel):
    """Giudizio strutturato restituito dal modello.

    I campi aggiunti dopo il primo rilascio hanno tutti un valore predefinito:
    i giudizi gia' salvati nel database non li hanno, e l'interfaccia deve
    poterli leggere lo stesso.
    """

    score: int = Field(ge=0, le=100, description="Compatibilita' complessiva da 0 a 100")
    reasoning: str = Field(
        description="Due o tre frasi in italiano rivolte al candidato: perche' "
                    "questa offerta fa o non fa per lui")
    key_matches: list[str] = Field(
        default_factory=list,
        description="Cosa del suo profilo corrisponde a quanto chiede l'annuncio")
    key_gaps: list[str] = Field(
        default_factory=list,
        description="Requisiti chiesti dall'annuncio che il candidato non copre, "
                    "citati con le parole dell'annuncio")
    experience_note: str = Field(
        default="",
        description="Quanta esperienza chiede l'annuncio, quanta ne ha il candidato, "
                    "e se la distanza e' un ostacolo. Vuoto se l'annuncio non lo dice")
    concerns: list[str] = Field(
        default_factory=list,
        description="Motivi per cui, viste le offerte che ha gia' scartato, "
                    "potrebbe non volere questa")
    recommendation: str = Field(
        default="valuta",
        description="Una fra: candidati, valuta, lascia_perdere")
    seniority_fit: str = Field(
        default="adeguata",
        description="Una fra: sotto_qualificato, adeguata, sovra_qualificato",
    )


# --------------------------------------------------------------------------
# Anagrafica dei fornitori
# --------------------------------------------------------------------------

PROVIDERS: dict[str, dict[str, Any]] = {
    "gemini": {
        "label": "Google Gemini",
        # Predefinito prudente: i modelli piu' recenti sono anche i piu'
        # richiesti e rispondono 500 "high demand" nelle ore di punta, mentre
        # questo regge. La scelta si cambia dalle impostazioni, che elencano i
        # modelli realmente disponibili per la chiave (vedi `available_models`).
        "model": "gemini-3.5-flash",
        "secret": "gemini_api_key",
        "package": "google.genai",
        "install": "pip install google-genai",
        "env_var": "GEMINI_API_KEY",
        "signup": "aistudio.google.com/apikey",
        "note": "Chiave gratuita con un account Google, senza carta di credito.",
    },
    "claude": {
        "label": "Anthropic Claude",
        "model": "claude-opus-5",
        "secret": "anthropic_api_key",
        "package": "anthropic",
        "install": "pip install anthropic",
        "env_var": "ANTHROPIC_API_KEY",
        "signup": "platform.claude.com",
        "note": "Richiede un'organizzazione Console con fatturazione, "
                "separata dall'abbonamento Claude.",
    },
}

DEFAULT_PROVIDER = "gemini"


def provider_info(name: str) -> dict[str, Any]:
    return PROVIDERS.get(name, PROVIDERS[DEFAULT_PROVIDER])


def catalogue() -> list[dict[str, Any]]:
    """Elenco dei fornitori con il loro stato, per la pagina Impostazioni."""
    entries = []
    for name, info in PROVIDERS.items():
        available, reason = is_available(name)
        entries.append({
            "name": name,
            "label": info["label"],
            "model": info["model"],
            "env_var": info["env_var"],
            "install": info["install"],
            "signup": info["signup"],
            "note": info["note"],
            "available": available,
            "reason": reason,
        })
    return entries


def _has_package(dotted: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(dotted) is not None
    except (ImportError, ValueError):
        return False


def is_available(name: str) -> tuple[bool, str]:
    """Dice se un fornitore e' utilizzabile, e altrimenti perche' no."""
    info = PROVIDERS.get(name)
    if info is None:
        return False, f"fornitore sconosciuto: {name}"
    if not SECRETS.get(info["secret"]):
        return False, f"{info['env_var']} non impostata nel file .env"
    if not _has_package(info["package"]):
        return False, f"libreria mancante: installala con  {info['install']}"
    return True, "disponibile"


# --------------------------------------------------------------------------
# Composizione della richiesta
# --------------------------------------------------------------------------

def _cv_summary(cv: Any) -> str:
    return "\n".join([
        f"Titolo di studio: {cv.education_label or 'non rilevato'}"
        + (f" in {', '.join(cv.education_fields)}" if cv.education_fields else ""),
        f"Anni di esperienza stimati: {cv.years_experience}",
        f"Aree professionali: {', '.join(cv.roles) or 'non rilevate'}",
        f"Lingue: {', '.join(cv.languages) or 'non rilevate'}",
        f"Competenze riconosciute: {', '.join(cv.skills) or 'nessuna'}",
    ])


def build_prompt(job: Any, cv: Any, rejected: str = "", preferences: str = "") -> str:
    # Gli scarti passati sono l'informazione piu' densa che il candidato possa
    # dare: dicono cosa non vuole, che dal solo curriculum non si deduce.
    ricorrenze = f"""

## COSA SI E' CAPITO DALLE SUE SCELTE
{preferences[:MAX_FEEDBACK_CHARS]}

Questo e' il quadro d'insieme, non un caso singolo: e' la parte che si applica
anche a un'offerta mai vista. Guarda con piu' severita' i criteri indicati, e
se questa offerta ripete uno dei motivi ricorrenti scrivilo fra i motivi di
dubbio e tienine conto nel punteggio.""" if preferences else ""

    memoria = f"""

## OFFERTE CHE IL CANDIDATO HA GIA' SCARTATO, CON IL MOTIVO
{rejected[:MAX_FEEDBACK_CHARS]}

Leggi il motivo, non solo il titolo. Se il candidato ha scartato un'offerta
perche' chiedeva troppa esperienza, o per la sede, o per il contratto, quel
mestiere gli interessa: e' il resto che non andava, e un'offerta simile ma senza
quel problema va valutata bene. Abbassa il punteggio solo quando ritrovi qui il
motivo per cui aveva scartato, e scrivilo fra i motivi di dubbio.""" if rejected else ""

    return f"""Valuta la compatibilita' fra questo candidato e questa offerta,
e spiega al candidato perche' fa o non fa per lui.

## OFFERTA
Titolo: {job.title}
Azienda: {job.company}
Sede: {job.location}

{job.description[:MAX_JOB_CHARS]}

## CANDIDATO
{_cv_summary(cv)}

## TESTO DEL CURRICULUM
{cv.raw_text[:MAX_CV_CHARS]}{ricorrenze}{memoria}"""


# --------------------------------------------------------------------------
# Implementazioni per fornitore
# --------------------------------------------------------------------------

def _call_gemini(prompt: str, model: str, system: str, schema: type[BaseModel],
                 max_tokens: int) -> BaseModel:
    from google import genai

    client = genai.Client(api_key=SECRETS["gemini_api_key"])
    interaction = client.interactions.create(
        model=model,
        system_instruction=system,
        input=prompt,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": schema.model_json_schema(),
        },
        generation_config={"max_output_tokens": max_tokens, "thinking_level": "low"},
    )
    return schema.model_validate_json(interaction.output_text)


def _call_claude(prompt: str, model: str, system: str, schema: type[BaseModel],
                 max_tokens: int) -> BaseModel:
    import anthropic

    client = anthropic.Anthropic(
        api_key=SECRETS["anthropic_api_key"], max_retries=2, timeout=60.0
    )
    response = client.messages.parse(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_format=schema,
    )
    return response.parsed_output


_BACKENDS: dict[str, Callable[..., BaseModel]] = {
    "gemini": _call_gemini,
    "claude": _call_claude,
}


def _chiedi(provider: str, model: str, system: str, prompt: str,
            schema: type[BaseModel], max_tokens: int) -> BaseModel | None:
    """Una domanda al modello, con la stessa gestione degli errori ovunque.

    Restituisce None su qualunque problema: rete, quota, chiave non valida o
    risposta non conforme allo schema. Chi chiama prosegue senza.
    """
    available, reason = is_available(provider)
    if not available:
        log.debug("livello semantico non disponibile (%s): %s", provider, reason)
        return None
    backend = _BACKENDS.get(provider)
    if backend is None:
        return None
    try:
        return backend(prompt, model.strip() or provider_info(provider)["model"],
                       system, schema, max_tokens)
    except Exception as exc:
        log.warning("richiesta al modello fallita (%s): %s: %s",
                    provider, type(exc).__name__, str(exc)[:180])
        return None


# --------------------------------------------------------------------------
# Interfaccia pubblica
# --------------------------------------------------------------------------

# L'elenco dei modelli cambia di rado ma la sua richiesta esce su internet:
# tenerlo da parte per qualche minuto evita di far aspettare la pagina delle
# impostazioni a ogni visita. (valore, scadenza)
_CACHE_MODELLI: dict[str, tuple[list[str], float]] = {}
_DURATA_CACHE = 600.0


def available_models(provider: str) -> list[str]:
    """Modelli realmente utilizzabili con la chiave configurata.

    Serve alle impostazioni per proporre una scelta vera invece di un elenco
    scritto a mano, che invecchia in fretta e non tiene conto di cosa la
    singola chiave abbia effettivamente abilitato.
    """
    if provider != "gemini" or not is_available("gemini")[0]:
        return []

    import time

    in_memoria = _CACHE_MODELLI.get(provider)
    if in_memoria and in_memoria[1] > time.monotonic():
        return in_memoria[0]

    try:
        from google import genai

        client = genai.Client(api_key=SECRETS["gemini_api_key"])
        nomi = [str(getattr(m, "name", "")).removeprefix("models/") for m in client.models.list()]
    except Exception as exc:
        log.warning("elenco modelli non recuperabile: %s", str(exc)[:140])
        return []
    # Solo modelli testuali generalisti: immagini, voce e simili qui non servono.
    escludi = ("image", "tts", "embedding", "aqa", "omni", "banana", "veo", "imagen", "gemma")
    modelli = sorted(n for n in nomi if n and not any(e in n for e in escludi))
    _CACHE_MODELLI[provider] = (modelli, time.monotonic() + _DURATA_CACHE)
    return modelli


def evaluate(
    job: Any,
    cv: Any,
    provider: str = DEFAULT_PROVIDER,
    model: str = "",
    rejected: str = "",
    preferences: str = "",
) -> LlmVerdict | None:
    """Chiede al modello un giudizio sulla compatibilita'.

    `model` vuoto significa "quello predefinito del fornitore".

    Restituisce None su qualunque errore: il punteggio lessicale resta valido da
    solo, e un problema di rete o di quota non deve far fallire il ciclo di
    controllo.
    """
    verdetto = _chiedi(provider, model, SYSTEM,
                       build_prompt(job, cv, rejected, preferences), LlmVerdict, 2000)
    return verdetto if isinstance(verdetto, LlmVerdict) else None


# --------------------------------------------------------------------------
# Lettura del curriculum
# --------------------------------------------------------------------------
# Le euristiche leggono il curriculum con espressioni regolari e un dizionario
# scritto a mano: precise dove arrivano, cieche fuori. Il modello non ha quel
# limite, ma puo' inventare. Le due letture restano quindi separate e vengono
# confrontate: dove non vanno d'accordo, lo si dice invece di sceglierne una in
# silenzio.

MAX_CV_LETTURA_CHARS = 14000


class CvReading(BaseModel):
    """Il curriculum come lo legge il modello."""

    skills: list[str] = Field(
        default_factory=list,
        description="Competenze concrete, come etichette brevi in italiano "
                    "(strumenti, tecniche, mansioni). Niente frasi")
    languages: list[str] = Field(default_factory=list, description="Lingue conosciute")
    roles: list[str] = Field(
        default_factory=list, description="Mestieri svolti, come titoli brevi")
    education_level: str = Field(
        default="",
        description="Il titolo di studio piu' alto effettivamente conseguito dalla "
                    "persona, scelto fra le etichette elencate nella richiesta. "
                    "Stringa vuota se non e' scritto")
    education_fields: list[str] = Field(
        default_factory=list, description="Aree di studio, per esempio Chimica, Economia")
    years_experience: float = Field(
        default=0.0,
        description="Anni di sola esperienza lavorativa, studi esclusi. Somma le "
                    "durate dei singoli incarichi e non contare due volte i periodi "
                    "sovrapposti")
    experience_items: list[str] = Field(
        default_factory=list,
        description="Un rigo per incarico: ruolo, azienda, periodo e durata in mesi. "
                    "E' la prova da cui viene il totale")
    notes: str = Field(
        default="", description="Cosa non sei riuscito a leggere, in una frase. Vuoto se tutto chiaro")


SYSTEM_CV = """Leggi un curriculum e ne estrai i dati, senza aggiungere nulla.

Regole:
- Riporta solo cio' che e' scritto. Se un'informazione non c'e', lascia il campo
  vuoto: un dato inventato vale meno di un dato mancante.
- Gli anni di esperienza sono di solo lavoro. Tirocini e stage contano, gli anni
  di studio no. Somma la durata di ogni incarico, e se due periodi si
  sovrappongono contali una volta sola.
- Elenca gli incarichi da cui hai ricavato il totale, con la durata in mesi:
  serve a far controllare il conto.
- Il titolo di studio e' quello conseguito dalla persona. Un titolo citato per
  altri motivi - il gruppo di ricerca dove ha lavorato, un corso seguito da
  altri, il titolo richiesto da un annuncio incollato - non e' il suo.
- Le competenze sono cose concrete: strumenti, tecniche, mansioni, programmi.
  Etichette brevi, in italiano, senza frasi e senza aggettivi da sole.
- Rispondi sempre in italiano."""


def build_cv_prompt(text: str, education_labels: list[str]) -> str:
    return f"""Estrai i dati da questo curriculum.

Per il titolo di studio scegli una sola fra queste etichette, esattamente come
sono scritte, oppure lascia il campo vuoto se non risulta nessun titolo:
{", ".join(education_labels)}

## CURRICULUM
{text[:MAX_CV_LETTURA_CHARS]}"""


def read_cv(text: str, provider: str = DEFAULT_PROVIDER, model: str = "",
            education_labels: list[str] | None = None) -> CvReading | None:
    """Fa leggere il curriculum al modello. None se non e' utilizzabile."""
    if not (text or "").strip():
        return None
    lettura = _chiedi(provider, model, SYSTEM_CV,
                      build_cv_prompt(text, education_labels or []), CvReading, 3000)
    return lettura if isinstance(lettura, CvReading) else None


def blend(lexical_score: float, verdict: LlmVerdict | None, llm_weight: float) -> float:
    """Combina punteggio lessicale e giudizio del modello.

    `llm_weight` e' la quota percentuale assegnata al modello (0-100).
    """
    if verdict is None:
        return lexical_score
    weight = max(0.0, min(100.0, llm_weight)) / 100.0
    return lexical_score * (1 - weight) + verdict.score * weight
