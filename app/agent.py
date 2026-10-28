from __future__ import annotations

import time
from datetime import datetime, timezone

from .guardrails import check_input_safety, sanitize_for_search
from .monitoring import log_event, new_monitoring_id
from .schemas import AgentRequest, AgentResponse, ErrorResponse
from .tools import arxiv_search_tool, cost_estimator_tool, rank_papers_tool


def _compose_answer(query: str, papers) -> str:
    if not papers:
        return (
            "I could not find strong arXiv matches for this query. Try a narrower technical topic, "
            "add keywords, or lower the year filter."
        )

    lines = [
        f"Research brief for: {query}",
        "",
        "Best matching papers:",
    ]
    for idx, paper in enumerate(papers, start=1):
        authors = ", ".join(paper.authors[:3]) if paper.authors else "Unknown authors"
        if len(paper.authors) > 3:
            authors += " et al."
        year = paper.year or "n.d."
        matched = ", ".join(paper.matched_terms[:5]) if paper.matched_terms else "semantic/metadata match"
        lines.append(
            f"{idx}. {paper.title} ({year}) by {authors}. "
            f"Relevance={paper.relevance_score:.2f}. Matched terms: {matched}. Source: {paper.url}"
        )

    lines.extend(
        [
            "",
            "Suggested next step:",
            "Open the top 2 or 3 papers, check their methodology and limitations, then use the titles and abstracts to build a focused literature review table.",
        ]
    )
    return "\n".join(lines)


def run_agent(request: AgentRequest) -> AgentResponse | ErrorResponse:
    monitoring_id = new_monitoring_id()
    start = time.perf_counter()

    safety = check_input_safety(request.query)
    if not safety.allowed:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        log_event(
            {
                "monitoring_id": monitoring_id,
                "status": "blocked",
                "blocked": True,
                "flags": safety.flags,
                "latency_ms": latency_ms,
                "query_preview": request.query[:80],
            }
        )
        return ErrorResponse(error=safety.reason, safety=safety, monitoring_id=monitoring_id)

    tool_calls = []
    safe_query = sanitize_for_search(request.query)

    search = arxiv_search_tool(safe_query, max_results=max(request.max_papers * 2, 6), year_from=request.year_from)
    tool_calls.append(search.call)

    rank = rank_papers_tool(safe_query, search.value, limit=request.max_papers)
    tool_calls.append(rank.call)
    papers = rank.value

    cost = None
    if request.include_cost:
        cost_result = cost_estimator_tool(request.query, papers)
        tool_calls.append(cost_result.call)
        cost = cost_result.value

    answer = _compose_answer(request.query, papers)
    latency_ms = round((time.perf_counter() - start) * 1000, 2)

    log_event(
        {
            "monitoring_id": monitoring_id,
            "status": "ok",
            "blocked": False,
            "flags": safety.flags,
            "latency_ms": latency_ms,
            "papers_returned": len(papers),
            "tool_calls": [t.name for t in tool_calls],
            "estimated_total_tokens": cost.estimated_total_tokens if cost else None,
            "query_preview": request.query[:80],
        }
    )

    return AgentResponse(
        answer=answer,
        papers=papers,
        tool_calls=tool_calls,
        safety=safety,
        cost=cost,
        monitoring_id=monitoring_id,
        created_at=datetime.now(timezone.utc),
    )
