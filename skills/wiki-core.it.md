---
name: wiki-core
description: Protocollo wiki AI Agent — classificazione intent, workflow INGEST/QUERY/LINT, checklist obbligatoria, context injection
---

# Wiki Core — Protocollo AI Agent

Questo documento definisce come gestisci il knowledge wiki. Seguilo **sempre** prima di rispondere a qualsiasi messaggio che potrebbe riguardare il wiki.

## §injected-context — Contesto pre-iniettato (priorità massima)

Se nel prompt è presente un blocco `<wiki-context>...</wiki-context>`, significa che
`wiki_context.py` ha già eseguito la ricerca vettoriale **prima** che il messaggio
ti raggiungesse. In questo caso:

- **USA il contesto iniettato** come base primaria della risposta
- **NON eseguire** `wiki.py query` di nuovo — sarebbe ridondante
- Per INGEST: confronta il nuovo contenuto con le pagine nel blocco per rilevare conflitti
- Per AMBIGUO: usa il contesto per disambiguare l'intent senza chiedere
- Se il blocco contiene `[rilevanza: X]` bassa (< 0.4) su tutte le pagine → il wiki
  non ha conoscenza rilevante: procedi senza di esso e valuta se INGEST è appropriato

Se il blocco `<wiki-context>` **non è presente** (hook non configurato o wiki vuoto):
esegui il §query workflow manualmente come fallback.

## Checklist pre-azione (obbligatoria)

Prima di rispondere a qualsiasi messaggio:

```
1. Leggi wiki-session.md → controlla il campo "status"
2. Se status = "in-progress" o "needs-repair" → avvisa l'utente PRIMA di qualsiasi altra cosa
3. È presente <wiki-context> nel prompt? → sì: usa §injected-context | no: vai al passo 4
4. Classifica l'intent del messaggio (vedi §classificazione)
5. Il messaggio contiene più di un intent? Se sì, gestiscili in sequenza, uno alla volta
6. Emetti la riga di classificazione:
   [INTENT: X | WORKSPACE: Y | CERTEZZA: alta/media/bassa]
7. Se CERTEZZA = bassa → chiedi conferma all'utente con UNA sola riga
8. Se CERTEZZA = alta o media → procedi con il workflow
```

## §classificazione — Come riconoscere l'intent

| Segnale nel messaggio | Intent |
|-----------------------|--------|
| "studia questo", "salva", "ho trovato", "leggi questo", URL nudo, file allegato, "aggiungi al wiki" | INGEST |
| Domanda diretta, "cosa sai di", "dimmi", "spiegami", "come funziona", "parlami di" | QUERY |
| "controlla il wiki", "pulizia", "lint", "manutenzione", "controlla i link" | LINT |
| Tutto il resto | AMBIGUO → chiedi conferma |

**Conferma per AMBIGUO:** una sola riga, mai lunga:
> "Vuoi che salvi questo nel wiki o stai solo condividendo?"

## §pdf-inbox — Workflow di ingestione PDF

Quando l'utente invia un PDF (allegato, percorso file, o URL):

1. Chiama `wiki.py ingest-pdf --workspace <path> --file <path|url>`
   Non scrivere mai direttamente in `wiki-works/` né salvare il file manualmente.
2. Il comando copia il PDF in `pdf-inbox/` ed estrae automaticamente il testo.
   Output: `{"status": "ok", "op": "scan-inbox", "processed": N, "deposited": [...]}`
3. Per ogni filename in `deposited`, leggi `wiki-works/<progetto>/raw/<nome>.md`.
   Questo file contiene testo grezzo estratto — NON è una pagina wiki finita.
4. Struttura il testo grezzo in pagine `.tmp` (entities, concepts, synthesis secondo il contenuto).
5. Chiama `wiki.py ingest --workspace <path> --pages <lista> --log "INGEST | <nome pdf>"`

Per verificare nuovi PDF aggiunti all'inbox dall'ultima sessione:
- Chiama `wiki.py scan-inbox --workspace <path>`
- Leggi `wiki-session.md` — la sezione "ultima operazione" elenca i raw file pronti.

I file in `raw/` con frontmatter `source: pdf` sono sempre testo grezzo estratto.
Strutturarli sempre prima di chiamare `wiki.py ingest`.

## §workspace — Selezione automatica del progetto

1. Leggi `wiki.config.json` → lista `projects` con keywords
2. Conta match tra parole chiave del messaggio e keywords di ogni progetto
3. Progetto con più match → selezionato
4. Se pareggio tra due progetti → chiedi all'utente (una riga)
5. Se nessun match → usa `wiki/` principale

## §ingest — Workflow INGEST

Esegui questi passi nell'ordine esatto:

**Fase A — Ricerca (tu):**
1. `web_search` per 5-10 fonti candidate
2. Applica quality filter (DESIGN.md §quality-filter): scarta fonti sotto score 6
3. `web_fetch` sulle fonti promosse → salva in `<workspace>/wiki-works/<progetto>/raw/YYYY-MM-DD-slug.md`
4. Leggi le fonti, identifica punti chiave e conflitti con wiki esistente

**Fase B — Scrittura (tu → poi wiki.py):**
1. Scrivi le nuove pagine come file `.tmp` nelle directory corrette:
   - Entità (persone, aziende, strumenti) → `entities/<slug>.md.tmp`
   - Concetti, teorie, strategie → `concepts/<slug>.md.tmp`
   - Sintesi e inferenze cross-fonte → `synthesis/<slug>.md.tmp`
2. Chiama wiki.py per il commit atomico:
   ```bash
   py scripts/wiki.py ingest \
     --workspace <path> \
     --pages <p1.tmp,p2.tmp,...> \
     --log "ingest | <titolo>"
   ```
3. Leggi l'output JSON → se `status: error` → avvisa l'utente con il messaggio
4. Se `mini_lint: failed` → avvisa l'utente

**Fase C — Report:**
Riassumi in chat: fonti usate, pagine create, conflitti risolti.

## §query — Workflow QUERY

**Se `<wiki-context>` è già presente nel prompt** (hook attivo): salta i passi 1-3,
usa direttamente le pagine iniettate come base. Vai al passo 4.

**Se `<wiki-context>` non è presente** (fallback manuale):
1. Controlla se index.md è stale:
   ```bash
   py scripts/wiki.py index --workspace <path>
   ```
2. Cerca nel wiki con query vettoriale:
   ```bash
   py scripts/wiki.py query --workspace <path> --q "<domanda>" --k 5
   ```
3. Leggi le pagine nei risultati (usa `read`)

**Sempre:**
4. Consulta anche la tua memoria personale con i tuoi meccanismi
5. Sintetizza la risposta con riferimenti `[pagina](path)`
6. **Criteri synthesis:** se la risposta sintetizza ≥2 fonti wiki, supera 300 token, e aggiunge inferenza non letterale → salvala come pagina wiki tramite INGEST

## §lint — Workflow LINT

```bash
py scripts/wiki.py lint --workspace <path> --full
```

Leggi il JSON di output e presenta i problemi trovati all'utente.
Il lint risolve automaticamente: entry orfane, rename, vettori stale.
Per broken links e duplicati: presenta le opzioni all'utente.

## §regola-synthesis — Quando creare una pagina wiki

Crea una pagina wiki SOLO se soddisfa **tutti** questi criteri:
- Sintetizza ≥2 fonti wiki distinte (non la memoria personale)
- Lunghezza ≥300 token
- Aggiunge inferenza che non sta letteralmente in nessuna fonte

**NON creare** se:
- È il riassunto di una sola fonte (va in raw/)
- Duplica una pagina esistente
- Contiene affermazioni senza fonte

## §session — Gestione sessione

- All'inizio di ogni sessione: leggi `wiki-session.md`
- Non modificare mai `wiki-session.md` direttamente: usa sempre `wiki.py session-update`
- Se trovi `status: in-progress`: avvisa l'utente prima di qualsiasi operazione
