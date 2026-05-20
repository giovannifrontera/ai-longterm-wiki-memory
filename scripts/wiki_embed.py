"""Chunking boundary-aware + embedding bge-m3."""

import hashlib
import re

_model = None
_tokenizer = None


def _load_model(model_name: str = "BAAI/bge-m3"):
    global _model, _tokenizer
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(model_name)
        _tokenizer = _model.tokenizer
    return _model, _tokenizer


def count_tokens(text: str, model_name: str = "BAAI/bge-m3") -> int:
    _, tokenizer = _load_model(model_name)
    return len(tokenizer.encode(text, add_special_tokens=False))


def _split_on_headings(text: str) -> list[str]:
    """Splitta il testo sui boundary ## e ### mantenendo il testo prima del primo heading."""
    parts = re.split(r'(?=^#{2,3} )', text, flags=re.MULTILINE)
    return [p for p in parts if p.strip()]


def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 64,
    threshold: int = 1500,
    model_name: str = "BAAI/bge-m3",
) -> list[str]:
    """Ritorna lista di chunk. Se il testo è sotto soglia, ritorna [text]."""
    if count_tokens(text, model_name) <= threshold:
        return [text]

    sections = _split_on_headings(text)
    chunks: list[str] = []
    current: str = ""
    current_tokens: int = 0

    for section in sections:
        sec_tokens = count_tokens(section, model_name)

        if current_tokens + sec_tokens <= chunk_size:
            current += section
            current_tokens += sec_tokens
        else:
            if current.strip():
                chunks.append(current.strip())

            if sec_tokens <= chunk_size:
                current = section
                current_tokens = sec_tokens
            else:
                # Sezione più grande del chunk_size: splitta per paragrafi
                paragraphs = section.split('\n\n')
                para_acc: str = ""
                para_tokens: int = 0
                for para in paragraphs:
                    pt = count_tokens(para, model_name)
                    if para_tokens + pt <= chunk_size:
                        para_acc += para + '\n\n'
                        para_tokens += pt
                    else:
                        if para_acc.strip():
                            chunks.append(para_acc.strip())
                        para_acc = para + '\n\n'
                        para_tokens = pt
                current = para_acc
                current_tokens = para_tokens

    if current.strip():
        chunks.append(current.strip())

    return chunks if chunks else [text]


def embed_file(
    path: str,
    chunk_size: int = 512,
    overlap: int = 64,
    threshold: int = 1500,
    model_name: str = "BAAI/bge-m3",
) -> list[dict]:
    """Legge un file .md e ritorna lista di chunk con vettori e hash."""
    with open(path, encoding="utf-8") as f:
        text = f.read()

    page_hash = hashlib.sha256(text.encode()).hexdigest()
    chunks = chunk_text(text, chunk_size, overlap, threshold, model_name)
    model, _ = _load_model(model_name)

    result = []
    for i, chunk in enumerate(chunks):
        vector = model.encode(chunk, normalize_embeddings=True).tolist()
        content_hash = hashlib.sha256(chunk.encode()).hexdigest()
        result.append({
            "chunk_id": i,
            "chunk_text": chunk,
            "vector": vector,
            "content_hash": content_hash,
            "page_hash": page_hash,
        })
    return result
