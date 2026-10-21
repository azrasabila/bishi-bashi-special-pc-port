import subprocess
import tempfile
import unittest
from pathlib import Path

from port.tools import recompile


class RuntimePatchTest(unittest.TestCase):
    def test_libds_reads_payload_without_double_stepping(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'RecompOne'
            subprocess.run(['git', 'clone', '-q', '--shared', str(recompile.ROOT / '.local/RecompOne'), str(repo)], check=True)
            self.assertIsNotNone(getattr(recompile, 'apply_runtime_patch', None))
            recompile.apply_runtime_patch(repo)
            recompile.apply_runtime_patch(repo)
            code = (repo / 'RecompOne.Runtime/sdk/LibCd.cs').read_text()
            self.assertIn('ReadSectorData(lba, dsSector ? 2048 : SectorSize(_mode))', code)
            self.assertIn('if (!dsSector && !_inDataCb && _readActive', code)
            self.assertEqual(subprocess.run(['git', '-C', str(repo), 'diff', '--name-only'],
                                            capture_output=True, text=True, check=True).stdout.strip(),
                             'RecompOne.Runtime/sdk/LibCd.cs')
            subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Test',
                            '-c', 'user.email=test@example.invalid', 'commit', '-qm',
                            'wrong revision', '--allow-empty'], check=True)
            with self.assertRaises(ValueError):
                recompile.apply_runtime_patch(repo)
