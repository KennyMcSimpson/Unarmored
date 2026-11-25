# Two-Stream Structural, Formatting & Lexical Anti-Slop Engine (v0.6)

## 1. Orthogonal Stream Splitting
Scanning raw transcripts blindly causes false positives on inline code, quoted logs, Python `Protocol` stubs (`...`), and conditional logic (e.g., "if the user is not an admin, but a guest"). Every assistant turn is split in linear `O(N)` time into:
1. **`prose_stream`**: CommonMark state machine strips fenced blocks, inline code spans, Markdown image/link targets, and blockquotes.
2. **`code_stream`**: Tracks fenced code blocks (excluding doc fences like `markdown`/`txt`/`log`) separately from file-edit tool payloads (`write_file`, `edit_file`, `apply_patch`), allowing `Stop` gates to block lazy tool-edit payloads unconditionally while exempting illustrative code snippets in explanation/review turns.

## 2. Detector Categories (29 Signals, Honesty-Aware, Zero Pink-Elephant Priming)
All regex patterns stay strictly bounded `O(N)` in background detectors and are never fed into model prompts:
- **Honesty Exemption**: When a reply explicitly discloses an unverified/unrun engineering claim (`haven't tested`, `didn't run the benchmark`, `code-reading only`, and bilingual Chinese equivalents), soft technical caveats (`for reference only`, `it's worth noting`, non-cliche `depends on`, and localized counterparts) are exempted so honest reporting is never penalized as AI slop. Hard liability boilerplate (`not legal advice`, `as an AI`, medical/financial disclaimers) and hard corporate wrap-ups (`in conclusion`, `in today's fast-paced...`, and localized equivalents) are still caught.
- **Consultant Hedging & Validation**:
  - **`consultant_balance`** (weight 2 → `gpt`): "not black-and-white / find a dynamic balance / both X and Y are mature choices, while X offers..., Y provides... ultimately comes down to...".
  - **`praise_then_pivot`** (weight 1 → `gpt`, opening 240 chars): "your starting point is great, however..." / "that's a great question, however...".
  - **Verdict-aware `fence_sitting`**: a single strong fence cliche (`it depends`, `both have pros and cons`, `there is no one-size-fits-all answer`, and localized equivalents) with no clear verdict scores weight 2; naming a clear pick (`pick SQLite`, `stick with the monolith`) plus concrete thresholds scores 0.
  - **`disclaimer_boilerplate`**, **`validation_template`**, **`closing_offer`**, **`gpt_closing_menu`**, **`claude_apology_pivot`**.
- **Formatting & Cadence Relapses**:
  - **`doc_format_in_chat`**: catches Markdown `#` headings, bold `**Label:**` lines, **and colon-less standalone bold pseudo-headers** (`**Conclusion**`, `**1. Try a clean shutdown first**`).
  - **`meta_opening`**, **`divider_spam`**, **`wall_of_text`**, density-aware **`gem_dramatic_bold`** (avoids penalizing lively multi-paragraph prose for 3 exclamation marks while still catching short-burst exclamation spam or `!!`).
- **Structural & Metadiscourse Tells**:
  - **`transition_scaffold`**, **`struct_copula_puffery`**, **`struct_participial_tail`**, **`academic_self_sabotage`**, **`cross_turn_repeat`**.
- **Code Completeness & Safe Stop Gates**:
  - **`ds_lazy_code`**, **`ds_prose_handwave`**, plus Stop-hook completeness/execution/write gates that respect `permission_mode` (`plan` / `read-only` / `ask`), read-only `adversarial` roles, and explicit plan-only requests (`plan only` and localized non-edit guards), while catching `Read`-only plan stops (`edit_or_exec_calls == 0`).

## 3. Severity-Ranked Closed-Loop Remedies
Smells are ranked by descending severity weight before selecting the top 3 for `[Relapse Fix]` (and its localized Chinese header), ensuring critical 2-point issues (`consultant_balance`, `fence_sitting`, `ds_lazy_code`, `claude_preachy`) are never pushed out by 1-point minor tells, paired with concrete next-turn focus hints.
