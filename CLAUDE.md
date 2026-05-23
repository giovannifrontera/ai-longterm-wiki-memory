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

Once installed, every prompt is automatically preceded by a `<wiki-context>` block containing the most relevant wiki pages.

### Session start

At the start of every session:
1. Read `wiki-session.md` for the current wiki context
2. Before any wiki operation, re-read `skills/wiki-core.md` to verify the protocol

Never write directly into `wiki/` or `wiki-works/`. Always use `wiki.py`.

### Wiki context injection

When a `<wiki-context>` block is present, use it directly — do not run `wiki.py query` again for the same prompt.

### Dashboard (v2.2+)

`wiki.py serve` exposes a `[Stats]` tab at `http://localhost:7331` with embedding coverage, stale pages, lint status, and top queried pages.

### PDF inbox

```
wiki.py ingest-pdf --workspace <path> --file <path|url>
wiki.py scan-inbox --workspace <path>
```
