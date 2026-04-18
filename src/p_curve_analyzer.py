import json
import math
from typing import List, Dict, Any

from stats_utils import binom_test_greater


class PCurveAnalyzer:
    """
    Analyzes the distribution of p-values to detect 'p-hacking'.
    Real effects have a right-skewed p-curve (more 0.01s than 0.04s).
    P-hacked effects have a flat or left-skewed p-curve.

    Reference: Simonsohn, Nelson & Simmons (2014, 2015),
    Journal of Experimental Psychology: General.

    Uses a binomial test to evaluate whether the proportion of p-values
    in the high bin (0.025-0.05) exceeds what is expected under the null
    (flat p-curve), replacing the naive 50% count comparison.
    """
    def __init__(self):
        pass

    def analyze_p_values(self, p_values: List[float],
                         validated_independent: bool = False) -> Dict[str, Any]:
        """
        Performs a p-curve analysis on a set of reported results.

        Parameters:
            p_values: List of p-values from studies.
            validated_independent: If True, the caller confirms that
                p-values are independent (one per study, from the key
                test). If False, a warning is included in the output.
        """
        significant_ps = [p for p in p_values if 0 < p <= 0.05]

        if len(significant_ps) < 5:
            return {"status": "INCONCLUSIVE", "reason": "Requires at least 5 significant p-values for p-curve analysis."}

        # Count p-values in bins
        low_bin = [p for p in significant_ps if p <= 0.025]
        high_bin = [p for p in significant_ps if 0.025 < p <= 0.05]

        low_count = len(low_bin)
        high_count = len(high_bin)
        n_sig = len(significant_ps)

        # In a real effect, low_count should be much higher than high_count
        ratio = low_count / n_sig

        # Binomial test: does the proportion in high bin exceed 50% (flat null)?
        p_flat = binom_test_greater(high_count, n_sig, 0.5)
        # Binomial test: does the proportion in low bin exceed 50% (evidential value)?
        p_right = binom_test_greater(low_count, n_sig, 0.5)

        # Flag as suspicious only if the flatness/left-skewness test is significant
        is_suspicious = p_flat < 0.10
        has_evidential_value = p_right < 0.10

        if is_suspicious:
            status = "SUSPICIOUS (P-HACKING RISK)"
        elif has_evidential_value:
            status = "EVIDENTIAL_VALUE_PRESENT"
        else:
            status = "INCONCLUSIVE_CURVE"

        reason = (f"Found {high_count} p-values just below 0.05 vs {low_count} "
                  f"highly significant p-values. ")
        if is_suspicious:
            reason += (f"Binomial test for flatness: p={round(p_flat, 4)} (significant at 0.10). "
                       "This distribution is characteristic of selective reporting.")
        elif has_evidential_value:
            reason += (f"Binomial test for right-skewness: p={round(p_right, 4)} (significant at 0.10). "
                       "The distribution suggests a robust effect.")
        else:
            reason += "Neither flatness nor right-skewness test reached significance."

        result = {
            "status": status,
            "p_values_analyzed": n_sig,
            "distribution": {"0-0.025": low_count, "0.025-0.05": high_count},
            "low_p_ratio": round(ratio, 2),
            "p_flat_test": round(p_flat, 6),
            "p_right_skewness_test": round(p_right, 6),
            "reason": reason
        }

        if not validated_independent:
            result["warning"] = (
                "WARNING: P-curve validity requires independent p-values "
                "(one per study, from the key test). Dependent p-values "
                "(multiple endpoints from one study) will produce misleading "
                "results. Reference: Simonsohn, Nelson & Simmons (2014)."
            )

        return result


if __name__ == "__main__":
    analyzer = PCurveAnalyzer()
    # Test P-Hacking: Cluster around 0.04 (need 5+ values now)
    print(json.dumps(analyzer.analyze_p_values([0.041, 0.048, 0.049, 0.035, 0.044]), indent=2))
    # Test Real Effect: Cluster around 0.001
    print(json.dumps(analyzer.analyze_p_values([0.001, 0.002, 0.005, 0.01, 0.04]), indent=2))
