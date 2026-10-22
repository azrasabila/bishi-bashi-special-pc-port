import tempfile
import unittest
from pathlib import Path

from port.tools.code_banks import Bank
from port.tools.verify_banks import verify_generated


class VerifyBanksTest(unittest.TestCase):
    def test_checks_each_generated_bank_not_other_bank_with_same_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            banks = [Bank('super', slot, 0x800C13F0, relative, lba, 0x4800,
                          0x800C0000) for slot, relative, lba in
                     ((4, 0x408, 1221), (5, 0x430, 1261))]
            (output / 'Entry.cs').write_text(''.join(
                f'Dispatcher.Register("{b.name}", new Super_bank_{b.slot:02d}DispatchTable());\n'
                for b in banks))
            for bank in banks:
                (output / f'{bank.name}.cs').write_text(
                    f'public string Name => "{bank.name}";\n'
                    f'public int LbaStart => {bank.lba};\n'
                    'public uint Base => 0x800C0000u;\n'
                    'public uint Size => 0x4800u;\n'
                    '[0x800C13F0u] = callback,\n')
            rows = verify_generated(banks, output)
            self.assertEqual([(r['slot'], r['lba'], r['entry']) for r in rows],
                             [(4, 1221, '0x800C13F0'), (5, 1261, '0x800C13F0')])
            self.assertEqual([r['activationTest'] for r in rows], ['pending', 'pending'])

            second = output / 'super_bank_05.cs'
            second.write_text(second.read_text().replace('[0x800C13F0u]', '[0x800C1400u]'))
            with self.assertRaisesRegex(ValueError, 'super slot 5'):
                verify_generated(banks, output)
            second.write_text(second.read_text().replace('[0x800C1400u]', '[0x800C13F0u]'))
            second.write_text(second.read_text().replace('LbaStart => 1261', 'LbaStart => 999'))
            with self.assertRaisesRegex(ValueError, 'super slot 5'):
                verify_generated(banks, output)
            second.write_text(second.read_text().replace('LbaStart => 999', 'LbaStart => 1261'))
            second.write_text(second.read_text().replace('Size => 0x4800u', 'Size => 0x4000u'))
            with self.assertRaisesRegex(ValueError, 'super slot 5'):
                verify_generated(banks, output)
            second.write_text(second.read_text().replace('Size => 0x4000u', 'Size => 0x4800u'))
            entry = output / 'Entry.cs'
            entry.write_text(entry.read_text().replace('Dispatcher.Register("super_bank_05",',
                                                       'Dispatcher.Register("missing_bank",'))
            with self.assertRaisesRegex(ValueError, 'super slot 5'):
                verify_generated(banks, output)

    def test_shared_bank_has_no_game_slot_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / 'Entry.cs').write_text(
                'Dispatcher.Register("hyper_bank_shared", new Hyper_bank_sharedDispatchTable());')
            (output / 'hyper_bank_shared.cs').write_text(
                'public string Name => "hyper_bank_shared";\n'
                'public int LbaStart => 5613;\n'
                'public uint Base => 0x80098000u;\n'
                'public uint Size => 0x4000u;\n')
            rows = verify_generated([Bank('hyper', -1, None, 671, 5613,
                                          0x4000, 0x80098000)], output)
            self.assertEqual((rows[0]['entry'], rows[0]['activationTest']),
                             (None, 'not-applicable'))


if __name__ == '__main__':
    unittest.main()
