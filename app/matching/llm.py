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
    "openai": {
        "label": "OpenAI o modello locale",
        # Un nome plausibile per Ollama, non una scelta: quali modelli esistano
        # lo decide il servizio all'altro capo, e la pagina delle impostazioni
        # elenca quelli che ci sono davvero (vedi `available_models`).
        "model": "llama3.1:8b",
        "secret": "openai_api_key",
        # Nessuna libreria da installare: si parla direttamente con l'API
        # compatibile OpenAI, che e' una POST con del JSON, usando `httpx` che
        # c'e' sempre. Per chi vuole far girare un modello sul proprio computer
        # un "pip install" in piu' sarebbe l'ostacolo di troppo.
        "package": "",
        "install": "",
        "base_url_secret": "openai_base_url",
        "env_var": "OPENAI_API_KEY",
        "signup": "ollama.com oppure lmstudio.ai",
        "note": "Qualunque servizio con API compatibile OpenAI. Sul proprio "
                "computer con Ollama o LM Studio non serve nessuna chiave, non "
                "costa niente e il curriculum non esce dalla macchina; con "
                "l'indirizzo di OpenAI (o di un servizio simile) serve la sua "
                "chiave. Indirizzo e chiave si impostano fra le credenziali.",
    },
}

DEFAULT_PROVIDER = "gemini"


def provider_info(name: str) -> dict[str, Any]:
    return PROVIDERS.get(name, PROVIDERS[DEFAULT_PROVIDER])


def base_url(provider: str = "openai") -> str:
    """L'indirizzo del servizio, per i fornitori che ne hanno uno configurabile.

    Stringa vuota per gli altri: Gemini e Claude parlano con il proprio
    servizio e non c'e' niente da scegliere.
    """
    chiave = (PROVIDERS.get(provider) or {}).get("base_url_secret")
    if not chiave:
        return ""
    return (SECRETS.get(chiave, "") or "").strip().rstrip("/")


# Indirizzi che stanno sulla macchina di chi usa l'applicazione, o sulla sua
# rete: la' un modello gira senza chiave e senza costi.
_HOST_IN_CASA = ("localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]",
                 "host.docker.internal")


def _vuole_chiave(url: str) -> bool:
    """Se quell'indirizzo e' un servizio remoto, e quindi la chiave ci vuole.

    Serve a non chiedere una chiave a chi ha un modello sul proprio computer -
    Ollama e LM Studio accettano qualunque cosa, o niente - e a dirlo subito a
    chi invece punta a un servizio a pagamento e la chiave l'ha dimenticata.
    """
    from urllib.parse import urlparse

    host = (urlparse(url).hostname or "").lower()
    if not host or host in _HOST_IN_CASA or host.endswith(".local"):
        return False
    # Reti private: un modello sul server di casa o in un altro contenitore.
    if host.startswith(("192.168.", "10.")) or host.startswith("172."):
        return False
    return True


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
            # Vuoto per i fornitori che non hanno un indirizzo da scegliere:
            # l'interfaccia lo mostra solo a chi ce l'ha.
            "base_url": base_url(name),
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
    if info.get("base_url_secret"):
        # Qui il requisito e' l'indirizzo, non la chiave: un modello che gira
        # in locale non ne vuole nessuna, e pretenderla avrebbe reso
        # inutilizzabile proprio il caso piu' semplice.
        indirizzo = base_url(name)
        if not indirizzo:
            return False, ("indirizzo del servizio non impostato: scrivilo in "
                           "Impostazioni, sotto «Credenziali dei servizi». Per Ollama "
                           "e' http://localhost:11434/v1, per LM Studio "
                           "http://localhost:1234/v1")
        if _vuole_chiave(indirizzo) and not SECRETS.get(info["secret"]):
            return False, (f"{info['env_var']} non impostata: {indirizzo} e' un "
                           "servizio remoto e la chiede. Un modello sul tuo computer no.")
        return True, "disponibile"
    if not SECRETS.get(info["secret"]):
        return False, (f"{info['env_var']} non impostata: scrivi la chiave in "
                       "Impostazioni, sotto «Credenziali dei servizi», oppure nel file .env")
    if info["package"] and not _has_package(info["package"]):
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


# Quanto aspettare una risposta da un servizio compatibile OpenAI. E' generoso
# di proposito: un modello da otto miliardi di parametri sul portatile di chi lo
# usa puo' metterci un minuto a scrivere un giudizio, e col timeout dei servizi
# remoti si sarebbe visto solo un errore di rete al posto di una risposta che
# stava arrivando.
TIMEOUT_COMPATIBILE = 180.0


def _json_dal_testo(testo: str) -> str:
    """Il primo oggetto JSON dentro una risposta, ignorando cio' che lo circonda.

    I modelli locali non rispondono sempre col solo JSON: lo racchiudono in un
    blocco markdown, o lo fanno precedere dal proprio ragionamento (i modelli
    che "pensano" scrivono un blocco <think> prima della risposta). Si cerca
    quindi la prima graffa e si prosegue contando le graffe, tenendo fuori dal
    conto quelle dentro le stringhe, perche' una descrizione puo' contenerne.
    """
    inizio = testo.find("{")
    if inizio < 0:
        return testo
    profondita = 0
    in_stringa = False
    fuga = False
    for i in range(inizio, len(testo)):
        c = testo[i]
        if fuga:
            fuga = False
        elif c == "\\":
            fuga = True
        elif c == '"':
            in_stringa = not in_stringa
        elif not in_stringa:
            if c == "{":
                profondita += 1
            elif c == "}":
                profondita -= 1
                if profondita == 0:
                    return testo[inizio:i + 1]
    # Risposta troncata a metà: si restituisce quel che c'e' e sara' lo schema
    # a bocciarla, con un messaggio piu' utile di "graffa mancante".
    return testo[inizio:]


def _call_openai(prompt: str, model: str, system: str, schema: type[BaseModel],
                 max_tokens: int) -> BaseModel:
    """Interroga un servizio con API compatibile OpenAI.

    Vale per Ollama e LM Studio sul proprio computer, per OpenAI stessa e per i
    servizi che ne imitano l'API. Non usa la libreria `openai`: la richiesta e'
    una POST con del JSON, e `httpx` c'e' gia'.

    La parte delicata e' ottenere una risposta strutturata, perche' i servizi
    compatibili non sostengono tutti le stesse cose. Si prova dal modo piu'
    stretto al piu' tollerante - schema vincolante, poi "rispondi in JSON", poi
    solo la richiesta scritta nel testo - e si passa al successivo quando il
    server rifiuta. Il modo che ha funzionato non si ricorda: costa una
    richiesta in piu' una volta sola, e ricordarlo vorrebbe dire sbagliare
    quando l'utente cambia servizio.
    """
    import json

    base = base_url("openai")
    if not base:
        raise RuntimeError("indirizzo del servizio non impostato")

    intestazioni = {"Content-Type": "application/json"}
    chiave = SECRETS.get("openai_api_key", "")
    if chiave:
        intestazioni["Authorization"] = f"Bearer {chiave}"

    schema_json = schema.model_json_schema()
    promemoria = (
        "\n\nRispondi soltanto con un oggetto JSON conforme a questo schema, "
        "senza testo prima o dopo e senza blocchi markdown:\n"
        + json.dumps(schema_json, ensure_ascii=False)
    )
    forme = [
        {"type": "json_schema", "json_schema": {"name": "risposta", "schema": schema_json}},
        {"type": "json_object"},
        None,
    ]

    ultimo_errore = ""
    tetto = "max_tokens"
    for forma in forme:
        # Lo schema si scrive anche nel testo quando non lo vincola il server:
        # e' l'unica indicazione che il modello ha su cosa scrivere.
        vincolato = bool(forma) and forma["type"] == "json_schema"
        corpo: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system if vincolato else system + promemoria},
                {"role": "user", "content": prompt},
            ],
            # Un giudizio deve essere ripetibile: la stessa offerta e lo stesso
            # curriculum non possono dare due punteggi diversi.
            "temperature": 0,
            tetto: max_tokens,
        }
        if forma:
            corpo["response_format"] = forma

        risposta = _posta_compatibile(base, intestazioni, corpo)
        if risposta.status_code == 400:
            dettaglio = risposta.text[:400]
            # I modelli recenti di OpenAI rifiutano `max_tokens` e vogliono
            # `max_completion_tokens`. E' un rifiuto che si riconosce dal
            # messaggio, e si corregge una volta per tutte.
            if tetto == "max_tokens" and "max_completion_tokens" in dettaglio:
                tetto = "max_completion_tokens"
                corpo.pop("max_tokens", None)
                corpo[tetto] = max_tokens
                risposta = _posta_compatibile(base, intestazioni, corpo)
            if risposta.status_code == 400:
                # Il server non conosce questa forma di risposta strutturata:
                # si scende di un gradino.
                ultimo_errore = f"HTTP 400: {dettaglio}"
                continue
        if risposta.status_code == 404:
            raise RuntimeError(
                f"{base} risponde 404: l'indirizzo deve finire con /v1 e il "
                f"modello «{model}» deve esistere sul servizio")
        if risposta.status_code in (401, 403):
            raise RuntimeError(
                f"HTTP {risposta.status_code}: il servizio ha rifiutato la chiave")
        if risposta.status_code >= 400:
            raise RuntimeError(f"HTTP {risposta.status_code}: {risposta.text[:220]}")

        try:
            dati = risposta.json()
            testo = dati["choices"][0]["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            ultimo_errore = f"risposta illeggibile ({type(exc).__name__})"
            continue
        try:
            return schema.model_validate_json(_json_dal_testo(testo))
        except Exception as exc:
            # Con lo schema vincolante una risposta non conforme non e' colpa
            # del modello ma del server che non lo vincola davvero: vale la
            # pena riprovare col modo successivo.
            ultimo_errore = f"{type(exc).__name__}: {str(exc)[:160]}"
            continue

    raise RuntimeError(ultimo_errore or "nessuna risposta utilizzabile dal servizio")


def _posta_compatibile(base: str, intestazioni: dict[str, str],
                       corpo: dict[str, Any]) -> Any:
    """Una POST a /chat/completions, con l'errore di rete tradotto."""
    import httpx

    try:
        with httpx.Client(timeout=TIMEOUT_COMPATIBILE) as http:
            return http.post(f"{base}/chat/completions", json=corpo, headers=intestazioni)
    except httpx.HTTPError as exc:
        # Corto di proposito: `prova` mostra i primi 220 caratteri dell'errore,
        # e un suggerimento che cade fuori da quel taglio non serve a nessuno.
        raise RuntimeError(
            f"non raggiungibile su {base}: {exc}. In un contenitore «localhost» e' "
            "il contenitore stesso: prova host.docker.internal") from exc


_BACKENDS: dict[str, Callable[..., BaseModel]] = {
    "gemini": _call_gemini,
    "claude": _call_claude,
    "openai": _call_openai,
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
    import time

    lettore = _ELENCHI.get(provider)
    if lettore is None or not is_available(provider)[0]:
        return []

    # L'indirizzo entra nella chiave: chi passa da Ollama a LM Studio cambia
    # l'elenco dei modelli, e senza questo si vedrebbero ancora i precedenti.
    chiave_cache = f"{provider}|{base_url(provider)}"
    in_memoria = _CACHE_MODELLI.get(chiave_cache)
    if in_memoria and in_memoria[1] > time.monotonic():
        return in_memoria[0]

    try:
        nomi = lettore()
    except Exception as exc:
        log.warning("elenco modelli non recuperabile (%s): %s", provider, str(exc)[:140])
        return []
    # Solo modelli testuali generalisti: immagini, voce e simili qui non servono.
    escludi = ("image", "tts", "embed", "aqa", "omni", "banana", "veo", "imagen",
               "gemma", "whisper", "dall-e", "moderation", "audio", "realtime",
               "rerank", "clip", "guard")
    modelli = sorted(n for n in nomi if n and not any(e in n for e in escludi))
    _CACHE_MODELLI[chiave_cache] = (modelli, time.monotonic() + _DURATA_CACHE)
    return modelli


def _modelli_gemini() -> list[str]:
    from google import genai

    client = genai.Client(api_key=SECRETS["gemini_api_key"])
    return [str(getattr(m, "name", "")).removeprefix("models/") for m in client.models.list()]


def _modelli_openai() -> list[str]:
    """I modelli che il servizio compatibile dichiara di avere.

    Con Ollama e LM Studio sono quelli davvero scaricati sul computer, ed e' la
    ragione per cui vale la pena chiederli: il nome di un modello locale non lo
    si indovina («llama3.1:8b», con i due punti e la dimensione) e sbagliarlo
    da' un 404 che non spiega niente.
    """
    import httpx

    intestazioni = {}
    chiave = SECRETS.get("openai_api_key", "")
    if chiave:
        intestazioni["Authorization"] = f"Bearer {chiave}"
    with httpx.Client(timeout=15.0) as http:
        risposta = http.get(f"{base_url('openai')}/models", headers=intestazioni)
    risposta.raise_for_status()
    return [str(v.get("id", "")) for v in (risposta.json().get("data") or [])]


# Chi sa elencare i propri modelli. Claude non c'e': la sua libreria lo
# permetterebbe, ma i nomi sono pochi, stabili e documentati, e una richiesta
# in piu' a ogni apertura delle impostazioni non ripaga.
_ELENCHI: dict[str, Callable[[], list[str]]] = {
    "gemini": _modelli_gemini,
    "openai": _modelli_openai,
}


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


class ParoleSimili(BaseModel):
    """Le altre forme con cui si scrive la stessa cosa negli annunci."""

    variants: list[str] = Field(default_factory=list, max_length=12)


SYSTEM_PAROLE = """Conosci il linguaggio degli annunci di lavoro, in italiano e in inglese.
Ti viene data una parola o un'espressione. Elenchi le altre forme con cui la
stessa cosa compare negli annunci: sinonimi, sigle e abbreviazioni, la forma
inglese di quella italiana e viceversa, le grafie alternative.

Regole:
- solo forme che un annuncio userebbe davvero al posto di quella data;
- niente forme piu' generiche o piu' specifiche: "sviluppatore" non e' una
  variante di "sviluppatore backend", e "python" non e' una variante di
  "programmatore";
- tutto in minuscolo, senza ripetere la parola di partenza;
- al massimo otto voci, meglio poche e giuste che molte."""


def parole_simili(parola: str, provider: str = DEFAULT_PROVIDER,
                  model: str = "") -> list[str] | None:
    """Le varianti di una parola secondo il modello. None se non e' utilizzabile.

    Le varianti meccaniche - trattino, plurale, accenti - le trova gia'
    l'interfaccia da sola: qui interessano quelle che richiedono di sapere cosa
    vuol dire la parola.
    """
    parola = (parola or "").strip()
    if not parola:
        return []
    risposta = _chiedi(provider, model, SYSTEM_PAROLE,
                       f"Parola: {parola}", ParoleSimili, 500)
    if not isinstance(risposta, ParoleSimili):
        return None
    pulite: list[str] = []
    for voce in risposta.variants:
        v = " ".join(str(voce).split()).lower()
        if v and v != parola.lower() and v not in pulite and len(v) <= 60:
            pulite.append(v)
    return pulite[:8]


# Un annuncio minimo e un profilo minimo: alla prova non interessa il giudizio,
# interessa sapere se la chiave, la libreria e il modello stanno insieme.
class _FintaOfferta:
    title = "Tecnico di laboratorio"
    company = "Prova"
    location = "Milano"
    description = "Analisi di controllo qualita' in laboratorio."


class _FintoProfilo:
    education_label = "Laurea triennale"
    education_fields = ["Chimica"]
    years_experience = 2
    roles = ["tecnico di laboratorio"]
    languages = ["Italiano"]
    skills = ["HPLC"]
    raw_text = "Tecnico di laboratorio con esperienza in analisi chimiche."


def prova(provider: str = DEFAULT_PROVIDER, model: str = "") -> tuple[bool, str]:
    """Interroga davvero il modello e riporta l'errore esatto se non risponde.

    `evaluate` inghiotte gli errori di proposito, perche' un problema di rete
    non deve far fallire il ciclo di controllo. Qui e' l'opposto: il motivo del
    fallimento e' l'unica cosa che si vuole sapere, ed e' quello che distingue
    "chiave sbagliata" da "libreria mancante" da "modello inesistente".
    """
    disponibile, motivo = is_available(provider)
    if not disponibile:
        return False, motivo

    backend = _BACKENDS.get(provider)
    if backend is None:
        return False, f"fornitore sconosciuto: {provider}"

    nome_modello = model.strip() or provider_info(provider)["model"]
    try:
        verdetto = backend(build_prompt(_FintaOfferta(), _FintoProfilo()),
                           nome_modello, SYSTEM, LlmVerdict, 600)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {str(exc)[:220]}"
    if not isinstance(verdetto, LlmVerdict):
        return False, "risposta non conforme allo schema"
    return True, f"{provider_info(provider)['label']} ha risposto con {nome_modello}"


def mescola(lexical_score: float, llm_score: float | None, llm_weight: float) -> float:
    """Combina un punteggio lessicale e uno del modello, dati i due numeri.

    Sta separata da `blend` perche' la usa anche il ricalcolo dei punteggi, che
    ha in mano un giudizio gia' salvato - un dizionario letto dal database - e
    non l'oggetto restituito dal modello.
    """
    if llm_score is None:
        return lexical_score
    weight = max(0.0, min(100.0, llm_weight)) / 100.0
    return lexical_score * (1 - weight) + float(llm_score) * weight


def blend(lexical_score: float, verdict: LlmVerdict | None, llm_weight: float) -> float:
    """Combina punteggio lessicale e giudizio del modello.

    `llm_weight` e' la quota percentuale assegnata al modello (0-100).
    """
    if verdict is None:
        return lexical_score
    return mescola(lexical_score, verdict.score, llm_weight)
