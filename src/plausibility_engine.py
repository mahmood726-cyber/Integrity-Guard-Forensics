import math
import random
import statistics
from typing import Any

from stats_utils import t_sf


class PlausibilityEngine:
    """
    Monte Carlo Plausibility Tester.
    Re-simulates trials thousands of times to see if reported results are outliers.

    Uses a proper Student's t-distribution (via regularized incomplete beta
    function) instead of the normal CDF approximation, which was off by up
    to 11x for df=1.

    Deterministic seeding ensures reproducible forensic results.
    """
    def __init__(self, simulations: int = 10000, seed: int | None = 42):
        self.simulations = simulations
        self.rng = random.Random(seed)

    def simulate_p_value(self, m1: float, sd1: float, n1: int, m2: float, sd2: float, n2: int) -> float:
        """
        Simulates two groups and calculates a p-value using Welch's t-test
        with proper t-distribution CDF.
        """
        if n1 < 2 or n2 < 2:
            raise ValueError("Group sizes must be at least 2 for variance estimation.")

        group1 = [self.rng.gauss(m1, sd1) for _ in range(n1)]
        group2 = [self.rng.gauss(m2, sd2) for _ in range(n2)]

        # Sample variances
        v1 = statistics.variance(group1) if n1 > 1 else 0
        v2 = statistics.variance(group2) if n2 > 1 else 0

        se = math.sqrt((v1 / n1) + (v2 / n2))
        if se == 0:
            return 1.0 if statistics.mean(group1) == statistics.mean(group2) else 0.0

        t = abs(statistics.mean(group1) - statistics.mean(group2)) / se

        # Welch-Satterthwaite degrees of freedom
        num = (v1 / n1 + v2 / n2) ** 2
        denom = (v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1)
        if denom == 0:
            return 1.0
        df = num / denom

        # Two-sided p-value using proper t-distribution CDF
        p = 2.0 * t_sf(t, df)
        return p

    def run_simulation(self, reported_m1, sd1, n1, reported_m2, sd2, n2, reported_p) -> dict[str, Any]:
        """
        Runs simulations to see where the reported p-value falls.
        """
        simulated_ps = []
        for _ in range(self.simulations):
            try:
                p = self.simulate_p_value(reported_m1, sd1, n1, reported_m2, sd2, n2)
                simulated_ps.append(p)
            except (ValueError, statistics.StatisticsError):
                continue

        if not simulated_ps:
            return {"status": "ERROR", "reason": "Simulation failed to produce valid p-values."}

        avg_sim_p = statistics.mean(simulated_ps)
        # Percentile check
        outliers = sum(1 for p in simulated_ps if p < reported_p)
        percentile = (outliers / len(simulated_ps)) * 100

        # If the reported p is vastly different from simulated ps
        is_implausible = abs(avg_sim_p - reported_p) > 0.1 and (percentile < 5 or percentile > 95)

        return {
            "status": "IMPLAUSIBLE_OUTCOME" if is_implausible else "PLAUSIBLE_OUTCOME",
            "avg_simulated_p": round(avg_sim_p, 4),
            "reported_p": reported_p,
            "percentile": round(percentile, 1),
            "simulations": len(simulated_ps),
            "reason": f"Monte Carlo simulation (n={len(simulated_ps)}) shows an average expected p of {round(avg_sim_p, 4)}. " +
                      ("The reported p is an outlier in this distribution." if is_implausible else "The reported p falls within the expected range.")
        }
