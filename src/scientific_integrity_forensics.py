import json
import math
from typing import List, Dict, Any

from stats_utils import chi2_gof_test


class ScientificIntegrityForensics:
    """
    Forensic engine to detect patterns of data fabrication/falsification.
    Based on historical fraud detection methods (Fujii, Boldt, etc.).
    """
    def __init__(self):
        pass

    def grim_test(self, mean: float, n: int, precision: int = 2,
                  data_type: str = "unknown") -> Dict[str, Any]:
        """
        Granularity-Related Inconsistency of Means (GRIM).
        Checks if a mean is mathematically possible for a given N and precision.
        Formula: (mean * n) should be close to an integer.

        Reference: Brown & Heathers (2017), Social Psychological and
        Personality Science.

        Parameters:
            mean: The reported mean.
            n: The sample size.
            precision: Number of decimal places in the reported mean.
            data_type: One of "integer_count", "continuous", "percentage",
                       or "unknown". GRIM only applies to integer-count
                       data (e.g., Likert scales, counts).
        """
        if data_type == "continuous":
            return {
                "status": "INCONCLUSIVE",
                "reason": ("GRIM test only applies to integer-count data "
                           "(e.g., Likert scales). Not applicable to "
                           "continuous measurements.")
            }

        if n <= 0:
            return {"status": "INCONCLUSIVE", "reason": "N must be > 0"}

        # Calculate sum
        total_sum = mean * n
        rounded_sum = round(total_sum)

        # The difference should be very small if the mean is real
        # Tolerance depends on precision (e.g., if mean is 2.45, it could be 2.445 to 2.454)
        tolerance = 0.5 / (10**precision) * n
        diff = abs(total_sum - rounded_sum)

        is_consistent = diff <= (tolerance + 1e-9)

        result = {
            "status": "CONSISTENT" if is_consistent else "INCONSISTENT",
            "diff": diff,
            "max_allowed_diff": tolerance,
            "reason": f"A mean of {mean} with N={n} is mathematically {'possible' if is_consistent else 'impossible'}."
        }

        if data_type == "unknown":
            result["warning"] = (
                "CAUTION: GRIM test validity depends on the data being "
                "integer-count (e.g., Likert scales). Verify data type "
                "before interpreting."
            )

        return result

    def benfords_law_test(self, numbers: List[float]) -> Dict[str, Any]:
        """
        Checks if the leading digits of a dataset follow Benford's Law
        using a chi-square goodness-of-fit test.

        Fabricated data often fails this (humans tend to over-use digits
        like 5, 6, 7). Flags as SUSPICIOUS if chi-square p < 0.05
        (significant deviation from Benford's distribution).

        Reference: Nigrini (2012), Benford's Law: Applications for
        Forensic Accounting, Auditing, and Fraud Detection, Wiley.

        Requires at least 20 numbers for the chi-square test to be valid.
        """
        if len(numbers) < 20:
            return {"status": "INCONCLUSIVE", "reason": "Requires at least 20 numbers for statistical significance."}

        # Benford's expected proportions for digits 1-9 (as fractions)
        benford_proportions = [
            math.log10(1 + 1/d) for d in range(1, 10)
        ]

        first_digits = []
        for n in numbers:
            s = str(abs(n)).replace(".", "").lstrip("0")
            if s:
                first_digits.append(int(s[0]))

        total = len(first_digits)
        if total < 20:
            return {"status": "INCONCLUSIVE", "reason": "Fewer than 20 valid leading digits extracted."}

        observed_counts = [first_digits.count(i) for i in range(1, 10)]
        expected_counts = [p * total for p in benford_proportions]

        # Chi-square goodness-of-fit test
        chi_sq, df, p_value = chi2_gof_test(observed_counts, expected_counts)

        observed_pct = [(c / total) * 100 for c in observed_counts]
        expected_pct = [p * 100 for p in benford_proportions]

        is_suspicious = p_value < 0.05

        return {
            "status": "SUSPICIOUS" if is_suspicious else "TYPICAL",
            "chi_square": round(chi_sq, 4),
            "df": df,
            "p_value": round(p_value, 6),
            "observed_distribution": observed_pct,
            "expected_distribution": [round(e, 1) for e in expected_pct],
            "reason": (f"Chi-square goodness-of-fit test: chi2={round(chi_sq, 2)}, "
                       f"df={df}, p={round(p_value, 4)}. "
                       + ("Significant deviation from Benford's Law (p < 0.05)."
                          if is_suspicious
                          else "Distribution is consistent with Benford's Law."))
        }


if __name__ == "__main__":
    forensics = ScientificIntegrityForensics()
    # Test GRIM: Mean 2.11 with N=100 is possible (211/100)
    # Mean 2.11 with N=10 is IMPOSSIBLE (21.1/10 is not an integer-count sum)
    print(json.dumps(forensics.grim_test(2.11, 10, 2, data_type="integer_count"), indent=2))

    # Test Benford (Random numbers fail, real physical data usually passes)
    import random
    random_nums = [random.uniform(1, 1000) for _ in range(100)]
    print(json.dumps(forensics.benfords_law_test(random_nums), indent=2))
