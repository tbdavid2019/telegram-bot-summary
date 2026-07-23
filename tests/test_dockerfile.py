from pathlib import Path
import unittest


class DockerfileTests(unittest.TestCase):
    def test_copies_app_package_and_runs_package_entrypoint(self):
        dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

        self.assertIn("COPY app /app/app", dockerfile)
        self.assertIn('ENTRYPOINT ["python3", "-u", "-m", "app.main"]', dockerfile)
