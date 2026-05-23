# CLAUDE.md — ai-wiki-system

This repo provides a long-term wiki memory system that injects relevant wiki pages into every prompt via a `UserPromptSubmit` hook.

## Installation

Run from the repo root:

```
py scripts/install_claude_code_hook.py --workspace /absolute/path/to/your/workspace
```

The workspace is the directory containing `wiki.config.json`.
The script writes a hook into `.claude/settings.json` and is idempotent — safe to run multiple times.
Restart Claude Code after installation.

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--workspace` | required | Absolute path to the wiki workspace |
| `--k` | 3 | Number of wiki chunks to inject per prompt |
| `--python` | `py` / `python3` | Python executable |
| `--dry-run` | — | Preview without writing |

## Usage

Once installed, every prompt is automatically preceded by a `<wiki-context>` block containing the most relevant wiki pages. See `AGENTS_PATCH.md` for the full usage protocol.
