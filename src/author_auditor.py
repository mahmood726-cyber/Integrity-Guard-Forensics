import os
import sys
import time

import requests

# Ensure src is on the path for sibling imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from fraud_lead_generator import FraudLeadGenerator
except ImportError:
    from .fraud_lead_generator import FraudLeadGenerator

PORTFOLIO_DISCLAIMER = (
    "WARNING: This is an automated screening tool. Portfolio analysis by name alone "
    "is unreliable due to name ambiguity, common names, and incomplete registry data. "
    "Results MUST be verified via ORCID or institutional affiliation before drawing "
    "any conclusions. False positives are expected."
)


def audit_author_portfolio(author_name: str):
    # Print disclaimer at the start of every audit
    print(f"\n{'='*60}")
    print(PORTFOLIO_DISCLAIMER)
    print(f"{'='*60}")
    print(f"\nInvestigating Career Portfolio: {author_name}")

    generator = FraudLeadGenerator()

    # Search for all trials by this author
    url = "https://clinicaltrials.gov/api/v2/studies"
    params = {
        "query.term": author_name,
        "pageSize": 50,
        "fields": "protocolSection.identificationModule.nctId,protocolSection.identificationModule.briefTitle"
    }

    try:
        # P1-12: Add timeout to requests
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        studies = response.json().get("studies", [])
        nct_ids = [s["protocolSection"]["identificationModule"]["nctId"] for s in studies]

        if not nct_ids:
            print(f"   No other trials found for {author_name}.")
            return

        print(f"   Found {len(nct_ids)} trials in portfolio. Running deep forensics...")
        leads = generator.scan_leads(nct_ids)

        if not leads:
            print(f"   Clean Portfolio: No statistical anomaly patterns found for {author_name}.")
        else:
            print(f"   ALERT: Found {len(leads)} trials with statistical anomalies in this author's portfolio.")
            for lead in leads:
                print(f"      - {lead['nctId']}: {lead['title']}")
                for a in lead['anomalies']:
                    print(f"         * {a}")

    except Exception as e:
        print(f"   Error auditing portfolio: {e}")

# P0-10: Remove hardcoded real researcher names
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python author_auditor.py <author_name> [author_name2 ...]")
        print("Example: python author_auditor.py \"Jane Doe\" \"John Smith\"")
        sys.exit(1)

    authors = sys.argv[1:]
    for author in authors:
        audit_author_portfolio(author)
        time.sleep(1)  # Rate limit friendly
