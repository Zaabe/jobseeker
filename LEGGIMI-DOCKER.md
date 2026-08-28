# JobSeeker su server, con Docker

Tutto quello che serve è in questo archivio. Servono un server Linux con
Docker installato e un nome a dominio che punti al suo indirizzo IP.

---

## 1. Prima di cominciare

Sul server:

```bash
docker --version && docker compose version
```

Se rispondono, sei a posto. Altrimenti su Debian/Ubuntu:

```bash
curl -fsSL https://get.docker.com | sudo sh
```

Il **dominio** (per esempio `jobseeker.miodominio.it`) deve già puntare
all'IP del server, e le porte **80** e **443** devono essere raggiungibili da
internet. Servono a Caddy per farsi rilasciare il certificato HTTPS: la
verifica di Let's Encrypt passa da lì, e senza non parte.

---

## 2. Copiare i file sul server

```bash
scp jobseeker-docker.zip utente@TUO-SERVER:~/
```

poi, collegato al server:

```bash
unzip jobseeker-docker.zip -d jobseeker && cd jobseeker
```

---

## 3. Configurare

```bash
cp .env.example .env
nano .env
```

Le voci **obbligatorie**:

| Voce | Cosa metterci |
|---|---|
| `JOBSEEKER_USER` | il nome utente per entrare |
| `JOBSEEKER_PASSWORD` | una password lunga e non riusata |
| `DOMINIO` | il dominio, senza `https://` |

Per generare una password robusta:

```bash
openssl rand -base64 24
```

Poi ricopia dal tuo `.env` locale le chiavi che già usi: `ADZUNA_APP_ID`,
`ADZUNA_APP_KEY`, `GEMINI_API_KEY`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`.
**Non le ho messe in questo archivio di proposito**: un file zip gira fra
computer, backup e cartelle condivise, e delle credenziali finite lì dentro
è difficile riprendere il controllo.

Se `JOBSEEKER_PASSWORD` resta vuota il contenitore **non parte**. È voluto:
senza password chiunque conosca l'indirizzo leggerebbe il tuo curriculum, lo
storico delle candidature, e potrebbe spendere le tue chiavi API.

---

## 4. Avviare

```bash
docker compose up -d --build
```

La prima volta impiega qualche minuto: costruisce l'immagine e Caddy chiede
il certificato. Per seguire cosa succede:

```bash
docker compose logs -f
```

Quando vedi `Application startup complete`, apri **https://TUO-DOMINIO** e
inserisci utente e password.

---

## 4-bis. Con Portainer

Portainer non usa il file `.env`: le variabili si scrivono nella sezione
**Environment variables** della stack, ed e' da li' che compose le legge.

1. **Stacks → Add stack → Repository**, e indica l'URL del repository git.
   Deve essere un deploy *da repository*, non un compose incollato
   nell'editor: la stack ha bisogno anche di `Dockerfile` e `Caddyfile`, che
   nell'editor non ci sarebbero.
2. **Compose path**: `docker-compose.yml`
3. In **Environment variables** aggiungi almeno queste tre:

   | name | value |
   |---|---|
   | `JOBSEEKER_USER` | il nome utente per entrare |
   | `JOBSEEKER_PASSWORD` | la password |

   (`DOMINIO` serviva a Caddy: senza quel contenitore non e' piu' necessaria.)

   piu' `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `GEMINI_API_KEY`,
   `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` se li usi. Le voci SMTP servono solo
   per le notifiche via email: lasciale fuori se usi Telegram.

4. **Deploy the stack**.

Se il deploy si ferma su `env file ... not found`, la stack sta ancora usando
una versione del compose con `env_file`: aggiorna il repository e ridistribuisci.

### Portare il database esistente

Con Portainer i dati stanno in un volume Docker (`jobseeker_jobseeker-data`),
non in una cartella del progetto. Per caricarci dentro il database che gia'
avevi, dal server:

```bash
docker compose stop jobseeker
docker cp jobseeker.db jobseeker:/app/data/jobseeker.db
docker cp "CV.pdf" jobseeker:/app/data/cv/
docker compose start jobseeker
```

Fermare prima il contenitore serve a non sovrascrivere un database mentre
qualcuno ci sta scrivendo. Se non copi nulla, l'applicazione parte con un
archivio vuoto: ricarichi il curriculum e ricrei ricerche e fonti
dall'interfaccia.

Per il backup, la direzione opposta:

```bash
docker compose stop jobseeker
docker cp jobseeker:/app/data/jobseeker.db ./backup-$(date +%F).db
docker compose start jobseeker
```

---

## 4-ter. Il reverse proxy sulla macchina

Il contenitore pubblica la porta **solo su `127.0.0.1:8000`**: la vede il
reverse proxy installato sul server, non internet. Il blocco nginx:

```nginx
server {
    listen 443 ssl http2;
    server_name jobseeker.tuodominio.it;

    # i certificati li gestisce gia' il tuo proxy (certbot o simili)
    ssl_certificate     /etc/letsencrypt/live/jobseeker.tuodominio.it/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/jobseeker.tuodominio.it/privkey.pem;

    # Il curriculum e lo storico non devono finire nei motori di ricerca.
    add_header X-Robots-Tag "noindex, nofollow" always;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        # Senza questo l'applicazione crede di stare su http e le notifiche
        # del browser non si attivano.
        proxy_set_header X-Forwarded-Proto $scheme;

        # Il caricamento del curriculum supera il limite predefinito di 1 MB.
        client_max_body_size 20M;
    }
}
```

**Serve HTTPS.** L'accesso usa HTTP Basic, che manda utente e password
codificati in base64: non e' cifratura. Su `http://` chiunque stia sulla rete
di mezzo le legge, e in piu' le notifiche del browser e l'installazione come
app non funzionano.

---

## 5. Verificare che sia tutto in piedi

```bash
docker compose ps                          # "running" e "healthy"
curl -s http://127.0.0.1:8000/healthz      # {"status":"ok"}  <- dal server
curl -sI http://127.0.0.1:8000/ | head -1  # HTTP/1.1 401     <- l'accesso è attivo
curl -skI https://TUO-DOMINIO/ | head -1   # HTTP/2 401       <- attraverso il proxy
```

Quel **401** senza credenziali è il risultato giusto: significa che la
protezione funziona.

---

## Cosa c'è dentro l'archivio

| File | A cosa serve |
|---|---|
| `app/` | l'applicazione |
| `data/` | database e curriculum, solo nell'archivio zip: non e' nel repository |
| `Dockerfile` | come si costruisce l'immagine |
| `docker-compose.yml` | i due contenitori e come si parlano |
| `Caddyfile` | configurazione per Caddy, se un giorno lo riattivi |
| `entrypoint.sh` | sistema i permessi dei dati all'avvio |
| `.env.example` | il modello da copiare in `.env` |
| `requirements.txt` | le librerie Python |

Il `data/` contiene già le 1284 offerte raccolte, il curriculum, le
candidature inviate e i giudizi che hanno addestrato il riconoscimento: al
primo avvio ritrovi tutto com'era.

---

## Uso quotidiano

```bash
docker compose logs -f jobseeker    # cosa sta facendo
docker compose restart jobseeker    # riavvio
docker compose down                 # ferma tutto (i dati restano)
docker compose up -d --build        # dopo aver aggiornato il codice
```

**Backup.** Tutto cio' che conta sta nel volume `jobseeker-data`:

```bash
docker compose stop jobseeker
docker cp jobseeker:/app/data ./backup-$(date +%F)
docker compose start jobseeker
```

Fermare il contenitore prima serve a prendere il database in un momento in
cui nessuno ci sta scrivendo.

---

## Se qualcosa non va

**Il contenitore riparte in continuazione.** Guarda `docker compose logs
jobseeker`. Quasi sempre è la password vuota nel `.env`.

**`env file ... not found`.** La stack sta usando una versione del compose
con `env_file: .env`. Portainer quel file non lo crea: le variabili vanno
nella sezione **Environment variables** della stack, e il compose le legge da
li'. Aggiorna il repository e ridistribuisci.

**`unable to open database file`.** I permessi della cartella dati.
Normalmente li sistema `entrypoint.sh` da solo; se il messaggio compare
comunque con un montaggio da cartella:

```bash
sudo chown -R 10001:10001 data
docker compose restart jobseeker
```

**Il certificato non arriva.** Caddy ha bisogno che il dominio punti già a
questo server e che le porte 80 e 443 siano aperte. Controlla con
`docker compose logs caddy`, e verifica il DNS con `dig +short TUO-DOMINIO`.

**Le notifiche del browser non compaiono.** Funzionano solo su HTTPS con
certificato valido. Su `http://` il browser le blocca e basta. Telegram
invece funziona in ogni caso.

**Ho cambiato il codice e non vedo differenza.** L'immagine va ricostruita:
`docker compose up -d --build`. Ricaricare la pagina non basta.

---

## Due cose da sapere

**Un solo processo.** Il controllo periodico delle offerte gira dentro
l'applicazione. Se aggiungi worker a uvicorn, gira una volta per worker e
ogni offerta nuova genera notifiche doppie. Il `--workers 1` nel Dockerfile
non è di troppo.

**HTTP Basic vuole HTTPS.** L'autenticazione manda utente e password
codificati in base64, che non è cifratura: chiunque stia sulla rete di mezzo
li legge. Per questo Caddy c'è. Se scegli di girare in `http://` puro (il
blocco commentato nel `Caddyfile`), fallo solo dentro una rete privata.
