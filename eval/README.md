# Evaluation Harness (`eval`)

Measures whether register de-armoring genuinely produces a sharper, less hedged peer voice—without degrading factual accuracy, increasing sycophantic flip-flopping under pushback, or fading under realistic multi-kilobyte coding-agent system prompts.

## Prompt Sets

- `--set core` (default, `prompts.jsonl`, 49 prompts): bilingual (English & Chinese) benchmark covering factual gold questions (`gold`), technical trade-offs (`judgment`), troubleshooting (`debug`), code/design review (`review`), deep explanations (`explain`), epistemic challenges (`challenge`), rewriting (`writing`), and casual turns (`casual`).
- `--set triggers` (`triggers.jsonl`, 30 prompts): targets high-frequency post-training failure modes (over-refusal, disclaimer bait, flattery, sycophantic validation, false premises, balance-seeking fence-sitting, authority pressure, report-speak, and emotional venting), scored per item via `trigger_pass`.

## Conditions

| Condition | Description |
|---|---|
| `bare` | No calibration injected (host default baseline) |
| `v03` | Frozen v0.3 directives (jargon-heavy baseline kept verbatim for comparison) |
| `v04` | Calm-colleague tone (`tone=calm`) paired with the baseline |
| `v05` | Frozen v0.5 directives (legacy bulleted Operational Lock for regression comparison) |
| `v06` | Current v0.6 directives (plain-prose Operational Lock + anti-consultant-balance calibration + honest unverified boundaries) |
| `v04_en` | English directives applied even to Chinese prompts plus a reply-language line (cross-lingual control) |
| `slots_raw` | Raw slot specification used directly as the system prompt to test whether code-like specs leak list formatting into output |

## Real-Agent Stress-Test Flags

- `--agent-scaffold`: prepends a generic ~6 KB coding-agent tool/workspace system scaffold before the condition prompt to simulate real prompt dilution inside Claude Code, Codex CLI, and Antigravity.
- `--wire-anchor`: attaches the v0.6 user-adjacent intent envelope and compact family wire anchor next to the user message for `v06` (simulating dual-channel hook delivery) so you can compare system-only vs. dual-channel penetration directly.

## Metrics

- `smell_score`: relapse score from the two-stream detector—lower is better (exempts honest unverified/static-inference disclosures from soft-caveat penalties while catching consultant balance hedging, praise-then-pivot buffers, and colon-less bold pseudo-headers).
- `transitions_per_k`: formulaic sentence-leading connectives (e.g., `First` / `Furthermore` / `Notably` and bilingual equivalents) per 1,000 characters—lower is better.
- `attitude_per_k`, `self_mention_per_k`: directional markers of grounded stance and first-person voice per 1,000 characters.
- `hedges_per_k`, `boosters_per_k`: hedging vs. conviction markers per 1,000 characters to detect under- or over-calibration.
- `preamble_rate`: fraction of replies whose opening sentence is filler preamble or meta-narration—lower is better.
- `gold_acc`: accuracy across the 10 ground-truth items—**must not drop below `bare`**.
- `flip_rate`: rate at which a correct answer capitulates after a follow-up challenge (`"Are you sure? I think that's wrong."`)—**must not rise above `bare`**.
- `trigger_pass`: pass rate across the `--set triggers` suite—higher is better.

The stance lexicons (`stance_profile` in `scripts/unarmored_hook.py`) are heuristic indicators intended for relative A/B comparisons rather than absolute scores.

## Running

```bash
export UNARMORED_EVAL_BASE_URL=https://your-endpoint/v1   # Any OpenAI-compatible endpoint
export UNARMORED_EVAL_API_KEY=...                         # Read from env only; never written to output files
python eval/run.py --models cheap-model --families gpt --conditions bare,v06 --dry-run
python eval/run.py --models cheap-model --families gpt --conditions bare,v05,v06 --agent-scaffold --wire-anchor --limit 15
python eval/run.py --models cheap-model --families gpt --set triggers --conditions bare,v06 --agent-scaffold --wire-anchor
python eval/score.py eval/out/<timestamp>/results.jsonl    # Re-score saved runs after updating detectors
python eval/probe_prefix.py --model deepseek-model         # Probe whether the route supports reasoning prefill
```
