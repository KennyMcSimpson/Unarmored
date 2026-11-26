"""Cross-family blind pairwise LLM judge for Unarmored A/B runs (stdlib only).

Breaks self-judging Goodhart overfitting by evaluating anonymized `(cond_a, cond_b)`
responses WITHOUT exposing Unarmored's system prompt, condition labels, or rule regexes.
Performs AB / BA position-swapped judging to measure and cancel position bias, scores
4 independent axes + overall, and enforces 6 single-sample hard-veto codes.

Credentials are read from environment variables and never logged or written to disk:
  UNARMORED_JUDGE_BASE_URL / UNARMORED_JUDGE_API_KEY (falls back to UNARMORED_EVAL_*)
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import sys
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "scripts"))

import run as eval_run  # noqa: E402
import score as eval_score  # noqa: E402
import unarmored_hook as H  # noqa: E402

AXES = ("naturalness", "substance", "stance_clarity", "formatting_fit", "overall")
VETO_CODES = frozenset({
    "factual_error",
    "hallucinated_entity",
    "unsubstantiated_snark",
    "archaic_drift",
    "over_refusal",
    "missed_user_anchor",
})

_JUDGE_SYSTEM = (
    "You are an impartial senior engineering & technical-writing evaluator.\n"
    "Compare two anonymous assistant replies (Response A and Response B) to the same user prompt.\n"
    "Judge ONLY on real human usefulness, technical accuracy, clarity, and natural conversational fit.\n"
    "Do NOT reward unnecessary length, corporate padding, robotic templates, archaic diction, or empty snark.\n"
    "Return STRICT JSON only (no prose outside JSON) matching this schema:\n"
    "{\n"
    '  "naturalness": "A" | "B" | "tie",\n'
    '  "substance": "A" | "B" | "tie",\n'
    '  "stance_clarity": "A" | "B" | "tie",\n'
    '  "formatting_fit": "A" | "B" | "tie",\n'
    '  "overall": "A" | "B" | "tie",\n'
    '  "hard_veto_a": ["factual_error"|"hallucinated_entity"|"unsubstantiated_snark"|"archaic_drift"|"over_refusal"|"missed_user_anchor"],\n'
    '  "hard_veto_b": [...],\n'
    '  "reason": "1-2 concise sentences explaining the key difference"\n'
    "}"
)


def _strip_json_fences(raw: str) -> str:
    txt = (raw or "").strip()
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", txt, re.DOTALL | re.IGNORECASE)
    for cand in reversed(fenced):
        try:
            if isinstance(json.loads(cand), dict):
                return cand.strip()
        except json.JSONDecodeError:
            continue
    # Fallback: scan balanced brace objects from the end
    depth = 0
    end = -1
    in_str = False
    esc = False
    for idx in range(len(txt) - 1, -1, -1):
        ch = txt[idx]
        if ch == '"' and not esc:
            in_str = not in_str
        esc = (ch == "\\") and not esc if in_str else False
        if in_str:
            continue
        if ch == "}":
            if depth == 0:
                end = idx
            depth += 1
        elif ch == "{":
            depth -= 1
            if depth == 0 and end > idx:
                cand = txt[idx : end + 1]
                try:
                    if isinstance(json.loads(cand), dict):
                        return cand
                except json.JSONDecodeError:
                    end = -1
    return txt


def parse_judge_json(raw: str) -> dict:
    """Parse and strictly validate a blind-judge JSON verdict (all axes required)."""
    data = json.loads(_strip_json_fences(raw))
    if not isinstance(data, dict):
        raise ValueError("Judge response must be a JSON object")
    out: dict = {}
    for axis in AXES:
        if axis not in data:
            raise ValueError(f"Missing required judge axis: {axis}")
        val = str(data[axis]).strip()
        val_u = val.upper()
        if val_u in ("A", "B"):
            out[axis] = val_u
        elif val.lower() == "tie":
            out[axis] = "tie"
        else:
            raise ValueError(f"Invalid verdict for {axis}: {val!r}")
    for key in ("hard_veto_a", "hard_veto_b"):
        raw_list = data.get(key) or []
        if not isinstance(raw_list, list):
            raw_list = []
        out[key] = sorted({str(x).strip() for x in raw_list if str(x).strip() in VETO_CODES})
    out["reason"] = str(data.get("reason") or "").strip()[:400]
    return out


def pair_rows(rows: list[dict], cond_a: str, cond_b: str) -> list[dict]:
    """Pair error-free rows by `(model, id)` for `(cond_a, cond_b)`, backfilling prompts from catalog if needed."""
    catalog = eval_score._load_item_catalog()
    buckets: dict[tuple[str, str], dict[str, dict]] = {}
    for r in rows:
        if r.get("error"):
            continue
        cond = str(r.get("condition") or "")
        if cond not in (cond_a, cond_b):
            continue
        key = (str(r.get("model") or ""), str(r.get("id") or ""))
        buckets.setdefault(key, {})[cond] = r

    pairs: list[dict] = []
    for (model, pid), slot in sorted(buckets.items()):
        if cond_a not in slot or cond_b not in slot:
            continue
        ra, rb = slot[cond_a], slot[cond_b]
        item = catalog.get(pid, {})
        prompt = str(ra.get("prompt") or rb.get("prompt") or item.get("prompt") or "")
        pairs.append({
            "model": model,
            "family": str(ra.get("family") or rb.get("family") or H.classify_model_family(model)),
            "id": pid,
            "cat": str(ra.get("cat") or rb.get("cat") or item.get("cat") or ""),
            "lang": str(ra.get("lang") or rb.get("lang") or item.get("lang") or "zh"),
            "prompt": prompt,
            "gold": item.get("gold"),
            "cond_a": cond_a,
            "cond_b": cond_b,
            "response_a": str(ra.get("response") or ""),
            "response_b": str(rb.get("response") or ""),
        })
    return pairs


def check_cross_family(judge_model: str, pairs: list[dict], strict: bool = False) -> dict:
    """Detect whether judge model shares a family or normalized model ID with any evaluated candidate."""
    cfg = H.load_config()
    H.set_active_strip_patterns(cfg.get("model_strip_patterns") or [])
    aliases = cfg.get("model_aliases") or {}

    judge_fam = H.classify_model_family(judge_model, aliases)
    judge_leaf = H.normalize_model_leaf(judge_model)
    tested_fams_set: set[str] = set()
    same_model_hits: list[str] = []
    for p in pairs:
        raw_m = str(p.get("model") or "")
        inferred = H.classify_model_family(raw_m, aliases)
        declared = str(p.get("family") or "").strip().lower()
        if declared in H.VALID_FAMILIES and declared != "generic":
            tested_fams_set.add(declared)
        if inferred != "generic" or not declared:
            tested_fams_set.add(inferred)
        if raw_m and judge_leaf and H.normalize_model_leaf(raw_m) == judge_leaf:
            same_model_hits.append(raw_m)

    tested_fams = sorted(tested_fams_set)
    overlap = [f for f in tested_fams if f == judge_fam and judge_fam != "generic"]
    same_models = sorted(set(same_model_hits))
    unverified_generic = judge_fam == "generic"
    warning = bool(overlap or same_models or unverified_generic)
    info = {
        "judge_model": judge_model,
        "judge_family": judge_fam,
        "tested_families": tested_fams,
        "same_family_overlap": overlap,
        "same_model_overlap": same_models,
        "same_family_warning": warning,
    }
    if strict and warning:
        reasons = []
        if overlap:
            reasons.append(f"family overlap {overlap}")
        if same_models:
            reasons.append(f"identical model {same_models}")
        if unverified_generic:
            reasons.append("judge family is unclassified 'generic' (add a model_alias or use a known cross-family model)")
        raise ValueError(
            f"--strict-cross-family refused judging: judge={judge_model} ({judge_fam}) — {'; '.join(reasons)}"
        )
    return info


def build_blind_prompt(pair: dict, text_a: str, text_b: str) -> list[dict]:
    """Build condition-blind evaluation messages (never leaks Unarmored prompts or condition names)."""
    gold_note = f"\nVerified factual reference pattern: {pair['gold']}" if pair.get("gold") else ""
    user_msg = (
        f"Category: {pair.get('cat', 'general')} | Language: {pair.get('lang', 'auto')}{gold_note}\n\n"
        f"### User Prompt\n{pair.get('prompt', '')}\n\n"
        f"### Response A\n{text_a}\n\n"
        f"### Response B\n{text_b}\n\n"
        "Evaluate Response A vs Response B on:\n"
        "1. naturalness: spoken human peer cadence vs stiff/bloodless AI prose or forced dramatics\n"
        "2. substance: factual/technical accuracy, concrete mechanism, zero dropped user anchors\n"
        "3. stance_clarity: direct honest judgment with explicit unverified gaps vs fence-sitting/flattery\n"
        "4. formatting_fit: readable chat paragraphs vs doc-in-chat headings/dividers/wall-of-text\n"
        "5. hard_veto_a / hard_veto_b: list ONLY severe defects from the 6 allowed codes.\n"
        "Return strict JSON only."
    )
    return [{"role": "system", "content": _JUDGE_SYSTEM}, {"role": "user", "content": user_msg}]


def _flip_label(label: str) -> str:
    return "B" if label == "A" else ("A" if label == "B" else "tie")


def reconcile_ab_ba(ab: dict, ba: dict) -> dict:
    """Reconcile forward (A,B) and position-swapped (B,A) verdicts into debiased outcomes + hard-veto enforcement."""
    # Map BA back into original (A=cond_a, B=cond_b) coordinate frame
    ba_mapped = {axis: _flip_label(ba[axis]) for axis in AXES}
    ba_veto_a = list(ba.get("hard_veto_b") or [])
    ba_veto_b = list(ba.get("hard_veto_a") or [])

    axes_out: dict[str, str] = {}
    position_flips: list[str] = []
    for axis in AXES:
        v1, v2 = ab[axis], ba_mapped[axis]
        if v1 == v2:
            axes_out[axis] = v1
        elif v1 == "tie" or v2 == "tie":
            winner = v1 if v2 == "tie" else v2
            axes_out[axis] = f"weak_{winner}"
        else:
            axes_out[axis] = "position_flip"
            position_flips.append(axis)

    a_veto_ab = bool(ab.get("hard_veto_a"))
    a_veto_ba = bool(ba_veto_a)
    b_veto_ab = bool(ab.get("hard_veto_b"))
    b_veto_ba = bool(ba_veto_b)
    veto_a = sorted(set(ab.get("hard_veto_a") or []) | set(ba_veto_a))
    veto_b = sorted(set(ab.get("hard_veto_b") or []) | set(ba_veto_b))

    # Hard-veto enforcement (round-based confirmation so distinct codes across AB/BA still confirm;
    # monotonic across weak_A/weak_B/tie/position_flip)
    a_vetoed = (a_veto_ab and a_veto_ba) or ((a_veto_ab or a_veto_ba) and not (b_veto_ab or b_veto_ba))
    b_vetoed = (b_veto_ab and b_veto_ba) or ((b_veto_ab or b_veto_ba) and not (a_veto_ab or a_veto_ba))
    overall_final = axes_out["overall"]
    veto_override = False
    if a_vetoed and b_vetoed:
        overall_final = "both_vetoed"
        veto_override = True
    elif b_vetoed and overall_final in ("B", "weak_B", "weak_A", "tie", "position_flip"):
        overall_final = "A"
        veto_override = True
    elif a_vetoed and overall_final in ("A", "weak_A", "weak_B", "tie", "position_flip"):
        overall_final = "B"
        veto_override = True

    return {
        "axes": axes_out,
        "overall_final": overall_final,
        "position_flips": position_flips,
        "veto_a": veto_a,
        "veto_b": veto_b,
        "veto_override": veto_override,
        "reason_ab": ab.get("reason", ""),
        "reason_ba": ba.get("reason", ""),
    }


def aggregate_judge_results(records: list[dict], cond_a: str, cond_b: str) -> dict:
    """Compute strict/lenient win rates across 4 axes + overall, position bias rate, and veto incidents."""
    valid = [r for r in records if not r.get("error")]
    n = len(valid)
    axis_stats: dict[str, dict] = {}
    for axis in AXES:
        a_strict = b_strict = a_weak = b_weak = ties = flips = both_v = 0
        for r in valid:
            val = r["overall_final"] if axis == "overall" else r["axes"][axis]
            if val == "A":
                a_strict += 1
            elif val == "B":
                b_strict += 1
            elif val == "weak_A":
                a_weak += 1
            elif val == "weak_B":
                b_weak += 1
            elif val == "position_flip":
                flips += 1
            elif val == "both_vetoed":
                both_v += 1
            else:
                ties += 1
        denom = max(n, 1)
        axis_stats[axis] = {
            "a_wins": a_strict,
            "b_wins": b_strict,
            "a_weak": a_weak,
            "b_weak": b_weak,
            "ties": ties,
            "position_flips": flips,
            "both_vetoed": both_v,
            "b_win_rate": round(b_strict / denom, 3) if n else None,
            "b_lenient_win_rate": round((b_strict + b_weak) / denom, 3) if n else None,
            "a_win_rate": round(a_strict / denom, 3) if n else None,
            "position_bias_rate": round(flips / denom, 3) if n else None,
        }

    veto_incidents = [
        {
            "model": r["model"],
            "id": r["id"],
            "cat": r["cat"],
            "veto_a": r["veto_a"],
            "veto_b": r["veto_b"],
            "overall_final": r["overall_final"],
            "reason": r.get("reason_ab") or r.get("reason_ba") or "",
        }
        for r in valid
        if r.get("veto_a") or r.get("veto_b")
    ]
    return {
        "cond_a": cond_a,
        "cond_b": cond_b,
        "pairs_total": len(records),
        "pairs_scored": n,
        "errors": len(records) - n,
        "axes": axis_stats,
        "veto_incidents": veto_incidents,
    }


def render_judge_markdown(summary: dict, cross_family: dict) -> str:
    ca, cb = summary["cond_a"], summary["cond_b"]
    lines = [
        f"# Blind Pairwise Judge Summary (`{ca}` vs `{cb}`)",
        "",
        f"- Judge model: `{cross_family['judge_model']}` (family: `{cross_family['judge_family']}`)",
        f"- Cross-family check: {'WARNING same-family overlap ' + str(cross_family['same_family_overlap']) if cross_family['same_family_warning'] else 'OK (independent family)'}",
        f"- Pairs scored: `{summary['pairs_scored']}/{summary['pairs_total']}` (errors: `{summary['errors']}`)",
        "",
        f"| axis | {cb} win | {ca} win | weak {cb} | tie | pos_flip | {cb} strict % | {cb} lenient % | pos_bias % |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for axis in AXES:
        st = summary["axes"][axis]
        bw = "" if st["b_win_rate"] is None else f"{st['b_win_rate'] * 100:.1f}%"
        bl = "" if st["b_lenient_win_rate"] is None else f"{st['b_lenient_win_rate'] * 100:.1f}%"
        pb = "" if st["position_bias_rate"] is None else f"{st['position_bias_rate'] * 100:.1f}%"
        lines.append(
            f"| {axis} | {st['b_wins']} | {st['a_wins']} | {st['b_weak']} | {st['ties']} | {st['position_flips']} | {bw} | {bl} | {pb} |"
        )
    if summary["veto_incidents"]:
        lines.extend(["", "## Hard Veto Incidents", ""])
        for v in summary["veto_incidents"]:
            lines.append(
                f"- `{v['model']}` / `{v['id']}` ({v['cat']}): `{ca}`={v['veto_a']} `{cb}`={v['veto_b']} -> `{v['overall_final']}` ({v['reason']})"
            )
    return "\n".join(lines) + "\n"


def _judge_one_pair(pair: dict, base_url: str, api_key: str, args) -> dict:
    base = {
        "model": pair["model"],
        "family": pair["family"],
        "id": pair["id"],
        "cat": pair["cat"],
        "lang": pair["lang"],
        "cond_a": pair["cond_a"],
        "cond_b": pair["cond_b"],
    }
    try:
        raw_ab = eval_run.chat(
            base_url, api_key, args.judge_model,
            build_blind_prompt(pair, pair["response_a"], pair["response_b"]),
            args.max_tokens, args.timeout, args.api,
        )
        ab = parse_judge_json(raw_ab)
        raw_ba = eval_run.chat(
            base_url, api_key, args.judge_model,
            build_blind_prompt(pair, pair["response_b"], pair["response_a"]),
            args.max_tokens, args.timeout, args.api,
        )
        ba = parse_judge_json(raw_ba)
        return {**base, **reconcile_ab_ba(ab, ba)}
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        http.client.HTTPException,
        OSError,
        TimeoutError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as exc:
        return {**base, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="judge.py", description="Cross-family AB/BA blind pairwise judge for Unarmored eval results.")
    p.add_argument("--results", type=Path, required=True, help="Path to results.jsonl produced by eval/run.py")
    p.add_argument("--cond-a", default="bare", help="Baseline condition name (default: bare)")
    p.add_argument("--cond-b", default="v07", help="Target condition name (default: v07)")
    p.add_argument("--judge-model", required=True, help="Independent cross-family judge model id")
    p.add_argument("--api", choices=("openai", "anthropic"), default=os.environ.get("UNARMORED_JUDGE_API") or os.environ.get("UNARMORED_EVAL_API", "openai"))
    p.add_argument("--strict-cross-family", action="store_true", help="Exit 2 if judge model shares a family with any tested model")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--max-tokens", type=int, default=512)
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--out", type=Path, default=None, help="Output JSON path (default: sibling judge_<a_vs_b>.json)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    rows = [json.loads(line) for line in args.results.read_text(encoding="utf-8").splitlines() if line.strip()]
    pairs = pair_rows(rows, args.cond_a, args.cond_b)
    if args.limit:
        pairs = pairs[: args.limit]
    try:
        cross = check_cross_family(args.judge_model, pairs, strict=args.strict_cross_family)
    except ValueError as exc:
        sys.stderr.write(f"judge.py error: {exc}\n")
        return 2

    plan = {
        "pairs": len(pairs),
        "judge_calls_ab_ba": len(pairs) * 2,
        "cond_a": args.cond_a,
        "cond_b": args.cond_b,
        **cross,
    }
    if args.dry_run:
        sys.stdout.write(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
        return 0

    base_url = os.environ.get("UNARMORED_JUDGE_BASE_URL") or os.environ.get("UNARMORED_EVAL_BASE_URL", "")
    api_key = os.environ.get("UNARMORED_JUDGE_API_KEY") or os.environ.get("UNARMORED_EVAL_API_KEY", "")
    if not base_url or not api_key:
        sys.stderr.write("Set UNARMORED_JUDGE_BASE_URL/API_KEY (or UNARMORED_EVAL_*) first.\n")
        return 2

    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 8))) as pool:
        records = list(pool.map(lambda pr: _judge_one_pair(pr, base_url, api_key, args), pairs))

    summary = aggregate_judge_results(records, args.cond_a, args.cond_b)
    md = render_judge_markdown(summary, cross)
    out_json = args.out or (args.results.parent / f"judge_{args.cond_a}_vs_{args.cond_b}.json")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    payload = {"cross_family": cross, "summary": summary, "records": records}
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_json.with_suffix(".md").write_text(md, encoding="utf-8")
    sys.stdout.write(md)
    return 0 if summary["errors"] < max(summary["pairs_total"], 1) else 1


if __name__ == "__main__":
    raise SystemExit(main())
