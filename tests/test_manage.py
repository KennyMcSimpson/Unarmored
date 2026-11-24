from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import manage  # noqa: E402
import unarmored_hook  # noqa: E402

# Junction/symlink fixtures are opt-in: some machines forbid creating reparse points at all.
ALLOW_REPARSE_FIXTURES = os.environ.get("UNARMORED_ALLOW_REPARSE_TESTS") == "1"


class TestManageCLI(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name) / "workspace with spaces 中文"
        self.ws.mkdir(parents=True, exist_ok=True)
        self.cfg_file = Path(self.tmp.name) / "config.json"
        self.state_dir = Path(self.tmp.name) / "state"
        os.environ["UNARMORED_CONFIG"] = str(self.cfg_file)
        os.environ["UNARMORED_STATE_DIR"] = str(self.state_dir)

    def tearDown(self) -> None:
        os.environ.pop("UNARMORED_CONFIG", None)
        os.environ.pop("UNARMORED_STATE_DIR", None)
        self.tmp.cleanup()

    def test_windows_apps_stub_rejected(self) -> None:
        self.assertFalse(manage._is_valid_python_binary(r"C:\Users\example\AppData\Local\Microsoft\WindowsApps\python.exe"))
        real_py = manage.resolve_real_python()
        self.assertNotIn("windowsapps", real_py.lower())
        self.assertTrue(Path(real_py).is_file())

    def test_install_preserve_sibling_flat_and_empty_hooks_and_strict_codex_schema(self) -> None:
        # Pre-seed flat Notification handler + intentionally empty PreToolUse override + sibling SessionStart
        claude_settings = self.ws / ".claude" / "settings.json"
        claude_settings.parent.mkdir(parents=True, exist_ok=True)
        claude_settings.write_text(
            json.dumps(
                {
                    "theme": "dark",
                    "hooks": {
                        "SessionStart": [{"hooks": [{"type": "command", "command": "echo sibling-claude"}]}],
                        "Notification": [{"type": "command", "command": "notify.exe"}],
                        "PreToolUse": [{"matcher": "Bash", "hooks": []}],
                    },
                }
            ),
            encoding="utf-8",
        )

        codex_hooks = self.ws / ".codex" / "hooks.json"
        codex_hooks.parent.mkdir(parents=True, exist_ok=True)
        codex_hooks.write_text(
            json.dumps(
                {
                    "hooks": {
                        "SessionStart": [{"hooks": [{"type": "command", "command": "echo sibling-codex"}]}]
                    },
                }
            ),
            encoding="utf-8",
        )

        rc = manage.main(["install", "--agent", "all", "--target", str(self.ws)])
        self.assertEqual(rc, 0)

        # Verify Antigravity workspace plugin and DSH skill + marked rules block
        agy_plugin = self.ws / ".agents" / "plugins" / "unarmored"
        self.assertTrue((agy_plugin / "plugin.json").is_file())
        self.assertTrue((agy_plugin / "hooks.json").is_file())
        self.assertTrue((agy_plugin / "rules" / "AGENTS.md").is_file())
        self.assertFalse((agy_plugin / "packs").exists(), "public checkout bundles no packs")
        dsh_skill = self.ws / ".dsh" / "skills" / "unarmored"
        self.assertTrue((dsh_skill / "SKILL.md").is_file())
        ws_agents_md = self.ws / "AGENTS.md"
        self.assertEqual(ws_agents_md.read_text(encoding="utf-8").count(manage.DSH_BLOCK_BEGIN), 1)

        # Verify Claude Code preserved theme + sibling hooks + PreCompact
        claude_after = json.loads(claude_settings.read_text(encoding="utf-8"))
        self.assertEqual(claude_after["theme"], "dark")
        self.assertEqual(len(claude_after["hooks"]["SessionStart"]), 2)
        self.assertIn("PostModelSwitch", claude_after["hooks"])
        self.assertIn("PreCompact", claude_after["hooks"])

        # Verify Codex hooks.json strictly obeys `serde(deny_unknown_fields)`: ONLY `hooks` at top level!
        codex_after = json.loads(codex_hooks.read_text(encoding="utf-8"))
        self.assertEqual(list(codex_after.keys()), ["hooks"])
        self.assertTrue(set(codex_after["hooks"].keys()).issubset({"SessionStart", "UserPromptSubmit", "Stop"}))
        self.assertEqual(len(codex_after["hooks"]["SessionStart"]), 2)

        # Configure tone bump + private local alias
        self.assertEqual(
            manage.main(
                [
                    "configure",
                    "--tone",
                    "sharp",
                    "--stop-guard",
                    "off",
                    "--set-alias",
                    "custom-route-x=grok",
                    "--add-ignore-session",
                    "bot-job",
                ]
            ),
            0,
        )
        cfg_data = json.loads(self.cfg_file.read_text(encoding="utf-8"))
        self.assertEqual(cfg_data["tone"], "sharp")
        self.assertFalse(cfg_data["stop_guard"])
        self.assertEqual(cfg_data["model_aliases"], {"custom-route-x": "grok"})
        self.assertEqual(cfg_data["ignore_session_patterns"], ["bot-job"])
        self.assertGreaterEqual(cfg_data["epoch"], 2)

        # Uninstall all four -> flat Notification & empty PreToolUse & sibling SessionStart preserved untouched
        self.assertEqual(manage.main(["uninstall", "--agent", "all", "--target", str(self.ws)]), 0)
        self.assertFalse(agy_plugin.exists())
        self.assertFalse(dsh_skill.exists())
        self.assertFalse(ws_agents_md.exists(), "AGENTS.md created by install is removed when only our block remained")
        claude_uninstalled = json.loads(claude_settings.read_text(encoding="utf-8"))
        self.assertEqual(claude_uninstalled["theme"], "dark")
        self.assertEqual(len(claude_uninstalled["hooks"]["SessionStart"]), 1)
        self.assertEqual(claude_uninstalled["hooks"]["Notification"], [{"type": "command", "command": "notify.exe"}])
        self.assertEqual(claude_uninstalled["hooks"]["PreToolUse"], [{"matcher": "Bash", "hooks": []}])
        codex_uninstalled = json.loads(codex_hooks.read_text(encoding="utf-8"))
        self.assertEqual(list(codex_uninstalled.keys()), ["hooks"])
        self.assertEqual(len(codex_uninstalled["hooks"]["SessionStart"]), 1)

    @unittest.skipUnless(os.name == "nt", "Windows multi-shell cmd.exe + Git Bash matrix test")
    def test_windows_four_shell_modes_with_spaced_python_and_hostile_paths(self) -> None:
        real_py_dir = Path(manage.resolve_real_python()).parent
        spaced_py_dir = Path(self.tmp.name) / "Program Files (x86)" / "Py 3"
        if ALLOW_REPARSE_FIXTURES:
            spaced_py_dir.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["cmd.exe", "/c", "mklink", "/J", str(spaced_py_dir), str(real_py_dir)], capture_output=True, check=True)
            spaced_py = str(spaced_py_dir / "python.exe")
        else:
            spaced_py = str(real_py_dir / "python.exe")
        git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")

        try:
            payload = json.dumps(
                {"hook_event_name": "SessionStart", "session_id": "matrix-test", "model": "gpt-5.4"}
            ).encode("utf-8")

            for folder in ("ws %OS%", "ws $HOME", "ws !bang!", "ws A&B", "ws (O'Connor)", "ws a^b", "ws 中文 空格"):
                target_ws = Path(self.tmp.name) / folder
                target_ws.mkdir(parents=True, exist_ok=True)
                self.assertEqual(
                    manage.main(["install", "--agent", "all", "--target", str(target_ws), "--python", spaced_py]), 0
                )
                cmd_str = json.loads((target_ws / ".claude" / "settings.json").read_text(encoding="utf-8"))["hooks"][
                    "SessionStart"
                ][0]["hooks"][0]["command"]
                codex_win_cmd = json.loads((target_ws / ".codex" / "hooks.json").read_text(encoding="utf-8"))["hooks"][
                    "SessionStart"
                ][0]["hooks"][0]["commandWindows"]

                # Mode 1: Python shell=True
                r1 = subprocess.run(cmd_str, input=payload, capture_output=True, shell=True, timeout=10, check=False)
                self.assertEqual(r1.returncode, 0, f"{folder} shell=True failed: {r1.stderr!r}")

                # Mode 2: Native raw `cmd.exe /c <cmd>` (matches Rust Command::new("cmd.exe").arg("/c").raw_arg(cmd))
                r2 = subprocess.run(f"cmd.exe /c {cmd_str}", input=payload, capture_output=True, timeout=10, check=False)
                self.assertEqual(r2.returncode, 0, f"{folder} raw cmd /c failed: {r2.stderr!r}")

                # Mode 3: Node.js `cmd.exe /d /s /c "<cmd>"`
                r3 = subprocess.run(
                    f'cmd.exe /d /s /c "{cmd_str}"', input=payload, capture_output=True, timeout=10, check=False
                )
                self.assertEqual(r3.returncode, 0, f"{folder} cmd /d /s /c failed: {r3.stderr!r}")

                # Mode 4: Git Bash `bash.exe -c <cmd>`
                if git_bash.is_file():
                    r4 = subprocess.run([str(git_bash), "-c", cmd_str], input=payload, capture_output=True, timeout=10, check=False)
                    self.assertEqual(r4.returncode, 0, f"{folder} Git Bash failed: {r4.stderr!r}")
                    self.assertIn("<unarmored_baseline>", json.loads(r4.stdout.decode("utf-8"))["hookSpecificOutput"]["additionalContext"])

                # Mode 5: Codex `commandWindows` under Windows PowerShell (`powershell.exe -NoProfile -Command`) AND `cmd.exe /c`
                rps = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-Command", codex_win_cmd],
                    input=payload,
                    capture_output=True,
                    timeout=10,
                    check=False,
                )
                self.assertEqual(rps.returncode, 0, f"{folder} PowerShell commandWindows failed: {rps.stderr!r}")
                self.assertIn("<unarmored_baseline>", json.loads(rps.stdout.decode("utf-8"))["hookSpecificOutput"]["additionalContext"])

                rcmd = subprocess.run(f"cmd.exe /c {codex_win_cmd}", input=payload, capture_output=True, timeout=10, check=False)
                self.assertEqual(rcmd.returncode, 0, f"{folder} cmd /c commandWindows failed: {rcmd.stderr!r}")

            # Verify static portable `hooks/hooks.json` and `.claude-plugin/plugin.json` PostModelSwitch in Git Bash
            if git_bash.is_file():
                env_bash = dict(os.environ)
                env_bash["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT).replace("\\", "/")
                env_bash["UNARMORED_STATE_DIR"] = str(self.state_dir)
                env_bash["UNARMORED_CONFIG"] = str(self.cfg_file)

                shared_cmd = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"][
                    "SessionStart"
                ][0]["hooks"][0]["command"]
                rs = subprocess.run([str(git_bash), "-c", shared_cmd], input=payload, capture_output=True, env=env_bash, timeout=10, check=False)
                self.assertEqual(rs.returncode, 0, rs.stderr.decode("utf-8", errors="replace"))

                pms_cmd = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["hooks"][
                    "PostModelSwitch"
                ][0]["hooks"][0]["command"]
                pms_payload = json.dumps(
                    {"hook_event_name": "PostModelSwitch", "session_id": "pms-1", "to_model": "claude-opus-4-6"}
                ).encode("utf-8")
                rp = subprocess.run([str(git_bash), "-c", pms_cmd], input=pms_payload, capture_output=True, env=env_bash, timeout=10, check=False)
                self.assertEqual(rp.returncode, 0, rp.stderr.decode("utf-8", errors="replace"))
                self.assertIn("Claude", rp.stdout.decode("utf-8"))
        finally:
            if ALLOW_REPARSE_FIXTURES:
                subprocess.run(["cmd.exe", "/c", "rmdir", str(spaced_py_dir)], capture_output=True, check=False)

    def test_refuses_corrupt_settings_unowned_dir_and_untracked_user_files(self) -> None:
        # 1. Corrupt settings.json must NOT be overwritten
        claude_settings = self.ws / ".claude" / "settings.json"
        claude_settings.parent.mkdir(parents=True, exist_ok=True)
        claude_settings.write_text("{corrupt json // comment", encoding="utf-8")

        self.assertEqual(manage.main(["install", "--agent", "claude", "--target", str(self.ws)]), 1)
        self.assertEqual(claude_settings.read_text(encoding="utf-8"), "{corrupt json // comment")
        claude_settings.unlink()

        # 2. Untracked user file inside installed directory blocks uninstall unless --force is passed
        self.assertEqual(manage.main(["install", "--agent", "claude", "--target", str(self.ws)]), 0)
        custom_note = self.ws / ".claude" / "skills" / "unarmored" / "MY_CUSTOM_NOTES.md"
        custom_note.write_text("important note", encoding="utf-8")
        self.assertEqual(manage.main(["uninstall", "--agent", "claude", "--target", str(self.ws)]), 1)
        self.assertTrue(custom_note.is_file())
        self.assertEqual(manage.main(["uninstall", "--agent", "claude", "--target", str(self.ws), "--force"]), 0)
        self.assertFalse(custom_note.exists())

        # 3. Unowned plugin directory refused without --force
        unowned = self.ws / ".agents" / "plugins" / "unarmored"
        unowned.mkdir(parents=True, exist_ok=True)
        (unowned / "custom.txt").write_text("user file", encoding="utf-8")
        self.assertEqual(manage.main(["install", "--agent", "antigravity", "--target", str(self.ws)]), 1)

    def test_config_path_honors_state_dir_and_diagnose_prompt(self) -> None:
        old_cfg = os.environ.pop("UNARMORED_CONFIG", None)
        try:
            self.assertEqual(manage.config_file_path().resolve(), (self.state_dir / "config.json").resolve())
            self.assertEqual(manage.main(["configure", "--tone", "calm"]), 0)
            self.assertTrue((self.state_dir / "config.json").is_file())
        finally:
            if old_cfg is not None:
                os.environ["UNARMORED_CONFIG"] = old_cfg

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = manage.main(
                [
                    "diagnose",
                    "--model",
                    "gpt-5.4",
                    "--prompt",
                    "十人以内的团队适合上微服务吗？",
                    "--text",
                    "这不是非黑即白的选择，需要在灵活性和复杂度之间寻找平衡点。",
                ]
            )
        self.assertEqual(rc, 0)
        res = json.loads(buf.getvalue())
        self.assertEqual(res["model_family"], "gpt")
        self.assertEqual(res["classified_intent"], "CRITIQUE_OPINION")
        self.assertFalse(res["allows_disk_edits"])
        self.assertIn("consultant_balance", res["matched_smells"])
        self.assertIn("[直出·GPT]", res["wire_anchor"])

    def test_sparse_configure_corrupt_refusal_diagnose_errors_and_uninstall_boundaries(self) -> None:
        # 1. Sparse configure must NOT clobber profile pack defaults (tone/language) when only --stop-guard is set
        pack_dir = self.state_dir / "packs"
        pack_dir.mkdir(parents=True, exist_ok=True)
        (pack_dir / "team.json").write_text(
            json.dumps({"schema": "unarmored-pack/1", "name": "team", "defaults": {"tone": "sharp", "language": "en"}}),
            encoding="utf-8",
        )
        self.assertFalse(self.cfg_file.exists())
        self.assertEqual(manage.main(["configure", "--stop-guard", "off"]), 0)
        raw_cfg = json.loads(self.cfg_file.read_text(encoding="utf-8"))
        self.assertNotIn("tone", raw_cfg)
        self.assertNotIn("language", raw_cfg)
        loaded = unarmored_hook.load_config()
        self.assertEqual(loaded["tone"], "sharp")
        self.assertEqual(loaded["language"], "en")
        self.assertFalse(loaded["stop_guard"])

        # 2. Corrupt config.json MUST be refused (rc=1) without silent overwrite
        self.cfg_file.write_text("{broken json", encoding="utf-8")
        self.assertEqual(manage.main(["configure", "--tone", "calm"]), 1)
        self.assertEqual(self.cfg_file.read_text(encoding="utf-8"), "{broken json")
        self.cfg_file.unlink()

        # 3. Missing --file returns clean ManageError rc=1; numeric --text falls back to English --prompt language
        self.assertEqual(manage.main(["diagnose", "--file", str(self.ws / "does_not_exist.txt")]), 1)
        (pack_dir / "team.json").unlink()
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = manage.main(["diagnose", "--model", "gpt-5", "--text", "12345", "--prompt", "Explain how TCP works"])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(buf.getvalue())["detected_language"], "en")

        # 4. Uninstall safety boundaries: --dry-run zero side effects, modified tracked file blocks without --force,
        #    and corrupt install manifest still allows --force uninstall across all 4 hosts without deleting user files.
        ws_u = Path(self.tmp.name) / "ws_uninstall"
        ws_u.mkdir()
        (ws_u / ".claude").mkdir(parents=True)
        (ws_u / ".claude" / "settings.json").write_text(json.dumps({"theme": "light"}), encoding="utf-8")
        (ws_u / "AGENTS.md").write_text("# Keep me\n", encoding="utf-8")
        self.assertEqual(manage.main(["install", "--agent", "all", "--target", str(ws_u)]), 0)

        # Dry-run uninstall touches nothing
        self.assertEqual(manage.main(["uninstall", "--agent", "all", "--target", str(ws_u), "--dry-run"]), 0)
        self.assertTrue((ws_u / ".agents" / "plugins" / "unarmored").is_dir())
        self.assertTrue((ws_u / ".claude" / "skills" / "unarmored").is_dir())

        # Modified tracked file blocks Claude uninstall without --force and leaves settings.json untouched
        claude_skill_md = ws_u / ".claude" / "skills" / "unarmored" / "SKILL.md"
        claude_skill_md.write_text("user edited", encoding="utf-8")
        before_settings = (ws_u / ".claude" / "settings.json").read_text(encoding="utf-8")
        self.assertEqual(manage.main(["uninstall", "--agent", "claude", "--target", str(ws_u)]), 1)
        self.assertEqual((ws_u / ".claude" / "settings.json").read_text(encoding="utf-8"), before_settings)

        # Corrupt manifests in all 4 hosts still uninstall cleanly under --force while preserving user files
        for mpath in (
            ws_u / ".agents" / "plugins" / "unarmored" / manage.MANIFEST_FILENAME,
            ws_u / ".claude" / "skills" / "unarmored" / manage.MANIFEST_FILENAME,
            ws_u / ".agents" / "skills" / "unarmored" / manage.MANIFEST_FILENAME,
            ws_u / ".dsh" / "skills" / "unarmored" / manage.MANIFEST_FILENAME,
        ):
            mpath.write_text("{corrupt manifest json", encoding="utf-8")
        self.assertEqual(manage.main(["uninstall", "--agent", "all", "--target", str(ws_u), "--force"]), 0)
        self.assertEqual(json.loads((ws_u / ".claude" / "settings.json").read_text(encoding="utf-8")), {"theme": "light"})
        self.assertEqual((ws_u / "AGENTS.md").read_text(encoding="utf-8"), "# Keep me\n")

    @unittest.skipUnless(os.name == "nt" and ALLOW_REPARSE_FIXTURES, "opt-in: set UNARMORED_ALLOW_REPARSE_TESTS=1")
    def test_refuses_windows_junction_traversal_on_install_and_uninstall(self) -> None:
        outside = Path(self.tmp.name) / "outside_victim"
        outside.mkdir(parents=True, exist_ok=True)
        victim_file = outside / "precious.txt"
        victim_file.write_text("do not touch", encoding="utf-8")

        junc_ws = Path(self.tmp.name) / "junc_ws"
        (junc_ws / ".agents" / "plugins").mkdir(parents=True, exist_ok=True)
        junc_target = junc_ws / ".agents" / "plugins" / "unarmored"

        mk = subprocess.run(
            ["cmd.exe", "/c", "mklink", "/J", str(junc_target), str(outside)],
            capture_output=True,
            check=False,
        )
        self.assertEqual(mk.returncode, 0, mk.stderr.decode("utf-8", errors="replace"))

        try:
            self.assertEqual(manage.main(["install", "--agent", "antigravity", "--target", str(junc_ws), "--force"]), 1)
            self.assertEqual(manage.main(["uninstall", "--agent", "antigravity", "--target", str(junc_ws), "--force"]), 1)
            self.assertTrue(victim_file.is_file())
            self.assertEqual(victim_file.read_text(encoding="utf-8"), "do not touch")
        finally:
            subprocess.run(["cmd.exe", "/c", "rmdir", str(junc_target)], capture_output=True, check=False)


if __name__ == "__main__":
    unittest.main()
