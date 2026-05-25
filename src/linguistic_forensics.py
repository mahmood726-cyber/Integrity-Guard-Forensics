import json
import re
from typing import Any


class LinguisticForensics:
    """
    Analyzes scientific text for linguistic markers of potential fraud/over-promotion.
    Based on research from Retraction Watch and linguistic forensic studies.
    """
    def __init__(self):
        # Words often over-used in fraudulent or hyped research
        self.PROMOTIONAL_MARKERS = [
            "extraordinary", "groundbreaking", "unprecedented", "unique",
            "transformative", "landmark", "miraculous", "exceptional",
            "novel", "robustly", "dramatically", "revolutionary"
        ]

        # Uncertainty words often missing from over-confident fraudulent papers
        self.UNCERTAINTY_WORDS = [
            "perhaps", "suggest", "potential", "limitation", "caveat",
            "maybe", "could", "likely", "possible", "uncertain", "notably"
        ]

    def analyze_text(self, text: str) -> dict[str, Any]:
        """
        Analyzes the text for markers of over-promotion vs uncertainty.
        """
        if not text:
            return {"status": "INCONCLUSIVE", "reason": "No text provided for analysis."}

        text_lower = text.lower()
        words = re.findall(r'\w+', text_lower)
        word_count = len(words)

        promo_count = sum(1 for w in words if w in self.PROMOTIONAL_MARKERS)
        uncertainty_count = sum(1 for w in words if w in self.UNCERTAINTY_WORDS)

        # Calculate scores
        # We want a healthy balance. Over-confident papers have high promo, low uncertainty.
        promo_density = promo_count / word_count * 100 if word_count > 0 else 0
        uncertain_density = uncertainty_count / word_count * 100 if word_count > 0 else 0

        is_suspicious = promo_density > 2.0 and uncertain_density < 0.5

        return {
            "status": "SUSPICIOUS (OVER-CONFIDENCE)" if is_suspicious else "TYPICAL (SCIENTIFIC_TONE)",
            "promotional_density": round(promo_density, 2),
            "uncertainty_density": round(uncertain_density, 2),
            "reason": f"Promotion density is {round(promo_density, 2)}% while uncertainty/caution words are {round(uncertain_density, 2)}%." +
                      (" This tone is unusually promotional for medical research." if is_suspicious else " The tone appears balanced.")
        }

if __name__ == "__main__":
    forensics = LinguisticForensics()
    # Test hypes
    hyped_text = "This groundbreaking study presents a unique and revolutionary treatment that has an extraordinary and unprecedented effect on patient outcomes."
    print(json.dumps(forensics.analyze_text(hyped_text), indent=2))
