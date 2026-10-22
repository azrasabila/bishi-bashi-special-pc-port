import json
import tempfile
import unittest
from pathlib import Path

from port.tools.code_banks import Bank
from port.tools.recompile import clear_generated, prepare

LEGACY = [
    {'name': 'cd_data1_code', 'file': 'CD_DATA1.BIN', 'offset': 1046528,
     'size': 12288, 'base': '0x800C0000', 'functions': [
         {'address': '800C00B4'}, {'address': '800C0A44'}, {'address': '800C0FB0'}]},
    {'name': 'cd_data1_pins', 'file': 'CD_DATA1.BIN', 'offset': 1435648,
     'size': 20480, 'base': '0x800C0000', 'functions': [
         {'address': '800C0540'}, {'address': '800C4530'}]},
    {'name': 'cd_data1_roach', 'file': 'CD_DATA1.BIN', 'offset': 2576384,
     'size': 14336, 'base': '0x800C0000', 'functions': [{'address': '800C0CC0'}]},
]


def bank_fixture():
    result = []
    for game, count, base, cd_lba, shared in (
        ('super', 46, 0x800C0000, 189, 700),
        ('hyper', 48, 0x80098000, 4942, 5613),
    ):
        for slot in range(-1, count):
            lba = shared if slot == -1 else shared + 25 * (slot + 1)
            entry = None if slot == -1 else base + 0x100
            if game == 'super' and slot in (1, 4, 6):
                lba, entry = {1: (890, 0x800C0540), 4: (1221, 0x800C13F0),
                              6: (1447, 0x800C0CC0)}[slot]
            if game == 'hyper' and slot == 6:
                lba, entry = 6265, 0x80098810
            result.append(Bank(game, slot, entry, lba - cd_lba, lba,
                               0x4000 if slot == -1 else 0x5000, base))
    return result


BANKS = bank_fixture()


class RecompileTest(unittest.TestCase):
    def test_preserves_hooks_and_migrates_legacy_banks_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'funcmaps').mkdir()
            funcmap = root / 'funcmaps/main.json'
            funcmap.write_text(json.dumps({'functions': [
                {'address': '0x800243CC', 'name': 'PadInitDirect', 'size': 176},
                {'address': '0x80018F3C', 'name': 'VSync', 'size': 376},
                {'address': '0x80010D48', 'name': 'func_80010D48', 'size': 856}]}))
            (root / 'funcmaps/bishi1.json').write_text(json.dumps({'functions': [
                {'address': '0x80014CDC', 'name': 'func_80014CDC', 'size': 2048}]}))
            (root / 'funcmaps/bishi2.json').write_text(json.dumps({'functions': [
                {'address': '0x80012FC0', 'name': 'func_80012FC0', 'size': 2136}]}))
            config = root / 'BishiBashi.json'
            config.write_text(json.dumps({'game': {'id': 'SLES-02537'},
                                          'funcMap': 'funcmaps/main.json', 'patches': [],
                                          'overlays': [
                                              {'name': 'bishi1', 'funcMap': 'funcmaps/bishi1.json'},
                                              {'name': 'bishi2', 'funcMap': 'funcmaps/bishi2.json'},
                                              *LEGACY]}))
            broken = json.loads(config.read_text())
            broken['overlays'][2]['size'] = 2048
            config.write_text(json.dumps(broken))
            snapshot = config.read_text()
            with self.assertRaisesRegex(ValueError, 'cd_data1_code'):
                prepare(config, BANKS)
            self.assertEqual(snapshot, config.read_text())
            self.assertEqual(json.loads(funcmap.read_text())['functions'][0]['name'], 'PadInitDirect')
            broken['overlays'][2]['size'] = 12288
            config.write_text(json.dumps(broken))

            prepare(config, BANKS)
            once = config.read_text()
            prepare(config, BANKS)
            self.assertEqual(config.read_text(), once)
            self.assertEqual(json.loads(funcmap.read_text())['functions'][0]['name'],
                             'PadInitDirect_Game')
            functions = json.loads(funcmap.read_text())['functions']
            self.assertEqual([(f['address'], f['size']) for f in functions if f['address'] in
                              ('0x80010D48', '0x80011054')],
                             [('0x80010D48', 780), ('0x80011054', 76)])
            for name, start, callback in [('bishi1', '0x80014CDC', '0x80015414'),
                                          ('bishi2', '0x80012FC0', '0x80013750')]:
                functions = json.loads((root / f'funcmaps/{name}.json').read_text())['functions']
                self.assertEqual([(f['address'], f['size']) for f in functions],
                                 [(start, 1848 if name == 'bishi1' else 1936), (callback, 200)])
            config_obj = json.loads(once)
            self.assertEqual(config_obj['patches'], [
                {'overlay': 'main', 'address': '0x800243CC', 'mode': 'pre',
                 'target': 'Recompiled.PadPatches.InitDirect'},
                {'overlay': 'main', 'address': '0x80018F3C', 'mode': 'pre',
                 'target': 'Recompiled.CdPatches.PumpWhenPolling'}])
            rows = [o for o in config_obj['overlays'] if o['name'].startswith(('super_bank_', 'hyper_bank_'))]
            self.assertEqual((len(rows), len({o['name'] for o in rows})), (96, 96))
            self.assertFalse({row['name'] for row in config_obj['overlays']} &
                             {row['name'] for row in LEGACY})
            self.assertEqual(next(o for o in rows if o['name'] == 'super_bank_04')['lba'], 1221)
            self.assertEqual(next(o for o in rows if o['name'] == 'hyper_bank_06'), {
                'name': 'hyper_bank_06', 'lba': 6265, 'size': 0x5000,
                'base': '0x80098000', 'functions': [{'address': '80098810'}]})
            self.assertEqual(next(o for o in rows if o['name'] == 'super_bank_shared')['functions'],
                             [{'address': '800C00B4'}, {'address': '800C0A44'},
                              {'address': '800C0FB0'}])
            self.assertEqual(next(o for o in rows if o['name'] == 'super_bank_01')['functions'],
                             [{'address': '800C0540'}, {'address': '800C4530'}])
            broken = json.loads(once)
            next(o for o in broken['overlays'] if o['name'] == 'super_bank_04')['lba'] = 999
            config.write_text(json.dumps(broken))
            snapshot = config.read_text()
            with self.assertRaisesRegex(ValueError, 'super slot 4'):
                prepare(config, BANKS)
            self.assertEqual(config.read_text(), snapshot)
            broken = json.loads(once)
            broken['overlays'].append(next(o for o in broken['overlays']
                                           if o['name'] == 'super_bank_04').copy())
            config.write_text(json.dumps(broken))
            with self.assertRaisesRegex(ValueError, 'super slot 4'):
                prepare(config, BANKS)

    def test_rejects_unexpected_disc_or_function_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'funcmaps').mkdir()
            (root / 'funcmaps/main.json').write_text(json.dumps({'functions': [
                {'address': '0x800243CC', 'name': 'SomethingElse'},
                {'address': '0x80018F3C', 'name': 'VSync'}]}))
            config = root / 'BishiBashi.json'
            config.write_text(json.dumps({'game': {'id': 'SLES-02537'},
                                          'funcMap': 'funcmaps/main.json'}))
            with self.assertRaises(ValueError):
                prepare(config, BANKS)
            self.assertNotIn('patches', json.loads(config.read_text()))
            (root / 'funcmaps/main.json').write_text(json.dumps({'functions': [
                {'address': '0x800243CC', 'name': 'PadInitDirect'},
                {'address': '0x80018F3C', 'name': 'Wrong'}]}))
            with self.assertRaises(ValueError):
                prepare(config, BANKS)
            self.assertNotIn('patches', json.loads(config.read_text()))
            (root / 'funcmaps/main.json').write_text(json.dumps({'functions': [
                {'address': '0x800243CC', 'name': 'PadInitDirect'},
                {'address': '0x80018F3C', 'name': 'VSync'},
                {'address': '0x80010D48', 'name': 'func_80010D48', 'size': 855}]}))
            with self.assertRaises(ValueError):
                prepare(config, BANKS)
            self.assertNotIn('patches', json.loads(config.read_text()))
            config.write_text(json.dumps({'game': {'id': 'WRONG'},
                                          'funcMap': 'funcmaps/main.json'}))
            with self.assertRaises(ValueError):
                prepare(config, BANKS)

    def test_old_generated_translations_do_not_enter_new_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            stale = output / 'cd_data1_roach.cs'
            stale.write_text('stale translation')
            keep = output / 'notes.txt'
            keep.write_text('user notes')
            clear_generated(output)
            clear_generated(output)
            self.assertFalse(stale.exists())
            self.assertEqual(keep.read_text(), 'user notes')

    def test_rejects_incomplete_catalog(self):
        with self.assertRaisesRegex(ValueError, '96'):
            prepare(Path('/missing'), BANKS[:-1])


if __name__ == '__main__':
    unittest.main()
