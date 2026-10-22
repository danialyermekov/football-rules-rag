"""Atomic writes for local pipeline artifacts."""

import hashlib
import json
import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from tempfile import NamedTemporaryFile


def write_jsonl(path: Path, records: Iterable[Mapping[str, object]]) -> str:
    """Write UTF-8/LF JSONL and return its SHA-256 without exposing partial output."""
    content = "".join(
        json.dumps(record, ensure_ascii=False) + "\n" for record in records
    )
    encoded = content.encode("utf-8")

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None

    try:
        with NamedTemporaryFile(
            dir=path.parent, suffix=".tmp", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(encoded)

        os.replace(temporary_path, path)

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return hashlib.sha256(encoded).hexdigest()
