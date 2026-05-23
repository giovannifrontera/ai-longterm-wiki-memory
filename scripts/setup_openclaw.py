#!/usr/bin/env python3
"""
setup_openclaw.py — injects wiki-context-plugin into the OpenClaw config file.

Usage:
    py scripts/setup_openclaw.py --workspace /path/to/workspace
    py scripts/setup_openclaw.py --workspace /path/to/workspace --config /path/to/openclaw/config.json

The script:
- Auto-detects the OpenClaw config file in common locations (or uses --config)
- Injects the wiki-context-plugin entry into the plugins array
- Skips silently if the plugin is already present
- Writes atomically (temp file + rename)
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path


CANDIDATE_PATHS = [
    Path.home() / ".openclaw" / "config.json",
    Path.home() / ".config" / "openclaw" / "config.json",
    Path(os.environ.get("APPDATA", "")) / "openclaw" / "config.json",
    Path(os.environ.get("LOCALAPPDATA", "")) / "openclaw" / "config.json",
    Path.cwd() / "openclaw.config.json",
]


def find_openclaw_config() -> Path | None:
    for p in CANDIDATE_PATHS:
        if p.exists():
            return p
    return None


def detect_python() -> str:
    return "py" if os.name == "nt" else "python3"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inject wiki-context-plugin into OpenClaw config"
    )
    parser.add_argument(
        "--workspace",
        required=True,
        help="Absolute path to the wiki workspace (directory containing wiki.config.json)",
    )
    parser.add_argument(
        "--config",
        help="Path to the OpenClaw config file (default: auto-detected)",
    )
    parser.add_argument(
        "--python",
        default=detect_python(),
        help=f"Python executable (default: {detect_python()})",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=3,
        help="Number of wiki chunks to inject per prompt (default: 3)",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=15000,
        dest="timeout_ms",
        help="Timeout for wiki_context.py in milliseconds (default: 15000)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resulting config without writing it",
    )
    args = parser.parse_args()

    # Resolve workspace
    workspace = Path(args.workspace).resolve()
    if not workspace.exists():
        print(f"ERROR: workspace not found: {workspace}", file=sys.stderr)
        sys.exit(1)
    if not (workspace / "wiki.config.json").exists():
        print(f"WARNING: wiki.config.json not found in {workspace}.", file=sys.stderr)
        print("The plugin will fail silently until wiki.config.json is created.", file=sys.stderr)

    # Resolve wiki_context.py path
    script_path = (Path(__file__).parent / "wiki_context.py").resolve()
    if not script_path.exists():
        print(f"ERROR: wiki_context.py not found at {script_path}", file=sys.stderr)
        sys.exit(1)

    # Resolve plugin directory
    plugin_path = (Path(__file__).parent.parent / "plugins" / "wiki-context-plugin").resolve()
    if not plugin_path.exists():
        print(f"ERROR: plugin directory not found at {plugin_path}", file=sys.stderr)
        sys.exit(1)

    # Locate OpenClaw config
    if args.config:
        config_path = Path(args.config).resolve()
        if not config_path.exists():
            print(f"ERROR: config file not found: {config_path}", file=sys.stderr)
            sys.exit(1)
    else:
        config_path = find_openclaw_config()
        if config_path is None:
            print("ERROR: could not auto-detect OpenClaw config file.", file=sys.stderr)
            print("Tried:", file=sys.stderr)
            for p in CANDIDATE_PATHS:
                print(f"  {p}", file=sys.stderr)
            print("\nPass --config /path/to/openclaw/config.json explicitly.", file=sys.stderr)
            sys.exit(1)

    # Load existing config
    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: could not parse {config_path}: {e}", file=sys.stderr)
        sys.exit(1)

    # Check if already installed
    plugins = config.setdefault("plugins", [])
    for entry in plugins:
        if entry.get("id") == "wiki-context-plugin":
            print(f"Plugin already present in {config_path} — nothing to do.")
            sys.exit(0)

    # Build plugin entry
    plugin_entry = {
        "id": "wiki-context-plugin",
        "path": str(plugin_path).replace("\\", "/"),
        "config": {
            "workspace": str(workspace).replace("\\", "/"),
            "wikiContextScript": str(script_path).replace("\\", "/"),
            "pythonExecutable": args.python,
            "k": args.k,
            "timeoutMs": args.timeout_ms,
        },
    }
    plugins.append(plugin_entry)

    if args.dry_run:
        print(f"DRY RUN — would write to: {config_path}\n")
        print(json.dumps(config, indent=2))
        return

    # Write atomically
    fd, tmp_path = tempfile.mkstemp(dir=config_path.parent, prefix=".openclaw.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, config_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    print(f"Plugin injected into {config_path}")
    print(f"  workspace  : {str(workspace).replace(chr(92), '/')}")
    print(f"  script     : {str(script_path).replace(chr(92), '/')}")
    print(f"  plugin dir : {str(plugin_path).replace(chr(92), '/')}")
    print(f"  python     : {args.python}")
    print(f"  k          : {args.k}")
    print()
    print("Restart OpenClaw to activate the plugin.")


if __name__ == "__main__":
    main()
