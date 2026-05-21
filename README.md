<div align="center">

# AI Wiki System

**Semantic long-term memory for AI agents**

Give your AI agent a wiki it actually maintains — not a flat note dump, but a structured, self-healing knowledge base where every page is simultaneously a readable document and a searchable vector.

[![Version](https://img.shields.io/badge/version-1.1.0-informational)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/tests-37%20passed-brightgreen)](tests/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-AGPL--3.0-blue)](LICENSE)
[![OpenClaw](https://img.shields.io/badge/works%20with-OpenClaw-purple)](https://github.com/openclaw/openclaw)

[Getting Started](#getting-started) · [OpenClaw Integration](#openclaw-integration) · [How It Works](#how-it-works) · [Documentation](#documentation)

---

</div>

## The problem

AI agents forget everything between sessions. Personal memory systems exist, but they're flat and unstructured — a pile of facts, not a knowledge base.

When you work on recurring research (trading signals, academic literature, competitive analysis, legal cases), you need something more: **organized, interconnected, semantically searchable knowledge** that persists and grows over time.

## What AI Wiki System does

AI Wiki System gives your agent a two-level wiki it can maintain autonomously:

- **`wiki/`** — permanent, curated knowledge (entities, concepts, synthesis pages)
- **`wiki-works/<project>/`** — active research per domain (raw sources + structured pages)

The agent ingests content, queries it with vector search, detects stale or broken knowledge, and synthesizes new pages when multiple sources support a non-obvious inference — all without corrupting the knowledge base even if a process crashes mid-operation.

```
User: "study this paper on RAG architectures"

Agent: [INTENT: INGEST | WORKSPACE: research | CONFIDENCE: high]
       → fetches content, writes structured pages as .tmp files
       → calls wiki.py ingest (atomic commit: staging → production)
       → embeddings written to LanceDB in the same atomic operation
       → "2 pages written. 1 conflict resolved. Mini-lint: ok."

User: "what do you know about retrieval-augmented generation?"

Agent: [INTENT: QUERY | WORKSPACE: research | CONFIDENCE: high]
       → semantic vector search across embedded wiki pages
       → reads relevant pages, synthesizes with citations
       → if synthesis meets threshold → auto-saves as new wiki page + embeddings
```

---

## The core architectural idea: wiki and vector DB as one

> **Karpathy's original pattern** ([gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)) assumed the LLM would navigate the wiki by *reading* its markdown files — essentially visual inspection of a directory structure. This works for small wikis but breaks down at scale: the agent cannot scan dozens of pages on every query.

AI Wiki System solves this with a **dual-representation architecture**: every wiki page is two things at once.

```
  Write a wiki page
        │
        ▼
┌───────────────────┐     ┌──────────────────────────┐
│  Markdown file    │     │  LanceDB vector store     │
│  wiki/concepts/   │◄────►  bge-m3 embeddings        │
│  rag.md           │     │  (1024-dim, HNSW index)   │
└───────────────────┘     └──────────────────────────┘
   humans navigate             LLM retrieves
   LLM generates               semantically
```

The markdown file and its embeddings are **written atomically in the same operation** and kept in sync at all times. When a page is updated, the vectors are re-embedded. When a page is deleted, its vectors are removed. The lint pass detects and repairs any drift.

This means:

- **The agent never scans files to answer a query.** It calls `wiki.py query`, which runs a vector similarity search and returns the most relevant pages — even when the query has no keyword overlap with the content.
- **The wiki is always queryable without re-indexing.** There is no "build the index" step. The vector DB is the index, maintained continuously.
- **Navigation and retrieval serve different purposes.** Humans browse the markdown; the LLM retrieves via vectors. Both views are always consistent.

A query about *"how LLMs handle long context"* retrieves pages about *"positional encoding"* and *"sliding window attention"* — without any keyword overlap — because the meaning is close in embedding space.

---

## Key features

### Semantic vector search
Uses [bge-m3](https://huggingface.co/BAAI/bge-m3) embeddings (multilingual, 1024-dim, HNSW index). Queries retrieve by meaning, not keywords.

### Atomic writes — crash-safe
Every ingest follows a `.tmp → staging LanceDB → atomic promotion` pattern. A crash mid-operation leaves the system in a detectable state (`status: in-progress` in `wiki-session.md`). The agent recovers gracefully at the next session without silent data corruption.

### Multi-project routing
Define multiple research domains in `wiki.config.json` with keyword lists. The agent auto-selects the right workspace from message content — no need to specify it manually.

### Automatic synthesis
When a query response integrates ≥2 wiki sources, exceeds 300 tokens, and adds non-literal inference, the agent saves it as a new wiki page — with its embeddings written atomically. Knowledge compounds over time.

### Self-healing lint
`wiki.py lint --full` detects and repairs:
- **Broken wiki links** (`[[page]]` with no matching file)
- **Orphan LanceDB entries** (vectors for deleted files — auto-removed)
- **Renames** (file moved → updates DB path without re-embedding, using `content_hash` comparison)
- **Semantic duplicates** (cosine similarity > 0.95 across pages)

### Token-budget index
`index.md` respects a configurable token budget (default 4000). When exceeded, it applies reduction strategies automatically — so the agent can navigate the wiki even on small context windows.

### Pre-prompt context injection *(v1.1)*
`wiki_context.py` runs a vector search **before every user message reaches the agent** and prepends a `<wiki-context>` block with the most relevant pages. This eliminates the main failure mode of skill-based approaches: instruction drift causing the agent to skip the wiki entirely on non-QUERY intents.

```
User types a message
        │
        ▼
wiki_context.py runs vector search
        │
        ▼
<wiki-context> block prepended to the prompt
        │
        ▼
Agent always has relevant context — regardless of intent classification
```

Wire it as a `UserPromptSubmit` hook (Claude Code) or a `before_prompt_build` TypeScript plugin (OpenClaw). See [`AGENTS_PATCH.md`](AGENTS_PATCH.md) for exact configuration. The script always exits 0 — it never blocks a prompt.

---

## Architecture

```
workspace/
├── skills/
│   └── wiki-core.md          ← permanent skill: intent classification, workflows
├── wiki-session.md           ← live session state (generated by wiki.py)
├── wiki.config.json          ← configuration
├── scripts/
│   ├── wiki.py               ← unified CLI entry point
│   ├── wiki_context.py       ← pre-prompt context injector (hook)
│   ├── wiki_embed.py         ← boundary-aware chunking + bge-m3 embeddings
│   ├── wiki_lancedb.py       ← LanceDB ops (upsert, staging, rename detection)
│   └── wiki_index.py         ← token-budget index generation
├── wiki/                     ← permanent knowledge base
│   ├── entities/             ← people, tools, organizations
│   ├── concepts/             ← theories, strategies, definitions
│   └── synthesis/            ← cross-source inferences
├── wiki-works/               ← active research (per project)
│   └── <project>/
│       ├── raw/              ← raw fetched sources (not indexed)
│       ├── entities/
│       ├── concepts/
│       └── synthesis/
└── memory/
    └── lancedb/              ← vector database (git-ignored, rebuildable)
```

**Core invariant:** The agent never writes directly to the wiki. Everything goes through `wiki.py`. The skill guides *when* and *why*; the scripts handle *how*.

---

## OpenClaw Integration

[OpenClaw](https://github.com/openclaw/openclaw) is a self-hosted AI agent gateway that connects messaging channels (Telegram, Discord, web) to AI agents with tool access: `bash`, `read`, `write`, `edit`, `browser` on the host filesystem.

AI Wiki System is designed as a first-class OpenClaw extension:

### Setup (5 minutes)

**1. Copy the skill to your workspace**
```
<workspace>/skills/wiki-core.md
```

**2. Add to your `AGENTS.md`**
```
At the start of every session, read <workspace>/wiki-session.md for current wiki state.
Before any wiki operation, re-read skills/wiki-core.md to verify the protocol.
```

The second line forces the agent to reload the rules before acting — not just at session start — mitigating instruction drift on long context windows.

**3. Configure your projects**
```json
{
  "workspace": "/path/to/your/workspace",
  "projects": {
    "trading": {
      "path": "wiki-works/trading",
      "keywords": ["markets", "indicators", "trading", "stocks", "ticker"]
    },
    "research": {
      "path": "wiki-works/research",
      "keywords": ["paper", "study", "systematic review", "article"]
    }
  }
}
```

**4. Initialize**
```bash
py scripts/wiki.py rebuild --workspace /path/to/your/workspace
```

**5. (Recommended) Wire context injection**

See [`AGENTS_PATCH.md`](AGENTS_PATCH.md) for the full hook configuration. Quick version for Claude Code — add to `.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "py /ABSOLUTE/PATH/scripts/wiki_context.py --workspace /ABSOLUTE/PATH/workspace --q \"$CLAUDE_USER_PROMPT\" --k 3"
      }]
    }]
  }
}
```

This makes the agent consult the wiki on **every** prompt — not only when it classifies the message as a QUERY.

### What the agent does automatically

| User says | Agent does |
|-----------|-----------|
| URL / "study this" / file | INGEST: fetch → structure → atomic write + embed |
| Direct question / "explain" | QUERY: vector search → read pages → synthesize |
| "check the wiki" / "maintenance" | LINT: broken links, orphans, renames, semantic duplicates |
| Ambiguous | Asks one clarifying question, never guesses |

The agent always emits a classification line before acting:
```
[INTENT: INGEST | WORKSPACE: trading | CONFIDENCE: high]
```
You can correct it before execution.

### Session state

`wiki-session.md` (managed exclusively by `wiki.py`) tracks:
- Current status: `ok` / `in-progress` / `needs-repair`
- Last operation: type, timestamp, detail
- Active workspace and page count

If the agent finds `in-progress` at session start, it warns before doing anything — no silent state corruption.

---

## Origins & Inspiration

AI Wiki System is inspired by the **LLM Wiki Pattern** described by [Andrej Karpathy](https://karpathy.ai/) in his gist [*"llm-wiki: a pattern for persistent, LLM-maintained knowledge bases"*](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

Karpathy's core insight: instead of re-deriving knowledge on every query (classic RAG), an LLM should *maintain* a persistent wiki — a structured set of markdown files it builds, updates, and cross-references over time. The tedious part of maintaining a knowledge base is not the reading or the thinking — it's the bookkeeping. LLMs handle bookkeeping well; humans don't.

### How this project differs

| Dimension | Karpathy's pattern | AI Wiki System |
|-----------|-------------------|----------------|
| **Form** | Conceptual pattern — prose + guidelines | Full Python implementation with CLI |
| **Retrieval** | LLM reads/scans markdown files visually | Semantic vector search — LLM never scans files |
| **Wiki + vectors** | Separate concerns (or unaddressed) | One atomic operation: write page = write embeddings |
| **Crash safety** | Not addressed | Atomic `.tmp → staging → promotion` pipeline |
| **Multi-project** | Single wiki | Routed workspaces via `wiki.config.json` |
| **Knowledge compounding** | Query answers stay in chat | Auto-synthesis: saved as new wiki page + embeddings |
| **Lint** | Basic health check concept | 11-check self-healing: orphan vectors, semantic duplicates, renames |
| **Index management** | Manual `index.md` maintained by agent | Token-budget `index.md` generated on-demand |
| **Rename detection** | Not addressed | Content-hash comparison → path update without re-embedding |
| **Languages** | English-focused | Multilingual — bge-m3 supports 100+ languages |
| **Context injection** | Not addressed | `wiki_context.py` pre-injects relevant pages before every prompt |
| **Testing** | None | 37 automated tests |

### Key architectural differences

**Dual-representation by design** — Karpathy's pattern treats the wiki as a file system the agent reads. AI Wiki System treats every page as having two synchronized representations: markdown for humans and generation, vectors for retrieval. These are written together, maintained together, and linted together. There is no gap between "what's in the files" and "what's searchable."

**Two-level wiki** — Karpathy proposes a single wiki directory. AI Wiki System separates permanent curated knowledge (`wiki/`) from active project research (`wiki-works/<project>/`). Research noise never pollutes the stable knowledge base.

**No direct agent writes** — The agent never writes to the wiki directly. Everything goes through `wiki.py`. This single invariant eliminates the class of corruption bugs where agents write partial or malformed pages.

---

## Getting Started

### Requirements

**Python 3.10+** — required for modern type hints and structural pattern matching.

**~2 GB disk** — for the BAAI/bge-m3 embedding model, downloaded automatically on first run via `sentence-transformers`.

**Python dependencies** (`pip install -r requirements.txt`):

| Package | Version | Purpose |
|---------|---------|---------|
| `lancedb` | ≥ 0.6.0 | Vector database — stores and queries bge-m3 embeddings; provides the staging table for atomic ingest |
| `sentence-transformers` | ≥ 3.0.0 | Loads and runs BAAI/bge-m3 locally; handles multilingual chunked embedding |
| `pyarrow` | ≥ 14.0.0 | Columnar storage format required by LanceDB for batch operations and schema enforcement |
| `pandas` | ≥ 2.0.0 | DataFrame operations used in bulk embedding, lint statistics, and rename-detection comparisons |
| `pytest` | ≥ 8.0.0 | Test runner — 37 automated tests covering ingest atomicity, query routing, lint, and CLI output |
| `pyyaml` | ≥ 6.0 | Parses `wiki.config.json` and YAML frontmatter in wiki pages |
| `requests` | ≥ 2.31.0 | HTTP fetching used during source ingestion to retrieve external content |

### Install

```bash
git clone https://github.com/giovannifrontera/ai-wiki-system
cd ai-wiki-system
pip install -r requirements.txt
```

### Configure

```bash
cp wiki.config.json my-workspace/wiki.config.json
# Edit: set workspace path, add your projects and keywords
```

### Initialize

```bash
py scripts/wiki.py rebuild --workspace my-workspace/
```

### Run tests

```bash
pytest tests/ -v
# Expected: 37 passed
```

---

## CLI Reference

```
wiki.py <command> [arguments]

  ingest         --workspace <path> --pages <p1.tmp,p2.tmp,...> --log <str>
  query          --workspace <path> --q <string> [--k 5]
  lint           --workspace <path> [--full]
  index          --workspace <path>
  rebuild        --workspace <path>
  session-update --workspace <path> --op <type> --status <ok|failed|in-progress> [--detail <json>]

wiki_context.py [hook — outputs <wiki-context> block to stdout]

  --workspace    <path>    workspace containing wiki.config.json
  --q            <string>  query text (the user's prompt)
  --k            <int>     number of pages to return (default: 3)
  --max-chars    <int>     max characters per page excerpt (default: 600)
```

Every command outputs JSON to stdout:

```json
{ "status": "ok", "op": "ingest", "pages_written": 2, "conflicts": [], "mini_lint": "ok" }
{ "status": "error", "code": "lock_exists", "message": "Previous operation did not complete", "recoverable": true }
{ "status": "conflict", "level": 3, "page": "concepts/rag.md", "detail": "..." }
```

Conflict level 3 (semantic contradiction between sources) blocks page promotion and asks for human resolution.

---

## How It Works

### Chunking

Pages are split using the bge-m3 native tokenizer (not character approximation). Boundaries respect `##` and `###` headings — chunks never cut mid-section. Pages under 1500 tokens are embedded whole; larger pages are chunked at 512 tokens with 64-token overlap.

### Upsert semantics

`upsert(path, chunks)` deletes **all** existing chunks for that path before inserting new ones. This prevents orphan chunks when a page changes its chunk count.

### Rename detection

During lint, the system compares `content_hash` between DB-only paths and filesystem-only paths. Matching hashes = rename detected → path updated in DB without re-embedding.

### Staging table

Ingest writes vectors to `staging_wiki_pages` first. Only `promote_staging()` moves them to `wiki_pages`. A crash leaves staging populated; the next session detects and clears it silently, then logs the event.

---

## Documentation

| File | Contents |
|------|----------|
| [`DESIGN.md`](DESIGN.md) | Full architecture, workflow specs, LanceDB schema, conflict resolution |
| [`SPEC.md`](SPEC.md) | Implementation spec, error states table, OpenClaw integration detail |
| [`skills/wiki-core.md`](skills/wiki-core.md) | The skill file to install in your agent |
| [`AGENTS_PATCH.md`](AGENTS_PATCH.md) | Exact text to add to your `AGENTS.md` |
| [`README.it.md`](README.it.md) | Documentazione in italiano |

---

## Changelog

### v1.1.0 — 2026-05-21

**New: Pre-prompt context injection**
- `scripts/wiki_context.py` — new script that runs a vector search before every prompt and prepends a `<wiki-context>` block. Eliminates instruction drift as a failure mode: the agent always has relevant wiki context regardless of intent classification.
- `skills/wiki-core.md` — new `§injected-context` section; checklist updated to prioritize the pre-injected block over manual `wiki.py query` calls.
- `AGENTS_PATCH.md` — added hook configuration for Claude Code (`UserPromptSubmit`) and OpenClaw (`before_prompt_build` plugin).
- `plugins/wiki-context-plugin/` — ready-to-use TypeScript plugin for OpenClaw.

**Bug fixes**
- **[CRITICAL]** `wiki_index.py`: `_build_full()` and `_build_slugs_only()` referenced `wiki_dir` as an implicit global — a local variable from the caller. Every call to `rebuild_index()` (INGEST, INDEX commands) crashed with `NameError`. Fixed by adding `wiki_dir` as an explicit parameter.
- **[MEDIUM]** `wiki_workflows.py`: `cmd_index` wrote `index.md` without ensuring `wiki/` existed, causing `FileNotFoundError` on fresh workspaces. Fixed with `os.makedirs(wiki_dir, exist_ok=True)`.
- **[LOW]** `wiki_context.py`: emptiness check loaded the entire LanceDB table into a pandas DataFrame. Removed — empty search results are already handled downstream.

---

## License

AGPL-3.0 — requires anyone who distributes or runs the software as a service to share the source code.

---

<div align="center">

Built to work with [OpenClaw](https://github.com/openclaw/openclaw) · Embeddings by [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3) · Vector store by [LanceDB](https://lancedb.github.io/lancedb/)

</div>
