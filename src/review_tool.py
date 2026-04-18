import json
import argparse
from datetime import datetime
from typing import Dict, Any, List

from utils import update_consensus, validate_report_schema


class ReviewTool:
    def __init__(self, report_path: str):
        self.report_path = report_path
        self.report = self._load_report()

    def _load_report(self) -> Dict[str, Any]:
        with open(self.report_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        validate_report_schema(data)
        return data

    def _save_report(self):
        with open(self.report_path, 'w', encoding='utf-8') as f:
            json.dump(self.report, f, indent=2)

    def add_review_interactive(self, reviewer_name: str):
        """
        Interactively walk through discrepancies and add a review.
        """
        discrepancies = self.report.get("discrepancy_results", {}).get("discrepancies", [])
        if not discrepancies:
            print("No discrepancies found to review.")
            return

        print(f"--- Multi-Person Review: {reviewer_name} ---")
        for i, d in enumerate(discrepancies):
            # P2-6: Fix display to 1-based, "X of Y" format
            print(f"\nDiscrepancy {i + 1} of {len(discrepancies)}:")
            print(f"Type: {d.get('type', 'Unknown')}")
            print(f"Measure: {d.get('publication_outcome', d.get('protocol_outcome', ''))}")
            print(f"Reason: {d.get('reason', '')}")

            # Show existing reviews safely
            reviews = d.setdefault("reviews", [])
            if reviews:
                print("Existing Reviews:")
                for r in reviews:
                    print(f"  - {r.get('reviewer', 'Unknown')}: {r.get('status', 'PENDING')} ({r.get('comment', '')})")

            # P2-7: Input validation loop for status
            valid_codes = {"C", "F", "I"}
            status_map = {"C": "CONFIRMED", "F": "FALSE_POSITIVE", "I": "INCONCLUSIVE"}
            while True:
                status_input = input("Status (C=Confirmed, F=False Positive, I=Inconclusive) [C]: ").strip().upper() or "C"
                if status_input in valid_codes:
                    break
                print(f"Invalid input '{status_input}'. Please enter C, F, or I.")
            status = status_map[status_input]

            comment = input("Comment: ")

            review = {
                "reviewer": reviewer_name,
                "status": status,
                "comment": comment,
                "timestamp": datetime.now().isoformat()
            }

            reviews.append(review)
            update_consensus(d)

        self._save_report()
        print("\nReview session complete. Report updated.")

    def add_review_non_interactive(self, reviewer_name: str, discrepancy_idx: int, status_code: str, comment: str):
        discrepancies = self.report.get("discrepancy_results", {}).get("discrepancies", [])
        if not discrepancies:
            print("No discrepancies found.")
            return

        if discrepancy_idx < 0 or discrepancy_idx >= len(discrepancies):
            print(f"Invalid discrepancy index. Must be between 0 and {len(discrepancies)-1}")
            return

        d = discrepancies[discrepancy_idx]
        status_map = {"C": "CONFIRMED", "F": "FALSE_POSITIVE", "I": "INCONCLUSIVE"}
        status = status_map.get(status_code.upper(), "CONFIRMED")

        review = {
            "reviewer": reviewer_name,
            "status": status,
            "comment": comment,
            "timestamp": datetime.now().isoformat()
        }

        d.setdefault("reviews", []).append(review)
        update_consensus(d)
        self._save_report()
        print(f"Added review for discrepancy {discrepancy_idx}. Consensus is now {d.get('consensus_status', 'PENDING')}.")

def main():
    parser = argparse.ArgumentParser(description="Review tool for Evidence-Integrity-Guard reports.")
    parser.add_argument("--report", type=str, required=True, help="Path to the report JSON.")
    parser.add_argument("--name", type=str, required=True, help="Reviewer name.")
    parser.add_argument("--idx", type=int, help="Discrepancy index for non-interactive mode.")
    parser.add_argument("--status", type=str, choices=['C', 'F', 'I'], help="Status: C/F/I")
    parser.add_argument("--comment", type=str, default="", help="Review comment")

    args = parser.parse_args()

    tool = ReviewTool(args.report)

    if args.idx is not None and args.status is not None:
        tool.add_review_non_interactive(args.name, args.idx, args.status, args.comment)
    else:
        tool.add_review_interactive(args.name)


if __name__ == "__main__":
    main()
