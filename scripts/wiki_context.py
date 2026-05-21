#!/usr/bin/env python3
"""
wiki_context.py — Pre-prompt wiki context injector.

Usage:
    py scripts/wiki_context.py --workspace <path> --q "<query>" [--k 3] [--max-chars 600]

Outputs a <wiki-context> block to stdout with the most relevant wiki pages.
Designed for use as a UserPromptSubmit hook in Claude Code or as a pre-hook in OpenClaw.

Exit codes:
    0 — always (hook must never block the user's prompt)
"""

import argparse
import json
import os
import sys
from pathlib import Path


def load_config(workspace: str) -> dict | None:
    config_path = os.path.join(workspace, "wiki.config.json")
    if not os.path.exists(config_path):
        return None
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def read_page(workspace: str, rel_path: str, max_chars: int) -> str:
    abs_path = os.path.join(workspace, rel_path)
    try:
        with open(abs_path, encoding="utf-8") as f:
            content = f.read()
        if len(content) > max_chars:
            content = content[:max_chars].rstrip() + "\n[...troncato]"
        return content
    except OSError:
        return "[pagina non leggibile]"


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
    parser.add_argument("--max-chars", type=int, default=600,
                        help="Caratteri massimi per pagina (default: 600)")
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
    if table.to_pandas().empty:
        return

    model = SentenceTransformer(cfg["lancedb"]["embedding_model"])
    vector = model.encode(args.q, normalize_embeddings=True).tolist()

    # Over-fetch per deduplicare per pagina, poi prendere i top-k
    raw = table.search(vector).limit(args.k * 4).to_list()

    seen: dict[str, dict] = {}
    for r in raw:
        path = r["path"]
        dist = float(r.get("_distance", 1.0))
        if path not in seen or dist < seen[path]["dist"]:
            seen[path] = {"dist": dist}

    top = sorted(seen.items(), key=lambda x: x[1]["dist"])[: args.k]
    if not top:
        return

    lines = ["<wiki-context>"]
    lines.append(
        f"Contesto wiki pre-caricato (top {len(top)} pagine per rilevanza semantica):\n"
    )
    for path, info in top:
        score = round(1.0 - info["dist"], 3)
        content = read_page(args.workspace, path, args.max_chars)
        lines.append(f"### {path}  [rilevanza: {score}]")
        lines.append(content)
        lines.append("")
    lines.append(
        "</wiki-context>\n"
        "Usa il contesto sopra per rispondere, rilevare conflitti durante l'INGEST, "
        "o disambiguare intent incerti. Non eseguire wiki.py query se il contesto è già sufficiente."
    )

    print("\n".join(lines))


if __name__ == "__main__":
    main()
