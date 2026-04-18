import json
import logging
from typing import List, Dict, Any, Optional
from difflib import SequenceMatcher

from clinical_synonyms import (
    clinical_similarity,
    detect_timeframe_change,
    classify_endpoint,
    HARD_ENDPOINTS,
    SURROGATE_ENDPOINTS,
)

logger = logging.getLogger(__name__)

class DiscrepancyEngine:
    def __init__(self):
        pass

    def string_similarity(self, a: str, b: str) -> float:
        """
        Returns a similarity ratio between two strings.
        """
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def clinical_match_score(self, a: str, b: str) -> float:
        """
        Returns a clinical-aware similarity score using abbreviation expansion,
        synonym canonicalization, and token-set matching.
        """
        return clinical_similarity(a, b)

    def analyze_impact(self, discrepancy: Dict[str, Any]):
        """
        Adds semantic clinical reasoning to the discrepancy.
        Detects 'Hard Endpoints' vs 'Surrogate Endpoints' switches
        using clinical_synonyms.classify_endpoint for robust matching.
        """
        measure = (discrepancy.get("protocol_outcome") or discrepancy.get("publication_outcome") or "")
        endpoint_class = classify_endpoint(measure)

        reasoning = ""
        if discrepancy["type"] == "OUTCOME_MISSING":
            if endpoint_class == "HARD":
                reasoning = "⚠️ HIGH SEVERITY: A hard clinical endpoint (e.g., mortality/survival) was registered but omitted from the publication. This is a primary sign of reporting bias."
            else:
                reasoning = "MEDIUM SEVERITY: A registered outcome was omitted. This may lead to an incomplete understanding of trial effects."

        elif discrepancy["type"] == "OUTCOME_ADDED":
            if endpoint_class == "SURROGATE":
                reasoning = "⚠️ HIGH SEVERITY: A surrogate or symptom-based endpoint was added post-registration. This is often done to find a 'p-significant' result when primary endpoints failed."
            else:
                reasoning = "LOW SEVERITY: A new outcome was reported. Ensure it was properly pre-specified in an internal statistical plan."

        elif discrepancy["type"] == "TIMEFRAME_CHANGED":
            reasoning = "MEDIUM SEVERITY: The outcome timeframe was changed between protocol registration and publication."

        if reasoning:
            discrepancy["clinical_reasoning"] = reasoning

    def compare_outcomes(self, protocol_outcomes: List[Dict[str, Any]], publication_outcomes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compares protocol outcomes vs publication outcomes.
        Returns a list of potential discrepancies with clinical reasoning.

        Uses clinical_match_score (abbreviation-aware, synonym-aware) with
        a 0.6 threshold, and detects timeframe changes on matched pairs.
        """
        discrepancies = []

        # Clinical-aware matching by description/measure
        matched_indices = set()
        # Track which protocol outcome matched each publication outcome
        match_pairs: List[tuple] = []  # (pub_measure, prot_idx, prot_measure, similarity)

        for pub_idx, pub_outcome in enumerate(publication_outcomes):
            pub_measure = pub_outcome.get("measure", "")
            best_match_idx = -1
            best_similarity = 0.0

            for prot_idx, prot_outcome in enumerate(protocol_outcomes):
                prot_measure = prot_outcome.get("measure", "")
                similarity = self.clinical_match_score(pub_measure, prot_measure)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match_idx = prot_idx

            if best_similarity > 0.6:
                # Likely a match
                matched_indices.add(best_match_idx)
                prot_measure = protocol_outcomes[best_match_idx].get("measure", "")
                match_pairs.append((pub_measure, best_match_idx, prot_measure, best_similarity))
            else:
                # Potential discrepancy: outcome reported in publication but not in protocol
                d = {
                    "type": "OUTCOME_ADDED",
                    "publication_outcome": pub_measure,
                    "confidence": 1.0 - best_similarity,
                    "reason": "This outcome appears in the publication but was not found in the original protocol."
                }
                self.analyze_impact(d)
                discrepancies.append(d)

        # Check matched pairs for timeframe changes
        for pub_measure, prot_idx, prot_measure, similarity in match_pairs:
            tf_warning = detect_timeframe_change(prot_measure, pub_measure)
            if tf_warning:
                d = {
                    "type": "TIMEFRAME_CHANGED",
                    "protocol_outcome": prot_measure,
                    "publication_outcome": pub_measure,
                    "confidence": 0.8,
                    "reason": tf_warning,
                }
                self.analyze_impact(d)
                discrepancies.append(d)

        # Check for outcomes in protocol but NOT in publication
        for prot_idx, prot_outcome in enumerate(protocol_outcomes):
            if prot_idx not in matched_indices:
                d = {
                    "type": "OUTCOME_MISSING",
                    "protocol_outcome": prot_outcome.get("measure", ""),
                    "confidence": 1.0,
                    "reason": "This outcome was registered in the protocol but is not reported in the publication."
                }
                self.analyze_impact(d)
                discrepancies.append(d)

        return {
            "discrepancies": discrepancies,
            "status": "PASS" if not discrepancies else "WARNING"
        }

if __name__ == "__main__":
    engine = DiscrepancyEngine()
    
    # Mock data
    protocol = [
        {"measure": "Overall Survival at 12 months"},
        {"measure": "Progression-free survival"}
    ]
    
    publication = [
        {"measure": "Overall Survival at 12 months"},
        {"measure": "Quality of Life Score"} # Added
    ]
    
    results = engine.compare_outcomes(protocol, publication)
    print(json.dumps(results, indent=2))
