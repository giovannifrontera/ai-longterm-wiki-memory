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

See `AGENTS_PATCH.md` for the full protocol on how to use the wiki during sessions.
