#!/usr/bin/env python3
"""Cross-agent installer, hot-configurator, and smell diagnostic CLI for Unarmored.

Supports Google Antigravity, Claude Code, OpenAI Codex CLI (hooks) and DeepSeek Harness / DSH
(static rules block + skill), global or workspace-scoped. Profile packs found in `<repo>/packs/*.json`
are bundled into every install; the public repository ships none.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PLUGIN_NAME = "unarmored"
MANIFEST_FILENAME = ".unarmored-install-manifest.json"
FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
UNSAFE_PYTHON_EXE_CHARS = set('%$`!"\r\n')
HEX_BOOTSTRAP_SCRIPT_CHARS = set('%$`!"&|<>^()\'\r\n')

BUNDLE_FILES = [
    "VERSION",
    "LICENSE",
    "plugin.json",
    "README.md",
    "assets/logo.svg",
    "rules/AGENTS.md",
    "scripts/unarmored_hook.py",
    "skills/unarmored/SKILL.md",
    "skills/unarmored/agents/openai.yaml",
    "skills/unarmored/references/model-profiles.md",
    "skills/unarmored/references/anti-slop-patterns.md",
]

PACK_SCHEMA = "unarmored-pack/1"
HOOK_AGENTS = ("antigravity", "claude", "codex")
ALL_AGENTS = ("antigravity", "claude", "codex", "dsh")
AGENT_CHOICES = (*ALL_AGENTS, "all")
DSH_BLOCK_BEGIN = "<!-- unarmored:begin -->"
DSH_BLOCK_END = "<!-- unarmored:end -->"


def bundled_pack_files(root: Path) -> dict[str, bytes]:
    """Collect `<root>/packs/*.json` profile packs (validated schema) for bundling into installs."""
    out: dict[str, bytes] = {}
    pack_dir = root / "packs"
    if not pack_dir.is_dir():
        return out
    if is_reparse_or_symlink(pack_dir):
        raise ManageError(f"Refusing to bundle packs from symlink or junction: {pack_dir}")
    for pack in sorted(pack_dir.glob("*.json")):
        if is_reparse_or_symlink(pack) or not pack.is_file():
            raise ManageError(f"Refusing to bundle non-regular pack file: {pack}")
        data = pack.read_bytes()
        try:
            parsed = json.loads(data.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ManageError(f"Malformed profile pack {pack}: {exc}") from exc
        if not isinstance(parsed, dict) or parsed.get("schema") != PACK_SCHEMA:
            raise ManageError(f"Profile pack {pack} must declare \"schema\": \"{PACK_SCHEMA}\"")
        out[f"packs/{pack.name}"] = data
    return out


class ManageError(RuntimeError):
    """Expected user-facing management error."""


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json_file_checked(path: Path) -> dict:
    try:
        data = json.loads(path.read_bytes().decode("utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ManageError(f"Malformed JSON in existing configuration file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ManageError(f"Expected top-level JSON object in {path}")
    return data


def is_reparse_or_symlink(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        if os.name == "nt" and path.exists():
            st = os.lstat(path)
            attrs = getattr(st, "st_file_attributes", 0)
            if attrs & FILE_ATTRIBUTE_REPARSE_POINT:
                return True
    except OSError:
        return False
    return False


def ensure_safe_target(path: Path, stop_at: Path | None = None) -> None:
    cur = path
    boundary = None
    if stop_at is not None:
        try:
            boundary = stop_at.resolve() if stop_at.exists() else stop_at.absolute()
        except OSError:
            boundary = stop_at.absolute()

    visited = set()
    while cur not in visited:
        visited.add(cur)
        if boundary is not None:
            try:
                cur_cmp = cur.resolve() if cur.exists() and not is_reparse_or_symlink(cur) else cur.absolute()
                if cur_cmp == boundary:
                    break
            except OSError:
                pass
        if is_reparse_or_symlink(cur):
            raise ManageError(f"Refusing to traverse symlink or Windows junction: {cur}")
        if cur.parent == cur:
            break
        cur = cur.parent


def ensure_tree_no_reparse(root_dir: Path) -> None:
    if is_reparse_or_symlink(root_dir):
        raise ManageError(f"Refusing to delete symlink or Windows junction: {root_dir}")
    for dirpath, dirnames, filenames in os.walk(root_dir, followlinks=False):
        base = Path(dirpath)
        for name in dirnames + filenames:
            candidate = base / name
            if is_reparse_or_symlink(candidate):
                raise ManageError(f"Refusing to remove directory containing symlink or junction: {candidate}")


def atomic_write_bytes(path: Path, data: bytes, stop_at: Path | None = None) -> None:
    ensure_safe_target(path, stop_at=stop_at)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _atomic_write_json(path: Path, data: dict, stop_at: Path | None = None) -> None:
    atomic_write_bytes(path, (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8"), stop_at=stop_at)


def _guard_owned_dir_for_install(target_dir: Path, boundary: Path, label: str, force: bool) -> Path:
    ensure_safe_target(target_dir, stop_at=boundary)
    manifest_path = target_dir / MANIFEST_FILENAME
    if target_dir.exists() and not manifest_path.is_file() and not force:
        raise ManageError(f"Unowned {label} directory exists: {target_dir} (pass --force to overwrite)")
    return manifest_path


def _verify_owned_dir_for_uninstall(target_dir: Path, boundary: Path, label: str, force: bool) -> dict:
    ensure_safe_target(target_dir, stop_at=boundary)
    ensure_tree_no_reparse(target_dir)
    manifest_path = target_dir / MANIFEST_FILENAME
    if not manifest_path.is_file() and not force:
        raise ManageError(f"Refusing to remove unowned {label} directory without --force: {target_dir}")
    if manifest_path.is_file():
        if not force:
            return _verify_manifest_hashes(target_dir, manifest_path)
        try:
            return load_json_file_checked(manifest_path)
        except ManageError:
            return {}
    return {}


def _verify_manifest_hashes(target_dir: Path, manifest_path: Path) -> dict:
    manifest = load_json_file_checked(manifest_path)
    tracked_files = manifest.get("files") or {}
    tracked_norm = {rel.replace("\\", "/") for rel in tracked_files}

    for rel, expected_sha in tracked_files.items():
        f = target_dir / rel
        if f.is_file() and sha256_bytes(f.read_bytes()) != expected_sha:
            raise ManageError(f"Modified file detected in installation ({f}); pass --force to remove anyway.")

    for dirpath, dirnames, filenames in os.walk(target_dir, followlinks=False):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        base = Path(dirpath)
        for fname in filenames:
            if fname == MANIFEST_FILENAME or fname.endswith((".pyc", ".pyo")):
                continue
            full_path = base / fname
            rel_norm = full_path.relative_to(target_dir).as_posix()
            if rel_norm not in tracked_norm:
                raise ManageError(f"Untracked user file detected in installation ({full_path}); pass --force to remove anyway.")

    return manifest


def _is_valid_python_binary(candidate: str) -> bool:
    if not candidate:
        return False
    if any(ch in candidate for ch in UNSAFE_PYTHON_EXE_CHARS):
        return False
    norm = candidate.replace("/", "\\").lower()
    if "\\microsoft\\windowsapps\\" in norm:
        return False
    p = Path(candidate)
    if not p.is_file():
        return False
    try:
        if p.stat().st_size == 0:
            return False
    except OSError:
        return False
    try:
        proc = subprocess.run(
            [str(p), "-E", "-S", "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        return proc.returncode == 0
    except Exception:
        return False


def resolve_real_python() -> str:
    """Locate a verified Python >=3.10 interpreter, skipping WindowsApps 9009 stubs."""
    candidates: list[str] = []
    if sys.executable:
        candidates.append(sys.executable)

    if os.name == "nt":
        try:
            res = subprocess.run(["where.exe", "python"], capture_output=True, text=True, timeout=5, check=False)
            if res.returncode == 0:
                candidates.extend(line.strip() for line in res.stdout.splitlines() if line.strip())
        except Exception:
            pass
        local_app = os.environ.get("LOCALAPPDATA", "")
        prog_data = os.environ.get("ProgramData", r"C:\ProgramData")
        user_home = str(Path.home())
        for pattern_base in [
            Path(prog_data) / "anaconda3" / "python.exe",
            Path(prog_data) / "miniconda3" / "python.exe",
            Path(user_home) / "anaconda3" / "python.exe",
            Path(user_home) / "miniconda3" / "python.exe",
            Path(user_home) / "scoop" / "apps" / "python" / "current" / "python.exe",
        ]:
            candidates.append(str(pattern_base))
        if local_app:
            py_dir = Path(local_app) / "Programs" / "Python"
            if py_dir.is_dir():
                for sub in sorted(py_dir.glob("Python3*"), reverse=True):
                    candidates.append(str(sub / "python.exe"))
    else:
        for name in ("python3", "python"):
            found = shutil.which(name)
            if found:
                candidates.append(found)

    seen = set()
    for cand in candidates:
        key = os.path.normcase(os.path.abspath(cand)) if cand else ""
        if not key or key in seen:
            continue
        seen.add(key)
        if _is_valid_python_binary(cand):
            return os.path.abspath(cand)

    raise ManageError("Could not locate a working Python >=3.10 executable (excluding WindowsApps stubs).")


def format_antigravity_command(python_exe: str, rel_script: str = "scripts/unarmored_hook.py", is_windows: bool | None = None) -> str:
    """Build a cmd.exe /c and sh -c safe command when CWD is guaranteed to be <plugin_root>."""
    if any(ch in python_exe for ch in UNSAFE_PYTHON_EXE_CHARS):
        raise ManageError(f"Python path contains unsafe shell expansion characters: {python_exe}")
    win = (os.name == "nt") if is_windows is None else is_windows
    rel_clean = rel_script.replace("\\", "/").lstrip("./")
    if win:
        py_fwd = python_exe.replace("\\", "/")
        return f'cd . && "{py_fwd}" -E -S "{rel_clean}"'
    return f"{shlex.quote(python_exe)} -E -S {shlex.quote(rel_clean)}"


def _windows_python_invocation(python_exe: str, abs_script: str) -> str:
    if any(ch in python_exe for ch in UNSAFE_PYTHON_EXE_CHARS):
        raise ManageError(f"Python path contains unsafe shell expansion characters: {python_exe}")
    py_fwd = python_exe.replace("\\", "/")
    sc_fwd = abs_script.replace("\\", "/")
    if any(ch in sc_fwd for ch in HEX_BOOTSTRAP_SCRIPT_CHARS):
        hex_path = sc_fwd.encode("utf-8").hex()
        return (
            f'"{py_fwd}" -E -S -c '
            f"\"import os,runpy;os.environ['UNARMORED_TAG']='unarmored_hook.py';"
            f"runpy.run_path(bytes.fromhex('{hex_path}').decode('utf-8'),run_name='__main__')\""
        )
    return f'"{py_fwd}" -E -S "{sc_fwd}"'


def format_external_hook_command(python_exe: str, abs_script: str, is_windows: bool | None = None) -> str:
    """Build a dual-shell command valid across Windows `cmd.exe /c`, `cmd /d /s /c`, and Git Bash (`bash -c`), plus POSIX `sh -c`.

    Prefixes `cd . && ` on Windows so the first character is never `"`, preventing `cmd.exe /c` quote stripping.
    """
    win = (os.name == "nt") if is_windows is None else is_windows
    if win:
        return f"cd . && {_windows_python_invocation(python_exe, abs_script)}"
    if any(ch in python_exe for ch in UNSAFE_PYTHON_EXE_CHARS):
        raise ManageError(f"Python path contains unsafe shell expansion characters: {python_exe}")
    return f"{shlex.quote(python_exe)} -E -S {shlex.quote(abs_script)}"


def format_codex_windows_command(python_exe: str, abs_script: str) -> str:
    """Build a Codex `commandWindows` string valid in PowerShell 5.1, pwsh 7, `cmd.exe /c`, and `cmd /d /s /c`."""
    return f'cmd.exe --% /d /s /c "{_windows_python_invocation(python_exe, abs_script)}"'


def build_antigravity_hooks_dict(python_exe: str) -> dict:
    cmd = format_antigravity_command(python_exe, "scripts/unarmored_hook.py")
    handler = {"type": "command", "command": cmd, "timeout": 10}
    return {
        "unarmored-calibration": {
            "enabled": True,
            "SessionStart": [dict(handler)],
            "PreInvocation": [dict(handler)],
            "Stop": [dict(handler)],
        }
    }


def _is_our_hook_handler(handler: object) -> bool:
    if not isinstance(handler, dict):
        return False
    cmd = str(handler.get("command") or "") + " " + str(handler.get("commandWindows") or "")
    return "unarmored_hook.py" in cmd


def _clean_event_entries(entries: list) -> list:
    """Remove only Unarmored handlers while preserving flat third-party handlers and empty groups untouched."""
    cleaned = []
    for item in entries:
        if not isinstance(item, dict):
            cleaned.append(item)
            continue
        if "hooks" not in item or not isinstance(item.get("hooks"), list):
            # Flat third-party handler object
            if not _is_our_hook_handler(item):
                cleaned.append(item)
            continue
        orig_inner = item["hooks"]
        had_ours = any(_is_our_hook_handler(h) for h in orig_inner)
        if not had_ours:
            cleaned.append(item)
            continue
        kept_inner = [h for h in orig_inner if not _is_our_hook_handler(h)]
        if kept_inner:
            new_grp = dict(item)
            new_grp["hooks"] = kept_inner
            cleaned.append(new_grp)
    return cleaned


def _merge_grouped_hooks_config(
    existing: dict,
    events: list[str],
    handler_factory,
    strict_hooks_only_root: bool = False,
) -> dict:
    hooks_map = dict(existing.get("hooks")) if isinstance(existing, dict) and isinstance(existing.get("hooks"), dict) else {}

    for ev in events:
        raw_list = list(hooks_map.get(ev)) if isinstance(hooks_map.get(ev), list) else []
        cleaned = _clean_event_entries(raw_list)
        cleaned.append({"hooks": [handler_factory(ev)]})
        hooks_map[ev] = cleaned

    if strict_hooks_only_root:
        # Codex CLI `HooksFile` uses `#[serde(deny_unknown_fields)]` and allows ONLY top-level `hooks`
        return {"hooks": hooks_map}

    out = dict(existing) if isinstance(existing, dict) else {}
    out["hooks"] = hooks_map
    return out


def _remove_our_grouped_hooks(existing: dict, strict_hooks_only_root: bool = False) -> dict:
    if not isinstance(existing, dict) or not isinstance(existing.get("hooks"), dict):
        return {"hooks": {}} if strict_hooks_only_root else existing

    hooks_map = {}
    for ev, raw_list in existing["hooks"].items():
        if not isinstance(raw_list, list):
            hooks_map[ev] = raw_list
            continue
        had_ours_anywhere = any(
            _is_our_hook_handler(item)
            or (isinstance(item, dict) and isinstance(item.get("hooks"), list) and any(_is_our_hook_handler(h) for h in item["hooks"]))
            for item in raw_list
        )
        if not had_ours_anywhere:
            hooks_map[ev] = raw_list
            continue
        cleaned = _clean_event_entries(raw_list)
        if cleaned:
            hooks_map[ev] = cleaned

    if strict_hooks_only_root:
        return {"hooks": hooks_map} if hooks_map else {}

    out = dict(existing)
    if hooks_map:
        out["hooks"] = hooks_map
    else:
        out.pop("hooks", None)
    return out


def _antigravity_paths(workspace: Path | None) -> tuple[Path, Path]:
    boundary = workspace if workspace else Path.home()
    dest_dir = (
        workspace / ".agents" / "plugins" / PLUGIN_NAME
        if workspace
        else Path.home() / ".gemini" / "config" / "plugins" / PLUGIN_NAME
    )
    return boundary, dest_dir


def _claude_paths(workspace: Path | None) -> tuple[Path, Path, Path]:
    boundary = workspace if workspace else Path.home()
    base_dir = (workspace / ".claude") if workspace else (Path.home() / ".claude")
    return boundary, base_dir / "skills" / PLUGIN_NAME, base_dir / "settings.json"


def install_antigravity(root: Path, python_exe: str, workspace: Path | None, dry_run: bool, force: bool) -> dict:
    boundary, dest_dir = _antigravity_paths(workspace)
    manifest_path = _guard_owned_dir_for_install(dest_dir, boundary, "Antigravity plugin", force)

    planned_files: dict[str, bytes] = {}
    for rel in BUNDLE_FILES:
        src = root / rel
        if not src.is_file():
            raise ManageError(f"Missing source bundle file: {src}")
        planned_files[rel] = src.read_bytes()
    planned_files.update(bundled_pack_files(root))
    planned_files["hooks.json"] = (json.dumps(build_antigravity_hooks_dict(python_exe), indent=2, ensure_ascii=False) + "\n").encode("utf-8")

    if not dry_run:
        written_hashes = {}
        for rel, data in planned_files.items():
            atomic_write_bytes(dest_dir / rel, data, stop_at=boundary)
            written_hashes[rel] = sha256_bytes(data)
        _atomic_write_json(
            manifest_path,
            {"plugin": PLUGIN_NAME, "agent": "antigravity", "python_exe": python_exe, "files": written_hashes},
            stop_at=boundary,
        )
    return {"agent": "antigravity", "path": str(dest_dir), "dry_run": dry_run, "files_count": len(planned_files)}


def uninstall_antigravity(workspace: Path | None, dry_run: bool, force: bool) -> dict:
    boundary, dest_dir = _antigravity_paths(workspace)
    if not dest_dir.exists():
        return {"agent": "antigravity", "path": str(dest_dir), "removed": False, "reason": "not_installed"}
    _verify_owned_dir_for_uninstall(dest_dir, boundary, "Antigravity plugin", force)
    if not dry_run:
        shutil.rmtree(dest_dir)
    return {"agent": "antigravity", "path": str(dest_dir), "removed": True, "dry_run": dry_run}


def _copy_skill_and_hook_bundle(root: Path, skill_dest: Path, boundary: Path, dry_run: bool) -> dict[str, str]:
    files_map = {
        "SKILL.md": (root / "skills" / PLUGIN_NAME / "SKILL.md").read_bytes(),
        "agents/openai.yaml": (root / "skills" / PLUGIN_NAME / "agents" / "openai.yaml").read_bytes(),
        "references/model-profiles.md": (root / "skills" / PLUGIN_NAME / "references" / "model-profiles.md").read_bytes(),
        "references/anti-slop-patterns.md": (root / "skills" / PLUGIN_NAME / "references" / "anti-slop-patterns.md").read_bytes(),
        "scripts/unarmored_hook.py": (root / "scripts" / "unarmored_hook.py").read_bytes(),
    }
    files_map.update(bundled_pack_files(root))
    hashes = {}
    for rel, content in files_map.items():
        hashes[rel] = sha256_bytes(content)
        if not dry_run:
            atomic_write_bytes(skill_dest / rel, content, stop_at=boundary)
    return hashes


def install_claude(root: Path, python_exe: str, workspace: Path | None, dry_run: bool, force: bool) -> dict:
    boundary, skill_dest, settings_path = _claude_paths(workspace)
    manifest_path = _guard_owned_dir_for_install(skill_dest, boundary, "Claude skill", force)
    ensure_safe_target(settings_path, stop_at=boundary)

    cmd = format_external_hook_command(python_exe, str(skill_dest / "scripts" / "unarmored_hook.py"))
    had_settings = settings_path.is_file()
    existing_settings = load_json_file_checked(settings_path) if had_settings else {}
    merged = _merge_grouped_hooks_config(
        existing_settings,
        ["SessionStart", "UserPromptSubmit", "PostModelSwitch", "PreCompact", "Stop"],
        lambda _ev: {"type": "command", "command": cmd, "timeout": 10},
    )

    hashes = _copy_skill_and_hook_bundle(root, skill_dest, boundary, dry_run)
    if not dry_run:
        _atomic_write_json(settings_path, merged, stop_at=boundary)
        _atomic_write_json(
            manifest_path,
            {
                "plugin": PLUGIN_NAME,
                "agent": "claude",
                "python_exe": python_exe,
                "settings_path": str(settings_path),
                "had_settings_before": had_settings,
                "files": hashes,
            },
            stop_at=boundary,
        )
    return {"agent": "claude", "skill_path": str(skill_dest), "settings_path": str(settings_path), "dry_run": dry_run}


def uninstall_claude(workspace: Path | None, dry_run: bool, force: bool) -> dict:
    boundary, skill_dest, settings_path = _claude_paths(workspace)
    removed_any = False
    had_settings_before = True

    if skill_dest.exists():
        mdata = _verify_owned_dir_for_uninstall(skill_dest, boundary, "Claude skill", force)
        had_settings_before = bool(mdata.get("had_settings_before", True))

    if settings_path.is_file():
        ensure_safe_target(settings_path, stop_at=boundary)
        current = load_json_file_checked(settings_path)
        cleaned = _remove_our_grouped_hooks(current)
        if cleaned != current:
            removed_any = True
            if not dry_run:
                if cleaned or had_settings_before:
                    _atomic_write_json(settings_path, cleaned, stop_at=boundary)
                else:
                    settings_path.unlink()

    if skill_dest.exists():
        removed_any = True
        if not dry_run:
            shutil.rmtree(skill_dest)
    return {"agent": "claude", "skill_path": str(skill_dest), "removed": removed_any, "dry_run": dry_run}


def _codex_paths(workspace: Path | None) -> tuple[Path, Path, Path]:
    codex_home = Path(os.environ["CODEX_HOME"]).resolve() if (not workspace and os.environ.get("CODEX_HOME")) else None
    boundary = workspace if workspace else (codex_home or Path.home())
    codex_dir = (workspace / ".codex") if workspace else (codex_home or (Path.home() / ".codex"))
    skill_dest = (
        (workspace / ".agents" / "skills" / PLUGIN_NAME)
        if workspace
        else ((codex_home / "skills" / PLUGIN_NAME) if codex_home else (Path.home() / ".agents" / "skills" / PLUGIN_NAME))
    )
    return boundary, codex_dir, skill_dest


def install_codex(root: Path, python_exe: str, workspace: Path | None, dry_run: bool, force: bool) -> dict:
    boundary, codex_dir, skill_dest = _codex_paths(workspace)
    hooks_path = codex_dir / "hooks.json"
    manifest_path = _guard_owned_dir_for_install(skill_dest, boundary, "Codex skill", force)
    ensure_safe_target(hooks_path, stop_at=boundary)

    script_target = skill_dest / "scripts" / "unarmored_hook.py"
    if os.name == "nt":
        posix_rel = ".agents/skills/unarmored/scripts/unarmored_hook.py" if workspace else "~/.agents/skills/unarmored/scripts/unarmored_hook.py"
        posix_cmd = f"python3 -E -S {posix_rel}"
    else:
        posix_cmd = format_external_hook_command(python_exe, str(script_target), is_windows=False)
    win_cmd = (
        format_codex_windows_command(python_exe, str(script_target))
        if os.name == "nt"
        else 'cmd.exe --% /d /s /c "python -E -S \"%USERPROFILE%/.agents/skills/unarmored/scripts/unarmored_hook.py\""'
    )

    existing_hooks = load_json_file_checked(hooks_path) if hooks_path.is_file() else {}

    def _make_codex_handler(ev: str) -> dict:
        h = {"type": "command", "command": posix_cmd, "commandWindows": win_cmd, "timeout": 10}
        if ev != "Stop":
            h["additionalContextLimit"] = 4000
        return h

    merged = _merge_grouped_hooks_config(
        existing_hooks, ["SessionStart", "UserPromptSubmit", "Stop"], _make_codex_handler, strict_hooks_only_root=True
    )
    hashes = _copy_skill_and_hook_bundle(root, skill_dest, boundary, dry_run)
    if not dry_run:
        _atomic_write_json(hooks_path, merged, stop_at=boundary)
        _atomic_write_json(
            manifest_path,
            {"plugin": PLUGIN_NAME, "agent": "codex", "python_exe": python_exe, "hooks_path": str(hooks_path), "files": hashes},
            stop_at=boundary,
        )
    return {"agent": "codex", "skill_path": str(skill_dest), "hooks_path": str(hooks_path), "dry_run": dry_run}


def uninstall_codex(workspace: Path | None, dry_run: bool, force: bool) -> dict:
    boundary, codex_dir, skill_dest = _codex_paths(workspace)
    hooks_path = codex_dir / "hooks.json"
    removed_any = False

    if skill_dest.exists():
        _verify_owned_dir_for_uninstall(skill_dest, boundary, "Codex skill", force)

    if hooks_path.is_file():
        ensure_safe_target(hooks_path, stop_at=boundary)
        current = load_json_file_checked(hooks_path)
        cleaned = _remove_our_grouped_hooks(current, strict_hooks_only_root=True)
        if cleaned != current:
            removed_any = True
            if not dry_run:
                if cleaned.get("hooks"):
                    _atomic_write_json(hooks_path, cleaned, stop_at=boundary)
                else:
                    hooks_path.unlink()

    if skill_dest.exists():
        removed_any = True
        if not dry_run:
            shutil.rmtree(skill_dest)
    return {"agent": "codex", "skill_path": str(skill_dest), "removed": removed_any, "dry_run": dry_run}


def _dsh_paths(workspace: Path | None, dsh_home: Path | None = None) -> tuple[Path, Path, Path]:
    """Return (boundary, skill_dest, agents_md) for DeepSeek Harness (DSH).

    Global: `$DSH_HOME` (default `~/.dsh`) -> `<home>/skills/unarmored` + `<home>/AGENTS.md`.
    Workspace: `<ws>/.dsh/skills/unarmored` + `<ws>/AGENTS.md`.
    """
    if workspace is not None:
        return workspace, workspace / ".dsh" / "skills" / PLUGIN_NAME, workspace / "AGENTS.md"
    if dsh_home is None:
        env_home = os.environ.get("DSH_HOME")
        dsh_home = Path(env_home) if env_home else (Path.home() / ".dsh")
    home = dsh_home.absolute()
    return home, home / "skills" / PLUGIN_NAME, home / "AGENTS.md"


def _default_block_language() -> str:
    import locale

    for probe in (os.environ.get("LANG", ""), os.environ.get("LC_ALL", "")):
        if probe.lower().startswith("zh"):
            return "zh"
    try:
        loc = (locale.getlocale()[0] or "").lower()
    except Exception:
        loc = ""
    return "zh" if loc.startswith(("zh", "chinese")) else "en"


def render_dsh_block(root: Path, lang: str) -> str:
    """Static rules block for hosts without lifecycle hooks; folds in bundled pack voice/deepseek directive."""
    template = (root / "adapters" / "dsh" / f"AGENTS.block.{lang}.md").read_text(encoding="utf-8").strip()
    extras: list[str] = []
    for rel, data in bundled_pack_files(root).items():
        pack = json.loads(data.decode("utf-8-sig"))
        voice = (pack.get("voice") or {}).get(lang) if isinstance(pack.get("voice"), dict) else None
        ds = ((pack.get("directives") or {}).get("deepseek") or {}).get(lang) if isinstance(pack.get("directives"), dict) else None
        for text in (voice, ds):
            if isinstance(text, str) and text.strip():
                extras.append(f"- {text.strip()[:600]}")
    body = template + ("\n" + "\n".join(extras) if extras else "")
    return f"{DSH_BLOCK_BEGIN}\n{body}\n{DSH_BLOCK_END}\n"


def _strip_dsh_block(text: str) -> tuple[str, bool]:
    start = text.find(DSH_BLOCK_BEGIN)
    if start == -1:
        return text, False
    end = text.find(DSH_BLOCK_END, start)
    if end == -1:
        raise ManageError("Found Unarmored begin marker without end marker in AGENTS.md; fix it manually before continuing.")
    end += len(DSH_BLOCK_END)
    before = text[:start].rstrip("\r\n")
    after = text[end:].lstrip("\r\n")
    if before and after:
        merged = before + "\n\n" + after
    else:
        merged = before or after
    if merged and not merged.endswith("\n"):
        merged += "\n"
    return merged, True


def install_dsh(
    root: Path,
    workspace: Path | None,
    dry_run: bool,
    force: bool,
    dsh_home: Path | None = None,
    lang: str | None = None,
) -> dict:
    boundary, skill_dest, agents_md = _dsh_paths(workspace, dsh_home)
    manifest_path = _guard_owned_dir_for_install(skill_dest, boundary, "DSH skill", force)
    ensure_safe_target(agents_md, stop_at=boundary)

    block_lang = lang if lang in ("zh", "en") else _default_block_language()
    block = render_dsh_block(root, block_lang)
    had_agents_md = agents_md.is_file()
    base = _strip_dsh_block(agents_md.read_bytes().decode("utf-8-sig"))[0] if had_agents_md else ""
    new_text = (base.rstrip("\r\n") + "\n\n" + block) if base.strip() else block

    hashes = _copy_skill_and_hook_bundle(root, skill_dest, boundary, dry_run)
    if not dry_run:
        prev_manifest = {}
        if manifest_path.is_file():
            try:
                prev_manifest = load_json_file_checked(manifest_path)
            except ManageError:
                prev_manifest = {}
        atomic_write_bytes(agents_md, new_text.encode("utf-8"), stop_at=boundary)
        _atomic_write_json(
            manifest_path,
            {
                "plugin": PLUGIN_NAME,
                "agent": "dsh",
                "agents_md": str(agents_md),
                "created_agents_md": bool(prev_manifest.get("created_agents_md", not had_agents_md)),
                "block_language": block_lang,
                "files": hashes,
            },
            stop_at=boundary,
        )
    return {
        "agent": "dsh",
        "skill_path": str(skill_dest),
        "agents_md": str(agents_md),
        "block_language": block_lang,
        "dry_run": dry_run,
    }


def uninstall_dsh(workspace: Path | None, dry_run: bool, force: bool, dsh_home: Path | None = None) -> dict:
    boundary, skill_dest, agents_md = _dsh_paths(workspace, dsh_home)
    removed_any = False
    created_agents_md = False

    if skill_dest.exists():
        mdata = _verify_owned_dir_for_uninstall(skill_dest, boundary, "DSH skill", force)
        created_agents_md = bool(mdata.get("created_agents_md", False))

    if agents_md.is_file():
        ensure_safe_target(agents_md, stop_at=boundary)
        cleaned, had_block = _strip_dsh_block(agents_md.read_bytes().decode("utf-8-sig"))
        if had_block:
            removed_any = True
            if not dry_run:
                if cleaned.strip() or not created_agents_md:
                    atomic_write_bytes(agents_md, cleaned.encode("utf-8"), stop_at=boundary)
                else:
                    agents_md.unlink()

    if skill_dest.exists():
        removed_any = True
        if not dry_run:
            shutil.rmtree(skill_dest)

    return {"agent": "dsh", "skill_path": str(skill_dest), "agents_md": str(agents_md), "removed": removed_any, "dry_run": dry_run}


def config_file_path() -> Path:
    override = os.environ.get("UNARMORED_CONFIG")
    if override:
        return Path(override)
    state_override = os.environ.get("UNARMORED_STATE_DIR")
    if state_override:
        return Path(os.path.abspath(state_override)) / "config.json"
    plugin_data = os.environ.get("PLUGIN_DATA")
    if plugin_data:
        return Path(os.path.abspath(plugin_data)) / "unarmored" / "config.json"
    return Path.home() / ".unarmored" / "config.json"


def _load_hook_module():
    scripts_dir = str(repo_root() / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import unarmored_hook

    return unarmored_hook


def configure_runtime(args: argparse.Namespace) -> dict:
    unarmored_hook = _load_hook_module()

    cfg_path = config_file_path()
    # Preserve sparse config so unspecified fields never clobber profile pack `defaults`,
    # and refuse to silently overwrite a syntactically corrupt existing config.json.
    current: dict = {}
    if cfg_path.is_file():
        current = load_json_file_checked(cfg_path)

    if args.tone:
        current["tone"] = args.tone
    if args.language:
        current["language"] = args.language
    if args.enable:
        current["enabled"] = True
    elif args.disable:
        current["enabled"] = False
    if args.stop_guard:
        current["stop_guard"] = args.stop_guard == "on"
    if getattr(args, "clear_aliases", False):
        current["model_aliases"] = {}
    if getattr(args, "set_alias", None):
        aliases = dict(current.get("model_aliases") or {})
        for raw_pair in args.set_alias:
            if "=" not in raw_pair:
                raise ManageError(f"Expected KEY=FAMILY in --set-alias, got: {raw_pair!r}")
            k, v = raw_pair.split("=", 1)
            kl, vl = k.strip().lower(), v.strip().lower()
            if not kl or vl not in unarmored_hook.VALID_FAMILIES:
                raise ManageError(
                    f"Invalid --set-alias {raw_pair!r}; family must be one of {unarmored_hook.VALID_FAMILIES}"
                )
            aliases[kl] = vl
        current["model_aliases"] = aliases
    if getattr(args, "add_ignore_session", None):
        existing_ign = list(current.get("ignore_session_patterns") or [])
        for pat in args.add_ignore_session:
            p = pat.strip()
            if p and p not in existing_ign:
                existing_ign.append(p)
        current["ignore_session_patterns"] = existing_ign
    if getattr(args, "add_ignore_marker", None):
        existing_mk = list(current.get("ignore_prompt_markers") or [])
        for mk in args.add_ignore_marker:
            m = mk.strip()
            if m and m not in existing_mk:
                existing_mk.append(m)
        current["ignore_prompt_markers"] = existing_mk

    try:
        prev_epoch = int(current.get("epoch", 1))
    except (TypeError, ValueError):
        prev_epoch = 1
    current["epoch"] = prev_epoch + 1
    _atomic_write_json(cfg_path, current)
    return {"config_path": str(cfg_path), "config": current}


def _diagnose_single_text(text: str, prompt_text: str, model_hint: str, cfg: dict, unarmored_hook) -> dict:
    unarmored_hook.set_active_strip_patterns(cfg.get("model_strip_patterns") or [])
    fam = unarmored_hook.classify_model_family(model_hint or "", cfg.get("model_aliases"))
    cfg_lang = cfg.get("language", "auto")
    if cfg_lang in ("zh", "en"):
        lang = cfg_lang
    else:
        lang = unarmored_hook._infer_text_language(text) or unarmored_hook._infer_text_language(prompt_text) or "zh"
    mode = unarmored_hook.classify_intent(prompt_text) if prompt_text else ""
    report = unarmored_hook.analyze_response_smells(text, mode=mode, tone=cfg.get("tone", "peer"))
    overcorr_kind = str(report.get("overcorrection_kind") or "")
    remedy = (
        unarmored_hook.format_smell_remedy(report["smells"], lang, overcorrection_kind=overcorr_kind)
        if report["score"] >= 2
        else ""
    )
    stance = report.get("stance") or {}
    spans = unarmored_hook.extract_smell_spans(text, report)
    cur_tone = cfg.get("tone", "peer")
    stepped = unarmored_hook._step_down_tone(cur_tone) if overcorr_kind else None
    step_down = stepped if (stepped and stepped != cur_tone) else None
    out = {
        "model_family": fam,
        "detected_language": lang,
        "relapse_score": report["score"],
        "triggers_injection": report["score"] >= 2,
        "matched_smells": report["smells"],
        "model_directive": unarmored_hook.directive_for(cfg, fam, lang),
        "wire_anchor": unarmored_hook.WIRE_ANCHORS[fam][lang],
        "remedy_directive": remedy,
        "packs_loaded": cfg.get("packs_loaded") or [],
        "metrics": {
            "sent_count": stance.get("sent_count", 0),
            "sent_len_cv": stance.get("sent_len_cv"),
            "short_punch_count": stance.get("short_punch_count", 0),
            "opener_diversity": stance.get("opener_diversity"),
            "transitions_per_k": stance.get("transitions_per_k", 0.0),
            "attitude_per_k": stance.get("attitude_per_k", 0.0),
            "spoken_pivot": stance.get("spoken_pivot", 0),
            "self_mention_singular": stance.get("self_mention_singular", 0),
            "overcorrection_kind": overcorr_kind,
        },
        "highlights": spans,
        "soft_tone_step_down": step_down,
        "_prose": report.get("prose", ""),
    }
    if prompt_text:
        out["classified_intent"] = mode
        out["allows_disk_edits"] = unarmored_hook.allows_disk_edits(prompt_text, mode)
        out["is_epistemic_challenge"] = unarmored_hook.is_epistemic_challenge(prompt_text)
        out["mode_directive"] = unarmored_hook.MODE_DIRECTIVES[mode][lang]
    return out


def _read_diag_file(path_str: str, flag: str = "--file") -> str:
    try:
        return Path(path_str).read_bytes().decode("utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise ManageError(f"Failed to read {flag} {path_str}: {exc}") from exc


def _diagnose_internal(args: argparse.Namespace) -> dict:
    unarmored_hook = _load_hook_module()
    cfg = unarmored_hook.load_config()
    prompt_text = getattr(args, "prompt", None) or ""

    compare_pair = getattr(args, "compare", None)
    if compare_pair:
        fa, fb = compare_pair[0], compare_pair[1]
        a = _diagnose_single_text(_read_diag_file(fa, "--compare"), prompt_text, args.model or "", cfg, unarmored_hook)
        b = _diagnose_single_text(_read_diag_file(fb, "--compare"), prompt_text, args.model or "", cfg, unarmored_hook)
        ma, mb = a["metrics"], b["metrics"]
        d_score = b["relapse_score"] - a["relapse_score"]
        cva, cvb = ma.get("sent_len_cv"), mb.get("sent_len_cv")
        d_cv = round(cvb - cva, 3) if isinstance(cva, (int, float)) and isinstance(cvb, (int, float)) else None
        oa, ob = ma.get("opener_diversity"), mb.get("opener_diversity")
        d_open = round(ob - oa, 3) if isinstance(oa, (int, float)) and isinstance(ob, (int, float)) else None
        removed = [s for s in a["matched_smells"] if s not in b["matched_smells"]]
        added = [s for s in b["matched_smells"] if s not in a["matched_smells"]]
        verdict = "improved" if d_score < 0 else ("regressed" if d_score > 0 else "tied")
        return {
            "mode": "compare",
            "file_a": str(fa),
            "file_b": str(fb),
            "a": {k: v for k, v in a.items() if k != "_prose"},
            "b": {k: v for k, v in b.items() if k != "_prose"},
            "diff": {
                "delta_score": d_score,
                "delta_cv": d_cv,
                "delta_opener_diversity": d_open,
                "smells_removed": removed,
                "smells_added": added,
                "verdict": verdict,
            },
            "_prose_a": a.get("_prose", ""),
            "_prose_b": b.get("_prose", ""),
        }

    text = _read_diag_file(args.file, "--file") if args.file else (args.text or "")
    return _diagnose_single_text(text, prompt_text, args.model or "", cfg, unarmored_hook)


def diagnose_text(args: argparse.Namespace) -> dict:
    raw = _diagnose_internal(args)
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def _render_inline_highlights(prose: str, spans: list[dict], use_color: bool) -> str:
    if not prose or not spans:
        return prose
    out: list[str] = []
    pos = 0
    for sp in spans:
        st, en = sp["start"], sp["end"]
        if st < pos or en > len(prose):
            continue
        out.append(prose[pos:st])
        seg = prose[st:en]
        tag = f"[#{sp['smell']}]"
        if use_color:
            code = "\x1b[35;1m" if sp["smell"] == "overcorrection_drift" else ("\x1b[31;1m" if sp["weight"] >= 2 else "\x1b[33;1m")
            out.append(f"{code}«{seg}»{tag}\x1b[0m")
        else:
            out.append(f"«{seg}»{tag}")
        pos = en
    out.append(prose[pos:])
    return "".join(out)


def format_diagnose_pretty(data: dict, use_color: bool = False) -> str:
    """Format diagnose or diagnose --compare output into a compact badge bar + inline span highlights."""
    if data.get("mode") == "compare":
        a, b, d = data["a"], data["b"], data["diff"]
        ma, mb = a["metrics"], b["metrics"]
        lines = [
            f"[UNARMORED v0.7 COMPARE] verdict={d['verdict'].upper()} | Δscore={d['delta_score']:+d} | "
            f"Δcv={d['delta_cv']} | Δopener_div={d['delta_opener_diversity']}",
            f"  A ({data['file_a']}): score={a['relapse_score']} smells={a['matched_smells']} cv={ma.get('sent_len_cv')} spk={ma.get('spoken_pivot')} att={ma.get('attitude_per_k')}/k",
            f"  B ({data['file_b']}): score={b['relapse_score']} smells={b['matched_smells']} cv={mb.get('sent_len_cv')} spk={mb.get('spoken_pivot')} att={mb.get('attitude_per_k')}/k",
            f"  removed={d['smells_removed']} | added={d['smells_added']}",
        ]
        if data.get("_prose_a"):
            lines.extend(["--- A highlights ---", _render_inline_highlights(data["_prose_a"], a.get("highlights") or [], use_color)])
        if data.get("_prose_b"):
            lines.extend(["--- B highlights ---", _render_inline_highlights(data["_prose_b"], b.get("highlights") or [], use_color)])
        return "\n".join(lines) + "\n"

    m = data.get("metrics") or {}
    trig = "TRIGGER" if data.get("triggers_injection") else "PASS"
    over = m.get("overcorrection_kind") or "none"
    lines = [
        f"[UNARMORED v0.7] family={data['model_family']} | lang={data['detected_language']} | "
        f"score={data['relapse_score']} ({trig}) | cv={m.get('sent_len_cv')} | "
        f"opener_div={m.get('opener_diversity')} | spk={m.get('spoken_pivot')} | "
        f"att={m.get('attitude_per_k')}/k | overcorr={over}"
    ]
    if data.get("matched_smells"):
        lines.append(f"Smells: {', '.join(data['matched_smells'])}")
    if data.get("soft_tone_step_down"):
        lines.append(f"Bidirectional Brake: step tone -> {data['soft_tone_step_down']} (2 turns)")
    if data.get("remedy_directive"):
        lines.append(f"Remedy: {data['remedy_directive']}")
    if data.get("classified_intent"):
        lines.append(
            f"Intent: {data['classified_intent']} | disk_edits={data['allows_disk_edits']} | challenge={data['is_epistemic_challenge']}"
        )
    prose = data.get("_prose") or ""
    if prose and data.get("highlights"):
        lines.extend(["--- Highlights ---", _render_inline_highlights(prose, data["highlights"], use_color)])
    return "\n".join(lines) + "\n"


def status_report(workspace: Path | None) -> dict:
    unarmored_hook = _load_hook_module()

    try:
        py_exe = resolve_real_python()
    except ManageError as exc:
        py_exe = f"ERROR: {exc}"

    _, agy_dir = _antigravity_paths(workspace)
    _, claude_dir, _ = _claude_paths(workspace)
    _, _, codex_dir = _codex_paths(workspace)
    _, dsh_dir, dsh_agents_md = _dsh_paths(workspace)
    return {
        "version": (repo_root() / "VERSION").read_text(encoding="utf-8").strip(),
        "resolved_python": py_exe,
        "config": unarmored_hook.load_config(),
        "bundled_packs": sorted(bundled_pack_files(repo_root()).keys()),
        "installed": {
            "antigravity": {"installed": agy_dir.is_dir(), "path": str(agy_dir)},
            "claude": {"installed": claude_dir.is_dir(), "path": str(claude_dir)},
            "codex": {"installed": codex_dir.is_dir(), "path": str(codex_dir)},
            "dsh": {"installed": dsh_dir.is_dir(), "path": str(dsh_dir), "agents_md": str(dsh_agents_md)},
        },
    }


def sync_local_repo_hooks(root: Path, python_exe: str) -> dict:
    hooks_path = root / "hooks.json"
    _atomic_write_json(hooks_path, build_antigravity_hooks_dict(python_exe), stop_at=root)
    return {"hooks_json": str(hooks_path), "python_exe": python_exe}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="manage.py", description="Manage Unarmored cross-agent plugin & calibration runtime.")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_status = sub.add_parser("status", help="Inspect Python runtime, active config, and host installation states.")
    p_status.add_argument("--target", type=Path, default=None, help="Optional workspace directory.")

    p_install = sub.add_parser("install", help="Install Unarmored into Antigravity, Claude Code, Codex CLI, DSH, or all.")
    p_install.add_argument("--agent", choices=AGENT_CHOICES, default="antigravity")
    p_install.add_argument("--target", type=Path, default=None, help="Install into a workspace instead of global user config.")
    p_install.add_argument("--dsh-home", type=Path, default=None, help="Explicit DSH home (default: $DSH_HOME or ~/.dsh).")
    p_install.add_argument("--block-language", choices=("zh", "en"), default=None, help="Language of the DSH static rules block.")
    p_install.add_argument("--python", dest="python_override", default=None, help="Explicit Python >=3.10 executable path.")
    p_install.add_argument("--dry-run", action="store_true")
    p_install.add_argument("--force", action="store_true")

    p_uninstall = sub.add_parser("uninstall", help="Uninstall Unarmored cleanly while preserving sibling hooks.")
    p_uninstall.add_argument("--agent", choices=AGENT_CHOICES, default="antigravity")
    p_uninstall.add_argument("--target", type=Path, default=None)
    p_uninstall.add_argument("--dsh-home", type=Path, default=None, help="Explicit DSH home (default: $DSH_HOME or ~/.dsh).")
    p_uninstall.add_argument("--dry-run", action="store_true")
    p_uninstall.add_argument("--force", action="store_true")

    p_cfg = sub.add_parser("configure", help="Hot-switch tone stance, language, local model aliases, or bypass rules.")
    p_cfg.add_argument("--tone", choices=("calm", "peer", "sharp"), default=None)
    p_cfg.add_argument("--language", choices=("auto", "zh", "en"), default=None)
    grp = p_cfg.add_mutually_exclusive_group()
    grp.add_argument("--enable", action="store_true")
    grp.add_argument("--disable", action="store_true")
    p_cfg.add_argument("--stop-guard", choices=("on", "off"), default=None)
    p_cfg.add_argument("--set-alias", action="append", default=None, help="Local model alias mapping KEY=FAMILY (saved in ~/.unarmored/config.json).")
    p_cfg.add_argument("--clear-aliases", action="store_true", help="Clear local model_aliases in config.")
    p_cfg.add_argument("--add-ignore-session", action="append", default=None, help="Substring of session IDs to bypass locally.")
    p_cfg.add_argument("--add-ignore-marker", action="append", default=None, help="Prompt substring marker to bypass locally.")

    p_diag = sub.add_parser("diagnose", help="Analyze sample model output for AI-armor smells and preview calibration.")
    p_diag.add_argument("--text", default=None, help="Sample assistant response text.")
    p_diag.add_argument("--file", default=None, help="Path to file containing sample assistant output.")
    p_diag.add_argument("--compare", nargs=2, metavar=("FILE_A", "FILE_B"), default=None, help="Compare two output files side-by-side.")
    p_diag.add_argument("--pretty", action="store_true", help="Render human-readable badge summary and inline smell highlights.")
    p_diag.add_argument("--prompt", default=None, help="Optional user prompt to preview intent classification, disk-edit safety, and mode directive.")
    p_diag.add_argument("--model", default="gpt-5", help="Model name hint (e.g. gpt-5, gemini-4-carbon, claude-opus, deepseek-r1).")

    p_sync = sub.add_parser("sync-local", help="Stamp repository root hooks.json with this machine's verified Python path.")
    p_sync.add_argument("--python", dest="python_override", default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    parser = build_parser()
    args = parser.parse_args(argv)
    root = repo_root()

    try:
        if args.subcommand == "status":
            ws = args.target.resolve() if args.target else None
            res = status_report(ws)
        elif args.subcommand == "install":
            ws = args.target.resolve() if args.target else None
            dsh_home = args.dsh_home.absolute() if args.dsh_home else None
            targets = list(ALL_AGENTS) if args.agent == "all" else [args.agent]
            py_exe = ""
            if any(t in HOOK_AGENTS for t in targets):
                py_exe = args.python_override or resolve_real_python()
                if not _is_valid_python_binary(py_exe):
                    raise ManageError(f"Invalid or stub Python executable: {py_exe}")
            results = []
            for t in targets:
                if t == "dsh":
                    if args.agent == "all" and ws is None and dsh_home is None and not os.environ.get("DSH_HOME") and not (Path.home() / ".dsh").is_dir():
                        results.append({"agent": "dsh", "installed": False, "skipped": "dsh_not_detected"})
                        continue
                    results.append(install_dsh(root, ws, args.dry_run, args.force, dsh_home=dsh_home, lang=args.block_language))
                elif t == "antigravity":
                    results.append(install_antigravity(root, py_exe, ws, args.dry_run, args.force))
                elif t == "claude":
                    results.append(install_claude(root, py_exe, ws, args.dry_run, args.force))
                elif t == "codex":
                    results.append(install_codex(root, py_exe, ws, args.dry_run, args.force))
            res = {"installed": results}
        elif args.subcommand == "uninstall":
            ws = args.target.resolve() if args.target else None
            dsh_home = args.dsh_home.absolute() if args.dsh_home else None
            targets = list(ALL_AGENTS) if args.agent == "all" else [args.agent]
            results = []
            for t in targets:
                if t == "dsh":
                    results.append(uninstall_dsh(ws, args.dry_run, args.force, dsh_home=dsh_home))
                elif t == "antigravity":
                    results.append(uninstall_antigravity(ws, args.dry_run, args.force))
                elif t == "claude":
                    results.append(uninstall_claude(ws, args.dry_run, args.force))
                elif t == "codex":
                    results.append(uninstall_codex(ws, args.dry_run, args.force))
            res = {"uninstalled": results}
        elif args.subcommand == "configure":
            res = configure_runtime(args)
        elif args.subcommand == "diagnose":
            raw_diag = _diagnose_internal(args)
            if args.pretty:
                use_color = bool(getattr(sys.stdout, "isatty", lambda: False)()) and not os.environ.get("NO_COLOR")
                sys.stdout.write(format_diagnose_pretty(raw_diag, use_color=use_color))
                return 0
            res = {k: v for k, v in raw_diag.items() if not k.startswith("_")}
        elif args.subcommand == "sync-local":
            py_exe = args.python_override or resolve_real_python()
            if not _is_valid_python_binary(py_exe):
                raise ManageError(f"Invalid or stub Python executable: {py_exe}")
            res = sync_local_repo_hooks(root, py_exe)
        else:
            raise ManageError(f"Unknown subcommand: {args.subcommand}")

        sys.stdout.write(json.dumps(res, indent=2, ensure_ascii=False) + "\n")
        return 0
    except ManageError as exc:
        sys.stderr.write(f"manage.py error: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
