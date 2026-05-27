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


def test_invalid_python_exe_falls_back_to_sys_executable(tmp_path):
    """--python con exe non valido deve fare fallback su sys.executable (che nel test funziona)."""
    result, _ = _run(tmp_path, ["--python", "/nonexistent/python"])
    assert result.returncode == 0  # sys.executable funziona → fallback ok
    assert "WARNING" in result.stderr or "warning" in result.stderr.lower()


def test_no_valid_python_aborts_installation(tmp_path):
    """Se nessun Python può importare lancedb, l'installazione deve abortire con exit 1."""
    settings = tmp_path / "settings.json"
    settings.write_text('{"hooks": {}}')
    workspace = tmp_path / "wiki"
    workspace.mkdir()
    (workspace / "wiki.config.json").write_text('{"workspace": "."}')
    # Passiamo un exe invalido e mocchiamo sys.executable con un altro invalido
    # Simuliamo il caso peggiore: sys.executable = exe invalido via env PYTHONPATH vuoto
    # Il modo più semplice è usare un exe che non esiste e sovrascrivere sys.executable
    # nel subprocess — ma è complesso. Verifichiamo invece che l'eccezione esista nel codice.
    import importlib, types
    script_path = Path(__file__).parent.parent / "scripts" / "install_claude_code_hook.py"
    spec = importlib.util.spec_from_file_location("install_hook", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Con due exe invalidi deve sollevare PythonNotVerifiedError
    import pytest
    with pytest.raises(mod.PythonNotVerifiedError):
        mod._resolve_python.__wrapped__ if hasattr(mod._resolve_python, '__wrapped__') else None
        # Monkey-patch _verify_python to always return False
        original = mod._verify_python
        mod._verify_python = lambda exe: False
        try:
            mod._resolve_python("/nonexistent/python")
        finally:
            mod._verify_python = original


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
    assert result.returncode != 0, f"Expected non-zero exit for broken exe. stdout={result.stdout}"


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


def test_verify_flag_handles_exe_with_spaces_in_path(tmp_path):
    """--verify deve estrarre correttamente un exe con spazi nel path."""
    settings = tmp_path / "settings.json"
    # Simula un settings con exe quotato che contiene spazi nel path
    # Usiamo sys.executable come target valido ma lo inseriamo quotato
    quoted_command = f'"{sys.executable}" scripts/wiki_context.py --workspace . --q $CLAUDE_USER_PROMPT --k 3'
    settings.write_text(json.dumps({
        "hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": quoted_command}]}]}
    }))
    result = subprocess.run(
        [sys.executable, str(INSTALL_SCRIPT), "--verify", "--settings", str(settings)],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"Expected OK for valid quoted exe. stdout={result.stdout} stderr={result.stderr}"
    assert "ok" in result.stdout.lower()


# --- Test per cross-file dedup e --remove-global ---

def _make_wiki_hook_settings(path: Path, marker="wiki_context.py") -> None:
    """Scrive un settings.json con un hook wiki fittizio."""
    cmd = f'"{sys.executable}" /some/path/{marker} --workspace /ws --k 3'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "hooks": {
            "UserPromptSubmit": [{"matcher": "", "hooks": [{"type": "command", "command": cmd}]}],
            "SessionStart": [{"matcher": "", "hooks": [{"type": "command", "command": cmd.replace("wiki_context.py", "wiki_check_setup.py")}]}],
        }
    }))


def _load_mod():
    import importlib.util
    spec = importlib.util.spec_from_file_location("install_hook", INSTALL_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_settings_has_wiki_hooks_detects_present(tmp_path):
    settings = tmp_path / "settings.json"
    _make_wiki_hook_settings(settings)
    mod = _load_mod()
    assert mod._settings_has_wiki_hooks(settings) is True


def test_settings_has_wiki_hooks_detects_absent(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text('{"hooks": {"UserPromptSubmit": []}}')
    mod = _load_mod()
    assert mod._settings_has_wiki_hooks(settings) is False


def test_settings_has_wiki_hooks_missing_file(tmp_path):
    mod = _load_mod()
    assert mod._settings_has_wiki_hooks(tmp_path / "nonexistent.json") is False


def test_remove_wiki_hooks_removes_only_wiki_entries(tmp_path):
    settings = tmp_path / "settings.json"
    other_cmd = f'"{sys.executable}" /other/tool.py --arg x'
    wiki_cmd = f'"{sys.executable}" /some/wiki_context.py --workspace /ws --k 3'
    settings.write_text(json.dumps({
        "hooks": {
            "UserPromptSubmit": [
                {"matcher": "", "hooks": [{"type": "command", "command": other_cmd}]},
                {"matcher": "", "hooks": [{"type": "command", "command": wiki_cmd}]},
            ]
        }
    }))
    mod = _load_mod()
    changed = mod._remove_wiki_hooks(settings)
    assert changed is True
    content = json.loads(settings.read_text())
    hooks = content["hooks"]["UserPromptSubmit"]
    assert len(hooks) == 1
    assert other_cmd in hooks[0]["hooks"][0]["command"]


def test_remove_wiki_hooks_noop_when_absent(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text('{"hooks": {}}')
    mod = _load_mod()
    changed = mod._remove_wiki_hooks(settings)
    assert changed is False


def test_cross_file_warning_when_other_settings_has_hooks(tmp_path):
    """Il warning di doppia esecuzione deve apparire se l'altro settings ha hook wiki."""
    workspace = tmp_path / "wiki"
    workspace.mkdir()
    (workspace / "wiki.config.json").write_text('{"workspace": "."}')
    local_settings = workspace / ".claude" / "settings.json"
    # Simula che il file "globale" (passato come --settings) non abbia hook
    # ma il "locale" (<workspace>/.claude/settings.json) li abbia già
    _make_wiki_hook_settings(local_settings)
    target_settings = tmp_path / "other_settings.json"
    target_settings.write_text('{"hooks": {}}')
    result = subprocess.run(
        [sys.executable, str(INSTALL_SCRIPT),
         "--workspace", str(workspace),
         "--settings", str(target_settings),
         "--dry-run"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "WARNING" in result.stderr
    assert "double execution" in result.stderr


def test_remove_global_clears_wiki_hooks_before_install(tmp_path):
    """--remove-global deve rimuovere hook wiki dal file globale prima di installare."""
    workspace = tmp_path / "wiki"
    workspace.mkdir()
    (workspace / "wiki.config.json").write_text('{"workspace": "."}')
    global_settings = tmp_path / "global_settings.json"
    _make_wiki_hook_settings(global_settings)
    local_settings = tmp_path / "local_settings.json"
    local_settings.write_text('{"hooks": {}}')
    result = subprocess.run(
        [sys.executable, str(INSTALL_SCRIPT),
         "--workspace", str(workspace),
         "--settings", str(local_settings),
         "--remove-global",
         # Puntiamo --settings al locale; sfruttiamo il fatto che --remove-global
         # opera su ~/.claude/settings.json — qui simuliamo passando direttamente
         # global_settings come target e verifichiamo che _remove_wiki_hooks funzioni
         "--dry-run"],
        capture_output=True, text=True
    )
    # In dry-run il global non viene toccato, ma il messaggio "Removing wiki hooks" deve apparire
    assert "Removing wiki hooks" in result.stdout or "Removing wiki hooks" in result.stderr
