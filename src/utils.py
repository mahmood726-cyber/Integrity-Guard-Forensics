"""
Shared utilities for Evidence-Integrity-Guard.

Centralizes functions that were duplicated across modules:
  - ensure_parent_dir (was in main.py AND openclaw_pipeline.py)
  - update_consensus (was in review_tool.py AND ai_reviewer.py)
  - validate_nct_id
"""

import os
import re
from typing import Any


def ensure_parent_dir(path: str):
    """Create parent directories for a file path if they don't exist."""
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def update_consensus(discrepancy: dict[str, Any]):
    """Robust consensus logic for Human-AI collaboration.

    States: PENDING → IN_PROGRESS → CONFIRMED / FALSE_POSITIVE / DISPUTED
    """
    reviews = discrepancy.get("reviews", [])
    if not reviews:
        discrepancy["consensus_status"] = "PENDING"
        return

    statuses = [r["status"] for r in reviews]

    if all(s == "CONFIRMED" for s in statuses):
        discrepancy["consensus_status"] = "CONFIRMED"
    elif all(s == "FALSE_POSITIVE" for s in statuses):
        discrepancy["consensus_status"] = "FALSE_POSITIVE"
    elif any(s == "FALSE_POSITIVE" for s in statuses) and any(s == "CONFIRMED" for s in statuses):
        discrepancy["consensus_status"] = "DISPUTED"
    else:
        discrepancy["consensus_status"] = "IN_PROGRESS"


_NCT_PATTERN = re.compile(r'^NCT\d{8,11}$')


def validate_nct_id(nct_id: str) -> bool:
    """Validate that a string is a properly formatted NCT ID."""
    return bool(_NCT_PATTERN.match(nct_id))


def validate_report_schema(data: dict) -> None:
    """Lightweight schema check for report JSON files.

    Raises ValueError if the structure is invalid.
    """
    results = data.get("discrepancy_results")
    if not isinstance(results, dict):
        raise ValueError("Invalid report: 'discrepancy_results' must be a dict")
    discs = results.get("discrepancies")
    if not isinstance(discs, list):
        raise ValueError("Invalid report: 'discrepancies' must be a list")


# Standard disclaimer for all outputs
TOOL_DISCLAIMER = (
    "DISCLAIMER: This is an automated screening tool. Statistical anomalies "
    "do not constitute evidence of fraud or misconduct. All findings require "
    "independent expert human review before any conclusions are drawn. "
    "False positives are expected; no automated tool can determine intent."
)
