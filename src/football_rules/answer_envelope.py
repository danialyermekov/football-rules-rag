"""Experimental whole-answer envelopes, independent of evaluation integrations."""

from hashlib import sha256
from typing import Any

_ENVELOPE_FIELDS = {
    "schema_version",
    "snapshot_id",
    "answer_sha256",
    "offset_unit",
    "units",
}
_UNIT_FIELDS = {"kind", "start", "end", "quote"}


def _validate_inputs(answer: str, snapshot_id: str) -> None:
    if not isinstance(answer, str):
        raise ValueError("answer must be a string")
    if answer == "":
        raise ValueError("answer must not be empty")
    if not isinstance(snapshot_id, str):
        raise ValueError("snapshot_id must be a string")


def build_answer_envelope(answer: str, snapshot_id: str) -> dict[str, Any]:
    """Bind the unmodified answer to a snapshot as one whole-answer unit.

    Raises:
        ValueError: If the answer is empty or either input is not a string.
    """
    _validate_inputs(answer, snapshot_id)
    return {
        "schema_version": 1,
        "snapshot_id": snapshot_id,
        "answer_sha256": sha256(answer.encode("utf-8")).hexdigest(),
        "offset_unit": "unicode_code_point",
        "units": [
            {"kind": "whole_answer", "start": 0, "end": len(answer), "quote": answer}
        ],
    }


def validate_answer_envelope(
    answer: str, snapshot_id: str, envelope: dict[str, Any]
) -> None:
    """Validate an exact whole-answer envelope without modifying or repairing it.

    Raises:
        ValueError: If inputs or any envelope fields violate the schema or do
            not match the supplied answer and snapshot.
    """
    _validate_inputs(answer, snapshot_id)
    if not isinstance(envelope, dict) or set(envelope) != _ENVELOPE_FIELDS:
        raise ValueError("envelope must contain exactly the schema fields")
    if type(envelope["schema_version"]) is not int or envelope["schema_version"] != 1:
        raise ValueError("schema_version must be the integer 1")
    if (
        not isinstance(envelope["snapshot_id"], str)
        or envelope["snapshot_id"] != snapshot_id
    ):
        raise ValueError("snapshot_id does not match")
    if (
        not isinstance(envelope["answer_sha256"], str)
        or envelope["answer_sha256"] != sha256(answer.encode("utf-8")).hexdigest()
    ):
        raise ValueError("answer_sha256 does not match the unmodified answer")
    if envelope["offset_unit"] != "unicode_code_point":
        raise ValueError("offset_unit must be unicode_code_point")
    units = envelope["units"]
    if not isinstance(units, list) or len(units) != 1:
        raise ValueError("units must be a list containing exactly one unit")
    unit = units[0]
    if not isinstance(unit, dict) or set(unit) != _UNIT_FIELDS:
        raise ValueError("unit must contain exactly the whole-answer fields")
    if unit["kind"] != "whole_answer":
        raise ValueError("unit kind must be whole_answer")
    if type(unit["start"]) is not int or type(unit["end"]) is not int:
        raise ValueError("unit offsets must be integers, not booleans")
    if unit["start"] != 0 or unit["end"] != len(answer):
        raise ValueError(
            "unit range must cover the entire answer in Unicode code points"
        )
    if not isinstance(unit["quote"], str) or unit["quote"] != answer:
        raise ValueError("unit quote must equal the unmodified answer")
