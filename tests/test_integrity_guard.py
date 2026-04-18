"""
Comprehensive test suite for Evidence-Integrity-Guard.

Tests all core engines against known values, edge cases, and
historical fraud patterns (Fujii, Boldt, Sato).
"""

import json
import math
import os
import random
import sys
import pytest

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from ai_reviewer import AIReviewer
from baseline_balance_engine import BaselineBalanceEngine
from clinical_synonyms import (
    clinical_similarity,
    classify_endpoint,
    detect_timeframe_change,
)
from discrepancy_engine import DiscrepancyEngine
from html_reporter import HTMLReporter
from linguistic_forensics import LinguisticForensics
from openclaw_pipeline import run_pipeline
from p_curve_analyzer import PCurveAnalyzer
from plausibility_engine import PlausibilityEngine
from review_tool import ReviewTool
from rob_mapper import RoBMapper
from scientific_integrity_forensics import ScientificIntegrityForensics
from stats_utils import (
    betainc,
    benjamini_hochberg,
    binom_pmf,
    binom_test_greater,
    chi2_cdf,
    chi2_gof_test,
    chi2_sf,
    fisher_method,
    normal_cdf,
    t_cdf,
    t_sf,
    welch_t_test,
)
from truthcert_builder import (
    ENV_HMAC_KEY,
    TruthCertBuilder,
    load_hmac_key,
    verify_bundle,
)
from utils import (
    TOOL_DISCLAIMER,
    ensure_parent_dir,
    update_consensus,
    validate_nct_id,
    validate_report_schema,
)


# ══════════════════════════════════════════════════════════════
# 1. STATS_UTILS — validated against scipy / tables
# ══════════════════════════════════════════════════════════════


class TestNormalCDF:
    def test_symmetry(self):
        assert abs(normal_cdf(0) - 0.5) < 1e-10

    def test_z_196(self):
        assert abs(normal_cdf(1.96) - 0.975002) < 1e-4

    def test_negative(self):
        assert abs(normal_cdf(-2.0) - 0.02275) < 1e-4

    def test_extreme(self):
        assert normal_cdf(10) > 0.9999999
        assert normal_cdf(-10) < 1e-7


class TestTCDF:
    """t-CDF accuracy — the key fix. Old code was off by up to 11x."""

    def test_df1_cauchy(self):
        # Cauchy distribution: known exact values
        assert abs(t_cdf(1.0, 1) - 0.75) < 1e-4
        assert abs(t_cdf(2.0, 1) - 0.852416) < 1e-4

    def test_df2(self):
        assert abs(t_cdf(2.0, 2) - 0.908248) < 1e-4

    def test_df5_critical(self):
        # t_{0.025, 5} = 2.5706
        assert abs(t_cdf(2.5706, 5) - 0.975) < 1e-3

    def test_df30_approaches_normal(self):
        assert abs(t_cdf(1.96, 30) - 0.9703) < 1e-3

    def test_symmetry(self):
        assert abs(t_cdf(0, 10) - 0.5) < 1e-10

    def test_negative_t(self):
        assert abs(t_cdf(-2.0, 5) - (1 - t_cdf(2.0, 5))) < 1e-10

    def test_survival_function(self):
        assert abs(t_sf(2.0, 10) - (1 - t_cdf(2.0, 10))) < 1e-10


class TestChi2CDF:
    def test_critical_values(self):
        # chi2_{0.05, 1} = 3.841
        assert abs(chi2_cdf(3.841, 1) - 0.950) < 1e-2
        # chi2_{0.05, 8} = 15.507
        assert abs(chi2_cdf(15.507, 8) - 0.950) < 1e-2

    def test_zero(self):
        assert chi2_cdf(0, 5) == 0.0

    def test_large_value(self):
        assert chi2_cdf(100, 10) > 0.999999


class TestWelchTTest:
    def test_equal_groups(self):
        t, df, p = welch_t_test(10, 2, 20, 10, 2, 20)
        assert abs(t) < 1e-10
        assert abs(p - 1.0) < 1e-10

    def test_significant_difference(self):
        t, df, p = welch_t_test(10, 2, 20, 12, 2, 20)
        assert p < 0.01

    def test_zero_sd_equal_means(self):
        _, _, p = welch_t_test(5.0, 0.0, 10, 5.0, 0.0, 10)
        assert p == 1.0

    def test_zero_sd_different_means(self):
        """Impossible data: constant variable with different means."""
        _, _, p = welch_t_test(5.0, 0.0, 10, 10.0, 0.0, 10)
        assert p < 1e-10


class TestChi2GOF:
    def test_perfect_fit(self):
        obs = [30, 18, 12, 10, 8, 7, 6, 5, 5]
        exp = [30.1, 17.6, 12.5, 9.7, 7.9, 6.7, 5.8, 5.1, 4.6]
        chi2, df, p = chi2_gof_test(obs, exp)
        assert p > 0.5  # Good fit

    def test_obvious_deviation(self):
        obs = [11, 11, 11, 11, 11, 11, 11, 11, 12]  # Uniform
        exp = [30.1, 17.6, 12.5, 9.7, 7.9, 6.7, 5.8, 5.1, 4.6]
        chi2, df, p = chi2_gof_test(obs, exp)
        assert p < 0.001  # Very significant deviation


class TestBinomialTest:
    def test_fair_coin(self):
        # P(X >= 3 | n=5, p=0.5) = 0.5
        assert abs(binom_test_greater(3, 5, 0.5) - 0.5) < 1e-6

    def test_all_successes(self):
        # P(X >= 5 | n=5, p=0.5) = 1/32
        assert abs(binom_test_greater(5, 5, 0.5) - 0.03125) < 1e-6

    def test_none(self):
        # P(X >= 0) = 1
        assert abs(binom_test_greater(0, 10, 0.5) - 1.0) < 1e-6


class TestFisherMethod:
    def test_standard_significant(self):
        # Very small p-values → combined should be very significant
        _, _, p = fisher_method([0.001, 0.01, 0.005], direction="standard")
        assert p < 0.001

    def test_reversed_too_perfect(self):
        # p-values near 1.0 → reversed Fisher flags too-perfect
        _, _, p = fisher_method([0.95, 0.98, 0.99, 0.97], direction="reversed")
        assert p < 0.01

    def test_uniform_not_suspicious(self):
        # Normal p-values → reversed Fisher should NOT flag
        _, _, p = fisher_method([0.3, 0.5, 0.7, 0.4], direction="reversed")
        assert p > 0.05


class TestBH_FDR:
    def test_correction(self):
        pvals = [0.001, 0.01, 0.03, 0.04, 0.5, 0.8]
        results = benjamini_hochberg(pvals, alpha=0.05)
        # First few should still be significant, last two should not
        assert results[0][2] is True   # 0.001
        assert results[1][2] is True   # 0.01
        assert results[5][2] is False  # 0.8


# ══════════════════════════════════════════════════════════════
# 2. CLINICAL SYNONYMS
# ══════════════════════════════════════════════════════════════


class TestClinicalSimilarity:
    def test_abbreviation_expansion(self):
        assert clinical_similarity("MACE", "Major Adverse Cardiovascular Events") > 0.9

    def test_synonym_matching(self):
        assert clinical_similarity("All-cause mortality", "Mortality (all causes)") > 0.9

    def test_cv_death(self):
        assert clinical_similarity("CV death", "Cardiovascular death") > 0.9

    def test_pfs(self):
        assert clinical_similarity("PFS", "Progression-Free Survival") > 0.9

    def test_mi(self):
        assert clinical_similarity("MI", "Myocardial infarction") > 0.9

    def test_unrelated_outcomes(self):
        # 0.4 Jaccard is well below the 0.6 match threshold — no false match
        assert clinical_similarity("Blood pressure", "Overall Survival") < 0.6

    def test_hf_hospitalization(self):
        assert clinical_similarity("HF hospitalization", "Heart failure hospitalization") > 0.9


class TestEndpointClassification:
    def test_hard_endpoints(self):
        assert classify_endpoint("Overall Survival") == "HARD"
        assert classify_endpoint("MACE") == "HARD"
        assert classify_endpoint("Heart failure hospitalization") == "HARD"
        assert classify_endpoint("All-cause mortality") == "HARD"

    def test_surrogate_endpoints(self):
        assert classify_endpoint("Blood pressure") == "SURROGATE"
        assert classify_endpoint("NT-proBNP") == "SURROGATE"
        assert classify_endpoint("HbA1c") == "SURROGATE"
        assert classify_endpoint("LDL-C") == "SURROGATE"

    def test_unknown(self):
        assert classify_endpoint("Serum Calcium") == "UNKNOWN"


class TestTimeframeDetection:
    def test_different_timeframes(self):
        result = detect_timeframe_change(
            "Overall Survival at 24 months",
            "Overall Survival at 12 months",
        )
        assert result is not None
        assert "24 months" in result and "12 months" in result

    def test_same_timeframe(self):
        result = detect_timeframe_change(
            "OS at 12 months", "Overall Survival at 12 months"
        )
        assert result is None

    def test_no_timeframe(self):
        result = detect_timeframe_change("Quality of Life", "QoL")
        assert result is None


# ══════════════════════════════════════════════════════════════
# 3. CORE ENGINES
# ══════════════════════════════════════════════════════════════


class TestGRIMTest:
    def test_consistent_mean(self):
        """Mean 2.10 with N=10: sum=21.0, integer → CONSISTENT."""
        forensics = ScientificIntegrityForensics()
        result = forensics.grim_test(2.10, 10, 2, data_type="integer_count")
        assert result["status"] == "CONSISTENT"

    def test_inconsistent_mean(self):
        """Mean 2.11 with N=10: sum=21.1, not close to integer → INCONSISTENT."""
        forensics = ScientificIntegrityForensics()
        result = forensics.grim_test(2.11, 10, 2, data_type="integer_count")
        assert result["status"] == "INCONSISTENT"

    def test_continuous_data_guard(self):
        """GRIM should return INCONCLUSIVE for continuous measurements."""
        forensics = ScientificIntegrityForensics()
        result = forensics.grim_test(72.41, 10, 2, data_type="continuous")
        assert result["status"] == "INCONCLUSIVE"
        assert "integer-count" in result["reason"].lower() or "continuous" in result["reason"].lower()

    def test_unknown_data_type_includes_warning(self):
        """Unknown data type should still compute but include a caution."""
        forensics = ScientificIntegrityForensics()
        result = forensics.grim_test(2.11, 10, 2, data_type="unknown")
        assert result["status"] == "INCONSISTENT"
        assert "caution" in result.get("warning", "").lower() or "caution" in result.get("reason", "").lower()


class TestBenfordsLaw:
    def test_fabricated_uniform_detected(self):
        """Uniform digit distribution should be flagged as suspicious."""
        forensics = ScientificIntegrityForensics()
        # Generate numbers with uniform first digits (fabrication pattern)
        fabricated = []
        for d in range(1, 10):
            fabricated.extend([d * 10 + i for i in range(5)])
        # At least 20 numbers, roughly uniform first digits
        result = forensics.benfords_law_test(fabricated)
        assert result["status"] == "SUSPICIOUS"

    def test_too_few_numbers(self):
        forensics = ScientificIntegrityForensics()
        result = forensics.benfords_law_test([1.0, 2.0, 3.0])
        assert result["status"] == "INCONCLUSIVE"


class TestBaselineBalanceEngine:
    def test_typical_balance_not_flagged(self):
        """Normal RCT baseline differences should pass."""
        engine = BaselineBalanceEngine()
        normal_data = [
            {"m1": 45.1, "sd1": 12.0, "n1": 100, "m2": 47.3, "sd2": 11.5, "n2": 100},
            {"m1": 70.2, "sd1": 15.0, "n1": 100, "m2": 68.9, "sd2": 14.2, "n2": 100},
            {"m1": 120.0, "sd1": 18.0, "n1": 100, "m2": 122.5, "sd2": 17.5, "n2": 100},
        ]
        result = engine.analyze_baseline_set(normal_data)
        assert "ANOMALOUS" not in result["status"]

    def test_fujii_pattern_detected(self):
        """Fujii pattern: impossibly identical groups across all variables."""
        engine = BaselineBalanceEngine()
        fujii_data = [
            {"m1": 45.1, "sd1": 5.2, "n1": 100, "m2": 45.1, "sd2": 5.2, "n2": 100},
            {"m1": 70.2, "sd1": 10.1, "n1": 100, "m2": 70.2, "sd2": 10.1, "n2": 100},
            {"m1": 165.4, "sd1": 8.5, "n1": 100, "m2": 165.4, "sd2": 8.5, "n2": 100},
        ]
        result = engine.analyze_baseline_set(fujii_data)
        assert "ANOMALOUS" in result["status"]

    def test_sd_identity_detected(self):
        """Boldt pattern: identical SDs across groups (copy-paste marker)."""
        engine = BaselineBalanceEngine()
        boldt_data = [
            {"m1": 45.1, "sd1": 5.0, "n1": 50, "m2": 46.3, "sd2": 5.0, "n2": 50},
            {"m1": 70.2, "sd1": 10.0, "n1": 50, "m2": 71.1, "sd2": 10.0, "n2": 50},
            {"m1": 120.0, "sd1": 15.0, "n1": 50, "m2": 121.5, "sd2": 15.0, "n2": 50},
        ]
        result = engine.analyze_baseline_set(boldt_data)
        assert result["sd_identical_count"] == 3

    def test_empty_data(self):
        engine = BaselineBalanceEngine()
        result = engine.analyze_baseline_set([])
        assert result["status"] == "INCONCLUSIVE"

    def test_no_inflammatory_language(self):
        """Verify all inflammatory language has been removed."""
        engine = BaselineBalanceEngine()
        data = [
            {"m1": 45.1, "sd1": 5.2, "n1": 100, "m2": 45.1, "sd2": 5.2, "n2": 100},
        ]
        result = engine.analyze_baseline_set(data)
        reason = result.get("reason", "")
        assert "FRAUD" not in reason.upper()
        assert "IMPOSSIBLE" not in reason.upper()
        assert "PROSECUTION" not in reason.upper()


class TestPCurveAnalyzer:
    def test_real_effect_not_flagged(self):
        """Highly significant p-values should show evidential value."""
        analyzer = PCurveAnalyzer()
        result = analyzer.analyze_p_values([0.001, 0.002, 0.005, 0.01, 0.003])
        assert "SUSPICIOUS" not in result["status"]

    def test_p_hacking_pattern(self):
        """All p-values clustering just below 0.05 → suspicious."""
        analyzer = PCurveAnalyzer()
        result = analyzer.analyze_p_values(
            [0.041, 0.048, 0.049, 0.045, 0.047, 0.043, 0.044]
        )
        assert "SUSPICIOUS" in result["status"]

    def test_minimum_5_required(self):
        analyzer = PCurveAnalyzer()
        result = analyzer.analyze_p_values([0.01, 0.02, 0.03])
        assert result["status"] == "INCONCLUSIVE"

    def test_independence_warning(self):
        analyzer = PCurveAnalyzer()
        result = analyzer.analyze_p_values(
            [0.01, 0.02, 0.03, 0.04, 0.05], validated_independent=False
        )
        assert "warning" in result or "WARNING" in result.get("reason", "")


class TestPlausibilityEngine:
    def test_deterministic(self):
        """Same seed → same result (reproducibility fix)."""
        e1 = PlausibilityEngine(simulations=100, seed=42)
        r1 = e1.run_simulation(10, 2, 20, 12, 2, 20, 0.03)
        e2 = PlausibilityEngine(simulations=100, seed=42)
        r2 = e2.run_simulation(10, 2, 20, 12, 2, 20, 0.03)
        assert r1["avg_simulated_p"] == r2["avg_simulated_p"]
        assert r1["percentile"] == r2["percentile"]

    def test_plausible_result(self):
        random.seed(0)
        result = PlausibilityEngine(simulations=100, seed=0).run_simulation(
            10, 2, 20, 12, 2, 20, 0.03
        )
        assert result["status"] in {"PLAUSIBLE_OUTCOME", "IMPLAUSIBLE_OUTCOME"}
        assert "avg_simulated_p" in result


# ══════════════════════════════════════════════════════════════
# 4. DISCREPANCY ENGINE
# ══════════════════════════════════════════════════════════════


class TestDiscrepancyEngine:
    def test_matching_outcomes_no_discrepancy(self):
        engine = DiscrepancyEngine()
        protocol = [{"measure": "Overall Survival at 12 months"}]
        publication = [{"measure": "Overall Survival at 12 months"}]
        result = engine.compare_outcomes(protocol, publication)
        assert result["status"] == "PASS"
        assert len(result["discrepancies"]) == 0

    def test_abbreviation_matching(self):
        """MACE should match Major Adverse Cardiovascular Events."""
        engine = DiscrepancyEngine()
        protocol = [{"measure": "Major Adverse Cardiovascular Events"}]
        publication = [{"measure": "MACE"}]
        result = engine.compare_outcomes(protocol, publication)
        # Should match — no OUTCOME_ADDED or OUTCOME_MISSING
        outcome_types = [d["type"] for d in result["discrepancies"]]
        assert "OUTCOME_ADDED" not in outcome_types
        assert "OUTCOME_MISSING" not in outcome_types

    def test_missing_outcome_detected(self):
        engine = DiscrepancyEngine()
        protocol = [
            {"measure": "Overall Survival"},
            {"measure": "Progression-free survival"},
        ]
        publication = [{"measure": "Overall Survival"}]
        result = engine.compare_outcomes(protocol, publication)
        missing = [d for d in result["discrepancies"] if d["type"] == "OUTCOME_MISSING"]
        assert len(missing) == 1

    def test_added_outcome_detected(self):
        engine = DiscrepancyEngine()
        protocol = [{"measure": "Overall Survival"}]
        publication = [
            {"measure": "Overall Survival"},
            {"measure": "Quality of Life Score"},
        ]
        result = engine.compare_outcomes(protocol, publication)
        added = [d for d in result["discrepancies"] if d["type"] == "OUTCOME_ADDED"]
        assert len(added) == 1

    def test_confidence_always_set(self):
        """P0-15: confidence must be set on all discrepancy types."""
        engine = DiscrepancyEngine()
        protocol = [{"measure": "Overall Survival"}]
        publication = [{"measure": "Serum Calcium"}]
        result = engine.compare_outcomes(protocol, publication)
        for d in result["discrepancies"]:
            assert "confidence" in d


# ══════════════════════════════════════════════════════════════
# 5. ROB MAPPER
# ══════════════════════════════════════════════════════════════


class TestRoBMapper:
    def test_no_discrepancies_low_risk(self):
        mapper = RoBMapper()
        result = mapper.assess_domain_5([])
        assert result["score"] == "Low"

    def test_confirmed_discrepancy_high_risk(self):
        mapper = RoBMapper()
        result = mapper.assess_domain_5(
            [
                {
                    "type": "OUTCOME_MISSING",
                    "consensus_status": "CONFIRMED",
                    "clinical_reasoning": "HIGH SEVERITY: hard endpoint omitted",
                }
            ]
        )
        assert result["score"] == "High"

    def test_disputed_not_excluded(self):
        """P1-4: DISPUTED should contribute to risk, not be excluded."""
        mapper = RoBMapper()
        result = mapper.assess_domain_5(
            [{"type": "OUTCOME_ADDED", "consensus_status": "DISPUTED"}]
        )
        # Should be at least "Some Concerns", not "Low"
        assert result["score"] != "Low"

    def test_false_positive_excluded(self):
        mapper = RoBMapper()
        result = mapper.assess_domain_5(
            [{"type": "OUTCOME_ADDED", "consensus_status": "FALSE_POSITIVE"}]
        )
        assert "Low" in result["score"]


# ══════════════════════════════════════════════════════════════
# 6. LINGUISTIC FORENSICS
# ══════════════════════════════════════════════════════════════


class TestLinguisticForensics:
    def test_hyped_text_flagged(self):
        forensics = LinguisticForensics()
        text = (
            "This groundbreaking study presents an extraordinary and unique "
            "revolutionary treatment that has an unprecedented and miraculous "
            "effect on patient outcomes, robustly transforming clinical practice "
            "dramatically."
        )
        result = forensics.analyze_text(text)
        assert "SUSPICIOUS" in result["status"]

    def test_balanced_text_not_flagged(self):
        forensics = LinguisticForensics()
        text = (
            "This study suggests a potential benefit of the intervention, "
            "though several limitations should be noted. The results are "
            "consistent with possible improvements in the primary endpoint."
        )
        result = forensics.analyze_text(text)
        assert "TYPICAL" in result["status"]

    def test_empty_text(self):
        forensics = LinguisticForensics()
        result = forensics.analyze_text("")
        assert result["status"] == "INCONCLUSIVE"


# ══════════════════════════════════════════════════════════════
# 7. REVIEW TOOL + AI REVIEWER
# ══════════════════════════════════════════════════════════════


def test_review_tool_initializes_missing_reviews(tmp_path):
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "discrepancy_results": {
                    "discrepancies": [
                        {
                            "type": "OUTCOME_ADDED",
                            "reason": "Flagged",
                            "publication_outcome": "Outcome A",
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    ReviewTool(str(report_path)).add_review_non_interactive("Reviewer", 0, "C", "Confirmed")

    saved = json.loads(report_path.read_text(encoding="utf-8"))
    discrepancy = saved["discrepancy_results"]["discrepancies"][0]
    assert discrepancy["reviews"][0]["reviewer"] == "Reviewer"
    assert discrepancy["consensus_status"] == "CONFIRMED"


def test_ai_reviewer_added_safety_endpoint_dismissed(tmp_path):
    """OUTCOME_ADDED safety endpoints should be auto-dismissed as FALSE_POSITIVE."""
    report_path = tmp_path / "ai_report.json"
    report_path.write_text(
        json.dumps(
            {
                "discrepancy_results": {
                    "discrepancies": [
                        {
                            "type": "OUTCOME_ADDED",
                            "publication_outcome": "adverse events",
                            "confidence": 0.9,
                            "reviews": [],
                            "consensus_status": "PENDING",
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    AIReviewer(str(report_path)).auto_review()

    saved = json.loads(report_path.read_text(encoding="utf-8"))
    discrepancy = saved["discrepancy_results"]["discrepancies"][0]
    assert discrepancy["reviews"][0]["status"] == "FALSE_POSITIVE"


def test_ai_reviewer_missing_safety_endpoint_flagged(tmp_path):
    """P2-18: OUTCOME_MISSING safety data should be CONFIRMED (selective omission risk)."""
    report_path = tmp_path / "ai_report.json"
    report_path.write_text(
        json.dumps(
            {
                "discrepancy_results": {
                    "discrepancies": [
                        {
                            "type": "OUTCOME_MISSING",
                            "protocol_outcome": "serious adverse events",
                            "confidence": 0.9,
                            "reviews": [],
                            "consensus_status": "PENDING",
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    AIReviewer(str(report_path)).auto_review()

    saved = json.loads(report_path.read_text(encoding="utf-8"))
    discrepancy = saved["discrepancy_results"]["discrepancies"][0]
    assert discrepancy["reviews"][0]["status"] == "CONFIRMED"


def test_ai_reviewer_no_confidence_inconclusive(tmp_path):
    """P0-15: Missing confidence should produce INCONCLUSIVE, not auto-CONFIRMED."""
    report_path = tmp_path / "ai_report.json"
    report_path.write_text(
        json.dumps(
            {
                "discrepancy_results": {
                    "discrepancies": [
                        {
                            "publication_outcome": "some outcome",
                            "reviews": [],
                            "consensus_status": "PENDING",
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    AIReviewer(str(report_path)).auto_review()

    saved = json.loads(report_path.read_text(encoding="utf-8"))
    discrepancy = saved["discrepancy_results"]["discrepancies"][0]
    assert discrepancy["reviews"][0]["status"] == "INCONCLUSIVE"


def test_review_tool_invalid_schema_raises(tmp_path):
    report_path = tmp_path / "bad_report.json"
    report_path.write_text(json.dumps({"discrepancy_results": "bad"}), encoding="utf-8")

    with pytest.raises(ValueError):
        ReviewTool(str(report_path))


def test_ai_reviewer_invalid_schema_raises(tmp_path):
    report_path = tmp_path / "bad_report.json"
    report_path.write_text(
        json.dumps({"discrepancy_results": {"discrepancies": "bad"}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        AIReviewer(str(report_path))


# ══════════════════════════════════════════════════════════════
# 8. HTML REPORTER — XSS + DISCLAIMER
# ══════════════════════════════════════════════════════════════


def test_html_reporter_escapes_report_content(tmp_path):
    report_path = tmp_path / "report.json"
    html_path = tmp_path / "dashboard.html"
    report_path.write_text(
        json.dumps(
            {
                "nctId": "NCT<script>",
                "citation": "<script>alert(1)</script>",
                "timestamp": "2026-04-01",
                "discrepancy_results": {
                    "status": "WARNING",
                    "discrepancies": [
                        {
                            "type": "OUTCOME_ADDED",
                            "publication_outcome": "<img src=x onerror=alert(2)>",
                            "reason": "<svg onload=alert(3)>",
                            "reviews": [
                                {
                                    "reviewer": "A<script>",
                                    "status": "CONFIRMED",
                                    "comment": "<b>raw</b>",
                                }
                            ],
                            "consensus_status": "CONFIRMED",
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    HTMLReporter(str(report_path), str(html_path)).generate()
    rendered = html_path.read_text(encoding="utf-8")

    assert "{len(discrepancies)}" not in rendered
    assert "Identified Discrepancies (1)" in rendered
    assert "<script>alert(1)</script>" not in rendered
    assert "<img src=x onerror=alert(2)>" not in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered


def test_html_reporter_includes_disclaimer(tmp_path):
    report_path = tmp_path / "report.json"
    html_path = tmp_path / "dashboard.html"
    report_path.write_text(
        json.dumps(
            {
                "nctId": "NCT12345678",
                "citation": "Test",
                "timestamp": "2026-04-01",
                "discrepancy_results": {"status": "PASS", "discrepancies": []},
            }
        ),
        encoding="utf-8",
    )

    HTMLReporter(str(report_path), str(html_path)).generate()
    rendered = html_path.read_text(encoding="utf-8")
    assert "DISCLAIMER" in rendered
    assert "automated screening tool" in rendered


def test_html_reporter_rob_color_allowlist(tmp_path):
    """P0-11: Injected rob_color should be sanitized to gray."""
    report_path = tmp_path / "report.json"
    html_path = tmp_path / "dashboard.html"
    report_path.write_text(
        json.dumps(
            {
                "nctId": "NCT12345678",
                "citation": "Test",
                "timestamp": "2026-04-01",
                "discrepancy_results": {"status": "PASS", "discrepancies": []},
                "rob_assessment": {
                    "score": "Injected",
                    "color": "green-500 bg-red-500",
                    "justification": "test",
                },
            }
        ),
        encoding="utf-8",
    )

    HTMLReporter(str(report_path), str(html_path)).generate()
    rendered = html_path.read_text(encoding="utf-8")
    # Injected color should be sanitized to gray
    assert "bg-green-500 bg-red-500-500" not in rendered


def test_html_reporter_invalid_schema_does_not_write_output(tmp_path):
    report_path = tmp_path / "bad_report.json"
    html_path = tmp_path / "dashboard.html"
    report_path.write_text(json.dumps({"discrepancy_results": "bad"}), encoding="utf-8")

    HTMLReporter(str(report_path), str(html_path)).generate()

    assert not html_path.exists()


# ══════════════════════════════════════════════════════════════
# 9. TRUTHCERT BUILDER
# ══════════════════════════════════════════════════════════════


_TEST_KEY = b"test_key_do_not_use_in_prod"


class TestTruthCertBuilder:
    def test_bundle_has_disclaimer(self):
        builder = TruthCertBuilder("NCT12345678")
        bundle = builder.build_bundle("PASS", key=_TEST_KEY)
        assert "disclaimer" in bundle

    def test_bundle_has_integrity_hash(self):
        builder = TruthCertBuilder("NCT12345678")
        builder.add_evidence_source("test", "content", "locator")
        bundle = builder.build_bundle("PASS", key=_TEST_KEY)
        assert "integrity_hash" in bundle
        assert len(bundle["integrity_hash"]) == 64  # SHA256 hex

    def test_cert_id_not_timestamp_based(self):
        b1 = TruthCertBuilder("NCT12345678")
        b2 = TruthCertBuilder("NCT12345678")
        # Should be different (random) not same (timestamp)
        assert b1.cert_id != b2.cert_id

    def test_verify_bundle_accepts_untampered(self):
        builder = TruthCertBuilder("NCT12345678")
        builder.add_evidence_source("test", "content", "locator")
        bundle = builder.build_bundle("PASS", key=_TEST_KEY)
        assert verify_bundle(bundle, _TEST_KEY) is True

    def test_verify_bundle_rejects_tampered_bundle(self):
        builder = TruthCertBuilder("NCT12345678")
        builder.add_evidence_source("test", "content", "locator")
        bundle = builder.build_bundle("PASS", key=_TEST_KEY)
        bundle["status"] = "REJECT"  # flip a field after signing
        assert verify_bundle(bundle, _TEST_KEY) is False

    def test_verify_bundle_rejects_wrong_key(self):
        builder = TruthCertBuilder("NCT12345678")
        bundle = builder.build_bundle("PASS", key=_TEST_KEY)
        assert verify_bundle(bundle, b"different_key") is False

    def test_verify_bundle_rejects_missing_hash(self):
        builder = TruthCertBuilder("NCT12345678")
        bundle = builder.build_bundle("PASS", key=_TEST_KEY)
        bundle.pop("integrity_hash")
        assert verify_bundle(bundle, _TEST_KEY) is False

    def test_load_hmac_key_missing_raises_runtime_error(self, monkeypatch, tmp_path):
        monkeypatch.delenv(ENV_HMAC_KEY, raising=False)
        # Point repo root lookup at an empty tmp dir so the fallback file path
        # is also absent.
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "truthcert_builder._repo_root", lambda: tmp_path
        )
        with pytest.raises(RuntimeError, match="TRUTHCERT_HMAC_KEY not configured"):
            load_hmac_key()

    def test_load_hmac_key_env_precedence(self, monkeypatch, tmp_path):
        # File fallback exists with value B; env var set to value A must win.
        (tmp_path / ".truthcert_key").write_text("file_key_value", encoding="utf-8")
        monkeypatch.setattr(
            "truthcert_builder._repo_root", lambda: tmp_path
        )
        monkeypatch.setenv(ENV_HMAC_KEY, "env_key_value")
        assert load_hmac_key() == b"env_key_value"

    def test_load_hmac_key_file_fallback(self, monkeypatch, tmp_path):
        (tmp_path / ".truthcert_key").write_text("file_key_value", encoding="utf-8")
        monkeypatch.setattr(
            "truthcert_builder._repo_root", lambda: tmp_path
        )
        monkeypatch.delenv(ENV_HMAC_KEY, raising=False)
        assert load_hmac_key() == b"file_key_value"

    def test_build_bundle_missing_key_raises_runtime_error(self, monkeypatch, tmp_path):
        monkeypatch.delenv(ENV_HMAC_KEY, raising=False)
        monkeypatch.setattr(
            "truthcert_builder._repo_root", lambda: tmp_path
        )
        builder = TruthCertBuilder("NCT12345678")
        with pytest.raises(RuntimeError, match="TRUTHCERT_HMAC_KEY not configured"):
            builder.build_bundle("PASS")

    def test_deterministic_output_fixed_key(self):
        """Fixed key + fixed inputs + same cert_id must yield the same hash."""
        b1 = TruthCertBuilder("NCT12345678")
        b2 = TruthCertBuilder("NCT12345678")
        # Align cert_id so the canonical body is identical.
        b2.cert_id = b1.cert_id
        for b in (b1, b2):
            b.add_evidence_source("src", "content", "locator")
            b.certify_discrepancy(
                {"type": "OUTCOME_MISSING", "protocol_outcome": "A", "reason": "X"}
            )
            # Pin timestamps inside claims so canonical JSON matches.
            b.claims[0]["timestamp"] = "2026-01-01T00:00:00"
        h1 = b1.build_bundle("PASS", key=_TEST_KEY)["integrity_hash"]
        h2 = b2.build_bundle("PASS", key=_TEST_KEY)["integrity_hash"]
        assert h1 == h2

    def test_cert_id_not_in_hmac_key_source(self, monkeypatch, tmp_path):
        """Regression: key must not be self.cert_id (which lives in the bundle)."""
        monkeypatch.setattr(
            "truthcert_builder._repo_root", lambda: tmp_path
        )
        monkeypatch.setenv(ENV_HMAC_KEY, "secret_env_key")
        builder = TruthCertBuilder("NCT12345678")
        bundle = builder.build_bundle("PASS")
        # Using cert_id as the key (the old weak behaviour) must NOT verify.
        assert verify_bundle(bundle, builder.cert_id.encode()) is False
        # The real env key must verify.
        assert verify_bundle(bundle, b"secret_env_key") is True


# ══════════════════════════════════════════════════════════════
# 10. UTILS
# ══════════════════════════════════════════════════════════════


def test_ensure_parent_dir_creates_nested_parent(tmp_path):
    target = tmp_path / "nested" / "path" / "report.json"
    ensure_parent_dir(str(target))
    assert (tmp_path / "nested" / "path").is_dir()


def test_validate_nct_id():
    assert validate_nct_id("NCT12345678") is True
    assert validate_nct_id("NCT04458623") is True
    assert validate_nct_id("INVALID") is False
    assert validate_nct_id("NCT123") is False
    assert validate_nct_id("../admin") is False


def test_update_consensus_logic():
    d = {"reviews": [{"status": "CONFIRMED"}, {"status": "CONFIRMED"}]}
    update_consensus(d)
    assert d["consensus_status"] == "CONFIRMED"

    d = {"reviews": [{"status": "FALSE_POSITIVE"}, {"status": "FALSE_POSITIVE"}]}
    update_consensus(d)
    assert d["consensus_status"] == "FALSE_POSITIVE"

    d = {"reviews": [{"status": "CONFIRMED"}, {"status": "FALSE_POSITIVE"}]}
    update_consensus(d)
    assert d["consensus_status"] == "DISPUTED"

    d = {"reviews": []}
    update_consensus(d)
    assert d["consensus_status"] == "PENDING"


def test_validate_report_schema():
    validate_report_schema({"discrepancy_results": {"discrepancies": []}})

    with pytest.raises(ValueError):
        validate_report_schema({"discrepancy_results": "not a dict"})

    with pytest.raises(ValueError):
        validate_report_schema({"discrepancy_results": {"discrepancies": "not a list"}})


def test_openclaw_requires_extracted_outcomes(tmp_path, monkeypatch, capsys):
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(
        json.dumps(
            {
                "nctId": "NCT12345678",
                "citation": "Test citation",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        ["openclaw_pipeline.py", "--bundle", str(bundle_path)],
    )

    run_pipeline()
    captured = capsys.readouterr()
    assert "extractedOutcomes" in captured.out
