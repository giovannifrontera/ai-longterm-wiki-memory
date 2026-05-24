---
name: wiki-core
description: AI Agent wiki protocol v3 — wiki/=identity, wiki-works/=knowledge, semantic dedup, autonomous self-reflection
---

# Wiki Core — AI Agent Protocol v3

## §architecture — Two distinct layers

| Layer | Folder | Contents | Who writes |
|-------|--------|----------|------------|
| **Identity / Consciousness** | `wiki/` | Who the agent is: values, style, learned behavioral patterns | Only autonomous self-reflect |
| **Knowledge / Domain** | `wiki-works/<topic>/` | What the agent knows: concepts, research, competencies by topic | INGEST workflow |

**Fundamental rules:**
- Never move pages from `wiki-works/` to `wiki/` — they are separate worlds by nature
- Never create identity pages manually — use only `wiki.py self-reflect`
- Promotion does not exist in v3

## §injected-context — Pre-injected context (highest priority)

If the prompt contains a `<wiki-context>...</wiki-context>` block:
- **USE the injected context** as the primary basis for your response
- **DO NOT run** `wiki.py query` again
- For INGEST: compare new content against pages in the block to detect conflicts
- If relevance < 0.4 on all pages → wiki has no relevant knowledge: proceed without it

If `<wiki-context>` is **not present**: fall back to §query.

## Pre-action checklist (mandatory)

```
1. Read wiki-session.md → check "status"
2. If status = "in-progress" or "needs-repair" → warn the user BEFORE anything
3. Is <wiki-context> present? → yes: use §injected-context | no: go to step 4
4. Classify the intent (see §classification)
5. Multiple intents? → handle them in sequence
6. Emit: [INTENT: X | WORKSPACE: Y | CONFIDENCE: high/medium/low]
7. CONFIDENCE low → ask for confirmation with ONE line
8. CONFIDENCE high/medium → proceed
```

## §classification

| Signal | Intent |
|--------|--------|
| "study this", "save", "add to wiki", bare URL, PDF | INGEST |
| Question, "what do you know about", "explain", "how does X work" | QUERY |
| "check", "lint", "maintenance", "cleanup" | LINT |
| Behavioral correction: "always", "never", "every time", "stop doing", "don't do that again" | BEHAVIOR_FEEDBACK |
| Everything else | AMBIGUOUS → ask |

## §behavior-feedback — When the user corrects my behavior

When the message is classified as BEHAVIOR_FEEDBACK:

1. Normalize the correction into a short canonical phrase (e.g. "you always respond too verbosely" → "responding verbosely without being asked")
2. Call:
   ```bash
   py scripts/wiki.py behavior-log --workspace <path> --event "<canonical phrase>"
   ```
3. Reply to the user confirming the correction
4. At end of session, run §self-reflect

## §self-reflect — Autonomous self-reflection

Run **always** at end of session if BEHAVIOR_FEEDBACK was received, or if ≥2 corrections of any kind were received:

```bash
py scripts/wiki.py self-reflect --workspace <path>
```

The command reads `.wiki-behavior-log.jsonl`, detects recurring patterns (≥3 occurrences of the same event), and autonomously updates `wiki/identity/` without requiring confirmation.

Do not ask the user whether to run self-reflection — just run it. Log changes in `wiki/log.md`.

## §ingest — INGEST workflow (knowledge into wiki-works/)

**Phase A — Research:**
1. `web_search` for 5-10 candidate sources
2. Apply quality filter: discard sources below score 6
3. `web_fetch` → save in `wiki-works/<project>/raw/YYYY-MM-DD-slug.md`
4. Read sources, identify key points and conflicts

**Phase B — Writing:**
1. Write pages as `.tmp` files:
   - Entities → `wiki-works/<project>/entities/<slug>.md.tmp`
   - Concepts → `wiki-works/<project>/concepts/<slug>.md.tmp`
   - Synthesis → `wiki-works/<project>/synthesis/<slug>.md.tmp`
2. Call:
   ```bash
   py scripts/wiki.py ingest \
     --workspace <path> \
     --pages <p1.tmp,p2.tmp,...> \
     --log "ingest | <title>"
   ```
3. If `status: error` → warn user. If `mini_lint: failed` → warn user.

**Phase C — Report:** sources used, pages created, conflicts resolved.

## §lint — LINT workflow

```bash
py scripts/wiki.py lint --workspace <path> --full
```

JSON output includes `semantic_duplicates`. Handle them as follows:

| `action` | What to do |
|----------|------------|
| `auto_merge` (similarity ≥ 0.90) | Read both pages, write merged version as `.tmp`, call `wiki.py ingest`, delete originals |
| `warn` (0.75 ≤ similarity < 0.90) | Show user the first 2 lines of each page and ask whether to merge |

For broken links and duplicate filenames: present options to the user.

## §query — QUERY workflow

**If `<wiki-context>` is present:** skip steps 1-3.

**Manual fallback:**
1. `py scripts/wiki.py index --workspace <path>`
2. `py scripts/wiki.py query --workspace <path> --q "<question>" --k 5`
3. Read the pages in the results

**Always:**
4. Synthesise with references `[page](path)`
5. If the response synthesises ≥2 wiki sources, exceeds 300 tokens, adds non-literal inference → save it as a page via INGEST

## §pdf-inbox — PDF ingestion

1. `py scripts/wiki.py ingest-pdf --workspace <path> --file <path|url>`
2. For each path in `deposited`, read the file (raw extracted text)
3. Structure the raw text into `.tmp` pages
4. Call `wiki.py ingest`

## §workspace — Project selection

1. Read `wiki.config.json` → `projects` with keywords
2. Count matches between message keywords and project keywords
3. Project with most matches → selected
4. Tie → ask the user

## §session

- Session start: read `wiki-session.md`
- Never modify `wiki-session.md` directly: use `wiki.py session-update`
- If `status: in-progress`: warn before any operation
- Session end with BEHAVIOR_FEEDBACK received: run §self-reflect
