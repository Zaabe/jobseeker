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
Valuti quanto un curriculum sia adatto a un'offerta di lavoro.

Criteri:
- Conta la sostanza delle competenze, non le parole esatte: tecniche equivalenti
  o trasferibili valgono quanto una corrispondenza letterale.
- Considera se il candidato potrebbe realisticamente superare una prima
  selezione per quella posizione.
- Un profilo molto piu' qualificato del richiesto non e' un match perfetto:
  segnala il disallineamento di seniority.
- Sii severo: 90 o piu' significa candidato ideale, 70 candidato solido,
  50 candidatura sensata ma incerta, sotto 30 fuori bersaglio.
- Rispondi sempre in italiano."""


class LlmVerdict(BaseModel):
    """Giudizio strutturato restituito dal modello."""

    score: int = Field(ge=0, le=100, description="Compatibilita' complessiva da 0 a 100")
    reasoning: str = Field(description="Due frasi che spiegano il punteggio, in italiano")
    key_matches: list[str] = Field(default_factory=list, description="Punti di forza rilevanti")
    key_gaps: list[str] = Field(default_factory=list, description="Requisiti non coperti")
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


def build_prompt(job: Any, cv: Any, rejected: str = "") -> str:
    # Gli scarti passati sono l'informazione piu' densa che il candidato possa
    # dare: dicono cosa non vuole, che dal solo curriculum non si deduce.
    memoria = f"""

## OFFERTE CHE IL CANDIDATO HA GIA' SCARTATO, CON IL MOTIVO
{rejected[:MAX_FEEDBACK_CHARS]}

Leggi il motivo, non solo il titolo. Se il candidato ha scartato un'offerta
perche' chiedeva troppa esperienza, o per la sede, o per il contratto, quel
mestiere gli interessa: e' il resto che non andava, e un'offerta simile ma senza
quel problema va valutata bene. Abbassa il punteggio solo quando ritrovi qui il
motivo per cui aveva scartato, e scrivilo fra i requisiti non coperti.""" if rejected else ""

    return f"""Valuta la compatibilita' fra questo candidato e questa offerta.

## OFFERTA
Titolo: {job.title}
Azienda: {job.company}
Sede: {job.location}

{job.description[:MAX_JOB_CHARS]}

## CANDIDATO
{_cv_summary(cv)}

## TESTO DEL CURRICULUM
{cv.raw_text[:MAX_CV_CHARS]}{memoria}"""


# --------------------------------------------------------------------------
# Implementazioni per fornitore
# --------------------------------------------------------------------------

def _call_gemini(prompt: str, model: str) -> LlmVerdict:
    from google import genai

    client = genai.Client(api_key=SECRETS["gemini_api_key"])
    interaction = client.interactions.create(
        model=model,
        system_instruction=SYSTEM,
        input=prompt,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": LlmVerdict.model_json_schema(),
        },
        generation_config={"max_output_tokens": 2000, "thinking_level": "low"},
    )
    return LlmVerdict.model_validate_json(interaction.output_text)


def _call_claude(prompt: str, model: str) -> LlmVerdict:
    import anthropic

    client = anthropic.Anthropic(
        api_key=SECRETS["anthropic_api_key"], max_retries=2, timeout=60.0
    )
    response = client.messages.parse(
        model=model,
        max_tokens=2000,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        output_format=LlmVerdict,
    )
    return response.parsed_output


_BACKENDS: dict[str, Callable[[str, str], LlmVerdict]] = {
    "gemini": _call_gemini,
    "claude": _call_claude,
}


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
) -> LlmVerdict | None:
    """Chiede al modello un giudizio sulla compatibilita'.

    `model` vuoto significa "quello predefinito del fornitore".

    Restituisce None su qualunque errore: il punteggio lessicale resta valido da
    solo, e un problema di rete o di quota non deve far fallire il ciclo di
    controllo.
    """
    available, reason = is_available(provider)
    if not available:
        log.debug("livello semantico non disponibile (%s): %s", provider, reason)
        return None

    backend = _BACKENDS.get(provider)
    if backend is None:
        return None

    try:
        return backend(build_prompt(job, cv, rejected), model.strip() or provider_info(provider)["model"])
    except Exception as exc:
        # Comprende errori di rete, quota esaurita, chiave non valida e risposte
        # non conformi allo schema: in tutti questi casi si prosegue con il solo
        # punteggio lessicale.
        log.warning(
            "valutazione semantica fallita (%s): %s: %s",
            provider, type(exc).__name__, str(exc)[:180],
        )
        return None


def blend(lexical_score: float, verdict: LlmVerdict | None, llm_weight: float) -> float:
    """Combina punteggio lessicale e giudizio del modello.

    `llm_weight` e' la quota percentuale assegnata al modello (0-100).
    """
    if verdict is None:
        return lexical_score
    weight = max(0.0, min(100.0, llm_weight)) / 100.0
    return lexical_score * (1 - weight) + verdict.score * weight
