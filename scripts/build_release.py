#!/usr/bin/env python3
"""Deterministic release validator and archive builder for Unarmored."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import zipfile
from pathlib import Path

FIXED_ZIP_TIME = (2026, 1, 1, 0, 0, 0)
FILE_ATTRIBUTE_REPARSE_POINT = 0x0400

ALLOWED_ANTIGRAVITY_PLUGIN_KEYS = {
    "name",
    "displayName",
    "version",
    "description",
    "logo",
    "suggestedPrompts",
    "author",
    "homepage",
    "repository",
    "disabled",
}

ALLOWED_CODEX_HOOK_EVENTS = {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"}

SENSITIVE_FILENAME_RE = re.compile(r"(?:^\.env(?:\..+)?$|\.(?:pem|key|pfx|p12)$|secret|credential|id_rsa)", re.IGNORECASE)
MACHINE_SPECIFIC_PATH_RE = re.compile(r"(?:[A-Za-z]:\\|[A-Za-z]:/|anaconda3|miniconda3|/Users/|/home/)", re.IGNORECASE)
PLACEHOLDER_URL_RE = re.compile(r"https?://github\.com/example/", re.IGNORECASE)

PACKAGE_PATHS = [
    "VERSION",
    "LICENSE",
    "plugin.json",
    "hooks.json",
    ".claude-plugin/plugin.json",
    "hooks/hooks.json",
    ".codex-plugin/plugin.json",
    ".agents/plugins/marketplace.json",
    "adapters/claude/settings.hooks.example.json",
    "adapters/codex/hooks.example.json",
    "adapters/dsh/AGENTS.block.zh.md",
    "adapters/dsh/AGENTS.block.en.md",
    "assets/logo.svg",
    "assets/banner.svg",
    "CHANGELOG.md",
    "examples/packs/example.pack.json",
    "rules/AGENTS.md",
    "scripts/unarmored_hook.py",
    "scripts/manage.py",
    "scripts/build_release.py",
    "skills/unarmored/SKILL.md",
    "skills/unarmored/agents/openai.yaml",
    "skills/unarmored/references/model-profiles.md",
    "skills/unarmored/references/anti-slop-patterns.md",
    "README.md",
]

# Extra files that belong in the public source tree (git-ready export) but not in the plugin archive
SOURCE_TREE_EXTRA_PATHS = [
    ".gitignore",
    ".github/workflows/ci.yml",
    "tests/test_hook_engine.py",
    "tests/test_manage.py",
    "tests/test_build_release.py",
    "tests/test_eval.py",
    "eval/README.md",
    "eval/prompts.jsonl",
    "eval/triggers.jsonl",
    "eval/conditions.py",
    "eval/score.py",
    "eval/run.py",
    "eval/judge.py",
    "eval/report.py",
    "eval/probe_prefix.py",
]

# Directories that must never exist in a public checkout (private overlays live outside the public tree)
FORBIDDEN_PUBLIC_DIRS = ("packs",)
DENYLIST_ENV = "UNARMORED_OPSEC_DENYLIST"
LOCAL_DENYLIST_REL = ".opsec-denylist.txt"


class ReleaseValidationError(RuntimeError):
    """Raised when version, schema, or safety invariants fail."""


def _is_reparse_or_symlink(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        if os.name == "nt" and path.exists():
            st = os.lstat(path)
            if getattr(st, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT:
                return True
    except OSError:
        return False
    return False


def _verify_inside_root_no_reparse(root: Path, rel: str) -> Path:
    root_resolved = root.resolve()
    cur = root
    for part in Path(rel).parts:
        cur = cur / part
        if _is_reparse_or_symlink(cur):
            raise ReleaseValidationError(f"Symlink or Windows junction forbidden in release package path: {rel} ({cur})")
    if not cur.is_file():
        raise ReleaseValidationError(f"Missing required package file: {rel}")
    if not cur.resolve().is_relative_to(root_resolved):
        raise ReleaseValidationError(f"Packaged file escapes repository root: {rel}")
    return cur


def extract_skill_frontmatter_version(skill_md: str) -> str:
    m = re.match(r"^---\r?\n([\s\S]*?)\r?\n---", skill_md)
    if not m:
        raise ReleaseValidationError("SKILL.md is missing YAML frontmatter")
    fm = m.group(1)
    vm = re.search(r"^\s*version:\s*['\"]?([0-9]+\.[0-9]+\.[0-9]+)['\"]?\s*$", fm, re.MULTILINE)
    if not vm:
        raise ReleaseValidationError("SKILL.md frontmatter is missing metadata.version")
    return vm.group(1).strip()


def validate_repo(root: Path) -> str:
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    if not re.match(r"^[0-9]+\.[0-9]+\.[0-9]+$", version):
        raise ReleaseValidationError(f"Invalid semver in VERSION: {version!r}")

    for rel in PACKAGE_PATHS:
        fpath = _verify_inside_root_no_reparse(root, rel)
        if SENSITIVE_FILENAME_RE.search(fpath.name):
            raise ReleaseValidationError(f"Sensitive filename matched in package list: {rel}")
    for rel in SOURCE_TREE_EXTRA_PATHS:
        if (root / rel).exists() or _is_reparse_or_symlink(root / rel):
            fpath = _verify_inside_root_no_reparse(root, rel)
            if SENSITIVE_FILENAME_RE.search(fpath.name):
                raise ReleaseValidationError(f"Sensitive filename matched in source tree list: {rel}")

    # Read & parse plugin manifests once each
    manifest_raw: dict[str, str] = {}
    manifest_json: dict[str, dict] = {}
    for rel in ("plugin.json", ".claude-plugin/plugin.json", ".codex-plugin/plugin.json", ".agents/plugins/marketplace.json"):
        raw_txt = (root / rel).read_text(encoding="utf-8")
        if PLACEHOLDER_URL_RE.search(raw_txt):
            raise ReleaseValidationError(f"{rel} contains placeholder URL (github.com/example/)")
        manifest_raw[rel] = raw_txt
        manifest_json[rel] = json.loads(raw_txt)

    # 1. Antigravity root plugin.json strict schema check
    root_plugin = manifest_json["plugin.json"]
    unknown_keys = set(root_plugin.keys()) - ALLOWED_ANTIGRAVITY_PLUGIN_KEYS
    if unknown_keys:
        raise ReleaseValidationError(f"Root plugin.json contains unsupported keys for Antigravity: {sorted(unknown_keys)}")
    if root_plugin.get("version") != version:
        raise ReleaseValidationError(f"plugin.json version {root_plugin.get('version')} != VERSION {version}")
    logo_val = str(root_plugin.get("logo") or "")
    if logo_val.startswith(("http://", "https://", "/", "\\", "..")) or not (root / logo_val).is_file():
        raise ReleaseValidationError(f"Invalid or missing relative logo asset in plugin.json: {logo_val!r}")

    # 2. Claude, Codex, and local marketplace plugin manifests
    for sub_manifest in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        if manifest_json[sub_manifest].get("version") != version:
            raise ReleaseValidationError(f"{sub_manifest} version {manifest_json[sub_manifest].get('version')} != VERSION {version}")
    plugins_list = manifest_json[".agents/plugins/marketplace.json"].get("plugins")
    if not isinstance(plugins_list, list) or not plugins_list:
        raise ReleaseValidationError(".agents/plugins/marketplace.json must declare a non-empty 'plugins' array")
    for entry in plugins_list:
        if not isinstance(entry, dict) or entry.get("version") != version:
            raise ReleaseValidationError(
                f".agents/plugins/marketplace.json plugin version {entry.get('version') if isinstance(entry, dict) else None} != VERSION {version}"
            )
    if "PostModelSwitch" not in (manifest_json[".claude-plugin/plugin.json"].get("hooks") or {}):
        raise ReleaseValidationError(".claude-plugin/plugin.json must declare inline PostModelSwitch hook")
    for forbidden_dir in FORBIDDEN_PUBLIC_DIRS:
        if (root / forbidden_dir).exists():
            raise ReleaseValidationError(
                f"'{forbidden_dir}/' must not exist in the public tree (profile packs are user-local overlays)"
            )
    example_pack = json.loads((root / "examples/packs/example.pack.json").read_text(encoding="utf-8"))
    if example_pack.get("schema") != "unarmored-pack/1":
        raise ReleaseValidationError("examples/packs/example.pack.json must declare schema unarmored-pack/1")
    for lang in ("zh", "en"):
        block = (root / f"adapters/dsh/AGENTS.block.{lang}.md").read_text(encoding="utf-8")
        if "unarmored:begin" in block or "unarmored:end" in block:
            raise ReleaseValidationError("DSH block templates must not embed install markers (manage.py adds them)")
    iface = ((manifest_json[".codex-plugin/plugin.json"].get("extensions") or {}).get("com.openai") or {}).get("interface") or {}
    for icon_key in ("logo", "composerIcon"):
        icon_val = str(iface.get(icon_key) or "")
        if icon_val.startswith(".."):
            raise ReleaseValidationError(f".codex-plugin/plugin.json {icon_key} must not traverse above plugin root: {icon_val!r}")

    # 3. Codex hooks.example.json & shared hooks/hooks.json strict schema check (`serde(deny_unknown_fields)`)
    hook_raw: dict[str, str] = {".claude-plugin/plugin.json": manifest_raw[".claude-plugin/plugin.json"]}
    for codex_hook_rel in ("adapters/codex/hooks.example.json", "hooks/hooks.json"):
        raw_txt = (root / codex_hook_rel).read_text(encoding="utf-8")
        hook_raw[codex_hook_rel] = raw_txt
        codex_hooks = json.loads(raw_txt)
        if set(codex_hooks.keys()) != {"hooks"} or not isinstance(codex_hooks.get("hooks"), dict):
            raise ReleaseValidationError(f"{codex_hook_rel} must contain ONLY top-level 'hooks' object")
        bad_events = set(codex_hooks["hooks"].keys()) - ALLOWED_CODEX_HOOK_EVENTS
        if bad_events:
            raise ReleaseValidationError(f"{codex_hook_rel} contains events unsupported by Codex CLI: {sorted(bad_events)}")

    # 4. Ensure portable hook manifests contain no hardcoded developer machine paths
    for hook_manifest in (
        "hooks.json",
        "hooks/hooks.json",
        ".claude-plugin/plugin.json",
        "adapters/codex/hooks.example.json",
        "adapters/claude/settings.hooks.example.json",
    ):
        raw_txt = hook_raw.get(hook_manifest) or (root / hook_manifest).read_text(encoding="utf-8")
        if MACHINE_SPECIFIC_PATH_RE.search(raw_txt):
            raise ReleaseValidationError(f"{hook_manifest} contains machine-specific path; keep portable defaults in repo")

    # 5. SKILL.md version sync & rules budget check
    skill_ver = extract_skill_frontmatter_version((root / "skills/unarmored/SKILL.md").read_text(encoding="utf-8"))
    if skill_ver != version:
        raise ReleaseValidationError(f"SKILL.md version {skill_ver} != VERSION {version}")

    rules_size = (root / "rules/AGENTS.md").stat().st_size
    if rules_size > 24_000:
        raise ReleaseValidationError(f"rules/AGENTS.md ({rules_size} bytes) exceeds Antigravity 24,000-byte rule cap")

    # 6. OpSec: optional local denylist (never committed) scanned across archive + source-tree files
    scan_opsec_denylist(root, PACKAGE_PATHS + [p for p in SOURCE_TREE_EXTRA_PATHS if (root / p).is_file()])
    return version


def load_opsec_denylist(root: Path) -> list[str]:
    """Denylist terms come from $UNARMORED_OPSEC_DENYLIST or an untracked local file; the repo ships none."""
    candidates = []
    env_path = os.environ.get(DENYLIST_ENV)
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(root / LOCAL_DENYLIST_REL)
    for cand in candidates:
        if cand.is_file():
            terms = []
            for line in cand.read_text(encoding="utf-8-sig").splitlines():
                term = line.strip()
                if term and not term.startswith("#"):
                    terms.append(term.lower())
            return terms
    return []


def scan_opsec_denylist(root: Path, rel_paths: list[str]) -> None:
    terms = load_opsec_denylist(root)
    if not terms:
        return
    for rel in rel_paths:
        low = (root / rel).read_bytes().decode("utf-8", errors="replace").lower()
        for term in terms:
            if term in low:
                raise ReleaseValidationError(f"OpSec denylist term found in public file {rel} (term #{terms.index(term) + 1})")


def _normalized_bytes(root: Path, rel: str) -> bytes:
    raw = (root / rel).read_bytes()
    if rel.endswith((".py", ".md", ".json", ".jsonl", ".yaml", ".yml", ".svg")) or rel in ("VERSION", "LICENSE", ".gitignore"):
        raw = raw.replace(b"\r\n", b"\n")
    return raw


def build_archive(root: Path, out_dir: Path) -> dict:
    version = validate_repo(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    archive_name = f"unarmored-v{version}.zip"
    archive_path = out_dir / archive_name

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in sorted(PACKAGE_PATHS):
            raw = _normalized_bytes(root, rel)
            info = zipfile.ZipInfo(filename=f"unarmored/{rel}", date_time=FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 << 16) if rel.endswith(".py") else (0o644 << 16)
            zf.writestr(info, raw)

    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    sums_path = out_dir / "SHA256SUMS"
    sums_path.write_bytes(f"{digest}  {archive_name}\n".encode("utf-8"))
    return {"version": version, "archive": str(archive_path), "sha256": digest, "sha256sums": str(sums_path)}


def export_source_tree(root: Path, dest: Path) -> dict:
    """Write a clean, git-ready public source tree (archive files + tests + .gitignore) into an empty dest."""
    validate_repo(root)
    if dest.exists() and any(dest.iterdir()):
        raise ReleaseValidationError(f"Export destination must be empty or absent: {dest}")
    rels = sorted(set(PACKAGE_PATHS) | {p for p in SOURCE_TREE_EXTRA_PATHS if (root / p).is_file()})
    for rel in rels:
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_normalized_bytes(root, rel))
    return {"exported_to": str(dest), "files": len(rels)}


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parent.parent
    args = list(argv or [])
    try:
        if args and args[0] == "--export-tree":
            if len(args) < 2:
                raise ReleaseValidationError("usage: build_release.py --export-tree <empty-destination-dir>")
            info = export_source_tree(root, Path(args[1]).resolve())
        else:
            out_dir = Path(args[0]).resolve() if args else (root / "dist")
            info = build_archive(root, out_dir)
        sys.stdout.write(json.dumps(info, indent=2, ensure_ascii=False) + "\n")
        return 0
    except ReleaseValidationError as exc:
        sys.stderr.write(f"build_release error: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
