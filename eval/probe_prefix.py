"""Probe whether an OpenAI-compatible endpoint honours DeepSeek-style prefix completion with reasoning prefill.

Sends two requests to the same model and reports only status/shape facts (never the key, never full outputs):
  1. control: plain user turn
  2. probe:   same turn + trailing assistant message {"prefix": true, "reasoning_content": <steer>, "content": ""}

Interpretation:
  - probe HTTP error (400/422)  -> endpoint rejects prefix completion; reasoning prefill must stay off
  - probe OK                    -> fields were accepted; compare reasoning_preview against the control to judge
                                   whether the relay forwarded them or silently dropped them
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

STEER = "先把结论和证据定下来，定了就不为语气回头改，然后直接写给对方。"
QUESTION = "Redis 的默认端口号是多少？只回答数字和一句理由。"


def post(base: str, key: str, payload: dict, timeout: int) -> tuple[int, dict]:
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        return exc.code, {"error_excerpt": body}


def summarize(status: int, data: dict) -> dict:
    msg = ((data.get("choices") or [{}])[0].get("message") or {}) if isinstance(data, dict) else {}
    reasoning = str(msg.get("reasoning_content") or "")
    return {
        "status": status,
        "has_reasoning": bool(reasoning),
        "reasoning_preview": reasoning.strip()[:120],
        "content_preview": str(msg.get("content") or "")[:80],
        "error_excerpt": data.get("error_excerpt") if isinstance(data, dict) else None,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="probe_prefix.py")
    p.add_argument("--model", required=True)
    p.add_argument("--timeout", type=int, default=120)
    args = p.parse_args(argv)
    base = os.environ.get("UNARMORED_EVAL_BASE_URL", "")
    key = os.environ.get("UNARMORED_EVAL_API_KEY", "")
    if not base or not key:
        sys.stderr.write("Set UNARMORED_EVAL_BASE_URL and UNARMORED_EVAL_API_KEY first.\n")
        return 2
    user = {"role": "user", "content": QUESTION}
    control = summarize(*post(base, key, {"model": args.model, "messages": [user], "max_tokens": 300}, args.timeout))
    probe_payload = {
        "model": args.model,
        "messages": [user, {"role": "assistant", "content": "", "prefix": True, "reasoning_content": STEER}],
        "max_tokens": 300,
    }
    probe = summarize(*post(base, key, probe_payload, args.timeout))
    verdict = "rejected" if probe["status"] >= 400 else "accepted (compare reasoning_preview with control to judge whether the steer took effect)"
    sys.stdout.write(json.dumps({"model": args.model, "control": control, "probe": probe, "verdict": verdict}, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
