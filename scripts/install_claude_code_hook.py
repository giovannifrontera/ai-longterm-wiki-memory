#!/usr/bin/env python3
"""
install_claude_code_hook.py — installs wiki_context.py as a UserPromptSubmit hook in .claude/settings.json

Usage:
    py scripts/install_claude_code_hook.py --workspace /path/to/workspace

The script:
- Reads or creates .claude/settings.json in the workspace
- Appends the UserPromptSubmit hook without touching existing config
- Skips silently if the hook is already present
- Injects usage instructions into <workspace>/CLAUDE.md (idempotent via sentinel marker)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

USAGE_SENTINEL_START = "<!-- ai-wiki-system:usage-start -->"
USAGE_SENTINEL_END = "<!-- ai-wiki-system:usage-end -->"

USAGE_INSTRUCTIONS = """\
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
"""


def update_config_workspace(workspace: Path, dry_run: bool = False) -> None:
    """Update the workspace field in wiki.config.json if it is still a placeholder."""
    config_path = workspace / "wiki.config.json"
    if not config_path.exists():
        return
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    workspace_str = str(workspace).replace("\\", "/")
    current = cfg.get("workspace", "")
    if current == workspace_str:
        return  # already correct

    cfg["workspace"] = workspace_str
    if dry_run:
        print(f"DRY RUN — would update wiki.config.json workspace: {workspace_str}")
        return

    fd, tmp_path = tempfile.mkstemp(dir=workspace, prefix=".wiki_config.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp_path, config_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    print(f"wiki.config.json updated: workspace = {workspace_str}")


def inject_usage_instructions(workspace: Path, dry_run: bool = False) -> None:
    claude_md = workspace / "CLAUDE.md"
    if claude_md.exists():
        content = claude_md.read_text(encoding="utf-8")
        if USAGE_SENTINEL_START in content:
            print(f"Usage instructions already present in {claude_md} — skipping.")
            return
        new_content = content.rstrip("\n") + "\n\n" + USAGE_INSTRUCTIONS
    else:
        new_content = USAGE_INSTRUCTIONS

    if dry_run:
        print(f"DRY RUN — would write usage instructions to: {claude_md}")
        return

    fd, tmp_path = tempfile.mkstemp(dir=workspace, prefix=".claude_md.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(new_content)
        os.replace(tmp_path, claude_md)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    print(f"Usage instructions injected into {claude_md}")


def _verify_python(exe: str) -> bool:
    """Returns True if exe can import lancedb in its context."""
    try:
        r = subprocess.run([exe, "-c", "import lancedb"],
                           capture_output=True, timeout=10)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


class PythonNotVerifiedError(RuntimeError):
    """Raised when no Python executable can import lancedb."""


_PYTHON_FIX_HINT = (
    "Find the correct Python path with:\n"
    "  py -c \"import sys; print(sys.executable)\"\n"
    "Then re-run with:\n"
    "  py scripts/install_claude_code_hook.py --workspace <path> --python <correct-path>"
)


def _resolve_python(explicit: str | None) -> str:
    """Return a verified Python exe to write into the hook.

    Order: explicit (if provided and valid) → sys.executable.
    Raises PythonNotVerifiedError if no candidate can import lancedb.
    """
    if explicit:
        if _verify_python(explicit):
            return explicit
        # Explicit failed — try sys.executable as fallback
        print(
            f"WARNING: '{explicit}' cannot import lancedb. Trying {sys.executable}...",
            file=sys.stderr,
        )
        if _verify_python(sys.executable):
            return sys.executable
        raise PythonNotVerifiedError(
            f"Neither '{explicit}' nor '{sys.executable}' can import lancedb.\n"
            + _PYTHON_FIX_HINT
        )

    # No explicit: try sys.executable only
    if _verify_python(sys.executable):
        return sys.executable

    raise PythonNotVerifiedError(
        f"'{sys.executable}' cannot import lancedb.\n" + _PYTHON_FIX_HINT
    )


def detect_python() -> str:
    return "py" if os.name == "nt" else "python3"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install wiki-context UserPromptSubmit hook for Claude Code"
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Absolute path to the wiki workspace (directory containing wiki.config.json)",
    )
    parser.add_argument(
        "--script",
        help="Absolute path to wiki_context.py (default: auto-detected from this repo)",
    )
    parser.add_argument(
        "--settings",
        help="Path to .claude/settings.json to modify (default: <workspace>/.claude/settings.json)",
    )
    parser.add_argument(
        "--python",
        default=detect_python(),
        help=f"Python executable to use in the hook command (default: {detect_python()})",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=3,
        help="Number of wiki pages to inject per prompt (default: 3)",
    )
    parser.add_argument(
        "--no-session-check",
        action="store_true",
        help="Skip installing the SessionStart setup check hook",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resulting settings.json without writing it",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Read the existing hook from settings.json and verify the Python exe works",
    )
    args = parser.parse_args()

    if args.verify:
        settings_path = Path(args.settings).resolve() if args.settings else Path.home() / ".claude" / "settings.json"
        if not settings_path.exists():
            print(f"ERROR: settings.json not found at {settings_path}", file=sys.stderr)
            sys.exit(1)
        try:
            content = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"ERROR: cannot parse {settings_path}: {e}", file=sys.stderr)
            sys.exit(1)
        hooks = (
            content.get("hooks", {})
                   .get("UserPromptSubmit", [{}])[0]
                   .get("hooks", [{}])[0]
                   .get("command", "")
        )
        # Extract Python exe: try quoted path first (handles spaces), then unquoted
        match = re.match(r'^"([^"]+)"', hooks) or re.match(r'^(\S+)', hooks)
        exe = match.group(1) if match else ""
        if not exe or "wiki_context" not in hooks:
            print("WARNING: no wiki_context hook found in settings.json")
            sys.exit(1)
        if _verify_python(exe):
            print(f"OK: '{exe}' can import lancedb")
            sys.exit(0)
        else:
            print(f"ERROR: '{exe}' cannot import lancedb — re-run install without --verify to repair")
            sys.exit(2)

    # --workspace is required when not using --verify
    if not args.workspace:
        parser.error("the following arguments are required: --workspace")

    # Determine the Python exe: if user explicitly passed --python (not the default),
    # use it as the preferred candidate; otherwise let _resolve_python find the best one.
    default_py = detect_python()
    explicit_py = args.python if args.python != default_py else None
    try:
        resolved_python = _resolve_python(explicit_py)
    except PythonNotVerifiedError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Resolve workspace
    workspace = Path(args.workspace).resolve()
    if not workspace.exists():
        print(f"ERROR: workspace not found: {workspace}", file=sys.stderr)
        sys.exit(1)
    if not (workspace / "wiki.config.json").exists():
        print(f"WARNING: wiki.config.json not found in {workspace}.", file=sys.stderr)
        print("The hook will fail silently until wiki.config.json is created.", file=sys.stderr)
    else:
        update_config_workspace(workspace, dry_run=args.dry_run)

    # Resolve script path
    if args.script:
        script_path = Path(args.script).resolve()
    else:
        script_path = (Path(__file__).parent / "wiki_context.py").resolve()

    if not script_path.exists():
        print(f"ERROR: wiki_context.py not found at {script_path}", file=sys.stderr)
        print("Use --script to specify the path explicitly.", file=sys.stderr)
        sys.exit(1)

    # Resolve settings.json path
    if args.settings:
        settings_path = Path(args.settings).resolve()
    else:
        settings_path = workspace / ".claude" / "settings.json"

    # Load existing settings or start fresh
    if settings_path.exists():
        try:
            with open(settings_path, encoding="utf-8") as f:
                settings = json.load(f)
        except json.JSONDecodeError as e:
            print(f"ERROR: could not parse {settings_path}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        settings = {}

    # Build hook command — use forward slashes for cross-platform compatibility
    script_str = str(script_path).replace("\\", "/")
    workspace_str = str(workspace).replace("\\", "/")
    python_str = str(resolved_python).replace("\\", "/")
    # $CLAUDE_USER_PROMPT is NOT passed on the command line: on Windows, PowerShell
    # expands it as a PS variable (empty) before Claude Code sets the env var.
    # wiki_context.py reads CLAUDE_USER_PROMPT directly from os.environ instead.
    command = (
        f'"{python_str}" "{script_str}"'
        f' --workspace "{workspace_str}"'
        f" --k {args.k}"
    )

    # Check if UserPromptSubmit hook is already installed
    existing_hooks = (
        settings.get("hooks", {}).get("UserPromptSubmit", [])
    )
    user_prompt_already_installed = any(
        "wiki_context.py" in h.get("command", "")
        for block in existing_hooks
        for h in block.get("hooks", [])
    )

    if not user_prompt_already_installed:
        settings.setdefault("hooks", {}).setdefault("UserPromptSubmit", []).append(
            {"matcher": "", "hooks": [{"type": "command", "command": command}]}
        )
    else:
        print(f"UserPromptSubmit hook already present — skipping.")

    # SessionStart hook — runs wiki_check_setup.py at session start
    if not args.no_session_check:
        check_script = (Path(__file__).parent / "wiki_check_setup.py").resolve()
        check_script_str = str(check_script).replace("\\", "/")
        session_command = (
            f'"{resolved_python}" "{check_script_str}"'
            f' --workspace "{workspace_str}"'
        )
        existing_session_hooks = settings.get("hooks", {}).get("SessionStart", [])
        session_already_installed = any(
            "wiki_check_setup" in h.get("command", "")
            for block in existing_session_hooks
            for h in block.get("hooks", [])
        )
        if not session_already_installed:
            settings.setdefault("hooks", {}).setdefault("SessionStart", []).append(
                {"matcher": "", "hooks": [{"type": "command", "command": session_command}]}
            )

    if args.dry_run:
        print(f"DRY RUN — would write to: {settings_path}\n")
        print(f"  python    : {resolved_python}")
        print(json.dumps(settings, indent=2))
        inject_usage_instructions(workspace, dry_run=True)
        return

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=settings_path.parent, prefix=".settings.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, settings_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    print(f"Hook installed in {settings_path}")
    print(f"  workspace : {workspace_str}")
    print(f"  script    : {script_str}")
    print(f"  python    : {resolved_python}")
    print(f"  k         : {args.k}")
    if not args.no_session_check:
        print(f"  session check: enabled (wiki_check_setup.py)")
    print()
    print("Restart Claude Code to activate the hook.")

    inject_usage_instructions(workspace, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
