"""PDF inbox watcher: estrae testo da PDF e deposita in wiki-works/raw/."""

import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pdfplumber

INBOX_DIR = "pdf-inbox"
REGISTRY_FILE = ".registry.json"


def compute_hash(pdf_path: str) -> str:
    """SHA-256 del file PDF."""
    h = hashlib.sha256()
    with open(pdf_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def load_registry(workspace: str) -> dict:
    """Legge pdf-inbox/.registry.json. Ritorna {} se non esiste."""
    path = Path(workspace) / INBOX_DIR / REGISTRY_FILE
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_registry(workspace: str, data: dict) -> None:
    """Scrive .registry.json atomicamente via tempfile + os.replace."""
    inbox_dir = Path(workspace) / INBOX_DIR
    inbox_dir.mkdir(parents=True, exist_ok=True)
    target = inbox_dir / REGISTRY_FILE
    fd, tmp_path = tempfile.mkstemp(dir=str(inbox_dir), prefix=".registry.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, str(target))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def extract_text(pdf_path: str) -> str:
    """Estrae testo da PDF. Ritorna stringa vuota se nessun testo selezionabile."""
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n\n".join(text_parts)


def deposit_raw(text: str, pdf_name: str, workspace: str, cfg: dict) -> str:
    """Salva testo estratto in wiki-works/<project>/raw/<stem>.md con frontmatter.
    Ritorna il path relativo al workspace (slash forward)."""
    project = cfg.get("pdf_inbox", {}).get("project_default", "")
    if not project:
        projects = cfg.get("projects", {})
        project = next(iter(projects), "default") if projects else "default"

    raw_dir = Path(workspace) / "wiki-works" / project / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    stem = Path(pdf_name).stem
    out_path = raw_dir / f"{stem}.md"

    now = datetime.now().isoformat(timespec="seconds")
    content = f"---\nsource: pdf\noriginal: {pdf_name}\nextracted_at: {now}\n---\n\n{text}"
    out_path.write_text(content, encoding="utf-8")

    return os.path.relpath(str(out_path), workspace).replace("\\", "/")


def scan_inbox(workspace: str, cfg: dict) -> dict:
    raise NotImplementedError
