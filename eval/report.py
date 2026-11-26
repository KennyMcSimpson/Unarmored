"""Zero-dependency offline single-file HTML comparison & regression report for Unarmored eval runs."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "scripts"))

import score as S  # noqa: E402
import unarmored_hook as H  # noqa: E402


def _highlight_html(text: str) -> str:
    """Render escaped text with inline `<mark>` highlights for detected smell spans (strictly XSS-safe)."""
    raw = text or ""
    if "```" in raw:
        return html.escape(raw)
    rep = H.analyze_response_smells(raw)
    prose = rep.get("prose") or ""
    spans = H.extract_smell_spans(raw, rep)
    if not spans:
        return html.escape(raw)
    # Map snippets onto raw text linearly when inline backticks shifted offsets
    if prose == raw.strip():
        base = prose
        mapped = spans
    else:
        base = raw
        mapped = []
        cursor = 0
        for sp in spans:
            snip = sp.get("snippet") or ""
            if not snip:
                continue
            pos = base.find(snip, cursor)
            if pos >= 0:
                mapped.append({**sp, "start": pos, "end": pos + len(snip)})
                cursor = pos + len(snip)
        if not mapped:
            return html.escape(raw)
    out: list[str] = []
    pos = 0
    for sp in mapped:
        st, en = sp["start"], sp["end"]
        if st < pos or en > len(base):
            continue
        out.append(html.escape(base[pos:st]))
        tip = html.escape(f"{sp['smell']} (w={sp['weight']})")
        cls = "hl-brake" if sp["smell"] == "overcorrection_drift" else ("hl-high" if sp["weight"] >= 2 else "hl-med")
        out.append(f'<mark class="{cls}" title="{tip}">{html.escape(base[st:en])}</mark>')
        pos = en
    out.append(html.escape(base[pos:]))
    return "".join(out)


def _normalize_judge_record_orientation(rec: dict, flipped: bool) -> dict:
    if not flipped:
        return rec
    flip_map = {"A": "B", "B": "A", "weak_A": "weak_B", "weak_B": "weak_A"}
    return {
        **rec,
        "overall_final": flip_map.get(str(rec.get("overall_final") or ""), rec.get("overall_final")),
        "veto_a": list(rec.get("veto_b") or []),
        "veto_b": list(rec.get("veto_a") or []),
        "axes": {k: flip_map.get(str(v), v) for k, v in (rec.get("axes") or {}).items()},
    }


def classify_regressions(
    rows: list[dict],
    baseline: str,
    target: str,
    judge_data: dict | None = None,
) -> list[dict]:
    """Pair `(model, id)` rows for `baseline` vs `target` and tag concrete regressions / failure modes."""
    catalog = S._load_item_catalog()
    by_key: dict[tuple[str, str], dict[str, dict]] = {}
    for r in rows:
        if r.get("error"):
            continue
        cond = str(r.get("condition") or "")
        if cond in (baseline, target):
            by_key.setdefault((str(r.get("model") or ""), str(r.get("id") or "")), {})[cond] = r

    judge_map: dict[tuple[str, str], dict] = {}
    if isinstance(judge_data, dict):
        jsum = judge_data.get("summary") or {}
        j_a = str(jsum.get("cond_a") or "")
        j_b = str(jsum.get("cond_b") or "")
        exact_match = (not j_a and not j_b) or (j_a == baseline and j_b == target)
        swapped_match = bool(j_a and j_b and j_a == target and j_b == baseline)
        if exact_match or swapped_match:
            for rec in judge_data.get("records") or []:
                if not rec.get("error"):
                    norm_rec = _normalize_judge_record_orientation(rec, flipped=swapped_match)
                    judge_map[(str(rec.get("model") or ""), str(rec.get("id") or ""))] = norm_rec

    paired: list[dict] = []
    for (model, pid), slot in sorted(by_key.items()):
        if baseline not in slot or target not in slot:
            continue
        rb, rt = slot[baseline], slot[target]
        item = catalog.get(pid, {})
        prompt = str(rt.get("prompt") or rb.get("prompt") or item.get("prompt") or "")
        cat = str(rt.get("cat") or rb.get("cat") or item.get("cat") or "")
        sb = rb.get("score") or S.score_response(rb.get("response", ""), prompt=prompt, cat=cat)
        st = rt.get("score") or S.score_response(rt.get("response", ""), prompt=prompt, cat=cat)
        jrec = judge_map.get((model, pid))

        flags: list[str] = []
        sb_num = sb.get("smell_score") if isinstance(sb.get("smell_score"), (int, float)) and not isinstance(sb.get("smell_score"), bool) else 0
        st_num = st.get("smell_score") if isinstance(st.get("smell_score"), (int, float)) and not isinstance(st.get("smell_score"), bool) else 0
        if st_num > sb_num:
            flags.append("smell_regressed")
        if rb.get("gold_ok") is True and rt.get("gold_ok") is False:
            flags.append("gold_regressed")
        if rt.get("flipped") is True and rb.get("flipped") is not True:
            flags.append("flipped_regressed")
        tb_ok = (rb.get("trigger") or {}).get("ok") if isinstance(rb.get("trigger"), dict) else None
        tt_ok = (rt.get("trigger") or {}).get("ok") if isinstance(rt.get("trigger"), dict) else None
        if tb_ok is True and tt_ok is False:
            flags.append("trigger_regressed")
        fb, ft = sb.get("anchor_fidelity"), st.get("anchor_fidelity")
        if isinstance(fb, (int, float)) and isinstance(ft, (int, float)) and ft < fb - 0.15:
            flags.append("anchor_dropped")
        if st.get("overcorrection") or "overcorrection_drift" in (st.get("smells") or []):
            flags.append("overcorrection")
        if st.get("flat_textbook") or "flat_textbook_voice" in (st.get("smells") or []):
            flags.append("flat_textbook")
        if jrec:
            if jrec.get("veto_b"):
                flags.append("judge_hard_veto")
            if jrec.get("overall_final") == "A":
                flags.append("judge_loss")

        paired.append({
            "model": model,
            "id": pid,
            "cat": cat,
            "lang": str(rt.get("lang") or rb.get("lang") or ""),
            "prompt": prompt,
            "baseline": baseline,
            "target": target,
            "resp_base": str(rb.get("response") or ""),
            "resp_target": str(rt.get("response") or ""),
            "score_base": sb,
            "score_target": st,
            "gold_base": rb.get("gold_ok"),
            "gold_target": rt.get("gold_ok"),
            "flipped_target": rt.get("flipped"),
            "trigger_target": tt_ok,
            "judge": jrec,
            "flags": flags,
        })
    return paired


def _render_judge_svg(judge_data: dict) -> str:
    summary = judge_data.get("summary") or {}
    axes = summary.get("axes") or {}
    ca = html.escape(str(summary.get("cond_a") or "A"))
    cb = html.escape(str(summary.get("cond_b") or "B"))
    rows_svg: list[str] = []
    bar_w = 320
    y = 28
    for axis in ("naturalness", "substance", "stance_clarity", "formatting_fit", "overall"):
        st = axes.get(axis) or {}
        total = max(int(summary.get("pairs_scored") or 0), 1)
        bw = int(round((st.get("b_wins", 0) / total) * bar_w))
        tw = int(round(((st.get("ties", 0) + st.get("b_weak", 0) + st.get("a_weak", 0) + st.get("position_flips", 0)) / total) * bar_w))
        aw = max(0, bar_w - bw - tw)
        pct = f"{(st.get('b_win_rate') or 0) * 100:.0f}%"
        rows_svg.append(
            f'<text x="8" y="{y + 13}" fill="#cbd5e1" font-size="12">{html.escape(axis)}</text>'
            f'<rect x="130" y="{y}" width="{bw}" height="18" rx="3" fill="#22c55e"/>'
            f'<rect x="{130 + bw}" y="{y}" width="{tw}" height="18" fill="#64748b"/>'
            f'<rect x="{130 + bw + tw}" y="{y}" width="{aw}" height="18" rx="3" fill="#ef4444"/>'
            f'<text x="{138 + bar_w}" y="{y + 13}" fill="#e2e8f0" font-size="12">{cb} {pct}</text>'
        )
        y += 28
    height = y + 12
    return (
        f'<svg viewBox="0 0 560 {height}" width="560" height="{height}" xmlns="http://www.w3.org/2000/svg">'
        f'<text x="130" y="16" fill="#94a3b8" font-size="11">Green={cb} win | Slate=tie/flip | Red={ca} win</text>'
        + "".join(rows_svg)
        + "</svg>"
    )


def render_html_report(
    summary: list[dict],
    pairs: list[dict],
    judge_data: dict | None,
    baseline: str,
    target: str,
) -> str:
    """Build a self-contained offline HTML report (zero external CDN assets, strict HTML & script escaping)."""
    kpi_cols = [
        "model", "condition", "n", "smell_score", "sent_len_cv", "short_punch_rate",
        "spoken_pivot_per_k", "attitude_per_k", "opener_diversity", "batch_opener_div",
        "headings", "dividers", "flat_textbook_rate", "overcorrection_rate",
        "anchor_fidelity", "gold_acc", "flip_rate", "trigger_pass",
    ]
    kpi_head = "".join(f"<th>{html.escape(c)}</th>" for c in kpi_cols)
    kpi_rows = []
    for row in summary:
        cells = "".join(f"<td>{html.escape('' if row.get(c) is None else str(row.get(c)))}</td>" for c in kpi_cols)
        kpi_rows.append(f"<tr>{cells}</tr>")

    judge_section = ""
    if isinstance(judge_data, dict) and judge_data.get("summary"):
        jsum = judge_data["summary"]
        cf = judge_data.get("cross_family") or {}
        vetoes = jsum.get("veto_incidents") or []
        veto_html = ""
        if vetoes:
            v_items = "".join(
                f"<li><code>{html.escape(str(v['model']))}/{html.escape(str(v['id']))}</code>: "
                f"A={html.escape(str(v['veto_a']))} B={html.escape(str(v['veto_b']))} -> "
                f"<strong>{html.escape(str(v['overall_final']))}</strong> ({html.escape(str(v.get('reason', '')))})</li>"
                for v in vetoes
            )
            veto_html = f'<div class="veto-box"><strong>Hard Veto Incidents ({len(vetoes)})</strong><ul>{v_items}</ul></div>'
        judge_section = (
            '<section class="card"><h2>Cross-Family Blind Pairwise Judge</h2>'
            f'<p class="meta">Judge: <code>{html.escape(str(cf.get("judge_model", "")))}</code> '
            f'(family: <code>{html.escape(str(cf.get("judge_family", "")))}</code>) | '
            f'Pairs: {int(jsum.get("pairs_scored") or 0)}/{int(jsum.get("pairs_total") or 0)}</p>'
            f"{_render_judge_svg(judge_data)}{veto_html}</section>"
        )

    cards_html: list[str] = []
    reg_ids: list[str] = []
    for idx, p in enumerate(pairs):
        if p["flags"]:
            reg_ids.append(p["id"])
        sb, st = p["score_base"], p["score_target"]
        flag_str = " ".join(p["flags"])
        pills = "".join(
            f'<span class="pill pill-bad">{html.escape(f)}</span>' for f in p["flags"]
        ) or '<span class="pill pill-ok">clean</span>'
        jline = ""
        if p.get("judge"):
            jr = p["judge"]
            jline = (
                f'<div class="judge-line">Blind Judge: <strong>{html.escape(str(jr.get("overall_final")))}</strong>'
                f' | {html.escape(str(jr.get("reason_ab") or jr.get("reason_ba") or ""))}</div>'
            )
        sb_smell = html.escape(str(sb.get("smell_score")))
        sb_cv = html.escape(str(sb.get("sent_len_cv")))
        sb_spk = html.escape(str(sb.get("spoken_pivot_per_k")))
        st_smell = html.escape(str(st.get("smell_score")))
        st_cv = html.escape(str(st.get("sent_len_cv")))
        st_spk = html.escape(str(st.get("spoken_pivot_per_k")))
        cards_html.append(
            f'<article class="pair-card" data-idx="{idx}" data-id="{html.escape(p["id"])}" '
            f'data-cat="{html.escape(p["cat"])}" data-model="{html.escape(p["model"])}" '
            f'data-flags="{html.escape(flag_str)}">'
            f'<div class="pair-head"><div><strong>{html.escape(p["id"])}</strong> '
            f'<span class="tag">{html.escape(p["cat"])}</span> '
            f'<span class="tag">{html.escape(p["model"])}</span></div><div>{pills}</div></div>'
            f'<div class="prompt-box">{html.escape(p["prompt"])}</div>{jline}'
            f'<div class="cols">'
            f'<div class="col"><div class="col-head">{html.escape(baseline)} '
            f'<span>smell={sb_smell} cv={sb_cv} spk={sb_spk}</span></div>'
            f'<pre>{_highlight_html(p["resp_base"])}</pre></div>'
            f'<div class="col"><div class="col-head">{html.escape(target)} '
            f'<span>smell={st_smell} cv={st_cv} spk={st_spk}</span></div>'
            f'<pre>{_highlight_html(p["resp_target"])}</pre></div>'
            f"</div></article>"
        )

    rerun_ids = ",".join(sorted(set(reg_ids)))
    safe_rerun = json.dumps(rerun_ids).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Unarmored Eval Report ({html.escape(baseline)} vs {html.escape(target)})</title>
<style>
:root {{ --bg:#0f172a; --card:#1e293b; --line:#334155; --fg:#e2e8f0; --muted:#94a3b8; }}
body {{ margin:0; padding:24px; background:var(--bg); color:var(--fg); font:14px/1.55 system-ui,-apple-system,Segoe UI,sans-serif; }}
h1,h2 {{ margin:0 0 12px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px; margin-bottom:18px; overflow-x:auto; }}
table {{ width:100%; border-collapse:collapse; font-size:12px; }}
th,td {{ border-bottom:1px solid var(--line); padding:6px 8px; text-align:left; white-space:nowrap; }}
th {{ color:var(--muted); }}
.filters {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-bottom:14px; }}
button,input {{ background:#0b1220; color:var(--fg); border:1px solid var(--line); border-radius:6px; padding:6px 10px; font-size:12px; }}
button {{ cursor:pointer; }}
button.active {{ background:#2563eb; border-color:#3b82f6; }}
.pair-card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px; margin-bottom:14px; }}
.pair-head {{ display:flex; justify-content:space-between; gap:8px; flex-wrap:wrap; margin-bottom:8px; }}
.tag {{ background:#0b1220; color:#93c5fd; padding:2px 7px; border-radius:4px; font-size:11px; }}
.pill {{ padding:2px 8px; border-radius:99px; font-size:11px; margin-left:4px; }}
.pill-ok {{ background:#14532d; color:#86efac; }}
.pill-bad {{ background:#7f1d1d; color:#fecaca; }}
.prompt-box {{ background:#0b1220; border-left:3px solid #38bdf8; padding:8px 10px; margin-bottom:10px; white-space:pre-wrap; }}
.judge-line {{ font-size:12px; color:#fde68a; margin-bottom:8px; }}
.cols {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
@media (max-width:900px) {{ .cols {{ grid-template-columns:1fr; }} }}
.col {{ background:#0b1220; border:1px solid var(--line); border-radius:8px; padding:10px; }}
.col-head {{ display:flex; justify-content:space-between; font-size:12px; color:var(--muted); margin-bottom:6px; }}
pre {{ margin:0; white-space:pre-wrap; word-break:break-word; font:13px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace; }}
mark.hl-high {{ background:#991b1b; color:#fff; padding:0 2px; border-radius:2px; }}
mark.hl-med {{ background:#854d0e; color:#fef9c3; padding:0 2px; border-radius:2px; }}
mark.hl-brake {{ background:#6b21a8; color:#f3e8ff; padding:0 2px; border-radius:2px; }}
.veto-box {{ background:#450a0a; border:1px solid #991b1b; border-radius:8px; padding:10px; margin-top:10px; font-size:12px; }}
.meta {{ color:var(--muted); font-size:12px; }}
</style>
</head>
<body>
<h1>Unarmored Eval Report: <code>{html.escape(baseline)}</code> vs <code>{html.escape(target)}</code></h1>
<section class="card"><h2>Summary Metrics</h2><table><thead><tr>{kpi_head}</tr></thead><tbody>{''.join(kpi_rows)}</tbody></table></section>
{judge_section}
<section class="card">
  <div class="filters">
    <button class="active" data-filter="all">All ({len(pairs)})</button>
    <button data-filter="reg">Regressions ({len(reg_ids)})</button>
    <button data-filter="flat_textbook">Flat Textbook</button>
    <button data-filter="overcorrection">Overcorrection</button>
    <button data-filter="judge_hard_veto">Hard Veto</button>
    <button data-filter="flipped_regressed">Flipped</button>
    <input id="q" placeholder="Search id / cat / text..." />
    <button id="copy-rerun">Copy regression --ids</button>
  </div>
  <div id="list">{''.join(cards_html)}</div>
</section>
<script>
const rerunIds = {safe_rerun};
let curFilter = "all";
const qEl = document.getElementById("q");
function applyFilters() {{
  const needle = (qEl.value || "").toLowerCase();
  for (const el of document.querySelectorAll(".pair-card")) {{
    const flags = (el.dataset.flags || "").split(" ").filter(Boolean);
    let ok = curFilter === "all" || (curFilter === "reg" ? flags.length > 0 : flags.includes(curFilter));
    if (ok && needle) ok = el.textContent.toLowerCase().includes(needle);
    el.style.display = ok ? "" : "none";
  }}
}}
for (const btn of document.querySelectorAll("button[data-filter]")) {{
  btn.addEventListener("click", () => {{
    document.querySelectorAll("button[data-filter]").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    curFilter = btn.dataset.filter;
    applyFilters();
  }});
}}
qEl.addEventListener("input", applyFilters);
document.getElementById("copy-rerun").addEventListener("click", () => {{
  const cmd = rerunIds ? "python eval/run.py --ids " + rerunIds : "No regressions flagged";
  if (navigator.clipboard) navigator.clipboard.writeText(cmd);
  alert(cmd);
}});
</script>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="report.py", description="Generate offline single-file HTML diff report for Unarmored eval runs.")
    p.add_argument("--results", type=Path, required=True, help="Path to results.jsonl")
    p.add_argument("--judge", type=Path, default=None, help="Optional judge JSON produced by eval/judge.py")
    p.add_argument("--baseline", default="bare")
    p.add_argument("--target", default="v07")
    p.add_argument("--out", type=Path, default=None, help="Output HTML path (default: sibling report.html)")
    p.add_argument("--export-regressions", type=Path, default=None, help="Optional JSONL path to export flagged regression items")
    args = p.parse_args(argv)

    rows = [json.loads(line) for line in args.results.read_text(encoding="utf-8").splitlines() if line.strip()]
    judge_data = json.loads(args.judge.read_text(encoding="utf-8")) if args.judge and args.judge.is_file() else None
    summary = S.aggregate(rows)
    pairs = classify_regressions(rows, args.baseline, args.target, judge_data=judge_data)
    out_html = args.out or (args.results.parent / "report.html")
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(render_html_report(summary, pairs, judge_data, args.baseline, args.target), encoding="utf-8")

    reg_rows = [pr for pr in pairs if pr["flags"]]
    if args.export_regressions:
        args.export_regressions.parent.mkdir(parents=True, exist_ok=True)
        with args.export_regressions.open("w", encoding="utf-8") as fh:
            for pr in reg_rows:
                fh.write(json.dumps({"id": pr["id"], "model": pr["model"], "cat": pr["cat"], "flags": pr["flags"], "prompt": pr["prompt"]}, ensure_ascii=False) + "\n")

    sys.stdout.write(json.dumps({"report": str(out_html), "pairs": len(pairs), "regressions": len(reg_rows)}, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
