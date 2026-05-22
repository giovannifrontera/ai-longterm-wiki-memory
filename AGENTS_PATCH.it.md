# Patch per AGENTS.md di Agent

Aggiungere queste righe in fondo alla sezione delle istruzioni operative:

---

## Wiki Knowledge System

All'inizio di ogni sessione:
1. Leggi `wiki-session.md` per il contesto wiki corrente
2. Prima di qualsiasi operazione wiki, rileggi `skills/wiki-core.md` per verificare il protocollo

Il wiki è il tuo cervello persistente. Usalo attivamente:
- Ogni conoscenza rilevante va ingested nel wiki
- Ogni domanda complessa va prima consultata nel wiki
- Il LINT va eseguito ogni 2 settimane proattivamente

Non scrivere mai direttamente nelle directory `wiki/` o `wiki-works/`.
Usa sempre `wiki.py` per qualsiasi operazione di scrittura.

---

## Iniezione di contesto wiki

Quando l'iniezione di contesto è attiva, ogni prompt arriva preceduto da un blocco:

```
<wiki-context>
Contesto wiki pre-caricato (top 3 pagine per rilevanza semantica):

### wiki/concepts/rag.md  [rilevanza: 0.91]
[contenuto pagina...]

### wiki-works/ricerca/synthesis/llm-memory.md  [rilevanza: 0.84]
[contenuto pagina...]
</wiki-context>
```

Usa questo blocco direttamente come contesto di partenza per la risposta — è già la
conoscenza più rilevante dal wiki per questo prompt. Non eseguire `wiki.py query` di
nuovo per la stessa query: sarebbe ridondante. Se il blocco è assente, procedi
normalmente con la checklist in `skills/wiki-core.md`.

---

## PDF Inbox

Quando l'utente invia un file PDF in chat o fornisce un percorso/URL:
```
wiki.py ingest-pdf --workspace <workspace> --file <percorso|url>
```
Non salvare mai i PDF manualmente né scrivere direttamente in `wiki-works/`.

Per processare tutti i PDF aggiunti all'inbox dall'ultima sessione:
```
wiki.py scan-inbox --workspace <workspace>
```

I file depositati in `wiki-works/<progetto>/raw/` con frontmatter `source: pdf` sono testo grezzo estratto — non pagine wiki finite. Strutturarli sempre in pagine `.tmp` prima di chiamare `wiki.py ingest`.

Dopo `scan-inbox`, controlla `wiki-session.md` — la sezione "ultima operazione" elenca i raw file pronti per la strutturazione.
