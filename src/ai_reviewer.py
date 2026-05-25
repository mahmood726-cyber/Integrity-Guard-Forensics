import argparse
import json
from datetime import datetime

from discrepancy_engine import DiscrepancyEngine
from utils import update_consensus, validate_report_schema


class AIReviewer:
    def __init__(self, report_path: str):
        self.report_path = report_path
        # P2-14: Add encoding='utf-8' to open()
        with open(self.report_path, encoding='utf-8') as f:
            self.report = json.load(f)
        validate_report_schema(self.report)
        self.engine = DiscrepancyEngine()

    def auto_review(self):
        print("[*] Initializing AI Auto-Reviewer (Heuristic NLP Model)...")
        discrepancies = self.report.get("discrepancy_results", {}).get("discrepancies", [])

        if not discrepancies:
            print("No discrepancies to review.")
            return

        for d in discrepancies:
            measure = d.get('publication_outcome') or d.get('protocol_outcome', '')
            d_type = d.get('type', '')

            # P0-15: When confidence is missing, don't default to 1.0 for auto-confirmation
            confidence_score = d.get("confidence")
            if confidence_score is None:
                status = "INCONCLUSIVE"
                comment = "AI Auto-Review: No confidence score available. Human review required."
            # P2-18: Don't blanket-dismiss adverse events.
            # Only auto-dismiss as FALSE_POSITIVE if it's "OUTCOME_ADDED" and a safety endpoint.
            # If "OUTCOME_MISSING" and safety-related, it might be selective omission — flag it.
            elif d_type == "OUTCOME_ADDED" and ("adverse events" in measure.lower() or "safety" in measure.lower()):
                status = "FALSE_POSITIVE"
                comment = "AI Auto-Review: Added safety endpoint is standard reporting practice."
            elif d_type == "OUTCOME_MISSING" and ("adverse events" in measure.lower() or "safety" in measure.lower()):
                status = "CONFIRMED"
                comment = "AI Auto-Review: Missing safety/adverse event data may indicate selective omission of safety outcomes. Human review strongly recommended."
            elif confidence_score > 0.8:
                status = "CONFIRMED"
                comment = f"AI Auto-Review: High confidence mismatch ({round(confidence_score*100)}%). This appears to be a genuine reporting discrepancy."
            else:
                status = "INCONCLUSIVE"
                comment = "AI Auto-Review: NLP similarity is borderline. Human review required."

            review = {
                "reviewer": "OpenClaw AI Assessor",
                "status": status,
                "comment": comment,
                "timestamp": datetime.now().isoformat()
            }
            d.setdefault("reviews", []).append(review)
            update_consensus(d)

        # P2-14: Add encoding='utf-8' to open()
        with open(self.report_path, 'w', encoding='utf-8') as f:
            json.dump(self.report, f, indent=2)

        print("[+] AI Auto-Review complete. Report updated.")

def main():
    parser = argparse.ArgumentParser(description="AI Auto-Reviewer for Integrity Reports.")
    parser.add_argument("--report", required=True, help="Path to the JSON report.")
    args = parser.parse_args()

    ai = AIReviewer(args.report)
    ai.auto_review()


if __name__ == "__main__":
    main()
