"""Avvio dell'applicazione.

    python run.py

Apre il server locale e stampa l'indirizzo da usare nel browser.
"""
from __future__ import annotations

import socket
import sys
import time
import webbrowser
from pathlib import Path
from threading import Thread

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn

from app.config import PORT

# Quante porte provare dopo quella preferita prima di arrendersi.
PORTE_DA_PROVARE = 20


def _libera(porta: int) -> bool:
    """Se qualcuno sta gia' ascoltando su quella porta.

    Si prova ad occuparla davvero: e' l'unico controllo che non mente. Niente
    `SO_REUSEADDR`, che su alcuni sistemi farebbe riuscire il legame anche
    quando la porta e' occupata, cioe' esattamente il caso da riconoscere.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as presa:
        try:
            presa.bind(("127.0.0.1", porta))
            return True
        except OSError:
            return False


def scegli_porta(preferita: int) -> int:
    """La prima porta libera a partire da quella configurata.

    Con la porta occupata uvicorn moriva con un errore di sistema in mezzo a
    una decina di righe di traceback: chi apre l'applicazione con un doppio
    clic non ha modo di capire che il problema e' un'altra copia gia' aperta.
    """
    for porta in range(preferita, preferita + PORTE_DA_PROVARE):
        if _libera(porta):
            return porta
    return preferita


def apri_quando_pronto(porta: int) -> None:
    """Apre il browser appena il server risponde, non dopo un'attesa a caso.

    Il primo avvio installa, apre il database e legge le fonti: puo' metterci
    diversi secondi. Aprire il browser a tempo scaduto mostrava una pagina di
    errore proprio a chi sta usando l'applicazione per la prima volta.
    """
    for _ in range(150):          # un minuto abbondante, poi si lascia perdere
        try:
            with socket.create_connection(("127.0.0.1", porta), timeout=0.4):
                break
        except OSError:
            time.sleep(0.4)
    else:
        return
    try:
        webbrowser.open(f"http://127.0.0.1:{porta}/")
    except Exception:
        pass


if __name__ == "__main__":
    no_browser = "--no-browser" in sys.argv
    reload_mode = "--reload" in sys.argv

    porta = scegli_porta(PORT)
    if porta != PORT:
        # `flush`: avviando dal file .bat, con l'output rediretto, Python
        # accumula in memoria e questi messaggi comparirebbero solo alla
        # chiusura, cioe' quando non servono piu'.
        print(f"\n  La porta {PORT} e' occupata - forse JobSeeker e' gia' aperto.", flush=True)
        print(f"  Uso la {porta}.", flush=True)

    if not no_browser and not reload_mode:
        Thread(target=apri_quando_pronto, args=(porta,), daemon=True).start()

    print(f"\n  JobSeeker in ascolto su http://127.0.0.1:{porta}/", flush=True)
    print("  Premi Ctrl+C per fermarlo.\n", flush=True)
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=porta,
        reload=reload_mode,
        log_level="info",
        access_log=False,
    )
