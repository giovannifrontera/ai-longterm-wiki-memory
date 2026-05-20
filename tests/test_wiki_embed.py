import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from wiki_embed import count_tokens, chunk_text

SHORT_TEXT = "Questo è un testo breve che non supera la soglia di chunking."

LONG_TEXT = "\n".join([
    "## Sezione A",
    "Contenuto della sezione A. " * 100,
    "",
    "## Sezione B",
    "Contenuto della sezione B. " * 100,
    "",
    "## Sezione C",
    "Contenuto della sezione C. " * 100,
])

def test_count_tokens_returns_int():
    n = count_tokens(SHORT_TEXT)
    assert isinstance(n, int)
    assert n > 0

def test_short_text_not_chunked():
    chunks = chunk_text(SHORT_TEXT, chunk_size=512, overlap=64, threshold=1500)
    assert len(chunks) == 1
    assert chunks[0] == SHORT_TEXT

def test_long_text_chunked():
    chunks = chunk_text(LONG_TEXT, chunk_size=512, overlap=64, threshold=1500)
    assert len(chunks) > 1

def test_all_content_preserved():
    chunks = chunk_text(LONG_TEXT, chunk_size=512, overlap=64, threshold=1500)
    combined = " ".join(chunks)
    assert "Sezione A" in combined
    assert "Sezione B" in combined
    assert "Sezione C" in combined


import tempfile
from wiki_embed import embed_file


def test_embed_file_short(tmp_path):
    md = tmp_path / "page.md"
    md.write_text("# Titolo\nContenuto breve.", encoding="utf-8")
    chunks = embed_file(str(md))
    assert len(chunks) == 1
    assert chunks[0]["chunk_id"] == 0
    assert len(chunks[0]["vector"]) == 1024
    assert len(chunks[0]["content_hash"]) == 64   # SHA256 hex
    assert len(chunks[0]["page_hash"]) == 64
    assert chunks[0]["chunk_text"] == "# Titolo\nContenuto breve."


def test_embed_file_content_hash_changes_with_content(tmp_path):
    md = tmp_path / "page.md"
    md.write_text("Contenuto A", encoding="utf-8")
    h1 = embed_file(str(md))[0]["content_hash"]
    md.write_text("Contenuto B", encoding="utf-8")
    h2 = embed_file(str(md))[0]["content_hash"]
    assert h1 != h2


def test_embed_file_path_does_not_affect_hash(tmp_path):
    md1 = tmp_path / "a.md"
    md2 = tmp_path / "b.md"
    content = "Stesso contenuto"
    md1.write_text(content, encoding="utf-8")
    md2.write_text(content, encoding="utf-8")
    h1 = embed_file(str(md1))[0]["content_hash"]
    h2 = embed_file(str(md2))[0]["content_hash"]
    assert h1 == h2  # hash = SHA256(testo), path non incluso
