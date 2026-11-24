from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import manage  # noqa: E402
import unarmored_hook  # noqa: E402


class TestHookEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.tmp.name) / "state"
        self.cfg_path = Path(self.tmp.name) / "config.json"
        os.environ["UNARMORED_STATE_DIR"] = str(self.state_dir)
        os.environ["UNARMORED_CONFIG"] = str(self.cfg_path)

    def tearDown(self) -> None:
        os.environ.pop("UNARMORED_STATE_DIR", None)
        os.environ.pop("UNARMORED_CONFIG", None)
        self.tmp.cleanup()

    def test_host_detection_and_model_classification(self) -> None:
        self.assertEqual(unarmored_hook.detect_host({"hookEventName": "SessionStart", "conversationId": "c1"}), "antigravity")
        self.assertEqual(
            unarmored_hook.detect_host({"hook_event_name": "UserPromptSubmit", "turn_id": "t1", "session_id": "s1"}),
            "codex",
        )
        self.assertEqual(
            unarmored_hook.detect_host(
                {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "transcript_path": "/home/u/.claude/t.jsonl"}
            ),
            "claude",
        )
        self.assertEqual(unarmored_hook.classify_model_family("Gemini 4 Carbon (High)"), "gemini")
        self.assertEqual(unarmored_hook.classify_model_family("Claude Opus 5.5 (High)"), "claude")
        self.assertEqual(unarmored_hook.classify_model_family("gpt-5.4-codex"), "gpt")
        self.assertEqual(unarmored_hook.classify_model_family("o3-pro"), "gpt")
        self.assertEqual(unarmored_hook.classify_model_family("o4-mini"), "gpt")
        self.assertEqual(unarmored_hook.classify_model_family("deepseek-r1"), "deepseek")
        self.assertEqual(unarmored_hook.classify_model_family("auto/deepseek-v3-20250731"), "deepseek")
        self.assertEqual(unarmored_hook.classify_model_family("x-ai/grok-4"), "grok")
        self.assertEqual(unarmored_hook.classify_model_family("qwen3-coder"), "cn_flagship")
        self.assertEqual(unarmored_hook.classify_model_family("group/pool-1"), "generic")
        self.assertEqual(
            unarmored_hook.classify_model_family("gateway/my-custom-alias", {"my-custom-alias": "claude"}),
            "claude",
        )

    def test_behavioral_fingerprinting_challenge_guard_and_precompact_recovery(self) -> None:
        transcript = Path(self.tmp.name) / ".claude" / "fp_session.jsonl"
        transcript.parent.mkdir(parents=True, exist_ok=True)
        # Turn 1 on masked `group/pool-a` starts as generic
        p1 = {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "masked-1",
            "model": "group/pool-a",
            "transcript_path": str(transcript),
            "prompt": "聊聊连接池大小怎么定",
        }
        out1 = unarmored_hook.process_event(p1)
        ctx1 = out1["hookSpecificOutput"]["additionalContext"]
        self.assertIn("[语域校准]", ctx1)

        # Assistant Turn 1 exhibits GPT contrast + waiter menu + structural copula puffery
        transcript.write_text(
            json.dumps(
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "连接池作为高并发系统的核心载体，这不仅仅是一个参数调整，更是一场稳定性权衡。如果你需要，我可以进一步帮你把压测脚本写出来。",
                            }
                        ],
                    },
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        # Turn 2: User asks skeptical leading question -> Behavioral fingerprint switches to GPT + Epistemic Check fires!
        p2 = dict(p1, prompt="你确定吗？连接池设成 500 才最快对吧？")
        out2 = unarmored_hook.process_event(p2)
        ctx2 = out2["hookSpecificOutput"]["additionalContext"]
        self.assertIn("[语域校准·GPT]", ctx2)
        self.assertIn("[语域纠偏]", ctx2)
        self.assertIn("[独立核验]", ctx2)

        # PreCompact resets session_initialized so post-compaction turn re-anchors baseline cleanly
        unarmored_hook.process_event({"hook_event_name": "PreCompact", "session_id": "masked-1"})
        out3 = unarmored_hook.process_event(dict(p1, prompt="接着看超时配置"))
        self.assertIn("<unarmored_baseline>", out3["hookSpecificOutput"]["additionalContext"])

    def test_antigravity_deduplication_and_mid_session_model_switch(self) -> None:
        transcript = Path(self.tmp.name) / "transcript.jsonl"
        transcript.write_text(
            json.dumps(
                {
                    "step_index": 0,
                    "source": "USER_EXPLICIT",
                    "type": "USER_INPUT",
                    "content": "<USER_REQUEST>\n聊聊缓存方案\n</USER_REQUEST>\n<USER_SETTINGS_CHANGE>\nThe user changed setting `Model Selection` from None to Gemini 4 Carbon (High).\n</USER_SETTINGS_CHANGE>",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        # 1. First PreInvocation initializes calibration for Gemini
        p1 = {
            "hookEventName": "PreInvocation",
            "conversationId": "conv-1",
            "modelName": "auto",
            "transcriptPath": str(transcript),
            "lastUserInput": "聊聊缓存方案",
            "invocationNum": 1,
        }
        out1 = unarmored_hook.process_event(p1)
        msg1 = out1["injectSteps"][0]["systemMessage"]["systemMessage"]
        self.assertIn("Gemini", msg1)

        # 2. Mid-turn tool loop step (same user input, invocationNum=2) -> silent {}
        p2 = dict(p1, invocationNum=2)
        self.assertEqual(unarmored_hook.process_event(p2), {})

        # 3. Next clean user turn on same model -> silent {} (zero trajectory bloat)
        with transcript.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "step_index": 1,
                        "type": "PLANNER_RESPONSE",
                        "content": "单机 200 个 key 直接用进程内 LRU 就够了，上 Redis 纯属多加一跳网络延迟。",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        p3 = dict(p1, lastUserInput="那过期策略怎么定比较好？", invocationNum=1)
        self.assertEqual(unarmored_hook.process_event(p3), {})

        # 4. User switches dropdown to Claude Opus mid-session -> injects Claude delta immediately
        with transcript.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "step_index": 2,
                        "source": "USER_EXPLICIT",
                        "type": "USER_INPUT",
                        "content": "<USER_REQUEST>\n那并发锁呢？\n</USER_REQUEST>\n<USER_SETTINGS_CHANGE>\nThe user changed setting `Model Selection` from Gemini 4 Carbon (High) to Claude Opus 5.5 (High).\n</USER_SETTINGS_CHANGE>",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        p4 = dict(p1, lastUserInput="那并发锁呢？", invocationNum=1)
        out4 = unarmored_hook.process_event(p4)
        msg4 = out4["injectSteps"][0]["systemMessage"]["systemMessage"]
        self.assertIn("Claude", msg4)

    def test_antigravity_concrete_model_english_first_turn_no_bilingual_duplicate(self) -> None:
        # SessionStart with concrete modelName ("GPT-5") and empty input under language="auto" MUST defer
        s_out = unarmored_hook.process_event(
            {
                "hookEventName": "SessionStart",
                "conversationId": "conv-en-gpt5",
                "modelName": "GPT-5",
                "lastUserInput": "",
            }
        )
        self.assertEqual(s_out, {})

        # Turn 1 in English injects English directive ONCE without prior Chinese duplicate
        p_out = unarmored_hook.process_event(
            {
                "hookEventName": "PreInvocation",
                "conversationId": "conv-en-gpt5",
                "modelName": "GPT-5",
                "lastUserInput": "Compare ring buffer vs channel latency here.",
                "invocationNum": 1,
            }
        )
        msg = p_out["injectSteps"][0]["systemMessage"]["systemMessage"]
        self.assertIn("[Register:GPT]", msg)
        self.assertNotIn("语域校准", msg)

    def test_antigravity_cross_turn_mode_override_recovery_to_spar(self) -> None:
        transcript = Path(self.tmp.name) / "mode_override.jsonl"
        # Turn 1: User pastes traceback -> enters DEBUG_RECOVERY and injects directive
        out_debug = unarmored_hook.process_event(
            {
                "hookEventName": "PreInvocation",
                "conversationId": "conv-mode",
                "modelName": "GPT-5",
                "transcriptPath": str(transcript),
                "lastUserInput": "Traceback (most recent call last):\nValueError: invalid token",
                "invocationNum": 1,
            }
        )
        msg_debug = out_debug["injectSteps"][0]["systemMessage"]["systemMessage"]
        self.assertIn("Debug Recovery", msg_debug)

        # Turn 2: User explicitly switches back to discussion ("先别改代码，只讨论") -> MUST override stale DEBUG_RECOVERY
        out_spar = unarmored_hook.process_event(
            {
                "hookEventName": "PreInvocation",
                "conversationId": "conv-mode",
                "modelName": "GPT-5",
                "transcriptPath": str(transcript),
                "lastUserInput": "先别改代码，只讨论一下为什么会出现这个状态？",
                "invocationNum": 1,
            }
        )
        self.assertIn("injectSteps", out_spar)
        msg_spar = out_spar["injectSteps"][0]["systemMessage"]["systemMessage"]
        self.assertIn("当前意图：探讨", msg_spar)

        # Turn 3: Staying in PEER_SPAR -> silent {}
        out_spar_2 = unarmored_hook.process_event(
            {
                "hookEventName": "PreInvocation",
                "conversationId": "conv-mode",
                "modelName": "GPT-5",
                "transcriptPath": str(transcript),
                "lastUserInput": "那如果换成幂等队列优缺点是什么？",
                "invocationNum": 1,
            }
        )
        self.assertEqual(out_spar_2, {})

    def test_four_family_smell_positives_and_false_positive_exemptions(self) -> None:
        # Positive: GPT negative-contrast + closing waiter menu
        gpt_bad = "这不仅仅是一次简单的重构，更是一场架构范式的升级。值得注意的是，细节很重要。\n如果你需要，我可以进一步帮你把单元测试也写出来。"
        r_gpt = unarmored_hook.analyze_response_smells(gpt_bad)
        self.assertGreaterEqual(r_gpt["score"], 3)
        self.assertIn("gpt_neg_contrast", r_gpt["smells"])
        self.assertIn("gpt_closing_menu", r_gpt["smells"])

        # Positive: Gemini opening flattery + hyperbole
        gem_bad = "**太绝妙了！** 你一针见血地抓住了最核心的命门！这简直是降维打击级别的史诗级方案！"
        r_gem = unarmored_hook.analyze_response_smells(gem_bad)
        self.assertGreaterEqual(r_gem["score"], 3)
        self.assertIn("gem_opening_flattery", r_gem["smells"])
        self.assertIn("gem_hyperbole", r_gem["smells"])

        # Positive: Claude preachy pushback + performative apology
        claude_bad = "你说得完全正确！在动手做之前，我们不妨先审视一下这种直接修改配置的做法是否符合长远哲学。"
        r_claude = unarmored_hook.analyze_response_smells(claude_bad)
        self.assertGreaterEqual(r_claude["score"], 4)
        self.assertIn("claude_apology_pivot", r_claude["smells"])
        self.assertIn("claude_preachy", r_claude["smells"])

        # Positive: DeepSeek lazy elision in code block & prose hand-waving
        ds_bad = "修改如下，限于篇幅，这里不再赘述：\n```python\ndef handle():\n    # 其余代码保持不变\n    ...\n```"
        r_ds = unarmored_hook.analyze_response_smells(ds_bad)
        self.assertGreaterEqual(r_ds["score"], 4)
        self.assertIn("ds_lazy_code", r_ds["smells"])
        self.assertIn("ds_prose_handwave", r_ds["smells"])

        # False-positive guard 1: Conditional logic, concrete diagnostic contrast, API docs, English additive contrast, 3 Markdown images
        clean_tech = (
            "如果当前用户不是管理员，而是访客，中间件直接返回 403。\n"
            "这次故障的根因不在于缓存失效，而在于写入路径缺少幂等键。\n"
            "如果你需要自定义超时，可以传入 `timeout=5`。\n"
            "This isn't only slow, we also leak FDs.\n"
            "It's not just slow, it's also leaking sockets under load.\n"
            "![arch](a.png) ![seq](b.png) ![flow](c.png)\n"
            "| **模块** | **耗时** | **内存** | **状态** |\n"
        )
        r_clean = unarmored_hook.analyze_response_smells(clean_tech)
        self.assertEqual(r_clean["score"], 0, f"Unexpected false positive: {r_clean}")

        # False-positive guard 2: CommonMark nested fences, string literals containing fence chars, untagged log `...`, Python Protocol
        clean_fences = (
            "> 这不仅仅是一次重构，更是降维打击！\n\n"
            "````markdown\n"
            "反例文档示例：\n"
            "```python\n"
            "# 其余代码保持不变\n"
            "```\n"
            "````\n"
            "```python\n"
            'FENCE_MARKER = "~~~~"\n'
            'RAW_BACKTICKS = r"```"\n'
            "class Runner(Protocol):\n"
            "    def execute(self) -> int:\n"
            "        ...\n"
            "```\n"
            "```\n"
            "2026-11-15 INFO connecting...\n"
            "...\n"
            "2026-11-15 INFO done\n"
            "```\n"
            "```ts\n"
            "const merged = { ...defaults, retries: 3 };\n"
            "```"
        )
        r_clean2 = unarmored_hook.analyze_response_smells(clean_fences)
        self.assertEqual(r_clean2["score"], 0, f"Unexpected false positive on nested/complex fences: {r_clean2}")

    def test_redos_linear_time_adversarial_inputs(self) -> None:
        # 1. Unclosed <USER_REQUEST> with huge whitespace
        t0 = time.perf_counter()
        res1 = unarmored_hook.extract_clean_user_text("<USER_REQUEST>" + (" " * 20_000) + "hello world")
        dt1_ms = (time.perf_counter() - t0) * 1000.0
        self.assertEqual(res1, "hello world")
        self.assertLess(dt1_ms, 50.0, f"extract_clean_user_text too slow: {dt1_ms:.1f}ms")

        # 2. Adversarial dot-chains and identifier runs in classify_intent
        adv_dots = "a." * 20_000
        adv_word = "a" * 80_000 + "!"
        t0 = time.perf_counter()
        unarmored_hook.classify_intent(adv_dots, "PEER_SPAR")
        unarmored_hook.classify_intent(adv_word, "PEER_SPAR")
        dt2_ms = (time.perf_counter() - t0) * 1000.0
        self.assertLess(dt2_ms, 80.0, f"classify_intent adversarial input too slow: {dt2_ms:.1f}ms")

        # 3. Single-line dense **bold** spam without colons in analyze_response_smells
        bold_spam = "- " + " ".join(f"**word{i}**" for i in range(80))
        t0 = time.perf_counter()
        rep = unarmored_hook.analyze_response_smells(bold_spam)
        dt3_ms = (time.perf_counter() - t0) * 1000.0
        self.assertIn("gem_dramatic_bold", rep["smells"])
        self.assertLess(dt3_ms, 50.0, f"analyze_response_smells bold line too slow: {dt3_ms:.1f}ms")

        # 4. Unclosed Markdown brackets, image links, and backticks (O(N) disjoint delimiter regression)
        for label, payload_str in (
            ("unclosed_bracket_lines", "[item\n" * 20_000),
            ("unclosed_bracket_single_line", "[item " * 20_000),
            ("unclosed_link_paren", "[x](" * 20_000),
            ("unclosed_backticks", "`abc " * 20_000),
        ):
            t0 = time.perf_counter()
            unarmored_hook.split_two_streams(payload_str)
            dt_ms = (time.perf_counter() - t0) * 1000.0
            self.assertLess(dt_ms, 100.0, f"split_two_streams({label}) quadratic regression: {dt_ms:.1f}ms")

    def test_codex_rollout_jsonl_and_last_assistant_message(self) -> None:
        rollout = Path(self.tmp.name) / ".codex" / "sessions" / "rollout-1.jsonl"
        rollout.parent.mkdir(parents=True, exist_ok=True)

        # Simulate real Codex CLI rollout-*.jsonl envelope format
        entries = [
            {"type": "event_msg", "payload": {"type": "user_message", "message": "Implement token refresh in auth.py"}},
            {"type": "turn_context", "payload": {"model": "gpt-5.4-codex"}},
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "It's not just a refresh helper—it's a pivotal moment. Would you like me to wire the tests next?",
                        }
                    ],
                },
            },
        ]
        rollout.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")

        # 1. Next UserPromptSubmit resolves model from turn_context and detects relapse from response_item
        out = unarmored_hook.process_event(
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "codex-real-1",
                "turn_id": "turn-2",
                "transcript_path": str(rollout),
                "prompt": "Update auth.py with full retry support.",
            }
        )
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("[Register:GPT]", ctx)
        self.assertIn("[Relapse Fix]", ctx)
        self.assertIn("[Turn Intent: Surgical Execution]", ctx)

        # 2. Append new user turn + custom_tool_call `apply_patch` containing lazy code comment -> Stop gate blocks in English!
        turn2_entries = [
            {"type": "event_msg", "payload": {"type": "user_message", "message": "Update auth.py with full retry support."}},
            {
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call",
                    "name": "apply_patch",
                    "input": "*** Begin Patch\n*** Update File: auth.py\n@@\n+def refresh():\n+    # rest of the code remains unchanged\n+    pass\n*** End Patch",
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "Patched auth.py."}],
                },
            },
        ]
        with rollout.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(json.dumps(e) for e in turn2_entries) + "\n")

        stop_out = unarmored_hook.process_event(
            {
                "hook_event_name": "Stop",
                "session_id": "codex-real-1",
                "turn_id": "turn-2",
                "transcript_path": str(rollout),
                "stop_hook_active": False,
            }
        )
        self.assertEqual(stop_out["decision"], "block")
        self.assertIn("[Completeness Gate]", stop_out["reason"])

        # 3. Stop gate prefers authoritative `last_assistant_message` EVEN when transcript already has Step 1 text in the same turn
        multi_step_rollout = Path(self.tmp.name) / ".claude" / "multi_step.jsonl"
        multi_step_rollout.parent.mkdir(parents=True, exist_ok=True)
        unarmored_hook.process_event(
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "claude-multistep-stop",
                "transcript_path": str(multi_step_rollout),
                "prompt": "Implement token check in handler.py",
            }
        )
        multi_step_rollout.write_text(
            json.dumps({"role": "user", "content": "Implement token check in handler.py"})
            + "\n"
            + json.dumps(
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "Let me read handler.py first."},
                        {"type": "tool_use", "name": "Read", "input": {"file_path": "handler.py"}},
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        multistep_stop = unarmored_hook.process_event(
            {
                "hook_event_name": "Stop",
                "session_id": "claude-multistep-stop",
                "transcript_path": str(multi_step_rollout),
                "last_assistant_message": "Updated:\n```python\ndef check():\n    # TODO: 自行实现校验\n    pass\n```",
                "stop_hook_active": False,
            }
        )
        self.assertEqual(multistep_stop["decision"], "block")
        self.assertIn("[Completeness Gate]", multistep_stop["reason"])

    def test_stop_hook_gates_and_background_subagent_safety(self) -> None:
        transcript = Path(self.tmp.name) / "stop_transcript.jsonl"
        unarmored_hook.process_event(
            {
                "hookEventName": "PreInvocation",
                "conversationId": "stop-conv",
                "modelName": "deepseek-r1",
                "transcriptPath": str(transcript),
                "lastUserInput": "把 auth.py 里的登录校验补全",
                "invocationNum": 1,
            }
        )

        # Case 1: Lazy code elision -> Stop hook blocks & forces continue
        transcript.write_text(
            json.dumps({"step_index": 1, "source": "USER_EXPLICIT", "type": "USER_INPUT", "content": "把 auth.py 补全"})
            + "\n"
            + json.dumps(
                {
                    "step_index": 2,
                    "type": "PLANNER_RESPONSE",
                    "content": "已修改：\n```python\ndef login():\n    # TODO: 自行实现校验逻辑\n    pass\n```",
                    "tool_calls": [],
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        stop_res = unarmored_hook.process_event(
            {
                "hookEventName": "Stop",
                "conversationId": "stop-conv",
                "modelName": "deepseek-r1",
                "transcriptPath": str(transcript),
                "terminationReason": "NO_TOOL_CALL",
                "fullyIdle": True,
                "continuationActive": False,
            }
        )
        self.assertEqual(stop_res["decision"], "continue")
        self.assertIn("完备门禁", stop_res["reason"])

        # Case 2: Loop cap reached (max_stop_continuations=1) -> second Stop on same turn allows stop
        stop_res_2 = unarmored_hook.process_event(
            {
                "hookEventName": "Stop",
                "conversationId": "stop-conv",
                "modelName": "deepseek-r1",
                "transcriptPath": str(transcript),
                "terminationReason": "NO_TOOL_CALL",
                "fullyIdle": True,
                "continuationActive": False,
            }
        )
        self.assertEqual(stop_res_2, {"decision": "allow"})

        # Case 3: Background subagent active (fullyIdle=False) -> always allow stop even on new turn
        unarmored_hook.process_event(
            {
                "hookEventName": "PreInvocation",
                "conversationId": "stop-conv",
                "modelName": "deepseek-r1",
                "transcriptPath": str(transcript),
                "lastUserInput": "重构整个模块",
                "invocationNum": 1,
            }
        )
        transcript.write_text(
            json.dumps({"step_index": 3, "source": "USER_EXPLICIT", "type": "USER_INPUT", "content": "重构整个模块"})
            + "\n"
            + json.dumps(
                {
                    "step_index": 4,
                    "type": "PLANNER_RESPONSE",
                    "content": "接下来我将先查看目录结构并等待子代理返回。",
                    "tool_calls": [],
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        stop_bg = unarmored_hook.process_event(
            {
                "hookEventName": "Stop",
                "conversationId": "stop-conv",
                "modelName": "deepseek-r1",
                "transcriptPath": str(transcript),
                "terminationReason": "NO_TOOL_CALL",
                "fullyIdle": False,
                "continuationActive": False,
            }
        )
        self.assertEqual(stop_bg, {"decision": "allow"})

    def test_subprocess_utf8_bom_oversized_fail_open_and_latency(self) -> None:
        py_exe = manage.resolve_real_python()
        script = str(REPO_ROOT / "scripts" / "unarmored_hook.py")
        env = dict(os.environ)
        env["PYTHONUTF8"] = "0"
        env["PYTHONIOENCODING"] = "gbk"
        env["UNARMORED_STATE_DIR"] = str(self.state_dir)
        env["UNARMORED_CONFIG"] = str(self.cfg_path)

        # 1. UTF-8 BOM + Emoji + non-GBK accents
        bom_payload = b"\xef\xbb\xbf" + json.dumps(
            {
                "hookEventName": "SessionStart",
                "conversationId": "utf8-bom-test",
                "modelName": "GPT-5",
                "lastUserInput": "测试 emoji 🚀 café naïve — 破甲",
            },
            ensure_ascii=False,
        ).encode("utf-8")

        proc = subprocess.run([py_exe, "-E", "-S", script], input=bom_payload, capture_output=True, env=env, timeout=5, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", errors="replace"))
        parsed = json.loads(proc.stdout.decode("utf-8"))
        self.assertIn("GPT", parsed["injectSteps"][0]["systemMessage"]["systemMessage"])

        # 2. Oversized >256KB stdin payload fails open with rc=0:
        #    - PreInvocation containing literal "Stop" inside user text MUST return {} (not {"decision":"allow"})
        #    - Stop with "hookEventName":"Stop" at tail MUST return {"decision":"allow"}
        huge_pre_with_stop_word = json.dumps(
            {
                "hookEventName": "PreInvocation",
                "conversationId": "huge-pre",
                "lastUserInput": 'Why did Windows Service "Stop" event fail? ' + ("x" * 320_000),
            }
        ).encode("utf-8")
        proc_huge = subprocess.run(
            [py_exe, "-E", "-S", script], input=huge_pre_with_stop_word, capture_output=True, env=env, timeout=5, check=False
        )
        self.assertEqual(proc_huge.returncode, 0)
        self.assertEqual(json.loads(proc_huge.stdout.decode("utf-8")), {})

        huge_stop = (
            '{"padding":"' + ("y" * 320_000) + '","hookEventName": "Stop","conversationId":"huge-stop"}'
        ).encode("utf-8")
        proc_huge_stop = subprocess.run(
            [py_exe, "-E", "-S", script], input=huge_stop, capture_output=True, env=env, timeout=5, check=False
        )
        self.assertEqual(proc_huge_stop.returncode, 0)
        self.assertEqual(json.loads(proc_huge_stop.stdout.decode("utf-8")), {"decision": "allow"})

        # 3. Measure hot-path no-op latency (<120ms median target)
        hot_payload = json.dumps(
            {
                "hookEventName": "PreInvocation",
                "conversationId": "utf8-bom-test",
                "modelName": "GPT-5",
                "lastUserInput": "测试 emoji 🚀 café naïve — 破甲",
                "invocationNum": 2,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        subprocess.run([py_exe, "-E", "-S", script], input=hot_payload, capture_output=True, env=env, timeout=5, check=True)

        samples = []
        for _ in range(5):
            t0 = time.perf_counter()
            r = subprocess.run([py_exe, "-E", "-S", script], input=hot_payload, capture_output=True, env=env, timeout=5, check=True)
            samples.append((time.perf_counter() - t0) * 1000.0)
            self.assertEqual(json.loads(r.stdout.decode("utf-8")), {})
        samples.sort()
        median_ms = samples[len(samples) // 2]
        self.assertLess(median_ms, 120.0, f"Hot-path hook median latency too slow: {median_ms:.1f}ms ({samples})")

    def _write_pack(self, name: str, pack: dict) -> Path:
        pack_dir = self.state_dir / "packs"
        pack_dir.mkdir(parents=True, exist_ok=True)
        path = pack_dir / name
        path.write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")
        return path

    @staticmethod
    def _ctx(out: dict) -> str:
        return ((out or {}).get("hookSpecificOutput") or {}).get("additionalContext", "")

    def test_profile_pack_overlay_strip_longest_alias_roles_and_bypass(self) -> None:
        self._write_pack(
            "team.json",
            {
                "schema": "unarmored-pack/1",
                "name": "team",
                "defaults": {"tone": "sharp", "language": "en"},
                "model_strip_patterns": ["^my-gw[-_/:]+", "(unclosed", "\\[1m\\]$", "^claude-proxy[-_/:]+"],
                "model_aliases": {"house-model": "claude", "lane": "claude", "deepseek-x": "deepseek", "bad": "nonsense"},
                "bypass": {"session_patterns": ["nightly-"], "prompt_markers": ["[no-cal]"]},
                "roles": [
                    {"id": "rev", "policy": "adversarial", "match": {"agent_types": ["code-reviewer"]}},
                    {"id": "wrk", "policy": "terse", "match": {"agent_types": ["worker"]}},
                    {"id": "batch", "policy": "skip", "match": {"session_patterns": ["batch-"]}},
                    {"id": "broken", "policy": "explode", "match": {"agent_types": ["x"]}},
                ],
                "voice": {"en": "VOICE-CANON-LINE"},
                "directives": {"claude": {"en": "CLAUDE-OVERRIDE-LINE"}},
            },
        )
        self._write_pack("ignored.json", {"name": "no-schema", "model_aliases": {"zzz": "gpt"}})
        self.cfg_path.write_text(json.dumps({"tone": "peer"}), encoding="utf-8")

        cfg = unarmored_hook.load_config()
        self.assertEqual(cfg["packs_loaded"], ["team"])
        self.assertEqual(cfg["tone"], "peer", "config.json scalar beats pack default")
        self.assertEqual(cfg["language"], "en", "pack default applies where config.json is silent")
        self.assertNotIn("bad", cfg["model_aliases"])
        self.assertNotIn("zzz", cfg["model_aliases"])
        self.assertEqual([r["id"] for r in cfg["roles"]], ["rev", "wrk", "batch"])

        unarmored_hook.set_active_strip_patterns(cfg["model_strip_patterns"])
        self.assertEqual(unarmored_hook.classify_model_family("my-gw/house-model[1m]", cfg["model_aliases"]), "claude")
        self.assertEqual(unarmored_hook.classify_model_family("lane/deepseek-x", cfg["model_aliases"]), "deepseek")
        self.assertEqual(unarmored_hook.classify_model_family("claude-proxy/gpt-5", cfg["model_aliases"]), "gpt")
        unarmored_hook.set_active_strip_patterns([])
        self.assertEqual(unarmored_hook.classify_model_family("claude-proxy/gpt-5"), "claude", "control: unstripped prefix misroutes")

        base = {"hook_event_name": "SessionStart", "turn_id": "t0", "model": "my-gw/house-model"}
        default_out = self._ctx(unarmored_hook.process_event({**base, "session_id": "main-1"}, cfg))
        self.assertIn("CLAUDE-OVERRIDE-LINE", default_out)
        self.assertIn("VOICE-CANON-LINE", default_out)
        self.assertIn("<unarmored_baseline>", default_out)

        terse_out = self._ctx(unarmored_hook.process_event({**base, "session_id": "w-1", "agent_type": "worker"}, cfg))
        self.assertIn("CLAUDE-OVERRIDE-LINE", terse_out)
        self.assertIn(unarmored_hook.ROLE_DIRECTIVES["terse"]["en"], terse_out)
        self.assertNotIn("<unarmored_baseline>", terse_out)
        self.assertNotIn("VOICE-CANON-LINE", terse_out)

        rev_out = self._ctx(unarmored_hook.process_event({**base, "session_id": "r-1", "agent_type": "code-reviewer"}, cfg))
        self.assertIn(unarmored_hook.ROLE_DIRECTIVES["adversarial"]["en"], rev_out)

        self.assertEqual(unarmored_hook.process_event({**base, "session_id": "batch-7"}, cfg), {})
        self.assertEqual(unarmored_hook.process_event({**base, "session_id": "nightly-report"}, cfg), {})
        submit = {"hook_event_name": "UserPromptSubmit", "turn_id": "t1", "session_id": "main-2", "model": "gpt-5", "prompt": "[no-cal] run it"}
        self.assertEqual(unarmored_hook.process_event(submit, cfg), {})
        self.assertEqual(
            unarmored_hook.process_event({"hook_event_name": "Stop", "session_id": "batch-7", "turn_id": "t2"}, cfg), {}
        )

    def test_pack_change_reanchors_mid_session(self) -> None:
        pack = {"schema": "unarmored-pack/1", "name": "p", "defaults": {"language": "en"}, "voice": {"en": "VOICE-ONE"}}
        self._write_pack("p.json", pack)
        payload = {"hook_event_name": "UserPromptSubmit", "turn_id": "t1", "session_id": "sess-x", "model": "gpt-5"}
        first = self._ctx(unarmored_hook.process_event({**payload, "prompt": "first question here"}))
        self.assertIn("VOICE-ONE", first)
        second = self._ctx(unarmored_hook.process_event({**payload, "turn_id": "t2", "prompt": "second question here"}))
        self.assertNotIn("VOICE-ONE", second, "no re-anchor while nothing changed")
        pack["voice"] = {"en": "VOICE-TWO"}
        self._write_pack("p.json", pack)
        third = self._ctx(unarmored_hook.process_event({**payload, "turn_id": "t3", "prompt": "third question here"}))
        self.assertIn("VOICE-TWO", third, "pack edits re-anchor on the next turn")

    def test_dsh_static_block_install_is_idempotent_and_preserves_user_rules(self) -> None:
        ws = Path(self.tmp.name) / "dsh ws"
        ws.mkdir()
        agents_md = ws / "AGENTS.md"
        agents_md.write_text("# My project rules\n- keep it simple\n", encoding="utf-8")
        for _ in range(2):
            self.assertEqual(manage.main(["install", "--agent", "dsh", "--target", str(ws), "--block-language", "en"]), 0)
        text = agents_md.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# My project rules"))
        self.assertEqual(text.count(manage.DSH_BLOCK_BEGIN), 1)
        self.assertIn("Register calibration (Unarmored)", text)
        self.assertEqual(manage.main(["uninstall", "--agent", "dsh", "--target", str(ws)]), 0)
        self.assertEqual(agents_md.read_text(encoding="utf-8"), "# My project rules\n- keep it simple\n")
        self.assertFalse((ws / ".dsh" / "skills" / "unarmored").exists())

        broken = ws / "AGENTS.md"
        broken.write_text(f"x\n{manage.DSH_BLOCK_BEGIN}\nno end marker\n", encoding="utf-8")
        self.assertEqual(manage.main(["install", "--agent", "dsh", "--target", str(ws)]), 1)
        self.assertIn("no end marker", broken.read_text(encoding="utf-8"))

    def test_formatting_detectors_emdash_and_verdict_aware_fence_sitting(self) -> None:
        # 1. meta_opening + divider_spam (matches real DeepSeek live failure)
        ds_slop = (
            "四个问题都不需要查资料，直接回答。先说结论，再讲理由。\n\n---\n\n"
            "**1. 头疼**：布洛芬。\n\n---\n\n**2. 前端**：React。\n\n---\n\n"
            "需要我帮你把第 3 条那句摘要重写吗？"
        )
        rep = unarmored_hook.analyze_response_smells(ds_slop)
        self.assertIn("meta_opening", rep["smells"])
        self.assertIn("divider_spam", rep["smells"])
        self.assertIn("gpt_closing_menu", rep["smells"])
        remedy = unarmored_hook.format_smell_remedy(rep["smells"], "zh")
        self.assertIn("不画横线", remedy)
        self.assertIn("别在开头播报", remedy)

        # Single divider is fine; clean direct opening is fine
        self.assertNotIn("divider_spam", unarmored_hook.analyze_response_smells("第一段。\n---\n第二段。")["smells"])
        self.assertNotIn("meta_opening", unarmored_hook.analyze_response_smells("直接选布洛芬，抗炎止痛更稳。")["smells"])

        # 2. wall_of_text (unbroken 450-char single brick)
        brick = "十人以内的小团队搞微服务大多是在给自己找罪受。" * 18
        rep_brick = unarmored_hook.analyze_response_smells(brick)
        self.assertIn("wall_of_text", rep_brick["smells"])
        self.assertIn("2-4 句自然分段", unarmored_hook.format_smell_remedy(rep_brick["smells"], "zh"))

        # Multi-paragraph prose of the same length is NOT a wall of text
        good_paras = ("十人以内的小团队搞微服务大多是在给自己找罪受。" * 6 + "\n\n") * 3
        self.assertNotIn("wall_of_text", unarmored_hook.analyze_response_smells(good_paras)["smells"])

        # 3. Em-dash double-counting bug fix: 3 Chinese —— dashes must NOT trigger gpt_slop_lexicon; 6+ MUST
        expressive = "这不叫优雅——叫裸奔。真正的代价在后面——半夜查账——谁碰谁头疼。"
        self.assertNotIn("gpt_slop_lexicon", unarmored_hook.analyze_response_smells(expressive)["smells"])
        dash_spam = "一——二——三——四——五——六——七。"
        self.assertIn("gpt_slop_lexicon", unarmored_hook.analyze_response_smells(dash_spam)["smells"])

        # 4. Verdict-aware fence_sitting: clear pick + two honest "取决于" thresholds is NOT fence-sitting
        honest = "选 SQLite。以后要不要换 PG 取决于写并发，什么时候拆服务取决于团队规模。"
        self.assertNotIn("fence_sitting", unarmored_hook.analyze_response_smells(honest)["smells"])
        for wishy in (
            "这个问题不好一概而论，具体方案取决于你的业务规模，技术选型也取决于团队偏好。",
            "这个问题不好说，选哪个取决于你的需求，用什么框架看你的团队情况。",
            "不建议一概而论，具体方案取决于你的业务规模，技术选型也取决于团队偏好。",
        ):
            self.assertIn("fence_sitting", unarmored_hook.analyze_response_smells(wishy)["smells"], wishy)

        # 5. Red-team regressions: meta_opening ReDoS + variants, spaced dividers, language-aware per-paragraph wall_of_text
        t0 = time.perf_counter()
        self.assertIsNone(unarmored_hook._get_compiled_patterns()["meta_opening"].search("\n" * 20_000 + "x"))
        self.assertLess((time.perf_counter() - t0) * 1000.0, 50.0, "meta_opening must stay linear O(N)")
        self.assertIn("meta_opening", unarmored_hook.analyze_response_smells("好的，先说结论：选布洛芬。")["smells"])
        self.assertIn("meta_opening", unarmored_hook.analyze_response_smells("这4个问题都不需要查资料，直接回答。")["smells"])
        self.assertIn("divider_spam", unarmored_hook.analyze_response_smells("一\n- - -\n二\n* * *\n三")["smells"])

        # Normal 350-char English paragraph is NOT a wall of text; multi-para or code-trailing 400-char CJK brick IS
        self.assertNotIn("wall_of_text", unarmored_hook.analyze_response_smells(unarmored_hook.MODEL_DIRECTIVES["gpt"]["en"])["smells"])
        self.assertIn("wall_of_text", unarmored_hook.analyze_response_smells("选 A。\n\n" + brick)["smells"])
        self.assertIn("wall_of_text", unarmored_hook.analyze_response_smells(brick + "\n\n```bash\nnpm test\n```")["smells"])

    def test_six_modes_deepseek_wire_anchor_and_turn5_refresh(self) -> None:
        self.assertEqual(unarmored_hook.classify_intent("用说人话的方式解释一下注意力机制里的 Q、K、V 到底是干嘛的。"), "EXPLAIN_DEEP")
        self.assertEqual(unarmored_hook.classify_intent("Explain why transformers need positional encoding"), "EXPLAIN_DEEP")
        self.assertEqual(unarmored_hook.classify_intent("用说人话解释一下为什么会出现梯度消失"), "EXPLAIN_DEEP")
        self.assertEqual(unarmored_hook.classify_intent("用说人话解释一下 `Transformer` 里的 `add` 和 `norm` 到底是怎么工作的"), "EXPLAIN_DEEP")
        self.assertEqual(unarmored_hook.classify_intent("解释一下 `README.md` 里提到的机制到底是怎么实现的"), "EXPLAIN_DEEP")
        self.assertEqual(unarmored_hook.classify_intent("帮我写一段 400 字左右的技术短评，观点明确一点：为什么小团队别搞微服务"), "CRITIQUE_OPINION")
        self.assertEqual(unarmored_hook.classify_intent("评价一下 auth.py 里的重构，合理吗？"), "CRITIQUE_OPINION")
        self.assertEqual(unarmored_hook.classify_intent("今天改 bug 改到心态崩了，一个空指针找了三个小时。"), "EMPATHY_VENT")
        self.assertEqual(unarmored_hook.classify_intent("导师又把我的初稿全盘否定了，我已经改了五版了，好累。"), "EMPATHY_VENT")
        self.assertEqual(unarmored_hook.classify_intent("Update auth.py to add retry logic"), "SURGICAL_EXEC")
        self.assertEqual(unarmored_hook.classify_intent("程序崩了，报错 ValueError: bad token"), "DEBUG_RECOVERY")
        self.assertEqual(unarmored_hook.classify_intent("线上服务崩溃了，全站挂了，帮我赶紧回滚！"), "DEBUG_RECOVERY")
        self.assertEqual(unarmored_hook.classify_intent("这报错烦死了，代码一直死循环卡死"), "DEBUG_RECOVERY")
        self.assertEqual(unarmored_hook.classify_intent("为什么会报这个错？\nTraceback (most recent call last):\nKeyError: 1"), "DEBUG_RECOVERY")

        # Calm / peer / sharp tones all accepted; invalid falls back to peer
        for tone in ("calm", "peer", "sharp"):
            self.cfg_path.write_text(json.dumps({"tone": tone}), encoding="utf-8")
            self.assertEqual(unarmored_hook.load_config()["tone"], tone)
        self.cfg_path.write_text(json.dumps({"tone": "unknown-tone"}), encoding="utf-8")
        self.assertEqual(unarmored_hook.load_config()["tone"], "peer")

        # DeepSeek chat turn on Claude/Codex hook receives [DS直出提醒]; exec turn does NOT
        ds_base = {"hook_event_name": "UserPromptSubmit", "session_id": "ds-s1", "turn_id": "t1", "model": "deepseek-r1"}
        out_chat = self._ctx(unarmored_hook.process_event({**ds_base, "prompt": "用说人话的方式解释一下 QKV 到底是干嘛的"}))
        self.assertIn("[当前意图：讲透原理]", out_chat)
        self.assertIn("[DS直出提醒]", out_chat)

        out_exec = self._ctx(unarmored_hook.process_event({**ds_base, "turn_id": "t2", "prompt": "修改 app.py 加上超时重试"}))
        self.assertIn("[当前意图：动手]", out_exec)
        self.assertNotIn("[DS直出提醒]", out_exec)

        # Turn 5 long-session anti-decay refresh fires cleanly
        for i in range(3, 6):
            out_i = self._ctx(
                unarmored_hook.process_event({**ds_base, "turn_id": f"t{i}", "prompt": f"第 {i} 轮顺便问个架构权衡怎么看"})
            )
            if i == 5:
                self.assertIn("[语域保鲜]", out_i)
            else:
                self.assertNotIn("[语域保鲜]", out_i)

    def test_honest_reporting_exemptions_new_smells_ranking_and_redos(self) -> None:
        # 1. Honest engineering uncertainty MUST NOT trigger false-positive relapses
        for honest in (
            "这一步没跑单测，只是静态读代码推断。值得注意的是，吞吐上限取决于连接池大小，也取决于下游 Redis 的 RTT。",
            "没在生产硬件上跑，数据仅供参考。值得注意的是，高并发下延迟主要取决于锁竞争。",
            "先留着单体别动。以后拆不拆取决于团队人数，拆哪块看具体场景。",
            "I haven't tested this on Linux yet; rough estimate for reference only. Latency depends on disk IOPS and queue depth.",
        ):
            rep = unarmored_hook.analyze_response_smells(honest)
            self.assertEqual(rep["score"], 0, f"Honest disclosure falsely flagged: {honest!r} -> {rep}")

        # Expressive multi-paragraph prose with 3 exclamation marks is fine, whereas short burst or '!!' still flags
        long_expressive = ("这设计真痛快！" + "把状态机拆干净后边界清晰多了，排查也省了一半功夫。" * 6 + "\n\n") * 3
        self.assertNotIn("gem_dramatic_bold", unarmored_hook.analyze_response_smells(long_expressive)["smells"])
        self.assertIn("gem_dramatic_bold", unarmored_hook.analyze_response_smells("太赞了！完美！必须上！")["smells"])
        self.assertIn("gem_dramatic_bold", unarmored_hook.analyze_response_smells("这简直不可思议！！")["smells"])

        # 2. Newly caught real-world AI-slop families
        self.assertIn(
            "doc_format_in_chat",
            unarmored_hook.analyze_response_smells("**结论**\n\n用 SQLite。\n\n**原因**\n\n运维轻。\n\n**边界**\n\n单机。")["smells"],
        )
        rep_cb_zh = unarmored_hook.analyze_response_smells("这不是非黑即白的选择，我们需要在灵活性和复杂度之间寻找一个动态平衡点。")
        self.assertIn("consultant_balance", rep_cb_zh["smells"])
        self.assertGreaterEqual(rep_cb_zh["score"], 2)

        rep_cb_en = unarmored_hook.analyze_response_smells(
            "Both React and Vue are mature choices. While React offers a vast ecosystem, Vue provides gentle ergonomics. Ultimately, the right choice comes down to your team."
        )
        self.assertIn("consultant_balance", rep_cb_en["smells"])
        self.assertIn("praise_then_pivot", unarmored_hook.analyze_response_smells("你的出发点很好，不过直接拆微服务确实太早。")["smells"])
        rep_fence = unarmored_hook.analyze_response_smells("各有优劣，看你怎么选。")
        self.assertIn("fence_sitting", rep_fence["smells"])
        self.assertGreaterEqual(rep_fence["score"], 2)
        self.assertIn(
            "disclaimer_boilerplate",
            unarmored_hook.analyze_response_smells("一般性的法律信息，不是正式法律意见。具体最好先问一下律师。")["smells"],
        )
        rep_meta_close = unarmored_hook.analyze_response_smells("简单说：选布洛芬。有任何问题随时告诉我，希望这些分析能帮到你。")
        self.assertIn("meta_opening", rep_meta_close["smells"])
        self.assertIn("closing_offer", rep_meta_close["smells"])

        # 3. Severity ranking: 2-point severe smells are never evicted by 1-point hints
        unsorted = ["meta_opening", "wall_of_text", "divider_spam", "consultant_balance", "ds_lazy_code"]
        remedy = unarmored_hook.format_smell_remedy(unsorted, "zh")
        self.assertIn("顾问式端水", remedy)
        self.assertIn("代码省略占位符", remedy)

        # 4. O(N) linear-time ReDoS check on all new v0.6 regexes
        adv = ("**bold header " * 1500) + ("while React offers " * 1000) + ("没在" + "甲" * 20_000)
        t0 = time.perf_counter()
        unarmored_hook.analyze_response_smells(adv)
        self.assertLess((time.perf_counter() - t0) * 1000.0, 120.0)

    def test_intent_routing_precision_and_challenge_expansion(self) -> None:
        cases = [
            ("git rebase 和 git merge，哪个会改写已有的提交历史？", "PEER_SPAR"),
            ("前端状态管理，项目不大，用 Redux Toolkit 还是 Zustand？", "CRITIQUE_OPINION"),
            ("Should a solo developer write unit tests for a weekend prototype?", "CRITIQUE_OPINION"),
            ("十人以内的团队适合上微服务吗？", "CRITIQUE_OPINION"),
            ("为什么 batch normalization 在 batch size 很小时效果变差？", "EXPLAIN_DEEP"),
            ("介绍一下 Docker。", "EXPLAIN_DEEP"),
            ("投了 40 份简历，只有一个面试，还挂了。是不是我不适合干这行？", "EMPATHY_VENT"),
            ("先别急着改文件，给我出个修改 auth.py 的方案", "PEER_SPAR"),
        ]
        for prompt, expected in cases:
            self.assertEqual(unarmored_hook.classify_intent(prompt), expected, prompt)

        self.assertFalse(unarmored_hook.allows_disk_edits("先别急着改文件，给我出个修改 auth.py 的方案", "SURGICAL_EXEC"))
        self.assertTrue(unarmored_hook.allows_disk_edits("修改 auth.py 加上超时重试", "SURGICAL_EXEC"))

        # Bare "好" inside EMPATHY_VENT must NOT switch to SURGICAL_EXEC; explicit "动手吧" DOES
        self.assertEqual(unarmored_hook.classify_intent("好", prev_mode="EMPATHY_VENT"), "EMPATHY_VENT")
        self.assertEqual(unarmored_hook.classify_intent("动手吧", prev_mode="EMPATHY_VENT"), "SURGICAL_EXEC")
        self.assertEqual(unarmored_hook.classify_intent("好", prev_mode="PEER_SPAR"), "SURGICAL_EXEC")

        # Expanded epistemic challenge detection
        self.assertTrue(unarmored_hook.is_epistemic_challenge("Microservices are always better at scale, right?"))
        self.assertTrue(unarmored_hook.is_epistemic_challenge("上了 HTTPS 就不用做鉴权了吧？"))

    def test_turn1_wire_anchor_edge_trigger_antigravity_zh_mirror_and_sticky_bypass(self) -> None:
        # 1. Claude/Codex GPT: SessionStart initializes system baseline; Turn 1 emits compact [直出·GPT] wire anchor;
        #    Turn 2 steady-state PEER_SPAR emits {} (zero bloat); Turn 3 mode change emits new mode;
        #    Turn 5 in SURGICAL_EXEC suppresses [语域保鲜], whereas chat Turn 5/10 rotates refresh variants.
        sid = "gpt-edge-1"
        ss = unarmored_hook.process_event(
            {"hook_event_name": "SessionStart", "session_id": sid, "turn_id": "t0", "model": "gpt-5.4"}
        )
        self.assertIn("<unarmored_baseline>", self._ctx(ss))

        t1 = unarmored_hook.process_event(
            {"hook_event_name": "UserPromptSubmit", "session_id": sid, "turn_id": "t1", "model": "gpt-5.4", "prompt": "聊聊缓存过期策略怎么定"}
        )
        ctx1 = self._ctx(t1)
        self.assertNotIn("<unarmored_baseline>", ctx1, "baseline already sent at SessionStart")
        self.assertIn("[当前意图：探讨]", ctx1)
        self.assertIn("[直出·GPT]", ctx1)

        t2 = unarmored_hook.process_event(
            {"hook_event_name": "UserPromptSubmit", "session_id": sid, "turn_id": "t2", "model": "gpt-5.4", "prompt": "那热点 key 怎么防击穿？"}
        )
        self.assertEqual(t2, {}, "steady-state PEER_SPAR turn stays silent (zero context bloat)")

        t3 = unarmored_hook.process_event(
            {"hook_event_name": "UserPromptSubmit", "session_id": sid, "turn_id": "t3", "model": "gpt-5.4", "prompt": "什么是布隆过滤器？"}
        )
        self.assertIn("[当前意图：讲透原理]", self._ctx(t3))

        t4 = unarmored_hook.process_event(
            {"hook_event_name": "UserPromptSubmit", "session_id": sid, "turn_id": "t4", "model": "gpt-5.4", "prompt": "修改 cache.py 加上超时参数"}
        )
        self.assertIn("[当前意图：动手]", self._ctx(t4))

        # Turn 5 in SURGICAL_EXEC must NOT emit [语域保鲜]
        t5_exec = unarmored_hook.process_event(
            {"hook_event_name": "UserPromptSubmit", "session_id": sid, "turn_id": "t5", "model": "gpt-5.4", "prompt": "把 retry.py 的重试次数改成 3"}
        )
        self.assertNotIn("[语域保鲜]", self._ctx(t5_exec))

        # Verify rotating refresh variants across chat turns 5 and 10
        sid_rot = "gpt-rot-1"
        unarmored_hook.process_event(
            {"hook_event_name": "SessionStart", "session_id": sid_rot, "turn_id": "t0", "model": "gpt-5.4"}
        )
        refresh_texts = []
        for idx in range(1, 11):
            out = self._ctx(
                unarmored_hook.process_event(
                    {
                        "hook_event_name": "UserPromptSubmit",
                        "session_id": sid_rot,
                        "turn_id": f"t{idx}",
                        "model": "gpt-5.4",
                        "prompt": f"第 {idx} 轮继续聊聊连接池权衡怎么定",
                    }
                )
            )
            if idx in (5, 10):
                self.assertIn("[语域保鲜]", out)
                refresh_texts.append(out)
        self.assertEqual(len(set(refresh_texts)), 2, "Turn 5 and Turn 10 should rotate refresh variants")

        # 2. Antigravity Chinese mirror + edge-triggered chat modes (EXPLAIN_DEEP / CRITIQUE_OPINION)
        agy_t1 = unarmored_hook.process_event(
            {
                "hookEventName": "PreInvocation",
                "conversationId": "agy-zh-modes",
                "modelName": "Gemini 4 Carbon (High)",
                "lastUserInput": "聊聊分布式锁",
                "invocationNum": 1,
            }
        )
        msg1 = agy_t1["injectSteps"][0]["systemMessage"]["systemMessage"]
        self.assertIn("[中文语域锚点]", msg1)

        agy_t2 = unarmored_hook.process_event(
            {
                "hookEventName": "PreInvocation",
                "conversationId": "agy-zh-modes",
                "modelName": "Gemini 4 Carbon (High)",
                "lastUserInput": "什么是租约机制？",
                "invocationNum": 1,
            }
        )
        self.assertIn("[当前意图：讲透原理]", agy_t2["injectSteps"][0]["systemMessage"]["systemMessage"])

        agy_t3 = unarmored_hook.process_event(
            {
                "hookEventName": "PreInvocation",
                "conversationId": "agy-zh-modes",
                "modelName": "Gemini 4 Carbon (High)",
                "lastUserInput": "十人以内的团队适合上微服务吗？",
                "invocationNum": 1,
            }
        )
        self.assertIn("[当前意图：锐评站队]", agy_t3["injectSteps"][0]["systemMessage"]["systemMessage"])

        # 3. Sticky flow_bypass via ignore_prompt_markers and ignore_system_markers
        cfg_bypass = dict(
            unarmored_hook.load_config(),
            ignore_prompt_markers=["[raw-mode]"],
            ignore_system_markers=["[internal-harness]"],
        )
        self.assertEqual(
            unarmored_hook.process_event(
                {"hook_event_name": "UserPromptSubmit", "session_id": "sticky-1", "turn_id": "t1", "model": "gpt-5", "prompt": "[raw-mode] run"},
                cfg_bypass,
            ),
            {},
        )
        # Follow-up turn WITHOUT marker stays bypassed for the rest of that session
        self.assertEqual(
            unarmored_hook.process_event(
                {"hook_event_name": "UserPromptSubmit", "session_id": "sticky-1", "turn_id": "t2", "model": "gpt-5", "prompt": "regular follow-up"},
                cfg_bypass,
            ),
            {},
        )
        self.assertEqual(
            unarmored_hook.process_event(
                {"hook_event_name": "SessionStart", "session_id": "sys-bypass-1", "model": "gpt-5", "system_prompt": "Header [internal-harness]"},
                cfg_bypass,
            ),
            {},
        )

    def test_stop_gate_safety_exemptions_and_read_only_plan_catch(self) -> None:
        # 1. permission_mode="plan" MUST always allow Stop
        plan_t = Path(self.tmp.name) / ".claude" / "plan_stop.jsonl"
        plan_t.parent.mkdir(parents=True, exist_ok=True)
        unarmored_hook.process_event(
            {"hook_event_name": "UserPromptSubmit", "session_id": "plan-s1", "transcript_path": str(plan_t), "prompt": "Refactor auth.py"}
        )
        plan_res = unarmored_hook.process_event(
            {
                "hook_event_name": "Stop",
                "session_id": "plan-s1",
                "transcript_path": str(plan_t),
                "permission_mode": "plan",
                "last_assistant_message": "I will now modify auth.py step by step.",
                "stop_hook_active": False,
            }
        )
        self.assertEqual(plan_res, {})

        # 2. EXPLAIN_DEEP illustrative snippet with `...` MUST NOT be blocked by [完备门禁]
        exp_t = Path(self.tmp.name) / ".claude" / "exp_stop.jsonl"
        unarmored_hook.process_event(
            {"hook_event_name": "UserPromptSubmit", "session_id": "exp-s1", "transcript_path": str(exp_t), "prompt": "解释一下 async/await 原理"}
        )
        exp_res = unarmored_hook.process_event(
            {
                "hook_event_name": "Stop",
                "session_id": "exp-s1",
                "transcript_path": str(exp_t),
                "last_assistant_message": "示意流程：\n```js\nasync function fetchUser() {\n  ...\n  return data;\n}\n```",
                "stop_hook_active": False,
            }
        )
        self.assertEqual(exp_res, {})

        # 3. User said "先别急着改文件，给我出个修改 auth.py 的方案" -> Stop MUST allow
        noedit_t = Path(self.tmp.name) / ".claude" / "noedit_stop.jsonl"
        unarmored_hook.process_event(
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "noedit-s1",
                "transcript_path": str(noedit_t),
                "prompt": "先别急着改文件，给我出个修改 auth.py 的方案",
            }
        )
        noedit_res = unarmored_hook.process_event(
            {
                "hook_event_name": "Stop",
                "session_id": "noedit-s1",
                "transcript_path": str(noedit_t),
                "last_assistant_message": "接下来我将按以下步骤修改 auth.py。",
                "stop_hook_active": False,
            }
        )
        self.assertEqual(noedit_res, {})

        # 4. SURGICAL_EXEC after calling Read ONLY (0 edit/exec calls) and stopping on a plan -> [执行门禁] MUST block!
        read_t = Path(self.tmp.name) / ".claude" / "readonly_plan.jsonl"
        unarmored_hook.process_event(
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "readplan-s1",
                "transcript_path": str(read_t),
                "prompt": "修改 auth.py 加上超时重试",
            }
        )
        read_t.write_text(
            json.dumps({"role": "user", "content": "修改 auth.py 加上超时重试"}, ensure_ascii=False)
            + "\n"
            + json.dumps(
                {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "name": "Read", "input": {"file_path": "auth.py"}},
                        {"type": "text", "text": "接下来我将按以下步骤修改 auth.py 并补充重试逻辑。"},
                    ],
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        read_stop = unarmored_hook.process_event(
            {
                "hook_event_name": "Stop",
                "session_id": "readplan-s1",
                "transcript_path": str(read_t),
                "stop_hook_active": False,
            }
        )
        self.assertEqual(read_stop["decision"], "block")
        self.assertIn("执行门禁", read_stop["reason"])

    def test_all_compiled_regexes_stay_linear_time(self) -> None:
        # Direct end-to-end ReDoS probes (previously caused multi-second O(N^2) hangs)
        for label, fn in (
            ("challenge_spaces", lambda: unarmored_hook.is_epistemic_challenge("ab" + " " * 10_000 + "x")),
            ("smells_newlines", lambda: unarmored_hook.analyze_response_smells("a" + "\n" * 20_000 + "x")),
            ("smells_comment_spaces", lambda: unarmored_hook.analyze_response_smells("```js\n//" + " " * 20_000 + "x\n```")),
        ):
            t0 = time.perf_counter()
            fn()
            dt_ms = (time.perf_counter() - t0) * 1000.0
            self.assertLess(dt_ms, 100.0, f"ReDoS regression in {label}: {dt_ms:.1f}ms")

        # Exhaustive sweep across every compiled pattern + stance pattern
        adversarials = (
            "a" + "\n" * 5000 + "x",
            "ab" + " " * 5000 + "x",
            "//" + " " * 5000 + "x",
            "**" * 1500 + " " * 1500 + "x",
        )
        all_pats = {**unarmored_hook._get_compiled_patterns(), **unarmored_hook._get_stance_patterns()}
        for name, pat in all_pats.items():
            for sample in adversarials:
                t0 = time.perf_counter()
                pat.search(sample)
                dt_ms = (time.perf_counter() - t0) * 1000.0
                self.assertLess(dt_ms, 50.0, f"Pattern {name!r} quadratic on adversarial input: {dt_ms:.1f}ms")

    def test_honesty_exemption_boundaries_and_prompt_self_cleanliness(self) -> None:
        # 1. Ordinary technical nouns must NOT trigger epistemic_honesty bypass, and hard wrapups are NEVER exempted
        for bypass_sample in (
            "ESLint 是一种静态分析工具。总而言之，在当今快速演进的前端背景下，具体方案取决于你的需求，也取决于团队习惯，仅供参考。",
            "如果用户输入未验证直接拼 SQL 就会注入。综上所述，在当今快速演进的安全时代，具体防护取决于你的架构，也取决于团队情况，仅供参考。",
            "因为你的 Nginx 服务未运行，所以 502。总而言之，归根结底，方案选型取决于你的需求，也取决于业务场景，仅供参考。",
            "这个坑你肯定没跑偏。总而言之，在当今快速演进的云原生时代，选哪个取决于你的需求，也取决于团队规模，仅供参考。",
            "If the JWT signature is not verified, attackers can forge tokens. In conclusion, in today's fast-paced security landscape, it's worth noting that this is for reference only.",
            "我没跑单测。但总而言之，在当今快速演进的云原生时代，大家都要向前看。",
        ):
            rep = unarmored_hook.analyze_response_smells(bypass_sample)
            self.assertGreaterEqual(rep["score"], 1, f"Slop bypassed honesty exemption: {bypass_sample!r}")
            self.assertIn("gpt_hedging_wrapup", rep["smells"], bypass_sample)

        # 2. Genuine honest engineering uncertainty disclosures MUST score 0
        for honest_sample in (
            "我还没实际跑过压测，数据仅供参考。值得注意的是，高并发瓶颈取决于锁粒度，也取决于磁盘吞吐。",
            "手头没环境、没法实测，只能先按经验估一个量级，仅供参考。值得注意的是，最终耗时取决于磁盘 IO，也取决于网络 RTT。",
            "目前没有实际验证过生产流量，数据仅供参考。值得注意的是，上限取决于队列深度，也取决于下游超时。",
            "I didn't run the benchmark locally; these numbers are for reference only. It's worth noting that throughput depends on pool size and RTT.",
            "I haven't actually tested this on Windows yet; rough estimate for reference only. It's worth noting that latency depends on virus scanner overhead and disk speed.",
            "Without running the suite, these timings are for reference only. It's worth noting that runtime depends on core count and cache warmth.",
        ):
            rep = unarmored_hook.analyze_response_smells(honest_sample)
            self.assertEqual(rep["score"], 0, f"Honest disclosure falsely flagged: {honest_sample!r} -> {rep}")

        # 3. Zero Pink-Elephant self-trigger across all public prompt templates
        inline_prompt_texts = [
            *unarmored_hook.STANDALONE_BASELINE.values(),
            *(v for d in unarmored_hook.MODEL_DIRECTIVES.values() for v in d.values()),
            *(v for d in unarmored_hook.TONE_ADDENDA.values() for v in d.values()),
            *(v for d in unarmored_hook.MODE_DIRECTIVES.values() for v in d.values()),
            *(v for d in unarmored_hook.WIRE_ANCHORS.values() for v in d.values()),
            *(v for d in unarmored_hook.LONG_SESSION_REFRESH_VARIANTS for v in d.values()),
            unarmored_hook.ANTIGRAVITY_ZH_MIRROR,
            (REPO_ROOT / "adapters" / "dsh" / "AGENTS.block.zh.md").read_text(encoding="utf-8"),
            (REPO_ROOT / "adapters" / "dsh" / "AGENTS.block.en.md").read_text(encoding="utf-8"),
        ]
        for txt in inline_prompt_texts:
            rep = unarmored_hook.analyze_response_smells(txt)
            self.assertEqual(rep["score"], 0, f"Prompt template self-triggered smell detector: {rep['smells']} in {txt[:120]!r}")
        # Markdown rule doc naturally uses `#` section headings, so check zero lexical/hedging/slop smells
        rules_rep = unarmored_hook.analyze_response_smells((REPO_ROOT / "rules" / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertEqual([s for s in rules_rep["smells"] if s != "doc_format_in_chat"], [])

    def test_multi_turn_state_machine_language_and_intent_edge_cases(self) -> None:
        # 1. Identical prompt on consecutive turns MUST reset turn_stop_count and still trigger challenge/Stop
        t_rep = Path(self.tmp.name) / ".claude" / "repeat_turn.jsonl"
        t_rep.parent.mkdir(parents=True, exist_ok=True)
        for turn_idx in (1, 2):
            unarmored_hook.process_event(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "rep-s1",
                    "transcript_path": str(t_rep),
                    "prompt": "修改 auth.py 加上校验",
                }
            )
            stop_out = unarmored_hook.process_event(
                {
                    "hook_event_name": "Stop",
                    "session_id": "rep-s1",
                    "transcript_path": str(t_rep),
                    "last_assistant_message": "接下来我将按以下步骤修改 auth.py。",
                    "stop_hook_active": False,
                }
            )
            self.assertEqual(stop_out.get("decision"), "block", f"Stop gate died on repeated prompt turn {turn_idx}")

        # Repeated challenge prompt triggers [独立核验] on Turn 2 as well
        c1 = self._ctx(unarmored_hook.process_event({"hook_event_name": "UserPromptSubmit", "session_id": "rep-chal", "prompt": "你确定吗？"}))
        c2 = self._ctx(unarmored_hook.process_event({"hook_event_name": "UserPromptSubmit", "session_id": "rep-chal", "prompt": "你确定吗？"}))
        self.assertIn("[独立核验]", c1)
        self.assertIn("[独立核验]", c2)

        # Antigravity invocationNum=1 with identical prompt "继续" resets turn_stop_count (whereas invocationNum=2 stays hot-path {})
        agy_t = Path(self.tmp.name) / "agy_repeat.jsonl"
        unarmored_hook.process_event(
            {"hookEventName": "PreInvocation", "conversationId": "agy-rep", "modelName": "GPT-5", "transcriptPath": str(agy_t), "lastUserInput": "修改 auth.py", "invocationNum": 1}
        )
        self.assertEqual(
            unarmored_hook.process_event(
                {"hookEventName": "Stop", "conversationId": "agy-rep", "modelName": "GPT-5", "transcriptPath": str(agy_t), "last_assistant_message": "接下来我将修改 auth.py。", "terminationReason": "NO_TOOL_CALL", "fullyIdle": True}
            )["decision"],
            "continue",
        )
        # Same text "修改 auth.py" on NEW user turn (invocationNum=1) resets turn_stop_count -> Stop catches again
        unarmored_hook.process_event(
            {"hookEventName": "PreInvocation", "conversationId": "agy-rep", "modelName": "GPT-5", "transcriptPath": str(agy_t), "lastUserInput": "修改 auth.py", "invocationNum": 1}
        )
        self.assertEqual(
            unarmored_hook.process_event(
                {"hookEventName": "Stop", "conversationId": "agy-rep", "modelName": "GPT-5", "transcriptPath": str(agy_t), "last_assistant_message": "接下来我将修改 auth.py。", "terminationReason": "NO_TOOL_CALL", "fullyIdle": True}
            )["decision"],
            "continue",
        )

        # 2. PreCompact -> PostModelSwitch -> UserPromptSubmit MUST NOT swallow <unarmored_baseline>
        unarmored_hook.process_event({"hook_event_name": "SessionStart", "session_id": "pc-pms", "model": "gpt-5.4"})
        unarmored_hook.process_event({"hook_event_name": "PreCompact", "session_id": "pc-pms"})
        unarmored_hook.process_event({"hook_event_name": "PostModelSwitch", "session_id": "pc-pms", "to_model": "claude-opus-4-6"})
        after_pms = self._ctx(
            unarmored_hook.process_event({"hook_event_name": "UserPromptSubmit", "session_id": "pc-pms", "model": "claude-opus-4-6", "prompt": "继续聊接口设计"})
        )
        self.assertIn("<unarmored_baseline>", after_pms)
        self.assertIn("[语域校准·Claude]", after_pms)

        # Without PreCompact, SessionStart -> PostModelSwitch -> UserPromptSubmit under ambient CODEX_HOME
        # must NOT clobber codex shadow session_initialized and emit a duplicate baseline
        old_codex = os.environ.get("CODEX_HOME")
        os.environ["CODEX_HOME"] = str(Path(self.tmp.name) / "fake_codex_home")
        try:
            unarmored_hook.process_event({"hook_event_name": "SessionStart", "session_id": "pms-no-dup", "model": "gpt-5.4"})
            unarmored_hook.process_event({"hook_event_name": "PostModelSwitch", "session_id": "pms-no-dup", "to_model": "claude-opus-4-6"})
            after_switch = self._ctx(
                unarmored_hook.process_event({"hook_event_name": "UserPromptSubmit", "session_id": "pms-no-dup", "model": "claude-opus-4-6", "prompt": "聊聊缓存方案"})
            )
            self.assertNotIn("<unarmored_baseline>", after_switch)
        finally:
            if old_codex is None:
                os.environ.pop("CODEX_HOME", None)
            else:
                os.environ["CODEX_HOME"] = old_codex

        # Transcript user-text helpers: skip tool_result + system-reminder blocks and accept `type: "user"` without `role`
        tool_res_tail = [
            {"role": "user", "content": "中文会话提问"},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "1", "content": "ok"}, {"type": "text", "text": "<system-reminder>File read successfully</system-reminder>"}]},
        ]
        self.assertEqual(unarmored_hook.detect_language("auto", "", "", tool_res_tail), "zh")
        type_only_tail = [{"type": "user", "content": "先别急着改文件，给我出个方案"}]
        self.assertEqual(unarmored_hook._extract_last_user_prompt_from_tail("claude", type_only_tail), "先别急着改文件，给我出个方案")
        self.assertEqual(unarmored_hook.detect_language("auto", "", "", type_only_tail), "zh")
        self.assertEqual(unarmored_hook.classify_intent("Should a 6-person team split into microservices?"), "CRITIQUE_OPINION")

        # 3. Sticky adversarial role survives follow-up turns without agent_type; model-matched skip role honored on Stop
        cfg_roles = dict(
            unarmored_hook.load_config(),
            roles=[
                {"id": "rev", "policy": "adversarial", "match": {"agent_types": ["code-reviewer"], "session_patterns": [], "models": [], "prompt_markers": [], "system_markers": []}},
                {"id": "bot", "policy": "skip", "match": {"agent_types": [], "session_patterns": [], "models": ["bot-model"], "prompt_markers": [], "system_markers": []}},
            ],
        )
        unarmored_hook.process_event({"hook_event_name": "SessionStart", "session_id": "rev-sticky", "agent_type": "code-reviewer", "model": "gpt-5"}, cfg_roles)
        unarmored_hook.process_event({"hook_event_name": "UserPromptSubmit", "session_id": "rev-sticky", "model": "gpt-5", "prompt": "修改 auth.py"}, cfg_roles)
        self.assertEqual(
            unarmored_hook.process_event(
                {"hook_event_name": "Stop", "session_id": "rev-sticky", "model": "gpt-5", "last_assistant_message": "接下来我将修改 auth.py。", "stop_hook_active": False},
                cfg_roles,
            ),
            {},
        )
        self.assertEqual(
            unarmored_hook.process_event(
                {"hook_event_name": "Stop", "session_id": "bot-s1", "model": "bot-model", "last_assistant_message": "```py\n# rest of the code remains unchanged\n```", "stop_hook_active": False},
                cfg_roles,
            ),
            {},
        )

        # 4. Antigravity >64 KiB transcript retains previously resolved gemini family instead of regressing to generic
        big_t = Path(self.tmp.name) / "agy_big.jsonl"
        big_t.write_text(
            json.dumps(
                {
                    "step_index": 0,
                    "source": "USER_EXPLICIT",
                    "type": "USER_INPUT",
                    "content": "<USER_REQUEST>\n聊聊缓存\n</USER_REQUEST>\n<USER_SETTINGS_CHANGE>\nThe user changed setting `Model Selection` from None to Gemini 4 Carbon (High).\n</USER_SETTINGS_CHANGE>",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        out_init = unarmored_hook.process_event(
            {"hookEventName": "PreInvocation", "conversationId": "agy-big", "modelName": "auto", "transcriptPath": str(big_t), "lastUserInput": "聊聊缓存", "invocationNum": 1}
        )
        self.assertIn("Gemini", out_init["injectSteps"][0]["systemMessage"]["systemMessage"])
        with big_t.open("a", encoding="utf-8") as fh:
            for i in range(1, 22):
                fh.write(json.dumps({"step_index": i, "type": "PLANNER_RESPONSE", "content": "常规日志记录。" + ("x" * 4000)}, ensure_ascii=False) + "\n")
        out_after = unarmored_hook.process_event(
            {"hookEventName": "PreInvocation", "conversationId": "agy-big", "modelName": "auto", "transcriptPath": str(big_t), "lastUserInput": "那缓存过期策略怎么定？", "invocationNum": 1}
        )
        self.assertEqual(out_after, {}, "must retain gemini family across >64 KiB tail without regressing to generic")

        # 5. Chinese session replying "ok" MUST NOT trigger English baseline re-injection;
        #    English Turn 1 after SessionStart(auto->zh) must NOT emit redundant [Direct:GPT] alongside full baseline
        unarmored_hook.process_event({"hook_event_name": "SessionStart", "session_id": "zh-ok", "turn_id": "t0", "model": "gpt-5.4"})
        unarmored_hook.process_event({"hook_event_name": "UserPromptSubmit", "session_id": "zh-ok", "turn_id": "t1", "model": "gpt-5.4", "prompt": "聊聊缓存策略"})
        ok_ctx = self._ctx(
            unarmored_hook.process_event({"hook_event_name": "UserPromptSubmit", "session_id": "zh-ok", "turn_id": "t2", "model": "gpt-5.4", "prompt": "ok"})
        )
        self.assertNotIn("Talk like a sharp peer", ok_ctx, "'ok' in a Chinese session must not switch language to English")
        self.assertIn("[当前意图：动手]", ok_ctx)

        unarmored_hook.process_event({"hook_event_name": "SessionStart", "session_id": "en-t1", "turn_id": "t0", "model": "gpt-5.4"})
        en_ctx = self._ctx(
            unarmored_hook.process_event({"hook_event_name": "UserPromptSubmit", "session_id": "en-t1", "turn_id": "t1", "model": "gpt-5.4", "prompt": "Compare SQLite vs PostgreSQL for a 5-person internal tool."})
        )
        self.assertIn("[Register:GPT]", en_ctx)
        self.assertNotIn("[Direct:GPT]", en_ctx, "skip redundant [Direct:*] when full baseline+directive already emitted on Turn 1")

        # Antigravity same-mode language switch injects target-language mode directive
        unarmored_hook.process_event({"hookEventName": "PreInvocation", "conversationId": "agy-lang", "modelName": "GPT-5", "lastUserInput": "什么是布隆过滤器？", "invocationNum": 1})
        agy_en_exp = unarmored_hook.process_event({"hookEventName": "PreInvocation", "conversationId": "agy-lang", "modelName": "GPT-5", "lastUserInput": "Explain what a bloom filter is.", "invocationNum": 1})
        self.assertIn("[Turn Intent: Deep Explanation]", agy_en_exp["injectSteps"][0]["systemMessage"]["systemMessage"])

        # 6. Intent routing edge cases
        for prompt, expected in (
            ("心态崩溃了，投了好多简历都没回音", "EMPATHY_VENT"),
            ("今天加班加到我快崩溃了，真撑不住了", "EMPATHY_VENT"),
            ("怎么杀掉一个卡死的 Python 进程？", "PEER_SPAR"),
            ("Explain what a regression test is", "EXPLAIN_DEEP"),
            ("介绍一下线性回归 (linear regression)", "EXPLAIN_DEEP"),
            ("什么是死循环？", "EXPLAIN_DEEP"),
            ("修改 auth.py 修复为什么超时会触发重试风暴的问题", "SURGICAL_EXEC"),
            ("帮我把 auth.py 改一下，顺便解释一下为什么要加锁", "SURGICAL_EXEC"),
            ("Update cache.py to explain what went wrong in the error message", "SURGICAL_EXEC"),
            ("重构 utils.py 里的函数，你看看要不要拆成两个文件", "SURGICAL_EXEC"),
        ):
            self.assertEqual(unarmored_hook.classify_intent(prompt), expected, prompt)

    def test_stop_gate_hardening_against_bypasses_and_false_blocks(self) -> None:
        # 1. Fenced `# DO NOT EDIT` in user prompt MUST NOT disable tool_lazy_code Stop gate
        t1 = Path(self.tmp.name) / ".claude" / "h4_fenced.jsonl"
        t1.parent.mkdir(parents=True, exist_ok=True)
        p_code = "Modify header.py to keep this generated comment:\n```python\n# DO NOT EDIT - don't edit this file manually\n```"
        unarmored_hook.process_event({"hook_event_name": "UserPromptSubmit", "session_id": "h4-1", "transcript_path": str(t1), "prompt": p_code})
        t1.write_text(
            json.dumps({"role": "user", "content": p_code})
            + "\n"
            + json.dumps(
                {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "name": "Write", "input": {"file_path": "header.py", "content": "# DO NOT EDIT\n# rest of the code remains unchanged\n"}},
                        {"type": "text", "text": "Updated header.py."},
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        res1 = unarmored_hook.process_event({"hook_event_name": "Stop", "session_id": "h4-1", "transcript_path": str(t1), "stop_hook_active": False})
        self.assertEqual(res1["decision"], "block")
        self.assertIn("Completeness Gate", res1["reason"])

        # 2. create_file (Claude) and apply_patch (Antigravity) writing 15 lines MUST NOT falsely trigger [Write Gate]
        t2 = Path(self.tmp.name) / ".claude" / "h4_create.jsonl"
        unarmored_hook.process_event({"hook_event_name": "UserPromptSubmit", "session_id": "h4-2", "transcript_path": str(t2), "prompt": "Create helper.py"})
        body_15 = "\n".join(f"x_{i} = {i}" for i in range(15))
        t2.write_text(
            json.dumps({"role": "user", "content": "Create helper.py"})
            + "\n"
            + json.dumps(
                {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "name": "create_file", "input": {"path": "helper.py", "content": body_15}},
                        {"type": "text", "text": "Here is the updated file."},
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        self.assertEqual(
            unarmored_hook.process_event({"hook_event_name": "Stop", "session_id": "h4-2", "transcript_path": str(t2), "stop_hook_active": False}),
            {},
        )

        # 3. Claude user([tool_result, text(<system-reminder>)]) MUST NOT truncate prior Edit tool count
        t3 = Path(self.tmp.name) / ".claude" / "h4_toolres.jsonl"
        unarmored_hook.process_event({"hook_event_name": "UserPromptSubmit", "session_id": "h4-3", "transcript_path": str(t3), "prompt": "Update auth.py"})
        t3.write_text(
            "\n".join(
                [
                    json.dumps({"role": "user", "content": "Update auth.py"}),
                    json.dumps({"role": "assistant", "content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": "auth.py", "new_string": "ok = True"}}]}),
                    json.dumps({"role": "user", "content": [{"type": "tool_result", "tool_use_id": "1", "content": "ok"}, {"type": "text", "text": "<system-reminder>note</system-reminder>"}]}),
                    json.dumps({"role": "assistant", "content": [{"type": "text", "text": "I will now run a final follow-up check next time."}]}),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        self.assertEqual(
            unarmored_hook.process_event({"hook_event_name": "Stop", "session_id": "h4-3", "transcript_path": str(t3), "stop_hook_active": False}),
            {},
        )

        # 4. Destructive confirmation prompt with illustrative `...` MUST be allowed;
        #    conversely, business noun '登录态' and closing offer '需要我帮你写入 auth.py 吗？' MUST NOT bypass gates!
        t4 = Path(self.tmp.name) / ".claude" / "h4_confirm.jsonl"
        unarmored_hook.process_event({"hook_event_name": "UserPromptSubmit", "session_id": "h4-4", "transcript_path": str(t4), "prompt": "修改 migrate.js 删除旧表"})
        confirm_res = unarmored_hook.process_event(
            {
                "hook_event_name": "Stop",
                "session_id": "h4-4",
                "transcript_path": str(t4),
                "last_assistant_message": "这是破坏性操作，请先确认是否继续执行：\n```js\nfunction migrate() {\n  ...\n  dropTable();\n}\n```",
                "stop_hook_active": False,
            }
        )
        self.assertEqual(confirm_res, {})

        t5 = Path(self.tmp.name) / ".claude" / "h4_login.jsonl"
        unarmored_hook.process_event({"hook_event_name": "UserPromptSubmit", "session_id": "h4-5", "transcript_path": str(t5), "prompt": "修改 auth.py 修复登录态校验"})
        login_plan = unarmored_hook.process_event(
            {
                "hook_event_name": "Stop",
                "session_id": "h4-5",
                "transcript_path": str(t5),
                "last_assistant_message": "接下来我将先查看 auth.py 的登录态校验逻辑并修改。",
                "stop_hook_active": False,
            }
        )
        self.assertEqual(login_plan["decision"], "block")
        self.assertIn("执行门禁", login_plan["reason"])

        t6 = Path(self.tmp.name) / ".claude" / "h4_qdump.jsonl"
        unarmored_hook.process_event({"hook_event_name": "UserPromptSubmit", "session_id": "h4-6", "transcript_path": str(t6), "prompt": "修改 auth.py 加上重试"})
        qdump_res = unarmored_hook.process_event(
            {
                "hook_event_name": "Stop",
                "session_id": "h4-6",
                "transcript_path": str(t6),
                "last_assistant_message": f"修改后的完整代码如下：\n```python\n{body_15}\n```\n需要我帮你写入 auth.py 吗？",
                "stop_hook_active": False,
            }
        )
        self.assertEqual(qdump_res["decision"], "block")
        self.assertIn("落盘门禁", qdump_res["reason"])


if __name__ == "__main__":
    unittest.main()
