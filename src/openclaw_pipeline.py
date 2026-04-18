import argparse
import json
import os
import sys
from datetime import datetime

# Ensure src is on the path for sibling imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from baseline_balance_engine import BaselineBalanceEngine
from ct_history_fetcher import CTHistoryFetcher
from discrepancy_engine import DiscrepancyEngine
from html_reporter import HTMLReporter
from inquiry_generator import ScientificInquiryGenerator
from linguistic_forensics import LinguisticForensics
from p_curve_analyzer import PCurveAnalyzer
from plausibility_engine import PlausibilityEngine
from rob_mapper import RoBMapper
from scientific_integrity_forensics import ScientificIntegrityForensics
from truthcert_builder import TruthCertBuilder
from utils import ensure_parent_dir


def run_pipeline():
    parser = argparse.ArgumentParser(description="OpenClaw: Verifiable Evidence Integrity Pipeline.")
    parser.add_argument("--bundle", required=True, help="Path to publication JSON.")
    parser.add_argument("--out-cert", default="truthcert_bundle.json", help="Path for TruthCert bundle.")
    parser.add_argument("--out-html", default="dashboard.html", help="Path for HTML dashboard.")
    parser.add_argument("--out-letter", default="letter_to_editor.md", help="Path for inquiry letter.")
    parser.add_argument("--out-report", default="report.json", help="Path for the JSON report used by the UI.")

    args = parser.parse_args()

    # P1-21: Wrap file load with specific error handling
    try:
        with open(args.bundle, "r", encoding="utf-8") as f:
            pub_json = f.read()
            pub_data = json.loads(pub_json)
    except FileNotFoundError:
        print(f"[ERROR] Bundle file not found: {args.bundle}")
        return
    except json.JSONDecodeError as e:
        print(f"[ERROR] Bundle is not valid JSON: {e}")
        return

    # P1-21: Use .get() instead of bracket access for nct_id
    nct_id = pub_data.get("nctId")
    if not nct_id:
        print("[ERROR] Bundle does not contain an 'nctId' field.")
        return

    publication_outcomes = pub_data.get("extractedOutcomes")
    if not isinstance(publication_outcomes, list):
        print("[ERROR] Bundle must contain an 'extractedOutcomes' list.")
        return

    print(f"[*] Starting OpenClaw Deep Forensic Audit for {nct_id}")

    fetcher = CTHistoryFetcher()
    print("[*] Fetching Protocol and Registry Results from ClinicalTrials.gov...")
    study_data = fetcher.get_study_version(nct_id)
    protocol_json = json.dumps(study_data)

    protocol_outcomes = fetcher.get_primary_outcomes(study_data)
    registry_results_outcomes = fetcher.get_results_outcomes(study_data)

    engine = DiscrepancyEngine()
    print("[*] Running Semantic Discrepancy Analysis...")
    reference_outcomes = registry_results_outcomes if registry_results_outcomes else protocol_outcomes
    results = engine.compare_outcomes(reference_outcomes, publication_outcomes)

    print("[*] Running Deep Forensics (Baseline Balance, Monte Carlo, P-Curve)...")
    forensics = ScientificIntegrityForensics()
    p_analyzer = PCurveAnalyzer()
    ling_forensics = LinguisticForensics()
    balance_engine = BaselineBalanceEngine()
    plausibility_engine = PlausibilityEngine()

    forensic_alerts = []

    if "baseline_data" in pub_data:
        balance = balance_engine.analyze_baseline_set(pub_data["baseline_data"])
        if "SUSPICIOUS" in balance["status"] or "MANIFEST" in balance["status"]:
            reason = balance["reason"]
            if balance.get("sd_identical_count", 0) > 0:
                reason += f" (Note: {balance['sd_identical_count']} identical SDs found)"

            forensic_alerts.append(
                {
                    "type": "SUB_RANDOM_BASELINE",
                    "measure": "Baseline Table",
                    "reason": reason,
                }
            )

    if "outcome_data" in pub_data:
        od = pub_data["outcome_data"]
        plaus = plausibility_engine.run_simulation(od["m1"], od["sd1"], od["n1"], od["m2"], od["sd2"], od["n2"], od["p"])
        if "IMPLAUSIBLE" in plaus["status"]:
            forensic_alerts.append(
                {
                    "type": "IMPLAUSIBLE_OUTCOME",
                    "measure": "Primary Outcome",
                    "reason": plaus["reason"],
                }
            )

    if "forensic_data" in pub_data:
        for item in pub_data["forensic_data"]:
            grim = forensics.grim_test(item["mean"], item["n"], item.get("precision", 2))
            if grim["status"] == "INCONSISTENT":
                forensic_alerts.append(
                    {
                        "type": "STATISTICAL_IMPOSSIBILITY",
                        "measure": item["measure"],
                        "reason": grim["reason"],
                    }
                )

    if "reported_p_values" in pub_data:
        p_curve = p_analyzer.analyze_p_values(pub_data["reported_p_values"])
        if "SUSPICIOUS" in p_curve["status"]:
            forensic_alerts.append(
                {
                    "type": "P_HACKING_DETECTED",
                    "measure": "P-Value Distribution",
                    "reason": p_curve["reason"],
                }
            )

    if "abstract_text" in pub_data:
        ling = ling_forensics.analyze_text(pub_data["abstract_text"])
        if "SUSPICIOUS" in ling["status"]:
            forensic_alerts.append(
                {
                    "type": "LINGUISTIC_HYPERBOLE",
                    "measure": "Text Analysis",
                    "reason": ling["reason"],
                }
            )

    results["discrepancies"].extend(forensic_alerts)
    if forensic_alerts:
        results["status"] = "WARNING"
        print(f"   [!] FOUND {len(forensic_alerts)} DEEP FORENSIC ANOMALIES.")

    # P0-16: Do all discrepancy mutations FIRST, then compute RoB assessment ONCE
    for d in results["discrepancies"]:
        if "clinical_reasoning" in d:
            d["reason"] += " | CLINICAL IMPACT: " + d["clinical_reasoning"]
        d.setdefault("reviews", [])
        d.setdefault("consensus_status", "PENDING")

    print("[*] Mapping to Cochrane Risk of Bias 2.0 (Domain 5)...")
    rob_mapper = RoBMapper()
    rob_assessment = rob_mapper.assess_domain_5(results["discrepancies"])

    print("[*] Generating Verifiable TruthCert Bundle...")
    cert_builder = TruthCertBuilder(nct_id)
    cert_builder.add_evidence_source("CT_GOV_REGISTRY", protocol_json, f"https://clinicaltrials.gov/api/v2/studies/{nct_id}")
    cert_builder.add_evidence_source("PUBLICATION_EXTRACT", pub_json, args.bundle)

    for d in results["discrepancies"]:
        cert_builder.certify_discrepancy(d)

    bundle = cert_builder.build_bundle(results["status"])
    bundle["rob_assessment"] = rob_assessment

    ensure_parent_dir(args.out_cert)
    with open(args.out_cert, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2)

    print("[*] Drafting Scientific Inquiry Letter...")
    report_for_letter = {
        "nctId": nct_id,
        "citation": pub_data.get("citation"),
        "discrepancy_results": results,
    }
    letter_gen = ScientificInquiryGenerator(report_for_letter)
    letter_text = letter_gen.generate_letter()
    ensure_parent_dir(args.out_letter)
    with open(args.out_letter, "w", encoding="utf-8") as f:
        f.write(letter_text)

    report_path = args.out_report

    report_for_ui = {
        "nctId": nct_id,
        "citation": pub_data.get("citation"),
        "timestamp": datetime.now().strftime("%Y-%m-%d"),
        "discrepancy_results": results,
        "rob_assessment": rob_assessment,
    }

    ensure_parent_dir(report_path)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_for_ui, f, indent=2)

    print(f"[*] Standard Report saved to {report_path}")
    print("[*] Generating Clinical Dashboard...")
    ensure_parent_dir(args.out_html)
    HTMLReporter(report_path, args.out_html).generate()

    print(f"[*] Pipeline Complete. View results at: {args.out_html}")


if __name__ == "__main__":
    run_pipeline()
