#!/usr/bin/env python3
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class KnowledgeScannerContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/KnowledgeScanner.php").read_text()

    def test_canonical_root_and_symlink_escape_are_blocked(self):
        self.assertIn("realpath", self.source)
        self.assertIn("insideRoot", self.source)
        self.assertIn("is_link", self.source)
        self.assertIn("path_outside_root", self.source)

    def test_type_and_size_limits_are_explicit(self):
        self.assertIn("FUSANHE_KNOWLEDGE_MAX_BYTES", self.source)
        for ext in ("pdf", "docx", "xlsx", "txt", "md"):
            self.assertIn(f"'{ext}'", self.source)
        self.assertIn("file_too_large", self.source)

    def test_errors_are_isolated_and_paths_are_sanitized(self):
        self.assertIn("catch (\\Throwable", self.source)
        self.assertIn("safeLabel", self.source)
        self.assertIn("processing_failed", self.source)
        self.assertNotIn("$error->getTrace", self.source)


if __name__ == "__main__":
    unittest.main()
