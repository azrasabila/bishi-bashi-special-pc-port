"""Keep game pad initialization and service CD work during VSync polling."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOK = {'overlay': 'main', 'address': '0x800243CC', 'mode': 'pre',
        'target': 'Recompiled.PadPatches.InitDirect'}
CD_HOOK = {'overlay': 'main', 'address': '0x80018F3C', 'mode': 'pre',
           'target': 'Recompiled.CdPatches.PumpWhenPolling'}
RUNTIME_REVISION = '4259b76fa923d1e607a6b3379ef908cb5d5b9354'
# At the crash, RAM 0x800C0000..0x800C3FFF matched CD_DATA1.BIN sectors 700..707.
RAW_CODE = {'name': 'cd_data1_code', 'file': 'CD_DATA1.BIN', 'offset': 1046528,
            'size': 12288, 'base': '0x800C0000', 'functions': [
                {'address': '800C00B4'}, {'address': '800C0A44'}, {'address': '800C0FB0'}]}
# The Pins overwrites that RAM region with code from CD_DATA1.BIN starting at LBA 890.
PINS_CODE = {'name': 'cd_data1_pins', 'file': 'CD_DATA1.BIN', 'offset': 1435648,
             'size': 20480, 'base': '0x800C0000', 'functions': [
                 {'address': '800C0540'}, {'address': '800C4530'}]}
# The Roach stage loads its own code into the same RAM region from LBA 1447.
ROACH_CODE = {'name': 'cd_data1_roach', 'file': 'CD_DATA1.BIN', 'offset': 2576384,
              'size': 14336, 'base': '0x800C0000', 'functions': [
                  {'address': '800C0CC0'}]}


def apply_runtime_patch(repo: Path) -> None:
    revision = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != RUNTIME_REVISION:
        raise ValueError(f'expected RecompOne {RUNTIME_REVISION}, got {revision}')
    patch = ROOT / 'port/patches/runtime-cd.patch'
    command = ['git', '-C', str(repo), 'apply']
    if subprocess.run(command + ['--reverse', '--check', str(patch)],
                      capture_output=True).returncode == 0:
        return
    subprocess.run(command + ['--check', str(patch)], check=True)
    subprocess.run(command + [str(patch)], check=True)


def prepare(path: Path) -> None:
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
        original = [f for f in mapped if f['address'] == start]
        cb = [f for f in mapped if f['address'] == target]
        if (len(original) != 1 or original[0]['name'] != f'func_{start[2:]}' or
            not ((original[0]['size'] == old_size and not cb) or
                 (original[0]['size'] == new_size and len(cb) == 1 and
                  cb[0]['name'] == f'func_{target[2:]}' and cb[0]['size'] == 200))):
            raise ValueError(f'unexpected {name} IRQ callback map at {target}')
        overlays.append((overlay_path, overlay, original[0], target, new_size))
    for code in (RAW_CODE, PINS_CODE, ROACH_CODE):
        found = [o for o in config['overlays'] if o['name'] == code['name']]
        if found and found != [code]:
            raise ValueError(f"unexpected CD_DATA1.BIN code overlay: {code['name']}")
        if not found:
            config['overlays'].append(code)
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
    matches[0]['name'] = 'PadInitDirect_Game'
    patches = config.setdefault('patches', [])
    for hook in (HOOK, CD_HOOK):
        if hook not in patches:
            patches.append(hook)
    funcmap_path.write_text(json.dumps(funcmap, indent=2) + '\n')
    path.write_text(json.dumps(config, indent=2) + '\n')


if __name__ == '__main__':
    # ponytail: requires local disc-probe maps; autogenerate them for clean-checkout builds.
    config_path = ROOT / '.local/probe/config/BishiBashi.json'
    apply_runtime_patch(ROOT / '.local/RecompOne')
    prepare(config_path)
    subprocess.run([str(ROOT / '.local/dotnet/dotnet'), 'run', '--project',
                    str(ROOT / '.local/RecompOne/RecompOne.Recompiler'), '-c', 'Release',
                    '--', str(config_path)], check=True, cwd=ROOT)
