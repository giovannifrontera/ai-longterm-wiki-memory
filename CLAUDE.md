# CLAUDE.md — ai-wiki-system

> ## ⛔ STOP — READ THIS BEFORE ANYTHING ELSE
>
> **Every session, before any action:**
> 1. `Read wiki-session.md` — check current status
> 2. `Read skills/wiki-core.md` — load the full protocol
>
> These are local files, not plugins. Use the **Read tool**, not the Skill tool.
> If you see `<wiki-briefing>` in your context, it already contains the summary —
> but you must still Read skills/wiki-core.md for the full protocol.
>
> **If you see `<wiki-setup-required>`:**
> Do NOT call `Skill("wiki-setup")` — it is not a registered plugin.
> Instead: `Read skills/wiki-setup.md` and follow every step in order.

---

This repo provides a long-term wiki memory system that injects relevant wiki pages into every prompt via a `UserPromptSubmit` hook.

## Installation

```bash
py scripts/install_claude_code_hook.py --workspace /absolute/path/to/workspace
```

The workspace is the directory containing `wiki.config.json`.
The script writes hooks into `.claude/settings.json` and is idempotent.
Restart Claude Code after installation.

> **Windows note:** if `py` resolves to a Python that cannot import `lancedb`,
> pass the explicit executable: `py -c "import sys; print(sys.executable)"` then
> use `--python <that-path>`. The shebang `#!/usr/bin/env python3` may resolve
> to a different Python than `py -c`.

> **Double-execution warning:** Claude Code merges hooks from `~/.claude/settings.json` (global)
> and `<workspace>/.claude/settings.json` (local). If wiki hooks are present in both files,
> every prompt triggers two context injections. The install script detects this and prints a warning.
> Fix: `py scripts/install_claude_code_hook.py --workspace <WORKSPACE> --remove-global`

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--workspace` | required | Absolute path to the wiki workspace |
| `--k` | 3 | Number of wiki chunks to inject per prompt |
| `--python` | `py` / `python3` | Python executable (use absolute path on Windows) |
| `--global` | — | Install into `~/.claude/settings.json` instead of local |
| `--remove-global` | — | Remove wiki hooks from global settings before installing locally |
| `--dry-run` | — | Preview without writing |

## Architecture (v3) — three layers, one brain

| Layer | Directory | Contents | Who writes |
|-------|-----------|----------|------------|
| **Domain knowledge** | `wiki-works/<topic>/` | Deep knowledge per topic | INGEST workflow |
| **Distilled knowledge** | `wiki/` | Cross-domain knowledge | Agent (autonomous promotion) |
| **Identity** | `wiki/identity/` | Values, style, behavioral patterns | Only `wiki.py self-reflect` |

## PDF ingestion — CRITICAL workflow

Text extraction uses **pdfplumber** (already bundled in `wiki_pdf_watcher.py`).

```bash
wiki.py ingest-pdf --workspace <path> --file <path|url>
```

This deposits extracted raw text into `wiki-works/<project>/raw/`.

**After `ingest-pdf`, the agent must:**
1. Read each deposited file in `raw/`
2. Write structured `.tmp` pages (see `skills/wiki-core.md §ingest`)
3. Call `wiki.py ingest --workspace <path> --pages <file.tmp>`

## process-raw vs ingest — DO NOT CONFUSE

| Command | When to use |
|---------|-------------|
| `wiki.py ingest` | Always — agent writes `.tmp` pages, then calls this |
| `wiki.py process-raw` | ONLY for bulk re-indexing of raw files already in `raw/` — does NOT create structured wiki pages |

**Never use `process-raw` as a shortcut for the INGEST workflow.**

## Behavioral feedback

When the user corrects behavior:
```bash
wiki.py behavior-log --workspace <path> --event "<canonical phrase>"
```
At end of session, run autonomously if ≥1 correction received:
```bash
wiki.py self-reflect --workspace <path>
```

## Wiki context injection

When a `<wiki-context>` block is present, use it directly — do not run `wiki.py query` again.

## Dashboard

```bash
wiki.py serve --workspace <path> [--no-auth]
```

Opens at `http://localhost:7331`. Tabs: **Graf** (page graph) and **Stats**.
No semantic query UI — queries happen only via the hook.

<!-- ai-wiki-system:usage-start -->
## Wiki Knowledge System

**Every session — mandatory reads (use Read tool):**
1. `wiki-session.md` — current session state and last operation
2. `skills/wiki-core.md` — full agent protocol (INGEST, QUERY, LINT, BEHAVIOR_FEEDBACK)

The wiki is your persistent brain:
- Every relevant piece of knowledge → INGEST into wiki
- Every complex question → check wiki first
- Run LINT proactively every 2 weeks
- Never write directly to `wiki/` or `wiki-works/` — always use `wiki.py`

## Wiki Context Injection

Every prompt arrives preceded by:
```
<wiki-context>
Pre-loaded wiki context (top 3 pages by semantic relevance):
### wiki/concepts/rag.md  [relevance: 0.91]
[page content...]
</wiki-context>
```

Use this directly. Do not re-run `wiki.py query` for the same prompt.
If all relevance scores < 0.4 → wiki has no relevant knowledge, proceed normally.

## PDF Inbox

```bash
wiki.py ingest-pdf --workspace <path> --file <path|url>
wiki.py scan-inbox --workspace <path>
```

After depositing, follow the INGEST workflow in `skills/wiki-core.md §ingest`.
<!-- ai-wiki-system:usage-end -->
