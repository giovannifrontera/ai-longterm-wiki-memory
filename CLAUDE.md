# CLAUDE.md — ai-wiki-system

> **MUST — Setup check (read before anything else)**
> If your context contains a `<wiki-setup-required>` block, invoke the `wiki-setup` skill **immediately** — before asking the user questions, before running any command, before any other action. The skill will guide you through the full setup step by step.

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

### Architecture (v3) — three layers, one brain

All layers are indexed together in LanceDB. The agent accesses everything through semantic search.

| Layer | Directory | Contents | Who writes |
|-------|-----------|----------|------------|
| **Domain knowledge** | `wiki-works/<topic>/` | Deep knowledge per topic: concepts, research, entities | INGEST workflow |
| **Distilled knowledge** | `wiki/` | Cross-domain knowledge, promoted autonomously | Agent (autonomous) |
| **Identity** | `wiki/identity/` | Values, style, learned behavioral patterns | Only `wiki.py self-reflect` |

Promote a page from `wiki-works/` to `wiki/` autonomously when it is relevant in ≥2 topics and retrieved in ≥3 queries. Use `wiki.py ingest` targeting `wiki/concepts/<slug>.md.tmp`.

### Behavioral feedback (v3)

When the user corrects your behavior:
```
wiki.py behavior-log --workspace <path> --event "<canonical phrase>"
```
At end of session, run autonomously (no user confirmation needed):
```
wiki.py self-reflect --workspace <path>
```

### Wiki context injection

When a `<wiki-context>` block is present, use it directly — do not run `wiki.py query` again for the same prompt.

### Dashboard (v2.2+)

`wiki.py serve` exposes a `[Stats]` tab at `http://localhost:7331` with embedding coverage, stale pages, lint status, and top queried pages.

### PDF inbox

```
wiki.py ingest-pdf --workspace <path> --file <path|url>
wiki.py scan-inbox --workspace <path>
```

<!-- ai-wiki-system:usage-start -->
## Wiki Knowledge System

At the start of every session:
1. Read `wiki-session.md` for the current wiki context
2. Before any wiki operation, re-read `skills/wiki-core.md` to verify the protocol

The wiki is your persistent brain. Use it actively:
- Every relevant piece of knowledge should be ingested into the wiki
- Every complex question should first be checked against the wiki
- Run LINT proactively every 2 weeks

Never write directly into the `wiki/` or `wiki-works/` directories.
Always use `wiki.py` for any write operation.

## Wiki Context Injection

When context injection is active, every prompt arrives preceded by a block like:

```
<wiki-context>
Pre-loaded wiki context (top 3 pages by semantic relevance):

### wiki/concepts/rag.md  [relevance: 0.91]
[page content...]
</wiki-context>
```

Use this block directly as the starting context — it is already the most relevant knowledge for this prompt. Do not run `wiki.py query` again for the same query; that would be redundant. If the block is absent, proceed normally with `skills/wiki-core.md`.

## Wiki Dashboard (v2.2+)

When the server is running (`wiki.py serve`), a `[Stats]` tab is available at `http://localhost:7331`.
Check there for: embedding coverage, stale pages, top queried pages, lint status.

REST endpoints (auth-protected):
- `GET  /api/stats` — full observability snapshot as JSON
- `POST /api/lint` — trigger lint (returns 409 if already running)

Auto-lint: add to `wiki.config.json`:
```json
{ "frontend": { "lint_interval_hours": 24 } }
```

## PDF Inbox

When the user sends a PDF file in chat or provides a file path/URL:
```
wiki.py ingest-pdf --workspace <workspace> --file <path|url>
wiki.py scan-inbox --workspace <workspace>
```
<!-- ai-wiki-system:usage-end -->
