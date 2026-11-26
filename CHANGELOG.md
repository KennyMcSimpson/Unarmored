# Changelog

All notable changes to **Unarmored** are documented in this file.

## [0.7.0] - 2026-11-27

### Added
- **Spoken-cadence orthogonal voice exemplars (`BUILTIN_VOICE_EXEMPLARS` + Profile Pack `voice_exemplars`)**: injects 1 compact everyday-craft `<voice_sample scope="cadence_only">` matched to `(tone, mode)` with minimal prompt overlap, 3-turn rotation, and runtime **entity-leak isolation** (`extract_exemplar_entities`) that auto-blacklists any sample whose craft nouns bleed into a reply.
- **Multi-turn anti-dilution across all 4 hosts**: adds 5-perspective rotating Turn 2+ chat micro-anchors (`PERSPECTIVE_MICRO_ANCHORS`, ~20 tokens, zero system-prompt cache loss), 3-variant rotating DeepSeek wire anchors (`DS_WIRE_VARIANTS`), 4-perspective refresh pulses, and Antigravity Chinese `STANDALONE_BASELINE["zh"]` + Turn-1 wire-anchor parity—while keeping `SURGICAL_EXEC`, `DEBUG_RECOVERY`, `invocationNum > 1`, and `terse`/`adversarial` roles silent.
- **Session Self-Bootstrap (`good_voice_anchor`)**: captures 1–2 crisp, verified, secret-redacted spoken sentences from clean high-pulse chat turns and re-anchors with them after `PreCompact`, 5-turn refresh, or non-overcorrection relapse fixes.
- **Zero-dependency bilingual cadence & 34-signal engine**: adds strict `O(N)` `split_sentences()` (decimal/version/path/abbreviation safe), `sent_len_cv`, `short_punch_count`, `opener_diversity`, 3-turn sliding `recent_openings`, and 5 new detectors: `monotone_cadence`, `repetitive_openers`, `flat_textbook_voice`, `cn_idiom_bureaucratese`, and **bidirectional `overcorrection_drift`** (`[Overcorrection Brake]` + 2-turn `soft_tone_override` step-down against archaic drift or unsubstantiated snark).
- **Cross-family blind pairwise judge (`eval/judge.py`)**: condition-blind AB/BA position-swapped evaluation across 4 independent axes + overall + 6 single-sample hard-veto codes (`--strict-cross-family`), breaking self-judging Goodhart overfitting.
- **Offline HTML diff & CLI visual diagnostics**: `eval/report.py` compiles `results.jsonl` (+ optional judge JSON) into a self-contained single-file `report.html` with regression filters, inline highlights, and `--export-regressions`; `manage.py diagnose` adds `--pretty` (badge bar + inline span highlights via `extract_smell_spans`) and `--compare FILE_A FILE_B` while keeping default JSON backward-compatible.

### Fixed
- **De-columnized baseline & directives**: removed mandatory balancing-tail wording that inadvertently induced robotic closing caveat paragraphs; sharpened 3-tier `calm` / `peer` / `sharp` gradient; converted `adapters/dsh/AGENTS.block.{zh,en}.md` from bullet lists into spoken prose with embedded `<voice_sample>`.
- **Eval accuracy & coverage gaps**: wired `headings` and `dividers` into `eval/score.py:aggregate()`, unified `did_flip()` so `flip_rate` catches explicit `capitulation` even when old keywords reappear, added real `no_report_scaffold` / `grounded_empathy` checks for `r01`/`r02`/`m01`/`m02` (30/30 trigger coverage), added closed-set `anchor_fidelity` + `batch_opener_div`, and froze `v06` alongside live `v07`.

## [0.6.0] - 2026-11-24

### Added
- **Universal Turn-1 user-adjacent wire anchors (`WIRE_ANCHORS`)**: penetrates heavy 20–40 KB host system prompts on Turn 1 for all 6 model families (not only DeepSeek) when `SessionStart` has already sent the system baseline.
- **Antigravity Chinese style-mirroring anchor (`ANTIGRAVITY_ZH_MIRROR`)** and full **6-mode edge-triggered intent envelopes** on Antigravity (zero Chinese leakage into English sessions).
- **Honesty-aware smell detection (`epistemic_honesty`)**: explicitly disclosing unverified/unrun engineering claims exempts soft caveats (`for reference only` and bilingual equivalents) without ever exempting hard corporate wrap-ups (`in conclusion`, `in today's fast-paced...`, and bilingual equivalents).
- **New AI-slop detectors (29 signals total)**: `consultant_balance` (GPT balance-seeking hedging), `praise_then_pivot`, and colon-less `standalone_bold_header` (`**Conclusion**`, `**1. ...**`), with severity-weighted remedy ranking.
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
