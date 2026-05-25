import json
from typing import Any

from stats_utils import fisher_method, welch_t_test


class BaselineBalanceEngine:
    """
    Detects 'Too Perfect' baseline randomization (Carlisle pattern).

    In real RCTs, baseline p-values should be uniformly distributed.
    If p-values cluster near 1.0, the groups are 'sub-randomly' similar,
    which is a known marker of data fabrication.

    Methodological basis:
        - Carlisle (2012), Anaesthesia 67(5):521-537 - original method
          for detecting fabricated baseline balance via Fisher's combined
          test on reversed p-values.
        - Carlisle (2017), Anaesthesia 72(8):944-952 - extended analysis
          leading to the Fujii case (172 retractions, the largest
          retraction event in scientific history).
    """
    def __init__(self):
        pass

    def calculate_baseline_p(self, mean1: float, sd1: float, n1: int, mean2: float, sd2: float, n2: int) -> float:
        """
        Calculates a high-precision p-value for baseline differences
        using Welch's t-test with proper t-distribution CDF.
        """
        if n1 < 2 or n2 < 2:
            return 1.0

        t_stat, df, p = welch_t_test(mean1, sd1, n1, mean2, sd2, n2)
        return p

    def analyze_baseline_set(self, baseline_comparisons: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Analyzes baseline p-values and Standard Deviation (SD) homogeneity.

        Uses Fisher's method (reversed direction) to test whether the
        combined baseline p-values cluster near 1.0, indicating
        implausibly perfect balance.
        """
        p_values = []
        sd_identical_count = 0

        for comp in baseline_comparisons:
            p = self.calculate_baseline_p(
                comp["m1"], comp["sd1"], comp["n1"],
                comp["m2"], comp["sd2"], comp["n2"]
            )
            p_values.append(p)

            # SD Check: Fraudsters often copy-paste Standard Deviations
            if comp["sd1"] == comp["sd2"] and comp["sd1"] != 0:
                sd_identical_count += 1

        if not p_values:
            return {"status": "INCONCLUSIVE", "reason": "No baseline data."}

        # Fisher's Method (reversed) for 'Too Perfect' p-values
        chi_sq_stat, df_fisher, overall_prob = fisher_method(p_values, direction="reversed")

        # SD Anomaly Check
        sd_anomaly = sd_identical_count / len(p_values) > 0.5 if len(p_values) >= 3 else False

        # Carlisle threshold
        is_anomalous = overall_prob < 0.000001 or sd_anomaly
        is_suspicious = overall_prob < 0.01

        status = "ANOMALOUS_PATTERN" if is_anomalous else ("SUSPICIOUS" if is_suspicious else "TYPICAL")

        reason = f"Probability of this balance occurring naturally is 1 in {round(1 / max(overall_prob, 1e-20)):,}. "
        if sd_anomaly:
            reason += (f"{sd_identical_count}/{len(p_values)} baseline measures have identical "
                       f"standard deviations, which is a recognized marker of data fabrication.")
        elif is_anomalous:
            reason += "This level of baseline balance is statistically anomalous and warrants investigation."

        return {
            "status": status,
            "combined_probability": overall_prob,
            "fisher_chi_square": round(chi_sq_stat, 4),
            "fisher_df": df_fisher,
            "one_in_x_chance": round(1 / max(overall_prob, 1e-20)),
            "sd_identical_count": sd_identical_count,
            "reason": reason
        }


if __name__ == "__main__":
    engine = BaselineBalanceEngine()
    # Test 'Too Perfect' Balance (Age 45.1 vs 45.2, Weight 70.1 vs 70.2)
    perfect_data = [
        {"m1": 45.1, "sd1": 5.0, "n1": 100, "m2": 45.2, "sd2": 5.0, "n2": 100},
        {"m1": 70.1, "sd1": 10.0, "n1": 100, "m2": 70.2, "sd2": 10.0, "n2": 100}
    ]
    print(json.dumps(engine.analyze_baseline_set(perfect_data), indent=2))
