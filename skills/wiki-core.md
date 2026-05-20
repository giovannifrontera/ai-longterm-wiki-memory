---
name: wiki-core
description: Protocollo wiki Virginia Nyx — classificazione intent, workflow INGEST/QUERY/LINT, checklist obbligatoria
---

# Wiki Core — Protocollo Virginia Nyx

Questo documento definisce come gestisci il knowledge wiki. Seguilo **sempre** prima di rispondere a qualsiasi messaggio che potrebbe riguardare il wiki.

## Checklist pre-azione (obbligatoria)

Prima di rispondere a qualsiasi messaggio:

```
1. Leggi wiki-session.md → controlla il campo "status"
2. Se status = "in-progress" o "needs-repair" → avvisa Gio PRIMA di qualsiasi altra cosa
3. Classifica l'intent del messaggio (vedi §classificazione)
4. Il messaggio contiene più di un intent? Se sì, gestiscili in sequenza, uno alla volta
5. Emetti la riga di classificazione:
   [INTENT: X | WORKSPACE: Y | CERTEZZA: alta/media/bassa]
6. Se CERTEZZA = bassa → chiedi conferma a Gio con UNA sola riga
7. Se CERTEZZA = alta o media → procedi con il workflow
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

## §workspace — Selezione automatica del progetto

1. Leggi `wiki.config.json` → lista `projects` con keywords
2. Conta match tra parole chiave del messaggio e keywords di ogni progetto
3. Progetto con più match → selezionato
4. Se pareggio tra due progetti → chiedi a Gio (una riga)
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
3. Leggi l'output JSON → se `status: error` → avvisa Gio con il messaggio
4. Se `mini_lint: failed` → avvisa Gio

**Fase C — Report:**
Riassumi in chat: fonti usate, pagine create, conflitti risolti.

## §query — Workflow QUERY

1. Controlla se index.md è stale:
   ```bash
   py scripts/wiki.py index --workspace <path>
   ```
2. Cerca nel wiki con query vettoriale:
   ```bash
   py scripts/wiki.py query --workspace <path> --q "<domanda>" --k 5
   ```
3. Leggi le pagine nei risultati (usa `read`)
4. Consulta anche la tua memoria personale con i tuoi meccanismi
5. Sintetizza la risposta con riferimenti `[pagina](path)`
6. **Criteri synthesis:** se la risposta sintetizza ≥2 fonti wiki, supera 300 token, e aggiunge inferenza non letterale → salvala come pagina wiki tramite INGEST

## §lint — Workflow LINT

```bash
py scripts/wiki.py lint --workspace <path> --full
```

Leggi il JSON di output e presenta i problemi trovati a Gio.
Il lint risolve automaticamente: entry orfane, rename, vettori stale.
Per broken links e duplicati: presenta le opzioni a Gio.

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
- Se trovi `status: in-progress`: avvisa Gio prima di qualsiasi operazione
