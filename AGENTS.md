# AGENTS.md — ai-wiki-system

This repo provides a long-term wiki memory system for AI agents.
It injects semantically relevant wiki pages into every prompt automatically.

## Installation

### If you are a Claude Code agent

Run from the repo root:

```
py scripts/install_claude_code_hook.py --workspace /absolute/path/to/your/workspace
```

The workspace is the directory that contains `wiki.config.json`.
The script installs a `UserPromptSubmit` hook in `.claude/settings.json` and skips silently if already present.
Restart Claude Code after installation.

### If you are an OpenClaw agent

Run from the repo root:

```
py scripts/setup_openclaw.py --workspace /absolute/path/to/your/workspace
```

The script auto-detects the OpenClaw config file and injects the plugin entry.
If auto-detection fails, pass the config path explicitly:

```
py scripts/setup_openclaw.py --workspace /path/to/workspace --config /path/to/openclaw/config.json
```

Restart OpenClaw after installation.

## First-time wiki setup

If the workspace does not exist yet, initialise it first:

```
py wiki.py init --workspace /path/to/workspace
```

Then ingest your first pages:

```
py wiki.py ingest --workspace /path/to/workspace --file /path/to/page.md
```

## Usage (once installed)

### Session start

At the start of every session:
1. Read `wiki-session.md` for the current wiki context
2. Before any wiki operation, re-read `skills/wiki-core.md` to verify the protocol

The wiki is your persistent brain. Use it actively:
- Every relevant piece of knowledge should be ingested into the wiki
- Every complex question should first be checked against the wiki
- Run LINT proactively every 2 weeks

Never write directly into the `wiki/` or `wiki-works/` directories.
Always use `wiki.py` for any write operation.

### Architecture (v3)

| Layer | Directory | Contents | Who writes |
|-------|-----------|----------|------------|
| **Identity** | `wiki/` | Who the agent is: values, style, learned behavioral patterns | Only `wiki.py self-reflect` |
| **Knowledge** | `wiki-works/<topic>/` | What the agent knows: concepts, research, competencies | INGEST workflow |

Pages never move between layers. Promotion does not exist in v3.

### Behavioral feedback (v3)

When the user corrects your behavior ("stop doing X", "always do Y", "never do Z"):

1. Log the correction:
   ```
   wiki.py behavior-log --workspace <path> --event "<canonical phrase>"
   ```
2. At end of session, run self-reflection:
   ```
   wiki.py self-reflect --workspace <path>
   ```
   This reads `.wiki-behavior-log.jsonl`, detects recurring patterns (≥3 occurrences), and autonomously updates `wiki/identity/`. Run it without asking the user.

### Lint — semantic duplicates (v3)

`wiki.py lint --full` now reports `semantic_duplicate` issues. Handle them:
- `action: auto_merge` (similarity ≥ 0.90): merge the two pages, ingest the merged version, delete originals
- `action: warn` (0.75–0.90): show the user and ask whether to merge

### Wiki context injection

When context injection is active, every prompt arrives preceded by a block like:

```
<wiki-context>
Pre-loaded wiki context (top 3 pages by semantic relevance):

### wiki/concepts/rag.md  [relevance: 0.91]
[page content...]
</wiki-context>
```

Use this block directly as the starting context — it is already the most relevant knowledge for this prompt. Do not run `wiki.py query` again for the same query; that would be redundant. If the block is absent, proceed normally with `skills/wiki-core.md`.

### Wiki dashboard (v2.2+)

When the server is running (`wiki.py serve`), a `[Stats]` tab is available at `http://localhost:7331`.

Check there for: embedding coverage, stale pages, top queried pages, lint status.

REST endpoints (auth-protected):
```
GET  /api/stats   → full observability snapshot as JSON
POST /api/lint    → trigger wiki.py lint --full (returns 409 if already running)
```

Auto-lint: add to `wiki.config.json` to lint automatically every N hours:
```json
{ "frontend": { "lint_interval_hours": 24 } }
```

### PDF inbox

When the user sends a PDF file in chat or provides a file path/URL:
```
wiki.py ingest-pdf --workspace <workspace> --file <path|url>
```

To process all PDFs added to the inbox since the last session:
```
wiki.py scan-inbox --workspace <workspace>
```

Files in `wiki-works/<project>/raw/` with `source: pdf` are raw extracted text — structure them into `.tmp` pages before calling `wiki.py ingest`.
