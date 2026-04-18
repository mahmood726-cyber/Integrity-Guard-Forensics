"""
Historical fraud pattern validation — converted to proper pytest tests.

Tests detection of known fraud patterns from landmark cases:
  - Fujii (172 retractions): impossibly perfect baseline similarity
  - GRIM inconsistency: mathematically impossible means
  - Boldt (89 retractions): linguistic over-confidence pattern
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from baseline_balance_engine import BaselineBalanceEngine
from linguistic_forensics import LinguisticForensics
from scientific_integrity_forensics import ScientificIntegrityForensics


def test_fujii_pattern_impossibly_perfect_baseline():
    """Fujii Pattern: groups nearly identical across all baseline variables.

    Yoshitaka Fujii fabricated data in 172 papers. Carlisle (2012) showed
    his baseline tables had sub-random similarity. The combined probability
    of his balance occurring naturally was astronomically small.
    """
    balance_engine = BaselineBalanceEngine()
    fujii_data = [
        {"m1": 45.1, "sd1": 5.2, "n1": 100, "m2": 45.1, "sd2": 5.2, "n2": 100},
        {"m1": 70.2, "sd1": 10.1, "n1": 100, "m2": 70.2, "sd2": 10.1, "n2": 100},
        {"m1": 165.4, "sd1": 8.5, "n1": 100, "m2": 165.4, "sd2": 8.5, "n2": 100},
    ]
    result = balance_engine.analyze_baseline_set(fujii_data)
    assert "ANOMALOUS" in result["status"], (
        f"Fujii pattern not detected: {result['status']}"
    )


def test_grim_inconsistency():
    """GRIM Pattern: mean that is mathematically impossible for the given N.

    Brown & Heathers (2016): for integer-count data, mean * N must round
    to an integer. Mean 2.11 with N=10 gives 21.1, which is impossible.
    """
    forensics = ScientificIntegrityForensics()
    result = forensics.grim_test(2.11, 10, 2, data_type="integer_count")
    assert result["status"] == "INCONSISTENT", (
        f"GRIM inconsistency not detected: {result['status']}"
    )


def test_boldt_pattern_linguistic_hyperbole():
    """Boldt Pattern: extreme promotional language without uncertainty.

    Joachim Boldt (89 retractions) used unusually promotional language.
    Retraction Watch and linguistic forensic studies identified this as
    a marker of fraudulent papers.
    """
    ling_forensics = LinguisticForensics()
    boldt_text = (
        "This groundbreaking and revolutionary study robustly demonstrates "
        "a unique and miraculous landmark effect that is dramatically superior "
        "to any previous exceptional trial."
    )
    result = ling_forensics.analyze_text(boldt_text)
    assert "SUSPICIOUS" in result["status"], (
        f"Boldt hyperbole not detected: {result['status']}"
    )
