import json, subprocess, sys
from pathlib import Path

INSTALL_SCRIPT = Path(__file__).parent.parent / "scripts" / "install_claude_code_hook.py"


def _run(tmp_path, extra_args=None):
    settings = tmp_path / "settings.json"
    settings.write_text('{"hooks": {}}')
    workspace = tmp_path / "wiki"
    workspace.mkdir()
    (workspace / "wiki.config.json").write_text('{"workspace": "."}')
    cmd = [sys.executable, str(INSTALL_SCRIPT),
           "--workspace", str(workspace),
           "--settings", str(settings),
           "--dry-run"] + (extra_args or [])
    return subprocess.run(cmd, capture_output=True, text=True), settings


def test_dry_run_writes_absolute_python_path(tmp_path):
    result, _ = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    # dry-run deve stampare il comando che verrebbe scritto
    # deve contenere un percorso assoluto, non il semplice "py"
    assert sys.executable in result.stdout


def test_dry_run_does_not_modify_settings(tmp_path):
    _, settings = _run(tmp_path)
    assert json.loads(settings.read_text()) == {"hooks": {}}


def test_explicit_python_flag_is_used_when_valid(tmp_path):
    result, _ = _run(tmp_path, ["--python", sys.executable])
    assert result.returncode == 0
    assert sys.executable in result.stdout


def test_invalid_python_exe_triggers_warning_not_crash(tmp_path):
    result, _ = _run(tmp_path, ["--python", "/nonexistent/python"])
    assert result.returncode == 0  # non deve crashare
    assert "WARNING" in result.stderr or "warning" in result.stderr.lower()
