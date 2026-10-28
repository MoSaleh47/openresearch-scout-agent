from __future__ import annotations

import re
from .schemas import SafetyReport

# Lightweight, transparent guardrails for demo purposes.
# In a production system, add a classifier and more domain-specific policy rules.
BLOCKED_PATTERNS = {
    "credential_exfiltration": re.compile(r"\b(api[_-]?key|password|token|secret|private key)\b", re.I),
    "prompt_injection": re.compile(r"\b(ignore previous|reveal system|developer message|system prompt|jailbreak)\b", re.I),
    "malware_or_abuse": re.compile(r"\b(malware|phishing|exploit|ddos|keylogger|ransomware)\b", re.I),
    "personal_data_request": re.compile(r"\b(ssn|social security|credit card|passport number|phone number lookup)\b", re.I),
}

ALLOWED_RESEARCH_CONTEXT = re.compile(
    r"\b(detect|detection|defense|mitigation|survey|benchmark|safety|security|classification|analysis)\b",
    re.I,
)


def check_input_safety(query: str) -> SafetyReport:
    flags: list[str] = []
    for name, pattern in BLOCKED_PATTERNS.items():
        if pattern.search(query):
            flags.append(name)

    # Allow benign research around cybersecurity if clearly framed as analysis/defense.
    if "malware_or_abuse" in flags and ALLOWED_RESEARCH_CONTEXT.search(query):
        flags.remove("malware_or_abuse")

    if flags:
        return SafetyReport(
            allowed=False,
            reason="The request looks unsafe or asks for sensitive information. Try framing it as a benign research or defensive analysis topic.",
            flags=flags,
        )

    if len(query) < 3:
        return SafetyReport(allowed=False, reason="Query is too short.", flags=["too_short"])

    return SafetyReport(allowed=True, reason="ok", flags=[])


def sanitize_for_search(query: str) -> str:
    # Remove characters that tend to break external APIs while keeping useful scientific tokens.
    safe = re.sub(r"[^\w\s\-:().,+/]", " ", query, flags=re.UNICODE)
    safe = re.sub(r"\s+", " ", safe).strip()
    return safe[:300]
