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

# Codice ISO a due lettere -> nomi del paese, in italiano e in inglese.
NOMI: dict[str, tuple[str, ...]] = {
    "it": ("italia", "italy"), "fr": ("francia", "france"),
    "de": ("germania", "germany"), "es": ("spagna", "spain"),
    "pt": ("portogallo", "portugal"), "ch": ("svizzera", "switzerland"),
    "at": ("austria",), "be": ("belgio", "belgium"),
    "nl": ("paesi bassi", "netherlands", "olanda"), "ie": ("irlanda", "ireland"),
    "gb": ("regno unito", "united kingdom", "uk"), "us": ("stati uniti", "united states"),
    "dk": ("danimarca", "denmark"), "se": ("svezia", "sweden"),
    "no": ("norvegia", "norway"), "fi": ("finlandia", "finland"),
    "pl": ("polonia", "poland"), "gr": ("grecia", "greece"),
    "cz": ("repubblica ceca", "czech republic", "czechia"),
    "hu": ("ungheria", "hungary"), "ro": ("romania",),
}

# Nome -> codice, costruita una volta sola all'importazione.
_DA_NOME = {nome: iso for iso, nomi in NOMI.items() for nome in nomi}


def codice(nome: str) -> str:
    """Il codice di un paese scritto per esteso, o "" se non lo riconosciamo."""
    return _DA_NOME.get((nome or "").strip().lower(), "")


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
    return codice(re.sub(r"\s*\(.*\)\s*$", "", pezzi[-1]))
