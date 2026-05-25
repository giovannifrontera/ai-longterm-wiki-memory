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
    # verifica che il percorso assoluto appaia nella riga "python :" del log
    assert any(
        sys.executable in line
        for line in result.stdout.splitlines()
        if "python" in line.lower()
    ), f"sys.executable not found in python log line. stdout:\n{result.stdout}"


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


def test_verify_flag_detects_broken_exe(tmp_path):
    """--verify deve segnalare un exe rotto leggendo settings.json."""
    settings = tmp_path / "settings.json"
    broken_hook_command = "/nonexistent/python scripts/wiki_context.py --workspace . --q $CLAUDE_USER_PROMPT --k 3"
    settings.write_text(json.dumps({
        "hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": broken_hook_command}]}]}
    }))
    result = subprocess.run(
        [sys.executable, str(INSTALL_SCRIPT), "--verify", "--settings", str(settings)],
        capture_output=True, text=True
    )
    assert result.returncode != 0  # deve segnalare il problema
    assert ("broken" in result.stdout.lower() or
            "error" in result.stdout.lower() or
            "warning" in result.stdout.lower() or
            "ERROR" in result.stdout or
            "WARNING" in result.stderr)


def test_verify_flag_ok_with_valid_exe(tmp_path):
    """--verify deve confermare ok se l'exe nel hook è quello corrente."""
    settings = tmp_path / "settings.json"
    valid_command = f'"{sys.executable}" scripts/wiki_context.py --workspace . --q $CLAUDE_USER_PROMPT --k 3'
    settings.write_text(json.dumps({
        "hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": valid_command}]}]}
    }))
    result = subprocess.run(
        [sys.executable, str(INSTALL_SCRIPT), "--verify", "--settings", str(settings)],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "ok" in result.stdout.lower()
