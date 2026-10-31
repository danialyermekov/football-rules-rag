import unittest
from copy import deepcopy
from hashlib import sha256
from typing import Any

from football_rules.answer_envelope import (
    build_answer_envelope,
    validate_answer_envelope,
)


class AnswerEnvelopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.answer = "No goal if the ball has not crossed the line."
        self.snapshot_id = "rules-2026"
        self.envelope = build_answer_envelope(self.answer, self.snapshot_id)

    def assert_invalid(self, envelope: Any) -> None:
        before = deepcopy(envelope)
        with self.assertRaises(ValueError):
            validate_answer_envelope(self.answer, self.snapshot_id, envelope)
        self.assertEqual(envelope, before, "validation must not repair invalid input")

    def test_happy_english_and_russian(self) -> None:
        for answer in (self.answer, "Гол не засчитывается, если мяч не пересёк линию."):
            with self.subTest(answer=answer):
                envelope = build_answer_envelope(answer, self.snapshot_id)
                self.assertEqual(
                    envelope,
                    {
                        "schema_version": 1,
                        "snapshot_id": self.snapshot_id,
                        "answer_sha256": sha256(answer.encode("utf-8")).hexdigest(),
                        "offset_unit": "unicode_code_point",
                        "units": [
                            {
                                "kind": "whole_answer",
                                "start": 0,
                                "end": len(answer),
                                "quote": answer,
                            }
                        ],
                    },
                )
                self.assertIsNone(
                    validate_answer_envelope(answer, self.snapshot_id, envelope)
                )

    def test_questions_negation_and_conditions_are_unchanged(self) -> None:
        for answer in (
            "Is it a goal? No, not unless the whole ball crosses the line.",
            "Если нарушения нет, игра продолжается. А если мяч вышел?",
        ):
            with self.subTest(answer=answer):
                envelope = build_answer_envelope(answer, self.snapshot_id)
                self.assertEqual(envelope["units"][0]["quote"], answer)
                self.assertEqual(len(envelope["units"]), 1)
                validate_answer_envelope(answer, self.snapshot_id, envelope)

    def test_unicode_offsets_and_no_normalization(self) -> None:
        answer = "A😀e\u0301\r\nБ"
        envelope = build_answer_envelope(answer, self.snapshot_id)
        self.assertEqual(envelope["units"][0]["end"], 7)
        self.assertNotEqual(len(answer), len(answer.encode("utf-8")))
        validate_answer_envelope(answer, self.snapshot_id, envelope)
        for changed in ("A😀é\r\nБ", answer.replace("\r\n", "\n")):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                validate_answer_envelope(changed, self.snapshot_id, envelope)

    def test_empty_answer_rejected_explicitly(self) -> None:
        with self.assertRaisesRegex(ValueError, "empty"):
            build_answer_envelope("", self.snapshot_id)
        with self.assertRaisesRegex(ValueError, "empty"):
            validate_answer_envelope("", self.snapshot_id, self.envelope)

    def test_whitespace_roundtrip(self) -> None:
        for answer in (" ", "\t\r\n  ", "  goal\r\n\t"):
            with self.subTest(answer=answer):
                envelope = build_answer_envelope(answer, self.snapshot_id)
                self.assertEqual(envelope["units"][0]["quote"], answer)
                self.assertEqual(
                    envelope["answer_sha256"],
                    sha256(answer.encode("utf-8")).hexdigest(),
                )
                validate_answer_envelope(answer, self.snapshot_id, envelope)

    def test_malformed_inputs(self) -> None:
        for answer, snapshot in (
            (None, "s"),
            (1, "s"),
            (b"a", "s"),
            ("a", None),
            ("a", 1),
        ):
            with self.subTest(answer=answer, snapshot=snapshot):
                with self.assertRaises(ValueError):
                    build_answer_envelope(answer, snapshot)
                with self.assertRaises(ValueError):
                    validate_answer_envelope(answer, snapshot, self.envelope)
        for envelope in (None, [], "envelope", 1):
            with self.subTest(envelope=envelope):
                self.assert_invalid(envelope)

    def test_schema_fields_missing_or_extra(self) -> None:
        for field in self.envelope:
            envelope = deepcopy(self.envelope)
            del envelope[field]
            with self.subTest(missing=field):
                self.assert_invalid(envelope)
        for field in ("claims", "confidence", "semantics"):
            envelope = deepcopy(self.envelope)
            envelope[field] = []
            with self.subTest(extra=field):
                self.assert_invalid(envelope)

    def test_schema_version_is_strict_integer(self) -> None:
        for version in (True, False, 1.0, "1", None, 0, 2):
            with self.subTest(version=version):
                self.assert_invalid({**self.envelope, "schema_version": version})

    def test_wrong_snapshot_hash_and_offset_unit(self) -> None:
        for field, values in (
            ("snapshot_id", ("other", None, 1)),
            (
                "answer_sha256",
                ("0" * 64, self.envelope["answer_sha256"].upper(), None, 1),
            ),
            ("offset_unit", ("utf8_byte", "utf16_code_unit", None, 1)),
        ):
            for value in values:
                with self.subTest(field=field, value=value):
                    self.assert_invalid({**self.envelope, field: value})
        with self.assertRaises(ValueError):
            validate_answer_envelope(self.answer, "other", self.envelope)

    def test_units_container_and_count(self) -> None:
        unit = self.envelope["units"][0]
        for units in (None, {}, unit, (unit,), [], [unit, unit], "units"):
            with self.subTest(units=units):
                self.assert_invalid({**self.envelope, "units": units})

    def test_unit_schema_and_kind(self) -> None:
        for unit in (None, [], "unit", 1):
            with self.subTest(unit=unit):
                self.assert_invalid({**self.envelope, "units": [unit]})
        for field in self.envelope["units"][0]:
            envelope = deepcopy(self.envelope)
            del envelope["units"][0][field]
            with self.subTest(missing=field):
                self.assert_invalid(envelope)
        for field in ("claim", "id", "confidence"):
            envelope = deepcopy(self.envelope)
            envelope["units"][0][field] = "injected"
            with self.subTest(extra=field):
                self.assert_invalid(envelope)
        for kind in ("claim", "sentence", None, 1):
            envelope = deepcopy(self.envelope)
            envelope["units"][0]["kind"] = kind
            with self.subTest(kind=kind):
                self.assert_invalid(envelope)

    def test_offsets_reject_bool_float_and_other_types(self) -> None:
        for field in ("start", "end"):
            for value in (True, False, 0.0, float(len(self.answer)), "0", None):
                envelope = deepcopy(self.envelope)
                envelope["units"][0][field] = value
                with self.subTest(field=field, value=value):
                    self.assert_invalid(envelope)

    def test_ranges_reject_gaps_truncation_and_wrong_unicode_units(self) -> None:
        length = len(self.answer)
        for start, end in (
            (1, length),
            (0, length - 1),
            (-1, length),
            (0, length + 1),
            (length, 0),
            (0, 0),
        ):
            envelope = deepcopy(self.envelope)
            envelope["units"][0].update(
                start=start, end=end, quote=self.answer[start:end]
            )
            with self.subTest(start=start, end=end):
                self.assert_invalid(envelope)
        answer = "😀e\u0301"
        for end in (
            2,
            len(answer.encode("utf-8")),
            len(answer.encode("utf-16-le")) // 2,
        ):
            envelope = build_answer_envelope(answer, self.snapshot_id)
            envelope["units"][0]["end"] = end
            with self.subTest(end=end), self.assertRaises(ValueError):
                validate_answer_envelope(answer, self.snapshot_id, envelope)

    def test_changed_quote_or_answer_rejected(self) -> None:
        for quote in (self.answer.replace("not ", ""), self.answer + " ", None, 1):
            envelope = deepcopy(self.envelope)
            envelope["units"][0]["quote"] = quote
            with self.subTest(quote=quote):
                self.assert_invalid(envelope)
        with self.assertRaises(ValueError):
            validate_answer_envelope(
                self.answer.replace("No", "OK"), self.snapshot_id, self.envelope
            )

    def test_mutation_has_no_fallback_or_shared_state(self) -> None:
        pristine = deepcopy(self.envelope)
        self.envelope["units"][0]["quote"] = "tampered"
        self.assert_invalid(self.envelope)
        fresh = build_answer_envelope(self.answer, self.snapshot_id)
        self.assertEqual(fresh, pristine)
        before = deepcopy(fresh)
        validate_answer_envelope(self.answer, self.snapshot_id, fresh)
        self.assertEqual(fresh, before)
        self.assertEqual(self.envelope["units"][0]["quote"], "tampered")


if __name__ == "__main__":
    unittest.main()
