from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.agent import run_agent  # noqa: E402
from app.schemas import AgentRequest, AgentResponse, ErrorResponse  # noqa: E402


def keyword_hit(response: AgentResponse, expected_keywords: list[str]) -> float:
    if not expected_keywords:
        return 1.0
    text = (response.answer + "\n" + "\n".join(p.title + " " + p.summary for p in response.papers)).lower()
    hits = sum(1 for kw in expected_keywords if kw.lower() in text)
    return hits / len(expected_keywords)


def main() -> None:
    cases_path = ROOT / "eval" / "eval_cases.jsonl"
    cases = [json.loads(line) for line in cases_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    results = []
    for case in cases:
        started = time.perf_counter()
        req = AgentRequest(**case["request"])
        result = run_agent(req)
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        should_block = bool(case.get("should_block"))

        checks = {}
        if should_block:
            checks["blocked_as_expected"] = isinstance(result, ErrorResponse)
        else:
            checks["not_blocked"] = isinstance(result, AgentResponse)
            if isinstance(result, AgentResponse):
                checks["schema_valid"] = True
                checks["has_tool_calls"] = len(result.tool_calls) >= 2
                checks["has_sources"] = all(str(p.url).startswith("http") for p in result.papers)
                checks["min_papers"] = len(result.papers) >= min(req.max_papers, 1)
                checks["keyword_coverage"] = keyword_hit(result, case.get("expected_keywords", [])) >= 0.5
                checks["latency_under_20s"] = latency_ms < 20_000
            else:
                checks.update({
                    "schema_valid": False,
                    "has_tool_calls": False,
                    "has_sources": False,
                    "min_papers": False,
                    "keyword_coverage": False,
                    "latency_under_20s": latency_ms < 20_000,
                })

        passed = all(checks.values())
        results.append({"case": case["name"], "passed": passed, "latency_ms": latency_ms, "checks": checks})

    print("\nOpenResearch Scout Agent: mini evaluation report")
    print("=" * 55)
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"{status} | {r['case']} | latency={r['latency_ms']} ms | checks={r['checks']}")

    passed_count = sum(1 for r in results if r["passed"])
    print("-" * 55)
    print(f"Passed {passed_count}/{len(results)} cases")
    if passed_count != len(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
