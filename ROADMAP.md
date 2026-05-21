# Roadmap — AI Wiki System

Future development ideas, not yet scheduled. Ordered by estimated priority.

---

## [DONE] Pre-prompt context injection — v1.1.0

**Status:** Released in v1.1.0 (2026-05-21)

`wiki_context.py` runs a vector search before every user prompt and injects the relevant pages as a `<wiki-context>` block. Wired as a `UserPromptSubmit` hook (Claude Code) or pre-hook (OpenClaw). See `AGENTS_PATCH.md`.

---

## [PLANNED] MCP Scientific Database Integration

**Status:** Under evaluation
**Effort:** Medium (skill + templates only, no changes to Python scripts)

### Problem

The current INGEST workflow uses `web_search` + `web_fetch` to retrieve content. For academic papers this produces raw HTML: inconsistent formatting, scattered metadata, no citation structure.

### Solution

Add a `RESEARCH_INGEST` intent to `wiki-core.md` that uses MCP tools for scientific databases when available:

| MCP Server | Database | Coverage |
|------------|----------|----------|
| `mcp__pubmed` | PubMed / MEDLINE | Medicine, biology, life sciences |
| `mcp__semantic-scholar` | Semantic Scholar | Computer science, AI, interdisciplinary |
| `mcp__eric` | ERIC | Education, pedagogy, school psychology |
| `mcp__ricerca-italia` | OpenAIRE | European research, Italian Open Access |

### How it would work

**Intent recognition:**

| Signal | Intent |
|--------|--------|
| Bare DOI (`10.xxxx/...`), PMID, "search pubmed", "find paper on", "studies on", article title | RESEARCH_INGEST |

**`§research-ingest` workflow:**

```
1. Identify the most appropriate database from context (topic, source type)
2. Call the MCP tool with query/DOI/PMID
3. Receive structured metadata: title, authors, abstract, year, DOI, citations
4. Optional: retrieve full text if available (mcp__pubmed__get_paper_fulltext)
5. Write .tmp pages using academic template (see below)
6. Call wiki.py ingest as usual (no changes to scripts)
```

**Paper page template:**

```markdown
---
type: paper
doi: 10.xxxx/...
authors: [Last, First; ...]
year: 2024
journal: Journal name
keywords: [keyword1, keyword2]
source_db: pubmed | semantic-scholar | eric | openaire
---

# Article title

## Abstract
[full abstract]

## Main contribution
[summary of the contribution — written by the agent]

## Methods
[if relevant]

## Limitations
[if stated]

## Key citations
- [[cited-paper-1-slug]]
- [[cited-paper-2-slug]]

## Links
- DOI: https://doi.org/10.xxxx/...
- Source: [database]
```

**Automatically generated side pages:**

- `entities/authors/<last-first>.md` — author profile with list of wiki papers
- `entities/journals/<journal-slug>.md` — journal with impact factor and paper list
- Bidirectional citation links — created by LINT if missing

### Portability

MCP tools are only available if configured in OpenClaw. The skill must handle the fallback:

```
If mcp__pubmed not available → use web_search on pubmed.ncbi.nlm.nih.gov
If mcp__semantic-scholar not available → use web_fetch on api.semanticscholar.org
```

No changes to Python scripts — `wiki.py ingest` remains identical.

### Files to modify

- `skills/wiki-core.md` — add `§research-ingest` block
- `skills/wiki-research.md` *(new)* — optional skill loadable separately with detailed workflows per database
- `SPEC.md` — add §research-ingest section
- `README.md` — "Academic Research" section

---

## [IDEA] Interactive conflict resolution via chat

**Status:** Rough idea
**Effort:** High

Today a Level 3 conflict (semantic contradiction between sources) blocks the merge and waits for human input. The agent could present both versions in chat with a structured UI (option A / option B / manual merge) instead of a generic message.

---

## [IDEA] PRISMA-ready export

**Status:** Rough idea
**Effort:** Medium

For systematic reviews: a `wiki.py export --format prisma --workspace wiki-works/research` command that generates a PRISMA table from all ingested papers, with fields: author, year, title, source database, inclusion/exclusion criteria (if tagged in the pages).

---

## [IDEA] wiki-works → wiki automatic promotion

**Status:** Rough idea
**Effort:** Low

`wiki.py promote --page wiki-works/trading/concepts/momentum.md` that moves a page from wiki-works/ to wiki/, updates all internal links, and logs `promote` in log.md. Today the process is manual.

---

*Updated: 2026-05-21*
