"""
Production-grade pure-Python statistical distribution functions.

No external dependencies (no scipy/numpy). Uses continued-fraction
and series expansions that are accurate to ~14 significant digits.

These replace the hand-rolled approximations that were in individual
modules (normal CDF pretending to be t-CDF, Wilson-Hilferty, etc.).

Key building blocks:
  - Regularized incomplete beta function  → t-distribution CDF
  - Regularized lower incomplete gamma    → chi-square CDF
  - Both use Lentz's modified continued-fraction algorithm

References:
  - Press et al., Numerical Recipes (3rd ed.), Ch. 6
  - Abramowitz & Stegun, Handbook of Mathematical Functions
  - NIST Digital Library of Mathematical Functions
"""

import math
from typing import List, Tuple, Optional


# ──────────────────────────────────────────────────────────────
# 1. BUILDING BLOCKS
# ──────────────────────────────────────────────────────────────

def _betacf(a: float, b: float, x: float,
            max_iter: int = 300, eps: float = 1e-14) -> float:
    """Continued fraction for the regularized incomplete beta function.
    Uses the Lentz modified algorithm (Numerical Recipes 6.4)."""
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        # Even step
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        h *= d * c
        # Odd step
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            return h
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function I_x(a, b).

    Uses continued fraction with symmetry relation for numerical stability.
    Accurate to ~14 significant digits for all valid inputs.
    """
    if x < 0.0 or x > 1.0:
        raise ValueError(f"x must be in [0, 1], got {x}")
    if a <= 0 or b <= 0:
        raise ValueError(f"a and b must be positive, got a={a}, b={b}")
    if x == 0.0:
        return 0.0
    if x == 1.0:
        return 1.0

    # Use symmetry: I_x(a,b) = 1 - I_{1-x}(b,a) when x > (a+1)/(a+b+2)
    if x < (a + 1.0) / (a + b + 2.0):
        log_prefix = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                      + a * math.log(x) + b * math.log(1.0 - x))
        return math.exp(log_prefix) * _betacf(a, b, x) / a
    else:
        log_prefix = (math.lgamma(a + b) - math.lgamma(b) - math.lgamma(a)
                      + b * math.log(1.0 - x) + a * math.log(x))
        return 1.0 - math.exp(log_prefix) * _betacf(b, a, 1.0 - x) / b


def _gammainc_series(a: float, x: float,
                     max_iter: int = 300, eps: float = 1e-14) -> float:
    """Series expansion for the regularized lower incomplete gamma function."""
    if x == 0.0:
        return 0.0
    ap = a
    sum_val = 1.0 / a
    delta = sum_val
    for _ in range(max_iter):
        ap += 1.0
        delta *= x / ap
        sum_val += delta
        if abs(delta) < abs(sum_val) * eps:
            break
    log_prefix = a * math.log(x) - x - math.lgamma(a)
    return sum_val * math.exp(log_prefix)


def _gammainc_cf(a: float, x: float,
                 max_iter: int = 300, eps: float = 1e-14) -> float:
    """Continued fraction for the upper incomplete gamma (Lentz's method)."""
    b0 = x + 1.0 - a
    c = 1.0 / 1e-30
    d = 1.0 / b0 if abs(b0) > 1e-30 else 1.0 / 1e-30
    h = d
    for i in range(1, max_iter + 1):
        an = -i * (i - a)
        b0 += 2.0
        d = an * d + b0
        if abs(d) < 1e-30:
            d = 1e-30
        c = b0 + an / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    log_prefix = a * math.log(x) - x - math.lgamma(a)
    return math.exp(log_prefix) * h


def gammainc_lower(a: float, x: float) -> float:
    """Regularized lower incomplete gamma function P(a, x).

    P(a, x) = gamma(a, x) / Gamma(a)
    Used for chi-square CDF: chi2_cdf(x, k) = P(k/2, x/2).
    """
    if x < 0.0:
        return 0.0
    if x == 0.0:
        return 0.0
    if a <= 0:
        raise ValueError(f"a must be positive, got {a}")
    if x < a + 1.0:
        return _gammainc_series(a, x)
    else:
        return 1.0 - _gammainc_cf(a, x)


# ──────────────────────────────────────────────────────────────
# 2. DISTRIBUTION CDFs
# ──────────────────────────────────────────────────────────────

def normal_cdf(x: float) -> float:
    """Standard normal CDF. Uses math.erf (accurate to full precision)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def normal_sf(x: float) -> float:
    """Standard normal survival function 1 - CDF."""
    return 0.5 * math.erfc(x / math.sqrt(2.0))


def t_cdf(t_val: float, df: float) -> float:
    """CDF of Student's t-distribution with df degrees of freedom.

    Uses the regularized incomplete beta function:
      F(t) = 1 - 0.5 * I_x(df/2, 1/2)   for t >= 0
      F(t) = 0.5 * I_x(df/2, 1/2)        for t < 0
    where x = df / (df + t^2).

    Accurate to ~14 significant digits (vs. the normal approximation
    that was off by up to 11x for small df).
    """
    if df <= 0:
        raise ValueError(f"df must be positive, got {df}")
    if t_val == 0:
        return 0.5
    x = df / (df + t_val * t_val)
    ib = betainc(df / 2.0, 0.5, x)
    if t_val > 0:
        return 1.0 - 0.5 * ib
    else:
        return 0.5 * ib


def t_sf(t_val: float, df: float) -> float:
    """Survival function (1 - CDF) of Student's t-distribution."""
    return 1.0 - t_cdf(t_val, df)


def chi2_cdf(x: float, df: int) -> float:
    """CDF of chi-squared distribution.

    chi2_cdf(x, k) = P(k/2, x/2) where P is the regularized
    lower incomplete gamma function.
    """
    if x <= 0:
        return 0.0
    if df <= 0:
        raise ValueError(f"df must be positive, got {df}")
    return gammainc_lower(df / 2.0, x / 2.0)


def chi2_sf(x: float, df: int) -> float:
    """Survival function (p-value) of chi-squared distribution."""
    return 1.0 - chi2_cdf(x, df)


# ──────────────────────────────────────────────────────────────
# 3. STATISTICAL TESTS
# ──────────────────────────────────────────────────────────────

def welch_t_test(m1: float, sd1: float, n1: int,
                 m2: float, sd2: float, n2: int) -> Tuple[float, float, float]:
    """Welch's unequal-variance t-test.

    Returns (t_statistic, degrees_of_freedom, two_sided_p_value).

    Handles edge cases:
      - se=0 with equal means → p=1.0
      - se=0 with different means → p≈0 (impossible constant data)
      - n < 2 → raises ValueError
    """
    if n1 < 2 or n2 < 2:
        raise ValueError(f"Group sizes must be >= 2, got n1={n1}, n2={n2}")

    v1 = sd1 ** 2
    v2 = sd2 ** 2
    se = math.sqrt(v1 / n1 + v2 / n2)

    if se == 0:
        if m1 == m2:
            return (0.0, float(n1 + n2 - 2), 1.0)
        else:
            # Impossible: constant variable with different means
            return (float('inf'), float(n1 + n2 - 2), 1e-15)

    t_stat = (m1 - m2) / se

    # Welch-Satterthwaite degrees of freedom
    num = (v1 / n1 + v2 / n2) ** 2
    denom = (v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1)
    df = num / denom

    # Two-sided p-value
    p = 2.0 * (1.0 - t_cdf(abs(t_stat), df))
    return (t_stat, df, max(p, 1e-15))


def chi2_gof_test(observed: List[float],
                  expected: List[float]) -> Tuple[float, int, float]:
    """Chi-square goodness-of-fit test.

    Returns (chi_square_statistic, degrees_of_freedom, p_value).
    df = len(observed) - 1 (one constraint: totals match).
    """
    if len(observed) != len(expected):
        raise ValueError("observed and expected must have same length")
    k = len(observed)
    if k < 2:
        raise ValueError("Need at least 2 categories")

    chi_sq = sum((o - e) ** 2 / e for o, e in zip(observed, expected)
                 if e > 0)
    df = k - 1
    p = chi2_sf(chi_sq, df)
    return (chi_sq, df, p)


def binom_pmf(k: int, n: int, p: float) -> float:
    """Binomial probability mass function P(X = k)."""
    if k < 0 or k > n:
        return 0.0
    log_pmf = (math.lgamma(n + 1) - math.lgamma(k + 1)
               - math.lgamma(n - k + 1))
    if p > 0:
        log_pmf += k * math.log(p)
    elif k > 0:
        return 0.0
    if p < 1:
        log_pmf += (n - k) * math.log(1 - p)
    elif k < n:
        return 0.0
    return math.exp(log_pmf)


def binom_test_greater(k: int, n: int, p: float = 0.5) -> float:
    """One-sided binomial test: P(X >= k) where X ~ Binomial(n, p).

    Used by p-curve analysis to test whether the proportion of
    p-values in the high bin exceeds what's expected by chance.
    """
    return sum(binom_pmf(i, n, p) for i in range(k, n + 1))


def fisher_method(p_values: List[float],
                  direction: str = "standard") -> Tuple[float, int, float]:
    """Fisher's method for combining p-values.

    direction="standard": -2 * sum(ln(p))  — tests if p-values are too small
    direction="reversed": -2 * sum(ln(1-p)) — tests if p-values cluster near 1.0
                          (Carlisle method for detecting too-perfect balance)

    Returns (chi_square_statistic, df, combined_p_value).
    """
    if not p_values:
        raise ValueError("p_values must not be empty")

    if direction == "standard":
        chi_sq = -2.0 * sum(math.log(max(p, 1e-15)) for p in p_values)
    elif direction == "reversed":
        chi_sq = -2.0 * sum(math.log(max(1.0 - p, 1e-15)) for p in p_values)
    else:
        raise ValueError(f"direction must be 'standard' or 'reversed', got {direction}")

    df = 2 * len(p_values)
    combined_p = chi2_sf(chi_sq, df)
    return (chi_sq, df, combined_p)


def benjamini_hochberg(p_values: List[float],
                       alpha: float = 0.05) -> List[Tuple[int, float, bool]]:
    """Benjamini-Hochberg FDR correction for multiple testing.

    Returns list of (original_index, adjusted_p_value, is_significant)
    sorted by original index.
    """
    n = len(p_values)
    if n == 0:
        return []

    # Sort by p-value, keeping track of original indices
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])

    # Compute adjusted p-values
    adjusted = [0.0] * n
    prev_adj = 0.0
    for rank, (orig_idx, p) in enumerate(indexed, 1):
        adj_p = min(p * n / rank, 1.0)
        adjusted[orig_idx] = adj_p

    # Enforce monotonicity (adjusted p-values must be non-decreasing
    # when sorted by original p-value)
    # Work backwards through sorted order
    min_so_far = 1.0
    for rank in range(n, 0, -1):
        orig_idx = indexed[rank - 1][0]
        adjusted[orig_idx] = min(adjusted[orig_idx], min_so_far)
        min_so_far = adjusted[orig_idx]

    return [(i, adjusted[i], adjusted[i] <= alpha) for i in range(n)]
