# Installazione — Claude Code

L'hook `UserPromptSubmit` inietta automaticamente il contesto wiki prima di ogni prompt quando usi Claude Code.

## Prerequisiti

- Claude Code installato
- Python (`py` su Windows, `python3` su macOS/Linux)
- Repository `ai-wiki-system` clonato
- Workspace wiki creato e configurato con `wiki.config.json`

## Installazione

```bash
py scripts/install_claude_code_hook.py --workspace /path/assoluto/al/workspace
```

Su macOS/Linux:
```bash
python3 scripts/install_claude_code_hook.py --workspace /path/to/workspace
```

### Opzioni

| Opzione | Default | Descrizione |
|---------|---------|-------------|
| `--workspace` | (obbligatorio) | Path assoluto al workspace wiki |
| `--k` | 3 | Numero di chunk wiki da iniettare per prompt |
| `--python` | `py` / `python3` | Eseguibile Python |
| `--dry-run` | — | Mostra il risultato senza scrivere |

## Verifica

```bash
py scripts/install_claude_code_hook.py --workspace /path --dry-run
```

Riavvia Claude Code dopo l'installazione per attivare l'hook.

## Come funziona

Ad ogni prompt, Claude Code esegue `wiki_context.py` in background. Lo script:
1. Codifica il prompt come vettore (bge-m3)
2. Cerca i chunk più rilevanti in LanceDB
3. Prepende un blocco `<wiki-context>` al prompt con i chunk trovati

## Escludere file dall'indice

Aggiungi pattern in `wiki.config.json`:
```json
"exclude_from_index": ["wiki/drafts/*.md", "wiki/archive/*.md"]
```

**Nota**: i pattern usano `fnmatch` (non glob ricorsivo). `wiki/sub/**` matcha solo un livello — usa pattern espliciti come `wiki/sub/*.md`.
