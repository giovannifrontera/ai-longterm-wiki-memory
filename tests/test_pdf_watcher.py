"""Tests for wiki_pdf_watcher."""

import hashlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))


@pytest.fixture
def cfg(tmp_workspace):
    return json.loads((tmp_workspace / "wiki.config.json").read_text())


@pytest.fixture
def sample_pdf(tmp_workspace):
    """PDF fixture minimale (file binario fake per test di hash/registry)."""
    pdf_path = tmp_workspace / "pdf-inbox" / "paper1.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake content for hashing")
    return pdf_path


# ── Registry tests ──────────────────────────────────────────────────────────

def test_compute_hash(sample_pdf):
    from wiki_pdf_watcher import compute_hash
    h = compute_hash(str(sample_pdf))
    assert h.startswith("sha256:")
    assert len(h) == 71  # len("sha256:") + 64 hex chars

def test_compute_hash_is_deterministic(sample_pdf):
    from wiki_pdf_watcher import compute_hash
    assert compute_hash(str(sample_pdf)) == compute_hash(str(sample_pdf))

def test_compute_hash_differs_on_content_change(tmp_workspace):
    from wiki_pdf_watcher import compute_hash
    p = tmp_workspace / "pdf-inbox" / "a.pdf"
    p.write_bytes(b"content A")
    h1 = compute_hash(str(p))
    p.write_bytes(b"content B")
    h2 = compute_hash(str(p))
    assert h1 != h2

def test_load_registry_returns_empty_dict_when_missing(tmp_workspace):
    from wiki_pdf_watcher import load_registry
    result = load_registry(str(tmp_workspace))
    assert result == {}

def test_registry_roundtrip(tmp_workspace):
    from wiki_pdf_watcher import load_registry, save_registry
    data = {"paper1.pdf": {"hash": "sha256:abc123", "status": "deposited"}}
    save_registry(str(tmp_workspace), data)
    assert load_registry(str(tmp_workspace)) == data

def test_registry_atomic_write_leaves_no_tmp_files(tmp_workspace):
    from wiki_pdf_watcher import save_registry
    save_registry(str(tmp_workspace), {"paper1.pdf": {"status": "deposited"}})
    tmp_files = list((tmp_workspace / "pdf-inbox").glob(".registry.*.tmp"))
    assert tmp_files == []


# ── extract_text tests ───────────────────────────────────────────────────────

def test_extract_text_returns_text_from_pages(sample_pdf):
    from wiki_pdf_watcher import extract_text
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Hello World\nSecond line"
    with patch("wiki_pdf_watcher.pdfplumber") as mock_plumber:
        mock_plumber.open.return_value.__enter__.return_value.pages = [mock_page]
        result = extract_text(str(sample_pdf))
    assert "Hello World" in result
    assert "Second line" in result

def test_extract_text_joins_pages_with_double_newline(sample_pdf):
    from wiki_pdf_watcher import extract_text
    page1 = MagicMock()
    page1.extract_text.return_value = "Page one text"
    page2 = MagicMock()
    page2.extract_text.return_value = "Page two text"
    with patch("wiki_pdf_watcher.pdfplumber") as mock_plumber:
        mock_plumber.open.return_value.__enter__.return_value.pages = [page1, page2]
        result = extract_text(str(sample_pdf))
    assert result == "Page one text\n\nPage two text"

def test_scanned_pdf_no_text_returns_empty_string(sample_pdf):
    from wiki_pdf_watcher import extract_text
    mock_page = MagicMock()
    mock_page.extract_text.return_value = None
    with patch("wiki_pdf_watcher.pdfplumber") as mock_plumber:
        mock_plumber.open.return_value.__enter__.return_value.pages = [mock_page]
        result = extract_text(str(sample_pdf))
    assert result == ""


# ── deposit_raw tests ────────────────────────────────────────────────────────

def test_deposit_raw_creates_file_in_raw_dir(tmp_workspace, cfg):
    from wiki_pdf_watcher import deposit_raw
    rel = deposit_raw("# Title\n\nAbstract here.", "paper1.pdf", str(tmp_workspace), cfg)
    out = tmp_workspace / rel.replace("/", os.sep)
    assert out.exists()

def test_deposit_raw_includes_frontmatter(tmp_workspace, cfg):
    from wiki_pdf_watcher import deposit_raw
    rel = deposit_raw("Some text", "paper1.pdf", str(tmp_workspace), cfg)
    content = (tmp_workspace / rel.replace("/", os.sep)).read_text(encoding="utf-8")
    assert "source: pdf" in content
    assert "original: paper1.pdf" in content
    assert "extracted_at:" in content

def test_deposit_raw_preserves_text(tmp_workspace, cfg):
    from wiki_pdf_watcher import deposit_raw
    rel = deposit_raw("Important content here.", "paper1.pdf", str(tmp_workspace), cfg)
    content = (tmp_workspace / rel.replace("/", os.sep)).read_text(encoding="utf-8")
    assert "Important content here." in content

def test_deposit_raw_uses_project_default(tmp_workspace, cfg):
    from wiki_pdf_watcher import deposit_raw
    rel = deposit_raw("text", "paper1.pdf", str(tmp_workspace), cfg)
    assert "wiki-works/test/raw/paper1.md" == rel
