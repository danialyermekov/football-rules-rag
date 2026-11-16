import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import setup_data


class SetupDataTests(unittest.TestCase):
    def test_download_pdfs_skips_verified_and_downloads_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = b"%PDF-1.7 test content"
            sha = hashlib.sha256(payload).hexdigest()
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    [
                        {
                            "id": "doc-1",
                            "edition": "2026/27",
                            "language": "en",
                            "publisher": "IFAB",
                            "source_url": "https://example.com/doc.pdf",
                            "local_path": "data/raw/doc.pdf",
                            "sha256": sha,
                            "bytes": len(payload),
                            "pdf_pages": 1,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            response = MagicMock()
            response.__enter__.return_value.read.return_value = payload
            with patch("setup_data.urlopen", return_value=response) as mock_open:
                paths = setup_data.download_pdfs(manifest, root)
                mock_open.assert_called_once()
                self.assertTrue(paths[0].is_file())
                self.assertEqual(paths[0].read_bytes(), payload)

            with patch("setup_data.urlopen") as mock_open:
                setup_data.download_pdfs(manifest, root)
                mock_open.assert_not_called()

    def test_download_pdfs_rejects_corrupted_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    [
                        {
                            "id": "doc-1",
                            "edition": "2026/27",
                            "language": "en",
                            "publisher": "IFAB",
                            "source_url": "https://example.com/doc.pdf",
                            "local_path": "data/raw/doc.pdf",
                            "sha256": "0" * 64,
                            "bytes": 10,
                            "pdf_pages": 1,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            response = MagicMock()
            response.__enter__.return_value.read.return_value = b"wrong-bytes"
            with (
                patch("setup_data.urlopen", return_value=response),
                self.assertRaisesRegex(ValueError, "failed verification"),
            ):
                setup_data.download_pdfs(manifest, root)


if __name__ == "__main__":
    unittest.main()
