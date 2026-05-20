"""Implementazione dei workflow INGEST, QUERY, LINT, INDEX, REBUILD, SESSION-UPDATE."""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from wiki import ok, error, acquire_lock, release_lock
from wiki_embed import embed_file
from wiki_lancedb import get_db, upsert, promote_staging, rollback_staging, ensure_table
from wiki_index import rebuild_index, is_stale, EXCLUDED_NAMES


def _lancedb_path(workspace: str, cfg: dict) -> str:
    return os.path.join(workspace, cfg["lancedb"]["path"])


def _append_log(workspace: str, wiki_subdir: str, entry: str) -> None:
    log_path = Path(workspace) / wiki_subdir / "log.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    line = f"## [{date}] {entry}\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


def _mini_lint(workspace: str, written_paths: list, db) -> str:
    """Verifica le invarianti post-ingest. Ritorna 'ok' o descrizione errore."""
    table = ensure_table(db)
    df = table.to_pandas()
    for path in written_paths:
        if not os.path.exists(path):
            return f"file_missing:{path}"
        rel = os.path.relpath(path, workspace).replace("\\", "/")
        if df[df["path"] == rel].empty:
            return f"not_embedded:{rel}"
    for p in Path(workspace).rglob("*.tmp"):
        return f"tmp_remaining:{p}"
    return "ok"


def cmd_ingest(args, cfg):
    workspace = args.workspace
    lock_path = os.path.join(workspace, ".wiki-lock")
    db = get_db(_lancedb_path(workspace, cfg))
    thresholds = cfg["thresholds"]

    try:
        acquire_lock(lock_path)
    except RuntimeError as e:
        print(e.args[0])
        return

    _write_session(workspace, "ingest", "in-progress", {})

    tmp_paths = [p.strip() for p in args.pages.split(",")]
    final_paths = []

    try:
        for tmp_path in tmp_paths:
            if not os.path.exists(tmp_path):
                raise FileNotFoundError(f"File .tmp non trovato: {tmp_path}")

        for tmp_path in tmp_paths:
            rel_final = os.path.relpath(tmp_path, workspace).replace(".tmp", "").replace("\\", "/")
            chunks = embed_file(
                tmp_path,
                chunk_size=thresholds["chunk_size_tokens"],
                overlap=thresholds["chunk_overlap_tokens"],
                threshold=thresholds["page_chunk_threshold_tokens"],
                model_name=cfg["lancedb"]["embedding_model"],
            )
            upsert(db, rel_final, chunks, table_name="staging_wiki_pages")
            final_paths.append((tmp_path, os.path.join(workspace, rel_final.replace("/", os.sep))))

        for tmp_path, final_path in final_paths:
            os.makedirs(os.path.dirname(final_path), exist_ok=True)
            shutil.move(tmp_path, final_path)

        promote_staging(db)

        wiki_dir = os.path.join(workspace, "wiki")
        if os.path.isdir(wiki_dir):
            idx_content = rebuild_index(wiki_dir, thresholds["index_token_budget"])
            Path(wiki_dir, "index.md").write_text(idx_content, encoding="utf-8")

        _append_log(workspace, "wiki", args.log)

        written = [fp for _, fp in final_paths]
        lint_result = _mini_lint(workspace, written, db)

        if lint_result != "ok":
            _append_log(workspace, "wiki", f"mini-lint-failed | {lint_result}")

        _write_session(workspace, "ingest", "ok",
                       {"pages_written": len(final_paths), "mini_lint": lint_result})
        ok({"op": "ingest", "pages_written": len(final_paths), "mini_lint": lint_result, "conflicts": []})

    except Exception as e:
        rollback_staging(db)
        for tmp_path, _ in final_paths:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        _write_session(workspace, "ingest", "failed", {"error": str(e)})
        error("ingest_failed", str(e))
    finally:
        release_lock(lock_path)


def cmd_query(args, cfg):
    from wiki_embed import _load_model
    db = get_db(_lancedb_path(args.workspace, cfg))
    model, _ = _load_model(cfg["lancedb"]["embedding_model"])
    vector = model.encode(args.q, normalize_embeddings=True).tolist()

    from wiki_lancedb import query_similar
    results = query_similar(db, vector, k=args.k)

    wiki_dir = os.path.join(args.workspace, "wiki")
    index_path = os.path.join(wiki_dir, "index.md")
    if is_stale(index_path, wiki_dir):
        idx_content = rebuild_index(wiki_dir, cfg["thresholds"]["index_token_budget"])
        Path(index_path).write_text(idx_content, encoding="utf-8")

    ok({"op": "query", "results": [
        {"path": r["path"], "chunk_id": r["chunk_id"],
         "score": float(r.get("_distance", 0)), "excerpt": r["chunk_text"][:200]}
        for r in results
    ]})


def cmd_index(args, cfg):
    wiki_dir = os.path.join(args.workspace, "wiki")
    idx_content = rebuild_index(wiki_dir, cfg["thresholds"]["index_token_budget"])
    Path(wiki_dir, "index.md").write_text(idx_content, encoding="utf-8")
    ok({"op": "index", "wiki_dir": wiki_dir})


def cmd_rebuild(args, cfg):
    db = get_db(_lancedb_path(args.workspace, cfg))
    thresholds = cfg["thresholds"]

    if "wiki_pages" in db.table_names():
        db.drop_table("wiki_pages")

    count = 0
    for md_file in Path(args.workspace).rglob("*.md"):
        if md_file.name in EXCLUDED_NAMES:
            continue
        if "raw" in md_file.parts or ".archive" in md_file.parts:
            continue
        rel = os.path.relpath(str(md_file), args.workspace).replace("\\", "/")
        chunks = embed_file(
            str(md_file),
            chunk_size=thresholds["chunk_size_tokens"],
            overlap=thresholds["chunk_overlap_tokens"],
            threshold=thresholds["page_chunk_threshold_tokens"],
            model_name=cfg["lancedb"]["embedding_model"],
        )
        upsert(db, rel, chunks)
        count += 1

    _append_log(args.workspace, "wiki", f"rebuild-lancedb | {count} pagine")
    ok({"op": "rebuild", "pages_embedded": count})


def cmd_lint(args, cfg):
    db = get_db(_lancedb_path(args.workspace, cfg))
    report = []

    if args.full:
        import re
        from wiki_lancedb import detect_renames
        for md_file in Path(args.workspace).rglob("*.md"):
            if "raw" in md_file.parts:
                continue
            try:
                text = md_file.read_text(encoding="utf-8")
            except OSError:
                continue
            for link in re.findall(r'\[\[([^\]]+)\]\]', text):
                matches = list(Path(args.workspace).rglob(f"{link}.md"))
                if not matches:
                    report.append({"type": "broken_link", "file": str(md_file), "link": link})

        table = ensure_table(db)
        df = table.to_pandas()
        for path in df["path"].unique():
            full = os.path.join(args.workspace, path.replace("/", os.sep))
            if not os.path.exists(full):
                report.append({"type": "orphan_entry", "path": path})
                try:
                    table.delete(f"path = '{path}'")
                except Exception:
                    pass

        fs_paths = {str(p) for p in Path(args.workspace).rglob("*.md")
                    if "raw" not in p.parts}
        renames = detect_renames(db, fs_paths)
        for r in renames:
            report.append({"type": "rename_detected", **r})

    ok({"op": "lint", "full": args.full, "issues": report, "issues_count": len(report)})


def cmd_session_update(args, cfg):
    _write_session(args.workspace, args.op, args.status, json.loads(args.detail))
    ok({"op": "session-update", "status": args.status})


def _write_session(workspace: str, op: str, status: str, detail: dict) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    content = f"""# Wiki Session — {now}

## Status
status: {status}

## Ultima operazione
Tipo: {op}
Completata: {now}
Dettaglio: {json.dumps(detail, ensure_ascii=False)}

## Wiki principale
Pagine totali: {_count_pages(workspace)}
"""
    Path(workspace, "wiki-session.md").write_text(content, encoding="utf-8")


def _count_pages(workspace: str) -> int:
    return sum(
        1 for p in Path(workspace).rglob("*.md")
        if p.name not in EXCLUDED_NAMES and "raw" not in p.parts and not p.name.endswith(".tmp")
    )
