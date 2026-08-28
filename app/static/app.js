/* JobSeeker — logica dell'interfaccia. Nessuna libreria esterna.
   Parla con gli stessi endpoint della versione precedente: il backend non
   sa che il frontend è cambiato. */
"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

/* ------------------------------------------------------------------ testi */

const T = {
  it: {
    overview: "Riepilogo", jobs: "Offerte", history: "Storico", searches: "Ricerche",
    sources: "Fonti", cv: "Curriculum", settings: "Impostazioni",
    subOverview: "Come sta andando la ricerca in questo momento.",
    subJobs: "Tutte le offerte raccolte dalle fonti, ordinate per compatibilità con il tuo profilo.",
    subHistory: "Le offerte a cui hai assegnato uno stato.",
    subSearches: "Le parole chiave che decidono quali offerte vengono archiviate.",
    subSources: "I portali che JobSeeker interroga a ogni ciclo.",
    subCv: "Il profilo con cui vengono confrontate le offerte.",
    subSettings: "Frequenza dei controlli, notifiche e composizione del punteggio.",
    run: "Controlla ora", running: "Controllo…", toggleSidebar: "Comprimi la barra laterale",
    themeDark: "Passa al tema scuro", themeLight: "Passa al tema chiaro",
    nextIn: "Prossimo controllo fra", paused: "In pausa", offline: "Server non raggiungibile",
    searchPh: "Titolo, azienda, parola nel testo…", cityPh: "Milano, Pavia…",
    allSources: "Tutte le fonti", minMatch: "Match minimo",
    sortScore: "Compatibilità", sortDate: "Data", sortCompany: "Azienda",
    newBadge: "NEW", results: "risultati", result: "risultato", loadMore: "Carica altre offerte",
    emptyJobsTitle: "Nessuna offerta con questi filtri",
    emptyJobsBody: "Abbassa la soglia di compatibilità, allarga la città, oppure premi «Controlla ora» per interrogare subito le fonti.",
    emptyJobsFirst: "Comincia aggiungendo una fonte dalla scheda «Fonti» e una ricerca dalla scheda «Ricerche».",
    clearFilters: "Azzera i filtri", na: "n.d.",
    all: "Tutte", saved: "Salvata", applied: "Candidato", interview: "Colloquio",
    offer: "Offerta ricevuta", rejected: "Rifiutata", discarded: "Scartata",
    emptyHistoryTitle: "Lo storico è vuoto",
    emptyHistoryBody: "Apri un'offerta e assegnale uno stato per tenere traccia delle candidature.",
    edit: "Modifica", delete: "Elimina", cancel: "Annulla", add: "Aggiungi", test: "Prova", runOne: "Controlla",
    active: "Attiva", inactive: "Disattivata", download: "Scarica", activate: "Rendi attivo",
    newSearch: "Nuova ricerca", editSearch: "Modifica ricerca",
    searchHint: "Le parole chiave definiscono cosa cerchi: un'offerta è pertinente se ne contiene almeno una.",
    fName: "Nome della ricerca", fKeywords: "Parole chiave (separate da virgola)",
    fExclude: "Parole da escludere", fLocation: "Località", fCountry: "Paese", fThreshold: "Soglia specifica",
    phName: "Es. Biotecnologo Lombardia", phKeywords: "Biotecnologo, biologia molecolare, laboratorio",
    phExclude: "Stage non retribuito, commerciale", phLocation: "Milano",
    phThreshold: "0 - 100  (vuoto = soglia globale)",
    tRemote: "Accetto posizioni da remoto", tLocFilter: "Scarta le offerte fuori dalla località indicata",
    saveSearch: "Salva ricerca", anywhere: "Ovunque", remoteOk: "Remoto accettato", threshold: "Soglia",
    emptySearchesTitle: "Nessuna ricerca configurata",
    emptySearchesBody: "Senza ricerche vengono archiviate tutte le offerte trovate dalle fonti, senza filtro.",
    confirmDelSearch: "Eliminare questa ricerca?",
    detectTitle: "Aggiungi una fonte dal suo indirizzo",
    detectBody: "Incolla il link della pagina «lavora con noi» di un'azienda. Se usa uno dei sistemi supportati, JobSeeker lo riconosce da solo e interroga l'API ufficiale.",
    detectBtn: "Riconosci", detecting: "Riconoscimento in corso…", addSource: "Aggiungi questa fonte",
    recognisedAs: "Riconosciuta come", needsKeyWarn: "Attenzione: questa fonte richiede una chiave nel file .env.",
    catalogueTitle: "Oppure scegli dall'elenco", configuredSources: "Fonti configurate",
    needsKey: "Richiede una chiave", collected: "offerte raccolte", every: "Ogni",
    emptyProvidersTitle: "Nessuna fonte configurata",
    emptyProvidersBody: "Incolla qui sopra il link di una board aziendale, oppure scegli una fonte dall'elenco.",
    confirmDelProvider: "Eliminare questa fonte? Le offerte che ha raccolto verranno rimosse.",
    querying: "Interrogazione in corso…", available: "offerte disponibili", relevant: "pertinenti",
    rejLocation: "scartate dal filtro sulla sede", rejKeywords: "senza le parole chiave",
    noDescription: "(senza descrizione)", noLocation: "sede n.d.",
    modalCancel: "Annulla", modalTest: "Prova senza salvare", modalSave: "Aggiungi la fonte",
    modalUpdate: "Salva le modifiche", modalInterval: "Ogni quanto controllarla (minuti)",
    optional: "Facoltativo", modalNoFields: "Questa fonte non richiede parametri.",
    modalKeyWarn: "Questa fonte richiede una chiave nel file .env per funzionare.",
    modalFromUrl: "Oppure compila dall'indirizzo", modalFill: "Ricava i campi dall'indirizzo",
    modalFilled: "Campi compilati dall'indirizzo.", modalName: "Nome della fonte", modalEnabled: "Fonte attiva",
    wdSearch: "Cerca l'azienda per nome", wdFind: "Cerca il portale",
    wdNote: "Molte aziende mettono davanti a Workday un sito con il proprio marchio, che non rivela l'indirizzo sottostante. Questa ricerca lo trova.",
    wdFound: "Scegli quale portale usare:", fillFirst: "Compila",
    dropTitle: "Trascina qui il curriculum",
    dropBody: "PDF, DOCX o TXT. Il file resta sul tuo computer: viene letto in locale per estrarre competenze e anni di esperienza.",
    dropBrowse: "scegli dal disco", reading: "Lettura di",
    manualCv: "Crea un profilo senza curriculum",
    manualBody: "Non hai un curriculum a portata di mano? Puoi dichiarare le competenze a mano: il punteggio funziona lo stesso, basandosi su quelle invece che sul testo del documento.",
    manualPrompt: "Come vuoi chiamare questo profilo?", manualDefault: "Il mio profilo",
    addSkillPh: "Aggiungi una competenza… (es. HPLC, GMP, colture cellulari)",
    tagLegend: "In verde le competenze riconosciute dal motore, che partecipano al confronto con le offerte. In blu le etichette libere, che contribuiscono solo all'affinità testuale.",
    noTags: "Nessuna competenza: aggiungine almeno una.",
    years: "Anni di esperienza", saveRescore: "Salva e ricalcola",
    manualTag: "Compilato a mano", uploadedAgo: "caricato", createdAgo: "creato",
    noDegree: "titolo non indicato", noLangs: "lingue non indicate", yearsShort: "anni di esperienza",
    emptyCvTitle: "Nessun profilo",
    emptyCvBody: "Carica un curriculum oppure creane uno a mano: senza, le offerte vengono raccolte ma non ricevono un punteggio di compatibilità.",
    confirmDelCv: "Eliminare questo profilo?",
    testTitle: "Prova il punteggio",
    testBody: "Incolla un annuncio per vedere come viene calcolata la compatibilità con il profilo attivo.",
    testTitlePh: "Ricercatore Junior — Biologia Molecolare", testDescPh: "Incolla qui la descrizione…",
    compute: "Calcola compatibilità", pasteFirst: "Incolla il testo di un annuncio",
    gGeneral: "Controllo automatico",
    gGeneralNote: "Ogni quanto JobSeeker interroga le fonti e quanto insiste con gli avvisi.",
    gNotify: "Notifiche",
    gNotifyNote: "Telegram è il canale più affidabile sul telefono: arriva anche ad applicazione chiusa.",
    sInterval: "Intervallo tra i controlli",
    sIntervalHelp: "In secondi. Sotto i 60 secondi le fonti iniziano a limitare le richieste.",
    sThreshold: "Soglia di notifica", sMaxCycle: "Massimo avvisi per ciclo",
    sCooldown: "Non ripetere lo stesso avviso per", sCooldownHelp: "Ore.",
    sRetention: "Archivia le offerte dopo", sRetentionHelp: "Giorni.",
    sDesktop: "Notifica di sistema", sDesktopHelp: "Solo quando l'applicazione è aperta.",
    sEmail: "Notifica via email", sEmailTo: "Indirizzo destinatario", sTelegram: "Notifica su Telegram",
    askPerm: "Attiva notifiche del browser", permOk: "Notifiche del browser attivate",
    permNo: "Permesso negato: le notifiche di sistema resteranno disattivate",
    guideEmail: "Come attivare le notifiche via email",
    guideTelegram: "Come attivare le notifiche su Telegram",
    testEmail: "Invia email di prova", findChat: "Trova la chat", testTelegram: "Invia messaggio di prova",
    weightsTitle: "Peso delle componenti",
    learnedTitle: "Cosa ho imparato dai tuoi scarti",
    learnedNote: "Ogni offerta che metti fra gli scarti, con il motivo, insegna cosa non proporti. Il motivo conta: scartare per «troppa esperienza» non vuol dire che quel settore non ti interessi.",
    learnedEmpty: "Nessuna offerta scartata finora. Scegli «Scartata» su un'offerta e indica perché: da lì si comincia.",
    learnedNeed: "Il riconoscimento per somiglianza si accende a {n} scarti motivati dal contenuto (ruolo, settore, requisiti, studi). Ne hai {have}.",
    learnedReady: "Riconoscimento per somiglianza attivo su {have} scarti motivati dal contenuto e {kept} offerte tenute.",
    learnedReasons: "Motivi che hai indicato",
    learnedTerms: "Tratti che ora segnalano un'offerta da scartare",
    learnedTermsHelp: "Il numero è su quanti scarti si regge. Se uno è sbagliato, toglilo: non verrà più usato.",
    learnedIgnored: "Tratti che hai escluso",
    learnedRestore: "rimetti",
    learnedRemoved: "Tratto escluso",
    learnedEmphasis: "Criteri che ora pesano di più",
    discardWhy: "Perché la scarti?",
    discardWhyHelp: "Facoltativo. Serve a non riproporti offerte simili.",
    weightsNote: "Quanto ciascun fattore incide sulla percentuale finale. Una componente che l'annuncio non permette di valutare viene esclusa e le altre vengono riproporzionate.",
    weight_skills: "Competenze", weight_similarity: "Affinità complessiva", weight_title: "Ruolo",
    weight_education: "Titolo di studio", weight_experience: "Esperienza", weight_location: "Sede",
    weightsSum: "Somma dei pesi", rescored: "offerte ricalcolate",
    llmTitle: "Livello semantico",
    llmNote: "Un modello linguistico rilegge annuncio e curriculum e corregge il punteggio lessicale, cogliendo le affinità che il confronto per parole non vede. Richiede una chiave nel file .env.",
    llmModel: "Modello", llmModelDefault: "Predefinito del fornitore:",
    llmEnable: "Attiva la valutazione semantica", llmWeight: "Peso del giudizio del modello",
    llmFloor: "Valuta solo sopra un punteggio lessicale di", llmMax: "Massimo valutazioni per ciclo",
    ready: "Pronto", noKey: "Chiave mancante", keyPresent: "Chiave presente",
    keyFrom: "Chiave da", intoEnv: "nel file .env come", library: "libreria",
    diagTitle: "Diagnostica", diagRuns: "Ultime esecuzioni",
    dSource: "Fonte", dKind: "Tipo", dJobs: "Offerte", dState: "Stato", dFails: "Errori di fila",
    dWhen: "Quando", dOutcome: "Esito", dFound: "Trovate", dNew: "Nuove", dError: "Errore",
    neverRun: "mai eseguita", ok: "ok", error: "errore",
    topMatches: "Migliori corrispondenze", seeAll: "Vedi tutte",
    pipeline: "Candidature", activity: "Attività recente",
    statJobs: "Offerte in archivio", statNew: "Nuove nelle 24 ore", statAvg: "Match medio", statApps: "Candidature",
    aboveThreshold: "sopra la soglia di notifica", awaiting: "in attesa di riscontro",
    onProfile: "sul profilo attivo", noProfile: "nessun profilo attivo",
    noApps: "Nessuna candidatura. Apri un'offerta e assegnale uno stato per seguirla da qui.",
    noActivity: "Nessuna attività. Premi «Controlla ora» per interrogare subito le fonti.",
    openPosting: "Apri l'offerta", statusPlaceholder: "— stato candidatura —",
    backToNotifications: "Torna alle notifiche",
    removeStatus: "Togli dallo storico", scoreBreakdown: "Come è composto il punteggio",
    notEvaluable: "non valutabile", skillsSection: "Competenze",
    matchedSkills: "Competenze in comune", missingSkills: "Richieste non rilevate",
    bonusSkills: "Tue competenze affini",
    notes: "Note personali", notesPh: "Promemoria, contatti, data del colloquio…", saveNotes: "Salva note",
    description: "Descrizione", noDescriptionLong: "Nessuna descrizione disponibile da questa fonte.",
    jobDetail: "Dettaglio offerta", notifications: "Notifiche",
    notificationsBody: "Offerte che hanno superato la soglia di compatibilità impostata.",
    clearAll: "Svuota l'elenco", noNotifications: "Nessuna notifica",
    clearAllDone: "{n} notifiche cancellate",
    noNotificationsBody: "Compariranno qui le offerte sopra la soglia di compatibilità che hai impostato.",
    missing: "Manca", remote: "Da remoto", posted: "pubblicata", weightLbl: "peso", lexical: "lessicale",
    justNow: "Poco fa", minsAgo: "min fa", hoursAgo: "ore fa", daysAgo: "giorni fa", yesterday: "ieri",
    savedOk: "Impostazione salvata", notesSaved: "Note salvate", markedAs: "Segnata come",
    removedFromHistory: "Rimossa dallo storico", searchDeleted: "Ricerca eliminata",
    searchCreated: "Ricerca creata", searchUpdated: "Ricerca aggiornata", nameFirst: "Dai un nome alla ricerca",
    sourceAdded: "Fonte aggiunta", sourceUpdated: "Fonte aggiornata", sourceDeleted: "Fonte eliminata",
    profileSaved: "Profilo salvato", profileCreated: "Profilo creato: ora aggiungi le tue competenze",
    profileDeleted: "Profilo eliminato", profileActivated: "Profilo attivato, ricalcolo in corso…",
    cvParsed: "Curriculum analizzato", skillsFound: "competenze riconosciute",
    jobsRescored: "offerte rivalutate", dupSkill: "Questa competenza c'era già",
    urlFirst: "Incolla un indirizzo", back: "Collegamento al server ripristinato",
    bootFailed: "Avvio non riuscito", providersRun: "fonti interrogate", newJobs: "offerte nuove",
    byEmail: "per email", onTelegram: "su Telegram",
    cvHint: "Carica un curriculum dalla scheda «Curriculum» per attivare i punteggi di compatibilità.",
    chatFound: "Chat trovata",
  },
  en: {
    overview: "Overview", jobs: "Jobs", history: "Pipeline", searches: "Searches",
    sources: "Sources", cv: "Profile", settings: "Settings",
    subOverview: "How the search is doing right now.",
    subJobs: "Every posting collected from your sources, ranked by match with your profile.",
    subHistory: "Postings you have given a status to.",
    subSearches: "The keywords that decide which postings get stored.",
    subSources: "The boards JobSeeker queries on every cycle.",
    subCv: "The profile every posting is compared against.",
    subSettings: "Check frequency, notifications and score composition.",
    run: "Check now", running: "Checking…", toggleSidebar: "Collapse sidebar",
    themeDark: "Switch to dark theme", themeLight: "Switch to light theme",
    nextIn: "Next check in", paused: "Paused", offline: "Server unreachable",
    searchPh: "Title, company, any word…", cityPh: "Milan, Pavia…",
    allSources: "All sources", minMatch: "Min. match",
    sortScore: "Match", sortDate: "Date", sortCompany: "Company",
    newBadge: "NEW", results: "results", result: "result", loadMore: "Load more postings",
    emptyJobsTitle: "No postings match these filters",
    emptyJobsBody: "Lower the match threshold, widen the city, or hit “Check now” to query the sources right away.",
    emptyJobsFirst: "Start by adding a source under “Sources” and a search under “Searches”.",
    clearFilters: "Clear filters", na: "n/a",
    all: "All", saved: "Saved", applied: "Applied", interview: "Interview",
    offer: "Offer received", rejected: "Rejected", discarded: "Discarded",
    emptyHistoryTitle: "The pipeline is empty",
    emptyHistoryBody: "Open a posting and give it a status to track your applications.",
    edit: "Edit", delete: "Delete", cancel: "Cancel", add: "Add", test: "Test", runOne: "Run",
    active: "Active", inactive: "Paused", download: "Download", activate: "Make active",
    newSearch: "New search", editSearch: "Edit search",
    searchHint: "Keywords define what you are looking for: a posting is relevant if it contains at least one of them.",
    fName: "Search name", fKeywords: "Keywords (comma separated)",
    fExclude: "Excluded words", fLocation: "Location", fCountry: "Country", fThreshold: "Custom threshold",
    phName: "E.g. Biotechnologist Lombardy", phKeywords: "Biotechnologist, molecular biology, lab",
    phExclude: "Unpaid internship, sales", phLocation: "Milan",
    phThreshold: "0 - 100  (empty = global threshold)",
    tRemote: "Accept remote positions", tLocFilter: "Drop postings outside the given location",
    saveSearch: "Save search", anywhere: "Anywhere", remoteOk: "Remote accepted", threshold: "Threshold",
    emptySearchesTitle: "No searches configured",
    emptySearchesBody: "Without searches every posting the sources return gets stored, unfiltered.",
    confirmDelSearch: "Delete this search?",
    detectTitle: "Add a source from its URL",
    detectBody: "Paste a company careers page link. If it runs on a supported system, JobSeeker recognises it and queries the official API.",
    detectBtn: "Detect", detecting: "Detecting…", addSource: "Add this source",
    recognisedAs: "Recognised as", needsKeyWarn: "Note: this source needs a key in your .env file.",
    catalogueTitle: "Or pick from the catalogue", configuredSources: "Configured sources",
    needsKey: "Needs an API key", collected: "postings collected", every: "Every",
    emptyProvidersTitle: "No sources configured",
    emptyProvidersBody: "Paste a company board link above, or pick a source from the catalogue.",
    confirmDelProvider: "Delete this source? The postings it collected will be removed.",
    querying: "Querying…", available: "postings available", relevant: "relevant",
    rejLocation: "dropped by the location filter", rejKeywords: "without the keywords",
    noDescription: "(no description)", noLocation: "location n/a",
    modalCancel: "Cancel", modalTest: "Test without saving", modalSave: "Add source",
    modalUpdate: "Save changes", modalInterval: "Check interval (minutes)",
    optional: "Optional", modalNoFields: "This source needs no parameters.",
    modalKeyWarn: "This source needs a key in your .env file to work.",
    modalFromUrl: "Or fill in from a URL", modalFill: "Derive the fields from the URL",
    modalFilled: "Fields filled in from the URL.", modalName: "Source name", modalEnabled: "Source active",
    wdSearch: "Search the company by name", wdFind: "Find the portal",
    wdNote: "Many companies put a white-labelled site in front of Workday that hides the underlying address. This search finds it.",
    wdFound: "Pick which portal to use:", fillFirst: "Fill in",
    dropTitle: "Drop your résumé here",
    dropBody: "PDF, DOCX or TXT. The file stays on your machine: it is parsed locally to extract skills and years of experience.",
    dropBrowse: "pick from disk", reading: "Reading",
    manualCv: "Create a profile without a résumé",
    manualBody: "No résumé at hand? You can declare your skills by hand: the score works just the same, based on those instead of the document text.",
    manualPrompt: "What should this profile be called?", manualDefault: "My profile",
    addSkillPh: "Add a skill… (e.g. HPLC, GMP, cell culture)",
    tagLegend: "Green tags are skills the engine recognises and uses in the comparison. Blue tags are free labels that only feed textual similarity.",
    noTags: "No skills yet: add at least one.",
    years: "Years of experience", saveRescore: "Save and rescore",
    manualTag: "Filled in by hand", uploadedAgo: "uploaded", createdAgo: "created",
    noDegree: "degree not stated", noLangs: "languages not stated", yearsShort: "years of experience",
    emptyCvTitle: "No profile",
    emptyCvBody: "Upload a résumé or create one by hand: without it, postings are collected but get no match score.",
    confirmDelCv: "Delete this profile?",
    testTitle: "Try the score",
    testBody: "Paste a posting to see how the match against the active profile is computed.",
    testTitlePh: "Junior Researcher — Molecular Biology", testDescPh: "Paste the description here…",
    compute: "Compute match", pasteFirst: "Paste a posting first",
    gGeneral: "Automatic checks",
    gGeneralNote: "How often JobSeeker queries the sources, and how insistent the alerts are.",
    gNotify: "Notifications",
    gNotifyNote: "Telegram is the most reliable channel on a phone: it arrives even with the app closed.",
    sInterval: "Interval between checks",
    sIntervalHelp: "In seconds. Below 60 seconds sources start rate-limiting.",
    sThreshold: "Notification threshold", sMaxCycle: "Max alerts per cycle",
    sCooldown: "Do not repeat an alert for", sCooldownHelp: "Hours.",
    sRetention: "Archive postings after", sRetentionHelp: "Days.",
    sDesktop: "System notification", sDesktopHelp: "Only while the app is open.",
    sEmail: "Email notification", sEmailTo: "Recipient address", sTelegram: "Telegram notification",
    askPerm: "Enable browser notifications", permOk: "Browser notifications enabled",
    permNo: "Permission denied: system notifications will stay off",
    guideEmail: "How to turn on email notifications",
    guideTelegram: "How to turn on Telegram notifications",
    testEmail: "Send a test email", findChat: "Find the chat", testTelegram: "Send a test message",
    weightsTitle: "Score component weights",
    learnedTitle: "What I learned from your rejects",
    learnedNote: "Every offer you discard, with a reason, teaches what not to show you. The reason matters: discarding for “too much experience” does not mean that field is of no interest.",
    learnedEmpty: "No discarded offers yet. Pick “Discarded” on an offer and say why: that is where it starts.",
    learnedNeed: "Similarity matching switches on at {n} discards about content (role, field, requirements, studies). You have {have}.",
    learnedReady: "Similarity matching active on {have} content-based rejects and {kept} kept offers.",
    learnedReasons: "Reasons you gave",
    learnedTerms: "Traits that now flag an offer to discard",
    learnedTermsHelp: "The number is how many rejects it rests on. If one is wrong, drop it: it will not be used again.",
    learnedIgnored: "Traits you excluded",
    learnedRestore: "restore",
    learnedRemoved: "Trait excluded",
    learnedEmphasis: "Criteria that now weigh more",
    discardWhy: "Why are you discarding it?",
    discardWhyHelp: "Optional. It keeps similar offers from coming back.",
    weightsNote: "How much each factor moves the final percentage. A component a posting cannot support is dropped and the rest are re-proportioned.",
    weight_skills: "Skills", weight_similarity: "Overall similarity", weight_title: "Role",
    weight_education: "Education", weight_experience: "Experience", weight_location: "Location",
    weightsSum: "Sum of weights", rescored: "postings rescored",
    llmTitle: "Semantic layer",
    llmNote: "A language model re-reads the posting and the résumé and corrects the lexical score, catching affinities a word-by-word comparison misses. Requires a key in the .env file.",
    llmModel: "Model", llmModelDefault: "Provider default:",
    llmEnable: "Enable semantic evaluation", llmWeight: "Weight of the model's judgement",
    llmFloor: "Only evaluate above a lexical score of", llmMax: "Max evaluations per cycle",
    ready: "Ready", noKey: "Key missing", keyPresent: "Key present",
    keyFrom: "Key from", intoEnv: "into .env as", library: "library",
    diagTitle: "Diagnostics", diagRuns: "Latest runs",
    dSource: "Source", dKind: "Kind", dJobs: "Postings", dState: "State", dFails: "Failures in a row",
    dWhen: "When", dOutcome: "Outcome", dFound: "Found", dNew: "New", dError: "Error",
    neverRun: "never run", ok: "ok", error: "error",
    topMatches: "Best matches", seeAll: "See all",
    pipeline: "Applications", activity: "Recent activity",
    statJobs: "Postings stored", statNew: "New in 24 hours", statAvg: "Average match", statApps: "Applications",
    aboveThreshold: "above the notification threshold", awaiting: "awaiting a reply",
    onProfile: "on the active profile", noProfile: "no active profile",
    noApps: "No applications yet. Open a posting and give it a status to track it from here.",
    noActivity: "No activity yet. Hit “Check now” to query the sources right away.",
    openPosting: "Open posting", statusPlaceholder: "— application status —",
    backToNotifications: "Back to notifications",
    removeStatus: "Remove from pipeline", scoreBreakdown: "How the score breaks down",
    notEvaluable: "not evaluable", skillsSection: "Skills",
    matchedSkills: "Shared skills", missingSkills: "Requirements not found",
    bonusSkills: "Your related skills",
    notes: "Personal notes", notesPh: "Reminders, contacts, interview date…", saveNotes: "Save notes",
    description: "Description", noDescriptionLong: "No description available from this source.",
    jobDetail: "Job detail", notifications: "Notifications",
    notificationsBody: "Postings that cleared the match threshold you set.",
    clearAll: "Clear the list", noNotifications: "No notifications",
    clearAllDone: "{n} notifications deleted",
    noNotificationsBody: "Postings above the match threshold you set will show up here.",
    missing: "Missing", remote: "Remote", posted: "posted", weightLbl: "weight", lexical: "lexical",
    justNow: "Just now", minsAgo: "min ago", hoursAgo: "h ago", daysAgo: "d ago", yesterday: "yesterday",
    savedOk: "Setting saved", notesSaved: "Notes saved", markedAs: "Marked as",
    removedFromHistory: "Removed from the pipeline", searchDeleted: "Search deleted",
    searchCreated: "Search created", searchUpdated: "Search updated", nameFirst: "Name the search first",
    sourceAdded: "Source added", sourceUpdated: "Source updated", sourceDeleted: "Source deleted",
    profileSaved: "Profile saved", profileCreated: "Profile created: now add your skills",
    profileDeleted: "Profile deleted", profileActivated: "Profile activated, rescoring…",
    cvParsed: "Résumé parsed", skillsFound: "skills recognised",
    jobsRescored: "postings re-evaluated", dupSkill: "That skill is already there",
    urlFirst: "Paste a URL", back: "Connection to the server restored",
    bootFailed: "Startup failed", providersRun: "sources queried", newJobs: "new postings",
    byEmail: "by email", onTelegram: "on Telegram",
    cvHint: "Upload a résumé under “Profile” to switch on match scores.",
    chatFound: "Chat found",
  },
};

const ICONS = {
  overview: "M4 4h7v7H4zM13 4h7v4h-7zM13 10h7v10h-7zM4 13h7v7H4z",
  jobs: "M3 8h18v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1zM8 8V6a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2",
  history: "M8 4H6a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2M9 4h6v2H9zM9 13l2 2 4-4",
  searches: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14M16.5 16.5L21 21",
  sources: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18M3 12h18M12 3c2.5 2.5 3.8 5.6 3.8 9S14.5 18.5 12 21M12 3C9.5 5.5 8.2 8.6 8.2 12s1.3 6.5 3.8 9",
  cv: "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M9 13h6M9 17h4",
  settings: "M4 7h10M18 7h2M4 17h4M12 17h8M14 4v6M8 14v6",
  spark: "M12 3l2.2 5.3L20 9.6l-4.2 3.8 1.1 5.6L12 16.3 7.1 19l1.1-5.6L4 9.6l5.8-1.3z",
  target: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M12 11.4a.6.6 0 1 0 0 1.2.6.6 0 0 0 0-1.2",
  check: "M4 12.5l5 5L20 6.5",
  cross: "M5.5 5.5l13 13M18.5 5.5l-13 13",
  sun: "M12 4.5v-2M12 21.5v-2M4.5 12h-2M21.5 12h-2M6.7 6.7L5.3 5.3M18.7 18.7l-1.4-1.4M6.7 17.3l-1.4 1.4M18.7 5.3l-1.4 1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8",
  moon: "M20 14.2A8.2 8.2 0 0 1 9.8 4 8.5 8.5 0 1 0 20 14.2Z",
  upload: "M12 16V4M7.5 8.5L12 4l4.5 4.5M4 16v2.5A1.5 1.5 0 0 0 5.5 20h13a1.5 1.5 0 0 0 1.5-1.5V16",
  trash: "M4 7h16M9 7V5h6v2M6.5 7l1 13h9l1-13M10 11v5M14 11v5",
  chevron: "M7 10l5 5 5-5",
  chevronRight: "M9 5l7 7-7 7",
  bell: "M12 3a5.5 5.5 0 0 0-5.5 5.5v3.2L5 15.5h14l-1.5-3.8V8.5A5.5 5.5 0 0 0 12 3ZM10 18.5a2 2 0 0 0 4 0",
  external: "M8 5h11v11M19 5L6 18",
};

const VIEWS = ["overview", "jobs", "history", "searches", "sources", "cv", "settings"];
const STATUSES = ["saved", "applied", "interview", "offer", "rejected", "discarded"];
// Stati per cui ha senso chiedere il motivo: sono quelli da cui l'app impara.
const STATI_NEGATIVI = ["discarded", "rejected"];
const WEIGHT_KEYS = ["weight_skills", "weight_similarity", "weight_title", "weight_education", "weight_experience", "weight_location"];

/* Ripiego usato solo finché il backend non ha risposto con l'elenco vero.
   I modelli disponibili dipendono dalla chiave, quindi un elenco scritto qui
   non può essere accurato: viene sostituito da /api/llm/models appena arriva.
   Le chiavi corrispondono ai nomi dei fornitori usati dal backend. */
const LLM_MODELS = {
  gemini: ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.5-pro"],
  claude: ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"],
};

/* ------------------------------------------------------------------ stato */

const state = {
  view: "jobs",
  // Da dove si e' aperto il dettaglio: se valorizzato, la X torna li' invece
  // di chiudere tutto. Contiene la funzione che ridisegna il pannello padre.
  ritorno: null,
  notifiche: [],
  reasonsCatalogue: [],
  feedback: null,
  pendingReason: null,
  lang: "it",
  collapsed: false,
  jobs: { items: [], total: 0, offset: 0, limit: 30 },
  filters: { q: "", city: "", minScore: 0, provider: "", sort: "score" },
  providers: [],
  searches: [],
  catalogue: [],
  cvs: [],
  skills: [],
  cvTags: {},
  settings: {},
  meta: { smtp: {}, telegram: {}, llm: {} },
  diagnostics: null,
  appFilter: "",
  form: {},
  detected: null,
  guide: null,
  dd: null,
  status: null,
  nextRunAt: null,
  offline: false,
  notifiedIds: new Set(),
  overview: null,
  testResult: null,
};

const t = (k) => T[state.lang][k] ?? k;

/* ------------------------------------------------------------------- rete */

async function api(path, options = {}) {
  const opts = { headers: {}, ...options };
  if (opts.body && !(opts.body instanceof FormData)) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.body);
  }
  const response = await fetch(path, opts);
  const isJson = (response.headers.get("content-type") || "").includes("json");
  const payload = isJson ? await response.json() : await response.text();
  if (!response.ok) throw new Error((payload && payload.error) || `Errore ${response.status}`);
  return payload;
}

/* --------------------------------------------------------------- utilità */

const esc = (v) => String(v ?? "")
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

const svg = (path, size = 16, extra = "") =>
  `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor"
    stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" ${extra}><path d="${path}"></path></svg>`;

function toast(message, kind = "") {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.innerHTML = `<span class="mark">${svg(kind === "bad" ? ICONS.cross : ICONS.check, 10, 'stroke-width="3.6"')}</span><span>${esc(message)}</span>`;
  $("#toasts").append(el);
  setTimeout(() => { el.style.opacity = "0"; }, 3400);
  setTimeout(() => el.remove(), 3800);
}

const ringColor = (v) => (v >= 70 ? "var(--ok)" : v >= 45 ? "var(--wn)" : "var(--tx5)");

function scoreRing(score, size = "md") {
  if (score === null || score === undefined) {
    return `<div class="score ${size} na" style="background:var(--ln4)"><i>${t("na")}</i></div>`;
  }
  const v = Math.round(score);
  return `<div class="score ${size}" style="background:conic-gradient(${ringColor(v)} ${v * 3.6}deg, var(--ln4) 0)"><i>${v}%</i></div>`;
}

function timeAgo(iso) {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 90) return t("justNow");
  if (diff < 3600) return `${Math.round(diff / 60)} ${t("minsAgo")}`;
  if (diff < 86400) return `${Math.round(diff / 3600)} ${t("hoursAgo")}`;
  const days = Math.round(diff / 86400);
  if (days === 1) return t("yesterday");
  if (days < 31) return `${days} ${t("daysAgo")}`;
  return new Date(iso).toLocaleDateString(state.lang === "it" ? "it-IT" : "en-GB",
    { day: "numeric", month: "short", year: "numeric" });
}

function salaryText(job) {
  const { salary_min: lo, salary_max: hi, currency } = job;
  if (!lo && !hi) return "";
  const fmt = (n) => Math.round(n).toLocaleString(state.lang === "it" ? "it-IT" : "en-GB");
  return lo && hi ? `${fmt(lo)}–${fmt(hi)} ${currency || ""}`.trim() : `${fmt(lo || hi)} ${currency || ""}`.trim();
}

const isFresh = (job) => {
  const seen = job.first_seen_at || job.posted_at;
  return !!seen && Date.now() - new Date(seen).getTime() < 86400000;
};

const jobMeta = (job, extra = []) => [
  job.company, job.remote ? t("remote") : (job.location || job.city), salaryText(job), ...extra,
].filter(Boolean).join("  ·  ");

const splitList = (v) => v.split(",").map((s) => s.trim()).filter(Boolean);
const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
const sliderBg = (v, max = 100) =>
  `background:linear-gradient(90deg,var(--ac) 0 ${(v / max) * 100}%,var(--tr) ${(v / max) * 100}% 100%) center/100% 4px no-repeat`;


/* Voci di ogni menu, conservate al momento del disegno. Servono per poterlo
   riaprire da solo, senza ridisegnare la vista che lo contiene. */
const _vociMenu = {};

function menuHTML(id, options, up) {
  return `<div class="dd-menu ${up ? "up" : ""}">${options.map((o) => `
      <button type="button" data-dd-pick="${id}" data-value="${esc(o.value)}" class="${o.on ? "on" : ""}">
        ${svg(ICONS.check, 12, 'class="check" stroke-width="3"')}
        <span>${esc(o.label)}</span>
        ${o.tint ? `<span class="tint" style="background:${o.tint}"></span>` : ""}
      </button>`).join("")}</div>`;
}

/* Riposizionatore attivo mentre un menu e' aperto. */
let _seguiMenu = null;

/* Chiude qualunque menu aperto agendo solo sul menu, senza toccare la pagina. */
function chiudiMenuAperto() {
  if (_seguiMenu) {
    removeEventListener("scroll", _seguiMenu, true);
    removeEventListener("resize", _seguiMenu);
    _seguiMenu = null;
  }
  document.querySelectorAll(".dd.open").forEach((d) => d.classList.remove("open"));
  document.querySelectorAll(".dd-menu").forEach((m) => m.remove());
}

/* Altezza massima di un menu: oltre questa un elenco non si legge, si subisce.
   Il tetto vale anche su schermi alti, dove lo spazio disponibile e' tanto. */
const MENU_ALTEZZA_MAX = 320;

/* Colloca il menu accanto al proprio pulsante, in coordinate di finestra.
   `naturale` e' l'altezza che avrebbe senza limiti, misurata una volta
   all'apertura: rimisurarla a ogni riposizionamento costringerebbe a
   togliere il limite di altezza, e quel cambio azzera lo scorrimento
   interno rendendo l'elenco impossibile da percorrere. */
function posizionaMenu(menu, trigger, preferisceAlto, naturale) {
  const t = trigger.getBoundingClientRect();
  const margine = 10;
  menu.style.minWidth = `${Math.round(t.width)}px`;

  const sotto = window.innerHeight - t.bottom - margine;
  const sopra = t.top - margine;
  const verso = preferisceAlto
    ? (sopra >= Math.min(naturale, 180) || sopra > sotto)
    : (sotto < Math.min(naturale, 180) && sopra > sotto);
  const spazio = Math.min(MENU_ALTEZZA_MAX, Math.max(140, verso ? sopra : sotto));
  const altezza = Math.min(naturale, spazio);
  menu.style.maxHeight = `${spazio}px`;
  menu.style.top = verso
    ? `${Math.max(margine, t.top - altezza - 6)}px`
    : `${t.bottom + 6}px`;

  const larghezza = menu.offsetWidth;
  let sinistra = t.left;
  if (sinistra + larghezza > window.innerWidth - margine) {
    sinistra = Math.max(margine, window.innerWidth - larghezza - margine);
  }
  menu.style.left = `${Math.max(margine, sinistra)}px`;
}

/* Apre il menu in un livello sopra la pagina, agganciato al proprio pulsante.
   Non viene inserito dentro la scheda: i contenitori hanno `overflow` per
   altri motivi (tabelle che scorrono, pannelli con i bordi arrotondati) e
   ritagliavano il menu appena superava il loro bordo. */
function apriMenuInPosto(trigger, id) {
  const conf = _vociMenu[id];
  if (!conf) return false;
  chiudiMenuAperto();
  trigger.closest(".dd")?.classList.add("open");

  const contenitore = document.createElement("div");
  contenitore.innerHTML = menuHTML(id, conf.options, conf.up);
  const menu = contenitore.firstElementChild;
  menu.classList.add("flottante");
  document.body.appendChild(menu);
  // Altezza senza limiti, misurata subito e poi riusata.
  const naturale = menu.offsetHeight;
  posizionaMenu(menu, trigger, conf.up, naturale);

  // Se la pagina scorre, il menu segue il pulsante invece di restarne staccato.
  _seguiMenu = (e) => {
    // Lo scorrimento *dentro* il menu non lo riguarda: intervenire qui
    // rimetterebbe l'elenco all'inizio a ogni rotella.
    if (e && e.target !== document && menu.contains(e.target)) return;
    if (!menu.isConnected || !trigger.isConnected) { chiudiMenuAperto(); return; }
    // Se il pulsante esce dalla vista, il menu non ha piu' un ancoraggio
    // visibile: seguirlo fuori schermo lo renderebbe solo illeggibile.
    const t = trigger.getBoundingClientRect();
    if (t.bottom < 0 || t.top > window.innerHeight) { state.dd = null; chiudiMenuAperto(); return; }
    posizionaMenu(menu, trigger, conf.up, naturale);
  };
  addEventListener("scroll", _seguiMenu, true);
  addEventListener("resize", _seguiMenu);
  return true;
}

/* Menu a tendina proprio: markup unico, comportamento in delegazione. */
function dropdown(id, label, options, { up = false, minWidth } = {}) {
  _vociMenu[id] = { options, up };
  // Il menu non viene mai scritto qui dentro: lo crea `apriMenuInPosto` in un
  // livello sopra la pagina. Qui resta solo il pulsante.
  return `<div class="dd">
    <button type="button" data-dd="${id}" ${minWidth ? `style="min-width:${minWidth}px"` : ""}>
      <span>${esc(label)}</span>${svg(ICONS.chevron, 13)}
    </button></div>`;
}

/* ------------------------------------------------------------------- tema */

function currentTheme() { return document.documentElement.dataset.theme || "light"; }

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  $('meta[name="theme-color"]').setAttribute("content", theme === "dark" ? "#16161a" : "#f5f5f7");
  $("#theme-path").setAttribute("d", theme === "dark" ? ICONS.sun : ICONS.moon);
  $("#btn-theme").title = theme === "dark" ? t("themeLight") : t("themeDark");
  try { localStorage.setItem("jobseeker-theme", theme); } catch (e) {}
}

/* ------------------------------------------------------------ intelaiatura */

function renderShell() {
  $("#nav").innerHTML = VIEWS.map((v) => {
    const counts = state.status ? state.status.counts || {} : {};
    const badge = { jobs: counts.jobs, history: state.overview ? state.overview.apps : null, sources: counts.providers }[v];
    return `<button type="button" data-view="${v}" class="${state.view === v ? "on" : ""}">
      ${svg(ICONS[v], 17)}
      <span class="label-only">${t(v)}</span>
      ${badge ? `<span class="count label-only">${badge}</span>` : ""}
    </button>`;
  }).join("");

  $("#page-title").textContent = t(state.view);
  $("#page-sub").textContent = t("sub" + cap(state.view));
  $("#run-label").textContent = t("run");
  $("#btn-sidebar").title = t("toggleSidebar");
  $("#btn-bell").title = t("notifications");
  $$("#lang-seg button").forEach((b) => b.classList.toggle("on", b.dataset.lang === state.lang));
  $("#app").classList.toggle("collapsed", state.collapsed);

  // `state.cvs` si popola solo entrando nella scheda Curriculum: fino a quel
  // momento la barra laterale annunciava "Nessun profilo" anche quando ce n'era
  // uno attivo. Lo stato generale lo conosce fin dall'avvio.
  const active = state.cvs.find((c) => c.is_active) || state.status?.active_cv || null;
  $("#me-name").textContent = active ? active.name : (state.lang === "it" ? "Nessun profilo" : "No profile");
  $("#me-sub").textContent = active
    ? (state.lang === "it" ? "Profilo attivo" : "Active profile")
    : (state.lang === "it" ? "Carica un curriculum" : "Upload a résumé");
  $("#me-initials").textContent = active
    ? active.name.split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase()
    : "—";
}

function tickCountdown() {
  const pulse = $("#pulse");
  const text = $("#cycle-text");
  if (state.offline) { pulse.className = "dot idle"; text.textContent = t("offline"); return; }
  if (!state.nextRunAt) { pulse.className = "dot idle"; text.textContent = t("paused"); return; }
  const secs = Math.max(0, Math.round((state.nextRunAt - Date.now()) / 1000));
  pulse.className = secs <= 2 ? "dot busy" : "dot";
  text.textContent = `${t("nextIn")} ${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, "0")}`;
}

/* ------------------------------------------------------------- riepilogo */

async function loadOverview() {
  const [status, jobs, apps, diag, cvs] = await Promise.all([
    api("/api/status"),
    api("/api/jobs?sort=score&limit=200&offset=0&min_score=0"),
    api("/api/applications"),
    api("/api/diagnostics?limit=25").catch(() => ({ runs: [], providers: [] })),
    api("/api/cv").catch(() => []),
  ]);
  state.status = status;
  state.cvs = cvs;

  const items = jobs.items || [];
  const scored = items.filter((j) => j.score !== null && j.score !== undefined);
  const dayAgo = Date.now() - 86400000;
  const fresh = items.filter((j) => new Date(j.posted_at || j.first_seen_at).getTime() > dayAgo);
  const threshold = Number(state.settings.min_match_notify || 0);
  const counts = apps.counts || {};

  state.overview = {
    total: status.counts.jobs,
    fresh: fresh.length,
    freshAbove: fresh.filter((j) => (j.score || 0) >= threshold).length,
    avg: scored.length ? Math.round(scored.reduce((a, j) => a + j.score, 0) / scored.length) : null,
    apps: Object.values(counts).reduce((a, b) => a + b, 0),
    awaiting: (counts.applied || 0) + (counts.interview || 0),
    counts,
    top: [...scored].sort((a, b) => b.score - a.score).slice(0, 5),
    runs: (diag.runs || []).slice(0, 5),
  };
  renderShell();
  renderOverview();
}

function renderOverview() {
  const o = state.overview;
  if (!o) { $("#view").innerHTML = ""; return; }
  const hasCv = state.cvs.some((c) => c.is_active);

  const stats = [
    { icon: ICONS.jobs, label: t("statJobs"), value: o.total, note: "", cls: "" },
    { icon: ICONS.spark, label: t("statNew"), value: o.fresh, note: `${o.freshAbove} ${t("aboveThreshold")}`, cls: "info" },
    { icon: ICONS.target, label: t("statAvg"), value: o.avg === null ? "—" : `${o.avg}%`, note: hasCv ? t("onProfile") : t("noProfile"), cls: hasCv ? "up" : "" },
    { icon: ICONS.check, label: t("statApps"), value: o.apps, note: `${o.awaiting} ${t("awaiting")}`, cls: "" },
  ];

  const fmax = Math.max(1, ...STATUSES.map((k) => o.counts[k] || 0));
  const barColor = { saved: "var(--ac)", applied: "var(--pp)", interview: "var(--wn)", offer: "var(--ok)", rejected: "var(--bad)", discarded: "var(--tx5)" };

  $("#view").innerHTML = `
    <div class="stack" style="gap:26px">
      <div class="stats">
        ${stats.map((s, i) => `<div class="card stat" style="animation-delay:${i * 55}ms">
          <div class="stat-label">${svg(s.icon, 14)}<span>${s.label}</span></div>
          <div class="stat-value">${esc(s.value)}</div>
          ${s.note ? `<div class="stat-note ${s.cls}">${esc(s.note)}</div>` : ""}
        </div>`).join("")}
      </div>

      <div class="split">
        <section class="card list-card">
          <div class="list-head">
            <h2>${t("topMatches")}</h2>
            <button class="link-btn" type="button" data-view="jobs">${t("seeAll")}</button>
          </div>
          ${o.top.length ? o.top.map((j) => `
            <div class="list-row" data-job="${j.id}">
              ${scoreRing(j.score, "xs")}
              <div class="list-row-main">
                <b>${esc(j.title)}</b>
                <span>${esc(jobMeta(j))}</span>
              </div>
              <span>${esc(timeAgo(j.posted_at || j.first_seen_at))}</span>
            </div>`).join("")
          : `<div style="padding:20px"><p class="empty-inline">${t("emptyJobsBody")}</p></div>`}
        </section>

        <div class="stack">
          <section class="panel">
            <h2 style="margin-bottom:14px">${t("pipeline")}</h2>
            ${o.apps ? `<div class="bars">${STATUSES.map((k) => `
              <div class="bar-row">
                <div><span>${t(k)}</span><span>${o.counts[k] || 0}</span></div>
                <div class="bar"><i style="width:${((o.counts[k] || 0) / fmax) * 100}%;background:${barColor[k]}"></i></div>
              </div>`).join("")}</div>`
              : `<p class="empty-inline">${t("noApps")}</p>`}
          </section>

          <section class="panel">
            <h2 style="margin-bottom:12px">${t("activity")}</h2>
            ${o.runs.length ? `<div class="feed">${o.runs.map((r) => {
              const color = r.ok ? "var(--ok)" : "var(--bad)";
              const text = r.ok
                ? `${r.label || t("dSource")}: ${r.fetched} ${t("dFound").toLowerCase()}, ${r.new_jobs} ${t("dNew").toLowerCase()}`
                : `${r.label || t("dSource")}: ${(r.error || t("error")).slice(0, 90)}`;
              return `<div class="feed-item"><span class="dot" style="background:${color}"></span>
                <div><b>${esc(text)}</b><span>${esc(timeAgo(r.started_at))}</span></div></div>`;
            }).join("")}</div>` : `<p class="empty-inline">${t("noActivity")}</p>`}
          </section>
        </div>
      </div>
    </div>`;
}

/* ---------------------------------------------------------------- offerte */

function renderJobsView() {
  const f = state.filters;
  const providerOpts = [{ value: "", label: t("allSources"), on: !f.provider }].concat(
    state.providers.map((p) => ({ value: String(p.id), label: p.label, on: String(p.id) === f.provider }))
  );
  const current = state.providers.find((p) => String(p.id) === f.provider);

  $("#view").innerHTML = `
    <div class="stack">
      <div class="card filters">
        <div class="filters-row">
          <div class="search-wrap">
            ${svg(ICONS.searches, 15, 'stroke-width="1.9"')}
            <input class="input" id="f-q" type="search" placeholder="${t("searchPh")}" value="${esc(f.q)}">
          </div>
          <!-- Larghezza e comportamento in riga li decide il foglio di stile:
               uno stile inline qui impediva al campo di adattarsi quando la
               scheda si restringe e i filtri vanno a capo. -->
          <input class="input filter-city" id="f-city" type="search"
                 placeholder="${t("cityPh")}" value="${esc(f.city)}" list="city-list">
          <datalist id="city-list"></datalist>
          ${dropdown("provider", current ? current.label : t("allSources"), providerOpts)}
        </div>
        <div class="filters-row wrap">
          <div class="slider-wrap">
            <span>${t("minMatch")}</span>
            <input type="range" id="f-score" min="0" max="100" step="1" value="${f.minScore}" style="${sliderBg(f.minScore)}">
            <output id="f-score-out">${f.minScore}%</output>
          </div>
          <div class="seg" id="f-sort">
            ${[["score", "sortScore"], ["date", "sortDate"], ["company", "sortCompany"]].map(([k, l]) =>
              `<button type="button" data-sort="${k}" class="${f.sort === k ? "on" : ""}">${t(l)}</button>`).join("")}
          </div>
          <span class="count-note" id="jobs-count"></span>
        </div>
      </div>
      <div id="jobs-list" class="stack" style="gap:11px"></div>
      <div id="jobs-pager" hidden style="display:flex;justify-content:center">
        <button class="btn" type="button" id="jobs-more">${t("loadMore")}</button>
      </div>
    </div>`;

  wireJobFilters();
  renderJobs();
}

function jobCard(job, index) {
  const b = job.breakdown || {};
  const matched = (b.matched_skills || []).slice(0, 3);
  const missing = (b.missing_skills || []).slice(0, 2);
  return `<article class="card job" data-job="${job.id}" style="animation-delay:${index * 45}ms">
    ${scoreRing(job.score, "md")}
    <div class="job-body">
      <div class="job-head">
        <h3>${esc(job.title)}</h3>
        ${isFresh(job) && !job.app_status ? `<span class="pill new">${t("newBadge")}</span>` : ""}
        ${job.app_status ? `<span class="pill ${job.app_status}">${t(job.app_status)}</span>` : ""}
      </div>
      <div class="job-sub">${esc(jobMeta(job))}</div>
      ${matched.length || missing.length ? `<div class="chips" style="margin-top:3px">
        ${matched.map((s) => `<span class="chip ok">${esc(s)}</span>`).join("")}
        ${missing.map((s) => `<span class="chip miss">${t("missing")} ${esc(s)}</span>`).join("")}
      </div>` : ""}
    </div>
    <div class="job-aside">
      <span>${esc(timeAgo(job.posted_at || job.first_seen_at))}</span>
      <span>${esc(job.provider_label || "")}</span>
    </div>
  </article>`;
}

function renderJobs(append = false) {
  const list = $("#jobs-list");
  if (!list) return;
  if (!append) list.innerHTML = "";

  if (!state.jobs.items.length && !append) {
    const hasProviders = state.providers.length > 0;
    list.innerHTML = `<div class="card empty">
      <div class="glyph">${svg(ICONS.searches, 22, 'stroke-width="1.6"')}</div>
      <b>${hasProviders ? t("emptyJobsTitle") : t("emptyProvidersTitle")}</b>
      <p>${hasProviders ? t("emptyJobsBody") : t("emptyJobsFirst")}</p>
      ${hasProviders ? `<button class="btn" type="button" id="clear-filters">${t("clearFilters")}</button>` : ""}
    </div>`;
    const clear = $("#clear-filters");
    if (clear) clear.onclick = () => {
      state.filters = { q: "", city: "", minScore: 0, provider: "", sort: "score" };
      renderJobsView();
      loadJobs();
    };
    $("#jobs-pager").hidden = true;
    $("#jobs-count").textContent = "";
    return;
  }

  const offset = append ? $$("#jobs-list .job").length : 0;
  list.insertAdjacentHTML("beforeend", state.jobs.items.map((j, i) => jobCard(j, i + (append ? 0 : offset))).join(""));
  const shown = $$("#jobs-list .job").length;
  $("#jobs-pager").hidden = shown >= state.jobs.total;
  $("#jobs-count").textContent = `${state.jobs.total} ${state.jobs.total === 1 ? t("result") : t("results")}`;
}

function wireJobFilters() {
  let debounce;
  const typed = (key) => (e) => {
    state.filters[key] = e.target.value;
    clearTimeout(debounce);
    debounce = setTimeout(() => loadJobs(), 320);
  };
  $("#f-q").oninput = typed("q");
  $("#f-city").oninput = typed("city");
  $("#f-score").oninput = (e) => {
    state.filters.minScore = Number(e.target.value);
    $("#f-score-out").textContent = `${e.target.value}%`;
    e.target.style.cssText = sliderBg(e.target.value);
  };
  $("#f-score").onchange = () => loadJobs();
  $("#f-sort").onclick = (e) => {
    const b = e.target.closest("[data-sort]");
    if (!b) return;
    state.filters.sort = b.dataset.sort;
    $$("#f-sort button").forEach((x) => x.classList.toggle("on", x === b));
    loadJobs();
  };
  $("#jobs-more").onclick = () => { state.jobs.offset += state.jobs.limit; loadJobs(true); };
  loadCities();
}

/* L'elenco delle citta' viene richiesto una volta e poi tenuto da parte: questa
   funzione e' in coda al disegno della vista offerte, che si ripete a ogni
   apertura di un menu a tendina. Senza la memoria, ogni clic sul menu delle
   fonti faceva partire una richiesta al server. */
function riempiElencoCitta() {
  const dl = $("#city-list");
  if (dl && state.cities) {
    dl.innerHTML = state.cities.map((c) => `<option value="${esc(c.name)}">${c.count}</option>`).join("");
  }
}

async function loadCities(forza = false) {
  if (state.cities && !forza) { riempiElencoCitta(); return; }
  try {
    state.cities = await api("/api/cities");
    riempiElencoCitta();
  } catch (e) { /* il completamento è un aiuto, non un requisito */ }
}

async function loadJobs(append = false) {
  if (!append) state.jobs.offset = 0;
  const f = state.filters;
  const params = new URLSearchParams({
    min_score: f.minScore, q: f.q.trim(), location: f.city.trim(), sort: f.sort,
    limit: state.jobs.limit, offset: state.jobs.offset,
  });
  if (f.provider) params.set("provider_id", f.provider);
  const data = await api(`/api/jobs?${params}`);
  state.jobs.items = data.items;
  state.jobs.total = data.total;
  renderJobs(append);
  renderShell();
}

/* ---------------------------------------------------------------- storico */

async function loadApplications() {
  const data = await api(`/api/applications${state.appFilter ? `?status=${state.appFilter}` : ""}`);
  const counts = data.counts || {};
  const total = Object.values(counts).reduce((a, b) => a + b, 0);

  $("#view").innerHTML = `
    <div class="stack">
      <div class="status-filter" id="status-filter">
        ${[{ k: "", l: t("all"), n: total }].concat(STATUSES.map((k) => ({ k, l: t(k), n: counts[k] || 0 })))
          .map((s) => `<button type="button" data-status="${s.k}" class="${state.appFilter === s.k ? "on" : ""}">
            <span>${s.l}</span><span>${s.n}</span></button>`).join("")}
      </div>
      <div class="stack" style="gap:11px">
        ${data.items.length ? data.items.map((a, i) => `
          <article class="card job" data-job="${a.job_id}" style="grid-template-columns:auto 1fr;animation-delay:${i * 45}ms">
            ${scoreRing(a.score, "sm")}
            <div class="job-body">
              <div class="job-head">
                <h3>${esc(a.title)}</h3>
                <span class="pill ${a.status}">${t(a.status)}</span>
              </div>
              <div class="job-sub">${esc([a.company, a.location, a.provider_label].filter(Boolean).join("  ·  "))}</div>
              <div class="chips">
                ${a.applied_at ? `<span class="chip">${t("applied")} ${esc(timeAgo(a.applied_at))}</span>` : ""}
                <span class="chip">${esc(timeAgo(a.updated_at))}</span>
              </div>
              ${a.notes ? `<div class="note-box">${esc(a.notes)}</div>` : ""}
            </div>
          </article>`).join("")
        : `<div class="card empty">
            <div class="glyph">${svg(ICONS.history, 22, 'stroke-width="1.6"')}</div>
            <b>${t("emptyHistoryTitle")}</b><p>${t("emptyHistoryBody")}</p></div>`}
      </div>
    </div>`;

  $("#status-filter").onclick = (e) => {
    const b = e.target.closest("[data-status]");
    if (!b) return;
    state.appFilter = b.dataset.status;
    loadApplications();
  };
}

/* --------------------------------------------------------------- ricerche */

async function loadSearches() {
  state.searches = await api("/api/searches");
  renderSearches();
}

function renderSearches() {
  const f = state.form.search || {};
  const fields = [
    ["name", "fName", "phName"], ["keywords", "fKeywords", "phKeywords"],
    ["exclude", "fExclude", "phExclude"], ["location", "fLocation", "phLocation"],
    ["country", "fCountry", null], ["min", "fThreshold", "phThreshold"],
  ];

  $("#view").innerHTML = `
    <div class="two-col">
      <div class="stack" style="gap:11px">
        ${state.searches.length ? state.searches.map((s, i) => `
          <article class="card search-card" style="animation-delay:${i * 55}ms">
            <div class="search-card-head">
              <h3>${esc(s.name)}</h3>
              <span class="pill ${s.enabled ? "offer" : "discarded"}">${s.enabled ? t("active") : t("inactive")}</span>
              <button class="switch sm ${s.enabled ? "on" : ""}" type="button" data-toggle-search="${s.id}"><i></i></button>
            </div>
            <div class="job-sub">${esc([
              s.location || t("anywhere"), (s.country || "").toUpperCase(),
              s.remote_ok ? t("remoteOk") : "",
              s.min_match !== null && s.min_match !== undefined ? `${t("threshold")} ${s.min_match}%` : "",
            ].filter(Boolean).join("  ·  "))}</div>
            <div class="chips">
              ${(s.keywords || []).map((k) => `<span class="chip info">${esc(k)}</span>`).join("")}
              ${(s.exclude || []).map((k) => `<span class="chip miss">− ${esc(k)}</span>`).join("")}
            </div>
            <div class="card-actions">
              <button class="btn small" type="button" data-edit-search="${s.id}">${t("edit")}</button>
              <button class="btn small danger" type="button" data-del-search="${s.id}">${t("delete")}</button>
            </div>
          </article>`).join("")
        : `<div class="card empty">
            <div class="glyph">${svg(ICONS.searches, 22, 'stroke-width="1.6"')}</div>
            <b>${t("emptySearchesTitle")}</b><p>${t("emptySearchesBody")}</p></div>`}
      </div>

      <section class="panel form-panel">
        <h2>${f.id ? t("editSearch") : t("newSearch")}</h2>
        <p class="lead" style="margin:0">${t("searchHint")}</p>
        ${fields.map(([k, label, ph]) => `<label class="field">
          <span>${t(label)}</span>
          <input class="input" data-sf="${k}" value="${esc(f[k] ?? (k === "country" ? "it" : ""))}"
            placeholder="${ph ? t(ph) : ""}">
        </label>`).join("")}
        <div class="form-toggles">
          ${[["remote_ok", "tRemote"], ["location_filter", "tLocFilter"]].map(([k, label]) => {
            const on = f[k] !== false;
            return `<div class="form-toggle">
              <button class="switch sm ${on ? "on" : ""}" type="button" data-sf-toggle="${k}"><i></i></button>
              <span>${t(label)}</span></div>`;
          }).join("")}
        </div>
        <div style="display:flex;gap:8px">
          <button class="btn primary" type="button" id="save-search" style="flex:1;justify-content:center">${t("saveSearch")}</button>
          ${f.id ? `<button class="btn" type="button" id="cancel-search">${t("cancel")}</button>` : ""}
        </div>
      </section>
    </div>`;

  $$("[data-sf]").forEach((i) => i.oninput = () => {
    state.form.search = { ...(state.form.search || {}), [i.dataset.sf]: i.value };
  });
  $$("[data-sf-toggle]").forEach((b) => b.onclick = () => {
    const k = b.dataset.sfToggle;
    const cur = (state.form.search || {})[k] !== false;
    state.form.search = { ...(state.form.search || {}), [k]: !cur };
    b.classList.toggle("on", !cur);
  });

  $("#save-search").onclick = saveSearch;
  const cancel = $("#cancel-search");
  if (cancel) cancel.onclick = () => { state.form.search = {}; renderSearches(); };

  $$("[data-edit-search]").forEach((b) => b.onclick = () => {
    const s = state.searches.find((x) => x.id === +b.dataset.editSearch);
    if (!s) return;
    state.form.search = {
      id: s.id, name: s.name, keywords: (s.keywords || []).join(", "),
      exclude: (s.exclude || []).join(", "), location: s.location || "",
      country: s.country || "it", min: s.min_match ?? "",
      remote_ok: !!s.remote_ok, location_filter: !!s.location_filter,
    };
    renderSearches();
    $("#main").scrollTo({ top: 0, behavior: "smooth" });
  });

  $$("[data-del-search]").forEach((b) => b.onclick = async () => {
    if (!confirm(t("confirmDelSearch"))) return;
    await api(`/api/searches/${b.dataset.delSearch}`, { method: "DELETE" });
    toast(t("searchDeleted"));
    loadSearches();
  });

  $$("[data-toggle-search]").forEach((b) => b.onclick = async () => {
    const s = state.searches.find((x) => x.id === +b.dataset.toggleSearch);
    await api(`/api/searches/${s.id}`, {
      method: "PUT",
      body: {
        name: s.name, keywords: s.keywords || [], exclude: s.exclude || [],
        location: s.location, country: s.country, remote_ok: !!s.remote_ok,
        location_filter: !!s.location_filter, min_match: s.min_match, enabled: !s.enabled,
      },
    });
    loadSearches();
  });
}

async function saveSearch() {
  const f = state.form.search || {};
  if (!(f.name || "").trim()) { toast(t("nameFirst"), "bad"); return; }
  const body = {
    name: f.name.trim(),
    keywords: splitList(f.keywords || ""),
    exclude: splitList(f.exclude || ""),
    location: (f.location || "").trim(),
    country: ((f.country || "it").trim() || "it").toLowerCase(),
    remote_ok: f.remote_ok !== false,
    location_filter: f.location_filter !== false,
    min_match: f.min === "" || f.min === undefined ? null : Number(f.min),
    enabled: true,
  };
  try {
    await api(f.id ? `/api/searches/${f.id}` : "/api/searches", { method: f.id ? "PUT" : "POST", body });
    toast(f.id ? t("searchUpdated") : t("searchCreated"));
    state.form.search = {};
    loadSearches();
  } catch (e) { toast(e.message, "bad"); }
}

/* ------------------------------------------------------------------ fonti */

async function loadSources() {
  const [providers, catalogue] = await Promise.all([api("/api/providers"), api("/api/providers/catalogue")]);
  state.providers = providers;
  state.catalogue = catalogue;
  renderSources();
  renderShell();
}

const CAT_TINTS = [
  ["var(--ok2)", "var(--ok-ink)"], ["var(--ac5)", "var(--ac-ink)"], ["var(--pp2t)", "var(--pp)"],
  ["var(--wn2)", "var(--wn-ink)"], ["var(--bd3)", "var(--bad-ink)"], ["var(--fl3)", "var(--tx2)"],
];

function renderSources() {
  const d = state.detected;
  $("#view").innerHTML = `
    <div class="stack" style="gap:22px">
      <section class="panel">
        <h2>${t("detectTitle")}</h2>
        <p class="lead">${t("detectBody")}</p>
        <div class="url-row">
          <input class="input" id="p-url" placeholder="https://jobs.ashbyhq.com/nomeazienda">
          <button class="btn primary" type="button" id="p-detect">${t("detectBtn")}</button>
        </div>
        <div id="p-detect-result">${d ? `
          <div class="notice ok spaced">
            <b>${t("recognisedAs")} ${esc(d.label)}</b>
            ${esc(d.description || "")}
            ${d.needs_credentials ? `<div style="margin-top:6px"><b>${t("needsKeyWarn")}</b></div>` : ""}
            <div style="margin-top:12px"><button class="btn small primary" type="button" id="p-confirm">${t("addSource")}</button></div>
          </div>` : ""}</div>
      </section>

      <section>
        <h2 class="section-title">${t("catalogueTitle")}</h2>
        <div class="catalogue">
          ${state.catalogue.map((c, i) => {
            const [tint, fg] = CAT_TINTS[i % CAT_TINTS.length];
            return `<button class="cat" type="button" data-add-kind="${esc(c.kind)}">
              <div class="cat-head">
                <span class="cat-mark" style="background:${tint};color:${fg}">${esc((c.label || "?")[0].toUpperCase())}</span>
                <b>${esc(c.label)}</b>
              </div>
              <p>${esc(c.description || "")}</p>
              <div class="cat-foot">
                <span class="btn small" style="pointer-events:none">${t("add")}</span>
                ${c.needs_credentials ? `<span class="cat-key">${t("needsKey")}</span>` : ""}
              </div>
            </button>`;
          }).join("")}
        </div>
      </section>

      <section>
        <h2 class="section-title">${t("configuredSources")}</h2>
        ${state.providers.length ? `<div class="card provider-list">
          ${state.providers.map((p) => `
            <div class="provider">
              <div>
                <div class="provider-head">
                  <span class="health ${p.health.level}"></span>
                  <b>${esc(p.label)}</b>
                  <span class="provider-kind">${esc(cap(p.kind))}</span>
                </div>
                <div class="job-sub" style="margin-top:5px;white-space:normal">${esc([
                  `${p.total_jobs} ${t("collected")}`,
                  `${t("every")} ${Math.round(p.min_interval_sec / 60)} min`,
                  p.last_run_at ? timeAgo(p.last_run_at) : "",
                ].filter(Boolean).join("  ·  "))}</div>
                <div class="health-msg ${p.health.level}">${esc(p.health.message)}</div>
                <div data-result="${p.id}"></div>
              </div>
              <div class="provider-actions">
                <button class="btn small" type="button" data-edit-provider="${p.id}">${t("edit")}</button>
                <button class="btn small" type="button" data-test-provider="${p.id}">${t("test")}</button>
                <button class="btn small" type="button" data-run-provider="${p.id}">${t("runOne")}</button>
                <button class="switch sm ${p.enabled ? "on" : ""}" type="button" data-toggle-provider="${p.id}"><i></i></button>
                <button class="btn small danger" type="button" data-del-provider="${p.id}">${t("delete")}</button>
              </div>
            </div>`).join("")}
        </div>` : `<div class="card empty">
          <div class="glyph">${svg(ICONS.sources, 22, 'stroke-width="1.6"')}</div>
          <b>${t("emptyProvidersTitle")}</b><p>${t("emptyProvidersBody")}</p></div>`}
      </section>
    </div>`;

  wireSources();
}

function wireSources() {
  const detect = async () => {
    const url = $("#p-url").value.trim();
    if (!url) { toast(t("urlFirst"), "bad"); return; }
    const box = $("#p-detect-result");
    box.innerHTML = `<div class="notice spaced">${t("detecting")}</div>`;
    try {
      const r = await api("/api/providers/detect", { method: "POST", body: { url } });
      if (!r.recognised) { box.innerHTML = `<div class="notice warn spaced">${esc(r.message)}</div>`; return; }
      state.detected = { ...r, url };
      renderSources();
    } catch (e) { box.innerHTML = `<div class="notice bad spaced">${esc(e.message)}</div>`; }
  };
  $("#p-detect").onclick = detect;
  $("#p-url").onkeydown = (e) => { if (e.key === "Enter") detect(); };

  const confirmBtn = $("#p-confirm");
  if (confirmBtn) confirmBtn.onclick = async () => {
    const d = state.detected;
    try {
      await api("/api/providers", { method: "POST", body: { url: d.url, kind: d.kind, config: d.config } });
      toast(t("sourceAdded"));
      state.detected = null;
      await Promise.all([loadSources(), loadJobs()]);
    } catch (e) { toast(e.message, "bad"); }
  };

  $$("[data-add-kind]").forEach((b) => b.onclick = () => openProviderModal(b.dataset.addKind));
  $$("[data-edit-provider]").forEach((b) => b.onclick = () => {
    const p = state.providers.find((x) => x.id === +b.dataset.editProvider);
    if (p) openProviderModal(p.kind, p);
  });

  $$("[data-test-provider]").forEach((b) => b.onclick = async () => {
    const target = $(`[data-result="${b.dataset.testProvider}"]`);
    b.disabled = true;
    target.innerHTML = `<div class="notice" style="margin-top:9px">${t("querying")}</div>`;
    try {
      const r = await api(`/api/providers/${b.dataset.testProvider}/test`, { method: "POST" });
      target.innerHTML = `<div style="margin-top:9px">${previewHtml(r)}</div>`;
    } catch (e) { target.innerHTML = `<div class="notice bad" style="margin-top:9px">${esc(e.message)}</div>`; }
    b.disabled = false;
  });

  $$("[data-run-provider]").forEach((b) => b.onclick = async () => {
    b.disabled = true;
    try {
      const r = await api(`/api/run?provider_id=${b.dataset.runProvider}`, { method: "POST" });
      toast(`${r.fetched} ${t("relevant")}, ${r.new_jobs} ${t("newJobs")}`);
      await Promise.all([loadSources(), loadJobs(), loadStatus()]);
    } catch (e) { toast(e.message, "bad"); }
    b.disabled = false;
  });

  $$("[data-toggle-provider]").forEach((b) => b.onclick = async () => {
    const p = state.providers.find((x) => x.id === +b.dataset.toggleProvider);
    await api(`/api/providers/${p.id}`, { method: "PATCH", body: { enabled: !p.enabled } });
    loadSources();
  });

  $$("[data-del-provider]").forEach((b) => b.onclick = async () => {
    if (!confirm(t("confirmDelProvider"))) return;
    await api(`/api/providers/${b.dataset.delProvider}`, { method: "DELETE" });
    toast(t("sourceDeleted"));
    await Promise.all([loadSources(), loadJobs()]);
  });
}

function previewHtml(r) {
  if (!r.ok) return `<div class="notice bad">${esc(r.error)}</div>`;
  const scarti = [];
  if (r.rejected_location) scarti.push(`${r.rejected_location} ${t("rejLocation")}`);
  if (r.rejected_keywords) scarti.push(`${r.rejected_keywords} ${t("rejKeywords")}`);
  return `<div class="notice ${r.relevant ? "ok" : "warn"}">
      <b>${r.total} ${t("available")}, ${r.relevant} ${t("relevant")}${scarti.length ? ` — ${scarti.join(", ")}` : "."}</b>
      ${(r.sample || []).map((s) => `<div class="sample">• ${esc(s.title)} — ${esc(s.location || t("noLocation"))}
        ${s.has_description === false ? ` <em>${t("noDescription")}</em>` : ""}</div>`).join("")}
    </div>`;
}

/* Modale dei parametri: i campi non sono scritti qui, arrivano dal catalogo
   che ogni provider compila per conto suo. */
function openProviderModal(kind, existing = null) {
  const info = state.catalogue.find((c) => c.kind === kind);
  if (!info) return;
  const fields = info.config_fields || [];
  const cfg = existing ? (existing.config || {}) : {};
  const values = { ...cfg };
  const idx = state.catalogue.indexOf(info);
  const [tint, fg] = CAT_TINTS[idx % CAT_TINTS.length];
  let touched = false;

  const draw = (result = "") => {
    $("#overlay").innerHTML = `
      <div class="modal-scrim">
        <div class="backdrop" data-close-modal></div>
        <div class="modal">
          <div class="modal-head">
            <span class="cat-mark" style="background:${tint};color:${fg}">${esc((info.label || "?")[0].toUpperCase())}</span>
            <div>
              <h2>${existing ? t("modalUpdate") : t("add")} · ${esc(info.label)}</h2>
              <p>${esc(info.description || "")}</p>
            </div>
            <button class="round-x" type="button" data-close-modal>${svg(ICONS.cross, 13, 'stroke-width="2.6"')}</button>
          </div>
          <div class="modal-body">
            ${info.needs_credentials ? `<div class="notice warn">${t("modalKeyWarn")}</div>` : ""}
            ${existing ? `
              <label class="field"><span>${t("modalName")}</span>
                <input class="input" id="pf-label" value="${esc(existing.label)}"></label>
              <div class="form-toggle">
                <button class="switch sm ${existing.enabled ? "on" : ""}" type="button" id="pf-enabled"><i></i></button>
                <span>${t("modalEnabled")}</span>
              </div>` : ""}
            ${kind === "workday" ? `
              <label class="field"><span>${t("wdSearch")}</span>
                <input class="input" id="pf-search" placeholder="thermofisher"></label>
              <div><button class="btn small" type="button" id="pf-find">${t("wdFind")}</button></div>
              <div id="pf-find-msg"></div>
              <p class="legend">${t("wdNote")}</p>` : ""}
            ${info.url_example ? `
              <label class="field"><span>${t("modalFromUrl")} <span class="hint">(${t("optional")})</span></span>
                <input class="input" id="pf-url" placeholder="${esc(info.url_example)}"></label>
              <div><button class="btn small" type="button" id="pf-fill">${t("modalFill")}</button></div>
              <div id="pf-fill-msg"></div>` : ""}
            ${fields.length ? fields.map((f) => `
              <label class="field">
                <span>${esc(f.label)}${f.required ? "" : ` <span class="hint">(${t("optional")})</span>`}</span>
                <input class="input ${touched && f.required && !values[f.name] ? "bad" : ""}"
                  data-pf="${esc(f.name)}" placeholder="${esc(f.placeholder || "")}" value="${esc(values[f.name] || "")}">
                ${f.help ? `<span class="hint">${esc(f.help)}</span>` : ""}
              </label>`).join("")
              : `<div class="notice">${t("modalNoFields")}</div>`}
            <label class="field" style="max-width:220px"><span>${t("modalInterval")}</span>
              <input class="input" id="pf-interval" style="text-align:left"
                value="${Math.round((existing ? existing.min_interval_sec : info.default_interval) / 60)}"></label>
            <div id="pf-result">${result}</div>
          </div>
          <div class="modal-foot">
            <button class="btn" type="button" data-close-modal>${t("modalCancel")}</button>
            <button class="btn" type="button" id="pf-test">${t("modalTest")}</button>
            <button class="btn primary" type="button" id="pf-save">${existing ? t("modalUpdate") : t("modalSave")}</button>
          </div>
        </div>
      </div>`;

    $$("[data-pf]").forEach((i) => i.oninput = () => { values[i.dataset.pf] = i.value; });
    const enabled = $("#pf-enabled");
    if (enabled) enabled.onclick = () => enabled.classList.toggle("on");

    const missing = () => fields.filter((f) => f.required && !(values[f.name] || "").trim()).map((f) => f.label);

    if ($("#pf-find")) {
      const find = async () => {
        const name = $("#pf-search").value.trim();
        if (!name) return;
        const msg = $("#pf-find-msg");
        msg.innerHTML = `<div class="notice">${t("querying")}</div>`;
        try {
          const r = await api("/api/providers/workday/discover", { method: "POST", body: { name } });
          if (!r.ok) { msg.innerHTML = `<div class="notice warn">${esc(r.message)}</div>`; return; }
          msg.innerHTML = `<div class="notice ok"><b>${t("wdFound")}</b>
            <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px">
            ${r.results.map((x, i) => `<button class="btn small" type="button" data-pick="${i}">
              ${esc(x.tenant)}.${esc(x.datacenter)}/${esc(x.site)} — ${x.total}</button>`).join("")}</div></div>`;
          r.results.forEach((x, i) => {
            const b = msg.querySelector(`[data-pick="${i}"]`);
            if (b) b.onclick = () => {
              ["tenant", "datacenter", "site"].forEach((k) => {
                values[k] = x[k];
                const input = $(`[data-pf="${k}"]`);
                if (input) input.value = x[k];
              });
              if (!values.company) {
                values.company = name;
                const c = $('[data-pf="company"]');
                if (c) c.value = name;
              }
            };
          });
        } catch (e) { msg.innerHTML = `<div class="notice bad">${esc(e.message)}</div>`; }
      };
      $("#pf-find").onclick = find;
      $("#pf-search").onkeydown = (e) => { if (e.key === "Enter") find(); };
    }

    if ($("#pf-fill")) {
      $("#pf-fill").onclick = async () => {
        const url = $("#pf-url").value.trim();
        if (!url) return;
        const msg = $("#pf-fill-msg");
        try {
          const r = await api("/api/providers/detect", { method: "POST", body: { url } });
          if (!r.recognised) { msg.innerHTML = `<div class="notice warn">${esc(r.message)}</div>`; return; }
          if (r.kind !== kind) {
            msg.innerHTML = `<div class="notice warn">${esc(r.kind)} ≠ ${esc(info.label)}</div>`;
            return;
          }
          Object.entries(r.config).forEach(([k, v]) => {
            values[k] = v;
            const input = $(`[data-pf="${k}"]`);
            if (input) input.value = v;
          });
          msg.innerHTML = `<div class="notice ok">${t("modalFilled")}</div>`;
        } catch (e) { msg.innerHTML = `<div class="notice bad">${esc(e.message)}</div>`; }
      };
    }

    $("#pf-test").onclick = async () => {
      const gaps = missing();
      if (gaps.length) { touched = true; draw(); toast(`${t("fillFirst")}: ${gaps.join(", ")}`, "bad"); return; }
      $("#pf-result").innerHTML = `<div class="notice">${t("querying")}</div>`;
      try {
        const r = await api("/api/providers/preview", { method: "POST", body: { kind, config: values } });
        $("#pf-result").innerHTML = previewHtml(r);
      } catch (e) { $("#pf-result").innerHTML = `<div class="notice bad">${esc(e.message)}</div>`; }
    };

    $("#pf-save").onclick = async () => {
      const gaps = missing();
      if (gaps.length) { touched = true; draw(); toast(`${t("fillFirst")}: ${gaps.join(", ")}`, "bad"); return; }
      const interval = Math.max(1, Number($("#pf-interval").value) || 10) * 60;
      try {
        if (existing) {
          await api(`/api/providers/${existing.id}`, {
            method: "PATCH",
            body: {
              label: ($("#pf-label").value || "").trim() || existing.label,
              enabled: $("#pf-enabled").classList.contains("on"),
              config: values, min_interval_sec: interval,
            },
          });
          toast(t("sourceUpdated"));
        } else {
          await api("/api/providers", { method: "POST", body: { kind, config: values, min_interval_sec: interval } });
          toast(t("sourceAdded"));
        }
        closeOverlay();
        await Promise.all([loadSources(), loadJobs()]);
      } catch (e) { toast(e.message, "bad"); }
    };
  };

  draw();
}

/* ------------------------------------------------------------- curriculum */

async function loadCv() {
  const [cvs, skills] = await Promise.all([
    api("/api/cv"),
    state.skills.length ? Promise.resolve(state.skills) : api("/api/skills").catch(() => []),
  ]);
  state.cvs = cvs;
  state.skills = skills;
  state.cvTags = {};
  cvs.forEach((c) => { state.cvTags[c.id] = [...(c.skills || []), ...(c.extra_tags || [])]; });
  renderCv();
  renderShell();
}

function tagChips(cvId) {
  const known = new Set(state.skills.map((s) => s.name));
  const all = state.cvTags[cvId] || [];
  if (!all.length) return `<span class="empty-inline">${t("noTags")}</span>`;
  return all.map((tag) => `<span class="chip tag ${known.has(tag) ? "ok" : "info"}">
      <span>${esc(tag)}</span>
      <button class="x" type="button" data-cv="${cvId}" data-tag="${esc(tag)}">
        ${svg(ICONS.cross, 9, 'stroke-width="3.4"')}</button>
    </span>`).join("");
}

function renderCv() {
  const r = state.testResult;
  $("#view").innerHTML = `
    <div class="two-col">
      <div class="stack">
        <div class="dropzone" id="dropzone">
          <input type="file" id="cv-file" accept=".pdf,.docx,.txt,.md" hidden>
          <div class="glyph">${svg(ICONS.upload, 21)}</div>
          <b>${t("dropTitle")}</b>
          <p>${t("dropBody")}</p>
          <p class="legend" id="cv-status"></p>
        </div>

        ${state.cvs.length ? state.cvs.map((c) => {
          const edu = c.education || {};
          return `<article class="panel" data-cvcard="${c.id}">
            <div class="search-card-head">
              <h3>${esc(c.name)}</h3>
              ${c.is_active ? `<span class="pill offer">${t("active")}</span>` : ""}
              ${c.is_manual ? `<span class="pill discarded">${t("manualTag")}</span>` : ""}
            </div>
            <div class="job-sub" style="margin-top:4px;white-space:normal">${esc([
              `${c.is_manual ? t("createdAgo") : t("uploadedAgo")} ${timeAgo(c.uploaded_at)}`,
              (edu.label || t("noDegree")) + ((edu.fields || []).length ? ` — ${edu.fields.join(", ")}` : ""),
              `${c.years_experience} ${t("yearsShort")}`,
              (c.languages || []).join(", ") || t("noLangs"),
            ].join("  ·  "))}</div>

            <div class="chips" style="margin-top:16px" data-tags="${c.id}">${tagChips(c.id)}</div>

            <div class="tag-add">
              <input class="input" list="skill-list" data-newtag="${c.id}" placeholder="${t("addSkillPh")}">
              <button class="btn" type="button" data-addtag="${c.id}">${t("add")}</button>
            </div>
            <p class="legend">${t("tagLegend")}</p>

            <div class="cv-foot">
              <label class="field"><span>${t("years")}</span>
                <input class="input" data-years="${c.id}" value="${c.years_experience}" style="text-align:left"></label>
              <button class="btn primary" type="button" data-savecv="${c.id}">${t("saveRescore")}</button>
              ${c.is_active ? "" : `<button class="btn" type="button" data-activate="${c.id}">${t("activate")}</button>`}
              ${c.is_manual ? "" : `<a class="btn" href="/api/cv/${c.id}/file" target="_blank" rel="noopener">${t("download")}</a>`}
              <button class="btn danger" type="button" data-delcv="${c.id}">${t("delete")}</button>
            </div>
          </article>`;
        }).join("") : `<div class="card empty">
          <div class="glyph">${svg(ICONS.cv, 22, 'stroke-width="1.6"')}</div>
          <b>${t("emptyCvTitle")}</b><p>${t("emptyCvBody")}</p>
          <button class="btn" type="button" id="cv-manual">${t("manualCv")}</button></div>`}

        ${state.cvs.length ? `<div class="panel">
          <p class="lead" style="margin:0 0 12px">${t("manualBody")}</p>
          <button class="btn" type="button" id="cv-manual">${t("manualCv")}</button>
        </div>` : ""}
        <datalist id="skill-list">${state.skills.map((s) =>
          `<option value="${esc(s.name)}">${esc(s.group || "")}</option>`).join("")}</datalist>
      </div>

      <section class="panel form-panel" style="position:static">
        <h2>${t("testTitle")}</h2>
        <p class="lead" style="margin:0">${t("testBody")}</p>
        <input class="input" id="a-title" placeholder="${t("testTitlePh")}">
        <textarea class="textarea" id="a-desc" rows="6" placeholder="${t("testDescPh")}"></textarea>
        <button class="btn primary block" type="button" id="a-run">${t("compute")}</button>
        <div id="a-result">${r ? `
          <div style="padding-top:14px;border-top:1px solid var(--ln);animation:expand .3s var(--ease) both">
            <div style="display:flex;align-items:center;gap:14px">
              ${scoreRing(r.score, "lg")}
              <div class="comp-detail" style="margin-top:0;font-size:12.5px;color:var(--tx2)">${esc((r.reasons || [])[0] || "")}</div>
            </div>
            <div class="comps" style="margin-top:16px">${componentRows(r)}</div>
          </div>` : ""}</div>
      </section>
    </div>`;

  wireCv();
}

function wireCv() {
  const dz = $("#dropzone");
  dz.onclick = () => $("#cv-file").click();
  $("#cv-file").onchange = (e) => { if (e.target.files[0]) uploadCv(e.target.files[0]); };
  ["dragenter", "dragover"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("over"); }));
  ["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("over"); }));
  dz.addEventListener("drop", (e) => { if (e.dataTransfer.files[0]) uploadCv(e.dataTransfer.files[0]); });

  const manual = $("#cv-manual");
  if (manual) manual.onclick = async () => {
    const name = prompt(t("manualPrompt"), t("manualDefault"));
    if (name === null) return;
    try {
      await api("/api/cv/manual", { method: "POST", body: { name: name.trim() || t("manualDefault") } });
      toast(t("profileCreated"));
      await Promise.all([loadCv(), loadStatus()]);
    } catch (e) { toast(e.message, "bad"); }
  };

  const redraw = (id) => { $(`[data-tags="${id}"]`).innerHTML = tagChips(id); bindRemovals(); };
  const bindRemovals = () => $$("[data-tags] .x").forEach((b) => b.onclick = (e) => {
    e.stopPropagation();
    const id = b.dataset.cv;
    state.cvTags[id] = (state.cvTags[id] || []).filter((x) => x !== b.dataset.tag);
    redraw(id);
  });
  bindRemovals();

  const addTag = async (id) => {
    const input = $(`[data-newtag="${id}"]`);
    const typed = input.value.trim();
    if (!typed) return;
    // La normalizzazione la fa il server, che conosce anche gli alias.
    let value = typed;
    try {
      const res = await api("/api/skills/resolve", { method: "POST", body: { text: typed } });
      if (res.canonical) value = res.canonical;
    } catch (e) { /* senza rete resta l'etichetta digitata */ }
    if ((state.cvTags[id] || []).includes(value)) { toast(t("dupSkill"), "bad"); }
    else state.cvTags[id].push(value);
    input.value = "";
    redraw(id);
    input.focus();
  };
  $$("[data-addtag]").forEach((b) => b.onclick = () => addTag(b.dataset.addtag));
  $$("[data-newtag]").forEach((i) => i.onkeydown = (e) => {
    if (e.key === "Enter") { e.preventDefault(); addTag(i.dataset.newtag); }
  });

  $$("[data-savecv]").forEach((b) => b.onclick = async () => {
    const id = b.dataset.savecv;
    b.disabled = true;
    try {
      const res = await api(`/api/cv/${id}`, {
        method: "PATCH",
        body: { tags: state.cvTags[id] || [], years_experience: Number($(`[data-years="${id}"]`).value) || 0 },
      });
      toast(res.rescored ? `${t("profileSaved")}, ${res.rescored} ${t("rescored")}` : t("profileSaved"));
      await Promise.all([loadCv(), loadStatus()]);
    } catch (e) { toast(e.message, "bad"); }
    b.disabled = false;
  });

  $$("[data-activate]").forEach((b) => b.onclick = async () => {
    await api(`/api/cv/${b.dataset.activate}/activate`, { method: "POST" });
    toast(t("profileActivated"));
    await api("/api/rescore", { method: "POST" });
    await Promise.all([loadCv(), loadStatus()]);
  });

  $$("[data-delcv]").forEach((b) => b.onclick = async () => {
    if (!confirm(t("confirmDelCv"))) return;
    await api(`/api/cv/${b.dataset.delcv}`, { method: "DELETE" });
    toast(t("profileDeleted"));
    loadCv();
  });

  $("#a-run").onclick = async () => {
    const description = $("#a-desc").value.trim();
    if (!description) { toast(t("pasteFirst"), "bad"); return; }
    try {
      state.testResult = await api("/api/analyze", {
        method: "POST", body: { title: $("#a-title").value.trim(), description },
      });
      const title = $("#a-title").value, desc = $("#a-desc").value;
      renderCv();
      $("#a-title").value = title;
      $("#a-desc").value = desc;
    } catch (e) { toast(e.message, "bad"); }
  };
}

async function uploadCv(file) {
  const form = new FormData();
  form.append("file", file);
  $("#cv-status").textContent = `${t("reading")} ${file.name}…`;
  try {
    const res = await api("/api/cv", { method: "POST", body: form });
    toast(`${res.skills.length} ${t("skillsFound")}, ${res.rescored} ${t("jobsRescored")}`);
    await Promise.all([loadCv(), loadStatus()]);
  } catch (e) {
    $("#cv-status").textContent = "";
    toast(e.message, "bad");
  }
}

/* ---------------------------------------------------------- impostazioni */

async function loadFeedback() {
  // Il catalogo dei motivi vive nel server insieme al criterio che ciascuno
  // mette in discussione: duplicarlo qui li farebbe divergere.
  try {
    state.feedback = await api("/api/feedback");
    state.reasonsCatalogue = state.feedback.available_reasons || [];
  } catch (e) {
    state.feedback = null;
  }
  return state.feedback;
}

async function loadSettings(alsoRender = true) {
  const data = await api("/api/settings");
  state.settings = data.settings;
  state.meta = { smtp: data.smtp || {}, telegram: data.telegram || {}, llm: data.llm || {} };
  if (alsoRender && state.view === "settings") {
    state.diagnostics = await api("/api/diagnostics?limit=25").catch(() => null);
    renderSettings();
  }
}

const GUIDES = {
  it: {
    email: [
      "Apri il file <code>.env</code> nella cartella del progetto.",
      "Compila <code>SMTP_HOST</code>, <code>SMTP_USER</code>, <code>SMTP_PASSWORD</code> e <code>SMTP_FROM</code> con i dati del tuo provider di posta. Con Gmail serve una password per le app, non quella dell'account.",
      "Riavvia l'applicazione, poi scrivi l'indirizzo destinatario qui sopra e manda un'email di prova.",
    ],
    telegram: [
      "Su Telegram cerca <b>@BotFather</b>, invia <code>/newbot</code> e segui le istruzioni. Ti restituisce un token: scrivilo in <code>TELEGRAM_TOKEN</code> nel file <code>.env</code> e riavvia l'applicazione.",
      "Apri il bot che hai appena creato e scrivigli qualcosa: un bot non può iniziare la conversazione da solo.",
      "Premi «Trova la chat» qui sotto: il numero lo ricava l'applicazione. Scrivilo in <code>TELEGRAM_CHAT_ID</code> e riavvia.",
    ],
  },
  en: {
    email: [
      "Open the <code>.env</code> file in the project folder.",
      "Fill in <code>SMTP_HOST</code>, <code>SMTP_USER</code>, <code>SMTP_PASSWORD</code> and <code>SMTP_FROM</code> with your mail provider's details. With Gmail you need an app password, not your account password.",
      "Restart the app, then enter the recipient address above and send a test email.",
    ],
    telegram: [
      "On Telegram find <b>@BotFather</b>, send <code>/newbot</code> and follow the prompts. It returns a token: put it in <code>TELEGRAM_TOKEN</code> in the <code>.env</code> file and restart the app.",
      "Open the bot you just created and send it a message: a bot cannot start the conversation itself.",
      "Press “Find the chat” below: the app works out the number. Put it in <code>TELEGRAM_CHAT_ID</code> and restart.",
    ],
  },
};

function appresoHTML() {
  const f = state.feedback;
  if (!f || !f.discarded) return `<p class="vuoto-appreso">${t("learnedEmpty")}</p>`;

  const stato = f.ready
    ? t("learnedReady").replace("{have}", f.topical).replace("{kept}", f.kept)
    : t("learnedNeed").replace("{n}", f.min_discarded).replace("{have}", f.topical);

  const motivi = (f.reasons || []).filter((r) => r.count);
  const enfasi = Object.entries(f.emphasis || {});
  return `
    <p class="stato-appreso">${esc(stato)}</p>
    ${motivi.length ? `<div class="blocco-appreso"><b>${t("learnedReasons")}</b>
      <div class="chips">${motivi.map((r) =>
        `<span class="chip miss">${esc(r.label)} · ${r.count}</span>`).join("")}</div></div>` : ""}
    ${enfasi.length ? `<div class="blocco-appreso"><b>${t("learnedEmphasis")}</b>
      <div class="chips">${enfasi.map(([k, v]) =>
        `<span class="chip info">${esc(t("weight_" + k) || k)} ×${v}</span>`).join("")}</div></div>` : ""}
    ${(f.terms || []).length ? `<div class="blocco-appreso"><b>${t("learnedTerms")}</b>
      <span class="motivi-aiuto">${t("learnedTermsHelp")}</span>
      <div class="chips" style="margin-top:7px">${f.terms.map((x) =>
        `<span class="chip tratto">${esc(x.term)} · ${x.support}<button type="button"
          class="togli" data-drop-trait="${esc(x.key)}" title="${esc(t("learnedTerms"))}">×</button></span>`).join("")}</div></div>` : ""}
    ${(f.excluded || []).length ? `<div class="blocco-appreso"><b>${t("learnedIgnored")}</b>
      <div class="chips">${f.excluded.map((k) =>
        `<span class="chip spento">${esc(k.replace(/^[a-z]:/, ""))}<button type="button"
          class="togli" data-keep-trait="${esc(k)}">${t("learnedRestore")}</button></span>`).join("")}</div></div>` : ""}`;
}


function renderSettings() {
  const s = state.settings;
  const m = state.meta;
  const on = (k) => s[k] === "true" || s[k] === true;

  const numRow = (key, label, help, unit) => `
    <div class="row">
      <div class="row-label"><b>${label}</b>${help ? `<span>${help}</span>` : ""}</div>
      <div class="row-control">
        <input class="input" data-set="${key}" data-type="number" value="${esc(s[key])}">
        ${unit ? `<output>${unit}</output>` : ""}
      </div>
    </div>`;

  const swRow = (key, label, help) => `
    <div class="row">
      <div class="row-label"><b>${label}</b>${help ? `<span>${help}</span>` : ""}</div>
      <div class="row-control">
        <button class="switch ${on(key) ? "on" : ""}" type="button" data-set-toggle="${key}"><i></i></button>
      </div>
    </div>`;

  const guide = (key, title, actions) => `
    <div class="guide ${state.guide === key ? "open" : ""}">
      <button class="guide-head" type="button" data-guide="${key}">
        ${svg(ICONS.chevronRight, 14, 'stroke-width="2.2"')}<span>${title}</span>
      </button>
      ${state.guide === key ? `<div class="guide-body">
        <ol>${GUIDES[state.lang][key].map((li) => `<li>${li}</li>`).join("")}</ol>
        <div class="notice ${key === "email" ? (m.smtp.configured ? "ok" : "warn") : (m.telegram.configured ? "ok" : "warn")}"
             style="margin-top:12px">${key === "email" ? smtpState() : telegramState()}</div>
        <div class="guide-actions">${actions}</div>
      </div>` : ""}
    </div>`;

  const llmCat = m.llm.catalogue || [];
  const activeLlm = llmCat.find((p) => p.name === m.llm.provider) || llmCat[0];
  // L'elenco vero arriva dal backend, che lo chiede al fornitore con la chiave
  // configurata; LLM_MODELS resta solo come ripiego prima della risposta.
  const models = activeLlm
    ? (state.llmModels?.provider === activeLlm.name && state.llmModels.models.length
        ? state.llmModels.models
        : (LLM_MODELS[activeLlm.name] || [activeLlm.model]))
    : [];
  const chosenModel = s.llm_model || (activeLlm ? activeLlm.model : "");

  $("#view").innerHTML = `
    <div class="settings">
      <section>
        <h2 class="group-title">${t("gGeneral")}</h2>
        <p class="group-note">${t("gGeneralNote")}</p>
        <div class="rows">
          ${numRow("poll_interval_sec", t("sInterval"), t("sIntervalHelp"))}
          <div class="row">
            <div class="row-label"><b>${t("sThreshold")}</b></div>
            <div class="row-control">
              <input type="range" min="0" max="100" step="1" data-set="min_match_notify" data-type="range"
                value="${s.min_match_notify}" style="${sliderBg(s.min_match_notify)}">
              <output>${s.min_match_notify}%</output>
            </div>
          </div>
          ${numRow("notify_max_per_cycle", t("sMaxCycle"))}
          ${numRow("notify_cooldown_hours", t("sCooldown"), t("sCooldownHelp"))}
          ${numRow("retention_days", t("sRetention"), t("sRetentionHelp"))}
        </div>
      </section>

      <section>
        <h2 class="group-title">${t("gNotify")}</h2>
        <p class="group-note">${t("gNotifyNote")}</p>
        <div class="rows">
          ${swRow("notify_desktop_enabled", t("sDesktop"), t("sDesktopHelp"))}
          ${swRow("notify_email_enabled", t("sEmail"))}
          <div class="row">
            <div class="row-label"><b>${t("sEmailTo")}</b></div>
            <div class="row-control">
              <input class="input" style="width:230px;text-align:left" data-set="notify_email_to"
                type="email" value="${esc(s.notify_email_to || "")}" placeholder="tua@email.it">
            </div>
          </div>
          ${swRow("notify_telegram_enabled", t("sTelegram"))}
          ${guide("email", t("guideEmail"),
            `<button class="btn small" type="button" id="btn-test-email">${t("testEmail")}</button>
             <button class="btn small" type="button" id="btn-perm">${t("askPerm")}</button>`)}
          ${guide("telegram", t("guideTelegram"),
            `<button class="btn small" type="button" id="btn-tg-chat">${t("findChat")}</button>
             <button class="btn small" type="button" id="btn-tg-test">${t("testTelegram")}</button>
             <div id="telegram-result" style="width:100%"></div>`)}
        </div>
      </section>

      <section>
        <h2 class="group-title">${t("weightsTitle")}</h2>
        <p class="group-note">${t("weightsNote")}</p>
        <div class="rows" style="padding:18px">
          <div class="weights">
            ${WEIGHT_KEYS.map((k) => `<div class="weight">
              <div><span>${t(k)}</span><span data-wout="${k}">${s[k]}</span></div>
              <input type="range" min="0" max="60" step="1" data-w="${k}" value="${s[k]}" style="${sliderBg(s[k], 60)}">
            </div>`).join("")}
          </div>
          <div class="weights-foot">
            <button class="btn primary" type="button" id="btn-rescore">${t("saveRescore")}</button>
            <span id="wsum">${t("weightsSum")}: ${WEIGHT_KEYS.reduce((a, k) => a + Number(s[k]), 0)}</span>
          </div>
        </div>
      </section>

      <section>
        <h2 class="group-title">${t("learnedTitle")}</h2>
        <p class="group-note">${t("learnedNote")}</p>
        <div class="rows" style="padding:18px">${appresoHTML()}</div>
      </section>

      <section>
        <h2 class="group-title">${t("llmTitle")}</h2>
        <p class="group-note">${t("llmNote")}</p>
        <div class="rows">
          ${llmCat.map((p) => `
            <button class="llm-row ${p.name === m.llm.provider ? "on" : ""}" type="button" data-llm="${esc(p.name)}">
              <span class="radio"><i></i></span>
              <span class="llm-main">
                <span><b>${esc(p.label)}</b><span class="chip">${esc(p.model)}</span></span>
                <p>${esc(p.note || "")}</p>
                ${p.available ? "" : `<p>${t("keyFrom")} <b>${esc(p.signup || "")}</b> → ${t("intoEnv")}
                  <code>${esc(p.env_var || "")}</code> · ${t("library")}: <code>${esc(p.install || "")}</code></p>`}
              </span>
              <span class="pill ${p.available ? "offer" : "discarded"}">${p.available ? t("keyPresent") : t("noKey")}</span>
            </button>`).join("")}
          <div class="model-row">
            <div>
              <b>${t("llmModel")}${activeLlm ? ` — ${esc(activeLlm.label)}` : ""}</b>
              <span class="dflt">${t("llmModelDefault")} ${esc(activeLlm ? activeLlm.model : "—")}</span>
            </div>
            ${dropdown("llmmodel", chosenModel || "—",
              models.map((x) => ({ value: x, label: x, on: x === chosenModel })), { up: true })}
          </div>
          ${swRow("llm_enabled", t("llmEnable"))}
          <div class="row">
            <div class="row-label"><b>${t("llmWeight")}</b></div>
            <div class="row-control">
              <input type="range" min="0" max="100" step="1" data-set="llm_weight" data-type="range"
                value="${s.llm_weight}" style="${sliderBg(s.llm_weight)}">
              <output>${s.llm_weight}%</output>
            </div>
          </div>
          ${numRow("llm_min_lexical", t("llmFloor"))}
          ${numRow("llm_max_per_cycle", t("llmMax"))}
        </div>
        <div class="notice ${m.llm.available ? "ok" : ""}" style="margin-top:10px">${
          m.llm.available
            ? `${t("ready")}: ${esc(m.llm.model)}.`
            : esc(state.lang === "it"
              ? `Fornitore non utilizzabile — ${m.llm.reason || ""}. I punteggi vengono calcolati dal motore lessicale, che non ha bisogno di chiavi né di connessione.`
              : `Provider unusable — ${m.llm.reason || ""}. Scores come from the lexical engine, which needs neither a key nor a connection.`)}</div>
      </section>

      <section>
        <h2 class="group-title">${t("diagTitle")}</h2>
        <div class="rows" style="padding:18px">${diagnosticsHtml()}</div>
      </section>
    </div>`;

  wireSettings();
}

function smtpState() {
  const d = state.meta.smtp;
  if (d.configured) return state.lang === "it"
    ? `SMTP configurato: invio da ${esc(d.from)} tramite ${esc(d.host)}.`
    : `SMTP configured: sending from ${esc(d.from)} via ${esc(d.host)}.`;
  return state.lang === "it"
    ? "SMTP non configurato: compila i quattro valori nel file .env e riavvia."
    : "SMTP not configured: fill in the four values in .env and restart.";
}

function telegramState() {
  const tg = state.meta.telegram;
  if (tg.configured) return state.lang === "it"
    ? "Telegram configurato: il bot può scriverti."
    : "Telegram configured: the bot can message you.";
  if (!tg.has_token) return state.lang === "it"
    ? "Manca TELEGRAM_TOKEN nel file .env — comincia dal passo 1."
    : "TELEGRAM_TOKEN missing from .env — start at step 1.";
  return state.lang === "it"
    ? "Token presente, manca TELEGRAM_CHAT_ID — sei al passo 3."
    : "Token present, TELEGRAM_CHAT_ID missing — you are at step 3.";
}

function diagnosticsHtml() {
  const d = state.diagnostics;
  if (!d) return `<p class="empty-inline">${t("noActivity")}</p>`;
  return `
    <table class="diag">
      <thead><tr><th>${t("dSource")}</th><th>${t("dKind")}</th><th>${t("dJobs")}</th>
        <th>${t("dState")}</th><th>${t("dFails")}</th></tr></thead>
      <tbody>${(d.providers || []).map((p) => `<tr>
        <td>${esc(p.label)}</td><td>${esc(cap(p.kind))}</td><td>${p.jobs}</td>
        <td>${esc(p.last_status || t("neverRun"))}</td><td>${p.consecutive_failures || 0}</td></tr>`).join("")}</tbody>
    </table>
    <h2 class="section-title" style="margin:20px 0 8px;font-size:13px">${t("diagRuns")}</h2>
    <table class="diag">
      <thead><tr><th>${t("dSource")}</th><th>${t("dWhen")}</th><th>${t("dOutcome")}</th>
        <th>${t("dFound")}</th><th>${t("dNew")}</th><th>${t("dError")}</th></tr></thead>
      <tbody>${(d.runs || []).slice(0, 12).map((r) => `<tr>
        <td>${esc(r.label || "—")}</td><td>${esc(timeAgo(r.started_at))}</td>
        <td>${r.ok ? t("ok") : t("error")}</td><td>${r.fetched}</td><td>${r.new_jobs}</td>
        <td class="err">${esc((r.error || "").slice(0, 90))}</td></tr>`).join("")}</tbody>
    </table>`;
}

/* Timer dei salvataggi differiti, tenuti fuori dalla funzione perche' la
   pagina delle impostazioni si ridisegna e ricollega i controlli. */
const _attesaSalvataggio = {};

function wireSettings() {
  const save = async (patch, silenzioso = false) => {
    await api("/api/settings", { method: "PUT", body: patch });
    Object.assign(state.settings, patch);
    if (!silenzioso) toast(t("savedOk"));
  };

  // I cursori cambiano valore a ogni passo: con le frecce della tastiera si
  // muovono di un punto per volta, e salvare a ogni scatto riempiva lo schermo
  // di conferme mentre si cercava la cifra desiderata. Si aspetta che il
  // movimento finisca, poi si salva una volta sola.
  const salvaQuandoFermo = (key, valore, dopo) => {
    clearTimeout(_attesaSalvataggio[key]);
    _attesaSalvataggio[key] = setTimeout(() => {
      save({ [key]: valore }).then(dopo).catch((e) => toast(e.message, "bad"));
    }, 700);
  };

  $$("[data-set]").forEach((el) => {
    const key = el.dataset.set;
    if (el.dataset.type === "range") {
      el.oninput = () => {
        el.style.cssText = sliderBg(el.value);
        const out = el.parentElement.querySelector("output");
        if (out) out.textContent = `${el.value}%`;
        salvaQuandoFermo(key, Number(el.value), () => {
          if (key === "min_match_notify") loadStatus();
        });
      };
    } else {
      el.onchange = () => {
        const value = el.dataset.type === "number" ? Number(el.value) : el.value;
        save({ [key]: value }).then(() => { if (key === "poll_interval_sec") loadStatus(); });
      };
    }
  });

  $$("[data-set-toggle]").forEach((b) => b.onclick = async () => {
    const key = b.dataset.setToggle;
    const next = !b.classList.contains("on");
    b.classList.toggle("on", next);
    await save({ [key]: next });
  });

  $$("[data-guide]").forEach((b) => b.onclick = () => {
    state.guide = state.guide === b.dataset.guide ? null : b.dataset.guide;
    renderSettings();
  });

  $$("[data-w]").forEach((el) => el.oninput = () => {
    el.style.cssText = sliderBg(el.value, 60);
    $(`[data-wout="${el.dataset.w}"]`).textContent = el.value;
    const sum = $$("[data-w]").reduce((a, x) => a + Number(x.value), 0);
    $("#wsum").textContent = `${t("weightsSum")}: ${sum}`;
  });

  $("#btn-rescore").onclick = async (e) => {
    const patch = {};
    $$("[data-w]").forEach((x) => { patch[x.dataset.w] = Number(x.value); });
    e.target.disabled = true;
    try {
      await api("/api/settings", { method: "PUT", body: patch });
      Object.assign(state.settings, patch);
      const r = await api("/api/rescore", { method: "POST" });
      toast(`${r.rescored} ${t("rescored")}`);
      if (state.view === "jobs") loadJobs();
    } catch (err) { toast(err.message, "bad"); }
    e.target.disabled = false;
  };

  $$("[data-llm]").forEach((b) => b.onclick = async () => {
    await api("/api/settings", { method: "PUT", body: { llm_provider: b.dataset.llm, llm_model: "" } });
    await loadSettings();
  });

  const testEmail = $("#btn-test-email");
  if (testEmail) testEmail.onclick = async () => {
    const r = await api("/api/notifications/test-email", { method: "POST" });
    toast(r.message, r.ok ? "" : "bad");
  };
  const perm = $("#btn-perm");
  if (perm) perm.onclick = async () => {
    const p = await Notification.requestPermission();
    toast(p === "granted" ? t("permOk") : t("permNo"), p === "granted" ? "" : "bad");
  };
  const tgChat = $("#btn-tg-chat");
  if (tgChat) tgChat.onclick = async () => {
    const box = $("#telegram-result");
    box.innerHTML = `<div class="notice" style="margin-top:8px">${t("querying")}</div>`;
    try {
      const r = await api("/api/notifications/telegram-chat", { method: "POST" });
      box.innerHTML = `<div class="notice ${r.ok ? "ok" : "warn"}" style="margin-top:8px">
        ${r.ok ? `<b>${t("chatFound")}: <code>${esc(r.chat_id)}</code></b>` : ""}${esc(r.message)}</div>`;
    } catch (e) { box.innerHTML = `<div class="notice bad" style="margin-top:8px">${esc(e.message)}</div>`; }
  };
  const tgTest = $("#btn-tg-test");
  if (tgTest) tgTest.onclick = async () => {
    const r = await api("/api/notifications/test-telegram", { method: "POST" });
    toast(r.message, r.ok ? "" : "bad");
  };
}

/* ---------------------------------------------------- dettaglio e notifiche */

function componentRows(breakdown) {
  return (breakdown.components || []).map((c) => `
    <div class="comp ${c.evaluated ? "" : "off"}">
      <div class="comp-head">
        <b>${esc(c.label)}</b>
        <span>${!c.evaluated ? t("notEvaluable")
          : Math.round(c.weight) > 0 ? `${Math.round(c.score)}%  ·  ${t("weightLbl")} ${Math.round(c.weight)}`
          : `${Math.round(c.score)}%`}</span>
      </div>
      <div class="bar"><i style="width:${c.evaluated ? Math.round(c.score) : 0}%;background:${ringColor(c.score || 0)}"></i></div>
      <div class="comp-detail">${esc(c.detail)}</div>
    </div>`).join("");
}

function closeOverlay() {
  $("#overlay").innerHTML = "";
  state.overlayRedraw = null;
  state.pendingJobStatus = null;
  state.pendingReason = null;
  state.ritorno = null;
  state.dd = null;
}

/* Il pulsante in alto a destra chiude, tranne quando si e' entrati nel
   dettaglio da un altro pannello: in quel caso ci riporta indietro. */
function tornaIndietroOChiudi() {
  const indietro = state.ritorno;
  if (!indietro) { closeOverlay(); return; }
  state.ritorno = null;
  state.overlayRedraw = null;
  state.pendingJobStatus = null;
  state.pendingReason = null;
  state.dd = null;
  indietro();
}

async function openJob(id, ritorno) {
  let job;
  try { job = await api(`/api/jobs/${id}`); } catch (e) { toast(e.message, "bad"); return; }
  // I motivi servono qui dentro anche a chi non e' mai passato dalle
  // impostazioni: si leggono una volta sola per sessione.
  if (!state.reasonsCatalogue.length) await loadFeedback();
  state.ritorno = ritorno || null;
  const b = job.breakdown || {};
  const llm = b.llm;

  const draw = () => {
    state.overlayRedraw = draw;
    // Lo stato va riletto a ogni disegno: calcolarlo una volta sola fuori di
    // qui lasciava l'etichetta ferma sul segnaposto anche dopo averne scelto uno.
    const current = job.app_status || "";
    let motiviAttuali = [];
    try { motiviAttuali = JSON.parse(job.app_reasons || "[]"); } catch (e) { motiviAttuali = []; }
    // Aprire un menu ridisegna il pannello, perche' il menu vive nel suo
    // markup. Senza conservare lo scorrimento il pannello risaliva in cima a
    // ogni apertura, e sembrava di averlo ricaricato.
    const scorrimento = document.querySelector("#overlay .drawer")?.scrollTop || 0;
    $("#overlay").innerHTML = `
      <div class="scrim">
        <div class="backdrop" data-close-drawer></div>
        <aside class="drawer">
          <div class="drawer-top">
            <span class="kicker">${t("jobDetail")}</span>
            ${state.ritorno
              ? `<button class="round-x indietro" type="button" data-close-drawer title="${t("backToNotifications")}">
                  ${svg(ICONS.chevronRight, 14, 'stroke-width="2.4"')}</button>`
              : `<button class="round-x" type="button" data-close-drawer>${svg(ICONS.cross, 13, 'stroke-width="2.6"')}</button>`}
          </div>
          <div class="drawer-body">
            <div class="detail-head">
              ${scoreRing(job.score, "lg")}
              <div>
                <h2>${esc(job.title)}</h2>
                <div class="job-sub">${esc(jobMeta(job, [job.provider_label, job.employment_type, job.department]))}</div>
                <div class="chips" style="margin-top:8px">
                  <span class="chip">${t("posted")} ${esc(timeAgo(job.posted_at || job.first_seen_at))}</span>
                </div>
              </div>
            </div>

            <div class="detail-actions">
              <a class="btn primary" href="${esc(job.apply_url || job.url)}" target="_blank" rel="noopener">
                <span>${t("openPosting")}</span>${svg(ICONS.external, 13, 'stroke-width="2.1"')}</a>
              ${dropdown("jobstatus", current ? t(current) : t("statusPlaceholder"),
                // Nessuna voce preselezionata finche' non si sceglie: prima
                // il segnaposto compariva nell'elenco come se fosse lo stato
                // corrente, con tanto di spunta. Per togliere uno stato c'e'
                // gia' il pulsante dedicato qui accanto.
                STATUSES.map((k) => ({ value: k, label: t(k), on: current === k })),
                { minWidth: 200 })}
              ${current ? `<button class="btn small danger" type="button" id="d-remove">${t("removeStatus")}</button>` : ""}
            </div>

            ${b.components ? `<h3>${t("scoreBreakdown")}</h3>
              <div class="comps">${componentRows(b)}</div>` : ""}

            ${llm ? `<div class="llm-box">
              <div class="llm-box-head">
                ${svg(ICONS.spark, 15, 'stroke-width="1.8"')}
                <b>${esc(cap(llm.provider || "modello"))}: ${llm.score}%</b>
                <span class="chip">${t("lexical")} ${llm.lexical_score}%  ·  ${t("weightLbl")} ${llm.weight}%</span>
              </div>
              <p>${esc(llm.reasoning || "")}</p>
              ${(llm.key_matches || []).length || (llm.key_gaps || []).length ? `<ul class="verdetto">
                ${(llm.key_matches || []).map((x) => `<li class="pro">${esc(x)}</li>`).join("")}
                ${(llm.key_gaps || []).map((x) => `<li class="contro">${esc(x)}</li>`).join("")}
              </ul>` : ""}
            </div>` : ""}

            ${(b.matched_skills || []).length ? `<h3>${t("matchedSkills")}</h3>
              <div class="chips">${b.matched_skills.map((x) => `<span class="chip ok">${esc(x)}</span>`).join("")}</div>` : ""}
            ${(b.missing_skills || []).length ? `<h3>${t("missingSkills")}</h3>
              <div class="chips">${b.missing_skills.map((x) => `<span class="chip miss">${esc(x)}</span>`).join("")}</div>` : ""}
            ${(b.bonus_skills || []).length ? `<h3>${t("bonusSkills")}</h3>
              <div class="chips">${b.bonus_skills.slice(0, 10).map((x) => `<span class="chip info">${esc(x)}</span>`).join("")}</div>` : ""}

            <div id="d-reasons" class="motivi" ${STATI_NEGATIVI.includes(current) ? "" : "hidden"}>
              <b>${t("discardWhy")}</b>
              <span class="motivi-aiuto">${t("discardWhyHelp")}</span>
              <div class="chips" style="margin-top:9px">
                ${(state.reasonsCatalogue || []).map((r) => `<button type="button"
                  class="chip scelta ${motiviAttuali.includes(r.key) ? "on" : ""}"
                  data-reason="${esc(r.key)}">${esc(r.label)}</button>`).join("")}
              </div>
            </div>

            <label class="field" style="margin-top:24px">
              <span>${t("notes")}</span>
              <textarea class="textarea" id="d-notes" rows="3" placeholder="${t("notesPh")}">${esc(job.app_notes || "")}</textarea>
            </label>
            <button class="btn small" type="button" id="d-save-notes" style="margin-top:8px">${t("saveNotes")}</button>

            <div class="description">
              <h3 style="margin-top:0">${t("description")}</h3>
              <p>${esc(job.description || t("noDescriptionLong"))}</p>
            </div>
          </div>
        </aside>
      </div>`;

    const pannello = document.querySelector("#overlay .drawer");
    if (pannello && scorrimento) pannello.scrollTop = scorrimento;

    const setStatus = async (status, notes) => {
      if (!status) return;
      // I motivi seguono lo stato: se non e' piu' uno scarto non hanno senso.
      if (!STATI_NEGATIVI.includes(status)) motiviAttuali = [];
      await api(`/api/jobs/${id}/application`, {
        method: "PUT",
        body: { status, notes: notes ?? (($("#d-notes") || {}).value || ""), reasons: motiviAttuali },
      });
      job.app_reasons = JSON.stringify(motiviAttuali);
      toast(`${t("markedAs")} «${t(status)}»`);
      aggiornaStatoInPosto(id, status, job);
    };

    $("#d-save-notes").onclick = async () => {
      await setStatus(job.app_status || "saved");
      toast(t("notesSaved"));
    };
    collegaRimozione(id, job);

    // I motivi dello scarto: si accendono e si spengono, e ogni cambio viene
    // salvato subito. Sono la materia prima di `matching/feedback.py`.
    state.pendingReason = async (chiave, bottone) => {
      const attivo = bottone.classList.toggle("on");
      motiviAttuali = attivo
        ? [...new Set([...motiviAttuali, chiave])]
        : motiviAttuali.filter((x) => x !== chiave);
      try {
        await setStatus(job.app_status || "discarded");
      } catch (e) {
        bottone.classList.toggle("on");
        toast(e.message, "bad");
      }
    };

    // Il menu dello stato vive qui: il click passa dalla delegazione globale.
    // Niente `draw()` in coda: ridisegnare tutto per cambiare una parola
    // faceva sparire e ricomparire il pannello.
    state.pendingJobStatus = async (value) => {
      state.dd = null;
      if (value) return setStatus(value);
      await api(`/api/jobs/${id}/application`, { method: "DELETE" });
      toast(t("removedFromHistory"));
      aggiornaStatoInPosto(id, "", job);
    };
  };

  draw();
}

async function refreshAfterChange() {
  await loadStatus();
  if (state.view === "jobs") loadJobs();
  else if (state.view === "history") loadApplications();
  else if (state.view === "overview") loadOverview();
}

/* Aggiorna solo cio' che lo stato ha cambiato, invece di ricaricare.
   Cambiare stato a un'offerta ridisegnava il pannello e rileggeva l'intera
   lista dal server: due lampi visibili per cambiare una parola. */
function aggiornaStatoInPosto(jobId, stato, job) {
  const dato = ((state.jobs || {}).items || []).find((x) => String(x.id) === String(jobId));
  const precedente = (job ? job.app_status : dato ? dato.app_status : "") || "";
  if (job) job.app_status = stato;
  if (dato) dato.app_status = stato;

  // la pastiglia sulla scheda in elenco
  const testa = document.querySelector(`.card.job[data-job="${jobId}"] .job-head`);
  if (testa) {
    testa.querySelectorAll(".pill").forEach((p) => p.remove());
    if (stato) testa.insertAdjacentHTML("beforeend", `<span class="pill ${stato}">${esc(t(stato))}</span>`);
    else if (job && isFresh(job)) testa.insertAdjacentHTML("beforeend", `<span class="pill new">${t("newBadge")}</span>`);
  }

  // etichetta del menu e pulsante "togli dallo storico" nel pannello
  const trigger = document.querySelector('#overlay [data-dd="jobstatus"] > span');
  if (trigger) trigger.textContent = stato ? t(stato) : t("statusPlaceholder");
  const motivi = document.querySelector("#overlay #d-reasons");
  if (motivi) {
    motivi.hidden = !STATI_NEGATIVI.includes(stato);
    if (motivi.hidden) motivi.querySelectorAll(".chip.scelta.on").forEach((c) => c.classList.remove("on"));
  }
  const azioni = document.querySelector("#overlay .detail-actions");
  const rimuovi = document.querySelector("#overlay #d-remove");
  if (stato && !rimuovi && azioni) {
    azioni.insertAdjacentHTML("beforeend",
      `<button class="btn small danger" type="button" id="d-remove">${t("removeStatus")}</button>`);
    collegaRimozione(jobId, job);
  } else if (!stato && rimuovi) {
    rimuovi.remove();
  }

  // il contatore Storico nella barra laterale, senza interrogare il server
  if (state.overview && typeof state.overview.apps === "number" && !!stato !== !!precedente) {
    state.overview.apps = Math.max(0, state.overview.apps + (stato ? 1 : -1));
    renderShell();
  }

  // Storico e Panoramica elencano proprio le candidature: li' cambiare stato
  // cambia davvero cosa va mostrato, quindi vanno riletti.
  if (state.view === "history") loadApplications();
  else if (state.view === "overview") loadOverview();
}

function collegaRimozione(jobId, job) {
  const remove = document.querySelector("#overlay #d-remove");
  if (!remove) return;
  remove.onclick = async () => {
    await api(`/api/jobs/${jobId}/application`, { method: "DELETE" });
    toast(t("removedFromHistory"));
    closeOverlay();
    aggiornaStatoInPosto(jobId, "", job);
  };
}

async function openNotifications(precaricate) {
  // Tornando indietro dal dettaglio si riusa l'elenco gia' in memoria: una
  // seconda lettura dal server farebbe lampeggiare il pannello per nulla.
  let items = Array.isArray(precaricate) ? precaricate : null;
  if (!items) {
    try { items = await api("/api/notifications?limit=25"); } catch (e) { toast(e.message, "bad"); return; }
  }
  state.notifiche = items;
  state.ritorno = null;

  $("#overlay").innerHTML = `
    <div class="scrim">
      <div class="backdrop" data-close-drawer></div>
      <aside class="drawer">
        <div class="drawer-top">
          <span class="kicker">${t("notifications")}</span>
          <button class="round-x" type="button" data-close-drawer>${svg(ICONS.cross, 13, 'stroke-width="2.6"')}</button>
        </div>
        <div class="drawer-body">
          <div class="notif-head">
            <div>
              <h2>${t("notifications")}</h2>
              <p>${t("notificationsBody")}</p>
            </div>
            ${items.length ? `<button class="btn small danger" type="button" id="n-clear">
              ${svg(ICONS.trash, 13, 'stroke-width="1.9"')}<span>${t("clearAll")}</span></button>` : ""}
          </div>
          ${items.length ? `<div class="notif-list">
            ${items.map((n) => `<div class="notif ${n.seen ? "" : "unseen"}" data-job="${n.job_id}">
              ${scoreRing(n.score, "xs")}
              <div class="list-row-main">
                <b>${esc(n.title)}</b>
                <span>${esc([n.company, n.location, n.channel, timeAgo(n.sent_at)].filter(Boolean).join("  ·  "))}</span>
              </div>
            </div>`).join("")}
          </div>` : `<div class="empty" style="padding:40px 0 0">
            <div class="glyph">${svg(ICONS.bell, 20, 'stroke-width="1.6"')}</div>
            <b>${t("noNotifications")}</b><p>${t("noNotificationsBody")}</p></div>`}
        </div>
      </aside>
    </div>`;

  const clear = $("#n-clear");
  if (clear) clear.onclick = async () => {
    // Il pannello segna gia' tutto come letto quando si apre, quindi un
    // "segna come lette" qui non avrebbe nulla da fare: il pulsante svuota
    // davvero l'elenco, come suggerisce la sua icona.
    // Nessuna richiesta di conferma: si cancella solo il registro degli
    // avvisi, mentre offerte e storico delle candidature restano intatti.
    try {
      const r = await api("/api/notifications", { method: "DELETE" });
      toast(t("clearAllDone").replace("{n}", r.deleted), "ok");
      await loadStatus();
      openNotifications();
    } catch (e) { toast(e.message, "bad"); }
  };

  if (items === precaricate) return;   // ridisegno: niente da rileggere
  await api("/api/notifications/seen", { method: "POST", body: { ids: null } }).catch(() => {});
  loadStatus();
}

/* ------------------------------------------------------- stato e notifiche */

async function loadStatus() {
  const status = await api("/api/status");
  state.status = status;
  state.nextRunAt = status.scheduler.next_run ? new Date(status.scheduler.next_run) : null;

  const count = status.unseen_notifications;
  $("#bell-count").hidden = !count;
  $("#bell-count").textContent = count;
  renderShell();

  if (status.counts.cvs === 0 && !sessionStorage.getItem("cv-hint")) {
    sessionStorage.setItem("cv-hint", "1");
    toast(t("cvHint"));
  }
  await pushDesktopNotifications();
}

async function pushDesktopNotifications() {
  if (typeof Notification === "undefined" || Notification.permission !== "granted") return;
  if (state.settings.notify_desktop_enabled === "false") return;
  const items = await api("/api/notifications?unseen_only=true&limit=5").catch(() => []);
  for (const item of items) {
    if (state.notifiedIds.has(item.id)) continue;
    state.notifiedIds.add(item.id);
    const note = new Notification(`${Math.round(item.score)}% · ${item.title}`, {
      body: `${item.company}${item.location ? " — " + item.location : ""}`,
      icon: "/static/icons/icon-192.png",
      tag: `job-${item.job_id}`,
    });
    note.onclick = () => { window.focus(); openJob(item.job_id); };
  }
}

/* ---------------------------------------------------------------- viste */

const LOADERS = {
  overview: loadOverview,
  jobs: () => { renderJobsView(); return loadJobs(); },
  history: loadApplications,
  searches: loadSearches,
  sources: loadSources,
  cv: loadCv,
  settings: async () => {
    await loadSettings(false);
    // Si disegna subito con quello che c'e'. Diagnostica ed elenco dei modelli
    // arrivano dopo: il secondo richiede un giro fino al fornitore, e aspettarlo
    // prima di mostrare qualcosa lasciava la pagina bianca per un paio di
    // secondi. Quando arrivano, si ridisegna.
    renderSettings();
    const [diag, , modelli] = await Promise.all([
      api("/api/diagnostics?limit=25").catch(() => null),
      // Cambia a ogni offerta scartata: si rilegge a ogni visita.
      loadFeedback(),
      // L'elenco dipende dalla chiave e cambia di rado: si chiede una volta
      // per fornitore, non a ogni visita.
      state.llmModels && state.llmModels.provider === state.settings.llm_provider
        ? Promise.resolve(state.llmModels)
        : api("/api/llm/models").catch(() => null),
    ]);
    state.diagnostics = diag;
    state.llmModels = modelli;
    // Non si ridisegna sotto le dita di chi sta gia' usando la pagina.
    if (state.view === "settings" && !state.dd) renderSettings();
  },
};

async function switchView(view) {
  state.view = view;
  state.dd = null;
  renderShell();
  $("#main").scrollTo({ top: 0 });
  try { await LOADERS[view](); } catch (e) { toast(e.message, "bad"); }
}

/* ------------------------------------------------------------------ avvio */

function wire() {
  document.addEventListener("click", (e) => {
    // menu a tendina
    const trigger = e.target.closest("[data-dd]");
    if (trigger) {
      e.stopPropagation();
      const id = trigger.dataset.dd;
      if (state.dd === id) { state.dd = null; chiudiMenuAperto(); return; }
      state.dd = id;
      if (!apriMenuInPosto(trigger, id)) state.dd = null;
      return;
    }
    const pick = e.target.closest("[data-dd-pick]");
    if (pick) {
      e.stopPropagation();
      // L'attributo e' `data-dd-pick`, che in JavaScript diventa `dataset.ddPick`:
      // leggere `dataset.dd` restituiva sempre undefined, e nessun ramo qui
      // sotto scattava mai. Le voci dei menu si aprivano ma non selezionavano.
      const dd = pick.dataset.ddPick;
      const value = pick.dataset.value;
      state.dd = null;
      chiudiMenuAperto();
      if (dd === "provider") { state.filters.provider = value; renderJobsView(); loadJobs(); }
      else if (dd === "llmmodel") {
        api("/api/settings", { method: "PUT", body: { llm_model: value } })
          .then(() => loadSettings())
          .catch((err) => toast(err.message, "bad"));
      } else if (dd === "jobstatus" && state.pendingJobStatus) { state.pendingJobStatus(value); }
      return;
    }
    // Clic fuori dal menu: basta chiuderlo, senza ricostruire nulla.
    if (state.dd) { state.dd = null; chiudiMenuAperto(); }

    // Il fondale e' il gesto "portami fuori": chiude comunque tutto.
    const chiusura = e.target.closest("[data-close-drawer], [data-close-modal]");
    if (chiusura) {
      if (chiusura.classList.contains("backdrop")) closeOverlay();
      else tornaIndietroOChiudi();
      return;
    }

    const nav = e.target.closest("[data-view]");
    if (nav) { switchView(nav.dataset.view); return; }

    const tratto = e.target.closest("[data-drop-trait], [data-keep-trait]");
    if (tratto) {
      const chiave = tratto.dataset.dropTrait || tratto.dataset.keepTrait;
      const rimetti = !!tratto.dataset.keepTrait;
      api("/api/feedback/excluded", { method: "POST", body: { key: chiave, remove: rimetti } })
        .then((f) => {
          state.feedback = f;
          state.reasonsCatalogue = f.available_reasons || [];
          if (state.view === "settings") renderSettings();
          if (!rimetti) toast(t("learnedRemoved"), "ok");
        })
        .catch((err) => toast(err.message, "bad"));
      return;
    }

    const motivo = e.target.closest("[data-reason]");
    if (motivo && state.pendingReason) { state.pendingReason(motivo.dataset.reason, motivo); return; }

    const avviso = e.target.closest(".notif[data-job]");
    if (avviso) { openJob(+avviso.dataset.job, () => openNotifications(state.notifiche)); return; }

    const card = e.target.closest("[data-job]");
    if (card && !e.target.closest("button, a, input, textarea, .dd")) openJob(+card.dataset.job);
  });

  document.addEventListener("keydown", (e) => {
    // Il primo Esc chiude il menu aperto, il secondo il pannello di dettaglio.
    if (e.key !== "Escape") return;
    if (state.dd) { state.dd = null; chiudiMenuAperto(); return; }
    tornaIndietroOChiudi();
  });

  /* Sotto una certa larghezza la barra laterale non si comprime ma scorre
     fuori dallo schermo: comprimerla a icone lascerebbe comunque 68px sottratti
     a una colonna già stretta. Lo stesso pulsante quindi apre e chiude. */
  const aScomparsa = () => matchMedia("(max-width: 860px)").matches;
  const chiudiMenu = () => $("#app").classList.remove("nav-open");
  $("#nav").addEventListener("click", () => { if (aScomparsa()) chiudiMenu(); });
  $("#overlay").addEventListener("click", chiudiMenu);
  addEventListener("keydown", (e) => { if (e.key === "Escape") chiudiMenu(); });
  addEventListener("resize", () => { if (!aScomparsa()) chiudiMenu(); });

  $("#btn-sidebar").onclick = () => {
    if (aScomparsa()) { $("#app").classList.toggle("nav-open"); return; }
    state.collapsed = !state.collapsed;
    $("#app").classList.toggle("collapsed", state.collapsed);
  };

  $("#btn-theme").onclick = () => applyTheme(currentTheme() === "dark" ? "light" : "dark");
  // niente riferimento diretto: passerebbe l'evento del click come elenco
  $("#btn-bell").onclick = () => openNotifications();

  $("#lang-seg").onclick = (e) => {
    const b = e.target.closest("[data-lang]");
    if (!b || b.dataset.lang === state.lang) return;
    state.lang = b.dataset.lang;
    document.documentElement.lang = state.lang;
    try { localStorage.setItem("jobseeker-lang", state.lang); } catch (err) {}
    applyTheme(currentTheme());
    switchView(state.view);
  };

  $("#me").onclick = () => switchView("cv");

  $("#btn-run").onclick = async () => {
    const button = $("#btn-run");
    button.disabled = true;
    button.querySelector(".spin").hidden = false;
    $("#run-label").textContent = t("running");
    try {
      const r = await api("/api/run", { method: "POST" });
      const parts = [`${r.providers_run} ${t("providersRun")}`, `${r.new_jobs} ${t("newJobs")}`];
      if (r.notify && r.notify.email_sent) parts.push(`${r.notify.email_sent} ${t("byEmail")}`);
      if (r.notify && r.notify.telegram_sent) parts.push(`${r.notify.telegram_sent} ${t("onTelegram")}`);
      toast(parts.join(", "), (r.errors || []).length ? "bad" : "");
      [...(r.errors || []), ...((r.notify && r.notify.errors) || [])].slice(0, 3)
        .forEach((err) => toast(err, "bad"));
      await loadStatus();
      if (LOADERS[state.view]) LOADERS[state.view]();
    } catch (e) { toast(e.message, "bad"); }
    button.disabled = false;
    button.querySelector(".spin").hidden = true;
    $("#run-label").textContent = t("run");
  };
}

/* Ridisegna solo la vista corrente: serve ai menu a tendina, che vivono
   dentro il markup della vista e non hanno uno stato proprio nel DOM. */
function rerenderCurrent() {
  // Un ridisegno sostituisce i pulsanti: un menu aperto resterebbe agganciato
  // a un elemento che non esiste piu'.
  if (state.dd) { state.dd = null; chiudiMenuAperto(); }
  if (state.view === "jobs") { renderJobsView(); renderJobs(); }
  else if (state.view === "settings") renderSettings();
  else if (state.view === "sources") renderSources();
  else if (state.view === "searches") renderSearches();
  else if (state.view === "cv") renderCv();
}

async function boot() {
  try { state.lang = localStorage.getItem("jobseeker-lang") || "it"; } catch (e) {}
  document.documentElement.lang = state.lang;
  applyTheme(currentTheme());
  wire();

  try {
    await loadSettings(false);
    await Promise.all([api("/api/providers").then((p) => { state.providers = p; }), loadStatus()]);
    await switchView("jobs");
  } catch (e) {
    toast(`${t("bootFailed")}: ${e.message}`, "bad");
  }

  setInterval(tickCountdown, 1000);
  // Il polling non deve far esplodere la pagina se il server viene riavviato:
  // si limita a segnalare l'assenza e riprende da solo al ritorno.
  setInterval(async () => {
    try {
      await loadStatus();
      if (state.offline) {
        state.offline = false;
        toast(t("back"));
        if (LOADERS[state.view]) LOADERS[state.view]();
      }
    } catch (e) {
      state.offline = true;
      state.nextRunAt = null;
    }
  }, 30000);

  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
}

boot();
