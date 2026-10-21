import hashlib
import tempfile
import unittest
from pathlib import Path
from tools.disc_preflight import validate, cue_text


class DiscTest(unittest.TestCase):
    def test_rejects_missing_and_wrong_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'game.bin'
            with self.assertRaises(ValueError): validate(path)
            path.write_bytes(b'bad')
            with self.assertRaises(ValueError): validate(path)
            path.write_bytes(b'\0' * 2352)
            with self.assertRaises(ValueError): validate(path)

    def test_checks_sector_mode_and_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'game.bin'
            sector = bytearray(2352)
            sector[:12] = bytes.fromhex('00ffffffffffffffffffff00')
            sector[12:16] = bytes([0, 2, 0, 2])
            path.write_bytes(sector)
            validate(path, expected_hash=hashlib.sha256(sector).hexdigest())
            for index, value in ((15, 1), (14, 1)):
                broken = sector.copy(); broken[index] = value
                path.write_bytes(broken)
                with self.assertRaises(ValueError):
                    validate(path, expected_hash=hashlib.sha256(broken).hexdigest())

    def test_rejects_non_decimal_bcd_that_aliases_a_valid_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'game.bin'
            with path.open('wb') as f:
                for lba in range(601):
                    sector = bytearray(2352)
                    sector[:12] = bytes.fromhex('00ffffffffffffffffffff00')
                    seconds, frame = divmod(lba + 150, 75)
                    minute, second = divmod(seconds, 60)
                    sector[12:16] = bytes((minute, (second // 10 << 4) | second % 10, (frame // 10 << 4) | frame % 10, 2))
                    if lba == 600:
                        sector[13] = 0x0A  # 0x0A and 0x10 decode to the same number if nibbles are not checked
                    f.write(sector)
            with self.assertRaises(ValueError):
                validate(path, expected_hash=hashlib.sha256(path.read_bytes()).hexdigest())

    def test_cue_syntax_and_name(self):
        self.assertEqual(cue_text('game.bin'), 'FILE "game.bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n')
        for name in ('bad".bin', 'bad\n.bin', '../bad.bin'):
            with self.assertRaises(ValueError): cue_text(name)
