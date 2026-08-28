"""Avvio dell'applicazione.

    python run.py

Apre il server locale e stampa l'indirizzo da usare nel browser.
"""
from __future__ import annotations

import sys
import webbrowser
from pathlib import Path
from threading import Timer

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn

from app.config import PORT


def _open_browser() -> None:
    try:
        webbrowser.open(f"http://127.0.0.1:{PORT}/")
    except Exception:
        pass


if __name__ == "__main__":
    no_browser = "--no-browser" in sys.argv
    reload_mode = "--reload" in sys.argv
    if not no_browser and not reload_mode:
        Timer(1.4, _open_browser).start()

    print(f"\n  JobSeeker in ascolto su http://127.0.0.1:{PORT}/")
    print("  Premi Ctrl+C per fermarlo.\n")
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=PORT,
        reload=reload_mode,
        log_level="info",
        access_log=False,
    )
