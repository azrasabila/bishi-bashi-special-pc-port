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
