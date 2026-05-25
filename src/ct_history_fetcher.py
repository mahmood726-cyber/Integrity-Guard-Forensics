import json
import logging
from typing import Any

import requests

from utils import validate_nct_id

# P2-17: Removed module-level logging config; just get the logger
logger = logging.getLogger(__name__)

class CTHistoryFetcher:
    BASE_URL = "https://clinicaltrials.gov/api/v2/studies"

    def __init__(self):
        self.session = requests.Session()

    def get_history_list(self, nct_id: str) -> list[dict[str, Any]]:
        """
        Fetches the history of versions for a given NCT ID.
        """
        # P1-15: Validate NCT ID format
        if not validate_nct_id(nct_id):
            logger.error(f"Invalid NCT ID format: {nct_id}")
            return []

        url = f"{self.BASE_URL}/{nct_id}/history"
        try:
            # P1-11: Add timeout to requests
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            # The structure in v2 seems to be a list of history objects
            # Each with 'version', 'postedDate', etc.
            return data.get("history", [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching history list for {nct_id}: {e}")
            return []

    def get_study_version(self, nct_id: str, version_number: int | None = None) -> dict[str, Any]:
        """
        Fetches a specific historical version of a study.
        If version_number is None, fetches the latest version.
        """
        # P1-15: Validate NCT ID format
        if not validate_nct_id(nct_id):
            logger.error(f"Invalid NCT ID format: {nct_id}")
            return {}

        url = f"{self.BASE_URL}/{nct_id}"
        params = {}
        if version_number is not None:
            params["version"] = version_number

        try:
            # P1-11: Add timeout to requests
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching study version {version_number} for {nct_id}: {e}")
            return {}

    def get_primary_outcomes(self, study_data: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Extracts primary outcomes from the Protocol section.
        """
        try:
            protocol_section = study_data.get("protocolSection", {})
            outcomes_module = protocol_section.get("outcomesModule", {})
            return outcomes_module.get("primaryOutcomes", [])
        except Exception as e:
            logger.error(f"Error extracting protocol primary outcomes: {e}")
            return []

    def get_results_outcomes(self, study_data: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Extracts outcomes from the Results section (if they exist).
        """
        try:
            results_section = study_data.get("resultsSection", {})
            outcome_measures_module = results_section.get("outcomeMeasuresModule", {})
            outcome_measures = outcome_measures_module.get("outcomeMeasures", [])

            # Filter for primary outcomes in results
            primaries = [m for m in outcome_measures if m.get("type", "").upper() == "PRIMARY"]
            return primaries
        except Exception as e:
            logger.error(f"Error extracting results outcomes: {e}")
            return []

if __name__ == "__main__":
    fetcher = CTHistoryFetcher()
    test_nct = "NCT04458623"
    history = fetcher.get_history_list(test_nct)
    print(f"History for {test_nct}: {len(history)} versions found.")

    if history:
        # Get the first version (index 0) and the latest version
        first_version_num = history[0].get("version")
        latest_version_num = history[-1].get("version")

        print(f"Fetching first version ({first_version_num})...")
        first_study = fetcher.get_study_version(test_nct, first_version_num)
        first_outcomes = fetcher.get_primary_outcomes(first_study)

        print(f"Fetching latest version ({latest_version_num})...")
        latest_study = fetcher.get_study_version(test_nct, latest_version_num)
        latest_outcomes = fetcher.get_primary_outcomes(latest_study)

        print("\nPrimary Outcomes (First Version):")
        print(json.dumps(first_outcomes, indent=2))

        print("\nPrimary Outcomes (Latest Version):")
        print(json.dumps(latest_outcomes, indent=2))
