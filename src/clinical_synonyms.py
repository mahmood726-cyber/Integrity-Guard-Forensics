"""
Medical abbreviation and synonym dictionary for clinical outcome matching.

Solves the core problem: SequenceMatcher gives 0.18 similarity for
"Major Adverse Cardiovascular Events" vs "MACE", but they are identical.

Approach:
  1. Abbreviation expansion: MACE → Major Adverse Cardiovascular Events
  2. Synonym groups: "mortality" ≡ "death" ≡ "died"
  3. Token-set similarity: Jaccard on word sets (order-independent)
  4. Hard vs surrogate endpoint classification
"""

import re
from typing import Dict, List, Set, Tuple, Optional
from difflib import SequenceMatcher


# ──────────────────────────────────────────────────────────────
# 1. ABBREVIATION DICTIONARY
# ──────────────────────────────────────────────────────────────

ABBREVIATIONS: Dict[str, str] = {
    # Cardiology
    "mace": "major adverse cardiovascular events",
    "cv": "cardiovascular",
    "mi": "myocardial infarction",
    "hf": "heart failure",
    "chf": "congestive heart failure",
    "af": "atrial fibrillation",
    "lvef": "left ventricular ejection fraction",
    "nyha": "new york heart association",
    "sbp": "systolic blood pressure",
    "dbp": "diastolic blood pressure",
    "bp": "blood pressure",
    "nt-probnp": "n-terminal pro-brain natriuretic peptide",
    "probnp": "pro-brain natriuretic peptide",
    "bnp": "brain natriuretic peptide",
    "egfr": "estimated glomerular filtration rate",
    "uacr": "urine albumin-to-creatinine ratio",
    "ldl": "low density lipoprotein",
    "ldl-c": "low density lipoprotein cholesterol",
    "hdl": "high density lipoprotein",
    "hdl-c": "high density lipoprotein cholesterol",
    "hba1c": "glycated hemoglobin",
    "tia": "transient ischemic attack",
    "pci": "percutaneous coronary intervention",
    "cabg": "coronary artery bypass grafting",
    "acs": "acute coronary syndrome",
    "stemi": "st elevation myocardial infarction",
    "nstemi": "non-st elevation myocardial infarction",
    "scd": "sudden cardiac death",

    # Oncology
    "os": "overall survival",
    "pfs": "progression-free survival",
    "dfs": "disease-free survival",
    "efs": "event-free survival",
    "rfs": "relapse-free survival",
    "ttp": "time to progression",
    "orr": "overall response rate",
    "cr": "complete response",
    "pr": "partial response",
    "sd": "stable disease",
    "pd": "progressive disease",
    "pcr": "pathological complete response",
    "dcr": "disease control rate",
    "dor": "duration of response",
    "ctdna": "circulating tumor dna",
    "psa": "prostate specific antigen",
    "ca-125": "cancer antigen 125",
    "cea": "carcinoembryonic antigen",

    # General
    "qol": "quality of life",
    "hrqol": "health related quality of life",
    "ae": "adverse event",
    "sae": "serious adverse event",
    "teae": "treatment emergent adverse event",
    "bmi": "body mass index",
    "gfr": "glomerular filtration rate",
    "fev1": "forced expiratory volume in one second",
    "bmd": "bone mineral density",
    "vas": "visual analog scale",
    "itt": "intention to treat",
    "pp": "per protocol",
    "ci": "confidence interval",
    "hr": "hazard ratio",
    "rr": "relative risk",
    "or": "odds ratio",
    "nnt": "number needed to treat",
}


# ──────────────────────────────────────────────────────────────
# 2. SYNONYM GROUPS (words that mean the same clinical concept)
# ──────────────────────────────────────────────────────────────

SYNONYM_GROUPS: List[Set[str]] = [
    {"mortality", "death", "died", "dying", "fatal", "fatality"},
    {"survival", "alive", "living"},
    {"myocardial infarction", "heart attack", "mi"},
    {"stroke", "cerebrovascular accident", "cva"},
    {"hospitalization", "hospitalisation", "hospital admission", "admitted"},
    {"recurrence", "relapse", "recurrent"},
    {"progression", "progressed", "progressive"},
    {"response", "responded", "responder"},
    {"remission", "complete remission"},
    {"adverse event", "side effect", "adverse reaction", "toxicity"},
    {"blood pressure", "bp", "arterial pressure"},
    {"kidney", "renal", "nephro"},
    {"heart", "cardiac", "cardio"},
    {"all-cause", "all cause", "all causes", "any cause"},
    {"composite", "combined", "co-primary"},
]

# Build a lookup: word → canonical form (first in group)
_SYNONYM_MAP: Dict[str, str] = {}
for group in SYNONYM_GROUPS:
    canonical = sorted(group)[0]  # alphabetically first = canonical
    for word in group:
        _SYNONYM_MAP[word] = canonical


# ──────────────────────────────────────────────────────────────
# 3. HARD vs SURROGATE ENDPOINT CLASSIFICATION
# ──────────────────────────────────────────────────────────────

HARD_ENDPOINTS: List[str] = [
    "survival", "mortality", "death", "overall survival",
    "stroke", "myocardial infarction", "heart attack",
    "heart failure hospitalization", "hospitalization",
    "cardiovascular death", "cardiac death", "sudden cardiac death",
    "cardiac arrest", "ventricular arrhythmia",
    "all-cause mortality", "all-cause hospitalization",
    "renal failure", "dialysis", "transplant", "transplantation",
    "amputation", "disability",
    "mace", "major adverse cardiovascular events",
    "progression-free survival", "disease-free survival",
    "event-free survival", "relapse-free survival",
    "quality of life", "functional capacity",
]

SURROGATE_ENDPOINTS: List[str] = [
    "biomarker", "blood pressure", "systolic blood pressure",
    "diastolic blood pressure", "cholesterol", "ldl", "hdl",
    "imaging", "symptom score", "laboratory",
    "ejection fraction", "lvef", "nt-probnp", "bnp", "probnp",
    "troponin", "egfr", "uacr", "hba1c", "fev1",
    "bone mineral density", "bmd", "viral load",
    "tumor response rate", "overall response rate", "orr",
    "disease control rate", "dcr", "duration of response",
    "ctdna", "tumor marker", "psa", "ca-125", "cea",
    "visual analog scale", "vas", "body mass index", "bmi",
    "change from baseline",
]


# ──────────────────────────────────────────────────────────────
# 4. MATCHING FUNCTIONS
# ──────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, normalize whitespace, flatten parentheticals."""
    text = text.lower().strip()
    # Flatten parenthetical qualifiers: "mortality (all causes)" → "mortality all causes"
    text = re.sub(r'[(\)]', ' ', text)
    text = re.sub(r'[^\w\s-]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _expand_abbreviations(text: str) -> str:
    """Expand known medical abbreviations in a text string."""
    normalized = _normalize(text)
    words = normalized.split()
    expanded = []
    for w in words:
        if w in ABBREVIATIONS:
            expanded.append(ABBREVIATIONS[w])
        else:
            expanded.append(w)
    return " ".join(expanded)


def _canonicalize_synonyms(text: str) -> str:
    """Replace synonyms with their canonical form."""
    # Try multi-word synonyms first (longest match)
    result = text
    for group in SYNONYM_GROUPS:
        for term in sorted(group, key=len, reverse=True):
            if term in result:
                canonical = sorted(group)[0]
                result = result.replace(term, canonical)
    return result


def _extract_timeframe(text: str) -> Optional[str]:
    """Extract timeframe from outcome description (e.g., '12 months', '1 year')."""
    patterns = [
        r'(\d+)\s*(?:month|mo)s?',
        r'(\d+)\s*(?:week|wk)s?',
        r'(\d+)\s*(?:year|yr)s?',
        r'(\d+)\s*(?:day)s?',
        r'at\s+(\d+)\s*(?:month|week|year|day)s?',
    ]
    for pat in patterns:
        m = re.search(pat, text.lower())
        if m:
            return m.group(0)
    return None


def _token_set_similarity(a: str, b: str) -> float:
    """Jaccard similarity on word sets (order-independent).

    "All-cause mortality at 12 months" vs "Mortality from all causes"
    shares most tokens even if SequenceMatcher gives low score.
    """
    set_a = set(a.lower().split())
    set_b = set(b.lower().split())
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def clinical_similarity(text_a: str, text_b: str) -> float:
    """Compute clinical-aware similarity between two outcome descriptions.

    Three-layer matching:
      1. Expand abbreviations → SequenceMatcher
      2. Canonicalize synonyms → SequenceMatcher
      3. Token-set (Jaccard) similarity

    Returns the maximum similarity across all methods (0.0 to 1.0).
    """
    # Layer 1: Direct SequenceMatcher
    norm_a = _normalize(text_a)
    norm_b = _normalize(text_b)
    sim_direct = SequenceMatcher(None, norm_a, norm_b).ratio()

    # Layer 2: Abbreviation expansion + SequenceMatcher
    exp_a = _expand_abbreviations(text_a)
    exp_b = _expand_abbreviations(text_b)
    sim_expanded = SequenceMatcher(None, exp_a, exp_b).ratio()

    # Layer 3: Synonym canonicalization + SequenceMatcher
    can_a = _canonicalize_synonyms(exp_a)
    can_b = _canonicalize_synonyms(exp_b)
    sim_canonical = SequenceMatcher(None, can_a, can_b).ratio()

    # Layer 4: Token-set Jaccard (catches reordering)
    sim_jaccard = _token_set_similarity(can_a, can_b)

    return max(sim_direct, sim_expanded, sim_canonical, sim_jaccard)


def detect_timeframe_change(text_a: str, text_b: str) -> Optional[str]:
    """Detect if two matched outcomes have different timeframes.

    Returns a warning string if timeframes differ, None if they match or
    neither specifies a timeframe.
    """
    tf_a = _extract_timeframe(text_a)
    tf_b = _extract_timeframe(text_b)
    if tf_a and tf_b and tf_a != tf_b:
        return f"Timeframe changed: '{tf_a}' vs '{tf_b}'"
    return None


def classify_endpoint(measure: str) -> str:
    """Classify an outcome measure as HARD, SURROGATE, or UNKNOWN."""
    lower = _normalize(measure)
    expanded = _expand_abbreviations(measure)

    for ep in HARD_ENDPOINTS:
        if ep in lower or ep in expanded:
            return "HARD"
    for ep in SURROGATE_ENDPOINTS:
        if ep in lower or ep in expanded:
            return "SURROGATE"
    return "UNKNOWN"
