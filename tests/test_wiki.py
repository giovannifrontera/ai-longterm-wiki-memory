import json
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from wiki import load_config, ConfigError, acquire_lock, release_lock

def test_load_config_ok(tmp_workspace):
    cfg = load_config(str(tmp_workspace / "wiki.config.json"))
    assert cfg["lancedb"]["embedding_model"] == "BAAI/bge-m3"
    assert "thresholds" in cfg

def test_load_config_missing_field(tmp_workspace):
    path = tmp_workspace / "wiki.config.json"
    cfg = json.loads(path.read_text())
    del cfg["thresholds"]["staleness_days"]
    path.write_text(json.dumps(cfg))
    with pytest.raises(ConfigError) as exc:
        load_config(str(path))
    assert "staleness_days" in str(exc.value)

def test_load_config_file_not_found(tmp_workspace):
    with pytest.raises(ConfigError):
        load_config(str(tmp_workspace / "nonexistent.json"))

def test_lock_acquire_and_release(tmp_workspace):
    lock_path = str(tmp_workspace / ".wiki-lock")
    acquire_lock(lock_path)
    assert os.path.exists(lock_path)
    release_lock(lock_path)
    assert not os.path.exists(lock_path)

def test_lock_already_exists(tmp_workspace):
    lock_path = str(tmp_workspace / ".wiki-lock")
    acquire_lock(lock_path)
    with pytest.raises(RuntimeError) as exc:
        acquire_lock(lock_path)
    assert "lock_exists" in str(exc.value)
    release_lock(lock_path)
