import argparse
import json
import os
import sys
from datetime import datetime

# Ensure src is on the path for sibling imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ct_history_fetcher import CTHistoryFetcher
from discrepancy_engine import DiscrepancyEngine
from html_reporter import HTMLReporter
from utils import ensure_parent_dir


def main():
    parser = argparse.ArgumentParser(description="Evidence-Integrity-Guard: Automated QA for RCT reporting.")
    parser.add_argument("--bundle", type=str, required=True, help="Path to the TruthCert bundle JSON.")
    parser.add_argument("--output", type=str, default="report.json", help="Path to save the JSON report.")
    parser.add_argument("--html", type=str, default="report.html", help="Path to save the HTML dashboard.")

    args = parser.parse_args()

    try:
        with open(args.bundle, encoding="utf-8") as f:
            bundle_data = json.load(f)
    except Exception as e:
        print(f"Error loading bundle: {e}")
        return

    nct_id = bundle_data.get("nctId")
    if not nct_id:
        print("Error: Bundle does not contain an NCT ID.")
        return

    print(f"Processing Study: {nct_id}")
    print(f"Publication: {bundle_data.get('citation')}")

    fetcher = CTHistoryFetcher()
    print("Fetching protocol history from ClinicalTrials.gov (v2 API)...")

    history_list = fetcher.get_history_list(nct_id)
    if not history_list:
        print("Could not retrieve history. Falling back to latest version only.")
        latest_study_data = fetcher.get_study_version(nct_id)
        first_study_data = latest_study_data
    else:
        first_version_num = history_list[0].get("version")
        latest_version_num = history_list[-1].get("version")
        print(f"Fetching First Version ({first_version_num}) and Latest Version ({latest_version_num})...")
        first_study_data = fetcher.get_study_version(nct_id, first_version_num)
        latest_study_data = fetcher.get_study_version(nct_id, latest_version_num)

    if not latest_study_data:
        print("Error: Could not fetch latest study data from CT.gov.")
        return

    first_protocol_outcomes = fetcher.get_primary_outcomes(first_study_data)
    latest_protocol_outcomes = fetcher.get_primary_outcomes(latest_study_data)

    print(f"First Version Primary Outcomes: {len(first_protocol_outcomes)}")
    print(f"Latest Version Primary Outcomes: {len(latest_protocol_outcomes)}")

    publication_outcomes = bundle_data.get("extractedOutcomes", [])
    print(f"Publication Outcomes: {len(publication_outcomes)} extracted.")

    engine = DiscrepancyEngine()
    print("Running discrepancy checks...")

    harking_results = engine.compare_outcomes(first_protocol_outcomes, latest_protocol_outcomes)
    harking_discrepancies = []
    for d in harking_results["discrepancies"]:
        # P1-23: Keep original type unchanged; add separate harking_risk flag
        d["harking_risk"] = True
        d["reason"] = "INTERNAL PROTOCOL CHANGE: " + d["reason"]
        harking_discrepancies.append(d)

    pub_results = engine.compare_outcomes(latest_protocol_outcomes, publication_outcomes)

    all_discrepancies = harking_discrepancies + pub_results["discrepancies"]
    overall_status = "WARNING" if all_discrepancies else "PASS"

    for d in all_discrepancies:
        d["reviews"] = []
        d["consensus_status"] = "PENDING"

    report = {
        "nctId": nct_id,
        "citation": bundle_data.get("citation"),
        "timestamp": datetime.now().strftime("%Y-%m-%d"),
        "protocol_summary": {
            "firstVersionOutcomes": first_protocol_outcomes,
            "latestVersionOutcomes": latest_protocol_outcomes,
        },
        "publication_summary": {"reportedOutcomes": publication_outcomes},
        "discrepancy_results": {"status": overall_status, "discrepancies": all_discrepancies},
    }

    ensure_parent_dir(args.output)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\nJSON Report saved to {args.output}")
    print("-" * 40)
    print(f"Status: {overall_status}")
    for d in all_discrepancies:
        print(f"- [{d['type']}] {d.get('publication_outcome', d.get('protocol_outcome', ''))}: {d['reason']}")

    try:
        ensure_parent_dir(args.html)
        HTMLReporter(args.output, args.html).generate()
    except Exception as e:
        print(f"Failed to generate HTML dashboard: {e}")


if __name__ == "__main__":
    main()
