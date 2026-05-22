# AGENTS.md Patch

Add these lines at the end of the operative instructions section in your `AGENTS.md`:

---

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

---

## Wiki Context Injection

When context injection is active, every prompt arrives preceded by a block like:

```
<wiki-context>
Pre-loaded wiki context (top 3 pages by semantic relevance):

### wiki/concepts/rag.md  [relevance: 0.91]
[page content...]

### wiki-works/research/synthesis/llm-memory.md  [relevance: 0.84]
[page content...]
</wiki-context>
```

Use this block directly as the starting context for your response — it is already the
most relevant knowledge from the wiki for this prompt. Do not run `wiki.py query` again
for the same query; that would be redundant. If the block is absent, proceed normally
with the checklist in `skills/wiki-core.md`.

---

## PDF Inbox

When the user sends a PDF file in chat or provides a file path/URL:
```
wiki.py ingest-pdf --workspace <workspace> --file <path|url>
```
Never save PDF files manually or write directly to `wiki-works/`.

To process all PDFs added to the inbox since the last session:
```
wiki.py scan-inbox --workspace <workspace>
```

Files deposited in `wiki-works/<project>/raw/` with `source: pdf` in their frontmatter are raw extracted text — not finished wiki pages. Always structure them into `.tmp` pages before calling `wiki.py ingest`.

After `scan-inbox` completes, check `wiki-session.md` — the "last operation" section lists which raw files are ready for structuring.
