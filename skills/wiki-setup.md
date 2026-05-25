---
name: wiki-setup
description: Step-by-step installation of ai-wiki-system. Rigid skill — follow every step in order without skipping.
type: rigid
---

# Wiki Setup — Guided Installation

**IMPORTANT: This is a rigid skill. Execute every step in the order shown. Do not skip or reorder.**

## Pre-check: identify your platform

- [ ] You are on **Claude Code** → follow §claude-code
- [ ] You are on **OpenClaw** → follow §openclaw

---

## §claude-code — Setup for Claude Code

### Step CC-1: Verify Python dependencies

```bash
py -m pip install -r requirements.txt
py -c "import lancedb, pyarrow, sentence_transformers; print('OK')"
```

If this fails: install Python 3.10+ and retry. Do not proceed until it prints `OK`.

### Step CC-2: Create or verify wiki.config.json

The workspace is the folder that will contain `wiki/`, `wiki-works/`, `memory/`.

If it does not exist yet:
```bash
mkdir -p <WORKSPACE>/wiki <WORKSPACE>/wiki-works <WORKSPACE>/memory
```

Create `<WORKSPACE>/wiki.config.json` with this content (replace `<WORKSPACE>` with the absolute path):
```json
{
  "workspace": "<WORKSPACE>",
  "pdf_inbox": { "project_default": "ricerca" },
  "projects": {
    "ricerca": { "path": "wiki-works/ricerca", "keywords": [] }
  },
  "thresholds": {
    "index_token_budget": 4000, "staleness_days": 90,
    "similarity_merge": 0.95, "similarity_orphan": 0.50,
    "synthesis_min_tokens": 300, "synthesis_min_sources": 2,
    "chunk_size_tokens": 512, "chunk_overlap_tokens": 64,
    "page_chunk_threshold_tokens": 1500, "quality_filter_min_score": 6,
    "dedup_auto": 0.90, "dedup_warn": 0.75
  },
  "self_reflection": { "enabled": true, "correction_threshold": 3 },
  "lancedb": { "path": "memory/lancedb", "embedding_model": "BAAI/bge-m3" },
  "exclude_from_index": []
}
```

### Step CC-3: Install the Claude Code hook

```bash
py scripts/install_claude_code_hook.py --workspace <WORKSPACE>
```

Verify there are no WARNING messages in the output. If you see `WARNING: no Python...`:
```bash
py -c "import sys; print(sys.executable)"
# Copy the path and use it with --python
py scripts/install_claude_code_hook.py --workspace <WORKSPACE> --python <PATH>
```

### Step CC-4: Initialize LanceDB

```bash
py scripts/wiki.py rebuild --workspace <WORKSPACE>
```

Expected: `"pages_embedded": 0` (normal — the wiki is empty).

### Step CC-5: Update your user CLAUDE.md

Open `~/.claude/CLAUDE.md` (or the current project's CLAUDE.md) and add:

```markdown
## Wiki workspace
Active wiki workspace: <WORKSPACE>
```

### Step CC-6: Restart Claude Code

Restart Claude Code. The next prompt should receive `<wiki-context>` (empty the first time — normal).

### Step CC-7: Final verification

```bash
py scripts/install_claude_code_hook.py --verify
```

Expected: `OK: '...' can import lancedb`

**Claude Code setup complete.**

---

## §openclaw — Setup for OpenClaw

### Step OC-1: Verify Python dependencies

Same as CC-1.

### Step OC-2: Create wiki.config.json

Same as CC-2.

### Step OC-3: Build the plugin

```bash
cd plugins/wiki-context-plugin
npm install
npm run build
```

### Step OC-4: Configure the plugin in OpenClaw

```bash
py scripts/setup_openclaw.py --workspace <WORKSPACE>
```

If auto-detection fails:
```bash
py scripts/setup_openclaw.py --workspace <WORKSPACE> --config <OPENCLAW_CONFIG_PATH>
```

Verify that `pythonExecutable` in the OpenClaw config is the absolute path:
```bash
py -c "import sys; print(sys.executable)"
```

### Step OC-5: Initialize LanceDB

Same as CC-4.

### Step OC-6: Update your user AGENTS.md

Open `AGENTS.md` of your project (or create `~/.openclaw/AGENTS.md`) and add:

```markdown
## Wiki workspace
Active wiki workspace: <WORKSPACE>
```

### Step OC-7: Restart OpenClaw

**OpenClaw setup complete.**
