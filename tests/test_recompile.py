import json
import tempfile
import unittest
from pathlib import Path
from port.tools.recompile import prepare


class RecompileTest(unittest.TestCase):
    def test_preserves_pad_initializer_and_splits_input_callback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'funcmaps').mkdir()
            funcmap = root / 'funcmaps/main.json'
            funcmap.write_text(json.dumps({'functions': [
                {'address': '0x800243CC', 'name': 'PadInitDirect', 'size': 176},
                {'address': '0x80018F3C', 'name': 'VSync', 'size': 376},
                {'address': '0x80010D48', 'name': 'func_80010D48', 'size': 856}]}))
            config = root / 'BishiBashi.json'
            config.write_text(json.dumps({'game': {'id': 'SLES-02537'},
                                          'funcMap': 'funcmaps/main.json', 'patches': []}))
            prepare(config)
            prepare(config)
            mapped = json.loads(funcmap.read_text())['functions'][0]
            self.assertEqual(mapped['name'], 'PadInitDirect_Game')
            functions = json.loads(funcmap.read_text())['functions']
            self.assertEqual([(f['address'], f['size']) for f in functions if f['address'] in
                              ('0x80010D48', '0x80011054')],
                             [('0x80010D48', 780), ('0x80011054', 76)])
            self.assertEqual(json.loads(config.read_text())['patches'], [{
                'overlay': 'main', 'address': '0x800243CC', 'mode': 'pre',
                'target': 'Recompiled.PadPatches.InitDirect'}, {
                'overlay': 'main', 'address': '0x80018F3C', 'mode': 'pre',
                'target': 'Recompiled.CdPatches.PumpWhenPolling'}])

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
