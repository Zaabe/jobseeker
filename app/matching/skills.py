"""Ontologia delle competenze, dei ruoli e dei titoli di studio.

Il riconoscimento avviene per n-grammi sul testo tokenizzato: ogni alias viene
ridotto alla sua sequenza di token e cercato nel documento. E' piu' preciso di
una ricerca per sottostringa (niente "R" dentro "Roma") e piu' veloce di una
alternanza di espressioni regolari lunga migliaia di voci.

Il campo `weight` misura quanto una competenza e' discriminante: "pcr" o "gmp"
dicono molto piu' di "microsoft office", e il punteggio ne tiene conto.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .text import normalize, normalize_lines, tokenize

# (canonico, gruppo, peso, alias)
SKILL_DEFS: list[tuple[str, str, float, list[str]]] = [
    # --- Biologia molecolare e cellulare ---------------------------------
    ("PCR", "biologia molecolare", 1.8, ["pcr", "reazione a catena della polimerasi", "polymerase chain reaction"]),
    ("qPCR / Real-time PCR", "biologia molecolare", 2.0, ["qpcr", "real time pcr", "realtime pcr", "rt-qpcr", "pcr quantitativa", "quantitative pcr"]),
    ("RT-PCR", "biologia molecolare", 1.9, ["rt-pcr", "rt pcr", "reverse transcription pcr", "retrotrascrizione"]),
    ("Elettroforesi", "biologia molecolare", 1.6, ["elettroforesi", "electrophoresis", "gel di agarosio", "agarose gel"]),
    ("SDS-PAGE", "biologia molecolare", 1.9, ["sds-page", "sds page", "gel di poliacrilammide"]),
    ("Western blot", "biologia molecolare", 1.9, ["western blot", "western blotting", "immunoblot", "immunoblotting"]),
    ("Southern / Northern blot", "biologia molecolare", 1.9, ["southern blot", "northern blot"]),
    ("ELISA", "biologia molecolare", 1.9, ["elisa", "saggio immunoenzimatico", "enzyme linked immunosorbent"]),
    ("Estrazione DNA/RNA", "biologia molecolare", 1.7, ["estrazione del dna", "estrazione dna", "estrazione rna", "dna extraction", "rna extraction", "purificazione acidi nucleici", "nucleic acid extraction"]),
    ("Clonaggio molecolare", "biologia molecolare", 1.9, ["clonaggio", "cloning", "molecular cloning", "clonaggio molecolare", "vettori plasmidici", "plasmid"]),
    ("Trasfezione / Trasformazione", "biologia molecolare", 1.8, ["trasfezione", "transfection", "trasformazione batterica", "bacterial transformation", "elettroporazione", "electroporation"]),
    ("CRISPR", "biologia molecolare", 2.0, ["crispr", "crispr-cas9", "cas9", "editing genomico", "gene editing", "genome editing"]),
    ("Sequenziamento NGS", "biologia molecolare", 2.0, ["ngs", "next generation sequencing", "sequenziamento di nuova generazione", "illumina", "rna-seq", "rnaseq", "whole genome sequencing", "wgs", "exome sequencing"]),
    ("Sequenziamento Sanger", "biologia molecolare", 1.8, ["sanger", "sequenziamento sanger", "sanger sequencing"]),
    ("Colture cellulari", "biologia cellulare", 1.9, ["colture cellulari", "coltura cellulare", "cell culture", "cell cultures", "colture primarie", "primary culture", "linee cellulari", "cell lines"]),
    ("Colture microbiche", "biologia cellulare", 1.7, ["colture batteriche", "bacterial culture", "microbiologia", "microbiology", "terreni di coltura", "fermentazione", "fermentation"]),
    ("Citofluorimetria", "biologia cellulare", 2.0, ["citofluorimetria", "citometria a flusso", "flow cytometry", "facs", "cytometry"]),
    ("Microscopia", "biologia cellulare", 1.7, ["microscopia", "microscopy", "microscopio", "confocale", "confocal", "immunofluorescenza", "immunofluorescence"]),
    ("Immunoistochimica", "biologia cellulare", 1.9, ["immunoistochimica", "immunohistochemistry", "ihc", "istologia", "histology"]),
    ("Saggi di citotossicita'", "biologia cellulare", 1.8, ["citotossicita", "cytotoxicity", "mtt assay", "saggio mtt", "vitalita cellulare", "cell viability"]),
    ("Purificazione proteine", "biochimica", 1.9, ["purificazione proteica", "purificazione delle proteine", "protein purification", "cromatografia di affinita", "affinity chromatography", "his-tag"]),
    ("Espressione proteica", "biochimica", 1.8, ["espressione proteica", "protein expression", "espressione ricombinante", "recombinant protein"]),
    ("Enzimologia", "biochimica", 1.8, ["enzimologia", "enzymology", "cinetica enzimatica", "enzyme kinetics", "saggio enzimatico", "enzyme assay"]),
    ("Spettrofotometria", "analitica", 1.6, ["spettrofotometria", "spectrophotometry", "spettrofotometro", "uv-vis", "nanodrop"]),

    # --- Chimica analitica -----------------------------------------------
    ("HPLC", "analitica", 2.0, ["hplc", "uplc", "cromatografia liquida ad alta prestazione", "high performance liquid chromatography"]),
    ("Cromatografia", "analitica", 1.7, ["cromatografia", "chromatography", "gascromatografia", "gas chromatography", "tlc", "cromatografia su strato sottile"]),
    ("Spettrometria di massa", "analitica", 2.0, ["spettrometria di massa", "mass spectrometry", "lc-ms", "gc-ms", "maldi", "maldi-tof", "ms/ms", "proteomica", "proteomics"]),
    ("NMR", "analitica", 2.0, ["nmr", "risonanza magnetica nucleare", "nuclear magnetic resonance"]),
    ("Titolazione / Chimica analitica", "analitica", 1.5, ["titolazione", "titration", "chimica analitica", "analytical chemistry", "analisi quantitativa"]),

    # --- Qualita', regolatorio, produzione --------------------------------
    ("GMP", "regolatorio", 2.0, ["gmp", "good manufacturing practice", "buone pratiche di fabbricazione", "cgmp", "eu gmp"]),
    ("GLP", "regolatorio", 2.0, ["glp", "good laboratory practice", "buone pratiche di laboratorio"]),
    ("GCP", "regolatorio", 2.0, ["gcp", "good clinical practice", "buona pratica clinica"]),
    ("Quality Assurance", "regolatorio", 1.6, ["quality assurance", "assicurazione qualita", "qa", "sistema qualita", "quality management system", "qms"]),
    ("Quality Control", "regolatorio", 1.6, ["quality control", "controllo qualita", "qc", "controlli di qualita"]),
    ("Affari regolatori", "regolatorio", 2.0, ["affari regolatori", "regulatory affairs", "dossier registrativo", "ctd", "emea", "ema", "fda", "aifa", "autorizzazione all immissione in commercio"]),
    ("Farmacovigilanza", "regolatorio", 2.0, ["farmacovigilanza", "pharmacovigilance", "segnalazione reazioni avverse", "adverse event reporting"]),
    ("Validazione di processo", "regolatorio", 1.9, ["validazione di processo", "process validation", "convalida", "qualifica iq oq pq", "iq oq pq", "validazione metodo", "method validation"]),
    ("CAPA / Deviazioni", "regolatorio", 1.9, ["capa", "azioni correttive", "corrective and preventive action", "deviazioni", "deviation management", "non conformita", "root cause analysis"]),
    ("ISO 9001", "regolatorio", 1.6, ["iso 9001", "iso9001"]),
    ("ISO 13485", "regolatorio", 1.9, ["iso 13485", "iso13485", "dispositivi medici", "medical device", "mdr"]),
    ("ISO 17025", "regolatorio", 1.9, ["iso 17025", "iso17025", "accreditamento laboratorio"]),
    ("HACCP", "regolatorio", 1.7, ["haccp", "sicurezza alimentare", "food safety"]),
    ("Documentazione GxP", "regolatorio", 1.7, ["batch record", "sop", "standard operating procedure", "procedure operative standard", "data integrity", "alcoa"]),
    ("Upstream / Downstream", "produzione", 2.0, ["upstream processing", "downstream processing", "bioprocesso", "bioprocess", "bioreattore", "bioreactor", "scale-up", "scale up"]),
    ("Sterilita' e camere bianche", "produzione", 1.8, ["camera bianca", "cleanroom", "clean room", "asepsi", "aseptic", "sterilita", "sterility"]),
    ("Lean / Six Sigma", "produzione", 1.6, ["lean manufacturing", "six sigma", "kaizen", "5s", "miglioramento continuo", "continuous improvement"]),

    # --- Clinico e ricerca ------------------------------------------------
    ("Studi clinici", "clinico", 1.9, ["studi clinici", "clinical trial", "clinical trials", "sperimentazione clinica", "cro", "clinical research"]),
    ("Data management clinico", "clinico", 1.9, ["clinical data management", "ecrf", "crf", "edc", "redcap"]),
    ("Biostatistica", "dati", 1.9, ["biostatistica", "biostatistics", "analisi statistica", "statistical analysis", "test statistici", "anova", "regressione"]),
    ("Redazione scientifica", "ricerca", 1.6, ["medical writing", "redazione scientifica", "pubblicazioni scientifiche", "scientific publications", "peer review", "stesura protocolli"]),
    ("Progettazione sperimentale", "ricerca", 1.7, ["disegno sperimentale", "experimental design", "design of experiments", "doe"]),
    ("Gestione progetti di ricerca", "ricerca", 1.6, ["grant", "bandi di ricerca", "horizon europe", "prin", "fondi di ricerca", "research funding"]),

    # --- Bioinformatica e dati -------------------------------------------
    ("Bioinformatica", "bioinformatica", 2.0, ["bioinformatica", "bioinformatics", "biologia computazionale", "computational biology"]),
    ("BLAST / Allineamento", "bioinformatica", 1.9, ["blast", "allineamento di sequenze", "sequence alignment", "clustal", "bowtie", "bwa"]),
    ("R", "dati", 1.7, ["r", "rstudio", "linguaggio r", "bioconductor", "ggplot2", "tidyverse"]),
    ("Python", "software", 1.5, ["python", "pandas", "numpy", "scipy", "biopython", "scikit-learn", "sklearn"]),
    ("MATLAB", "dati", 1.7, ["matlab", "simulink"]),
    ("SPSS / Prism", "dati", 1.7, ["spss", "graphpad", "graphpad prism", "prism", "sas", "stata", "minitab"]),
    ("SQL", "dati", 1.4, ["sql", "mysql", "postgresql", "postgres", "sqlite", "database relazionale", "t-sql", "plsql"]),
    ("Machine learning", "dati", 1.8, ["machine learning", "apprendimento automatico", "deep learning", "reti neurali", "neural network", "tensorflow", "pytorch"]),
    ("Power BI / Tableau", "dati", 1.6, ["power bi", "powerbi", "tableau", "qlik", "looker", "data visualization", "visualizzazione dati"]),
    ("LIMS", "dati", 1.9, ["lims", "laboratory information management", "eln", "electronic lab notebook", "quaderno elettronico"]),

    # --- Sviluppo software (copertura generale) ---------------------------
    ("JavaScript / TypeScript", "software", 1.4, ["javascript", "typescript", "node.js", "nodejs", "react", "vue", "angular", "next.js"]),
    ("Java", "software", 1.4, ["java", "spring", "spring boot", "kotlin"]),
    ("C / C++", "software", 1.5, ["c++", "cpp", "linguaggio c"]),
    ("C#/.NET", "software", 1.5, [".net", "dotnet", "c#", "asp.net"]),
    ("PHP", "software", 1.4, ["php", "laravel", "symfony", "wordpress"]),
    ("Go / Rust", "software", 1.6, ["golang", "go lang", "rust"]),
    ("Git", "software", 1.2, ["git", "github", "gitlab", "controllo di versione", "version control"]),
    ("Docker / Kubernetes", "software", 1.6, ["docker", "kubernetes", "k8s", "container", "containerizzazione"]),
    ("Cloud", "software", 1.5, ["aws", "amazon web services", "azure", "google cloud", "gcp", "cloud computing"]),
    ("CI/CD", "software", 1.5, ["ci/cd", "continuous integration", "integrazione continua", "jenkins", "github actions"]),
    ("API REST", "software", 1.4, ["rest api", "api rest", "restful", "graphql", "microservizi", "microservices"]),
    ("Linux", "software", 1.3, ["linux", "unix", "bash", "shell scripting", "ubuntu"]),

    # --- Ingegneria e tecnica --------------------------------------------
    ("CAD", "ingegneria", 1.6, ["cad", "autocad", "solidworks", "catia", "inventor", "progettazione meccanica"]),
    ("PLC / Automazione", "ingegneria", 1.7, ["plc", "scada", "automazione industriale", "industrial automation", "siemens s7"]),
    ("Manutenzione impianti", "ingegneria", 1.5, ["manutenzione", "maintenance", "manutenzione preventiva", "troubleshooting impianti"]),
    ("Sicurezza sul lavoro", "ingegneria", 1.5, ["sicurezza sul lavoro", "d.lgs 81", "rspp", "hse", "health and safety", "antinfortunistica"]),

    # --- Gestione e trasversali ------------------------------------------
    ("Project management", "gestione", 1.4, ["project management", "gestione progetti", "pmp", "prince2", "gantt", "agile", "scrum"]),
    ("Gestione team", "gestione", 1.4, ["gestione del team", "team leadership", "coordinamento team", "people management", "team leader"]),
    ("Budget e controllo costi", "gestione", 1.5, ["budget", "controllo di gestione", "cost control", "forecast", "analisi dei costi"]),
    ("Microsoft Office", "trasversali", 0.8, ["microsoft office", "pacchetto office", "office", "excel", "word", "powerpoint", "outlook"]),
    ("Comunicazione", "trasversali", 0.7, ["comunicazione", "communication skills", "public speaking", "presentazioni"]),
    ("Problem solving", "trasversali", 0.7, ["problem solving", "capacita analitiche", "analytical skills", "pensiero critico"]),
    ("Lavoro in team", "trasversali", 0.7, ["lavoro di squadra", "lavoro in team", "teamwork", "collaborazione"]),

    # --- Commerciale e amministrazione ------------------------------------
    ("Vendite / Business development", "commerciale", 1.4, ["vendite", "sales", "business development", "sviluppo commerciale", "account management", "crm", "salesforce"]),
    ("Marketing", "commerciale", 1.4, ["marketing", "digital marketing", "seo", "sem", "social media", "content marketing", "google analytics"]),
    ("Contabilita'", "amministrazione", 1.5, ["contabilita", "accounting", "bilancio", "partita doppia", "fatturazione", "prima nota"]),
    ("Risorse umane", "amministrazione", 1.5, ["risorse umane", "human resources", "recruiting", "selezione del personale", "amministrazione del personale"]),
    ("Segreteria e back office", "amministrazione", 1.2, ["segreteria", "segretaria", "back office", "gestione agenda", "data entry", "inserimento dati", "archiviazione documenti"]),
    ("Acquisti e fornitori", "amministrazione", 1.4, ["gestione ordini", "acquisti", "ufficio acquisti", "purchasing", "procurement", "gestione fornitori"]),
    ("Paghe e contributi", "amministrazione", 1.6, ["paghe e contributi", "cedolini", "payroll", "buste paga"]),

    # --- Logistica e magazzino --------------------------------------------
    ("Gestione magazzino", "logistica", 1.5, ["gestione magazzino", "magazzino", "magazziniere", "warehouse", "warehouse management", "stoccaggio", "inventario di magazzino"]),
    ("Carrello elevatore", "logistica", 1.6, ["carrello elevatore", "muletto", "patentino muletto", "forklift", "transpallet", "carrellista"]),
    ("Picking e preparazione ordini", "logistica", 1.4, ["picking", "preparazione ordini", "order picking", "packing", "imballaggio", "confezionamento"]),
    ("Spedizioni", "logistica", 1.4, ["spedizioni", "shipping", "logistica distributiva", "bolle di consegna", "ddt", "corriere"]),
    ("Gestione scorte", "logistica", 1.5, ["gestione scorte", "inventory management", "riordino scorte", "stock control"]),
    ("Patente C / CQC", "logistica", 1.7, ["cqc", "carta di qualificazione del conducente", "autista professionale", "patente superiore"]),

    # --- Vendita e clienti -------------------------------------------------
    ("Vendita al dettaglio", "commerciale", 1.3, ["vendita al dettaglio", "retail", "commesso", "commessa", "addetto vendite", "addetta vendite", "punto vendita", "shop assistant"]),
    ("Assistenza clienti", "commerciale", 1.3, ["assistenza clienti", "customer service", "customer care", "servizio clienti", "help desk", "call center"]),
    ("Operazioni di cassa", "commerciale", 1.2, ["addetto cassa", "addetta cassa", "operazioni di cassa", "cassiere", "cassiera"]),
    ("Visual merchandising", "commerciale", 1.5, ["visual merchandising", "allestimento vetrine", "merchandising"]),

    # --- Ristorazione e accoglienza ---------------------------------------
    ("Servizio di sala", "ristorazione", 1.3, ["servizio di sala", "cameriere", "cameriera", "sala e bar", "banconista", "waiter"]),
    ("Cucina", "ristorazione", 1.4, ["aiuto cuoco", "cuoco", "chef", "preparazione alimenti", "cucina professionale", "commis di cucina"]),
    ("Bar e caffetteria", "ristorazione", 1.3, ["barista", "caffetteria", "bartender", "preparazione bevande"]),
    ("Reception e front office", "ristorazione", 1.3, ["reception", "receptionist", "front office", "accoglienza clienti", "hospitality"]),

    # --- Produzione e mestieri --------------------------------------------
    ("Saldatura", "manifattura", 1.7, ["saldatura", "saldatore", "welding", "saldatura tig", "saldatura mig", "saldatura mag"]),
    ("Macchine utensili e CNC", "manifattura", 1.7, ["tornitura", "fresatura", "macchine utensili", "controllo numerico", "cnc", "tornitore", "fresatore"]),
    ("Montaggio e assemblaggio", "manifattura", 1.3, ["montaggio", "assemblaggio", "linea di produzione", "catena di montaggio", "operaio di produzione"]),
    ("Disegno tecnico", "manifattura", 1.6, ["disegno tecnico", "lettura del disegno", "technical drawing", "quote e tolleranze"]),
    ("Impianti elettrici", "manifattura", 1.6, ["impianti elettrici", "elettricista", "cablaggio", "quadri elettrici"]),
    ("Impianti idraulici", "manifattura", 1.5, ["idraulico", "impianti idraulici", "termoidraulica", "impianti termici"]),

    # --- Servizi alla persona ---------------------------------------------
    ("Assistenza alla persona", "servizi", 1.4, ["assistenza alla persona", "operatore socio sanitario", "oss", "badante", "caregiver", "assistenza domiciliare"]),
    ("Pulizie e sanificazione", "servizi", 1.2, ["addetto alle pulizie", "pulizie civili", "pulizie industriali", "sanificazione"]),
    ("Vigilanza", "servizi", 1.4, ["vigilanza", "guardia giurata", "addetto alla sicurezza", "antitaccheggio", "portierato"]),

    # --- Istruzione --------------------------------------------------------
    ("Insegnamento", "istruzione", 1.4, ["insegnamento", "insegnante", "docente", "tutoraggio", "lezioni private", "formazione in aula"]),
    ("Educazione infanzia", "istruzione", 1.5, ["educatore", "educatrice", "asilo nido", "scuola dell infanzia", "animatore"]),

    # --- Trasversali aggiuntive -------------------------------------------
    ("Patente B", "trasversali", 0.8, ["patente b", "patente di guida", "automunito", "automunita", "driving licence"]),
    ("Disponibilita' ai turni", "trasversali", 0.8, ["lavoro su turni", "turnista", "disponibilita ai turni", "shift work", "lavoro notturno"]),
    ("Organizzazione e precisione", "trasversali", 0.7, ["gestione del tempo", "time management", "organizzazione del lavoro", "precisione", "puntualita"]),
]

LANGUAGE_DEFS: list[tuple[str, list[str]]] = [
    ("Inglese", ["inglese", "english", "b2 english", "c1 english", "madrelingua inglese", "fluent english"]),
    ("Italiano", ["italiano", "italian", "madrelingua italiana"]),
    ("Francese", ["francese", "french", "francais"]),
    ("Tedesco", ["tedesco", "german", "deutsch"]),
    ("Spagnolo", ["spagnolo", "spanish", "espanol"]),
    ("Cinese", ["cinese", "mandarino", "chinese", "mandarin"]),
]

# Famiglie di ruolo: servono a capire che "Biotecnologo" e "Research Scientist"
# in laboratorio sono la stessa cosa, mentre "Sales Manager" non lo e'.
ROLE_FAMILIES: dict[str, list[str]] = {
    "ricerca life science": [
        "biotecnologo", "biotechnologist", "biologo", "biologist", "ricercatore", "researcher",
        "research scientist", "scientist", "research associate", "postdoc", "post-doc",
        "dottorando", "phd student", "borsista", "assegnista", "laboratory scientist",
        "scienziato", "research fellow",
    ],
    "tecnico di laboratorio": [
        "tecnico di laboratorio", "laboratory technician", "lab technician", "tecnico analista",
        "analista di laboratorio", "lab analyst", "tecnico chimico", "operatore di laboratorio",
        "research technician", "tecnico biologo",
    ],
    # Niente "compliance" o "auditor" da soli: valgono anche in ambito
    # finanziario e facevano risultare un ruolo antiriciclaggio in banca
    # affine a un profilo di qualita' farmaceutica.
    "qualita e regolatorio": [
        "quality assurance", "quality control", "qa specialist", "qc analyst", "regulatory affairs",
        "specialista regolatorio", "responsabile qualita", "quality manager",
        "auditor qualita", "quality auditor", "regulatory compliance",
        "farmacovigilanza", "pharmacovigilance specialist",
    ],
    # Niente "produzione"/"manufacturing" da soli: comparirebbero in qualunque
    # annuncio industriale e farebbero somigliare un manutentore meccanico a un
    # tecnologo farmaceutico.
    "produzione farmaceutica": [
        "tecnologo di produzione", "upstream processing", "downstream processing",
        "bioprocess engineer", "responsabile di produzione farmaceutica",
        "produzione farmaceutica", "produzione sterile", "officina farmaceutica",
    ],
    "clinico": [
        "clinical research associate", "cra", "clinical trial", "study coordinator", "data manager",
        "medical science liaison", "msl", "medical affairs", "clinical project manager",
    ],
    "bioinformatica e dati": [
        "bioinformatico", "bioinformatician", "data scientist", "data analyst", "analista dati",
        "computational biologist", "statistico", "biostatistician", "machine learning engineer",
    ],
    "sviluppo software": [
        "software engineer", "sviluppatore", "developer", "programmatore", "full stack", "backend",
        "frontend", "devops", "site reliability", "mobile developer", "software developer",
    ],
    "ingegneria": [
        "ingegnere", "engineer", "progettista", "design engineer", "automation engineer",
        "maintenance engineer", "process engineer", "field engineer",
    ],
    "commerciale": [
        "sales", "account executive", "account manager", "business developer", "commerciale",
        "venditore", "key account", "sales representative", "informatore scientifico",
    ],
    "marketing": [
        # "content" da sola non c'e' piu': e' una parola che compare in mezzo a
        # qualunque cosa - "content annotation", "content moderation", "content
        # delivery" - e bastava a far classificare come marketing un annuncio
        # che col marketing non c'entra niente. Nel titolo di un lavoro di
        # marketing "content" arriva sempre accompagnata.
        "marketing", "product manager", "brand manager", "growth",
        "communication specialist", "social media manager", "digital marketing",
        "content marketing", "content strategist", "content strategy",
        "content creator", "content editor", "content specialist", "copywriter",
    ],
    "amministrazione e hr": [
        "contabile", "accountant", "controller", "hr", "human resources", "recruiter",
        "amministrazione", "payroll", "risorse umane",
    ],
    "gestione": [
        "manager", "responsabile", "direttore", "head of", "team leader", "coordinatore",
        "supervisor", "chief", "lead",
    ],
    "logistica e magazzino": [
        "magazziniere", "addetto al magazzino", "carrellista", "mulettista", "logistica",
        "warehouse operator", "responsabile di magazzino", "autista", "corriere",
    ],
    "vendita e assistenza": [
        "commesso", "commessa", "addetto vendite", "addetta vendite", "cassiere", "cassiera",
        "store manager", "customer service", "assistenza clienti", "shop assistant",
    ],
    "ristorazione e accoglienza": [
        "cameriere", "cameriera", "cuoco", "chef", "barista", "banconista", "receptionist",
        "aiuto cuoco", "addetto alla ristorazione",
    ],
    "produzione e mestieri": [
        "operaio", "operatore di produzione", "saldatore", "tornitore", "fresatore",
        "elettricista", "idraulico", "manutentore", "montatore", "addetto alla produzione",
    ],
    "servizi alla persona": [
        "oss", "operatore socio sanitario", "badante", "educatore", "educatrice",
        "addetto alle pulizie", "guardia giurata", "assistente domiciliare",
    ],
    "istruzione": [
        "insegnante", "docente", "professore", "tutor", "formatore", "maestro", "maestra",
    ],
}

# "gestione" descrive un livello di responsabilita', non un mestiere: quasi ogni
# curriculum la contiene e quasi ogni annuncio la cita. Trattarla come un'area
# professionale faceva risultare un "Business Manager" affine a un biotecnologo
# solo perche' entrambi parlano di responsabilita'. Resta utile da mostrare nel
# profilo, ma non concorre alla somiglianza fra ruoli.
NON_DOMAIN_FAMILIES: frozenset[str] = frozenset({"gestione"})


def domain_families(families: Iterable[str]) -> set[str]:
    return {f for f in families if f not in NON_DOMAIN_FAMILIES}

# Livelli di studio, dal piu' alto al piu' basso. Il numero e' il livello.
EDUCATION_LEVELS: list[tuple[int, str, list[str]]] = [
    (5, "Dottorato", ["dottorato", "phd", "ph.d", "doctorate", "doctoral", "dottore di ricerca"]),
    (4, "Laurea magistrale", ["laurea magistrale", "laurea specialistica", "master degree", "master's degree", "msc", "m.sc", "laurea a ciclo unico", "master of science", "laurea quinquennale", "second cycle degree"]),
    (3, "Laurea triennale", ["laurea triennale", "laurea di primo livello", "bachelor", "bsc", "b.sc", "bachelor's degree", "first cycle degree", "laurea in"]),
    (2, "Diploma / ITS", ["diploma di perito", "istituto tecnico", "its", "diploma tecnico", "perito chimico", "perito industriale", "high school diploma"]),
    (1, "Diploma di maturita'", ["diploma di maturita", "maturita scientifica", "maturita classica", "scuola secondaria"]),
]

EDUCATION_FIELDS: list[tuple[str, list[str]]] = [
    ("Biotecnologie", ["biotecnologie", "biotechnology", "biotecnologico", "biotech"]),
    ("Biologia", ["biologia", "biology", "scienze biologiche", "biological sciences"]),
    ("Chimica", ["chimica", "chemistry", "scienze chimiche", "chimica industriale"]),
    ("CTF / Farmacia", ["farmacia", "pharmacy", "ctf", "chimica e tecnologia farmaceutiche", "pharmaceutical"]),
    ("Medicina", ["medicina", "medicine", "medical", "odontoiatria"]),
    ("Biotecnologie mediche", ["biotecnologie mediche", "medical biotechnology", "biotecnologie farmaceutiche"]),
    ("Scienze agrarie e alimentari", ["agraria", "scienze agrarie", "scienze alimentari", "food science", "agronomia", "agricultural"]),
    ("Veterinaria", ["veterinaria", "veterinary"]),
    ("Ingegneria", ["ingegneria", "engineering"]),
    ("Informatica", ["informatica", "computer science", "ingegneria informatica"]),
    ("Fisica", ["fisica", "physics"]),
    ("Matematica / Statistica", ["matematica", "mathematics", "statistica", "statistics"]),
    ("Economia", ["economia", "economics", "business administration", "management"]),
    ("Giurisprudenza", ["giurisprudenza", "law", "legge"]),
    ("Scienze naturali", ["scienze naturali", "natural sciences", "scienze ambientali", "environmental science"]),
]


# --------------------------------------------------------------------------
# Indice per il riconoscimento
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Skill:
    name: str
    group: str
    weight: float


def _build_index(defs: Iterable[tuple[str, list[str]]]) -> tuple[dict[tuple[str, ...], str], int]:
    """Traduce gli alias in sequenze di token per il confronto per n-grammi."""
    index: dict[tuple[str, ...], str] = {}
    longest = 1
    for canonical, aliases in defs:
        for alias in aliases:
            key = tuple(tokenize(alias, keep_stopwords=True))
            if not key:
                continue
            index.setdefault(key, canonical)
            longest = max(longest, len(key))
    return index, longest


SKILLS: dict[str, Skill] = {
    name: Skill(name, group, weight) for name, group, weight, _ in SKILL_DEFS
}
_SKILL_INDEX, _SKILL_MAX_LEN = _build_index([(n, a) for n, _, _, a in SKILL_DEFS])
_LANG_INDEX, _LANG_MAX_LEN = _build_index(LANGUAGE_DEFS)
_FIELD_INDEX, _FIELD_MAX_LEN = _build_index(EDUCATION_FIELDS)
_ROLE_INDEX, _ROLE_MAX_LEN = _build_index([(k, v) for k, v in ROLE_FAMILIES.items()])
_LEVEL_INDEX, _LEVEL_MAX_LEN = _build_index([(label, aliases) for _, label, aliases in EDUCATION_LEVELS])
_LEVEL_BY_LABEL = {label: level for level, label, _ in EDUCATION_LEVELS}


def _scan(text: str, index: dict[tuple[str, ...], str], max_len: int) -> list[str]:
    """Trova tutte le voci dell'indice presenti nel testo, senza duplicati."""
    tokens = tokenize(text, keep_stopwords=True)
    found: list[str] = []
    seen: set[str] = set()
    for i in range(len(tokens)):
        # Dal piu' lungo al piu' corto: "real time pcr" vince su "pcr".
        for span in range(min(max_len, len(tokens) - i), 0, -1):
            canonical = index.get(tuple(tokens[i : i + span]))
            if canonical is not None:
                if canonical not in seen:
                    seen.add(canonical)
                    found.append(canonical)
                break
    return found


def extract_skills(text: str) -> list[str]:
    return _scan(text, _SKILL_INDEX, _SKILL_MAX_LEN)


def extract_languages(text: str) -> list[str]:
    return _scan(text, _LANG_INDEX, _LANG_MAX_LEN)


def extract_roles(text: str) -> list[str]:
    return _scan(text, _ROLE_INDEX, _ROLE_MAX_LEN)


def extract_education_fields(text: str) -> list[str]:
    return _scan(text, _FIELD_INDEX, _FIELD_MAX_LEN)


def extract_education_level(text: str) -> tuple[int, str]:
    """Restituisce il livello di studio piu' alto citato nel testo."""
    labels = _scan(text, _LEVEL_INDEX, _LEVEL_MAX_LEN)
    best = (0, "")
    for label in labels:
        level = _LEVEL_BY_LABEL.get(label, 0)
        if level > best[0]:
            best = (level, label)
    return best


# Aree disciplinari affini. Un annuncio che chiede "Chimica o CTF" non deve
# scartare del tutto una laurea in Biotecnologie: sono percorsi vicini, e il
# punteggio riconosce la parentela invece di ragionare per uguaglianza esatta.
FIELD_CLUSTERS: dict[str, set[str]] = {
    "scienze della vita": {
        "Biotecnologie", "Biologia", "Biotecnologie mediche", "CTF / Farmacia",
        "Chimica", "Medicina", "Veterinaria", "Scienze agrarie e alimentari",
        "Scienze naturali",
    },
    "tecnico-scientifica": {
        "Ingegneria", "Informatica", "Fisica", "Matematica / Statistica", "Chimica",
    },
    "economico-giuridica": {"Economia", "Giurisprudenza"},
}


def fields_related(required: Iterable[str], owned: Iterable[str]) -> set[str]:
    """Aree disciplinari in cui le due liste di titoli si incontrano."""
    required, owned = set(required), set(owned)
    return {
        name
        for name, cluster in FIELD_CLUSTERS.items()
        if required & cluster and owned & cluster
    }


def resolve_skill(text: str) -> str | None:
    """Riconduce un'etichetta scritta a mano a una competenza del dizionario.

    Restituisce il nome canonico se il testo corrisponde a una competenza nota
    (anche tramite i suoi alias: "real time pcr" trova "qPCR / Real-time PCR"),
    altrimenti None: in quel caso l'etichetta resta libera.
    """
    if not text or not text.strip():
        return None
    if text.strip() in SKILLS:
        return text.strip()
    trovate = extract_skills(text)
    return trovate[0] if trovate else None


# Le etichette dei livelli, dal piu' alto al piu' basso: servono al prompt che
# chiede al modello di sceglierne una invece di inventarsi una formulazione.
EDUCATION_LABELS: list[str] = [label for _, label, _ in EDUCATION_LEVELS]


def education_level_value(label: str) -> int:
    """Il numero corrispondente a un'etichetta di titolo di studio, 0 se ignota."""
    return _LEVEL_BY_LABEL.get((label or "").strip(), 0)


def skill_catalogue() -> list[dict[str, object]]:
    """Tutte le competenze riconosciute, per il completamento automatico."""
    return [
        {"name": s.name, "group": s.group, "weight": s.weight}
        for s in sorted(SKILLS.values(), key=lambda s: (s.group, s.name))
    ]


def skill_weight(name: str) -> float:
    skill = SKILLS.get(name)
    return skill.weight if skill else 1.0


def skill_group(name: str) -> str:
    skill = SKILLS.get(name)
    return skill.group if skill else ""


# --------------------------------------------------------------------------
# Anni di esperienza
# --------------------------------------------------------------------------

# Gli annunci italiani scrivono la durata in tutti i modi: "3 anni", "almeno
# due anni", "esperienza comprovata di 2-3 anni", "minimo 6 mesi". Cercare solo
# le cifre seguite da "anni" lasciava fuori nove annunci su dieci.
_NUMERI_A_PAROLE = {
    "un": 1, "uno": 1, "una": 1, "due": 2, "tre": 3, "quattro": 4, "cinque": 5,
    "sei": 6, "sette": 7, "otto": 8, "nove": 9, "dieci": 10,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
_PAROLE_NUMERO = "|".join(sorted(_NUMERI_A_PAROLE, key=len, reverse=True))

_DURATA = re.compile(
    r"(?:(?P<soglia>almeno|minimo|min|at\s+least|minimum(?:\s+of)?|oltre|over|piu\s+di|"
    r"more\s+than)\s+)?"
    rf"\b(?P<n>\d{{1,2}}|{_PAROLE_NUMERO})\b"
    r"(?:\s*(?:[-–/]|a|to)\s*(?P<n2>\d{1,2}))?"      # intervalli: "2-3 anni"
    r"\s*\+?\s*(?P<unita>anni|anno|mesi|mese|years|year|months|month)\b"
)

# Il numero conta solo se intorno si parla dell'esperienza del candidato...
_VICINO_A_ESPERIENZA = re.compile(
    r"esperienz|experience|maturat|pregress|comprovat|seniority|nel ruolo|"
    r"nel settore|lavorativ|anzianit"
)
# ...e non dell'anzianita' dell'azienda, che negli annunci compare spessissimo
# ("un'azienda con oltre 50 anni di esperienza nella distribuzione").
_ETA_AZIENDA = re.compile(
    r"azienda|societ|gruppo|fondat|founded|has grown|nasce|opera\s+da|operiamo|"
    r"sul mercato|di attivit|di storia|di presenza|nel corso degli anni|vanta|"
    r"leader|dal\s+(?:19|20)\d\d|clienti|fatturato|dipendenti|sedi|realta|"
    r"professionals|employees|countries|paesi|multinazional"
)

# "da oltre 20 anni", "with over 25 years": e' l'anzianita' di chi assume, mai
# quella chiesta al candidato. La soglia ("oltre") e' quello che li distingue
# da un requisito vero, dove si scrive "almeno" o "minimo".
_ANZIANITA_DI_CHI_ASSUME = re.compile(
    r"(?:\bda\b|attiv|operant|present|nat[ao]|fondat|\bwith\b|\bsince\b)\s+"
    r"(?:sul\s+mercato\s+)?(?:da\s+)?(?:oltre|piu\s+di|over|more\s+than)\s*$"
)

# Esperienza chiesta senza dire quanta: "pregressa esperienza in laboratorio".
_ESPERIENZA_QUALITATIVA = re.compile(
    r"esperienza\s+(?:pregressa|precedente|comprovata|consolidata|documentata|"
    r"maturata|specifica|significativa|solida)|"
    r"(?:pregressa|precedente|comprovata|consolidata|documentata|solida|"
    r"significativa)\s+esperienza|"
    r"(?:proven|previous|prior|relevant|hands-on)\s+experience|"
    r"experience\s+(?:is\s+)?(?:required|mandatory|essential)|"
    # "- Esperienza nella gestione di laboratori": la riga di requisito nuda
    r"^[-\u2013*\s]*esperienza\s+(?:in|nel|nella|nei|nelle|con|di|come|presso|maturata)\b|"
    r"\bcon\s+esperienza\b|\bmaturato\s+(?:un')?esperienza|\bwith\s+experience\b"
)

# "Gradita", "costituisce un plus": e' una preferenza, non uno sbarramento.
_PREFERENZA = re.compile(
    r"preferibil|preferenzial|gradit|apprezzat|desiderabil|costituisce\s+(?:titolo|un\s+plus)|"
    r"titolo\s+preferenziale|\bplus\b|nice\s+to\s+have|non\s+indispensabil|"
    r"anche\s+breve|opzional|preferred|ideally|welcome|sara\s+considerat"
)
_OBBLIGO = re.compile(
    r"richiest|necessari|obbligatori|indispensabil|imprescindibil|\bmust\b|"
    r"\brequired\b|mandatory|essential|si\s+richiede|requisit|\bdeve\b|dovra|\bobbligatorio\b"
)

# "anche senza esperienza", "rivolto a neolaureati": qui l'esperienza compare
# per dire che non serve. Senza questo controllo l'annuncio piu' aperto di
# tutti diventava il piu' selettivo.
_NESSUN_REQUISITO = re.compile(
    r"senza\s+esperienza|anche\s+senza|non\s+(?:e|sono)\s+(?:necessari|richiest)|"
    r"nessuna\s+esperienza|non\s+richiediamo|no\s+(?:prior\s+|previous\s+)?experience|"
    r"neolaureat|prima\s+esperienza|primo\s+impiego|entry\s+level|no\s+experience\s+needed"
)

_FINESTRA = 120         # caratteri attorno alla frase in cui leggere il contesto
_ANNI_PLAUSIBILI = 25   # oltre, si parla quasi sempre dell'azienda

# Molti annunci sono un blocco unico senza elenchi: le frasi vanno separate
# anche sui punti, altrimenti "obbligo" o "preferenza" verrebbero decisi
# leggendo l'intera pagina invece del requisito.
_FINE_FRASE = re.compile(r"(?<=[a-z0-9\)])\.\s+")


@dataclass(frozen=True)
class ExperienceRequirement:
    """Cosa chiede un annuncio in fatto di esperienza.

    `years` resta None quando l'esperienza e' chiesta senza quantificarla: e' il
    caso piu' frequente, e trattarlo come "nessun requisito" faceva sparire il
    criterio dal punteggio proprio negli annunci che lo pretendevano.
    """

    years: float | None = None
    required: bool = False      # l'annuncio la chiede davvero
    hard: bool = False          # ...come requisito, non come preferenza
    evidence: str = ""          # la frase da cui viene, per spiegare il punteggio


def _valore(match: re.Match) -> float | None:
    """Durata in anni di una singola occorrenza, o None se non plausibile."""
    grezzo = match.group("n")
    n = float(grezzo) if grezzo.isdigit() else float(_NUMERI_A_PAROLE.get(grezzo, 0))
    if n <= 0:
        return None
    if match.group("unita").startswith(("mes", "month")):
        return round(n / 12.0, 2)
    return n if n <= _ANNI_PLAUSIBILI else None


def _segmenti(text: str) -> list[str]:
    """Frasi, righe e punti elenco: il requisito vive dentro la sua frase."""
    pezzi = []
    for riga in normalize_lines(text).split(chr(10)):
        for pezzo in re.split(r"[;\u2022\u00b7]", riga):
            pezzi.extend(_FINE_FRASE.split(pezzo))
    return [p.strip() for p in pezzi if p.strip()]


def _contesto(segmento: str, inizio: int, fine: int) -> str:
    return segmento[max(0, inizio - _FINESTRA):fine + _FINESTRA]


def extract_experience_requirement(text: str) -> ExperienceRequirement:
    """Legge il requisito di esperienza, quantificato o no."""
    if not text:
        return ExperienceRequirement()

    quantificati: list[tuple[float, bool, str]] = []   # (anni, obbligo, frase)
    qualitativi: list[tuple[bool, str]] = []           # (obbligo, frase)

    for segmento in _segmenti(text):
        trovato_numero = False
        for match in _DURATA.finditer(segmento):
            intorno = _contesto(segmento, match.start(), match.end())
            if not _VICINO_A_ESPERIENZA.search(intorno) or _ETA_AZIENDA.search(intorno):
                continue
            if _NESSUN_REQUISITO.search(intorno):
                continue
            if _ANZIANITA_DI_CHI_ASSUME.search(segmento[max(0, match.start() - 40):match.start()]):
                continue
            anni = _valore(match)
            if anni is None:
                continue
            trovato_numero = True
            # Un numero dichiarato e' un requisito, salvo che la frase dica
            # il contrario ("gradita esperienza di 2 anni").
            quantificati.append((anni, not _PREFERENZA.search(intorno), intorno))

        if trovato_numero:
            continue
        qualitativo = _ESPERIENZA_QUALITATIVA.search(segmento)
        if not qualitativo:
            continue
        intorno = _contesto(segmento, qualitativo.start(), qualitativo.end())
        if _NESSUN_REQUISITO.search(intorno) or _ETA_AZIENDA.search(intorno):
            continue
        qualitativi.append((not _PREFERENZA.search(intorno), intorno))

    if quantificati:
        # Fra piu' requisiti si tiene il piu' basso: e' la lettura piu' generosa
        # verso il candidato, coerente con il resto del punteggio.
        duri = [q for q in quantificati if q[1]]
        anni, hard, frase = min(duri or quantificati, key=lambda q: q[0])
        return ExperienceRequirement(anni, True, hard, frase.strip()[:200])

    if qualitativi:
        hard = any(q[0] for q in qualitativi)
        frase = next(q[1] for q in qualitativi if q[0] == hard)
        return ExperienceRequirement(None, True, hard, frase.strip()[:200])

    return ExperienceRequirement()


def extract_required_years(text: str) -> float | None:
    """Anni di esperienza richiesti da un annuncio, se dichiarati."""
    return extract_experience_requirement(text).years
