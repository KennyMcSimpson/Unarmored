# Six-Family Armor Anatomy & Cross-Family De-Armoring Profiles (v0.7)

Real-model A/B comparisons show that RLHF post-training traps models in **three** layers, not one:
1. **Level-1 Customer-support / report armor**: disclaimers, flattery, `---` dividers, `#` headers, bullet decks, and closing waiter offers.
2. **Level-2 Bloodless op-ed / tech-column centroid**: zero explicit clichés, yet uniform medium-long sentences (`sent_len_cv < 0.24`), zero short punches, ritual balancing tails, and zero human warmth—diluting Turn-1 rules within 2–3 turns via autoregressive self-conditioning.
3. **Overcorrection drift**: pushing too hard away from RLHF defaults can tip models into archaic formalism (`whilst`, `thereof`, and literary Chinese equivalents) or unsubstantiated abusive snark.

Unarmored v0.7 addresses all three with **spoken-cadence baseline + orthogonal `<voice_sample scope="cadence_only">` exemplars + rotating Turn 2+ micro-anchors + 34-signal detection + bidirectional overcorrection braking**.

## 1. GPT Family (`gpt-*`, `o1/o3/o4`, `codex`)
- **Armor**: Smooth tech-column prose, symmetrical aphorisms, praise-then-pivot buffers, ritual "that said, exceptions exist" balancing tails, and single-brick collapse.
- **Counter-Armor**: Written in crisp spoken cadence; explicitly drops balancing tails and symmetrical aphorisms while pairing Turn-1 `[Direct:GPT]` (localized per session language) wire anchors with an orthogonal voice sample and Turn 2+ rotating micro-anchors.

## 2. DeepSeek Family (`deepseek-*`, `ds-r1`, `ds-v*`)
- **Armor**: Strong native candor, but tutorial-deck reflexes (`---` dividers, meta-openers, 1-2-3-4 checklists, forced closing aphorisms) and fast system-prompt forgetting across `<think>`.
- **Counter-Armor**: Rotates 3 compact wire-anchor variants (`DS_WIRE_VARIANTS`) right next to the user turn to eliminate multi-turn habituation, while preserving 100% runnable code and tool execution.

## 3. Claude Family (`claude-*`, `opus`, `sonnet`, `haiku`)
- **Armor**: Polite professor framing, implicit memo outlines, validation sandwiches, and quiet soft-flipping under authority pushback.
- **Counter-Armor**: Spoken peer prose (eliminating awkward bilingual splices), strong anti-FlipFlop grounding, and short `<voice_sample>` cadence anchoring.

## 4. Gemini Family (`gemini-*`, `carbon`, `argon`, `gemma`)
- **Armor**: Ego-flattering openers, hype-blogger dramatics, exclamation/inline-bold spam, `###` headings, and English-rule translation drift on Antigravity Chinese sessions.
- **Counter-Armor**: Channels energy into everyday analogies and period-ended short punches; Antigravity Chinese sessions now receive `STANDALONE_BASELINE["zh"]`, `ANTIGRAVITY_ZH_MIRROR`, Turn-1 wire anchors, and orthogonal samples while keeping English sessions 100% English.

## 5. Grok Family (`grok-*`, `xai/*`)
- **Armor**: Forced meme/stand-up banter and cross-turn opener/metaphor latching.
- **Counter-Armor**: Keeps dry fact-tied wit, strips forced memes, and pairs with the 3-turn `recent_openings` window to catch opener recycling.

## 6. CN Flagship Family (`qwen*`, `glm*`, `kimi*`, `minimax*`, `doubao*`, `mimo*`)
- **Armor**: Bureaucratic report framing, stacked 4-character policy idioms, and grand institutional wrap-ups.
- **Counter-Armor**: Everyday conversational Chinese with varied sentence length, direct disagreement, and dedicated `cn_idiom_bureaucratese` detection.

## Multi-Turn Penetration Without Cache Invalidation
- **Cache-Stable System Channel**: Baseline, family directive, and 3-tier tone (`calm` / `peer` / `sharp`) stay stable at session start.
- **Ephemeral User-Adjacent Wire Channel**: Turn 1 injects mode + wire anchor + 1 orthogonal `<voice_sample>`; steady chat Turn 2+ injects 1 rotating `~20`-token 5-perspective micro-anchor; every 5 chat turns rotates 4 refresh perspectives + session Self-Bootstrap (`good_voice_anchor`). `SURGICAL_EXEC`, `DEBUG_RECOVERY`, `invocationNum > 1`, and `terse`/`adversarial` roles stay silent (`{}`).
