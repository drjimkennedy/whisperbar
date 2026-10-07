"""Failure-path checks that never capture audio, paste, or open app windows."""
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('preflight', ROOT / 'scripts/check_environment.py')
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class PreflightTests(unittest.TestCase):
    def check(self, isolated=True, missing=None, ffmpeg=True):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'pyvenv.cfg').write_text(
                'include-system-site-packages = ' + ('false' if isolated else 'true'))
            out = io.StringIO()
            with patch.object(sys, 'prefix', directory), \
                 patch.object(sys, 'version_info', (3, 9, 6)), \
                 patch.object(preflight.platform, 'system', return_value='Darwin'), \
                 patch.object(preflight.platform, 'machine', return_value='arm64'), \
                 patch.object(preflight.importlib.util, 'find_spec', side_effect=lambda name: None if name == missing else object()), \
                 patch.object(preflight.shutil, 'which', return_value='/test/ffmpeg' if ffmpeg else None), \
                 contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                code = preflight.main()
            return code, out.getvalue()

    def test_isolated_ready(self):
        self.assertEqual(self.check()[0], 0)

    def test_missing_package_is_actionable(self):
        code, text = self.check(missing='numpy')
        self.assertEqual(code, 1)
        self.assertIn('Missing numpy', text)
        self.assertIn('./scripts/setup.sh', text)

    def test_inherited_packages_rejected(self):
        code, text = self.check(isolated=False)
        self.assertEqual(code, 1)
        self.assertIn('isolated environment', text)

    def test_ffmpeg_missing(self):
        code, text = self.check(ffmpeg=False)
        self.assertEqual(code, 1)
        self.assertIn('brew install ffmpeg', text)



if __name__ == '__main__':
    unittest.main()
