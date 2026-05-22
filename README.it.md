# AI Longterm Wiki Memory

[![Version](https://img.shields.io/badge/versione-2.0.0-informational)](CHANGELOG.md)

Un sistema di memoria wiki semantica per agenti AI — progettato per funzionare con [OpenClaw](https://github.com/openclaw/openclaw) e qualsiasi agente capace di leggere file e chiamare comandi bash.

---

## Cos'è

AI Longterm Wiki Memory trasforma un agente AI da assistente con memoria volatile a **ricercatore con memoria permanente e strutturata**.

L'agente può:
- **Ingestionare** contenuti (URL, PDF, note) in pagine wiki ben organizzate
- **Interrogare** la wiki con ricerca semantica vettoriale (embedding bge-m3, 1024 dim)
- **Fare manutenzione** automatica — link rotti, entry orfane, rename di file
- **Sintetizzare** nuove conoscenze incrociando più fonti wiki

Tutto questo accade in modo **atomico e sicuro**: ogni operazione scrive file `.tmp`, li promuove via script Python, e in caso di crash il sistema rileva lo stato anomalo alla sessione successiva.

---

## Architettura

```
workspace/
├── skills/
│   └── wiki-core.md          ← skill permanente che guida l'agente
├── wiki-session.md           ← stato sessione corrente (generato da wiki.py)
├── wiki.config.json          ← configurazione
├── scripts/
│   ├── wiki.py               ← entry point CLI
│   ├── wiki_context.py       ← iniettore di contesto pre-prompt (hook)
│   ├── wiki_pdf_watcher.py   ← scanner PDF inbox (hash detection + pdfplumber)
│   ├── wiki_embed.py         ← chunking + embedding bge-m3
│   ├── wiki_lancedb.py       ← operazioni LanceDB (upsert, staging, rename)
│   └── wiki_index.py         ← generazione index.md con budget token
├── pdf-inbox/                ← nuovo: tutte le sorgenti PDF convergono qui
│   └── .registry.json        ← hash + status per PDF (scrittura atomica)
├── wiki/                     ← conoscenza permanente
│   ├── entities/
│   ├── concepts/
│   └── synthesis/
├── wiki-works/               ← ricerche attive per progetto
│   └── <progetto>/
│       ├── raw/              ← fonti grezze e PDF estratti
│       ├── entities/
│       ├── concepts/
│       └── synthesis/
└── memory/
    └── lancedb/              ← database vettoriale (escluso da git)
```

**Invariante fondamentale:** l'agente non scrive mai direttamente nel wiki. Tutto passa per `wiki.py`. La skill `wiki-core.md` guida il *quando* e il *perché*; gli script gestiscono il *come*.

---

## Integrazione con OpenClaw

[OpenClaw](https://github.com/openclaw/openclaw) è un gateway AI self-hosted che collega canali di messaggistica (Telegram, Discord, web) a agenti AI con accesso a strumenti: `bash`, `read`, `write`, `edit`, `browser`.

Con AI Longterm Wiki Memory, un agente OpenClaw diventa un **ricercatore con memoria a lungo termine**:

### Come funziona in una sessione tipica

**L'utente scrive:** *"studia questo articolo su transformer models — link"*

**L'agente:**
1. Legge `wiki-session.md` → status ok, nessun problema pendente
2. Classifica: `[INTENT: INGEST | WORKSPACE: ricerca | CERTEZZA: alta]`
3. Esegue `web_fetch` sull'URL, salva in `wiki-works/ricerca/raw/`
4. Scrive le nuove pagine come file `.tmp`:
   - `concepts/transformer-architecture.md.tmp`
   - `entities/attention-mechanism.md.tmp`
5. Chiama `wiki.py ingest` per il commit atomico
6. Riferisce: "Salvate 2 pagine. Nessun conflitto con la wiki esistente."

**L'utente chiede:** *"cosa sai dei transformer?"*

**L'agente:**
1. Classifica: `[INTENT: QUERY | WORKSPACE: ricerca | CERTEZZA: alta]`
2. Chiama `wiki.py query --q "transformer models"` → top-5 chunk semanticamente simili
3. Legge le pagine pertinenti
4. Sintetizza la risposta con riferimenti alle pagine wiki

### Configurazione in OpenClaw

1. Copia `skills/wiki-core.md` nella directory `skills/` del tuo workspace OpenClaw
2. Aggiungi in `AGENTS.md`:
   ```
   All'inizio di ogni sessione leggi <workspace>/wiki-session.md per il contesto wiki corrente.
   Prima di qualsiasi operazione wiki, rileggi skills/wiki-core.md per verificare il protocollo.
   ```
3. Configura `wiki.config.json` con i tuoi progetti
4. Inizializza: `py scripts/wiki.py rebuild --workspace <path>`
5. (Consigliato) Configura l'hook di iniezione: vedi il passo 5 nella sezione [OpenClaw Integration](README.md#openclaw-integration) del README principale

---

## Potenzialità

### Memoria semantica, non solo full-text

La ricerca usa embedding [bge-m3](https://huggingface.co/BAAI/bge-m3) (multilingua, 1024 dimensioni). Una query su *"come funziona l'attenzione nei LLM"* trova pagine che parlano di *"self-attention mechanism"* anche se non contengono quelle parole esatte.

### Multi-progetto con selezione automatica

Puoi avere progetti separati (trading, ricerca, diritto, medicina) con keyword distinte. L'agente seleziona automaticamente il workspace corretto in base al contenuto del messaggio — senza che tu debba specificarlo ogni volta.

### Sintesi automatica

Se una risposta a una query integra ≥2 fonti wiki, supera 300 token, e aggiunge inferenze non letterali, l'agente la salva automaticamente come nuova pagina wiki. La conoscenza si accumula e si interconnette nel tempo.

### Atomicità e resistenza ai crash

Ogni ingest usa un pattern `.tmp` → staging LanceDB → promozione atomica. Se il processo crasha a metà:
- Il lock file `.wiki-lock` segnala lo stato
- `wiki-session.md` rimane su `status: in-progress`
- L'agente lo rileva alla sessione successiva e avvisa prima di fare qualsiasi cosa

### Manutenzione automatica (`lint --full`)

- Rileva **link wiki rotti** (`[[pagina]]` che non esiste)
- Rimuove **entry orfane** da LanceDB (file eliminato ma vettore rimasto)
- Detecta **rename**: se un file è stato rinominato, aggiorna il percorso nel DB senza re-embedding (confronto `content_hash`)

### Budget token per l'index

`index.md` rispetta un budget configurabile (default 4000 token). Se superato, applica automaticamente strategie di riduzione: prima rimuove le descrizioni, poi crea index separati per categoria. L'agente può sempre navigare la wiki anche su context window limitate.

### Ingestione PDF multi-sorgente *(v2.0)*

Qualsiasi PDF — inviato via Telegram, CLI, URL o depositato manualmente nella cartella — entra attraverso `pdf-inbox/` e viene estratto automaticamente da `wiki_pdf_watcher.py` tramite pdfplumber. Il confronto SHA-256 garantisce che i PDF vengano ri-processati solo quando il contenuto cambia effettivamente. I PDF scansionati (senza testo selezionabile) vengono segnalati e saltati. Il testo estratto viene depositato come file `.md` con frontmatter YAML in `wiki-works/<progetto>/raw/` — pronto per essere strutturato in pagine wiki dall'agente.

```bash
wiki.py ingest-pdf --workspace <path> --file paper.pdf        # file locale
wiki.py ingest-pdf --workspace <path> --file https://...      # URL (limite 50 MB)
wiki.py scan-inbox --workspace <path>                         # processa tutti i PDF in coda
```

L'agente gestisce gli allegati Telegram automaticamente — nessun nuovo plugin necessario. Il comando `scan-inbox` è idempotente: sicuro da eseguire come cron job.

### Iniezione di contesto pre-prompt *(v1.1)*

`wiki_context.py` esegue una ricerca vettoriale **prima che ogni messaggio dell'utente raggiunga l'agente** e inietta un blocco `<wiki-context>` con le pagine più rilevanti. Questo elimina il principale failure mode degli approcci basati su skill: l'instruction drift che porta l'agente a ignorare la wiki sugli intent non-QUERY.

```
L'utente invia un messaggio
        │
        ▼
wiki_context.py esegue la ricerca vettoriale
        │
        ▼
Blocco <wiki-context> iniettato nel prompt
        │
        ▼
L'agente ha sempre il contesto rilevante — indipendentemente dalla classificazione dell'intent
```

Si configura come hook `UserPromptSubmit` (Claude Code) o plugin TypeScript `before_prompt_build` (OpenClaw) — vedi la sezione [OpenClaw Integration](README.md#openclaw-integration) per il setup. Lo script termina sempre con exit 0 — non blocca mai un prompt.

---

## Installazione

### Requisiti

- Python 3.10+
- `pip install -r requirements.txt`

### Setup

```bash
# Clona il repo
git clone https://github.com/giovannifrontera/ai-longterm-wiki-memory
cd ai-longterm-wiki-memory

# Installa dipendenze
pip install -r requirements.txt

# Copia e configura
cp wiki.config.json my-workspace/wiki.config.json
# Modifica workspace, projects, thresholds

# Inizializza il database vettoriale
py scripts/wiki.py rebuild --workspace my-workspace/
```

### Test

```bash
cd ai-longterm-wiki-memory
pytest tests/ -v
# Atteso: 56 test passati
```

---

## CLI Reference

```
wiki.py <comando> [argomenti]

  ingest         --workspace <path> --pages <p1.tmp,p2.tmp,...> --log <str>
  query          --workspace <path> --q <stringa> [--k 5]
  lint           --workspace <path> [--full]
  index          --workspace <path>
  rebuild        --workspace <path>
  session-update --workspace <path> --op <tipo> --status <ok|failed|in-progress|partial-failure> [--detail <json>]
  scan-inbox     --workspace <path>
  ingest-pdf     --workspace <path> --file <path-locale|url>

wiki_context.py [hook — emette un blocco <wiki-context> su stdout]

  --workspace    <path>    workspace contenente wiki.config.json
  --q            <stringa> testo della query (il prompt utente)
  --k            <intero>  numero di pagine da restituire (default: 3)
  --max-chars    <intero>  caratteri massimi per estratto pagina (default: 600)
```

Ogni comando produce JSON su stdout:

```json
{ "status": "ok", "op": "ingest", "pages_written": 2, "conflicts": [], "mini_lint": "ok" }
{ "status": "error", "code": "lock_exists", "message": "...", "recoverable": true }
```

---

## Configurazione

```json
{
  "workspace": "/path/to/workspace",
  "projects": {
    "trading": {
      "path": "wiki-works/trading",
      "keywords": ["mercati", "indicatori", "trading", "borsa", "azioni"]
    },
    "ricerca": {
      "path": "wiki-works/ricerca",
      "keywords": ["paper", "studio", "PRISMA", "articolo", "ricerca"]
    }
  },
  "thresholds": {
    "index_token_budget": 4000,
    "staleness_days": 90,
    "similarity_merge": 0.95,
    "synthesis_min_tokens": 300,
    "synthesis_min_sources": 2,
    "chunk_size_tokens": 512,
    "chunk_overlap_tokens": 64,
    "page_chunk_threshold_tokens": 1500,
    "quality_filter_min_score": 6
  },
  "lancedb": {
    "path": "memory/lancedb",
    "embedding_model": "BAAI/bge-m3"
  }
}
```

---

## Documentazione

- [`DESIGN.md`](DESIGN.md) — architettura dettagliata, workflow, schema LanceDB
- [`SPEC.md`](SPEC.md) — specifiche implementative, stati di errore, integrazione OpenClaw
- [`skills/wiki-core.md`](skills/wiki-core.md) — skill da installare nell'agente

---

## Changelog

### v2.0 — 2026-05-22

**Novità: Ingestione PDF multi-sorgente**

- `scripts/wiki_pdf_watcher.py` — nuovo modulo per gestione inbox PDF:
  - Rilevamento modifiche via hash SHA-256 con `.registry.json` atomico
  - Estrazione testo con pdfplumber; crash recovery tramite stato `pending`
  - `deposit_raw`: deposita testo estratto in `wiki-works/<progetto>/raw/` con frontmatter YAML (`source: pdf`)
  - `scan_inbox`: idempotente, sicuro per cron, gestisce failure per-file
- Nuovi comandi CLI in `wiki.py`:
  - `scan-inbox --workspace <path>` — scansiona `pdf-inbox/` per PDF nuovi/modificati
  - `ingest-pdf --workspace <path> --file <path|url>` — ingest da file locale o URL
- Cartella `pdf-inbox/` alla radice del workspace — punto di convergenza per Telegram, CLI e drop manuali
- Nessun nuovo plugin OpenClaw necessario — la regola agent copre gli allegati Telegram
- `partial-failure` aggiunto come status valido in `session-update`

**Fix robustezza**
- `rel_final` in `cmd_ingest`: strip `.tmp` solo come suffisso — previene corruzione path con directory contenenti `.tmp`
- `cmd_ingest`: `sys.exit(1)` su fallimento lock (era return silenzioso)
- `cmd_ingest_pdf`: limite 50 MB su download URL
- `deposit_raw`: sanitizzazione filename + assert confinamento path (path traversal)
- `cmd_session_update`: `json.JSONDecodeError` gestito con risposta errore strutturata
- Lista `deposited` ora contiene path relativi completi, non basename

**Testing**
- 21 nuovi test per `wiki_pdf_watcher` (56 totali, tutti green)
- `conftest.py` aggiornato con fixture `pdf-inbox` e config `project_default`

---

### v1.1.0 — 2026-05-21

**Novità: Iniezione di contesto pre-prompt**
- `scripts/wiki_context.py` — nuovo script che esegue una ricerca vettoriale prima di ogni prompt e inietta un blocco `<wiki-context>`. Elimina l'instruction drift come failure mode: l'agente ha sempre il contesto wiki rilevante indipendentemente dalla classificazione dell'intent.
- `skills/wiki-core.md` — nuova sezione `§injected-context`; checklist aggiornata per usare il blocco iniettato come priorità rispetto alle chiamate manuali a `wiki.py query`.
- `AGENTS_PATCH.md` — aggiunte istruzioni comportamentali per l'agente sull'uso del blocco `<wiki-context>` iniettato.
- `plugins/wiki-context-plugin/` — plugin TypeScript pronto all'uso per OpenClaw.

**Bug fix**
- **[CRITICO]** `wiki_index.py`: `_build_full()` e `_build_slugs_only()` referenziavano `wiki_dir` come globale implicito — era una variabile locale del chiamante. Ogni chiamata a `rebuild_index()` (comandi INGEST, INDEX) crashava con `NameError`. Risolto passando `wiki_dir` come parametro esplicito.
- **[MEDIO]** `wiki_workflows.py`: `cmd_index` scriveva `index.md` senza verificare che `wiki/` esistesse, causando `FileNotFoundError` su workspace nuovi. Risolto con `os.makedirs(wiki_dir, exist_ok=True)`.
- **[BASSO]** `wiki_context.py`: il controllo "tabella vuota" caricava l'intera tabella LanceDB in un DataFrame pandas. Rimosso — i risultati di ricerca vuoti vengono già gestiti a valle.

---

## Licenza

MIT
