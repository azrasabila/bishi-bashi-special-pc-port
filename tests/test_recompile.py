import json
import tempfile
import unittest
from pathlib import Path
from port.tools.recompile import prepare


class RecompileTest(unittest.TestCase):
    def test_preserves_game_pad_initializer_and_adds_one_hook(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'funcmaps').mkdir()
            funcmap = root / 'funcmaps/main.json'
            funcmap.write_text(json.dumps({'functions': [
                {'address': '0x800243CC', 'name': 'PadInitDirect', 'size': 176}]}))
            config = root / 'BishiBashi.json'
            config.write_text(json.dumps({'game': {'id': 'SLES-02537'},
                                          'funcMap': 'funcmaps/main.json', 'patches': []}))
            prepare(config)
            prepare(config)
            mapped = json.loads(funcmap.read_text())['functions'][0]
            self.assertEqual(mapped['name'], 'PadInitDirect_Game')
            self.assertEqual(json.loads(config.read_text())['patches'], [{
                'overlay': 'main', 'address': '0x800243CC', 'mode': 'pre',
                'target': 'Recompiled.PadPatches.InitDirect'}])

    def test_rejects_unexpected_disc_or_function_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'funcmaps').mkdir()
            (root / 'funcmaps/main.json').write_text(json.dumps({'functions': [
                {'address': '0x800243CC', 'name': 'SomethingElse'}]}))
            config = root / 'BishiBashi.json'
            config.write_text(json.dumps({'game': {'id': 'SLES-02537'},
                                          'funcMap': 'funcmaps/main.json'}))
            with self.assertRaises(ValueError):
                prepare(config)
            self.assertNotIn('patches', json.loads(config.read_text()))
            config.write_text(json.dumps({'game': {'id': 'WRONG'},
                                          'funcMap': 'funcmaps/main.json'}))
            with self.assertRaises(ValueError):
                prepare(config)
