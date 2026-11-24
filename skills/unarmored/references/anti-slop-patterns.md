# Two-Stream Structural, Formatting & Lexical Anti-Slop Engine (v0.6)

## 1. Orthogonal Stream Splitting
Scanning raw transcripts blindly causes false positives on inline code, quoted logs, Python `Protocol` stubs (`...`), and conditional logic (`如果用户不是管理员，而是访客`). Every assistant turn is split in linear `O(N)` time into:
1. **`prose_stream`**: CommonMark state machine strips fenced blocks, inline code spans, Markdown image/link targets, and blockquotes.
2. **`code_stream`**: Tracks fenced code blocks (excluding doc fences like `markdown`/`txt`/`log`) separately from file-edit tool payloads (`write_file`, `edit_file`, `apply_patch`), allowing `Stop` gates to block lazy tool-edit payloads unconditionally while exempting illustrative code snippets in explanation/review turns.

## 2. Detector Categories (29 Signals, Honesty-Aware, Zero Pink-Elephant Priming)
All regex patterns stay strictly bounded `O(N)` in background detectors and are never fed into model prompts:
- **Honesty Exemption**: When a reply explicitly discloses an unverified/unrun engineering claim (`没跑单测`, `没在生产硬件上跑`, `静态读代码推断`, `haven't tested`, `code-reading only`), soft technical caveats (`仅供参考`, `值得注意的是`, non-cliche `取决于`) are exempted so honest reporting is never penalized as AI slop. Hard liability boilerplate (`我不是医生`, `不构成法律意见`, `as an AI`) and hard corporate wrap-ups (`总而言之`, `in conclusion`) are still caught.
- **Consultant Hedging & Validation**:
  - **`consultant_balance`** (weight 2 → `gpt`): "not black-and-white / find a dynamic balance / both X and Y are mature choices, while X offers..., Y provides... ultimately comes down to...".
  - **`praise_then_pivot`** (weight 1 → `gpt`, opening 240 chars): "your starting point is great, however..." / "that's a great question, however...".
  - **Verdict-aware `fence_sitting`**: a single strong fence cliche (`各有优劣`, `没有绝对的标准答案`, `it depends`) with no clear verdict scores weight 2; naming a clear pick (`选 SQLite`, `先留着单体别动`, `stick with`) plus concrete thresholds scores 0.
  - **`disclaimer_boilerplate`**, **`validation_template`**, **`closing_offer`**, **`gpt_closing_menu`**, **`claude_apology_pivot`**.
- **Formatting & Cadence Relapses**:
  - **`doc_format_in_chat`**: catches Markdown `#` headings, bold `**Label:**` lines, **and colon-less standalone bold pseudo-headers** (`**结论**`, `**1. 先试正常退出**`).
  - **`meta_opening`**, **`divider_spam`**, **`wall_of_text`**, density-aware **`gem_dramatic_bold`** (avoids penalizing lively multi-paragraph prose for 3 exclamation marks while still catching short-burst exclamation spam or `!!`).
- **Structural & Metadiscourse Tells**:
  - **`transition_scaffold`**, **`struct_copula_puffery`**, **`struct_participial_tail`**, **`academic_self_sabotage`**, **`cross_turn_repeat`**.
- **Code Completeness & Safe Stop Gates**:
  - **`ds_lazy_code`**, **`ds_prose_handwave`**, plus Stop-hook completeness/execution/write gates that respect `permission_mode` (`plan` / `read-only` / `ask`), read-only `adversarial` roles, and explicit plan-only requests (`先别急着改` / `plan only`), while catching `Read`-only plan stops (`edit_or_exec_calls == 0`).

## 3. Severity-Ranked Closed-Loop Remedies
Smells are ranked by descending severity weight before selecting the top 3 for `[语域纠偏]` / `[Relapse Fix]`, ensuring critical 2-point issues (`consultant_balance`, `fence_sitting`, `ds_lazy_code`, `claude_preachy`) are never pushed out by 1-point minor tells, paired with concrete next-turn focus hints.
