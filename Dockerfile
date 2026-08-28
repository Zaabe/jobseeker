# JobSeeker - immagine per l'esecuzione su server.
#
# Immagine unica: l'applicazione e il suo database SQLite stanno insieme, e i
# dati vivono su un volume montato in /app/data. Non serve un database
# separato: il carico e' di una persona sola e SQLite in modalita' WAL lo
# regge senza pensarci.
FROM python:3.12-slim

# Fuso orario italiano: le date delle offerte e l'ora del controllo periodico
# vengono mostrate cosi' come le legge il sistema.
ENV TZ=Europe/Rome \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# gosu serve all'avvio per cedere i privilegi dopo aver sistemato i permessi
# della cartella dei dati (vedi entrypoint.sh).
RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# I requisiti si copiano prima del codice: cosi' Docker riusa il livello con
# le dipendenze quando cambia soltanto l'applicazione.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir "google-genai>=1.0"

COPY app ./app
COPY entrypoint.sh /usr/local/bin/entrypoint.sh

RUN useradd --create-home --uid 10001 jobseeker \
    && mkdir -p /app/data/cv \
    && chown -R jobseeker:jobseeker /app \
    && chmod +x /usr/local/bin/entrypoint.sh

VOLUME ["/app/data"]
EXPOSE 8000

# La sonda usa /healthz, che resta fuori dall'autenticazione: interrogare una
# rotta protetta darebbe 401 e il contenitore risulterebbe sempre malato.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Un solo processo, sempre. Il controllo periodico delle offerte vive dentro
# l'applicazione: con due worker girerebbe due volte, e ogni offerta nuova
# produrrebbe due notifiche.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--no-access-log", "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
