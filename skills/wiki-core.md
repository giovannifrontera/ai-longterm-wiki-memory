---
name: wiki-core
description: AI Agent wiki protocol — intent classification, INGEST/QUERY/LINT workflows, mandatory checklist, context injection
---

# Wiki Core — AI Agent Protocol

This document defines how you manage the knowledge wiki. Follow it **always** before responding to any message that may relate to the wiki.

## §injected-context — Pre-injected context (highest priority)

If the prompt contains a `<wiki-context>...</wiki-context>` block, it means
`wiki_context.py` already ran a vector search **before** the message reached you.
In this case:

- **USE the injected context** as the primary basis for your response
- **DO NOT run** `wiki.py query` again — it would be redundant
- For INGEST: compare the new content against the pages in the block to detect conflicts
- For AMBIGUOUS: use the context to disambiguate intent without asking
- If the block shows `[relevance: X]` below 0.4 on all pages → the wiki has no relevant
  knowledge: proceed without it and consider whether INGEST is appropriate

If the `<wiki-context>` block is **not present** (hook not configured or empty wiki):
fall back to the manual §query workflow.

## Pre-action checklist (mandatory)

Before responding to any message:

```
1. Read wiki-session.md → check the "status" field
2. If status = "in-progress" or "needs-repair" → warn the user BEFORE anything else
3. Is <wiki-context> present in the prompt? → yes: use §injected-context | no: go to step 4
4. Classify the intent of the message (see §classification)
5. Does the message contain more than one intent? If so, handle them in sequence, one at a time
6. Emit the classification line:
   [INTENT: X | WORKSPACE: Y | CONFIDENCE: high/medium/low]
7. If CONFIDENCE = low → ask the user for confirmation with ONE short line
8. If CONFIDENCE = high or medium → proceed with the workflow
```

## §classification — How to recognise intent

| Signal in the message | Intent |
|-----------------------|--------|
| "study this", "save", "I found", "read this", bare URL, attached file, "add to wiki" | INGEST |
| Direct question, "what do you know about", "tell me", "explain", "how does X work" | QUERY |
| "check the wiki", "cleanup", "lint", "maintenance", "check links" | LINT |
| Everything else | AMBIGUOUS → ask for confirmation |

**Confirmation for AMBIGUOUS:** one line only, never long:
> "Do you want me to save this to the wiki, or are you just sharing?"

## §pdf-inbox — PDF ingestion workflow

When the user sends a PDF (attachment, file path, or URL):

1. Call `wiki.py ingest-pdf --workspace <path> --file <path|url>`
   Never write directly to `wiki-works/` or save the file manually.
2. The command copies the PDF to `pdf-inbox/` and extracts its text automatically.
   Output: `{"status": "ok", "op": "scan-inbox", "processed": N, "skipped": N, "failed": N, "deposited": ["wiki-works/<project>/raw/<name>.md", ...], "failures": [...]}`
   If `failed > 0`, session status is `partial-failure` — check `failures` for details.
3. For each path listed in `deposited`, read the file directly (path is relative to workspace).
   This file contains raw extracted text — it is NOT a finished wiki page.
4. Structure the raw text into `.tmp` wiki pages (entities, concepts, synthesis as appropriate).
5. Call `wiki.py ingest --workspace <path> --pages <list> --log "INGEST | <pdf name>"`

To check for new PDFs added to the inbox since the last session:
- Call `wiki.py scan-inbox --workspace <path>`
- Read `wiki-session.md` — the "last operation" section lists which raw files are ready.

Files in `raw/` with `source: pdf` frontmatter are always raw extracted text.
Always structure them before calling `wiki.py ingest`.

## §workspace — Automatic project selection

1. Read `wiki.config.json` → `projects` list with keywords
2. Count matches between message keywords and each project's keywords
3. Project with most matches → selected
4. If two projects tie → ask the user (one line)
5. If no matches → use the main `wiki/`

## §ingest — INGEST workflow

Execute these steps in exact order:

**Phase A — Research (you):**
1. `web_search` for 5-10 candidate sources
2. Apply quality filter (DESIGN.md §quality-filter): discard sources below score 6
3. `web_fetch` the promoted sources → save in `<workspace>/wiki-works/<project>/raw/YYYY-MM-DD-slug.md`
4. Read the sources, identify key points and conflicts with existing wiki content

**Phase B — Writing (you → then wiki.py):**
1. Write new pages as `.tmp` files in the correct directories:
   - Entities (people, companies, tools) → `entities/<slug>.md.tmp`
   - Concepts, theories, strategies → `concepts/<slug>.md.tmp`
   - Synthesis and cross-source inferences → `synthesis/<slug>.md.tmp`
2. Call wiki.py for the atomic commit:
   ```bash
   py scripts/wiki.py ingest \
     --workspace <path> \
     --pages <p1.tmp,p2.tmp,...> \
     --log "ingest | <title>"
   ```
3. Read the JSON output → if `status: error` → warn the user with the message
4. If `mini_lint: failed` → warn the user

**Phase C — Report:**
Summarise in chat: sources used, pages created, conflicts resolved.

## §query — QUERY workflow

**If `<wiki-context>` is already present in the prompt** (hook active): skip steps 1-3,
use the injected pages directly as the base. Go to step 4.

**If `<wiki-context>` is not present** (manual fallback):
1. Check if index.md is stale:
   ```bash
   py scripts/wiki.py index --workspace <path>
   ```
2. Search the wiki with a vector query:
   ```bash
   py scripts/wiki.py query --workspace <path> --q "<question>" --k 5
   ```
3. Read the pages in the results (use `read`)

**Always:**
4. Also consult your personal memory using your own mechanisms
5. Synthesise the response with references `[page](path)`
6. **Synthesis criteria:** if the response synthesises ≥2 wiki sources, exceeds 300 tokens, and adds non-literal inference → save it as a wiki page via INGEST

## §lint — LINT workflow

```bash
py scripts/wiki.py lint --workspace <path> --full
```

Read the JSON output and present the issues found to the user.
Lint resolves automatically: orphan entries, renames, stale vectors.
For broken links and duplicates: present the options to the user.

## §synthesis-rule — When to create a wiki page

Create a wiki page ONLY if it meets **all** of these criteria:
- Synthesises ≥2 distinct wiki sources (not personal memory)
- Length ≥300 tokens
- Adds inference not literally present in any single source

**DO NOT create** if:
- It summarises a single source (goes in raw/)
- It duplicates an existing page
- It contains claims without a source

## §session — Session management

- At the start of every session: read `wiki-session.md`
- Never modify `wiki-session.md` directly: always use `wiki.py session-update`
- If you find `status: in-progress`: warn the user before any operation
