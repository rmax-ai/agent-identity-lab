from unittest.mock import MagicMock

from packages.audit.chain import compute_hash, verify_chain


def test_hash_chain_deterministic():
    data = {"action": "test", "result": "ok"}
    first_hash = compute_hash(data, None)
    second_hash = compute_hash(data, None)

    assert first_hash == second_hash


def test_chain_verification():
    first_event = MagicMock(data={"a": 1}, record_hash=compute_hash({"a": 1}, None))
    second_event = MagicMock(
        data={"b": 2},
        previous_hash=first_event.record_hash,
        record_hash=compute_hash({"b": 2}, first_event.record_hash),
    )

    result = verify_chain([first_event, second_event])

    assert result["valid"] is True


def test_tampered_chain_detected():
    first_event = MagicMock(data={"a": 1}, record_hash=compute_hash({"a": 1}, None))
    second_event = MagicMock(
        data={"b": 2},
        previous_hash=first_event.record_hash,
        record_hash="0000badhash",
    )

    result = verify_chain([first_event, second_event])

    assert result["valid"] is False
    assert result["broken_at"] == 1
