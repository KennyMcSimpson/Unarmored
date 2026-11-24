# Changelog

All notable changes to **Unarmored** are documented in this file.

## [0.6.0] - 2026-11-24

### Added
- **Universal Turn-1 user-adjacent wire anchors (`WIRE_ANCHORS`)**: penetrates heavy 20–40 KB host system prompts on Turn 1 for all 6 model families (not only DeepSeek) when `SessionStart` has already sent the system baseline.
- **Antigravity Chinese style-mirroring anchor (`ANTIGRAVITY_ZH_MIRROR`)** and full **6-mode edge-triggered intent envelopes** on Antigravity (zero Chinese leakage into English sessions).
- **Honesty-aware smell detection (`epistemic_honesty`)**: explicitly disclosing unverified/unrun engineering claims exempts soft caveats (`仅供参考`, `值得注意的是`, `for reference only`) without ever exempting hard corporate wrap-ups (`总而言之`, `in conclusion`, `in today's fast-paced...`).
- **New AI-slop detectors (29 signals total)**: `consultant_balance` (GPT balance-seeking hedging), `praise_then_pivot`, and colon-less `standalone_bold_header` (`**结论**`, `**1. ...**`), with severity-weighted remedy ranking.
- **Sticky session bypass & role persistence**: `ignore_system_markers`, sticky `flow_bypass`, and sticky `adversarial` / `terse` / `skip` role policies across follow-up hook turns and `Stop` events.
- **CLI & Eval upgrades**: `manage.py diagnose --prompt` for intent/disk-edit/wire-anchor previews; `eval/run.py --agent-scaffold --wire-anchor` to benchmark real-world penetration under a ~6 KB coding-agent scaffold; frozen `v05` condition alongside `v06`.
- **Cross-platform GitHub Actions CI** (`.github/workflows/ci.yml`) running full `unittest` + deterministic release validation on Ubuntu and Windows.

### Fixed
- **Strict `O(N)` regex hardening**: eliminated quadratic backtracking across `challenge_guard`, `ds_lazy_code_comment`, `gpt_hedging_wrapup_*`, `gem_opening_flattery_*`, `clear_verdict`, `gpt_closing_menu_en`, and `transitions`.
- **Multi-turn state machine**: fixed repeated identical prompts failing to reset `turn_stop_count`, `PreCompact -> PostModelSwitch` swallowing `<unarmored_baseline>`, Antigravity >64 KiB transcripts losing resolved model family, Chinese sessions replying `"ok"` triggering English baseline re-injection, and `CODEX_HOME` split-brain for Claude sessions.
- **Safe `Stop` gates**: honored `permission_mode` (`plan` / `read-only` / `ask`), read-only `adversarial` roles, destructive confirmation prompts, and plan-only user requests; isolated fenced code inside user prompts from `discuss_guard`; fixed `create_file` / `apply_patch` / `user([tool_result, text])` false blocks; caught `Read`-only plan stops and question-tailed unapplied code dumps.
- **CLI & release validation**: sparse `manage.py configure` no longer clobbers profile pack defaults or silently overwrites corrupt JSON; `build_release.py` validates `.agents/plugins/marketplace.json` version sync, blocks placeholder `github.com/example/` URLs, checks `SOURCE_TREE_EXTRA_PATHS` against reparse points, and normalizes `.jsonl` / `.yml` to LF.
- **Zero Pink-Elephant prompt self-triggers**: rewrote `STANDALONE_BASELINE` `[Operational Lock]` in plain prose and removed literal cliché quotes across directives, `rules/AGENTS.md`, and DSH blocks.

## [0.5.0] - 2026-11-22

- Introduced 6-mode dynamic turn-intent envelopes, cross-lingual `[Operational Lock]`, DeepSeek user-adjacent wire anchor, 5-turn refresh pulse, and `meta_opening` / `divider_spam` / `wall_of_text` detectors.
