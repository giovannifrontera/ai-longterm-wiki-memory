#!/usr/bin/env python3
"""
wiki_context.py — Pre-prompt wiki context injector.

Usage:
    py scripts/wiki_context.py --workspace <path> --q "<query>" [--k 3]

Outputs a <wiki-context> block to stdout with the most relevant wiki chunks.
Designed for use as a UserPromptSubmit hook in Claude Code or as a pre-hook in OpenClaw.

Exit codes:
    0 — always (hook must never block the user's prompt)
"""

import argparse
import fnmatch
import json
import os
import sys
from datetime import datetime


def load_config(workspace: str) -> dict | None:
    config_path = os.path.join(workspace, "wiki.config.json")
    if not os.path.exists(config_path):
        return None
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(
        description="Inietta contesto wiki prima di ogni prompt."
    )
    parser.add_argument("--workspace", required=True,
                        help="Path al workspace (deve contenere wiki.config.json)")
    parser.add_argument("--q", required=True,
                        help="Testo della query (il prompt utente)")
    parser.add_argument("--k", type=int, default=3,
                        help="Numero di pagine da restituire (default: 3)")
    args = parser.parse_args()

    try:
        _run(args)
    except Exception:
        pass  # Hook deve sempre fallire silenziosamente
    sys.exit(0)


def _run(args):
    cfg = load_config(args.workspace)
    if not cfg:
        return

    lancedb_path = os.path.join(args.workspace, cfg["lancedb"]["path"])
    if not os.path.exists(lancedb_path):
        return

    try:
        import lancedb
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return

    db = lancedb.connect(lancedb_path)
    existing = db.table_names() if hasattr(db, "table_names") else db.list_tables()
    if "wiki_pages" not in existing:
        return

    table = db.open_table("wiki_pages")
    model = SentenceTransformer(cfg["lancedb"]["embedding_model"])
    vector = model.encode(args.q, normalize_embeddings=True).tolist()

    # Over-fetch per deduplicare per pagina, poi prendere i top-k
    raw = table.search(vector).limit(args.k * 4).to_list()

    exclude_patterns = cfg.get("exclude_from_index", [])
    seen: dict[str, dict] = {}
    for r in raw:
        chunk = r.get("chunk_text") or ""
        if not chunk:
            continue
        path = r["path"]
        if any(fnmatch.fnmatch(path, p) for p in exclude_patterns):
            continue
        dist = float(r.get("_distance", 1.0))
        if path not in seen or dist < seen[path]["dist"]:
            seen[path] = {"dist": dist, "chunk_text": chunk}

    top = sorted(seen.items(), key=lambda x: x[1]["dist"])[: args.k]
    if not top:
        return

    # Write to query log so the dashboard can animate the retrieved nodes
    try:
        log_path = os.path.join(args.workspace, ".wiki-query-log.jsonl")
        entry = {"ts": datetime.now().isoformat(), "q": args.q, "paths": [p for p, _ in top]}
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

    lines = ["<wiki-context>"]
    lines.append(
        f"Pre-loaded wiki context (top {len(top)} pages by semantic relevance):\n"
    )
    for path, info in top:
        score = round(1.0 - info["dist"], 3)
        lines.append(f"### {path}  [relevance: {score}]")
        lines.append(info["chunk_text"])
        lines.append("")
    lines.append(
        "</wiki-context>\n"
        "Use the context above to inform your response, detect conflicts during INGEST, "
        "or disambiguate uncertain intents. Do not run wiki.py query if this context is already sufficient."
    )

    print("\n".join(lines))


if __name__ == "__main__":
    main()
