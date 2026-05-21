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

## Context Injection (raccomandato)

Per evitare instruction drift e garantire che il wiki venga consultato su **ogni** prompt
— non solo quando classificato come QUERY — configura `wiki_context.py` come hook
pre-prompt. Il contesto wiki viene iniettato automaticamente prima che il messaggio
raggiunga l'agente, senza dipendere dalla checklist.

### Claude Code — hook `UserPromptSubmit`

Aggiungi a `.claude/settings.json` (o `settings.local.json`) nel tuo workspace:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "py /PERCORSO/ASSOLUTO/scripts/wiki_context.py --workspace /PERCORSO/ASSOLUTO/workspace --q \"$CLAUDE_USER_PROMPT\" --k 3"
          }
        ]
      }
    ]
  }
}
```

Sostituisci `/PERCORSO/ASSOLUTO/` con il percorso reale del tuo sistema.
Su Windows usa backslash o percorsi con `/` in stile Unix (Git Bash li accetta entrambi).

**Nota prestazioni:** il primo avvio carica il modello bge-m3 (~3-5s). Le esecuzioni
successive sono più rapide grazie alla cache di sentence-transformers.
Per workspace vuoti o wiki non inizializzati, lo script termina silenziosamente in <0.1s.

### OpenClaw — plugin `before_prompt_build`

OpenClaw non ha un meccanismo nativo per script shell pre-messaggio. L'iniezione di
contesto richiede un plugin TypeScript che registra l'hook `before_prompt_build`.
Un plugin pronto all'uso è incluso in questo repo in `plugins/wiki-context-plugin/`.

**Setup:**

```bash
cd plugins/wiki-context-plugin
npm install
npm run build
openclaw plugins install local:./plugins/wiki-context-plugin
```

**Configura** in OpenClaw (impostazioni plugin):

```json
{
  "wiki-context-plugin": {
    "workspace": "/percorso/assoluto/workspace",
    "wikiContextScript": "/percorso/assoluto/ai-wiki-system/scripts/wiki_context.py",
    "pythonExecutable": "python",
    "k": 3,
    "maxChars": 600
  }
}
```

Il plugin chiama `wiki_context.py` prima di ogni prompt e restituisce l'output come
`prependContext`, che OpenClaw inserisce prima del messaggio utente.
Fallisce sempre silenziosamente — un timeout o wiki vuoto non blocca mai il prompt.

> **Nota sul nome del campo evento:** Il campo TypeScript esatto che contiene il testo
> del messaggio utente nell'evento `before_prompt_build` può variare in base alla versione
> di OpenClaw. Il plugin prova `event.userMessage`, `event.prompt`, `event.currentPrompt`
> e `event.input` in ordine. Se il contesto wiki non viene mai iniettato, controlla i tipi
> SDK in `node_modules/openclaw` e aggiorna il nome del campo in `src/index.ts`.

### Comportamento con il contesto iniettato

Quando l'hook è attivo, ogni prompt utente arriva all'agente preceduto da un blocco:

```
<wiki-context>
Contesto wiki pre-caricato (top 3 pagine per rilevanza semantica):

### wiki/concepts/rag.md  [rilevanza: 0.91]
[contenuto pagina...]

### wiki-works/ricerca/synthesis/llm-memory.md  [rilevanza: 0.84]
[contenuto pagina...]
</wiki-context>
```

L'agente usa questo contesto direttamente — vedi `skills/wiki-core.md §injected-context`.
Se nessuna pagina è rilevante (wiki vuoto o rilevanza bassa), lo script non emette nulla
e il prompt arriva invariato.
