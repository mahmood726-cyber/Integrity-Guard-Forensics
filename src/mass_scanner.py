import argparse
import json
import os
import sys
import time

import requests

# Ensure we use UTF-8 for output if possible to avoid charmap errors
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Ensure src is on the path for sibling imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from fraud_lead_generator import FraudLeadGenerator
except ImportError:
    from .fraud_lead_generator import FraudLeadGenerator

class MassScanner:
    """
    Designed to page through the entirety of the ClinicalTrials.gov v2 API.
    """
    BASE_URL = "https://clinicaltrials.gov/api/v2/studies"

    def __init__(self, output_file: str = "massive_fraud_leads.jsonl"):
        self.generator = FraudLeadGenerator()
        self.output_file = output_file

    def scan_all(self, max_trials: int = None):
        """
        Pages through the API. If max_trials is None, it scans until the end.
        """
        print("[*] Initializing Mass Scan of ClinicalTrials.gov...")
        print(f"[*] Saving active leads to: {self.output_file}")

        # Target: Trials with results.
        term = "AREA[HasResults]true"

        params = {
            "query.term": term,
            "pageSize": 100,
            "fields": "protocolSection.identificationModule.nctId,protocolSection.designModule.designInfo.allocation"
        }

        trials_processed = 0
        leads_found = 0
        page_token = None
        # P0-13: Max retry counter for network errors
        max_retries = 5
        consecutive_errors = 0

        with open(self.output_file, 'a', encoding='utf-8') as f:
            while True:
                if page_token:
                    params["pageToken"] = page_token

                try:
                    response = requests.get(self.BASE_URL, params=params, timeout=30)
                    response.raise_for_status()
                    data = response.json()
                    # Reset error counter on success
                    consecutive_errors = 0
                except requests.exceptions.RequestException as e:
                    consecutive_errors += 1
                    if consecutive_errors >= max_retries:
                        print(f"[!] Max retries ({max_retries}) exceeded. Stopping scan.")
                        break
                    print(f"[!] Network error ({consecutive_errors}/{max_retries}): {e}. Retrying in 10s...")
                    time.sleep(10)
                    continue

                studies = data.get("studies", [])
                if not studies:
                    break

                # Filter for Randomized in this batch
                nct_ids = []
                for s in studies:
                    allocation = s.get("protocolSection", {}).get("designModule", {}).get("designInfo", {}).get("allocation")
                    if allocation == "RANDOMIZED":
                        nct_ids.append(s["protocolSection"]["identificationModule"]["nctId"])

                if nct_ids:
                    print(f"\n[+] Batch Progress: {trials_processed} trials scanned globally...")
                    # Scan the batch
                    leads = self.generator.scan_leads(nct_ids)

                    for lead in leads:
                        if lead["score"] > 0:
                            f.write(json.dumps(lead) + "\n")
                            f.flush()
                            leads_found += 1

                trials_processed += len(studies)

                if max_trials and trials_processed >= max_trials:
                    print(f"\n[!] Reached specified limit of {max_trials} trials.")
                    break

                page_token = data.get("nextPageToken")
                if not page_token:
                    print("\n[+] Reached the end of the ClinicalTrials.gov database.")
                    break

                time.sleep(0.5)

        print("\n" + "="*50)
        print("[*] MASS SCAN COMPLETE")
        print(f"    Total Trials Evaluated: {trials_processed}")
        print(f"    Total Anomaly Leads Saved: {leads_found}")
        print(f"    Output File: {self.output_file}")
        # P1-8: Note about multiple testing
        print(f"    NOTE: With {trials_processed} trials tested, approximately {max(1, trials_processed // 10000)} false positives are statistically expected.")
        print("="*50)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mass CT.gov Forensic Scanner")
    parser.add_argument("--max", type=int, default=None, help="Maximum number of trials to scan.")
    parser.add_argument("--out", type=str, default="massive_fraud_leads.jsonl", help="Output JSONL file.")
    args = parser.parse_args()

    scanner = MassScanner(output_file=args.out)
    scanner.scan_all(max_trials=args.max)
