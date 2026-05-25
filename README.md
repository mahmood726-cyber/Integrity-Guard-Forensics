# Evidence-Integrity-Guard

[![ci](https://github.com/mahmood726-cyber/Integrity-Guard-Forensics/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/mahmood726-cyber/Integrity-Guard-Forensics/actions/workflows/ci.yml) [![codeql](https://github.com/mahmood726-cyber/Integrity-Guard-Forensics/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/mahmood726-cyber/Integrity-Guard-Forensics/actions/workflows/codeql.yml) [![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE) [![python: 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)

Automated Quality Assurance for Clinical Trial Reporting.

## Overview
Evidence-Integrity-Guard is a tool designed to ensure the transparency and integrity of clinical trial data. It cross-references extracted data from published reports (TruthCert bundles) against their original registrations in ClinicalTrials.gov (v2 API) to identify reporting discrepancies, such as:
- **Outcome Switching**: Primary outcomes changing between registration and publication.
- **Selective Reporting**: Registered outcomes missing from the final report.
- **Unregistered Outcomes**: New outcomes appearing in the publication that were not in the protocol.

## Features
- **CT.gov v2 Integration**: Fetches real-time protocol data using the latest ClinicalTrials.gov API.
- **Fuzzy Matching Discrepancy Engine**: Uses sequence matching to compare outcome measures even when worded differently.
- **Integrity Reports**: Generates detailed JSON reports with "PASS" or "WARNING" status.

## Usage
```bash
python src/main.py --bundle data/sample_bundle.json --output report.json
```

## Setup
```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

For editable local installs:
```bash
python -m pip install -e .[dev]
```

## Multi-Person Review
Evidence-Integrity-Guard supports collaborative review of discrepancies. Reviewers can analyze the findings and mark them as Confirmed or False Positives, and the tool will automatically calculate a `consensus_status` (e.g., `CONFIRMED`, `DISPUTED`, `IN_PROGRESS`).

**Interactive Mode:**
```bash
python src/review_tool.py --report report.json --name "Dr. Smith"
```

**Non-Interactive / Programmatic Mode:**
```bash
python src/review_tool.py --report report.json --name "Dr. Jones" --idx 0 --status C --comment "Agreed, clear outcome switching."
```

**OpenClaw Deep Audit:**
```bash
python src/openclaw_pipeline.py --bundle data/deep_fraud_bundle.json --out-report report.json --out-html dashboard.html
```

**Run Validation:**
```bash
python -m pytest -q
```

## Project Structure
- `src/`: Core logic (Fetcher, Engine, Main).
- `data/`: Sample TruthCert bundles.
- `docs/`: Documentation.
- `tests/`: Pytest coverage plus the historical validation script.
- `pyproject.toml` / `requirements.txt`: reproducible setup metadata

## Part of the TruthCert Ecosystem
This project fills the gap of "Evidence Integrity" within the broader meta-analysis and verifiable evidence stack.
