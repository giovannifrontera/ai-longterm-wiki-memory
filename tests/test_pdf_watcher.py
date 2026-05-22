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
