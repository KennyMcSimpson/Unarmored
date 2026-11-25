---
name: unarmored
description: >-
  Manage, diagnose, or tune Unarmored's cross-family register de-armoring, grounded peer voice, and edge-triggered multi-turn calibration across Antigravity, Claude Code, Codex CLI, and DeepSeek Harness (DSH). Activate when the user wants to adjust tone stance (calm / peer / sharp), add a profile pack (model aliases, route-wrapper stripping, bypass markers, role policies), diagnose AI-slop/formatting tells or preview prompt routing, or install/uninstall the plugin.
metadata:
  version: 0.6.0
---

# Unarmored Skill & Runtime Control (v0.6)

Unarmored shifts frontier models off both the **RLHF customer-support register** and the **cautious-consultant centroid** into a **sharp, grounded peer-expert register**: crystal-clear explanations and concrete mechanisms, carried with honest reaction tied strictly to the facts—zero roleplay, zero consultant fence-sitting, zero doc-in-chat divider spam, and zero wall-of-text bricks, while keeping honest unverified disclosures intact.

## Four-Layer Cross-Family De-Armoring Architecture

1. **Bounded Register Escape + Prose Cross-Lingual Lock (`System` channel)**:
   - Collapses social distance with an explicit face-saving waiver (zero diplomatic cushioning), written **in** the peer voice it asks for (style mirroring) paired with a plain-prose English `[Operational Lock]` (zero self-contradictory bullet lists inside the prompt) that preserves honest reporting of unverified gaps.
   - Separates baseline cadence cleanly from the tone dial (`calm` / `peer` / `sharp`) so `calm` never fights baseline framing.
   - Stays bounded to the style/register layer ONLY—never touching safety/harm refusal guardrails.
2. **Six-Family Targeted Counter-Armor + Universal Turn-1 Wire Anchors**:
   - **GPT**: breaks cautious-consultant hedging (praise-then-pivot, "both have merits / find a balance") and single-brick collapse; keeps concrete risks, unverified gaps, and flip thresholds inline.
   - **DeepSeek**: preserves native candor and 100% runnable code while clamping tutorial-deck `---` dividers, meta-openers, numbered checklists, and closing offers—reinforced on every chat turn by a compact user-adjacent wire anchor (`[DS Direct]` and its localized Chinese counterpart).
   - **Claude**: pairs candid peer prose with an English anti-FlipFlop & hard-stop tail; eliminates validation sandwiches and lecturing.
   - **Gemini**: redirects expressive energy from user-flattery/exclamation/bold spam into vivid causal analogies, while clamping `###` headings, dividers, and closing offers; Antigravity Chinese sessions automatically receive a dedicated Chinese style-mirroring anchor (`ANTIGRAVITY_ZH_MIRROR`) without leaking Chinese into English threads.
   - **Grok**: preserves dry bite tied strictly to facts while eliminating forced memes and cross-turn metaphor recycling.
   - **CN Flagships**: breaks civil-service report scaffolding into cohesive conversational paragraphs.
   - **Turn-1 Penetration across heavy agent prompts**: when `SessionStart` has already sent the system baseline (buried under 20–40 KB host prompts), Turn 1 emits a compact 1-line family wire anchor right next to the user turn for **all** model families—not just DeepSeek.
3. **Edge-Triggered Six-Mode Turn-Intent Envelopes (`Wire` / `PreInvocation` / `UserPromptSubmit`)**:
   - Routes each turn to `EXPLAIN_DEEP`, `CRITIQUE_OPINION`, `EMPATHY_VENT`, `PEER_SPAR`, `SURGICAL_EXEC`, or `DEBUG_RECOVERY` across **Claude Code, Codex CLI, and Antigravity**.
   - **Zero context bloat**: emits mode directives on Turn 1, mode transitions, explicit expressive/debug turns, or re-anchors—staying silent on steady-state follow-up turns instead of repeating identical boilerplate every round.
   - **Safe `Stop` gates**: honors read-only/plan permission modes (`plan`, `read-only`, `readonly`, `ask`), read-only `adversarial` reviewer roles, and explicit plan-only requests (`plan only` and localized non-edit guards), scopes prose code-ellipsis checks to authorized edit/debug turns, and catches `Read`-only plan stops.
4. **29-Signal Honesty-Aware Relapse Fix + Rotating 5-Turn Anti-Decay Pulse**:
   - Two-stream detector (`prose_stream` vs `code_stream`) tracks 29 lexical, structural, and formatting signals—adding `consultant_balance`, `praise_then_pivot`, and colon-less `standalone_bold_header` detection while exempting honest unverified engineering statements (`untested`, `code-reading only`, and bilingual equivalents) from false-positive caveat penalties.
   - Ranks relapse remedies by severity weight descending so critical issues are never evicted by minor hints.
   - Every 5 conversational turns (never during `SURGICAL_EXEC` / `DEBUG_RECOVERY`), emits a rotating compact refresh pulse.

Details: `references/model-profiles.md`, `references/anti-slop-patterns.md`.

## CLI (`scripts/manage.py`, Python 3.10+)

```bash
python scripts/manage.py status
python scripts/manage.py install --agent claude      # or codex / antigravity / dsh / all
python scripts/manage.py configure --tone sharp      # calm | peer (default) | sharp
python scripts/manage.py diagnose --model gpt-5 --prompt "Should a 6-person team split into microservices?" --text "Both monoliths and microservices are mature choices. Ultimately, the right choice comes down to your team."
python scripts/manage.py uninstall --agent all
```

## Profile packs (`unarmored-pack/1`)

A pack is a JSON overlay for one person's or one team's setup; the public repository ships none. Packs load from `<install>/packs/*.json`, `<state_dir>/packs/*.json` (`$UNARMORED_STATE_DIR` or `$PLUGIN_DATA/unarmored` or `~/.unarmored`), and `$UNARMORED_PACK` (later wins; `config.json` overrides pack defaults). Fields:

- `model_aliases`: `{substring: family}`; the longest matching key wins.
- `model_strip_patterns`: regexes removed from model ids before routing (gateway prefixes, context-size suffixes).
- `bypass.session_patterns` / `bypass.prompt_markers` / `bypass.system_markers`: skip calibration (prompt/system markers stick for the remainder of the session).
- `roles`: `[{id, policy, match}]` with policy `skip | terse | adversarial | persona | default`, matched on `agent_types`, `session_patterns`, `models`, `prompt_markers`, `system_markers`.
- `voice`, `directives.<family>`: `{zh, en}` text (≤600 chars) appended at baseline or replacing a family directive.

See `examples/packs/example.pack.json` in the repository.
