"""Local usage reservations; failed calls retain their conservative allowance."""

import json
import math
from pathlib import Path
from threading import Lock
from typing import Any

from football_rules.io import write_jsonl


class ApiBudget:
    def __init__(
        self, path: Path, limit_usd: float, input_rate: float, output_rate: float
    ) -> None:
        if not all(
            math.isfinite(v) and v > 0 for v in (limit_usd, input_rate, output_rate)
        ):
            raise ValueError("Budget and token rates must be positive and finite")
        self.path = path
        self.limit = limit_usd
        self.input_rate = input_rate
        self.output_rate = output_rate
        self.lock = Lock()
        self.entries: list[dict[str, Any]] = (
            list(map(json.loads, path.read_text(encoding="utf-8").splitlines()))
            if path.exists()
            else []
        )
        if any(
            e["input_rate"] != input_rate or e["output_rate"] != output_rate
            for e in self.entries
        ):
            raise ValueError("Existing budget ledger uses different token rates")

    def charged(self) -> float:
        return float(sum(e.get("actual_usd", e["reserved_usd"]) for e in self.entries))

    def reserve(self, input_bytes: int, max_output: int) -> int:
        if input_bytes < 0 or max_output < 1:
            raise ValueError("Invalid request bounds")
        # UTF-8 bytes plus schema/template margin conservatively bound text tokens.
        amount = (
            (input_bytes + 4096) * self.input_rate + max_output * self.output_rate
        ) / 1e6
        with self.lock:
            if self.charged() + amount > self.limit:
                raise RuntimeError(
                    "Local API spending cap reached; no new request sent"
                )
            self.entries.append(
                {
                    "reserved_usd": amount,
                    "input_rate": self.input_rate,
                    "output_rate": self.output_rate,
                }
            )
            write_jsonl(self.path, self.entries)
            return len(self.entries) - 1

    def settle(self, index: int, usage: dict[str, Any]) -> None:
        def tokens(snake: str, camel: str) -> int:
            value = usage.get(snake, usage.get(camel, 0))
            if not isinstance(value, int) or value < 0:
                raise ValueError("Invalid usage token count")
            return value

        if "prompt_token_count" not in usage and "promptTokenCount" not in usage:
            raise ValueError("Missing usage; retain reserved allowance")
        inputs = tokens("prompt_token_count", "promptTokenCount")
        outputs = tokens("candidates_token_count", "candidatesTokenCount") + tokens(
            "thoughts_token_count", "thoughtsTokenCount"
        )
        with self.lock:
            self.entries[index].update(
                {
                    "actual_usd": (
                        inputs * self.input_rate + outputs * self.output_rate
                    )
                    / 1e6,
                    "prompt_tokens": inputs,
                    "output_and_thought_tokens": outputs,
                }
            )
            write_jsonl(self.path, self.entries)
