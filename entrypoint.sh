#!/bin/sh
# Sistema i permessi della cartella dei dati, poi cede i privilegi.
#
# Serve perche' /app/data arriva da un montaggio dell'host: i file scompattati
# dallo zip appartengono a chi li ha scompattati, quasi mai all'utente 10001
# dell'immagine. Senza questo passaggio SQLite non riesce a scrivere e il
# contenitore muore con un "unable to open database file" che non spiega
# niente. Farlo qui evita di dover ricordare un chown a mano sul server.
set -e

mkdir -p /app/data/cv
if ! chown -R jobseeker:jobseeker /app/data 2>/dev/null; then
    echo "Attenzione: non ho potuto cambiare proprietario a /app/data." >&2
    echo "Se l'avvio fallisce, esegui sull'host:  sudo chown -R 10001:10001 data" >&2
fi

exec gosu jobseeker "$@"