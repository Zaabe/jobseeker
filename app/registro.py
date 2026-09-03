"""Le ultime righe di log, tenute in memoria per la sezione «Log».

Il contenitore scrive su stdout, e da dentro l'applicazione quello che e' gia'
uscito non si puo' rileggere: l'unico modo di mostrarlo nell'interfaccia e'
tenerne una copia mentre passa. Un anello di poche migliaia di righe, senza
file e senza database: se il processo riparte si ricomincia da capo, che e'
esattamente quello che succede anche a `docker logs` con un contenitore
ricreato.

Ogni riga ha un numero progressivo. E' quello che permette a chi guarda di
chiedere "dammi cosa e' successo dopo la riga 812" invece di riscaricare tutto
ogni due secondi.
"""
from __future__ import annotations

import itertools
import logging
import re
import threading
from collections import deque
from typing import Any

# Quante righe tenere. Duemila righe di log stanno in poco piu' di mezzo mega:
# abbastanza da coprire diversi cicli di controllo, poco abbastanza da non
# pesare in un contenitore piccolo.
MAX_RIGHE = 2000

LIVELLI = {"": 0, "debug": logging.DEBUG, "info": logging.INFO,
           "warning": logging.WARNING, "error": logging.ERROR}

# Chiavi e valori che non devono comparire nell'interfaccia. I log ci finiscono
# dentro senza volerlo - una richiesta ad Adzuna porta la chiave nell'indirizzo -
# e una schermata dei log e' una cosa che si manda a qualcuno per farsi aiutare.
_SEGRETI = re.compile(
    r"((?:app_key|api_key|apikey|key|token|secret|password|passwd|pwd|bot)"
    r"\s*[=:]\s*)([^\s&\"'}]{4,})",
    re.IGNORECASE,
)


def nascondi_segreti(testo: str) -> str:
    """Sostituisce il valore di chiavi e token con dei puntini."""
    return _SEGRETI.sub(lambda m: f"{m.group(1)}***", testo)


class RegistroInMemoria(logging.Handler):
    """Un gestore di logging che tiene le ultime righe in un anello."""

    def __init__(self, capienza: int = MAX_RIGHE) -> None:
        super().__init__()
        self._righe: deque[dict[str, Any]] = deque(maxlen=capienza)
        self._numero = itertools.count(1)
        # `deque` con maxlen e' atomico sulle singole operazioni, ma qui si
        # leggono liste intere mentre altri thread scrivono: lo scheduler e le
        # richieste web girano su thread diversi.
        self._lucchetto = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            testo = self.format(record)
        except Exception:  # un log rotto non deve fermare chi lo ha scritto
            return
        riga = {
            "n": next(self._numero),
            "livello": record.levelname,
            "peso": record.levelno,
            "nome": record.name,
            "testo": testo,
        }
        with self._lucchetto:
            self._righe.append(riga)

    def dopo(self, numero: int = 0, limite: int = 300, livello: str = "") -> dict[str, Any]:
        """Le righe successive a `numero`, al massimo `limite`.

        Con `numero` a zero restituisce le *ultime* righe, non le prime: chi
        apre la pagina vuole vedere cosa sta succedendo adesso, non l'inizio
        della memoria.
        """
        peso_minimo = LIVELLI.get((livello or "").lower(), 0)
        with self._lucchetto:
            tutte = list(self._righe)
        scelte = [r for r in tutte if r["peso"] >= peso_minimo]
        perse = 0
        if numero <= 0:
            fetta = scelte[-limite:]
        else:
            # Quante ne sono uscite dall'anello prima che qualcuno le
            # chiedesse: quelle non tornano piu', e si dice invece di far
            # credere che non sia successo niente. Le righe che restano fuori
            # solo per il tetto di questa risposta non sono perse - arrivano
            # alla richiesta dopo, perche' il cursore avanza di quello che e'
            # stato consegnato davvero.
            if tutte and tutte[0]["n"] > numero + 1:
                perse = tutte[0]["n"] - numero - 1
            fetta = [r for r in scelte if r["n"] > numero][:limite]
        ultimo = fetta[-1]["n"] if fetta else (numero if numero > 0 else
                                              (tutte[-1]["n"] if tutte else 0))
        return {
            "lines": [{"n": r["n"], "level": r["livello"], "logger": r["nome"],
                       "text": nascondi_segreti(r["testo"])}
                      for r in fetta],
            "last": ultimo,
            "dropped": perse,
            "buffered": len(tutte),
        }


# L'unico registro dell'applicazione. Viene agganciato al logger radice
# all'avvio, cosi' raccoglie anche quello che scrivono le librerie (httpx,
# apscheduler, uvicorn), che e' meta' di quello che si vuole vedere.
registro = RegistroInMemoria()


def collega(formato: str, data: str) -> None:
    """Aggancia il registro al logger radice, con lo stesso formato di stdout."""
    registro.setFormatter(logging.Formatter(formato, datefmt=data))
    radice = logging.getLogger()
    if registro not in radice.handlers:
        radice.addHandler(registro)
