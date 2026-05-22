"""Tests for wiki_workflows.py"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def test_lint_status_written(tmp_workspace, monkeypatch):
    import wiki_lancedb, wiki_workflows

    class FakeTable:
        def to_pandas(self):
            import pandas as pd
            return pd.DataFrame({"path": []})
        def delete(self, expr):
            pass

    monkeypatch.setattr(wiki_workflows, "get_db", lambda path: object())
    monkeypatch.setattr(wiki_lancedb, "ensure_table", lambda db, table_name="wiki_pages": FakeTable())
    monkeypatch.setattr(wiki_workflows, "ensure_table", lambda db, table_name="wiki_pages": FakeTable())
    monkeypatch.setattr(wiki_workflows, "detect_renames", lambda db, fs_paths, workspace: [])

    cfg = json.loads((tmp_workspace / "wiki.config.json").read_text())

    class Args:
        workspace = str(tmp_workspace)
        full = True

    wiki_workflows.cmd_lint(Args(), cfg)

    status_path = tmp_workspace / ".wiki-lint-status.json"
    assert status_path.exists(), ".wiki-lint-status.json not created"
    data = json.loads(status_path.read_text())
    assert "last_run" in data
    assert "errors" in data
    assert "warnings" in data
    assert "detail" in data
    assert data["errors"] == 0
