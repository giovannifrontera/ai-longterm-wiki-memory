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
