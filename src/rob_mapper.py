import json
from typing import Any

# Domain routing map: discrepancy type → RoB 2.0 domain
_DOMAIN_ROUTING: dict[str, str] = {
    "SUB_RANDOM_BASELINE": "Domain 1",
    "ANOMALOUS_PATTERN": "Domain 1",
    "STATISTICAL_IMPOSSIBILITY": "Domain 4",
    "IMPLAUSIBLE_OUTCOME": "Domain 4",
    "OUTCOME_MISSING": "Domain 5",
    "OUTCOME_ADDED": "Domain 5",
    "HARKING_RISK": "Domain 5",
    "TIMEFRAME_CHANGED": "Domain 5",
    "P_HACKING_DETECTED": "Domain 5",
}

_DOMAIN_LABELS: dict[str, str] = {
    "Domain 1": "Bias arising from the randomization process",
    "Domain 4": "Bias in measurement of the outcome",
    "Domain 5": "Bias in selection of the reported result",
}

# Severity ordering for comparisons
_SEVERITY_ORDER = {"Low": 0, "Low (Human Verified)": 0, "Some Concerns": 1, "High": 2}


class RoBMapper:
    """
    Maps discrepancies to Cochrane Risk of Bias (RoB 2.0) domains.

    Supports multi-domain routing:
      - Domain 1: randomization issues
      - Domain 4: measurement issues
      - Domain 5: selective reporting
      - LINGUISTIC_HYPERBOLE → general flag (no specific domain)
    """
    def __init__(self):
        pass

    def _assess_single_domain(self, domain_discrepancies: list[dict[str, Any]], disputed_count: int) -> dict[str, Any]:
        """Assess a single domain given its filtered discrepancies."""
        if not domain_discrepancies and disputed_count == 0:
            return {
                "score": "Low",
                "color": "green",
                "justification": "No relevant discrepancies found for this domain."
            }

        # Check for High Risk indicators
        high_risk_reasons = []
        for d in domain_discrepancies:
            is_confirmed = d.get("consensus_status") == "CONFIRMED"

            if "HIGH SEVERITY" in d.get("clinical_reasoning", "") or is_confirmed:
                high_risk_reasons.append(
                    f"Confirmed discrepancy: {d.get('publication_outcome') or d.get('protocol_outcome')}"
                )

            if "HARKING_RISK" in d.get("type", ""):
                high_risk_reasons.append("Verified evidence of HARKing (outcome switching).")

        if high_risk_reasons:
            justification = "Significant discrepancies confirmed by multi-person review: " + " ".join(high_risk_reasons[:2])
            if disputed_count > 0:
                justification += f" ({disputed_count} additional disputed item(s) under review.)"
            return {
                "score": "High",
                "color": "red",
                "justification": justification,
            }

        # If only disputed items remain (no non-disputed active), floor is Some Concerns
        if disputed_count > 0:
            return {
                "score": "Some Concerns",
                "color": "yellow",
                "justification": f"{disputed_count} disputed discrepancy(ies) require further review. "
                                 "Assessment floored at 'Some Concerns' until resolved.",
            }

        if domain_discrepancies:
            return {
                "score": "Some Concerns",
                "color": "yellow",
                "justification": "Minor discrepancies found that remain under review or lack full consensus.",
            }

        return {
            "score": "Low",
            "color": "green",
            "justification": "No significant discrepancies for this domain.",
        }

    def assess(self, discrepancies: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Multi-domain Risk of Bias assessment.

        Routes each discrepancy to the appropriate RoB 2.0 domain and
        returns per-domain assessments plus an overall score (worst-of).

        DISPUTED discrepancies are kept (floor = 'Some Concerns').
        Only FALSE_POSITIVE discrepancies are excluded.
        """
        if not discrepancies:
            return {
                "overall": {
                    "score": "Low",
                    "color": "green",
                    "justification": "The reported outcomes match the registered protocol perfectly.",
                },
                "domains": {},
            }

        # Filter: only exclude FALSE_POSITIVE
        active_discrepancies = [
            d for d in discrepancies
            if d.get("consensus_status") != "FALSE_POSITIVE"
        ]

        if not active_discrepancies:
            return {
                "overall": {
                    "score": "Low (Human Verified)",
                    "color": "green",
                    "justification": "Discrepancies were identified by AI but dismissed as non-significant by human reviewers.",
                },
                "domains": {},
            }

        # Separate disputed items
        disputed = [d for d in active_discrepancies if d.get("consensus_status") == "DISPUTED"]
        non_disputed = [d for d in active_discrepancies if d.get("consensus_status") != "DISPUTED"]

        # Route to domains
        domain_buckets: dict[str, list[dict[str, Any]]] = {}
        domain_disputed_counts: dict[str, int] = {}
        general_flags: list[dict[str, Any]] = []

        for d in non_disputed:
            dtype = d.get("type", "")
            domain = _DOMAIN_ROUTING.get(dtype)
            if domain is None:
                # LINGUISTIC_HYPERBOLE or unknown → general flag
                general_flags.append(d)
            else:
                domain_buckets.setdefault(domain, []).append(d)

        for d in disputed:
            dtype = d.get("type", "")
            domain = _DOMAIN_ROUTING.get(dtype, "Domain 5")  # default disputed to Domain 5
            domain_disputed_counts[domain] = domain_disputed_counts.get(domain, 0) + 1
            # Also ensure the domain appears in the output
            domain_buckets.setdefault(domain, [])

        # Assess each domain
        all_domains = set(list(domain_buckets.keys()) + list(domain_disputed_counts.keys()))
        domain_results: dict[str, Any] = {}

        for domain in sorted(all_domains):
            items = domain_buckets.get(domain, [])
            disp_count = domain_disputed_counts.get(domain, 0)
            result = self._assess_single_domain(items, disp_count)
            result["label"] = _DOMAIN_LABELS.get(domain, domain)
            domain_results[domain] = result

        # Overall = worst of all domains
        worst_score = "Low"
        worst_color = "green"
        worst_justification_parts = []

        for domain, result in domain_results.items():
            if _SEVERITY_ORDER.get(result["score"], 0) > _SEVERITY_ORDER.get(worst_score, 0):
                worst_score = result["score"]
                worst_color = result["color"]
            worst_justification_parts.append(f"{domain} ({result['label']}): {result['score']}")

        if general_flags:
            worst_justification_parts.append(
                f"General flags: {len(general_flags)} item(s) (e.g., linguistic hyperbole)"
            )

        overall_justification = "; ".join(worst_justification_parts)

        return {
            "overall": {
                "score": worst_score,
                "color": worst_color,
                "justification": overall_justification,
            },
            "domains": domain_results,
        }

    def assess_domain_5(self, discrepancies: list[dict[str, Any]]) -> dict[str, Any]:
        """Backwards-compatible alias: returns the overall assessment from assess()."""
        result = self.assess(discrepancies)
        return result["overall"]


if __name__ == "__main__":
    mapper = RoBMapper()
    # Test High Risk
    test_d = [{"type": "HARKING_RISK: OUTCOME_ADDED", "clinical_reasoning": "⚠️ HIGH SEVERITY: ..."}]
    print(json.dumps(mapper.assess_domain_5(test_d), indent=2))
    # Test multi-domain
    test_multi = [
        {"type": "ANOMALOUS_PATTERN", "clinical_reasoning": "⚠️ HIGH SEVERITY: ...", "protocol_outcome": "baseline imbalance"},
        {"type": "OUTCOME_MISSING", "clinical_reasoning": "MEDIUM SEVERITY: ...", "protocol_outcome": "OS"},
        {"type": "OUTCOME_MISSING", "clinical_reasoning": "...", "protocol_outcome": "PFS", "consensus_status": "DISPUTED"},
    ]
    print(json.dumps(mapper.assess(test_multi), indent=2))
