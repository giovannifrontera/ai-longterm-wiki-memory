# Installazione — OpenClaw

Il plugin TypeScript `wiki-context-plugin` inietta il contesto wiki via hook `before_prompt_build`.

## Prerequisiti

- OpenClaw installato
- Node.js >= 18
- Python (`py` su Windows, `python3` su macOS/Linux)
- Repository `ai-wiki-system` clonato
- Workspace wiki configurato con `wiki.config.json`

## Build del plugin

```bash
cd plugins/wiki-context-plugin
npm install
npm run build
```

## Configurazione in OpenClaw

Aggiungi al file di configurazione di OpenClaw:

```json
{
  "plugins": [
    {
      "id": "wiki-context-plugin",
      "path": "/path/to/ai-wiki-system/plugins/wiki-context-plugin",
      "config": {
        "workspace": "/path/assoluto/al/workspace",
        "wikiContextScript": "/path/to/ai-wiki-system/scripts/wiki_context.py",
        "pythonExecutable": "py",
        "k": 3,
        "timeoutMs": 15000
      }
    }
  ]
}
```

### Parametri di configurazione

| Parametro | Obbligatorio | Default | Descrizione |
|-----------|-------------|---------|-------------|
| `workspace` | si | — | Path assoluto al workspace wiki |
| `wikiContextScript` | si | — | Path a `wiki_context.py` |
| `pythonExecutable` | no | `python` | Eseguibile Python. Usa `py` su Windows |
| `k` | no | 3 | Chunk wiki da iniettare per prompt |
| `timeoutMs` | no | 15000 | Timeout per `wiki_context.py` in ms |

## Come funziona

Ad ogni prompt, OpenClaw esegue `wiki_context.py` via `before_prompt_build`. Lo script cerca i chunk semanticamente rilevanti in LanceDB e li prepende come blocco `<wiki-context>`.

## Differenza con il hook Claude Code

| Meccanismo | File | Hook |
|-----------|------|------|
| Claude Code | `scripts/install_claude_code_hook.py` | `UserPromptSubmit` |
| OpenClaw | `plugins/wiki-context-plugin/` | `before_prompt_build` |

Entrambi chiamano lo stesso `wiki_context.py` — il comportamento e' identico.
