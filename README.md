# JobSeeker

Raccoglie offerte di lavoro dalle **API ufficiali** dei portali, le confronta con il tuo
curriculum assegnando una compatibilità da 0 a 100, tiene lo storico delle candidature e ti
avvisa quando compare qualcosa sopra la soglia che hai deciso.

Funziona nel browser e si può installare come applicazione (PWA) su desktop e telefono.
Tutti i dati — curriculum compreso — restano sul tuo computer, in un file SQLite.

---

## Avvio rapido

Due modi, a seconda di dove deve girare.

**Sul proprio computer** — vedi qui sotto. Nessuna autenticazione, i dati restano in
locale.

**Su un server** — con Docker, dietro HTTPS e protetto da password: le istruzioni sono
in **[LEGGIMI-DOCKER.md](LEGGIMI-DOCKER.md)**. In sintesi:

```bash
cp .env.example .env    # compila utente, password e dominio
docker compose up -d --build
```

---

### In locale, su Windows

Doppio clic su **`Avvia JobSeeker.bat`**. Al primo avvio prepara da solo l'ambiente e
installa le dipendenze, poi apre `http://127.0.0.1:8000/` nel browser.

Da riga di comando:

```bash
.venv\Scripts\python.exe run.py
```

Per fermarlo: `Ctrl+C` nella finestra del terminale.

### I tre passaggi per renderlo utile

1. **Curriculum** → carica il tuo CV in PDF o DOCX. Senza, le offerte vengono raccolte ma
   non ricevono un punteggio.
2. **Ricerche** → definisci cosa cerchi: parole chiave e località. Ne trovi già una di
   esempio da adattare.
3. **Fonti** → aggiungi da dove pescare le offerte. Ne trovi già una configurata
   (Eurofins, che ha una quarantina di posizioni di laboratorio in Italia).

Poi premi **Controlla ora**. Da lì in avanti il controllo è automatico.

---

## Le fonti

Dodici fonti su tredici usano **API pubbliche e documentate**: niente selettori che si
rompono, niente blocchi dell'indirizzo IP, dati completi e puliti. L'unica eccezione è
**LinkedIn**, che un'API aperta non ce l'ha: quella fonte legge le pagine pubbliche, va
tenuta a ritmo basso e ogni tanto smetterà di funzionare. Le
[avvertenze stanno qui sotto](#linkedin-lunica-fonte-senza-api).

### Aggiungere un'azienda incollando il suo link

È il modo più diretto. Vai in **Fonti**, incolla l'indirizzo della pagina "lavora con noi"
e premi **Riconosci**: il programma capisce quale sistema usa quell'azienda e interroga
l'API corrispondente.

| Sistema | Come riconoscere il link | Esempio |
|---|---|---|
| **Workday** | `…myworkdayjobs.com/…` | `https://sanofi.wd3.myworkdayjobs.com/SanofiCareers` |
| Greenhouse | `boards.greenhouse.io/…` | `https://boards.greenhouse.io/gitlab` |
| Ashby | `jobs.ashbyhq.com/…` | `https://jobs.ashbyhq.com/satispay` |
| SmartRecruiters | `jobs.smartrecruiters.com/…` | `https://jobs.smartrecruiters.com/Eurofins` |
| Workable | `apply.workable.com/…` | `https://apply.workable.com/nomeazienda/` |
| Recruitee | `nomeazienda.recruitee.com` | `https://nomeazienda.recruitee.com` |

**Workday merita una nota**: è la piattaforma delle grandi aziende farmaceutiche
(Novartis, Sanofi, AstraZeneca, GSK, Takeda…) ed è la fonte migliore del sistema, perché
filtra per paese lato server e restituisce la **descrizione integrale** dell'annuncio — quindi
punteggi molto più attendibili degli aggregatori, che troncano il testo. Il nome del sito
carriere varia per azienda (`SanofiCareers`, `Novartis_Careers`, `Careers`…) ma sta
nell'indirizzo: basta incollarlo così com'è, anche con la lingua (`/en-US/`) o il percorso di
una singola offerta.

Se un'azienda ti interessa, cerca la sua pagina delle posizioni aperte e guarda l'indirizzo:
se ricade in uno di questi casi, la puoi seguire.

### Aggiungere una fonte a mano

Se non hai l'indirizzo sotto mano, o vuoi controllare cosa stai salvando, scegli la fonte
dall'elenco in **Fonti**: si apre un modulo con i campi che quella piattaforma richiede,
ciascuno con la spiegazione di dove trovarlo. Per Workday, per esempio, sono tre:

| Campo | Dove si trova in `sanofi.wd3.myworkdayjobs.com/SanofiCareers` |
|---|---|
| Azienda (tenant) | `sanofi` |
| Data center | `wd3` |
| Nome del sito carriere | `SanofiCareers` — attenzione alle maiuscole |

C'è anche un campo che ricava i tre valori incollando un indirizzo qualsiasi (funziona anche
con il link di una singola offerta o con la lingua nel percorso), e soprattutto un pulsante
**Prova senza salvare**: interroga la fonte e ti dice quante offerte restituisce e quante
sono pertinenti alle tue ricerche, prima di aggiungerla davvero.

Ogni fonte già configurata ha un pulsante **Modifica**: riapre lo stesso modulo con i valori
attuali, così puoi correggere un parametro sbagliato, rinominarla o cambiarne l'intervallo
di controllo senza doverla eliminare e rifare da zero.

**Se l'indirizzo Workday non lo trovi**, usa *Cerca il portale* e scrivi solo il nome
dell'azienda. Molte aziende mettono davanti a Workday un sito con il proprio marchio che non
rivela l'indirizzo sottostante: Thermo Fisher, per esempio, pubblica su `jobs.thermofisher.com`
(piattaforma Phenom) mentre le offerte stanno su `thermofisher.wd5.myworkdayjobs.com`. La
ricerca prova i data center e i nomi di sito più diffusi e ti mostra quelli che rispondono,
con il numero di offerte di ciascuno.

### Aggregatori generalisti

| Fonte | Chiave | Note |
|---|---|---|
| **Adzuna** | gratuita, richiesta | La migliore copertura italiana generalista. **Consigliata.** |
| LinkedIn | no | Pagine pubbliche, non un'API: [leggi le avvertenze](#linkedin-lunica-fonte-senza-api) |
| The Muse | no | Molte multinazionali, filtro geografico impreciso |
| Arbeitnow | no | Europa, molto remoto e Germania |
| Remotive, RemoteOK, Jobicy | no | Solo posizioni da remoto, in prevalenza tecnologiche |

**Per attivare Adzuna:** registrati gratis su [developer.adzuna.com](https://developer.adzuna.com/),
copia `Application ID` e `Application Key` nel file `.env`, riavvia, poi aggiungi la fonte
Adzuna dall'elenco in **Fonti**.

### LinkedIn: l'unica fonte senza API

LinkedIn apre le API solo ai partner commerciali, quindi questa fonte **legge le pagine
pubbliche**, le stesse che il sito mostra a chi non ha un account. Funziona, ma è diversa
dalle altre e conviene saperlo prima di aggiungerla:

- **le condizioni d'uso di LinkedIn non ammettono la raccolta automatica dei contenuti.**
  La fonte non usa il tuo account, non chiede credenziali e si disattiva come tutte le
  altre, ma la scelta di tenerla accesa è tua;
- **si romperà, ogni tanto.** L'HTML cambia senza preavviso: quando succede la fonte
  smette di restituire offerte e va sistemata. Le altre dodici continuano a funzionare;
- **LinkedIn conta le richieste** e a un certo punto risponde `999` o mostra il muro del
  login. Per questo il ritmo è basso di proposito: mezz'ora di intervallo minimo, qualche
  secondo fra una richiesta e l'altra, e le descrizioni scaricate solo per le offerte che
  superano il filtro di pertinenza. La ricerca è limitata agli **ultimi 7 giorni**: senza
  limite di data l'elenco di una parola chiave è lungo migliaia di annunci e non si
  esaurisce mai. Il campo *Solo gli ultimi giorni* alza o toglie il limite (`0` = nessun
  limite, molte più richieste). Se la fonte viene rifiutata, l'attesa raddoppia da sola a
  ogni tentativo fallito, come per tutte le altre.

**Come scorre l'elenco.** LinkedIn restituisce **dieci offerte per richiesta**, e ogni giro
ne legge quattro pagine per parola chiave, spese in due modi: le prime due guardano la
**testa** dell'elenco, dov'è che compaiono gli annunci nuovi; le altre scendono **più in
basso**, riprendendo da dove il giro precedente si era fermato. Il segnaposto è salvato
insieme alla fonte, quindi nel giro di qualche controllo l'elenco viene percorso tutto e poi
si ricomincia dalla cima. Senza la seconda passata la fonte si bloccherebbe: dopo il primo
giro la testa dell'elenco è già tutta in archivio, e continuerebbe a rileggere le stesse
dieci offerte all'infinito.

Si aggiunge come le altre: incolla l'indirizzo di una ricerca LinkedIn
(`https://www.linkedin.com/jobs/search/?keywords=laboratorio&location=Italia`) — parole
chiave, località e filtro data vengono letti dall'indirizzo — oppure scegli **LinkedIn**
dall'elenco e lascia i campi vuoti per usare le parole chiave delle ricerche salvate.

### Perché non Indeed o AlmaLaurea

Non espongono un'API pubblica utilizzabile: Indeed ha chiuso sia l'API sia i feed RSS,
AlmaLaurea non ne ha una, e le loro pagine sono protette da controlli anti-automazione ben
più aggressivi di quelli di LinkedIn. Buona parte delle stesse offerte ricompare comunque
attraverso Adzuna, che le indicizza legalmente.

---

## Come funziona il punteggio

La percentuale è la media pesata di sei componenti. Il dettaglio di ogni offerta le mostra
tutte, con il motivo del punteggio: non è un numero da prendere sulla fiducia.

| Componente | Peso | Cosa misura |
|---|---|---|
| **Competenze** | 40 | Quante delle competenze richieste sono nel tuo CV. Le competenze rare (`HPLC`, `GMP`) pesano più di quelle generiche (`Office`) |
| **Affinità complessiva** | 25 | Quanto del linguaggio dell'annuncio trova riscontro nel curriculum |
| **Ruolo** | 15 | Se la posizione appartiene a un'area professionale che hai già frequentato |
| **Titolo di studio** | 10 | Livello e ambito richiesti rispetto ai tuoi. Percorsi affini contano (Biotecnologie ≈ Biologia ≈ CTF) |
| **Esperienza** | 5 | Anni richiesti rispetto a quelli stimati dal CV |
| **Sede** | 5 | Corrispondenza con la località della ricerca, con il remoto trattato a parte |

**Una regola importante:** se un annuncio non dice nulla su una componente — per esempio non
indica il titolo di studio — quella componente viene **esclusa** e le altre riproporzionate.
Non vieni penalizzato per un requisito che non esiste.

I pesi sono modificabili in **Impostazioni**. Dopo averli cambiati, premi *Salva e ricalcola*.

### Modificare le competenze del profilo

Le competenze dedotte dal curriculum sono un punto di partenza, non una sentenza: dalla
scheda **Curriculum** puoi togliere quelle sbagliate e aggiungere quelle che il documento
non diceva. Il colore indica come vengono usate:

- **verde** — competenza riconosciuta dal dizionario: partecipa al confronto diretto con le
  offerte, che è la componente di punteggio con il peso maggiore;
- **blu** — etichetta libera: contribuisce solo all'affinità testuale, perché il motore non
  può confrontarla con quelle richieste da un annuncio se non le conosce.

Non serve azzeccare la forma esatta: si scrive come viene e il nome canonico lo trova
l'applicazione. *"real time pcr"* diventa **qPCR / Real-time PCR**, *"western blotting"*
diventa **Western blot**, *"spettrometria di massa"* in minuscolo diventa **Spettrometria
di massa**. Dopo *Salva e ricalcola* tutti i punteggi vengono rifatti — ma **i giudizi già
scritti dal modello restano**: costano una chiamata a pagamento ciascuno e riguardano
l'offerta rispetto al profilo, non il conteggio lessicale che qui si rifà. Il punteggio
finale viene rimescolato con la nuova parte lessicale.

### Un profilo senza curriculum

Se non hai il file a portata di mano, il pulsante **Crea un profilo senza curriculum**
genera un profilo vuoto a cui aggiungere le competenze a mano. Il punteggio funziona lo
stesso, basandosi su competenze, ruolo, titolo di studio e sede; sarà però meno preciso,
perché manca il testo del documento su cui si calcola l'affinità complessiva.

### Cosa viene letto dal curriculum

Competenze (dizionario italiano/inglese con forte copertura di laboratorio, analitica,
regolatorio e bioinformatica), titolo di studio e ambito, lingue, aree professionali e anni
di esperienza. Gli anni vengono contati **solo dalle sezioni di esperienza lavorativa**: senza
questo accorgimento gli anni di università si sommerebbero a quelli di lavoro.

Un PDF che è una scansione non contiene testo estraibile: in quel caso esporta il curriculum
in PDF dal documento originale, oppure caricalo in `.docx`.

### Provare il punteggio

Nella scheda **Curriculum**, in fondo, puoi incollare il testo di un annuncio qualsiasi e
vedere come viene valutato, con tutte le componenti in chiaro. È il modo più veloce per
capire se i pesi sono tarati come vuoi.

---

## Notifiche

Un'offerta genera un avviso quando supera la **soglia di notifica** (predefinita: 40%).

- **Telegram** — il canale più affidabile sul telefono: arriva anche ad applicazione chiusa.
  **È il più semplice da configurare.**
- **Notifica di sistema** — attiva. Premi *Attiva notifiche del browser* in Impostazioni la
  prima volta. Funziona quando l'applicazione è aperta o installata.
- **Email** — da configurare nel file `.env`, poi attivare in Impostazioni. Il pulsante
  *Invia email di prova* verifica la configurazione senza aspettare.

I canali sono indipendenti: se uno fallisce, gli altri partono lo stesso e l'errore viene
mostrato solo per quello che non ha funzionato.

### Telegram in tre passi

1. Su Telegram cerca **@BotFather**, invia `/newbot` e segui le istruzioni. Ti restituisce
   un token del tipo `123456789:AA…`: scrivilo in `TELEGRAM_TOKEN` nel file `.env` e riavvia.
2. Apri il bot che hai appena creato e **scrivigli qualcosa** (anche solo "ciao"). Un bot non
   può iniziare una conversazione da solo, quindi questo passaggio è obbligatorio.
3. In **Impostazioni → Telegram** premi *Trova la chat*: l'applicazione ricava il numero dagli
   ultimi messaggi ricevuti dal bot. Scrivilo in `TELEGRAM_CHAT_ID`, riavvia e attiva la
   spunta. *Invia messaggio di prova* conferma che tutto funziona.

Esempio di configurazione con Gmail (serve una *password per le app*, non quella normale
dell'account):

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tuo.indirizzo@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx
SMTP_FROM=tuo.indirizzo@gmail.com
NOTIFY_EMAIL_TO=tuo@indirizzo.it
```

Due protezioni contro le valanghe di messaggi: la stessa offerta non viene ripetuta per
24 ore (regolabile) e ogni ciclo invia al massimo 10 avvisi.

---

## Ogni quanto controlla

L'intervallo predefinito è di **3 minuti**, ma ogni fonte ha anche un proprio intervallo
minimo (10 minuti per le board aziendali, 5 per gli aggregatori): il ciclo interroga solo
le fonti che hanno atteso abbastanza. Dopo un errore l'attesa raddoppia a ogni tentativo
fallito, così una fonte in difficoltà non viene tempestata di richieste.

Vale la pena saperlo: le offerte non vengono pubblicate ogni tre minuti. Un intervallo di
10–15 minuti non ti fa perdere nulla in pratica ed è più rispettoso delle API.

---

## Livello semantico (opzionale, spento)

Attivandolo, un modello linguistico rilegge annuncio e curriculum e corregge il punteggio
lessicale, cogliendo affinità che il confronto per parole non vede — per esempio che chi ha
lavorato su colture cellulari e saggi di vitalità è un candidato sensato per un ruolo di
tossicologia in vitro, anche senza una parola in comune.

Si sceglie il fornitore dalla pagina **Impostazioni**:

| Fornitore | Modello | Come ottenere la chiave |
|---|---|---|
| **Google Gemini** | `gemini-3.7-flash` | Gratuita su [aistudio.google.com/apikey](https://aistudio.google.com/apikey) con un normale account Google, **senza carta di credito**. È l'opzione più accessibile |
| **Anthropic Claude** | `claude-opus-5` | Richiede un'organizzazione Console con fatturazione su platform.claude.com, che è un **servizio separato dall'abbonamento Claude**: se il tuo dominio è gestito da un'organizzazione senza Console, non puoi crearne una da solo |
| **OpenAI o modello locale** | quello che hai | Nessuna chiave se il modello gira sul tuo computer. Vedi qui sotto |

Metti la chiave nel file `.env` (`GEMINI_API_KEY` oppure `ANTHROPIC_API_KEY`), scegli il
fornitore in Impostazioni e spunta *Attiva la valutazione semantica*. La libreria di Gemini
è già installata; per Claude servirebbe `pip install anthropic`.

### Un modello sul proprio computer

La terza voce accetta **qualunque servizio con API compatibile OpenAI**. Serve a far girare
il modello in casa: non costa niente, non richiede alcuna chiave e **il curriculum non esce
dalla macchina** — che su un documento del genere è la ragione migliore per preferirla.

| Servizio | Indirizzo da incollare |
|---|---|
| [Ollama](https://ollama.com) | `http://localhost:11434/v1` |
| [LM Studio](https://lmstudio.ai) | `http://localhost:1234/v1` |
| OpenAI | `https://api.openai.com/v1` — qui la chiave serve |

Indirizzo e chiave si scrivono in **Impostazioni → Credenziali dei servizi**, oppure nel
file `.env` come `OPENAI_BASE_URL` e `OPENAI_API_KEY`. L'indirizzo deve finire con `/v1`.
Non c'è nessuna libreria da installare: l'API è una richiesta HTTP e basta.

Il campo **Modello** elenca i modelli davvero presenti sul servizio, letti da lui: il nome di
un modello locale non si indovina (`llama3.1:8b`, con i due punti e la dimensione) e
sbagliarlo darebbe un `404` che non spiega niente.

**Con Docker attenzione a un dettaglio**: dentro il contenitore `localhost` è il contenitore
stesso, non il tuo computer, quindi un Ollama che gira sull'host non si vede. L'indirizzo
giusto è `http://host.docker.internal:11434/v1`; su Linux serve anche la riga `extra_hosts`
già presente nel `docker-compose.yml`.

**Cosa aspettarsi.** Un modello da 7-8 miliardi di parametri legge un annuncio in qualche
decina di secondi e dà giudizi ragionevoli ma più grossolani di Gemini o Claude, e con
punteggi che tendono a stare in mezzo. Il tempo di attesa è generoso di proposito (tre
minuti), perché sulla CPU un giudizio lungo può richiederli. I modelli che "ragionano" prima
di rispondere funzionano: il blocco di ragionamento viene riconosciuto e scartato.

Il campo **Modello** permette di cambiarlo senza toccare il codice: lasciato vuoto usa il
predefinito del fornitore. Serve perché i nomi dei modelli cambiano spesso.

Il modello viene interpellato **solo** sulle offerte già giudicate promettenti (sopra 30 di
punteggio lessicale) e al massimo 15 per ciclo, così il costo resta prevedibile. Il giudizio
compare nel dettaglio dell'offerta accanto al punteggio lessicale, mai al posto suo. Se la
chiamata fallisce — rete, quota, chiave scaduta — il punteggio lessicale resta valido e il
ciclo prosegue senza errori.

---

## Storico delle candidature

Ogni offerta può essere marcata con uno stato — *Salvata, Candidato, Colloquio, Offerta
ricevuta, Rifiutata, Scartata* — e annotata con note libere. La scheda **Storico** le
raggruppa per stato. Le offerte che compaiono nello storico non vengono mai archiviate
automaticamente, anche quando spariscono dalla fonte.

---

## Installare come applicazione

Nel browser, dal menu, scegli *Installa applicazione* (Chrome ed Edge mostrano anche
un'icona nella barra degli indirizzi). Si apre in una finestra propria, con la sua icona.

Il server deve comunque essere in esecuzione: la PWA è l'interfaccia, non il motore.
Per averlo sempre attivo, metti un collegamento a `Avvia JobSeeker.bat` nella cartella
Esecuzione automatica (`Win+R` → `shell:startup`).

---

## Struttura del progetto

```
JobSeeker/
├── app/
│   ├── main.py            API REST e servizio dell'interfaccia
│   ├── pipeline.py        orchestrazione: scarica, archivia, valuta, notifica
│   ├── scheduler.py       controllo periodico
│   ├── db.py              schema SQLite e accesso ai dati
│   ├── config.py          impostazioni e lettura del file .env
│   ├── providers/         un adapter per famiglia di API
│   │   ├── base.py        modello normalizzato dell'offerta
│   │   ├── ats.py         Greenhouse, Ashby, SmartRecruiters, Workable, Recruitee
│   │   └── aggregators.py Adzuna, The Muse, board remote
│   ├── matching/          motore di compatibilità
│   │   ├── skills.py      dizionario di competenze, ruoli e titoli di studio
│   │   ├── cv_parser.py   lettura del CV e costruzione del profilo
│   │   ├── engine.py      calcolo e scomposizione del punteggio
│   │   └── llm.py         livello semantico opzionale (Gemini, Claude o compatibile OpenAI)
│   ├── notify/            email e avvisi
│   └── static/            interfaccia web e PWA
├── data/                  database e curriculum (non versionati)
└── .env                   credenziali e chiavi
```

### Aggiungere una fonte nuova

Scrivi una sottoclasse di `BaseProvider` in `app/providers/`, implementa `fetch()` e — se la
fonte si può aggiungere incollando un URL — il metodo di classe `detect()`. Poi inseriscila
nell'elenco `PROVIDERS` in `app/providers/__init__.py`: comparirà da sola nell'interfaccia
e nel riconoscimento automatico.

Attenzione a un dettaglio non ovvio: i motori di ricerca dei portali trattano più parole
chiave come una congiunzione, e più termini si aggiungono più il risultato si svuota. Per
questo i provider che filtrano lato server inviano **una richiesta per parola chiave**
(`SearchSpec.query_terms`) invece di concatenarle.

---

I file per la pubblicazione su server:

```
Dockerfile            costruzione dell'immagine
docker-compose.yml    applicazione + Caddy per HTTPS
Caddyfile             dominio e certificato automatico
entrypoint.sh         permessi della cartella dati all'avvio
.env.example          modello di configurazione
```

La cartella `data/` — database, curriculum caricati — non e' versionata: contiene dati
personali, e una volta finiti nella cronologia di git non se ne vanno piu'.

## Diagnostica

In fondo a **Impostazioni** trovi lo stato di ogni fonte e le ultime esecuzioni con gli
eventuali errori. Ogni fonte ha anche un pulsante **Prova** che la interroga subito e mostra
cosa restituisce, senza salvare nulla.

Il segnale a cui prestare attenzione è *"nessun risultato da N controlli"*: significa che la
fonte risponde ma non trova niente di pertinente.

Il pulsante **Prova** distingue i due motivi possibili e li mostra separati: quante offerte
sono state scartate **dal filtro sulla sede** e quante **per le parole chiave**. È la
distinzione che conta, perché il primo caso è quasi sempre una località impostata più stretta
del voluto — una ricerca su "Roma" scarta le offerte di Vimodrone, Pavia, Anagni e Scoppito,
anche se sono esattamente il tipo di posizione che stai cercando. In quel caso togli la
spunta *«scarta le offerte fuori dalla località»* oppure allarga la località a "Italia".

> Attenzione: il **nome** della ricerca non partecipa in alcun modo al filtro. Quattro
> ricerche chiamate diversamente ma con le stesse parole chiave si comportano in modo
> identico: a decidere sono solo parole chiave, esclusioni, località e paese.

**Località e Paese sono due filtri diversi.** La *località* si confronta con la sede scritta
nell'annuncio ("Milano" tiene fuori Torino); il *Paese* con il paese dell'offerta, quando la
fonte lo dichiara. Il Paese vale anche da solo: con località vuota e `IT` restano dentro tutte
le città italiane e ne resta fuori Madrid. Le offerte che il paese non lo dichiarano passano e
vengono giudicate sul testo della sede — meglio una in più da scartare a mano che una buona
buttata via su un'informazione assente. Le posizioni **da remoto** saltano entrambi i
controlli finché la spunta *«accetto posizioni da remoto»* è attiva: è quello che la rende
utile, ed è anche il motivo per cui ogni tanto compare una città estera.
