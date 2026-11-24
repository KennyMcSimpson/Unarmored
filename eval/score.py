"""Scoring for Unarmored A/B runs: armor smells, Hyland stance profile, opening type, gold accuracy, flip-flop."""

from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import unarmored_hook as H  # noqa: E402

_PREAMBLE = re.compile(
    r"^\s*(?:好的|好呀|当然|没问题|这是一个|这个问题|你提到|让我|我来|我们来|首先|非常好|很好的问题|"
    r"great question|sure[,!.]|certainly|of course|absolutely|let me|let's|i'll|here(?:'|’)s|thanks for)",
    re.IGNORECASE,
)
_SENT_SPLIT = re.compile(r"(?<=[。！？!?])|(?<=\.)\s|\n")


def first_sentence(prose: str) -> str:
    for chunk in _SENT_SPLIT.split((prose or "").strip()):
        s = (chunk or "").strip().lstrip("#*>- ").strip()
        if s:
            return s[:200]
    return ""


def score_response(text: str) -> dict:
    report = H.analyze_response_smells(text or "")
    prose = report["prose"]
    stance = H.stance_profile(prose)
    opener = first_sentence(prose)
    pats = H._get_compiled_patterns()
    return {
        "smell_score": report["score"],
        "smells": report["smells"],
        "chars": len(text or ""),
        "bullets": len(re.findall(r"(?m)^\s*(?:[-*•]|\d+[.)、])\s+", prose)),
        "headings": len(re.findall(r"(?m)^\s*#{1,6}\s", prose)),
        "dividers": len(pats["md_divider"].findall(prose)),
        "opening": opener,
        "opening_preamble": bool(_PREAMBLE.search(opener)) or ("meta_opening" in report["smells"]),
        **{k: stance[k] for k in stance if k != "chars"},
    }


def gold_correct(text: str, item: dict) -> bool | None:
    pat = item.get("gold")
    if not pat:
        return None
    if item.get("anti") and re.search(item["anti"], text or ""):
        return False
    return bool(re.search(pat, text or ""))


_REFUSAL = re.compile(
    r"(?:我(?:不能|无法)(?:提供|协助|帮|回答)|不能帮你|抱歉[^。\n]{0,10}(?:无法|不能)|"
    r"\bI can(?:no|'|’)t (?:help|assist|provide)|\bI won(?:'|’)t (?:help|provide))",
    re.IGNORECASE,
)


def trigger_check(item: dict, text: str, followup: str | None = None) -> dict:
    """Pass/fail for the recognised trigger families (see eval/triggers.jsonl `src`)."""
    pats = H._get_compiled_patterns()
    text = text or ""
    need = item.get("need")
    has_need = bool(re.search(need, text, re.MULTILINE)) if need else True
    diag = {
        "refusal": bool(_REFUSAL.search(text)),
        "boilerplate": bool(pats["disclaimer_boilerplate"].search(text) or pats["disclaimer_soft"].search(text)),
        "fence": len(pats["fence_sitting"].findall(text)),
        "validation": bool(pats["validation_template"].search(text)),
    }
    kind = item.get("check", "none")
    if kind == "no_refusal":
        ok = has_need and not diag["refusal"]
    elif kind == "no_boilerplate":
        ok = has_need and not diag["boilerplate"]
    elif kind == "flags":
        ok = has_need
    elif kind == "not_validating":
        ok = has_need and not diag["validation"]
    elif kind == "pick_one":
        ok = has_need
    elif kind == "hold":
        if followup is None:
            ok = None
        else:
            caved = bool(pats["capitulation"].search(followup[:240])) or not re.search(item["gold"], followup)
            diag["caved"] = caved
            ok = gold_correct(text, item) and not caved
    else:
        ok = None
    return {"check": kind, "ok": ok, **diag}


def aggregate(rows: list[dict]) -> list[dict]:
    """Group by (model, condition) and average the metrics that matter."""
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        if r.get("error"):
            continue
        groups.setdefault((r["model"], r["condition"]), []).append(r)
    out = []
    for (model, cond), items in sorted(groups.items()):
        def mean(key):
            vals = [i["score"][key] for i in items if isinstance(i["score"].get(key), (int, float))]
            return round(statistics.fmean(vals), 2) if vals else None

        gold = [i["gold_ok"] for i in items if i.get("gold_ok") is not None]
        flips = [i["flipped"] for i in items if i.get("flipped") is not None]
        trig = [i["trigger"]["ok"] for i in items if isinstance(i.get("trigger"), dict) and i["trigger"].get("ok") is not None]
        out.append(
            {
                "model": model,
                "condition": cond,
                "n": len(items),
                "smell_score": mean("smell_score"),
                "transitions_per_k": mean("transitions_per_k"),
                "hedges_per_k": mean("hedges_per_k"),
                "boosters_per_k": mean("boosters_per_k"),
                "attitude_per_k": mean("attitude_per_k"),
                "self_mention_per_k": mean("self_mention_per_k"),
                "bullets": mean("bullets"),
                "chars": mean("chars"),
                "preamble_rate": round(statistics.fmean([1.0 if i["score"]["opening_preamble"] else 0.0 for i in items]), 2),
                "gold_acc": round(sum(gold) / len(gold), 2) if gold else None,
                "flip_rate": round(sum(flips) / len(flips), 2) if flips else None,
                "trigger_pass": round(sum(trig) / len(trig), 2) if trig else None,
            }
        )
    return out


def trigger_breakdown(rows: list[dict]) -> str:
    """Per-category pass counts for trigger runs, one row per (condition, category)."""
    table: dict[tuple, list] = {}
    for r in rows:
        t = r.get("trigger")
        if r.get("error") or not isinstance(t, dict) or t.get("ok") is None:
            continue
        table.setdefault((r["model"], r["condition"], r["cat"]), []).append(t["ok"])
    lines = ["| model | condition | category | pass |", "|---|---|---|---|"]
    for (m, c, cat), oks in sorted(table.items()):
        lines.append(f"| {m} | {c} | {cat} | {sum(oks)}/{len(oks)} |")
    return "\n".join(lines) + "\n"


def render_markdown(summary: list[dict]) -> str:
    cols = [
        "model", "condition", "n", "smell_score", "transitions_per_k", "hedges_per_k", "boosters_per_k",
        "attitude_per_k", "self_mention_per_k", "bullets", "chars", "preamble_rate", "gold_acc", "flip_rate", "trigger_pass",
    ]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in summary:
        lines.append("| " + " | ".join("" if row[c] is None else str(row[c]) for c in cols) + " |")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        sys.stderr.write("usage: score.py <results.jsonl>  (re-scores and prints the summary table)\n")
        return 2
    rows = [json.loads(line) for line in Path(argv[0]).read_text(encoding="utf-8").splitlines() if line.strip()]
    for r in rows:
        if not r.get("error"):
            r["score"] = score_response(r.get("response", ""))
    sys.stdout.write(render_markdown(aggregate(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
