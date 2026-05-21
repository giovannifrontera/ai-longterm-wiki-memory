#!/usr/bin/env python3
"""
install_claude_hook.py — installs wiki_context.py as a UserPromptSubmit hook in .claude/settings.json

Usage:
    py scripts/install_claude_hook.py --workspace /path/to/workspace

The script:
- Reads or creates .claude/settings.json in the workspace
- Appends the UserPromptSubmit hook without touching existing config
- Skips silently if the hook is already present
"""

import argparse
import json
import os
import sys
from pathlib import Path


def detect_python() -> str:
    return "py" if os.name == "nt" else "python3"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install wiki-context UserPromptSubmit hook for Claude Code"
    )
    parser.add_argument(
        "--workspace",
        required=True,
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
        "--dry-run",
        action="store_true",
        help="Print the resulting settings.json without writing it",
    )
    args = parser.parse_args()

    # Resolve workspace
    workspace = Path(args.workspace).resolve()
    if not workspace.exists():
        print(f"ERROR: workspace not found: {workspace}", file=sys.stderr)
        sys.exit(1)

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
    command = (
        f'{args.python} "{script_str}"'
        f' --workspace "{workspace_str}"'
        f' --q "$CLAUDE_USER_PROMPT"'
        f' --k {args.k}'
    )

    # Check if already installed
    existing_hooks = (
        settings.get("hooks", {}).get("UserPromptSubmit", [])
    )
    for block in existing_hooks:
        for h in block.get("hooks", []):
            if "wiki_context.py" in h.get("command", ""):
                print(f"Hook already present in {settings_path} — nothing to do.")
                sys.exit(0)

    # Inject hook
    settings.setdefault("hooks", {}).setdefault("UserPromptSubmit", []).append(
        {"matcher": "", "hooks": [{"type": "command", "command": command}]}
    )

    if args.dry_run:
        print(f"DRY RUN — would write to: {settings_path}\n")
        print(json.dumps(settings, indent=2))
        return

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")

    print(f"Hook installed in {settings_path}")
    print(f"  workspace : {workspace_str}")
    print(f"  script    : {script_str}")
    print(f"  python    : {args.python}")
    print(f"  k         : {args.k}")
    print()
    print("Restart Claude Code to activate the hook.")


if __name__ == "__main__":
    main()
