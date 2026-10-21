import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOTNET = ROOT / '.local/dotnet/dotnet'
APP = ROOT / 'port/bin/Release/net10.0/BishiBashi.dll'


class PortCliTest(unittest.TestCase):
    def test_invalid_inputs_fail_without_waiting_for_disc(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = Path(tmp) / 'existing.txt'
            text.write_text('not a disc')
            for args in ([], [str(Path(tmp) / 'missing.cue')], [str(text)]):
                with self.subTest(args=args):
                    result = subprocess.run([str(DOTNET), str(APP), *args], capture_output=True,
                                            text=True, timeout=5,
                                            env={**os.environ, 'DOTNET_ROOT': str(DOTNET.parent)})
                    self.assertEqual(result.returncode, 2)
                    self.assertIn('Usage: BishiBashi', result.stderr)

    def test_explicit_disc_replaces_stale_runtime_setting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            disc = root / 'requested.cue'
            disc.write_text('FILE "missing.bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n')
            (root / 'settings.json').write_text(json.dumps({'system': {'discPath': 'stale.cue'}}))
            subprocess.run([str(DOTNET), str(APP), str(disc)], cwd=root, capture_output=True,
                           text=True, timeout=10,
                           env={**os.environ, 'DOTNET_ROOT': str(DOTNET.parent)})
            saved = json.loads((root / 'settings.json').read_text())
            self.assertEqual(saved['system']['discPath'], str(disc))

    def test_boot_exception_is_reported_by_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            disc = Path(tmp) / 'broken.cue'
            disc.write_text('not a disc')
            result = subprocess.run([str(DOTNET), str(APP), str(disc)], cwd=tmp,
                                    capture_output=True, text=True, timeout=10,
                                    env={**os.environ, 'DOTNET_ROOT': str(DOTNET.parent)})
            self.assertEqual(result.returncode, 3)
            self.assertIn('[Runtime] runtime has crashed:', result.stderr)
