# Two-Stream Structural, Cadence & Bidirectional Anti-Slop Engine (v0.7)

## 1. Orthogonal Stream Splitting & Bilingual Cadence Analysis
Every assistant turn is split in linear `O(N)` time into:
1. **`prose_stream`**: CommonMark state machine strips fenced blocks, inline code spans, Markdown image/link targets, and blockquotes.
2. **`code_stream`**: Tracks fenced code blocks separately from file-edit tool payloads (`write_file`, `edit_file`, `apply_patch`), letting `Stop` gates block lazy tool-edit payloads unconditionally while exempting illustrative code snippets in explanation/review turns.
3. **Bilingual Cadence (`stance_profile`)**: Zero-dependency `split_sentences()` (protecting decimals, versions, file paths, domains, and English abbreviations like `e.g.`/`Fig.`/`et al.`) computes `sent_len_cv`, `short_punch_count`, `opener_diversity`, `spoken_pivot`, `self_mention_singular`, and `textbook_frames` in <1 ms.

## 2. Detector Categories (34 Signals, Honesty-Aware, Bidirectional, Zero Pink-Elephant Priming)
All regex patterns stay strictly bounded `O(N)` in background detectors and are never fed into model prompts:
- **Honesty Exemption**: Explicit unverified disclosures (`haven't tested`, `code-reading only`, and Chinese equivalents) exempt soft caveats (`for reference only`, `worth noting`, and Chinese equivalents) while still catching hard liability boilerplate (`as an AI`, medical/legal disclaimers) and corporate wrap-ups (`in conclusion`, `in today's fast-paced...`).
- **Level-2 Cadence & Bloodless-Columnist Signals** *(strictly exempt on `SURGICAL_EXEC`, `DEBUG_RECOVERY`, code-heavy replies, or trace outputs)*:
  - **`monotone_cadence`** (weight 1): >=5 prose sentences with overly uniform length (`sent_len_cv < 0.18`).
  - **`repetitive_openers`** (weight 1): repeated sentence/paragraph openings (`opener_diversity < 0.65` or `max_opener_repeat >= 3`).
  - **`flat_textbook_voice`** (weight 1 -> `gpt`, exempt on `calm` tone): long bloodless prose with zero attitude, zero spoken pivots, zero singular self-mention, plus >=2 dry textbook/uniform-cadence cues.
  - **`cn_idiom_bureaucratese`** (weight 2 -> `cn_flagship`): stacked Chinese 4-character bureaucratic idioms and grand policy wrap-ups.
  - **3-Turn `cross_turn_repeat`** (weight 2): sliding 3-turn `recent_openings` window catching both exact opening repeats and A-B-A template collapses.
- **Bidirectional Overcorrection Brake**:
  - **`overcorrection_drift`** (weight 2): catches archaic/stilted drift (`whilst`, `thereof`, `herein`, `heretofore`, `notwithstanding`, and literary Chinese equivalents) OR unsubstantiated abusive snark lacking concrete code/numeric/causal grounding. Triggers `[Overcorrection Brake]` (localized per session language) and temporarily steps tone down 1 tier (`sharp -> peer -> calm`) for 2 turns.
- **Consultant Hedging, Formatting & Code Completeness**:
  - `consultant_balance`, `praise_then_pivot`, verdict-aware `fence_sitting`, `disclaimer_boilerplate`, `validation_template`, `closing_offer`, `gpt_closing_menu`, `claude_apology_pivot`, `doc_format_in_chat`, `meta_opening`, `divider_spam`, `wall_of_text`, density-aware `gem_dramatic_bold`, `transition_scaffold`, `struct_copula_puffery`, `struct_participial_tail`, `academic_self_sabotage`, `ds_lazy_code`, `ds_prose_handwave`.

## 3. Safe Self-Bootstrap & Entity-Leak Isolation
- **Entity-Leak Guard**: Tracks distinctive topic entities of each injected `<voice_sample>` (`extract_exemplar_entities`); if an exemplar's craft-topic term leaks into the next reply without appearing in the user's prompt, that exemplar ID is automatically blacklisted for the session.
- **Session Self-Bootstrap (`good_voice_anchor`)**: Clean (`score == 0`), high-pulse chat turns (non-code, secret/path-redacted) are captured once per `(lang, family, tone)` and replayed on `PreCompact` recovery, 5-turn refresh, or non-overcorrection relapse fixes.
