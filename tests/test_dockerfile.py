from pathlib import Path
import unittest


class DockerfileTests(unittest.TestCase):
    def test_copies_runtime_helper_required_by_application(self):
        dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

        self.assertIn("COPY runtime.py .", dockerfile)
