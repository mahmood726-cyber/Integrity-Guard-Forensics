import json
import logging
import requests
import argparse
import sys
import os
import time
from itertools import combinations
from typing import List, Dict, Any

# Ensure src is on the path for sibling imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from ct_history_fetcher import CTHistoryFetcher
    from discrepancy_engine import DiscrepancyEngine
    from scientific_integrity_forensics import ScientificIntegrityForensics
    from baseline_balance_engine import BaselineBalanceEngine
    from rob_mapper import RoBMapper
except ImportError:
    from .ct_history_fetcher import CTHistoryFetcher
    from .discrepancy_engine import DiscrepancyEngine
    from .scientific_integrity_forensics import ScientificIntegrityForensics
    from .baseline_balance_engine import BaselineBalanceEngine
    from .rob_mapper import RoBMapper

logger = logging.getLogger(__name__)


class FraudLeadGenerator:
    """
    Proactively searches CT.gov for suspicious patterns in recently posted results.
    Includes Duplicate Data Fingerprinting (Boldt Pattern).
    """
    BASE_URL = "https://clinicaltrials.gov/api/v2/studies"

    def __init__(self):
        self.fetcher = CTHistoryFetcher()
        self.forensics = ScientificIntegrityForensics()
        self.balance_engine = BaselineBalanceEngine()
        self.rob_mapper = RoBMapper()
        self.baseline_fingerprints = {} # (Mean, SD) -> NCT ID

    def find_recent_results(self, limit: int = 10, query: str = "") -> List[str]:
        """
        Target trials with results and filter for randomized in code.
        """
        term = "AREA[HasResults]true"
        if query:
            term += f" AND {query}"

        params = {
            "query.term": term,
            "pageSize": limit,
            "fields": "protocolSection.identificationModule.nctId,protocolSection.designModule.designInfo.allocation"
        }

        try:
            # P1-11/P1-12: Add timeout to requests
            response = requests.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            nct_ids = []
            for s in data.get("studies", []):
                allocation = s.get("protocolSection", {}).get("designModule", {}).get("designInfo", {}).get("allocation")
                if allocation == "RANDOMIZED":
                    nct_ids.append(s["protocolSection"]["identificationModule"]["nctId"])
            return nct_ids
        except (requests.exceptions.RequestException, ValueError, KeyError) as e:
            logger.warning(f"Error searching for leads: {e}")
            return []

    def extract_forensic_payload(self, study_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Improved extraction for multi-arm randomized trials.
        P1-7: Supports all arm pairs via itertools.combinations.
        P0-3: Skips variables with missing data instead of using defaults.
        """
        payload = {"baseline_data": [], "forensic_data": []}

        try:
            results = study_data.get("resultsSection", {})
            baseline_module = results.get("baselineCharacteristicsModule", {})
            measures = baseline_module.get("measures", [])

            group_ns = {}
            for denom in baseline_module.get("denoms", []):
                for count in denom.get("counts", []):
                    gid = count.get("groupId")
                    val = count.get("value")
                    if gid and val is not None:
                        try:
                            group_ns[gid] = int(val)
                        except (ValueError, TypeError):
                            pass

            for m in measures:
                if m.get("paramType") == "MEAN":
                    for c in m.get("classes", []):
                        for cat in c.get("categories", []):
                            measurements = cat.get("measurements", [])
                            if len(measurements) >= 2:
                                # P1-7: Multi-arm support — iterate over all pairs
                                pairs = list(combinations(range(len(measurements)), 2))
                                for i, j in pairs:
                                    g1 = measurements[i]
                                    g2 = measurements[j]

                                    # P0-3: Skip if required data is missing
                                    g1_val = g1.get("value")
                                    g1_spread = g1.get("spread")
                                    g2_val = g2.get("value")
                                    g2_spread = g2.get("spread")
                                    g1_gid = g1.get("groupId")
                                    g2_gid = g2.get("groupId")

                                    if g1_val is None or g1_spread is None:
                                        continue
                                    if g2_val is None or g2_spread is None:
                                        continue
                                    if g1_gid not in group_ns or g2_gid not in group_ns:
                                        continue

                                    try:
                                        payload["baseline_data"].append({
                                            "m1": float(g1_val),
                                            "sd1": float(g1_spread),
                                            "n1": group_ns[g1_gid],
                                            "m2": float(g2_val),
                                            "sd2": float(g2_spread),
                                            "n2": group_ns[g2_gid]
                                        })
                                    except (ValueError, TypeError):
                                        continue

        except (ValueError, KeyError, TypeError, IndexError) as e:
            logger.warning(f"Failed to extract forensic payload: {e}")

        return payload

    def scan_leads(self, nct_ids: List[str]):
        print(f"[*] Scanning {len(nct_ids)} trials for statistical anomaly patterns...")
        leads = []

        from datetime import datetime

        for nct_id in nct_ids:
            print(f"   Analyzing {nct_id}...")
            study_data = self.fetcher.get_study_version(nct_id)
            if not study_data:
                continue

            # Rate limiting between individual trial fetches
            time.sleep(0.3)

            # 0. Check for Design Context (Methodological Nuance)
            study_text = json.dumps(study_data).lower()
            is_adaptive = any(word in study_text for word in ["urn ", "minimization", "adaptive randomization", "stratified randomization"])

            payload = self.extract_forensic_payload(study_data)
            anomalies = []

            # 1. Run Carlisle-Bolt Balance Check
            if payload["baseline_data"]:
                balance = self.balance_engine.analyze_baseline_set(payload["baseline_data"])

                if balance["status"] == "MANIFEST_FRAUD_PATTERN":
                    if is_adaptive:
                        anomalies.append(f"[NOTE] DESIGN-EXPLAINED: Impossibly Perfect Baseline (Chance: 1 in {balance['one_in_x_chance']:,}). NOTE: Study uses adaptive/stratified design.")
                    else:
                        # P0-7: Replace inflammatory language
                        anomalies.append(f"[CRITICAL] STATISTICAL ANOMALY: Highly unusual baseline pattern (Chance: 1 in {balance['one_in_x_chance']:,})")
                elif balance["combined_probability"] < 0.01:
                    anomalies.append(f"[WARNING] EARLY WARNING: Unusual Baseline Balance (Chance: 1 in {balance['one_in_x_chance']:,})")

                # 2. Duplicate Data Fingerprint Check
                for b in payload["baseline_data"]:
                    fingerprint = (b["m1"], b["sd1"], b["m2"], b["sd2"])
                    if fingerprint in self.baseline_fingerprints and self.baseline_fingerprints[fingerprint] != nct_id:
                        # P0-7: Replace inflammatory language
                        anomalies.append(f"[CRITICAL] DATA SIMILARITY ALERT: Baseline fingerprint matches {self.baseline_fingerprints[fingerprint]}")
                    else:
                        self.baseline_fingerprints[fingerprint] = nct_id

            if anomalies:
                leads.append({
                    "nctId": nct_id,
                    "title": study_data.get("protocolSection", {}).get("identificationModule", {}).get("briefTitle"),
                    "anomalies": anomalies,
                    "score": len(anomalies)
                })
                print(f"      ALERT: {anomalies[0]}")

        return sorted(leads, key=lambda x: x["score"], reverse=True)

if __name__ == "__main__":
    generator = FraudLeadGenerator()
    # Batch scan 100 trials for duplicate data or sub-random patterns
    ids = generator.find_recent_results(limit=100)
    leads = generator.scan_leads(ids)

    print("\n" + "="*50)
    print("TOP STATISTICAL ANOMALY LEADS")
    print("="*50)
    if not leads:
        print("No critical anomalies found in this batch.")
    else:
        for i, lead in enumerate(leads):
            print(f"{i+1}. {lead['nctId']}: {lead['title']}")
            for a in lead['anomalies']:
                print(f"   - {a}")
    print("="*50)
