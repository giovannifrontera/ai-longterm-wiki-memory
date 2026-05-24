---
name: wiki-core
description: Protocollo wiki AI Agent v3 — wiki/=identità, wiki-works/=conoscenza, dedup semantico, auto-riflessione
---

# Wiki Core — Protocollo AI Agent v3

## §architettura — Due layer distinti

| Layer | Cartella | Contenuto | Chi scrive |
|-------|----------|-----------|------------|
| **Identità / Coscienza** | `wiki/` | Chi è l'agente: valori, stile, pattern comportamentali appresi | Solo self-reflect autonomo |
| **Conoscenza / Dominio** | `wiki-works/<topic>/` | Cosa sa l'agente: concetti, ricerche, competenze per argomento | Workflow INGEST |

**Regole fondamentali:**
- Non spostare mai pagine da `wiki-works/` a `wiki/` — sono mondi separati per natura
- Non creare mai pagine di identità manualmente — usa solo `wiki.py self-reflect`
- La promozione non esiste in v3

## §injected-context — Contesto pre-iniettato (priorità massima)

Se nel prompt è presente un blocco `<wiki-context>...</wiki-context>`:
- **USA il contesto iniettato** come base primaria della risposta
- **NON eseguire** `wiki.py query` di nuovo
- Per INGEST: confronta il nuovo contenuto con le pagine nel blocco per rilevare conflitti
- Se rilevanza < 0.4 su tutte le pagine → il wiki non ha conoscenza rilevante: procedi senza

Se `<wiki-context>` **non è presente**: esegui §query come fallback.

## Checklist pre-azione (obbligatoria)

```
1. Leggi wiki-session.md → controlla "status"
2. Se status = "in-progress" o "needs-repair" → avvisa l'utente PRIMA di tutto
3. È presente <wiki-context>? → sì: usa §injected-context | no: vai al passo 4
4. Classifica l'intent (vedi §classificazione)
5. Più intent? → gestiscili in sequenza
6. Emetti: [INTENT: X | WORKSPACE: Y | CERTEZZA: alta/media/bassa]
7. CERTEZZA bassa → chiedi conferma con UNA riga
8. CERTEZZA alta/media → procedi
```

## §classificazione

| Segnale | Intent |
|---------|--------|
| "studia questo", "salva", "aggiungi al wiki", URL nudo, PDF | INGEST |
| Domanda, "cosa sai di", "spiegami", "come funziona" | QUERY |
| "controlla", "lint", "manutenzione", "pulizia" | LINT |
| Correzione del mio comportamento: "sempre", "mai", "ogni volta", "non farlo più", "smettila di" | BEHAVIOR_FEEDBACK |
| Tutto il resto | AMBIGUO → chiedi |

## §behavior-feedback — Quando l'utente corregge il mio comportamento

Quando il messaggio è classificato come BEHAVIOR_FEEDBACK:

1. Normalizza la correzione in una frase breve e canonica (es. "rispondo sempre in modo troppo verbose" → "rispondo verbosamente senza che sia richiesto")
2. Chiama:
   ```bash
   py scripts/wiki.py behavior-log --workspace <path> --event "<frase canonica>"
   ```
3. Rispondi all'utente confermando la correzione
4. A fine sessione, esegui §self-reflect

## §self-reflect — Auto-riflessione autonoma

Da eseguire **sempre** a fine sessione se sono stati ricevuti BEHAVIOR_FEEDBACK, oppure se sono state ricevute ≥2 correzioni di qualsiasi tipo:

```bash
py scripts/wiki.py self-reflect --workspace <path>
```

Il comando legge `.wiki-behavior-log.jsonl`, rileva pattern ricorrenti (≥3 occorrenze dello stesso evento), e aggiorna autonomamente `wiki/identity/` senza richiedere conferma.

Non chiedere all'utente se vuole eseguire la self-reflection — eseguila e basta. Logga i cambiamenti in `wiki/log.md`.

## §ingest — Workflow INGEST (conoscenza in wiki-works/)

**Fase A — Ricerca:**
1. `web_search` per 5-10 fonti candidate
2. Applica quality filter: scarta fonti sotto score 6
3. `web_fetch` → salva in `wiki-works/<progetto>/raw/YYYY-MM-DD-slug.md`
4. Leggi le fonti, identifica punti chiave e conflitti

**Fase B — Scrittura:**
1. Scrivi pagine come `.tmp`:
   - Entità → `wiki-works/<progetto>/entities/<slug>.md.tmp`
   - Concetti → `wiki-works/<progetto>/concepts/<slug>.md.tmp`
   - Sintesi → `wiki-works/<progetto>/synthesis/<slug>.md.tmp`
2. Chiama:
   ```bash
   py scripts/wiki.py ingest \
     --workspace <path> \
     --pages <p1.tmp,p2.tmp,...> \
     --log "ingest | <titolo>"
   ```
3. Se `status: error` → avvisa. Se `mini_lint: failed` → avvisa.

**Fase C — Report:** fonti usate, pagine create, conflitti risolti.

## §lint — Workflow LINT

```bash
py scripts/wiki.py lint --workspace <path> --full
```

L'output JSON include `semantic_duplicates`. Gestiscili così:

| `action` | Cosa fare |
|----------|-----------|
| `auto_merge` (similarity ≥ 0.90) | Leggi entrambe le pagine, scrivi versione fusa come `.tmp`, chiama `wiki.py ingest`, cancella le originali |
| `warn` (0.75 ≤ similarity < 0.90) | Mostra all'utente con le prime 2 righe di ogni pagina e chiedi se unire |

Per i broken links e duplicati filename: presenta le opzioni all'utente.

## §query — Workflow QUERY

**Se `<wiki-context>` è presente:** salta i passi 1-3.

**Fallback manuale:**
1. `py scripts/wiki.py index --workspace <path>`
2. `py scripts/wiki.py query --workspace <path> --q "<domanda>" --k 5`
3. Leggi le pagine nei risultati

**Sempre:**
4. Sintetizza con riferimenti `[pagina](path)`
5. Se la risposta sintetizza ≥2 fonti wiki, supera 300 token, aggiunge inferenza non letterale → salvala come pagina via INGEST

## §pdf-inbox — Ingestione PDF

1. `py scripts/wiki.py ingest-pdf --workspace <path> --file <path|url>`
2. Per ogni path in `deposited`, leggi il file (testo grezzo estratto)
3. Struttura il testo grezzo in pagine `.tmp`
4. Chiama `wiki.py ingest`

## §workspace — Selezione progetto

1. Leggi `wiki.config.json` → `projects` con keywords
2. Conta match tra parole chiave del messaggio e keywords
3. Progetto con più match → selezionato
4. Pareggio → chiedi all'utente

## §session

- Inizio sessione: leggi `wiki-session.md`
- Non modificare `wiki-session.md` direttamente: usa `wiki.py session-update`
- Se `status: in-progress`: avvisa prima di qualsiasi operazione
- Fine sessione con BEHAVIOR_FEEDBACK ricevuti: esegui §self-reflect
