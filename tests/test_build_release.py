from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_release  # noqa: E402

# Junction/symlink fixtures are opt-in: some machines forbid creating reparse points at all.
ALLOW_REPARSE_FIXTURES = os.environ.get("UNARMORED_ALLOW_REPARSE_TESTS") == "1"


def _copy_public_tree(dest_root: Path) -> None:
    for rel in build_release.PACKAGE_PATHS + build_release.SOURCE_TREE_EXTRA_PATHS:
        src = REPO_ROOT / rel
        if not src.is_file():
            continue
        dest = dest_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


class TestBuildRelease(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_env = os.environ.pop(build_release.DENYLIST_ENV, None)

    def tearDown(self) -> None:
        if self._saved_env is not None:
            os.environ[build_release.DENYLIST_ENV] = self._saved_env

    def test_validate_and_deterministic_archive(self) -> None:
        ver = build_release.validate_repo(REPO_ROOT)
        self.assertEqual(ver, (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip())

        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            r1 = build_release.build_archive(REPO_ROOT, Path(d1))
            r2 = build_release.build_archive(REPO_ROOT, Path(d2))
            self.assertEqual(r1["sha256"], r2["sha256"])
            with zipfile.ZipFile(r1["archive"]) as zf:
                names = zf.namelist()
            self.assertIn("unarmored/adapters/dsh/AGENTS.block.zh.md", names)
            self.assertIn("unarmored/examples/packs/example.pack.json", names)
            self.assertFalse(any("/packs/" in n and "/examples/" not in n for n in names))
            self.assertFalse(any(n.endswith(".mjs") for n in names), "public archive must not carry host-private JS adapters")

    def test_export_tree_is_clean_and_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "export"
            info = build_release.export_source_tree(REPO_ROOT, dest)
            self.assertTrue((dest / "tests" / "test_hook_engine.py").is_file())
            self.assertTrue((dest / ".gitignore").is_file())
            self.assertFalse((dest / "packs").exists())
            exported = {p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file()}
            self.assertEqual(len(exported), info["files"])
            self.assertFalse(any(part.startswith("private") for rel in exported for part in rel.split("/")))
            with self.assertRaises(build_release.ReleaseValidationError):
                build_release.export_source_tree(REPO_ROOT, dest)  # non-empty destination refused

    def test_opsec_denylist_blocks_leaks_and_forbidden_pack_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copy_root = Path(tmp) / "repo"
            _copy_public_tree(copy_root)
            secret = "zz-private-" + "relay-name"  # assembled at runtime so this test file never contains the term
            deny = Path(tmp) / "deny.txt"
            deny.write_text(f"# comment\n{secret}\n", encoding="utf-8")
            os.environ[build_release.DENYLIST_ENV] = str(deny)

            build_release.validate_repo(copy_root)  # clean copy passes

            readme = copy_root / "README.md"
            readme.write_text(readme.read_text(encoding="utf-8") + f"\nroute: {secret.upper()}/x\n", encoding="utf-8")
            with self.assertRaises(build_release.ReleaseValidationError) as ctx:
                build_release.validate_repo(copy_root)
            self.assertNotIn(secret, str(ctx.exception).lower(), "error must not echo the secret term")

            shutil.copy2(REPO_ROOT / "README.md", readme)
            (copy_root / "packs").mkdir()
            with self.assertRaises(build_release.ReleaseValidationError):
                build_release.validate_repo(copy_root)

    def test_rejects_codex_unknown_top_level_key_and_machine_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copy_root = Path(tmp) / "repo"
            _copy_public_tree(copy_root)

            (copy_root / "adapters/codex/hooks.example.json").write_text(
                '{"description": "bad", "hooks": {}}\n', encoding="utf-8"
            )
            with self.assertRaises(build_release.ReleaseValidationError):
                build_release.validate_repo(copy_root)

            shutil.copy2(REPO_ROOT / "adapters/codex/hooks.example.json", copy_root / "adapters/codex/hooks.example.json")
            (copy_root / "hooks.json").write_text(
                '{"unarmored": {"enabled": true, "Stop": [{"type": "command", "command": "C:/ProgramData/anaconda3/python.exe x.py"}]}}\n',
                encoding="utf-8",
            )
            with self.assertRaises(build_release.ReleaseValidationError):
                build_release.validate_repo(copy_root)

    def test_rejects_marketplace_version_drift_and_placeholder_urls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copy_root = Path(tmp) / "repo"
            _copy_public_tree(copy_root)

            mp = copy_root / ".agents/plugins/marketplace.json"
            mp.write_text('{"name":"unarmored-local","plugins":[{"name":"unarmored","version":"0.1.0","source":"./"}]}\n', encoding="utf-8")
            with self.assertRaises(build_release.ReleaseValidationError):
                build_release.validate_repo(copy_root)

            shutil.copy2(REPO_ROOT / ".agents/plugins/marketplace.json", mp)
            pj = copy_root / "plugin.json"
            pj_data = json.loads(pj.read_text(encoding="utf-8"))
            pj_data["homepage"] = "https://github.com/example/unarmored"
            pj.write_text(json.dumps(pj_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            with self.assertRaises(build_release.ReleaseValidationError):
                build_release.validate_repo(copy_root)

            # Verify .jsonl files are LF-normalized on export
            shutil.copy2(REPO_ROOT / "plugin.json", pj)
            prompts = copy_root / "eval/prompts.jsonl"
            prompts.write_bytes(prompts.read_bytes().replace(b"\n", b"\r\n"))
            dest = Path(tmp) / "lf_export"
            build_release.export_source_tree(copy_root, dest)
            self.assertNotIn(b"\r\n", (dest / "eval/prompts.jsonl").read_bytes())

    @unittest.skipUnless(os.name == "nt" and ALLOW_REPARSE_FIXTURES, "opt-in: set UNARMORED_ALLOW_REPARSE_TESTS=1")
    def test_rejects_windows_junction_inside_package_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copy_root = Path(tmp) / "repo"
            outside = Path(tmp) / "outside_skill"
            _copy_public_tree(copy_root)

            shutil.move(str(copy_root / "skills" / "unarmored"), str(outside))
            mk = subprocess.run(
                ["cmd.exe", "/c", "mklink", "/J", str(copy_root / "skills" / "unarmored"), str(outside)],
                capture_output=True,
                check=False,
            )
            self.assertEqual(mk.returncode, 0)
            try:
                with self.assertRaises(build_release.ReleaseValidationError):
                    build_release.validate_repo(copy_root)
            finally:
                subprocess.run(["cmd.exe", "/c", "rmdir", str(copy_root / "skills" / "unarmored")], capture_output=True, check=False)


if __name__ == "__main__":
    unittest.main()
