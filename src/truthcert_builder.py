import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any

from utils import TOOL_DISCLAIMER

# Environment variable name follows the same convention as the reference
# Ed25519 implementation in truthcert-openclaw-supermemory-stack/certifier/signing.py
# but the primitive stays HMAC-SHA256 in this project.
ENV_HMAC_KEY = "TRUTHCERT_HMAC_KEY"
KEY_FILENAME = ".truthcert_key"


def _repo_root() -> Path:
    """Resolve the repo root (parent of this src/ directory)."""
    return Path(__file__).resolve().parent.parent


def load_hmac_key() -> bytes:
    """
    Load the HMAC signing key.

    Precedence:
      1. ``TRUTHCERT_HMAC_KEY`` environment variable (expected base64-encoded,
         decoded to raw bytes for strongest guarantees; a raw string is
         accepted as a fallback).
      2. ``.truthcert_key`` file in the repo root (same encoding rules).

    Raises:
        RuntimeError: if neither source is configured. No silent default.
    """
    env_val = os.environ.get(ENV_HMAC_KEY)
    if env_val:
        return _decode_key_material(env_val)

    key_path = _repo_root() / KEY_FILENAME
    if key_path.exists():
        raw = key_path.read_text(encoding="utf-8").strip()
        if raw:
            return _decode_key_material(raw)

    raise RuntimeError("TRUTHCERT_HMAC_KEY not configured")


def _decode_key_material(value: str) -> bytes:
    """Decode base64 if possible; otherwise use the raw UTF-8 bytes."""
    try:
        decoded = base64.b64decode(value, validate=True)
        if decoded:
            return decoded
    except (ValueError, base64.binascii.Error):
        pass
    return value.encode("utf-8")


class TruthCertBuilder:
    """
    Implements the 'TruthCert' requirement from CLAUDE.md:
    'certified claims MUST cite evidence locators + hashes.'

    Bundles are signed with HMAC-SHA256 over the canonical (sort_keys=True)
    JSON body. The HMAC key comes from the environment or a repo-local
    key file; a bundle-derived value is never used as the key (that would
    defeat HMAC, since attackers can see the bundle).
    """
    def __init__(self, nct_id: str):
        self.nct_id = nct_id
        # P1-14: cryptographic random cert_id (not timestamp).
        self.cert_id = f"CERT-{nct_id}-{secrets.token_hex(8)}"
        self.claims = []
        self.evidence_sources = {}

    def add_evidence_source(self, label: str, content: str, locator: str):
        """Adds a source and calculates its hash for verification."""
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        self.evidence_sources[label] = {
            "locator": locator,
            "hash": content_hash,
            "type": "JSON_API" if "clinicaltrials.gov" in locator else "TEXT_EXTRACT"
        }

    def certify_discrepancy(self, discrepancy: dict[str, Any]):
        """Turns a discrepancy into a certified claim."""
        claim = {
            "claim_id": f"CLAIM-{len(self.claims) + 1}",
            "type": discrepancy["type"],
            "subject": discrepancy.get("publication_outcome") or discrepancy.get("protocol_outcome"),
            "finding": discrepancy["reason"],
            "evidence_locators": list(self.evidence_sources.keys()),
            "confidence": discrepancy.get("confidence", 1.0),
            "certified_by": "Evidence-Integrity-Guard v2.0",
            "timestamp": datetime.now().isoformat()
        }
        self.claims.append(claim)

    def build_bundle(self, overall_status: str, key: bytes | None = None) -> dict[str, Any]:
        """
        Produce the final TruthCert Bundle signed with HMAC-SHA256.

        Args:
            overall_status: status label embedded in the bundle.
            key: optional explicit key bytes (primarily for testing). When
                omitted, the key is loaded via ``load_hmac_key()``.
        """
        bundle = {
            "truthcert_version": "1.0",
            "bundle_id": self.cert_id,
            "nct_id": self.nct_id,
            "status": overall_status,
            "certified_claims": self.claims,
            "evidence_manifest": self.evidence_sources,
            # P0-8: Add standard disclaimer.
            "disclaimer": TOOL_DISCLAIMER,
        }
        # P1-13: HMAC-based integrity signing.
        # NOTE: Production deployment should consider asymmetric signing
        # (RSA/Ed25519) so public verification does not require key sharing.
        if key is None:
            key = load_hmac_key()
        bundle["integrity_hash"] = _compute_integrity_hash(bundle, key)
        return bundle


def _compute_integrity_hash(bundle: dict[str, Any], key: bytes) -> str:
    """Compute HMAC-SHA256 over the canonical JSON body (excluding the hash)."""
    body = {k: v for k, v in bundle.items() if k != "integrity_hash"}
    canonical = json.dumps(body, sort_keys=True).encode("utf-8")
    return hmac.new(key, canonical, hashlib.sha256).hexdigest()


def verify_bundle(bundle: dict[str, Any], key: bytes) -> bool:
    """
    Verify the HMAC-SHA256 integrity hash on a bundle.

    The ``integrity_hash`` field is stripped before recomputation and
    comparison uses ``hmac.compare_digest`` (constant-time).
    Returns False if the field is missing or the signature does not match.
    """
    if not isinstance(bundle, dict):
        return False
    provided = bundle.get("integrity_hash")
    if not isinstance(provided, str):
        return False
    expected = _compute_integrity_hash(bundle, key)
    return hmac.compare_digest(provided, expected)


if __name__ == "__main__":
    # Quick test (requires TRUTHCERT_HMAC_KEY to be set in the environment).
    builder = TruthCertBuilder("NCT04458623")
    builder.add_evidence_source("Protocol", '{"outcomes": ["A"]}', "https://clinicaltrials.gov/api/v2/studies/NCT04458623")
    builder.certify_discrepancy({"type": "OUTCOME_MISSING", "protocol_outcome": "A", "reason": "Missing in pub"})
    print(json.dumps(builder.build_bundle("REJECT"), indent=2))
