import hashlib
import json


def compute_hash(event_data: dict, previous_hash: str | None) -> str:
    canonical = json.dumps(event_data, sort_keys=True, separators=(",", ":"), default=str)
    combined = f"{previous_hash or ''}{canonical}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def verify_chain(events: list) -> dict:
    """Verify the audit hash chain."""
    prev = None
    for index, event in enumerate(events):
        previous_hash = vars(event).get("previous_hash", prev)
        if previous_hash != prev:
            return {
                "valid": False,
                "broken_at": index,
                "expected_previous": prev,
                "got_previous": previous_hash,
            }

        expected = compute_hash(event.data, prev)
        if event.record_hash != expected:
            return {
                "valid": False,
                "broken_at": index,
                "expected": expected,
                "got": event.record_hash,
            }
        prev = event.record_hash
    return {"valid": True, "broken_at": None}
