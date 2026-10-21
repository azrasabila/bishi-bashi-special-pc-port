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
