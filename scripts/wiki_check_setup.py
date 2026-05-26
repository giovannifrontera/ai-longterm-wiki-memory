#!/usr/bin/env python3
"""
wiki_check_setup.py — Controlla se il wiki system è pronto.

Stampa <wiki-setup-required> se manca uno dei requisiti:
  - wiki.config.json nel workspace
  - lancedb inizializzato con almeno 1 riga

Esce sempre con codice 0 — non blocca mai il prompt.

Uso:
    python wiki_check_setup.py --workspace /path/to/workspace
"""

import argparse
import json
import sys
from pathlib import Path


def check(workspace: str) -> list[str]:
    """Ritorna lista di problemi. Lista vuota = tutto ok."""
    issues = []
    ws = Path(workspace)

    # 1. wiki.config.json
    config_path = ws / "wiki.config.json"
    if not config_path.exists():
        issues.append("wiki.config.json not found in workspace")
        return issues  # inutile controllare altro

    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        issues.append("wiki.config.json is not valid JSON")
        return issues

    # 2. lancedb path configurato e inizializzato
    ldb_rel = cfg.get("lancedb", {}).get("path", "")
    if not ldb_rel:
        issues.append("wiki.config.json: lancedb.path field missing")
    else:
        ldb_path = ws / ldb_rel
        if not ldb_path.exists():
            issues.append(f"LanceDB not found at {ldb_path} — run: wiki.py rebuild")
        else:
            # Separate the import check from the connection check so that
            # ImportErrors raised internally by lancedb (e.g. optional Unix
            # modules like posix/fcntl on Windows) are not mistaken for a
            # missing lancedb installation.
            try:
                import lancedb
            except ImportError:
                issues.append("lancedb not installed — run: pip install -r requirements.txt")
            else:
                try:
                    db = lancedb.connect(str(ldb_path))
                    table_result = db.list_tables()
                    tables = getattr(table_result, "tables", None) or list(table_result)
                    if "wiki_pages" not in tables:
                        issues.append("wiki_pages table not found — run: wiki.py rebuild")
                    elif db.open_table("wiki_pages").count_rows() == 0:
                        issues.append("wiki_pages is empty — run: wiki.py rebuild or process-raw")
                except Exception as e:
                    issues.append(f"LanceDB error: {e}")

    return issues


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    args = parser.parse_args()

    try:
        issues = check(args.workspace)
    except Exception as e:
        print(f"wiki_check_setup internal error: {e}", file=sys.stderr)
        sys.exit(0)  # never block the prompt

    if issues:
        lines = ["<wiki-setup-required>"]
        lines.append("The wiki system is not configured correctly. Run the wiki-setup skill before proceeding.\n")
        lines.append("Issues found:")
        for issue in issues:
            lines.append(f"  - {issue}")
        lines.append("</wiki-setup-required>")
        print("\n".join(lines))

    sys.exit(0)


if __name__ == "__main__":
    main()
