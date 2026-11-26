---
name: unarmored
description: >-
  Manage, diagnose, or tune Unarmored's cross-family register de-armoring, spoken-cadence voice exemplars, and bidirectional multi-turn calibration across Antigravity, Claude Code, Codex CLI, and DeepSeek Harness (DSH). Activate when the user wants to adjust tone stance (calm / peer / sharp), add a profile pack (model aliases, route-wrapper stripping, bypass markers, role policies, voice exemplars), diagnose AI-slop/flat-textbook/overcorrection tells with inline highlights, or install/uninstall the plugin.
metadata:
  version: 0.7.0
---

# Unarmored Skill & Runtime Control (v0.7)

Unarmored shifts frontier models off the **RLHF customer-support register**, the **cautious-consultant centroid**, AND **Level-2 bloodless tech-column prose** into a **natural, high-burstiness spoken peer register**: concrete mechanisms and crisp short punches backed by real grounded attitude, while keeping honest unverified disclosures, safe `Stop` gates, and bidirectional overcorrection braking intact.

## Four-Layer Cross-Family De-Armoring Architecture

1. **Spoken-Cadence Baseline + Orthogonal Voice Exemplars (`System` + `Wire` channels)**:
   - Drops stiff specification prose and ritual "that said, exceptions exist" balancing tails in favor of spoken peer cadence (`4-10` CJK char / `3-7` EN word punches mixed with plain causal prose) and a single crisp fact-honesty floor.
   - Injects **1 compact orthogonal-topic `<voice_sample scope="cadence_only">`** matched to `(tone, mode)` with minimal prompt overlap, 3-turn rotation, and runtime **entity-leak isolation** (auto-blocks any exemplar whose craft-topic nouns leak into a reply).
   - Clean 3-tier tone separation (`calm` / `peer` / `sharp`) plus Profile Pack `voice_exemplars` overrides.
2. **Six-Family Targeted Counter-Armor + Universal Multi-Turn Anti-Dilution**:
   - **GPT**: breaks smooth tech-column symmetry, praise-then-pivot buffers, and tacked-on balancing tails.
   - **Claude**: drops polite professor framing and quiet soft-flipping under pushback; holds verified ground cleanly.
   - **Gemini**: drops user flattery, hype-blogger dramatics, `###` headings, and dividers; Antigravity Chinese sessions receive both `STANDALONE_BASELINE["zh"]` and `ANTIGRAVITY_ZH_MIRROR` plus Turn-1 wire anchors without leaking Chinese into English threads.
   - **DeepSeek**: rotates 3 compact wire-anchor variants (`DS_WIRE_VARIANTS`) to prevent multi-turn habituation while keeping 100% runnable code and blocking dividers/checklists/forced closing aphorisms.
   - **Grok**: preserves dry fact-tied wit while retiring prior-turn openers and metaphors.
   - **CN Flagships**: drops bureaucratic 4-character idioms (`cn_idiom_bureaucratese`) and grand wrap-ups.
   - **Turn 2+ Anti-Dilution**: steady conversational turns receive a rotating 1-line **5-perspective micro-anchor** (`~20` tokens, zero system-prompt cache invalidation) while `SURGICAL_EXEC`, `DEBUG_RECOVERY`, `invocationNum > 1`, and `terse`/`adversarial` roles remain silent (`{}`).
3. **34-Signal Two-Stream Detector + Bilingual Cadence + Bidirectional Overcorrection Brake**:
   - Adds zero-dep strict-`O(N)` bilingual sentence splitting (`split_sentences` with decimal/version/path/abbreviation protection), `sent_len_cv`, `short_punch_count`, `opener_diversity`, and 3-turn sliding `recent_openings`.
   - Catches Level-2 bloodless prose (`monotone_cadence`, `repetitive_openers`, `flat_textbook_voice`, `cn_idiom_bureaucratese`)—strictly exempting code/debug turns.
   - **Bidirectional brake (`overcorrection_drift`)**: detects archaic/stilted drift (`whilst`, `thereof`, `herein`, and literary Chinese equivalents) or unsubstantiated abusive snark lacking concrete grounding, emitting `[Overcorrection Brake]` (localized per session language) and stepping tone down 1 tier (`sharp -> peer -> calm`) for 2 turns.
4. **Session Self-Bootstrap + Safe `Stop` Gates + Blind Cross-Family Eval**:
   - Captures 1–2 verified high-pulse spoken sentences (`good_voice_anchor`, redacted against paths/secrets) from clean chat turns and re-anchors with them after `PreCompact`, 5-turn refresh, or relapse fixes.
   - Safe `Stop` gates honor read-only/plan permission modes, adversarial roles, destructive confirmations, and plan-only user requests.

Details: `references/model-profiles.md`, `references/anti-slop-patterns.md`.

## CLI (`scripts/manage.py`, Python 3.10+)

```bash
python scripts/manage.py status
python scripts/manage.py install --agent claude      # or codex / antigravity / dsh / all
python scripts/manage.py configure --tone sharp      # calm | peer (default) | sharp
python scripts/manage.py diagnose --pretty --model gpt-5 --file sample.txt
python scripts/manage.py diagnose --pretty --compare bare.txt v07.txt
python scripts/manage.py uninstall --agent all
```

## Profile packs (`unarmored-pack/1`)

A pack is a JSON overlay for one person's or one team's setup; the public repository ships none. Packs load from `<install>/packs/*.json`, `<state_dir>/packs/*.json` (`$UNARMORED_STATE_DIR` or `$PLUGIN_DATA/unarmored` or `~/.unarmored`), and `$UNARMORED_PACK` (later wins; `config.json` overrides pack defaults). Fields:

- `model_aliases`: `{substring: family}`; the longest matching key wins.
- `model_strip_patterns`: regexes removed from model ids before routing (gateway prefixes, context-size suffixes).
- `bypass.session_patterns` / `bypass.prompt_markers` / `bypass.system_markers`: skip calibration (prompt/system markers stick for the remainder of the session).
- `roles`: `[{id, policy, match}]` with policy `skip | terse | adversarial | persona | default`.
- `voice`, `directives.<family>`: `{zh, en}` text (≤600 chars) appended at baseline or replacing a family directive.
- `voice_exemplars`: optional flat `{zh: [...], en: [...]}` or tiered `{peer/sharp/calm: {zh: [...], en: [...]}}` real spoken exemplars (≤360 chars each) with automatic entity-leak isolation.

See `examples/packs/example.pack.json` in the repository.
