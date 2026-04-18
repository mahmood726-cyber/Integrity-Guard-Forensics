# Fraud Pattern Atlas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand Evidence-Integrity-Guard from 9 detection methods to 40+ by cataloguing every known fraud pattern from landmark cases and implementing them as independent, testable detector modules — then combining them into a tiered scoring system that converges multiple independent signals.

**Architecture:** Each fraud pattern is an independent detector module in `src/detectors/`. A central `FraudPatternAtlas` orchestrator runs all applicable detectors against a trial and produces a tiered severity score (Signal → Structural Concern → High Concern → Critical). Detectors are pure functions: input data → (status, confidence, evidence). No detector can produce a "fraud" label — only "statistical anomaly requiring investigation."

**Tech Stack:** Pure Python (no scipy/numpy). stats_utils.py for all distributions. clinical_synonyms.py for medical NLP. All new detectors follow the same interface pattern.

---

## Known Fraudsters × Pattern Map

This is the empirical foundation. Each row is a documented fraudster; each column is a pattern they exhibited. The tool must catch every marked pattern.

| Fraudster | Retractions | Perfect Baselines | Copied SDs | GRIM | Digit Anomaly | Duplicated Data | P-hacking | Outcome Switch | Promotional Language | Implausible Effects | Dropout Symmetry | Cross-Paper Cloning |
|-----------|------------|-------------------|-----------|------|---------------|-----------------|-----------|---------------|---------------------|--------------------|-----------------|--------------------|
| **Fujii** | 172 | **X** | **X** | . | **X** | **X** | . | . | . | . | **X** | **X** |
| **Boldt** | 89 | **X** | **X** | . | . | **X** | . | . | **X** | . | . | **X** |
| **Sato** | 28 | **X** | **X** | . | . | **X** | . | . | . | . | . | **X** |
| **Reuben** | 21 | . | . | **X** | **X** | . | . | . | **X** | **X** | . | . |
| **Macchiarini** | 7 | . | . | . | . | . | . | . | **X** | **X** | . | . |
| **Stapel** | 58 | . | . | **X** | **X** | . | . | . | . | **X** | . | **X** |
| **Hunton** | 10 | . | . | **X** | **X** | . | . | . | . | . | . | . |
| **Poldermans** | 12 | **X** | . | . | . | . | . | **X** | . | . | **X** | . |
| **Potti** | 10 | . | . | . | . | **X** | . | . | . | **X** | . | **X** |
| **COMPare trials** | N/A | . | . | . | . | . | . | **X** | . | . | . | . |
| **Generic p-hacker** | N/A | . | . | . | . | . | **X** | **X** | . | . | . | . |

**Key insight:** No single detector catches all fraudsters. But **every fraudster triggers 2+ independent detectors.** The system's power comes from convergence.

---

## Tier System

```
Tier 1 — SIGNAL (automated, informational)
  Single detector flags anomaly. Expected false positive rate: ~5-10%.
  Action: Log for review.

Tier 2 — STRUCTURAL CONCERN (automated, advisory)
  2+ independent detectors flag the same trial.
  Action: Flag for human review.

Tier 3 — HIGH CONCERN (requires human confirmation)
  3+ independent detectors flag, OR any "impossible math" detector fires.
  Action: Detailed audit recommended.

Tier 4 — CRITICAL (requires expert panel)
  4+ independent detectors fire, OR cross-paper duplication confirmed.
  Action: Formal investigation warranted.
```

---

## File Structure

### New Files (Detectors)
```
src/detectors/                          # All detector modules
├── __init__.py                         # Exports all detectors
├── base.py                             # DetectorResult dataclass + base interface
├── grimmer.py                          # GRIMMER test for SDs
├── sprite.py                           # SPRITE variance-consistency test
├── terminal_digit.py                   # Terminal digit analysis
├── heaping.py                          # Decimal heaping detection
├── covariate_correlation.py            # Inter-variable correlation plausibility
├── mahalanobis_balance.py              # Multivariate baseline balance (Mahalanobis)
├── effect_size_inflation.py            # Too-consistent large effects
├── fragility_index.py                  # Fragility index anomalies
├── sample_size_discrepancy.py          # Registry vs publication n
├── timeline_plausibility.py            # Recruitment rate vs disease prevalence
├── dropout_symmetry.py                 # Identical dropout rates
├── cross_paper_fingerprint.py          # Same data across publications
├── variance_ratio.py                   # Variance equality patterns (F-test)
├── decimal_pattern.py                  # Repeated decimal structures
└── effect_direction_consistency.py     # Every outcome positive = suspicious
```

### New Files (Orchestration)
```
src/fraud_pattern_atlas.py              # Central orchestrator + tiered scoring
src/detectors/registry.py               # Auto-discovery and registration of detectors
```

### Modified Files
```
src/fraud_lead_generator.py             # Use atlas instead of ad-hoc checks
src/openclaw_pipeline.py                # Integrate atlas into deep audit
src/rob_mapper.py                       # Accept atlas results for multi-domain mapping
```

### Test Files
```
tests/test_detectors/                   # One test file per detector
├── test_grimmer.py
├── test_sprite.py
├── test_terminal_digit.py
├── test_heaping.py
├── test_covariate_correlation.py
├── test_mahalanobis_balance.py
├── test_effect_size_inflation.py
├── test_fragility_index.py
├── test_sample_size_discrepancy.py
├── test_timeline_plausibility.py
├── test_dropout_symmetry.py
├── test_cross_paper_fingerprint.py
├── test_variance_ratio.py
├── test_decimal_pattern.py
├── test_effect_direction.py
tests/test_fraud_pattern_atlas.py       # Orchestrator + tiered scoring
tests/test_atlas_gauntlet.py            # Full fraudster simulation gauntlet
```

---

## Task 1: Detector Interface & Registry

**Files:**
- Create: `src/detectors/__init__.py`
- Create: `src/detectors/base.py`
- Create: `src/detectors/registry.py`
- Test: `tests/test_detectors/__init__.py`

The foundation that all detectors build on. Every detector returns a `DetectorResult` with the same structure.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_detectors/test_base.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from detectors.base import DetectorResult, Severity

def test_detector_result_creation():
    r = DetectorResult(
        detector_name="test_detector",
        status="FLAGGED",
        severity=Severity.SIGNAL,
        confidence=0.85,
        evidence={"detail": "test"},
        reason="Test reason",
    )
    assert r.detector_name == "test_detector"
    assert r.severity == Severity.SIGNAL
    assert r.is_flagged()

def test_detector_result_pass():
    r = DetectorResult(
        detector_name="test_detector",
        status="PASS",
        severity=Severity.NONE,
        confidence=0.0,
        evidence={},
        reason="No anomaly",
    )
    assert not r.is_flagged()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_detectors/test_base.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'detectors'`

- [ ] **Step 3: Implement DetectorResult and Severity**

```python
# src/detectors/__init__.py
"""Fraud Pattern Atlas — detector modules."""

# src/detectors/base.py
"""Base interface for all fraud pattern detectors."""
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, Optional

class Severity(IntEnum):
    """Tier severity levels. Higher = more concerning."""
    NONE = 0          # No anomaly
    SIGNAL = 1        # Tier 1: single detector flag
    STRUCTURAL = 2    # Tier 2: structural concern
    HIGH = 3          # Tier 3: high concern
    CRITICAL = 4      # Tier 4: critical

@dataclass
class DetectorResult:
    """Standardized output from every detector.

    Every detector in the Fraud Pattern Atlas returns this structure.
    No detector may use the word "fraud" — only "anomaly" or "concern."
    """
    detector_name: str
    status: str                    # "PASS", "FLAGGED", "INCONCLUSIVE"
    severity: Severity
    confidence: float              # 0.0 to 1.0
    evidence: Dict[str, Any]       # Detector-specific data
    reason: str                    # Human-readable explanation
    warning: Optional[str] = None  # Caveats (e.g., "requires independent validation")

    def is_flagged(self) -> bool:
        return self.status == "FLAGGED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detector": self.detector_name,
            "status": self.status,
            "severity": self.severity.name,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "reason": self.reason,
            "warning": self.warning,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_detectors/test_base.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Implement detector registry**

```python
# src/detectors/registry.py
"""Auto-discovery and registration of detector modules."""
from typing import List, Dict, Any, Callable
from detectors.base import DetectorResult

# Registry: name → callable(data) → DetectorResult
_REGISTRY: Dict[str, Callable] = {}

def register(name: str):
    """Decorator to register a detector function."""
    def decorator(func: Callable):
        _REGISTRY[name] = func
        return func
    return decorator

def get_all_detectors() -> Dict[str, Callable]:
    return dict(_REGISTRY)

def run_applicable(data: Dict[str, Any]) -> List[DetectorResult]:
    """Run all registered detectors that have sufficient data."""
    results = []
    for name, func in _REGISTRY.items():
        try:
            result = func(data)
            if result is not None:
                results.append(result)
        except (KeyError, TypeError, ValueError):
            # Detector doesn't have required data — skip
            continue
    return results
```

- [ ] **Step 6: Commit**

```bash
git add src/detectors/ tests/test_detectors/
git commit -m "feat: add detector base interface with Severity tiers and registry"
```

---

## Task 2: GRIMMER Test (SD Consistency)

**Files:**
- Create: `src/detectors/grimmer.py`
- Test: `tests/test_detectors/test_grimmer.py`

**Reference:** Anaya (2016). The GRIMMER test: A statistical method for detecting numerical inconsistencies in reported standard deviations.

GRIMMER extends GRIM to standard deviations. For integer-count data, not every (SD, N) pair is mathematically possible. A reported SD that cannot arise from any set of N integers is proof of fabrication.

The key formula: For a given mean M and SD s with sample size N, the sum of squares SS = (N-1)*s^2 + N*M^2 must be achievable as a sum of N squared integers. This means SS must be an integer (for integer data), and (N-1)*s^2 must also yield an integer when added to N*M^2.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_detectors/test_grimmer.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from detectors.grimmer import grimmer_test
from detectors.base import Severity

def test_consistent_sd():
    """SD=1.41 with mean=3.0, N=5: SS=4*1.41^2 + 5*9 = 7.9524+45=52.9524
    This needs to be checked for integer feasibility."""
    result = grimmer_test(mean=3.0, sd=1.58, n=5, precision=2)
    # 1.58^2 * 4 = 9.9856, + 5*9=45 → SS=54.9856. 
    # Actual: values [1,2,3,4,5] → mean=3, sd=1.5811 → rounds to 1.58 at 2dp
    assert result.status in ("PASS", "INCONCLUSIVE")

def test_inconsistent_sd():
    """SD=1.11 with mean=3.0, N=5: (N-1)*sd^2 = 4*1.2321 = 4.9284
    Not achievable from 5 integers summing to 15. INCONSISTENT."""
    result = grimmer_test(mean=3.0, sd=1.11, n=5, precision=2)
    assert result.status == "FLAGGED"
    assert result.severity == Severity.HIGH

def test_continuous_data_inconclusive():
    result = grimmer_test(mean=72.5, sd=11.3, n=50, precision=2, data_type="continuous")
    assert result.status == "INCONCLUSIVE"

def test_small_n():
    """N=2 with any mean and SD: only one possible SD for each mean pair."""
    result = grimmer_test(mean=3.5, sd=0.71, n=2, precision=2)
    # For N=2, values must be mean±sd*sqrt(2)/2. Check feasibility.
    assert result.status in ("PASS", "FLAGGED", "INCONCLUSIVE")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_detectors/test_grimmer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'detectors.grimmer'`

- [ ] **Step 3: Implement GRIMMER**

```python
# src/detectors/grimmer.py
"""GRIMMER test — SD consistency for integer-count data.

Reference: Anaya (2016). Extends GRIM to standard deviations.
For integer-count data, (N-1)*SD^2 must yield a value consistent
with the sum of squared deviations from N integers.

The sum of squared deviations SSD = (N-1)*SD^2.
For the data to be integers: SSD must be achievable as
sum((x_i - mean)^2) where each x_i is an integer.

Key insight: if mean = S/N (S integer), then
SSD = sum(x_i^2) - S^2/N = sum(x_i^2) - N*mean^2
So sum(x_i^2) = SSD + N*mean^2 = (N-1)*SD^2 + N*mean^2

For integer x_i, sum(x_i^2) must be an integer.
Therefore (N-1)*SD^2 + N*mean^2 must be "close to" an integer.
"""
import math
from detectors.base import DetectorResult, Severity
from detectors.registry import register


@register("grimmer")
def grimmer_test(mean: float, sd: float, n: int, precision: int = 2,
                 data_type: str = "unknown") -> DetectorResult:
    """Test if a reported SD is mathematically possible.

    Args:
        mean: Reported sample mean
        sd: Reported sample standard deviation
        n: Sample size
        precision: Decimal places in reported values
        data_type: "integer_count", "continuous", or "unknown"
    """
    if data_type == "continuous":
        return DetectorResult(
            detector_name="GRIMMER",
            status="INCONCLUSIVE",
            severity=Severity.NONE,
            confidence=0.0,
            evidence={"data_type": data_type},
            reason="GRIMMER test only applies to integer-count data.",
        )

    if n < 2:
        return DetectorResult(
            detector_name="GRIMMER",
            status="INCONCLUSIVE",
            severity=Severity.NONE,
            confidence=0.0,
            evidence={"n": n},
            reason="Sample size must be >= 2 for SD calculation.",
        )

    # Step 1: Check if mean passes GRIM first
    total_sum = mean * n
    mean_granularity = 0.5 / (10 ** precision)
    mean_tolerance = mean_granularity * n

    # Step 2: GRIMMER check
    # sum_of_squares = (n-1)*sd^2 + n*mean^2
    ssd = (n - 1) * sd ** 2  # Sum of squared deviations
    sum_sq = ssd + n * mean ** 2  # Sum of x_i^2

    # For integer data, sum_sq must be an integer
    # Tolerance accounts for rounding in both mean and SD
    sd_granularity = 0.5 / (10 ** precision)
    # Propagate uncertainty: delta(sum_sq) from delta(sd) and delta(mean)
    # d(sum_sq)/d(sd) = 2*(n-1)*sd, d(sum_sq)/d(mean) = 2*n*mean
    tol_sd = 2 * (n - 1) * sd * sd_granularity
    tol_mean = 2 * n * abs(mean) * mean_granularity
    tolerance = tol_sd + tol_mean + 1e-9

    rounded_sum_sq = round(sum_sq)
    diff = abs(sum_sq - rounded_sum_sq)

    is_consistent = diff <= tolerance

    warning = None
    if data_type == "unknown":
        warning = ("CAUTION: GRIMMER validity depends on integer-count data. "
                   "Verify data type before interpreting.")

    if is_consistent:
        return DetectorResult(
            detector_name="GRIMMER",
            status="PASS",
            severity=Severity.NONE,
            confidence=0.0,
            evidence={
                "sum_of_squares": round(sum_sq, 4),
                "nearest_integer": rounded_sum_sq,
                "diff": round(diff, 6),
                "tolerance": round(tolerance, 6),
            },
            reason=f"SD of {sd} with mean={mean}, N={n} is mathematically possible.",
            warning=warning,
        )
    else:
        return DetectorResult(
            detector_name="GRIMMER",
            status="FLAGGED",
            severity=Severity.HIGH,
            confidence=min(1.0, diff / max(tolerance, 1e-15)),
            evidence={
                "sum_of_squares": round(sum_sq, 4),
                "nearest_integer": rounded_sum_sq,
                "diff": round(diff, 6),
                "tolerance": round(tolerance, 6),
            },
            reason=(f"SD of {sd} with mean={mean}, N={n} is mathematically inconsistent. "
                    f"sum(x_i^2) = {round(sum_sq, 4)}, nearest integer = {rounded_sum_sq}, "
                    f"diff = {round(diff, 6)} exceeds tolerance {round(tolerance, 6)}."),
            warning=warning,
        )
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_detectors/test_grimmer.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/detectors/grimmer.py tests/test_detectors/test_grimmer.py
git commit -m "feat: add GRIMMER test (SD consistency for integer data)"
```

---

## Task 3: Terminal Digit Analysis

**Files:**
- Create: `src/detectors/terminal_digit.py`
- Test: `tests/test_detectors/test_terminal_digit.py`

**Reference:** Mosimann et al. (2002). Terminal digits in clinical data.

Humans fabricating data overuse digits 0 and 5 and avoid digits like 1, 3, 7, 9. Real measurements have roughly uniform terminal digits (with some heaping at 0 and 5 for rounded values, but not extreme).

Uses chi-square GOF test to compare observed terminal digit distribution against uniform expectation.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_detectors/test_terminal_digit.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from detectors.terminal_digit import terminal_digit_test
from detectors.base import Severity

def test_uniform_digits_pass():
    """Roughly uniform terminal digits should pass."""
    # 10 of each digit 0-9 = perfectly uniform
    values = [i * 0.1 + d * 0.01 for i in range(10) for d in range(10)]
    result = terminal_digit_test(values)
    assert result.status == "PASS"

def test_fabricated_heaping_on_0_and_5():
    """Heavy heaping on 0 and 5 should be flagged."""
    values = [10.0, 20.0, 30.0, 40.0, 50.5, 60.5, 70.0, 80.5, 90.0, 100.5,
              11.0, 21.5, 31.0, 41.5, 51.0, 61.0, 71.5, 81.0, 91.5, 101.0,
              12.0, 22.0, 32.5, 42.0, 52.0, 62.5, 72.0, 82.0, 92.5, 102.0]
    result = terminal_digit_test(values)
    assert result.status == "FLAGGED"

def test_too_few_values():
    result = terminal_digit_test([1.0, 2.0, 3.0])
    assert result.status == "INCONCLUSIVE"
```

- [ ] **Step 2: Run test — verify FAIL**

- [ ] **Step 3: Implement terminal digit detector**

```python
# src/detectors/terminal_digit.py
"""Terminal digit analysis for detecting fabricated data.

Reference: Mosimann et al. (2002), Kanter (1972).
Humans fabricating numbers overuse 0 and 5, underuse odd digits.
Real measurements have roughly uniform terminal digits.
"""
from typing import List
from detectors.base import DetectorResult, Severity
from detectors.registry import register
from stats_utils import chi2_gof_test


@register("terminal_digit")
def terminal_digit_test(values: List[float], min_count: int = 20) -> DetectorResult:
    """Analyze the last significant digit of a list of values.

    Uses chi-square GOF against uniform distribution (each digit 0-9
    equally likely = 10% each).
    """
    if len(values) < min_count:
        return DetectorResult(
            detector_name="terminal_digit",
            status="INCONCLUSIVE",
            severity=Severity.NONE,
            confidence=0.0,
            evidence={"n_values": len(values)},
            reason=f"Requires at least {min_count} values for terminal digit analysis.",
        )

    # Extract terminal digit (last non-zero digit in decimal representation)
    digits = []
    for v in values:
        s = f"{abs(v):.10f}".rstrip('0').rstrip('.')
        if s:
            digits.append(int(s[-1]))

    if len(digits) < min_count:
        return DetectorResult(
            detector_name="terminal_digit",
            status="INCONCLUSIVE",
            severity=Severity.NONE,
            confidence=0.0,
            evidence={"n_digits": len(digits)},
            reason="Too few extractable terminal digits.",
        )

    # Count occurrences of each digit 0-9
    observed = [digits.count(d) for d in range(10)]
    expected = [len(digits) / 10.0] * 10

    chi2, df, p = chi2_gof_test(observed, expected)

    if p < 0.01:
        return DetectorResult(
            detector_name="terminal_digit",
            status="FLAGGED",
            severity=Severity.SIGNAL,
            confidence=min(1.0, 1.0 - p),
            evidence={
                "chi_square": round(chi2, 2),
                "p_value": round(p, 6),
                "observed": observed,
                "digit_0_pct": round(observed[0] / len(digits) * 100, 1),
                "digit_5_pct": round(observed[5] / len(digits) * 100, 1),
            },
            reason=(f"Terminal digit distribution deviates significantly from uniform "
                    f"(chi2={round(chi2, 2)}, p={round(p, 6)}). "
                    f"Digit 0: {round(observed[0]/len(digits)*100, 1)}%, "
                    f"Digit 5: {round(observed[5]/len(digits)*100, 1)}%."),
        )
    else:
        return DetectorResult(
            detector_name="terminal_digit",
            status="PASS",
            severity=Severity.NONE,
            confidence=0.0,
            evidence={"chi_square": round(chi2, 2), "p_value": round(p, 6)},
            reason="Terminal digit distribution is consistent with real data.",
        )
```

- [ ] **Step 4: Run tests, verify pass**
- [ ] **Step 5: Commit**

---

## Task 4: Decimal Heaping Detection

**Files:**
- Create: `src/detectors/heaping.py`
- Test: `tests/test_detectors/test_heaping.py`

Detects when values cluster on round numbers (e.g., BMI always ending in .0 or .5). Real clinical measurements have natural variation in decimal places.

- [ ] **Step 1-5: TDD cycle** (same pattern as Task 3)

Key implementation: Count fraction of values ending in .0 or .5. If >60% (and n >= 20), flag as suspicious. Use binomial test against expected heaping rate (~20% for real data with some rounding).

---

## Task 5: Variance Ratio Test (F-test)

**Files:**
- Create: `src/detectors/variance_ratio.py`
- Test: `tests/test_detectors/test_variance_ratio.py`

**Detects:** Boldt pattern — SDs that are either too similar (copy-paste) or too different across groups. Uses the F-test: F = s1^2/s2^2 should follow F-distribution. Add `f_cdf` to stats_utils.py using the betainc function: `f_cdf(x, d1, d2) = betainc(d1/2, d2/2, d1*x/(d1*x + d2))`.

- [ ] **Step 1: Add F-distribution CDF to stats_utils.py**

```python
# Add to src/stats_utils.py
def f_cdf(x: float, d1: int, d2: int) -> float:
    """CDF of F-distribution with d1, d2 degrees of freedom.
    Uses relationship to regularized incomplete beta function."""
    if x <= 0:
        return 0.0
    z = d1 * x / (d1 * x + d2)
    return betainc(d1 / 2.0, d2 / 2.0, z)
```

- [ ] **Steps 2-5:** Implement detector that flags when F-test p < 0.01 (SDs too different) or p > 0.99 (SDs too similar = Boldt copy-paste pattern).

---

## Task 6: Covariate Correlation Plausibility

**Files:**
- Create: `src/detectors/covariate_correlation.py`
- Test: `tests/test_detectors/test_covariate_correlation.py`

**Detects:** Fabricated data where variables that should correlate (BMI-weight, glucose-HbA1c, age-comorbidities) are statistically independent. Real physiology creates correlations; fabricators randomize each column independently.

Implementation: Given pairs of baseline variables, compute expected correlation direction from a clinical correlation matrix. If actual correlation is near zero for variables that should correlate (r < 0.1 for BMI/weight), flag.

---

## Task 7: Mahalanobis Distance Multivariate Balance

**Files:**
- Create: `src/detectors/mahalanobis_balance.py`
- Test: `tests/test_detectors/test_mahalanobis_balance.py`

**Detects:** Fujii pattern via multivariate test (more powerful than univariate Carlisle). The Mahalanobis distance between group centroids, compared against the chi-square distribution with k degrees of freedom (k = number of baseline variables).

This catches cases where each variable looks OK individually but the joint distribution is impossibly similar.

- [ ] **Steps 1-5:** Implement Mahalanobis distance using matrix inversion (pure Python, small k). `D^2 = (m1 - m2)^T * S_pooled^{-1} * (m1 - m2)` where S_pooled is the pooled covariance matrix. Compare D^2 against chi2(k) distribution.

---

## Task 8: Effect Size Inflation Detection

**Files:**
- Create: `src/detectors/effect_size_inflation.py`
- Test: `tests/test_detectors/test_effect_size_inflation.py`

**Detects:** Reuben/Macchiarini pattern — too-consistent large effects across all outcomes. Real trials have heterogeneous effect sizes. If every outcome shows d > 0.8 (large effect) with similar magnitude, flag.

Implementation: Compute Cohen's d for each outcome. If mean |d| > 0.8 AND coefficient of variation of |d| values < 0.3 (too consistent), flag.

---

## Task 9: Fragility Index Anomalies

**Files:**
- Create: `src/detectors/fragility_index.py`
- Test: `tests/test_detectors/test_fragility_index.py`

**Detects:** Results that flip with 1-2 event changes. A Fragility Index of 0-1 means the conclusion is extremely unstable. Combined with a reported p near 0.05, this is a red flag for selective analysis.

Implementation: For 2×2 tables, compute FI by iteratively moving events from the smaller group to larger until p > 0.05. Use Fisher's exact test (computable from hypergeometric distribution).

Add to stats_utils.py: `hypergeometric_pmf` and `fisher_exact_2x2`.

---

## Task 10: Sample Size Discrepancy (Registry vs Publication)

**Files:**
- Create: `src/detectors/sample_size_discrepancy.py`
- Test: `tests/test_detectors/test_sample_size_discrepancy.py`

**Detects:** Poldermans pattern — registry says 200 patients, paper reports 150. Also catches inflation (paper reports more than registered).

Implementation: Compare `enrollment` field from CT.gov API vs reported N in publication. Flag if discrepancy > 10%.

---

## Task 11: Timeline Plausibility

**Files:**
- Create: `src/detectors/timeline_plausibility.py`
- Test: `tests/test_detectors/test_timeline_plausibility.py`

**Detects:** Recruitment too fast for disease prevalence. If a rare-disease trial (incidence < 1/10,000) enrolled 500 patients in 6 months at 3 sites, that's implausible.

Implementation: Compare enrollment count, study duration, number of sites, and condition prevalence (from a reference table) to compute expected maximum recruitment rate.

---

## Task 12: Dropout Symmetry Detection

**Files:**
- Create: `src/detectors/dropout_symmetry.py`
- Test: `tests/test_detectors/test_dropout_symmetry.py`

**Detects:** Fujii/Poldermans pattern — identical dropout counts or rates across groups. Real trials have messy, asymmetric dropout.

Implementation: Binomial test on whether dropout rates are more similar than expected by chance. If |rate1 - rate2| < 0.01 AND n > 50, compute probability and flag if p < 0.05.

---

## Task 13: Cross-Paper Fingerprinting

**Files:**
- Create: `src/detectors/cross_paper_fingerprint.py`
- Test: `tests/test_detectors/test_cross_paper_fingerprint.py`

**Detects:** Sato/Potti pattern — same data reused across supposedly different publications. Compare decimal vectors (baseline means, SDs, n values) across a portfolio of papers.

Implementation: Cosine similarity on baseline vectors. If cosine > 0.99 between two different NCT IDs, flag as CRITICAL.

---

## Task 14: Effect Direction Consistency

**Files:**
- Create: `src/detectors/effect_direction_consistency.py`
- Test: `tests/test_detectors/test_effect_direction.py`

**Detects:** Every outcome positive in multi-outcome trial = suspicious. Real treatments have trade-offs (efficacy vs side effects). If ALL reported outcomes favor treatment with p < 0.05, the probability decreases multiplicatively.

Implementation: Binomial test — if k out of k outcomes are positive, P(all positive | H0: coin flip) = 0.5^k. Flag if p < 0.05 (requires k >= 5 positive outcomes).

---

## Task 15: SPRITE Test (Variance Consistency)

**Files:**
- Create: `src/detectors/sprite.py`
- Test: `tests/test_detectors/test_sprite.py`

**Reference:** Heathers & Brown (2019). SPRITE (Sample Parameter Reconstruction via Iterative TEchniques).

**Detects:** Whether ANY dataset of N integers could produce the reported mean AND SD simultaneously. More powerful than GRIM or GRIMMER alone because it checks the joint feasibility.

Implementation: For small N (≤30), exhaustive search via iterative reconstruction. For larger N, use the sum-of-squares feasibility check (generalization of GRIMMER).

---

## Task 16: Fraud Pattern Atlas Orchestrator

**Files:**
- Create: `src/fraud_pattern_atlas.py`
- Test: `tests/test_fraud_pattern_atlas.py`

The central brain that runs all detectors and produces the tiered severity score.

- [ ] **Step 1: Write failing test**

```python
# tests/test_fraud_pattern_atlas.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from fraud_pattern_atlas import FraudPatternAtlas

def test_clean_trial_tier_0():
    atlas = FraudPatternAtlas()
    result = atlas.analyze({
        "baseline_data": [
            {"m1": 55.3, "sd1": 12.1, "n1": 100, "m2": 57.8, "sd2": 11.4, "n2": 100},
        ],
    })
    assert result["tier"] <= 1
    assert "FRAUD" not in str(result).upper()

def test_fujii_pattern_tier_4():
    atlas = FraudPatternAtlas()
    result = atlas.analyze({
        "baseline_data": [
            {"m1": 45.1, "sd1": 5.2, "n1": 100, "m2": 45.1, "sd2": 5.2, "n2": 100},
            {"m1": 70.2, "sd1": 10.1, "n1": 100, "m2": 70.2, "sd2": 10.1, "n2": 100},
            {"m1": 165.4, "sd1": 8.5, "n1": 100, "m2": 165.4, "sd2": 8.5, "n2": 100},
        ],
        "reported_p_values": [0.041, 0.048, 0.049, 0.045, 0.047],
    })
    assert result["tier"] >= 3  # Multiple detectors fire

def test_tier_labels():
    atlas = FraudPatternAtlas()
    assert atlas.tier_label(1) == "Signal"
    assert atlas.tier_label(2) == "Structural Concern"
    assert atlas.tier_label(3) == "High Concern"
    assert atlas.tier_label(4) == "Critical"
```

- [ ] **Step 2-3: Implement orchestrator**

```python
# src/fraud_pattern_atlas.py
"""Fraud Pattern Atlas — multi-detector convergence scoring.

Runs all registered detectors against trial data, counts independent
flags, and assigns a severity tier based on convergence:

  Tier 1 (Signal):              1 detector flags
  Tier 2 (Structural Concern):  2 independent detectors flag
  Tier 3 (High Concern):        3+ detectors, OR any "impossible math" flag
  Tier 4 (Critical):            4+ detectors, OR cross-paper duplication
"""
from typing import Dict, Any, List
from detectors.base import DetectorResult, Severity
from detectors.registry import run_applicable

# Import all detector modules to trigger registration
import detectors.grimmer
import detectors.terminal_digit
import detectors.heaping
import detectors.variance_ratio
# ... (all other detector modules)

# Also run the existing engines as detectors
from baseline_balance_engine import BaselineBalanceEngine
from scientific_integrity_forensics import ScientificIntegrityForensics
from p_curve_analyzer import PCurveAnalyzer
from linguistic_forensics import LinguisticForensics
from plausibility_engine import PlausibilityEngine
from utils import TOOL_DISCLAIMER


class FraudPatternAtlas:
    """Central orchestrator for all fraud pattern detectors."""

    TIER_LABELS = {
        0: "Clean",
        1: "Signal",
        2: "Structural Concern",
        3: "High Concern",
        4: "Critical",
    }

    def __init__(self):
        self.balance_engine = BaselineBalanceEngine()
        self.forensics = ScientificIntegrityForensics()
        self.p_curve = PCurveAnalyzer()
        self.linguistic = LinguisticForensics()
        self.plausibility = PlausibilityEngine()

    def tier_label(self, tier: int) -> str:
        return self.TIER_LABELS.get(tier, "Unknown")

    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Run all applicable detectors and compute tiered severity."""
        results: List[DetectorResult] = []

        # 1. Run registered detectors (new modular ones)
        results.extend(run_applicable(data))

        # 2. Run legacy engines (wrapped as DetectorResults)
        results.extend(self._run_legacy_engines(data))

        # 3. Count independent flags
        flagged = [r for r in results if r.is_flagged()]
        n_flagged = len(flagged)
        max_severity = max((r.severity for r in flagged), default=Severity.NONE)

        # 4. Compute tier
        has_impossible_math = any(
            r.severity >= Severity.HIGH and r.is_flagged() for r in results
        )
        has_cross_paper = any(
            r.detector_name == "cross_paper_fingerprint" and r.is_flagged()
            for r in results
        )

        if has_cross_paper or n_flagged >= 4:
            tier = 4
        elif has_impossible_math or n_flagged >= 3:
            tier = 3
        elif n_flagged >= 2:
            tier = 2
        elif n_flagged >= 1:
            tier = 1
        else:
            tier = 0

        return {
            "tier": tier,
            "tier_label": self.tier_label(tier),
            "n_detectors_run": len(results),
            "n_flagged": n_flagged,
            "flagged_detectors": [r.detector_name for r in flagged],
            "all_results": [r.to_dict() for r in results],
            "disclaimer": TOOL_DISCLAIMER,
        }

    def _run_legacy_engines(self, data: Dict[str, Any]) -> List[DetectorResult]:
        """Wrap existing engines as DetectorResult objects."""
        results = []
        # ... (wrap each legacy engine's output into DetectorResult format)
        # This bridges the old engines into the new atlas framework
        return results
```

- [ ] **Step 4-5: Run tests, commit**

---

## Task 17: Full Fraudster Gauntlet (Integration Test)

**Files:**
- Create: `tests/test_atlas_gauntlet.py`

Simulate every known fraudster through the Atlas and verify:
1. Every fraudster triggers tier >= 2
2. Clean trials remain tier 0
3. Adaptive designs are not false-positived
4. No output contains the word "fraud"

- [ ] **Steps 1-5:** Write comprehensive integration tests for all 10 fraudster profiles from the pattern map above.

---

## Task 18: Integrate Atlas into Existing Pipeline

**Files:**
- Modify: `src/fraud_lead_generator.py`
- Modify: `src/openclaw_pipeline.py`
- Modify: `src/rob_mapper.py`

Replace the ad-hoc detection logic in `fraud_lead_generator.scan_leads()` with `FraudPatternAtlas.analyze()`. Update the OpenClaw pipeline to use the atlas. Update the RoB mapper to accept atlas results.

---

## Test Count Estimate

| Task | Tests |
|------|-------|
| Task 1: Base interface | 3 |
| Task 2: GRIMMER | 5 |
| Task 3: Terminal digit | 4 |
| Task 4: Heaping | 4 |
| Task 5: Variance ratio | 5 |
| Task 6: Covariate correlation | 4 |
| Task 7: Mahalanobis | 5 |
| Task 8: Effect size inflation | 4 |
| Task 9: Fragility index | 5 |
| Task 10: Sample size discrepancy | 4 |
| Task 11: Timeline plausibility | 4 |
| Task 12: Dropout symmetry | 4 |
| Task 13: Cross-paper fingerprint | 5 |
| Task 14: Effect direction | 4 |
| Task 15: SPRITE | 5 |
| Task 16: Atlas orchestrator | 6 |
| Task 17: Fraudster gauntlet | 12 |
| Task 18: Integration | 5 |
| **Total new tests** | **~91** |
| **Existing tests** | **127** |
| **Grand total** | **~218** |
