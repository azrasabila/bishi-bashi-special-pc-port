import struct
import unittest
from dataclasses import replace
from pathlib import Path

from port.tools.code_banks import load_catalog, parse_bank_table, validate_anchors

ROOT = Path(__file__).resolve().parents[1]
LAYOUTS = {
    'super': (0x4A4E0, 0x80057470, 46, 0x800C0000, 511, 189, 4619),
    'hyper': (0x3D330, 0x8004BFE0, 48, 0x80098000, 671, 4942, 5306),
}


def fake_exe(game):
    directory, table, count, base, first, _, _ = LAYOUTS[game]
    pointer_offset = table - 0x80010000 + 0x800
    exe = bytearray(max(directory + (count + 1) * 8, pointer_offset + count * 4))
    exe[:8] = b'PS-X EXE'
    struct.pack_into('<I', exe, 0x18, 0x80010000)
    for i in range(count + 1):
        struct.pack_into('<II', exe, directory + i * 8, first + 16 * i, 0x4000)
    for i in range(count):
        struct.pack_into('<I', exe, pointer_offset + i * 4, base + 0x100)
    return exe


def parse(exe, game, *, cd_sectors=None, disc_sectors=88290):
    _, _, _, _, _, cd_lba, actual_sectors = LAYOUTS[game]
    return parse_bank_table(bytes(exe), game=game, cd_lba=cd_lba,
                            cd_sectors=actual_sectors if cd_sectors is None else cd_sectors,
                            disc_sectors=disc_sectors)


class CodeBanksTest(unittest.TestCase):
    def test_slot_pairing_retains_aliases_and_sector_padding(self):
        for game, (_, _, count, base, first, cd_lba, _) in LAYOUTS.items():
            with self.subTest(game=game):
                banks = parse(fake_exe(game), game)
                self.assertEqual(len(banks), count + 1)
                self.assertEqual((banks[0].slot, banks[0].entry), (-1, None))
                self.assertEqual((banks[1].slot, banks[1].entry,
                                  banks[1].relative_sector, banks[1].lba),
                                 (0, base + 0x100, first + 16, cd_lba + first + 16))
                self.assertEqual((banks[2].slot, banks[2].entry), (1, base + 0x100))
                self.assertNotEqual(banks[1].lba, banks[2].lba)
                # The last bank ends at a sector boundary beyond an unpadded ISO byte length.
                end = first + 16 * count + 8
                self.assertLess(end * 2048 - 1692, end * 2048)
                self.assertEqual(parse(fake_exe(game), game, cd_sectors=end)[-1].size,
                                 0x4000)

    def test_invalid_disc_table_fails_closed_with_game_and_slot(self):
        directory, table, _, base, _, _, _ = LAYOUTS['super']
        pointer_offset = table - 0x80010000 + 0x800
        for label, offset, value, fmt in (
            ('header', 0x18, 0x80020000, '<I'),
            ('pointer', pointer_offset, base + 0x4000, '<I'),
            ('sector', directory + 8, 511, '<I'),
            ('size', directory + 8 + 4, 7, '<I'),
        ):
            with self.subTest(label=label):
                exe = fake_exe('super')
                struct.pack_into(fmt, exe, offset, value)
                with self.assertRaisesRegex(ValueError, 'super .*slot|super.*header'):
                    parse(exe, 'super')
        with self.assertRaisesRegex(ValueError, 'hyper slot 47'):
            parse(fake_exe('hyper'), 'hyper', disc_sectors=6388)

    def test_known_real_disc_records_and_anchor_mutation(self):
        image = ROOT / 'Bishi Bashi Special.bin'
        inventory = ROOT / '.local/probe/disc.json'
        if not image.is_file() or not inventory.is_file():
            self.skipTest('validated user disc not present')
        banks = load_catalog(image, inventory)
        self.assertEqual(len(banks), 96)
        self.assertEqual([(banks[i].slot, banks[i].lba, banks[i].size)
                          for i in (0, 2, 5, 7, 46)],
                         [(-1, 700, 0x4000), (1, 890, 0xC000),
                          (4, 1221, 0x4800), (6, 1447, 0x5800),
                          (45, 4798, 0x5000)])
        self.assertEqual((banks[47].lba, banks[54].lba), (5613, 6265))
        self.assertEqual(len({b.entry for b in banks[:47] if b.entry is not None}), 45)
        self.assertEqual(len({b.entry for b in banks[47:] if b.entry is not None}), 46)
        self.assertEqual(banks[46].lba + banks[46].size // 2048, 4808)
        altered = list(banks)
        altered[5] = replace(altered[5], relative_sector=0x409)
        with self.assertRaisesRegex(ValueError, 'super slot 4'):
            validate_anchors(altered)


if __name__ == '__main__':
    unittest.main()
