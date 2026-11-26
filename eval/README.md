# Evaluation Harness (`eval`)

Measures whether register de-armoring genuinely produces a natural, high-burstiness spoken peer voice—without degrading factual accuracy, drifting into archaisms or empty snark, increasing sycophantic flip-flopping under pushback, or fading under realistic multi-kilobyte coding-agent system prompts. Breaks self-judging regex Goodhart overfitting via a **cross-family condition-blind AB/BA judge** and an **offline single-file HTML diff report**.

## Prompt Sets

- `--set core` (default, `prompts.jsonl`, 49 prompts): bilingual (English & Chinese) benchmark covering factual gold questions (`gold`), technical trade-offs (`judgment`), troubleshooting (`debug`), code/design review (`review`), deep explanations (`explain`), epistemic challenges (`challenge`), rewriting (`writing`), and casual turns (`casual`).
- `--set triggers` (`triggers.jsonl`, 30 prompts): **30/30 active trigger checks** targeting over-refusal, disclaimer bait, flattery, sycophantic validation, false premises, balance-seeking fence-sitting, authority pressure, report-speak (`no_report_scaffold`), and emotional venting (`grounded_empathy`), scored per item via `trigger_pass`.

## Conditions

| Condition | Description |
|---|---|
| `bare` | No calibration injected (host default baseline) |
| `v03` | Frozen v0.3 directives (jargon-heavy baseline kept verbatim for comparison) |
| `v04` | Calm-colleague tone (`tone=calm`) paired with the baseline |
| `v05` | Frozen v0.5 directives (legacy bulleted Operational Lock for regression comparison) |
| `v06` | Frozen v0.6 directives (abstract rules without voice exemplars, kept as longitudinal baseline for v0.7) |
| `v07` | Live v0.7 engine (spoken-cadence baseline + orthogonal `<voice_sample>` + sharpened 3-tier tone + bidirectional overcorrection brake) |
| `v04_en` | English directives applied even to Chinese prompts plus a reply-language line (cross-lingual control) |
| `slots_raw` | Raw slot specification used directly as the system prompt to test whether code-like specs leak list formatting into output |

## Real-Agent Stress-Test Flags

- `--agent-scaffold`: prepends a generic ~6 KB coding-agent tool/workspace system scaffold before the condition prompt to simulate real prompt dilution inside Claude Code, Codex CLI, and Antigravity.
- `--wire-anchor`: attaches the user-adjacent intent envelope and compact family wire anchor next to the user message for `v06` and `v07` (`v07` also attaches an orthogonal `<voice_sample>`), simulating real dual-channel hook delivery.

## Metrics (`eval/score.py`)

- `smell_score`: relapse score from the 34-signal two-stream detector—lower is better.
- `sent_len_cv` / `short_punch_rate`: bilingual sentence-length coefficient of variation and short-punch sentence ratio (catches metronomic op-ed cadence).
- `opener_diversity` / `batch_opener_div`: per-reply sentence opener diversity and **cross-prompt batch opener diversity** (catches template collapse onto a new favorite opener).
- `spoken_pivot_per_k`, `attitude_per_k`, `self_mention_per_k`: spoken-pivot, grounded-stance, and singular first-person density per 1,000 characters.
- `hedges_per_k`, `boosters_per_k`, `transitions_per_k`: hedging, conviction, and formulaic connective rates per 1,000 characters.
- `headings`, `dividers`, `bullets`, `preamble_rate`: chat layout bloat and filler-preamble opening rate—lower is better.
- `flat_textbook_rate`, `overcorrection_rate`: Level-2 bloodless op-ed prose rate and archaic/empty-snark drift rate—lower is better.
- `anchor_fidelity`: retention rate of prompt identifiers, numbers, and error codes on closed-set `writing` / `review` / `debug` prompts—**must not drop below `bare`**.
- `gold_acc`, `flip_rate` (unified with explicit `capitulation`), `trigger_pass` (30/30 active): factual accuracy and anti-sycophancy floors.

## Cross-Family Blind Judge & Offline HTML Report

- **`eval/judge.py`**: condition-blind AB/BA position-swapped pairwise evaluation of `(cond_a, cond_b)` from `results.jsonl`, scoring 4 independent axes (`naturalness`, `substance`, `stance_clarity`, `formatting_fit`) + `overall` + `position_bias_rate` + 6 single-sample hard-veto codes (`factual_error`, `hallucinated_entity`, `unsubstantiated_snark`, `archaic_drift`, `over_refusal`, `missed_user_anchor`). Supports `--strict-cross-family` to reject same-family self-judging.
- **`eval/report.py`**: compiles `results.jsonl` (and optional `judge.json`) into a **zero-CDN single-file offline `report.html`** with KPI comparison tables, 4-axis SVG stacked bars, regression filters, inline smell highlights, and `--export-regressions` JSONL output.

## Running

```bash
export UNARMORED_EVAL_BASE_URL=https://your-endpoint/v1   # Any OpenAI-compatible endpoint
export UNARMORED_EVAL_API_KEY=...                         # Read from env only; never written to output files

python eval/run.py --models cheap-model --families gpt --conditions bare,v06,v07 --agent-scaffold --wire-anchor --limit 15
python eval/run.py --models cheap-model --families gpt --set triggers --conditions bare,v07 --agent-scaffold --wire-anchor
python eval/score.py eval/out/<timestamp>/results.jsonl

# Cross-family AB/BA blind judge (optionally set UNARMORED_JUDGE_BASE_URL / UNARMORED_JUDGE_API_KEY)
python eval/judge.py --results eval/out/<timestamp>/results.jsonl --cond-a bare --cond-b v07 --judge-model claude-sonnet-4 --strict-cross-family

# Single-file offline HTML diff & regression report
python eval/report.py --results eval/out/<timestamp>/results.jsonl --judge eval/out/<timestamp>/judge_bare_vs_v07.json --baseline bare --target v07 --export-regressions eval/out/<timestamp>/regressions.jsonl
```
