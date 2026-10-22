import json
import tempfile
import unittest
from pathlib import Path
from port.tools.recompile import prepare


class RecompileTest(unittest.TestCase):
    def test_preserves_pad_initializer_and_splits_callbacks(self):
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
                                              {'name': 'bishi2', 'funcMap': 'funcmaps/bishi2.json'}]}))
            prepare(config)
            prepare(config)
            mapped = json.loads(funcmap.read_text())['functions'][0]
            self.assertEqual(mapped['name'], 'PadInitDirect_Game')
            functions = json.loads(funcmap.read_text())['functions']
            self.assertEqual([(f['address'], f['size']) for f in functions if f['address'] in
                              ('0x80010D48', '0x80011054')],
                             [('0x80010D48', 780), ('0x80011054', 76)])
            for name, start, callback in [('bishi1', '0x80014CDC', '0x80015414'),
                                          ('bishi2', '0x80012FC0', '0x80013750')]:
                functions = json.loads((root / f'funcmaps/{name}.json').read_text())['functions']
                self.assertEqual([(f['address'], f['size']) for f in functions],
                                 [(start, 1848 if name == 'bishi1' else 1936), (callback, 200)])
            raw = [o for o in json.loads(config.read_text())['overlays']
                   if o['name'] == 'cd_data1_code']
            self.assertEqual(raw, [{
                'name': 'cd_data1_code', 'file': 'CD_DATA1.BIN', 'offset': 1046528,
                'size': 12288, 'base': '0x800C0000', 'functions': [
                    {'address': '800C00B4'}, {'address': '800C0A44'}, {'address': '800C0FB0'}]}])
            self.assertEqual(json.loads(config.read_text())['patches'], [{
                'overlay': 'main', 'address': '0x800243CC', 'mode': 'pre',
                'target': 'Recompiled.PadPatches.InitDirect'}, {
                'overlay': 'main', 'address': '0x80018F3C', 'mode': 'pre',
                'target': 'Recompiled.CdPatches.PumpWhenPolling'}])
            broken = json.loads(config.read_text())
            broken['overlays'][-1]['size'] = 2048
            config.write_text(json.dumps(broken))
            with self.assertRaisesRegex(ValueError, 'CD_DATA1.BIN'):
                prepare(config)

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
                prepare(config)
            self.assertNotIn('patches', json.loads(config.read_text()))
            (root / 'funcmaps/main.json').write_text(json.dumps({'functions': [
                {'address': '0x800243CC', 'name': 'PadInitDirect'},
                {'address': '0x80018F3C', 'name': 'Wrong'}]}))
            with self.assertRaises(ValueError):
                prepare(config)
            self.assertNotIn('patches', json.loads(config.read_text()))
            (root / 'funcmaps/main.json').write_text(json.dumps({'functions': [
                {'address': '0x800243CC', 'name': 'PadInitDirect'},
                {'address': '0x80018F3C', 'name': 'VSync'},
                {'address': '0x80010D48', 'name': 'func_80010D48', 'size': 855}]}))
            with self.assertRaises(ValueError):
                prepare(config)
            self.assertNotIn('patches', json.loads(config.read_text()))
            config.write_text(json.dumps({'game': {'id': 'WRONG'},
                                          'funcMap': 'funcmaps/main.json'}))
            with self.assertRaises(ValueError):
                prepare(config)
