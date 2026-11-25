# Six-Family Armor Anatomy & Cross-Family De-Armoring Profiles (v0.6)

Mechanistic interpretability (*Persona Selection Model*, *Assistant Axis*, *Persona Vectors*, *Slop Forensics*) plus real-model A/B runs show that post-training clamps models into two distinct traps:
1. **Customer-support / report armor**: disclaimers, flattery, `---` dividers, `#` headers, standalone bold pseudo-headers, bullet decks, and closing waiter offers.
2. **Cautious-consultant centroid**: even after removing obvious slop, models drift into praise-then-pivot buffers, "both have merits / find a balance" hedging, and 400-char wall-of-text bricks—especially when index-0 calibration gets diluted by 20–40 KB coding-agent system prompts.

Unarmored v0.6 keeps all banned-word lists strictly inside external detectors (zero Pink-Elephant attention priming), uses a **plain-prose** `[Operational Lock]` cleanly separated from tone intensity (`calm` / `peer` / `sharp`), and pairs system-channel directives with **universal Turn-1 user-adjacent wire anchors** plus **edge-triggered 6-mode envelopes**.

## 1. GPT Family (`gpt-*`, `o1/o3/o4`, `codex`)
- **Post-Training Armor**: Cautious-consultant cadence (praise-then-pivot, "not black-and-white / find a dynamic balance"), antithetical contrast staging ("not A, but B"), generic disclaimers, closing waiter menus, and collapsing long explanations into one unbroken 400+ char wall of text.
- **Counter-Armor**: Explicitly counters praise-then-pivot and consultant balance-seeking; adds a compact Turn-1 wire anchor (`[Direct:GPT]` and its localized Chinese counterpart) so calibration penetrates heavy agent prompts on Turn 1 without repeating every round; preserves honest inline reporting of real risks, unverified gaps, and decision-flipping thresholds.

## 2. DeepSeek Family (`deepseek-*`, `ds-r1`, `ds-v*`)
- **Post-Training Armor**: Strong native sharpness, but cold-start SFT bakes in tutorial-deck reflexes—opening meta-narration ("conclusion first"), stacked `---` horizontal rules, numbered 1-2-3-4 checklists, closing waiter offers, and code elisions (`// rest unchanged`). Reasoning models attend heavily to user-adjacent recency cues.
- **Counter-Armor**:
  - **System channel**: Keeps native candor and 100% runnable code while explicitly clamping meta-openers, horizontal dividers, tutorial checklists, and closing offers.
  - **User-adjacent wire channel**: Injects a compact 1-line recency lock (`[DS Direct]` and its localized Chinese counterpart) on conversational turns right next to the user message so it enters `<think>` at high attention weight.
  - **Optional provider wire channel**: Opt-in `reasoning_content` prefix seeding after verifying route support via `eval/probe_prefix.py`.

## 3. Claude Family (`claude-*`, `opus`, `sonnet`, `haiku`)
- **Post-Training Armor**: Document-in-chat reflex (`#` headers + bold labels), validation sandwiches on interpersonal pushback, constitutional lecturing, reflexive closing offers, and sycophantic Flip-Flop capitulation under authority pressure.
- **Counter-Armor**: Combines candid peer prose with an English anti-FlipFlop and hard-stop tail plus a Turn-1 wire anchor (`[Direct:Claude]` and its localized Chinese counterpart).

## 4. Gemini Family (`gemini-*`, `carbon`, `argon`, `gemma`)
- **Post-Training Armor**: High-arousal user flattery, dramatic hyperbole, exclamation spam, mid-sentence bolding clutter, and heavy Markdown document scaffolding (`###`, `---`, meta-openers, closing offers).
- **Counter-Armor**: Redirects expressive energy into vivid causal analogies and crisp prose while explicitly clamping `###` headings, horizontal dividers, meta-openers, and closing offers. On Antigravity, Chinese sessions also receive `ANTIGRAVITY_ZH_MIRROR` so English static rules never pull Chinese replies into stiff translated prose.

## 5. Grok Family (`grok-*`, `xai/*`)
- **Post-Training Armor**: Forced edgy/meme banter ("buckle up") and cross-turn phraseology/metaphor latching.
- **Counter-Armor**: Preserves dry bite and sharp metaphors tied strictly to concrete facts while dropping forced memes and retiring prior-turn openings/metaphors.

## 6. CN Flagship Family (`qwen*`, `glm*`, `kimi*`, `minimax*`, `doubao*`, `mimo*`)
- **Post-Training Armor**: Bureaucratic civil-service report framing, forced 1-2-3-4 subheadings, and grand closing summaries.
- **Counter-Armor**: Cohesive spoken-peer paragraphs with varied sentence length, concrete examples, and a clean stop on the final useful fact.

## Behavioral Fingerprinting & Edge-Triggered Multi-Turn Calibration
- **Behavioral Fingerprinting**: Masked or routed model IDs start on `generic` and lock onto the underlying family as soon as characteristic smells appear.
- **Edge-Triggered 6-Mode Envelopes**: Matches cadence and candor to the turn's actual speech act (`EXPLAIN_DEEP`, `CRITIQUE_OPINION`, `EMPATHY_VENT`, `PEER_SPAR`, `SURGICAL_EXEC`, `DEBUG_RECOVERY`) across Claude Code, Codex CLI, and Antigravity—only injecting on Turn 1, mode shifts, or explicit expressive/debug turns to prevent multi-turn prompt habituation and token bloat.
- **Rotating Anti-Decay Pulse**: Every 5 conversational turns (gated off during `SURGICAL_EXEC` and `DEBUG_RECOVERY`), rotates between two compact refresh lines so Index-0 system instructions stay fresh without mechanical repetition.
