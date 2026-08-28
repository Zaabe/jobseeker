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

## 5. Verificare che sia tutto in piedi

```bash
docker compose ps                      # entrambi "running", jobseeker "healthy"
curl -sk https://TUO-DOMINIO/healthz   # {"status":"ok"}
curl -skI https://TUO-DOMINIO/ | head -1   # HTTP/2 401  <- l'accesso è attivo
```

Quel **401** senza credenziali è il risultato giusto: significa che la
protezione funziona.

---

## Cosa c'è dentro l'archivio

| File | A cosa serve |
|---|---|
| `app/` | l'applicazione |
| `data/` | il tuo database e il curriculum già caricato |
| `Dockerfile` | come si costruisce l'immagine |
| `docker-compose.yml` | i due contenitori e come si parlano |
| `Caddyfile` | HTTPS e certificato automatico |
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

**Backup.** Tutto ciò che conta sta nella cartella `data/`:

```bash
docker compose stop jobseeker
tar czf backup-$(date +%F).tar.gz data/
docker compose start jobseeker
```

Fermare il contenitore prima serve a prendere il database in un momento in
cui nessuno ci sta scrivendo.

---

## Se qualcosa non va

**Il contenitore riparte in continuazione.** Guarda `docker compose logs
jobseeker`. Quasi sempre è la password vuota nel `.env`.

**`unable to open database file`.** I permessi della cartella dati.
Normalmente li sistema `entrypoint.sh` da solo; se il messaggio compare
comunque:

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
