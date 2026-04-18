import json
from datetime import datetime
from typing import Dict, Any, List

from utils import TOOL_DISCLAIMER


class ScientificInquiryGenerator:
    """
    Drafts a formal 'Letter to the Editor' based on detected reporting bias.
    """
    def __init__(self, report_data: Dict[str, Any]):
        self.report = report_data
        self.nct_id = self.report.get("nctId", "NCTXXXXXXXX")
        self.citation = self.report.get("citation", "Unknown Journal Article")

    def generate_letter(self) -> str:
        discrepancies = self.report.get("discrepancy_results", {}).get("discrepancies", [])
        if not discrepancies:
            return "No discrepancies found. No letter required."

        date_str = datetime.now().strftime("%B %d, %Y")

        # P0-9: Add "DRAFT" warning at the top
        letter = "DRAFT -- NOT FOR EXTERNAL USE WITHOUT EXPERT REVIEW\n"
        letter += "=" * 55 + "\n"

        letter += f"""
Dear Editor,

We are writing to comment on the reporting of primary outcomes in '{self.citation}' ({self.nct_id}).

Our automated screening tool identified potential reporting discrepancies that may warrant further examination. We performed a cross-reference between the published results and the original registration in ClinicalTrials.gov.

### Identified Discrepancies:
"""
        for idx, d in enumerate(discrepancies):
            m = d.get('publication_outcome') or d.get('protocol_outcome', 'Unspecified Outcome')
            letter += f"\n{idx+1}. **{d['type']}**: '{m}'"
            letter += f"\n   * Finding: {d['reason']}"
            if "clinical_reasoning" in d:
                letter += f"\n   * Clinical Impact: {d['clinical_reasoning']}"
            letter += "\n"

        letter += f"""
These findings raise concerns regarding potential reporting bias, specifically Domain 5 of the Cochrane Risk of Bias (RoB 2.0) framework: 'Bias in selection of the reported result'.

Transparency is the cornerstone of evidence-based medicine. We would welcome a response from the authors explaining why these specific outcomes were added or omitted post-registration, and whether these changes were pre-specified in an internal statistical analysis plan (SAP).

Our full audit, including cryptographic TruthCert proof for all evidence locators, is available upon request.

Sincerely,

OpenClaw Automated Audit Agent
On behalf of the TruthCert Meta-Research Project

---
{TOOL_DISCLAIMER}
"""
        return letter

if __name__ == "__main__":
    # Test with mock data
    mock_report = {
        "nctId": "NCT04458623",
        "citation": "Impact of Intervention X on Patient Outcome Y. Journal of Medicine.",
        "discrepancy_results": {
            "discrepancies": [
                {
                    "type": "OUTCOME_MISSING",
                    "protocol_outcome": "Overall Survival",
                    "reason": "Omitted in pub",
                    "clinical_reasoning": "HIGH SEVERITY: A hard clinical endpoint was registered but omitted."
                }
            ]
        }
    }
    gen = ScientificInquiryGenerator(mock_report)
    print(gen.generate_letter())
