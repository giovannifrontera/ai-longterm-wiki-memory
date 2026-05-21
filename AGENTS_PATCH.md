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

## Context Injection (recommended)

To prevent instruction drift and ensure the wiki is consulted on **every** prompt
— not only when classified as QUERY — configure `wiki_context.py` as a pre-prompt hook.
Wiki context is injected automatically before the message reaches the agent,
without depending on the checklist.

### Claude Code — `UserPromptSubmit` hook

Add to `.claude/settings.json` (or `settings.local.json`) in your workspace:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "py /ABSOLUTE/PATH/scripts/wiki_context.py --workspace /ABSOLUTE/PATH/workspace --q \"$CLAUDE_USER_PROMPT\" --k 3"
          }
        ]
      }
    ]
  }
}
```

Replace `/ABSOLUTE/PATH/` with the real path on your system.
On Windows you can use forward slashes (`/`) — Git Bash accepts both.

**Performance note:** the first run loads the bge-m3 model (~3-5s). Subsequent runs are
faster thanks to sentence-transformers caching.
For empty workspaces or uninitialised wikis, the script exits silently in <0.1s.

### OpenClaw — `before_prompt_build` plugin

OpenClaw does not have a native shell pre-hook mechanism. Context injection requires
a TypeScript plugin that registers the `before_prompt_build` hook.
A ready-to-use plugin is included in this repo at `plugins/wiki-context-plugin/`.

**Setup:**

```bash
cd plugins/wiki-context-plugin
npm install
npm run build
openclaw plugins install local:./plugins/wiki-context-plugin
```

**Configure** in OpenClaw (plugin settings):

```json
{
  "wiki-context-plugin": {
    "workspace": "/absolute/path/to/workspace",
    "wikiContextScript": "/absolute/path/to/ai-wiki-system/scripts/wiki_context.py",
    "pythonExecutable": "python",
    "k": 3,
    "maxChars": 600
  }
}
```

The plugin calls `wiki_context.py` before every prompt and returns the output as
`prependContext`, which OpenClaw inserts before the user message.
It always fails silently — a timeout or empty wiki never blocks the prompt.

> **Note on the event field name:** The exact TypeScript field that holds the user's
> message text in the `before_prompt_build` event may vary by OpenClaw version. The
> plugin tries `event.userMessage`, `event.prompt`, `event.currentPrompt`, and
> `event.input` in order. If the wiki context is never injected, check the SDK types
> in your `node_modules/openclaw` and update the field name in `src/index.ts`.

### Behaviour with injected context

When the hook is active, every user prompt arrives preceded by a block like:

```
<wiki-context>
Pre-loaded wiki context (top 3 pages by semantic relevance):

### wiki/concepts/rag.md  [relevance: 0.91]
[page content...]

### wiki-works/research/synthesis/llm-memory.md  [relevance: 0.84]
[page content...]
</wiki-context>
```

The agent uses this context directly — see `skills/wiki-core.md §injected-context`.
If no pages are relevant (empty wiki or low relevance), the script emits nothing
and the prompt arrives unchanged.
