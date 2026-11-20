from pathlib import Path
import unittest


class BuildScriptTests(unittest.TestCase):
    def test_requires_explicit_deploy_confirmation(self):
        source = Path("build.sh").read_text(encoding="utf-8")

        self.assertIn("DEPLOY_CONFIRM", source)
        self.assertIn('if [ "${DEPLOY_CONFIRM:-0}" != "1" ]', source)
        self.assertIn("/app/data", source)
        self.assertIn("com.centurylinklabs.watchtower.scope=summary", source)
