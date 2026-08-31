"""Credenziali di accesso: impronta della password, primo avvio.

Le credenziali possono arrivare da due posti. Il file `.env` resta valido per
chi distribuisce l'applicazione gia' configurata; l'interfaccia serve a chi la
riceve e non ha voglia di aprire un file di testo per usarla. Quando ci sono
entrambe vince il database, cosi' cambiare la password non richiede di rifare
il contenitore.

La password non viene mai conservata: nel database finisce solo la sua
impronta. Chi legge il file del database non puo' risalire alla password - e
una password di un'applicazione personale, molto spesso, e' la stessa usata
altrove.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets as _casuale

from . import db
from .config import AUTH_PASSWORD, AUTH_USER, REQUIRE_AUTH

# PBKDF2 dalla libreria standard: niente dipendenze in piu' per una cosa che
# gira una volta per accesso. Il numero di giri e' quello raccomandato da OWASP
# per SHA-256, e resta scritto dentro l'impronta: alzandolo in futuro le
# impronte gia' create continuano a funzionare.
GIRI = 210_000
ALGORITMO = "pbkdf2_sha256"

CHIAVE_UTENTE = "auth_user"
CHIAVE_IMPRONTA = "auth_password"
# Il segno che la procedura di primo avvio e' stata fatta. Serve perche' "e' la
# prima volta" non si puo' dedurre dall'assenza di una password: su un
# portatile la password non serve, e senza questo segno la procedura
# ricomparirebbe a ogni avvio.
CHIAVE_CONFIGURATO = "setup_done"


def impronta(password: str) -> str:
    """Impronta con sale casuale, nel formato `algoritmo$giri$sale$impronta`."""
    sale = _casuale.token_bytes(16)
    calcolata = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), sale, GIRI)
    return f"{ALGORITMO}${GIRI}${sale.hex()}${calcolata.hex()}"


def _corrisponde(password: str, memorizzata: str) -> bool:
    try:
        algoritmo, giri, sale, attesa = memorizzata.split("$")
        if algoritmo != ALGORITMO:
            return False
        calcolata = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(sale), int(giri))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calcolata.hex(), attesa)


def utente() -> str:
    """Il nome utente configurato, vuoto se va bene qualunque nome."""
    return db.get_setting(CHIAVE_UTENTE, "") or AUTH_USER


def impostate() -> bool:
    """C'e' una password, da qualunque parte venga."""
    return bool(db.get_setting(CHIAVE_IMPRONTA, "") or AUTH_PASSWORD)


def imposta(nome: str, password: str) -> None:
    db.set_setting(CHIAVE_UTENTE, (nome or "").strip())
    db.set_setting(CHIAVE_IMPRONTA, impronta(password))


def verifica(nome: str, password: str) -> bool:
    """Confronto a tempo costante fra le credenziali date e quelle configurate.

    `compare_digest` e non `==` perche' un confronto fra stringhe esce al primo
    carattere diverso, e i tempi di risposta rivelerebbero la password un
    carattere alla volta. Nome utente vuoto in configurazione significa
    "qualunque nome": conta solo la password.
    """
    memorizzata = db.get_setting(CHIAVE_IMPRONTA, "")
    if memorizzata:
        atteso = db.get_setting(CHIAVE_UTENTE, "")
        return (_casuale.compare_digest(nome, atteso or nome)
                and _corrisponde(password, memorizzata))
    # Nessuna credenziale nel database: valgono quelle del file .env, che sono
    # in chiaro perche' e' cosi' che le legge l'ambiente.
    if AUTH_PASSWORD:
        return (_casuale.compare_digest(nome, AUTH_USER or nome)
                and _casuale.compare_digest(password, AUTH_PASSWORD))
    return False


def firma_sessione() -> str:
    """Il segreto che lega i cookie di sessione alle credenziali attuali.

    Entra nella chiave con cui si firmano i cookie: cambiando la password,
    tutte le sessioni aperte altrove smettono di valere.
    """
    return db.get_setting(CHIAVE_IMPRONTA, "") or AUTH_PASSWORD


def gia_configurato() -> bool:
    return db.get_setting(CHIAVE_CONFIGURATO, "") == "1"


def segna_configurato() -> None:
    db.set_setting(CHIAVE_CONFIGURATO, "1")


def _ha_dati() -> bool:
    riga = db.query_one(
        "SELECT (SELECT COUNT(*) FROM cv) + (SELECT COUNT(*) FROM job) "
        "     + (SELECT COUNT(*) FROM provider) AS quanti")
    return bool(riga and riga["quanti"])


def riconosci_installazione_esistente() -> None:
    """Un'installazione che gira da tempo non e' al primo avvio.

    Il segno di "configurazione fatta" nasce con questa versione: chi aggiorna
    non ce l'ha, e senza questo controllo si troverebbe la procedura di primo
    avvio davanti a un archivio pieno di offerte. Si considera gia' configurata
    quella che ha delle credenziali o dei dati dentro.
    """
    if gia_configurato():
        return
    if impostate() or _ha_dati():
        segna_configurato()


def password_obbligatoria() -> bool:
    """Se la password si puo' saltare oppure no.

    Su un server raggiungibile dalla rete non e' negoziabile, ed e' quello che
    dice `JOBSEEKER_REQUIRE_AUTH`. Sul portatile di chi la usa, dove
    l'applicazione ascolta solo su 127.0.0.1, chiedere una password a ogni
    apertura e' un fastidio senza contropartita.
    """
    return REQUIRE_AUTH


def serve_configurazione() -> bool:
    """Se va mostrata la procedura di primo avvio.

    Due casi. Il primo: protezione richiesta e nessuna credenziale da nessuna
    parte - prima l'applicazione si rifiutava di partire, il che e' sicuro ma
    lascia chi la riceve davanti a un contenitore che muore e a un file da
    compilare al buio. Il secondo: non e' mai stata configurata, e allora la
    procedura serve comunque, foss'anche solo per incollare le chiavi.
    """
    if REQUIRE_AUTH and not impostate():
        return True
    return not gia_configurato()


def protetto() -> bool:
    """Se c'e' una password, tutto passa dall'accesso."""
    return impostate()
