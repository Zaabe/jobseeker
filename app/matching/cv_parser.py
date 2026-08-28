"""Estrazione del testo dal curriculum e costruzione del profilo.

Formati supportati: PDF, DOCX, TXT e Markdown. Da questi si ricavano le
competenze, il titolo di studio, le lingue, i ruoli ricoperti e una stima degli
anni di esperienza, che sono gli ingredienti del punteggio di compatibilita'.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Any

from .skills import (
    extract_education_fields,
    extract_education_level,
    extract_languages,
    extract_roles,
    extract_required_years,
    extract_skills,
)
from .text import normalize, normalize_lines


class CVParseError(RuntimeError):
    """Il file non e' leggibile o non contiene testo estraibile."""


# --------------------------------------------------------------------------
# Estrazione del testo
# --------------------------------------------------------------------------

def extract_text(data: bytes, filename: str) -> str:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix == "pdf":
        return _extract_pdf(data)
    if suffix in ("docx", "dotx"):
        return _extract_docx(data)
    if suffix in ("txt", "md", "text", "rtf"):
        return _decode(data)
    if suffix == "doc":
        raise CVParseError(
            "il formato .doc (Word 97-2003) non e' leggibile: converti il file in .docx o in PDF"
        )
    # Ultimo tentativo: se sembra testo, lo si usa comunque.
    text = _decode(data)
    if text.strip():
        return text
    raise CVParseError(f"formato non supportato: .{suffix or 'sconosciuto'}")


def _decode(data: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise CVParseError("libreria pypdf non disponibile") from exc
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise CVParseError(f"PDF illeggibile: {exc}") from exc
    text = "\n".join(pages).strip()
    if not text:
        raise CVParseError(
            "il PDF non contiene testo selezionabile: probabilmente e' una scansione. "
            "Esporta il curriculum in PDF dal documento originale, oppure caricalo in .docx"
        )
    return text


def _extract_docx(data: bytes) -> str:
    try:
        import docx
    except ImportError as exc:  # pragma: no cover
        raise CVParseError("libreria python-docx non disponibile") from exc
    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise CVParseError(f"DOCX illeggibile: {exc}") from exc
    parts = [p.text for p in document.paragraphs]
    # Molti curriculum impaginano le esperienze dentro tabelle.
    for table in document.tables:
        for row in table.rows:
            parts.extend(cell.text for cell in row.cells)
    text = "\n".join(p for p in parts if p and p.strip()).strip()
    if not text:
        raise CVParseError("il documento Word non contiene testo")
    return text


# --------------------------------------------------------------------------
# Stima degli anni di esperienza
# --------------------------------------------------------------------------

_MONTHS = {
    "gennaio": 1, "gen": 1, "january": 1, "jan": 1,
    "febbraio": 2, "feb": 2, "february": 2,
    "marzo": 3, "mar": 3, "march": 3,
    "aprile": 4, "apr": 4, "april": 4,
    "maggio": 5, "mag": 5, "may": 5,
    "giugno": 6, "giu": 6, "june": 6, "jun": 6,
    "luglio": 7, "lug": 7, "july": 7, "jul": 7,
    "agosto": 8, "ago": 8, "august": 8, "aug": 8,
    "settembre": 9, "set": 9, "sett": 9, "september": 9, "sep": 9, "sept": 9,
    "ottobre": 10, "ott": 10, "october": 10, "oct": 10,
    "novembre": 11, "nov": 11, "november": 11,
    "dicembre": 12, "dic": 12, "december": 12, "dec": 12,
}
_PRESENT = ("oggi", "attuale", "attualmente", "presente", "present", "current", "in corso", "ad oggi")
_MONTH_ALT = "|".join(sorted(_MONTHS, key=len, reverse=True))
_SEP = r"\s*(?:-|--|to|a|al|until|fino a|–|—)\s*"

_RANGE_RE = re.compile(
    rf"(?:(?P<m1>{_MONTH_ALT})\s+)?(?P<y1>(?:19|20)\d{{2}})"
    rf"{_SEP}"
    rf"(?:(?:(?P<m2>{_MONTH_ALT})\s+)?(?P<y2>(?:19|20)\d{{2}})|(?P<now>{'|'.join(_PRESENT)}))",
    re.IGNORECASE,
)
_NUMERIC_RANGE_RE = re.compile(
    rf"(?P<m1>\d{{1,2}})[/.](?P<y1>(?:19|20)\d{{2}})"
    rf"{_SEP}"
    rf"(?:(?P<m2>\d{{1,2}})[/.](?P<y2>(?:19|20)\d{{2}})|(?P<now>{'|'.join(_PRESENT)}))",
    re.IGNORECASE,
)

_CURRENT_YEAR = 2026


def _merge_intervals(intervals: list[tuple[int, int]]) -> int:
    """Somma la durata in mesi di intervalli che possono sovrapporsi."""
    if not intervals:
        return 0
    intervals.sort()
    total = 0
    start, end = intervals[0]
    for next_start, next_end in intervals[1:]:
        if next_start <= end:
            end = max(end, next_end)
        else:
            total += end - start
            start, end = next_start, next_end
    total += end - start
    return total


# Intestazioni con cui i curriculum separano le sezioni. Servono a contare gli
# anni di esperienza solo dove sono davvero, senza sommare gli anni di studio.
_SECTION_HEADERS: list[tuple[str, list[str]]] = [
    ("esperienza", [
        "esperienza professionale", "esperienze professionali", "esperienza lavorativa",
        "esperienze lavorative", "esperienza", "work experience", "professional experience",
        "employment history", "employment", "career history", "carriera", "attivita lavorativa",
        "percorso professionale", "experience",
    ]),
    ("formazione", [
        "formazione", "istruzione e formazione", "istruzione", "education",
        "titoli di studio", "percorso formativo", "formazione accademica",
        "academic background", "qualifications", "studi",
    ]),
    ("altro", [
        "competenze", "skills", "capacita e competenze", "lingue", "languages",
        "pubblicazioni", "publications", "certificazioni", "certifications",
        "corsi", "interessi", "hobby", "referenze", "references", "progetti", "projects",
    ]),
]

_HEADER_RE = re.compile(
    r"^[\s\W]{0,4}(" + "|".join(
        re.escape(h) for _, hs in _SECTION_HEADERS for h in sorted(hs, key=len, reverse=True)
    ) + r")[\s\W]{0,4}$",
    re.IGNORECASE | re.MULTILINE,
)

_HEADER_KIND = {h: kind for kind, hs in _SECTION_HEADERS for h in hs}


def split_sections(text: str) -> list[tuple[str, str]]:
    """Divide il curriculum in sezioni (tipo, contenuto) usando le intestazioni.

    Se non riconosce nessuna intestazione restituisce il testo come sezione
    unica di tipo sconosciuto, e chi chiama decide come comportarsi.
    """
    normalized = normalize_lines(text)
    matches = list(_HEADER_RE.finditer(normalized))
    if not matches:
        return [("sconosciuto", normalized)]
    sections: list[tuple[str, str]] = []
    if matches[0].start() > 0:
        sections.append(("intestazione", normalized[: matches[0].start()]))
    for i, match in enumerate(matches):
        kind = _HEADER_KIND.get(match.group(1).lower().strip(), "altro")
        end = matches[i + 1].start() if i + 1 < len(matches) else len(normalized)
        sections.append((kind, normalized[match.end() : end]))
    return sections


def estimate_years(text: str) -> float:
    """Stima gli anni di esperienza sommando gli intervalli di date del CV.

    Conta solo le date che cadono nelle sezioni di esperienza lavorativa: senza
    questo filtro gli anni di universita' verrebbero sommati a quelli di lavoro
    e ogni candidato risulterebbe molto piu' esperto di quanto sia.

    Gli intervalli sovrapposti (lavori paralleli, studio piu' lavoro) vengono
    fusi, altrimenti un curriculum ricco gonfierebbe comunque il totale.
    """
    sections = split_sections(text)
    work = [body for kind, body in sections if kind in ("esperienza", "sconosciuto")]
    # Nessuna sezione di esperienza riconosciuta: si ripiega sull'intero testo,
    # accettando una stima piu' grossolana.
    normalized = "\n".join(work) if work else normalize(text)
    intervals: list[tuple[int, int]] = []

    for regex, numeric in ((_RANGE_RE, False), (_NUMERIC_RANGE_RE, True)):
        for match in regex.finditer(normalized):
            year1 = int(match.group("y1"))
            if numeric:
                month1 = int(match.group("m1") or 1)
            else:
                month1 = _MONTHS.get((match.group("m1") or "").lower(), 1)
            if match.group("now"):
                year2, month2 = _CURRENT_YEAR, 12
            else:
                year2 = int(match.group("y2"))
                month2 = int(match.group("m2") or 12) if numeric else _MONTHS.get((match.group("m2") or "").lower(), 12)
            if not (1950 <= year1 <= _CURRENT_YEAR and year1 <= year2 <= _CURRENT_YEAR + 1):
                continue
            start = year1 * 12 + max(1, min(12, month1))
            end = year2 * 12 + max(1, min(12, month2))
            if 0 < end - start <= 12 * 45:
                intervals.append((start, end))

    months = _merge_intervals(intervals)
    if months:
        return round(months / 12.0, 1)
    # Nessun intervallo riconosciuto: si prova la dichiarazione esplicita.
    declared = extract_required_years(text)
    return float(declared) if declared else 0.0


# --------------------------------------------------------------------------
# Nome della persona
# --------------------------------------------------------------------------

# Righe che non possono essere un nome: contatti, date, elenchi puntati.
_NON_NOME = re.compile(r"[0-9@|/\\•·+_=]|https?:|www\.", re.IGNORECASE)

# Parole che compaiono in testa a un curriculum ma non sono nomi di persona.
_PAROLE_NON_NOME = {
    "curriculum", "vitae", "cv", "resume", "resumé", "profilo", "profile",
    "contatti", "contatto", "contact", "contacts", "lingue", "languages",
    "esperienza", "esperienze", "experience", "formazione", "education",
    "competenze", "skills", "istruzione", "studi", "obiettivo", "about",
    "informazioni", "personali", "personal", "dati", "riepilogo", "summary",
    "dottore", "dottoressa", "ingegnere", "avvocato", "sig", "sig.ra",
    "europass", "telefono", "cellulare", "indirizzo", "email", "mail",
    "nazionalita", "residenza", "domicilio", "portfolio", "linkedin",
}


def _sembra_nome(riga: str) -> list[str] | None:
    """Dice se una riga puo' essere un nome di persona, e la scompone in parole."""
    if not riga or len(riga) > 42 or _NON_NOME.search(riga):
        return None
    parole = riga.replace(",", " ").split()
    if not 1 <= len(parole) <= 4:
        return None
    for p in parole:
        pulita = p.replace("'", "").replace("-", "").replace(".", "")
        if not pulita.isalpha() or not 2 <= len(pulita) <= 20:
            return None
        if not p[0].isupper():
            return None
        if pulita.lower() in _PAROLE_NON_NOME:
            return None
    # Una riga tutta maiuscola con tre o piu' parole e' quasi sempre una
    # qualifica ("DOTTORE IN SCIENZE BIOLOGICHE"). Con due parole invece puo'
    # benissimo essere un nome scritto in maiuscolo ("LUCA VERDI").
    if riga.isupper() and len(parole) > 2:
        return None
    return parole


def extract_person_name(text: str) -> str:
    """Ricava nome e cognome dalle prime righe del curriculum.

    Due casi da coprire: il nome su una riga sola ("Mario Rossi") e il nome
    spezzato su righe consecutive, che capita spesso perche' nei PDF impaginati
    a colonne nome e cognome finiscono su capoversi diversi.

    Restituisce stringa vuota se non trova nulla di credibile: meglio ricadere
    sul nome del file che inventare un nome sbagliato.
    """
    righe = [r.strip() for r in text.splitlines()]
    righe = [r for r in righe if r][:12]
    if not righe:
        return ""

    # Si guarda solo la sequenza iniziale: il nome sta in cima, e fermarsi al
    # primo capoverso che non somiglia a un nome evita di pescare piu' avanti
    # parole isolate come "Lingue" o "Roma".
    sequenza: list[list[str]] = []
    for riga in righe:
        parole = _sembra_nome(riga)
        if parole is None:
            # Finche' non si e' trovato nulla si tira dritto: in cima possono
            # esserci "Curriculum Vitae" o un recapito. Una volta iniziata la
            # sequenza, invece, la prima riga diversa la chiude.
            if sequenza:
                break
            continue
        sequenza.append(parole)

    if not sequenza:
        return ""
    if len(sequenza[0]) >= 2:
        parole = sequenza[0][:4]
    else:
        # Nome e cognome su righe separate. Ci si ferma a due: una terza riga
        # da una parola sola e' piu' spesso la qualifica ("Farmacista") che un
        # secondo cognome, e sbagliare qui mette una professione al posto del nome.
        parole = [p[0] for p in sequenza[:2] if len(p) == 1]
        if len(parole) < 2:
            return ""

    nome = " ".join(parole)
    return nome.title() if nome.isupper() else nome


# --------------------------------------------------------------------------
# Profilo
# --------------------------------------------------------------------------

@dataclass
class CVProfile:
    raw_text: str
    skills: list[str] = field(default_factory=list)
    education_fields: list[str] = field(default_factory=list)
    education_level: int = 0
    education_label: str = ""
    languages: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    years_experience: float = 0.0

    def to_storage(self) -> dict[str, Any]:
        return {
            "skills": self.skills,
            "education": {
                "level": self.education_level,
                "label": self.education_label,
                "fields": self.education_fields,
            },
            "titles": self.roles,
            "languages": self.languages,
            "years_experience": self.years_experience,
        }


def build_profile(text: str) -> CVProfile:
    """Ricava dal testo del curriculum tutto cio' che serve al punteggio."""
    level, label = extract_education_level(text)
    return CVProfile(
        raw_text=text,
        skills=extract_skills(text),
        education_fields=extract_education_fields(text),
        education_level=level,
        education_label=label,
        languages=extract_languages(text),
        roles=extract_roles(text),
        years_experience=estimate_years(text),
    )
