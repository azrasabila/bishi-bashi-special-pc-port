"""Keep game pad initialization and service CD work during VSync polling."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from port.tools.code_banks import Bank, load_catalog
from port.tools.verify_banks import verify_generated
from tools.disc_preflight import cue_text

HOOK = {'overlay': 'main', 'address': '0x800243CC', 'mode': 'pre',
        'target': 'Recompiled.PadPatches.InitDirect'}
CD_HOOK = {'overlay': 'main', 'address': '0x80018F3C', 'mode': 'pre',
           'target': 'Recompiled.CdPatches.PumpWhenPolling'}
GPU_HOOK = {'overlay': 'bishi1', 'address': '0x80035418', 'mode': 'post',
            'target': 'Recompiled.GpuPatches.CacheDrawEnv'}
RUNTIME_REVISION = '4259b76fa923d1e607a6b3379ef908cb5d5b9354'
# Exact pre-catalog descriptors, only to validate and migrate old ignored configs.
LEGACY_BANKS = (
    {'name': 'cd_data1_code', 'file': 'CD_DATA1.BIN', 'offset': 1046528,
     'size': 12288, 'base': '0x800C0000', 'functions': [
         {'address': '800C00B4'}, {'address': '800C0A44'}, {'address': '800C0FB0'}]},
    {'name': 'cd_data1_pins', 'file': 'CD_DATA1.BIN', 'offset': 1435648,
     'size': 20480, 'base': '0x800C0000', 'functions': [
         {'address': '800C0540'}, {'address': '800C4530'}]},
    {'name': 'cd_data1_roach', 'file': 'CD_DATA1.BIN', 'offset': 2576384,
     'size': 14336, 'base': '0x800C0000', 'functions': [{'address': '800C0CC0'}]},
)


def apply_runtime_patch(repo: Path) -> None:
    revision = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != RUNTIME_REVISION:
        raise ValueError(f'expected RecompOne {RUNTIME_REVISION}, got {revision}')
    command = ['git', '-C', str(repo), 'apply']
    for filename in ('runtime-cd.patch', 'runtime-bank-switch.patch'):
        patch = ROOT / 'port/patches' / filename
        if subprocess.run(command + ['--reverse', '--check', str(patch)],
                          capture_output=True).returncode == 0:
            continue
        subprocess.run(command + ['--check', str(patch)], check=True)
        subprocess.run(command + [str(patch)], check=True)


def validate_source_cue(config_path: Path, image: Path) -> None:
    cue_value = json.loads(config_path.read_text()).get('cue')
    if not isinstance(cue_value, str) or not cue_value:
        raise ValueError('missing CUE for validated disc image')
    try:
        resolved_image = image.resolve(strict=True)
        cue = Path(cue_value).resolve(strict=True)
        if cue != resolved_image.with_suffix('.cue') or cue.read_text() != cue_text(resolved_image.name):
            raise ValueError('configured CUE does not reference validated BIN')
    except OSError as exc:
        raise ValueError(f'cannot read configured CUE: {exc}') from exc


def prepare(path: Path, banks: list[Bank]) -> None:
    if (len(banks) != 96 or
        [(b.game, b.slot) for b in banks] !=
            [(game, slot) for game, count in (('super', 46), ('hyper', 48))
             for slot in range(-1, count)] or
        len({b.lba for b in banks}) != 96):
        raise ValueError('expected 96 distinct, ordered Super/Hyper disc banks')
    config = json.loads(path.read_text())
    if config['game']['id'] != 'SLES-02537':
        raise ValueError('expected SLES-02537 disc configuration')
    funcmap_path = path.parent / config['funcMap']
    funcmap = json.loads(funcmap_path.read_text())
    matches = [f for f in funcmap['functions'] if f['address'] == HOOK['address']]
    if len(matches) != 1 or matches[0]['name'] not in ('PadInitDirect', 'PadInitDirect_Game'):
        raise ValueError('unexpected PadInitDirect map at 0x800243CC')
    vsync = [f for f in funcmap['functions'] if f['address'] == CD_HOOK['address']]
    if len(vsync) != 1 or vsync[0]['name'] != 'VSync':
        raise ValueError('unexpected VSync map at 0x80018F3C')
    functions = funcmap['functions']
    boot = [f for f in functions if f['address'] == '0x80010D48']
    callback = [f for f in functions if f['address'] == '0x80011054']
    if (len(boot) != 1 or boot[0]['name'] != 'func_80010D48' or
        not ((boot[0]['size'] == 856 and not callback) or
             (boot[0]['size'] == 780 and len(callback) == 1 and
              callback[0]['name'] == 'func_80011054' and callback[0]['size'] == 76))):
        raise ValueError('unexpected VBlank input callback map at 0x80011054')
    overlays = []
    for name, start, old_size, target, new_size in (
        ('bishi1', '0x80014CDC', 2048, '0x80015414', 1848),
        ('bishi2', '0x80012FC0', 2136, '0x80013750', 1936),
    ):
        entries = [o for o in config.get('overlays', []) if o['name'] == name]
        if len(entries) != 1:
            raise ValueError(f'missing {name} overlay')
        overlay_path = path.parent / entries[0]['funcMap']
        overlay = json.loads(overlay_path.read_text())
        mapped = overlay['functions']
        if name == 'bishi1' and [(f['name'], f['size']) for f in mapped
                                 if f['address'] == GPU_HOOK['address']] != [('PutDrawEnv', 192)]:
            raise ValueError('unexpected bishi1 PutDrawEnv map at 0x80035418')
        original = [f for f in mapped if f['address'] == start]
        cb = [f for f in mapped if f['address'] == target]
        if (len(original) != 1 or original[0]['name'] != f'func_{start[2:]}' or
            not ((original[0]['size'] == old_size and not cb) or
                 (original[0]['size'] == new_size and len(cb) == 1 and
                  cb[0]['name'] == f'func_{target[2:]}' and cb[0]['size'] == 200))):
            raise ValueError(f'unexpected {name} IRQ callback map at {target}')
        overlays.append((overlay_path, overlay, original[0], target, new_size))
    for code in LEGACY_BANKS:
        found = [o for o in config['overlays'] if o['name'] == code['name']]
        if found and found != [code]:
            raise ValueError(f"unexpected legacy CD_DATA1.BIN overlay: {code['name']}")
    empty_map = path.parent / 'funcmaps/code-bank-empty.json'
    if empty_map.exists() and json.loads(empty_map.read_text()) != {'functions': []}:
        raise ValueError('unexpected code-bank-empty function map')
    config['overlays'] = [o for o in config['overlays']
                          if o['name'] not in {code['name'] for code in LEGACY_BANKS}]
    for bank in banks:
        seeds = ([] if bank.entry is None else [{'address': f'{bank.entry:08X}'}])
        if bank.name == 'super_bank_shared':
            seeds = [{'address': f'{entry:08X}'} for entry in
                     (0x800C00B4, 0x800C0A44, 0x800C0FB0)]
        if bank.name == 'hyper_bank_shared':
            seeds = [{'address': '8009859C'}, {'address': '80098810'}]
        if bank.name == 'super_bank_01':
            seeds.append({'address': '800C4530'})
        overlay = {'name': bank.name, 'lba': bank.lba, 'size': bank.size,
                   'base': f'0x{bank.base:08X}', 'functions': seeds,
                   'funcMap': 'funcmaps/code-bank-empty.json',
                   'linearSweep': False, 'pointerScan': False}
        found = [o for o in config['overlays'] if o['name'] == bank.name]
        previous = {key: value for key, value in overlay.items()
                    if key not in ('funcMap', 'linearSweep', 'pointerScan')}
        allowed = [overlay, previous]
        if bank.name == 'hyper_bank_shared':
            allowed += [{**row, 'functions': old} for row in allowed
                        for old in ([], [{'address': '80098810'}])]
        if found:
            if len(found) != 1 or found[0] not in allowed:
                raise ValueError(f'{bank.game} slot {bank.slot}: unexpected existing overlay')
            found[0].clear()
            found[0].update(overlay)
        else:
            config['overlays'].append(overlay)
    if boot[0]['size'] == 856:
        boot[0]['size'] = 780
        functions.insert(functions.index(boot[0]) + 1,
                         {'address': '0x80011054', 'name': 'func_80011054', 'size': 76})
    for overlay_path, overlay, original, target, new_size in overlays:
        if original['size'] != new_size:
            original['size'] = new_size
            entries = overlay['functions']
            entries.insert(entries.index(original) + 1,
                           {'address': target, 'name': f'func_{target[2:]}', 'size': 200})
        overlay_path.write_text(json.dumps(overlay, indent=2) + '\n')
    empty_map.write_text('{"functions": []}\n')
    matches[0]['name'] = 'PadInitDirect_Game'
    patches = config.setdefault('patches', [])
    for hook in (HOOK, CD_HOOK, GPU_HOOK):
        if hook not in patches:
            patches.append(hook)
    funcmap_path.write_text(json.dumps(funcmap, indent=2) + '\n')
    path.write_text(json.dumps(config, indent=2) + '\n')


def clear_generated(directory: Path) -> None:
    for source in directory.glob('*.cs'):
        source.unlink()


if __name__ == '__main__':
    # ponytail: requires local disc-probe maps; autogenerate them for clean-checkout builds.
    config_path = ROOT / '.local/probe/config/BishiBashi.json'
    image = ROOT / 'Bishi Bashi Special.bin'
    banks = load_catalog(image, ROOT / '.local/probe/disc.json')
    validate_source_cue(config_path, image)
    apply_runtime_patch(ROOT / '.local/RecompOne')
    prepare(config_path, banks)
    generated_dir = (config_path.parent / json.loads(config_path.read_text())['game']['output']).resolve()
    clear_generated(generated_dir)
    subprocess.run([str(ROOT / '.local/dotnet/dotnet'), 'run', '--project',
                    str(ROOT / '.local/RecompOne/RecompOne.Recompiler'), '-c', 'Release',
                    '--', str(config_path)], check=True, cwd=ROOT)
    rows = verify_generated(banks, generated_dir)
    (ROOT / '.local/probe/bank-audit.json').write_text(json.dumps(rows, indent=2) + '\n')
