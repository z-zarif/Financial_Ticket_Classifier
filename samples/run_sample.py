"""Run the public sample cases through /analyze-ticket and dump responses.

Usage:
    python samples/run_sample.py [--base-url http://127.0.0.1:8000]

The script reads samples/sample_input.json, POSTs each case to
/analyze-ticket, and writes the array of responses to
samples/output/sample_output.json.

It first checks /health and aborts with a clear message if the server
is not reachable, so judges can quickly diagnose startup issues.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover — newer starlette deps
    import httpx2 as httpx


HERE = Path(__file__).resolve().parent
INPUT_FILE = HERE / "sample_input.json"
OUTPUT_DIR = HERE / "output"
OUTPUT_FILE = OUTPUT_DIR / "sample_output.json"


def _post_case(client: httpx.Client, base_url: str, case: dict) -> dict:
    name = case["name"]
    resp = client.post(f"{base_url}/analyze-ticket", json=case["request"])
    if resp.status_code != 200:
        return {
            "name": name,
            "request": case["request"],
            "error": True,
            "status_code": resp.status_code,
            "body": resp.text,
        }
    return {"name": name, "request": case["request"], "response": resp.json()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default=os.getenv("BASE_URL", "http://127.0.0.1:8000"),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
    )
    args = parser.parse_args()

    # Quick health check so judges get a clear failure if the server is down.
    with httpx.Client(timeout=args.timeout) as probe:
        try:
            h = probe.get(f"{args.base_url}/health")
        except httpx.HTTPError as exc:
            print(f"[!] Cannot reach {args.base_url}: {exc}", file=sys.stderr)
            return 2
        if h.status_code != 200:
            print(
                f"[!] /health returned {h.status_code}: {h.text}",
                file=sys.stderr,
            )
            return 2

    if not INPUT_FILE.exists():
        print(f"[!] Missing input file: {INPUT_FILE}", file=sys.stderr)
        return 1

    payload = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    cases = payload.get("cases", [])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    with httpx.Client(timeout=args.timeout) as client:
        for case in cases:
            print(f"-> {case['name']} ({case['request']['ticket_id']})")
            results.append(_post_case(client, args.base_url, case))

    OUTPUT_FILE.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"[+] Wrote {len(results)} responses to {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
