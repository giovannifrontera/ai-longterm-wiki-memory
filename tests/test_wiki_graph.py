import json
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from wiki_graph import build_graph


def _make_page(path: Path, title: str, description: str = "", body: str = "Content.") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\ntitle: {title}\ndescription: {description}\n---\n\n{body}",
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def reset_graph_cache():
    import wiki_graph
    wiki_graph._CACHE = None
    wiki_graph._CACHE_TIME = 0.0
    wiki_graph._DIRTY = False
    yield


def test_build_graph_nodes(tmp_workspace):
    _make_page(tmp_workspace / "wiki" / "entities" / "openai.md", "OpenAI", "AI company")
    _make_page(tmp_workspace / "wiki" / "concepts" / "rag.md", "RAG")

    cfg = json.loads((tmp_workspace / "wiki.config.json").read_text())
    result = build_graph(str(tmp_workspace), cfg)

    ids = {n["id"] for n in result["nodes"]}
    assert "wiki/entities/openai" in ids
    assert "wiki/concepts/rag" in ids
    assert result["edges"] == []


def test_build_graph_excludes_index_log(tmp_workspace):
    _make_page(tmp_workspace / "wiki" / "index.md", "Index")
    _make_page(tmp_workspace / "wiki" / "log.md", "Log")
    _make_page(tmp_workspace / "wiki" / "concepts" / "rag.md", "RAG")

    cfg = json.loads((tmp_workspace / "wiki.config.json").read_text())
    result = build_graph(str(tmp_workspace), cfg)

    ids = {n["id"] for n in result["nodes"]}
    assert "wiki/index" not in ids
    assert "wiki/log" not in ids
    assert "wiki/concepts/rag" in ids


def test_build_graph_excludes_raw_dirs(tmp_workspace):
    (tmp_workspace / "wiki-works" / "test" / "raw").mkdir(parents=True, exist_ok=True)
    _make_page(tmp_workspace / "wiki-works" / "test" / "raw" / "source.md", "Source")
    _make_page(tmp_workspace / "wiki" / "concepts" / "rag.md", "RAG")

    cfg = json.loads((tmp_workspace / "wiki.config.json").read_text())
    result = build_graph(str(tmp_workspace), cfg)

    ids = {n["id"] for n in result["nodes"]}
    assert not any("raw" in nid for nid in ids)
    assert "wiki/concepts/rag" in ids


def test_node_has_required_fields(tmp_workspace):
    _make_page(tmp_workspace / "wiki" / "entities" / "openai.md", "OpenAI", "AI company")

    cfg = json.loads((tmp_workspace / "wiki.config.json").read_text())
    result = build_graph(str(tmp_workspace), cfg)

    node = next(n for n in result["nodes"] if n["id"] == "wiki/entities/openai")
    for field in ("id", "path", "title", "category", "project", "description", "last_modified"):
        assert field in node, f"Missing field: {field}"
    assert node["title"] == "OpenAI"
    assert node["description"] == "AI company"
    assert node["category"] == "entities"
    assert node["project"] == "wiki"
