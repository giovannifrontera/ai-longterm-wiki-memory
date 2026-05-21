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

### OpenClaw — pre-hook sul messaggio

Nel file di configurazione del tuo agente OpenClaw, aggiungi un pre-hook che esegue:

```bash
py /percorso/scripts/wiki_context.py \
  --workspace /percorso/workspace \
  --q "$MESSAGE_TEXT" \
  --k 3
```

L'output del comando viene prepended al messaggio utente prima che raggiunga l'LLM.

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
