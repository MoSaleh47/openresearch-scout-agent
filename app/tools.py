from __future__ import annotations

import math
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests

from .schemas import Paper, ToolCall, CostReport
from .sample_data import SAMPLE_PAPERS

ARXIV_API = "https://export.arxiv.org/api/query"
STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "for", "to", "in", "on", "with", "by", "from", "is", "are", "as",
    "using", "use", "based", "agent", "agents", "ai", "llm", "llms", "model", "models", "study", "paper",
}


@dataclass
class ToolResult:
    value: Any
    call: ToolCall


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


def extract_keywords(text: str) -> list[str]:
    terms = re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{2,}", text.lower())
    unique: list[str] = []
    for term in terms:
        if term not in STOPWORDS and term not in unique:
            unique.append(term)
    return unique[:12]


def arxiv_search_tool(query: str, max_results: int = 8, year_from: int | None = None) -> ToolResult:
    """Search arXiv and return normalized paper dictionaries."""
    start = time.perf_counter()
    search_query = f"all:{query}"
    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    url = f"{ARXIV_API}?{urllib.parse.urlencode(params)}"

    papers: list[dict[str, Any]] = []
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
        for entry in root.findall("atom:entry", ns):
            title = " ".join((entry.findtext("atom:title", default="", namespaces=ns) or "").split())
            summary = " ".join((entry.findtext("atom:summary", default="", namespaces=ns) or "").split())
            published = entry.findtext("atom:published", default=None, namespaces=ns)
            year = None
            if published:
                try:
                    year = datetime.fromisoformat(published.replace("Z", "+00:00")).year
                except ValueError:
                    year = None
            if year_from and year and year < year_from:
                continue
            authors = [a.findtext("atom:name", default="", namespaces=ns) for a in entry.findall("atom:author", ns)]
            authors = [a for a in authors if a]
            paper_url = entry.findtext("atom:id", default="", namespaces=ns)
            arxiv_id = paper_url.rstrip("/").split("/")[-1] if paper_url else None
            papers.append(
                {
                    "title": title,
                    "authors": authors[:8],
                    "summary": summary,
                    "published": published,
                    "year": year,
                    "url": paper_url,
                    "arxiv_id": arxiv_id,
                }
            )
        success = True
        out = f"Found {len(papers)} candidate papers from arXiv."
    except Exception as exc:  # noqa: BLE001 - explicit error is returned in tool call
        success = False
        out = f"arXiv search failed: {type(exc).__name__}: {exc}"

    if not papers:
        fallback_terms = extract_keywords(query)
        fallback = []
        for item in SAMPLE_PAPERS:
            text = f"{item['title']} {item['summary']}".lower()
            if not fallback_terms or any(term in text for term in fallback_terms):
                if year_from and item.get("year") and item["year"] < year_from:
                    continue
                fallback.append(item)
        papers = fallback[:max_results]
        if papers:
            out = f"External arXiv search returned no usable results or failed; using {len(papers)} bundled fallback records for demo reliability."

    return ToolResult(
        papers,
        ToolCall(
            name="arxiv_search",
            input={"query": query, "max_results": max_results, "year_from": year_from},
            output_summary=out,
            latency_ms=_elapsed_ms(start),
            success=success,
        ),
    )


def rank_papers_tool(query: str, papers: list[dict[str, Any]], limit: int = 5) -> ToolResult:
    """Rank papers with transparent keyword overlap and recency weighting."""
    start = time.perf_counter()
    query_terms = extract_keywords(query)
    current_year = datetime.utcnow().year
    ranked: list[Paper] = []

    for paper in papers:
        text = f"{paper.get('title', '')} {paper.get('summary', '')}".lower()
        matched = [term for term in query_terms if term in text]
        overlap = len(matched) / max(len(query_terms), 1)
        year = paper.get("year")
        recency = 0.0
        if isinstance(year, int):
            recency = max(0.0, 1.0 - min(current_year - year, 10) / 10)
        # Keep ranking simple and explainable.
        score = round(min(1.0, 0.75 * overlap + 0.25 * recency), 3)
        ranked.append(
            Paper(
                title=paper.get("title", "Untitled"),
                authors=paper.get("authors", []),
                year=year,
                published=paper.get("published"),
                summary=paper.get("summary", "")[:1200],
                url=paper.get("url", ""),
                arxiv_id=paper.get("arxiv_id"),
                relevance_score=score,
                matched_terms=matched,
            )
        )

    ranked.sort(key=lambda p: p.relevance_score, reverse=True)
    ranked = ranked[:limit]
    return ToolResult(
        ranked,
        ToolCall(
            name="paper_ranker",
            input={"query_terms": query_terms, "candidate_count": len(papers), "limit": limit},
            output_summary=f"Ranked {len(papers)} papers and kept top {len(ranked)}.",
            latency_ms=_elapsed_ms(start),
            success=True,
        ),
    )


def cost_estimator_tool(query: str, papers: list[Paper]) -> ToolResult:
    """Estimate token volume for the request and generated answer."""
    start = time.perf_counter()
    text = query + "\n" + "\n".join([p.title + " " + p.summary for p in papers])
    # Common rough estimate: about 4 chars/token in English technical text.
    estimated_input_tokens = math.ceil(len(text) / 4)
    estimated_output_tokens = 450 + 80 * len(papers)
    report = CostReport(
        estimated_input_tokens=estimated_input_tokens,
        estimated_output_tokens=estimated_output_tokens,
        estimated_total_tokens=estimated_input_tokens + estimated_output_tokens,
        note="Token estimate only. Actual cost depends on the selected inference provider/model and its live pricing.",
    )
    return ToolResult(
        report,
        ToolCall(
            name="cost_estimator",
            input={"paper_count": len(papers)},
            output_summary=f"Estimated {report.estimated_total_tokens} total tokens.",
            latency_ms=_elapsed_ms(start),
            success=True,
        ),
    )
