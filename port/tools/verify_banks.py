"""Fail-closed audit of emitted code banks and their dispatcher activations."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from port.tools.code_banks import Bank


def verify_generated(banks: list[Bank], generated_dir: Path) -> list[dict]:
    entry_source = (generated_dir / 'Entry.cs').read_text()
    rows = []
    names = [b.name for b in banks]
    if len(names) != len(set(names)) or len({b.lba for b in banks}) != len(banks):
        raise ValueError('duplicate bank name or disc LBA')
    registered = re.findall(r'Dispatcher\.Register\("((?:super|hyper)_bank_[^"]+)",', entry_source)
    for bank in banks:
        label = f'{bank.game} slot {bank.slot}'
        cls = bank.name[0].upper() + bank.name[1:] + 'DispatchTable'
        if entry_source.count(f'Dispatcher.Register("{bank.name}", new {cls}());') != 1:
            raise ValueError(f'{label}: missing generated bank registration')
        try:
            source = (generated_dir / f'{bank.name}.cs').read_text()
        except FileNotFoundError as exc:
            raise ValueError(f'{label}: missing generated bank file') from exc
        required = [f'public string Name => "{bank.name}";',
                    f'public int LbaStart => {bank.lba};',
                    f'public uint Base => 0x{bank.base:08X}u;',
                    f'public uint Size => 0x{bank.size:X}u;']
        if bank.entry is not None:
            required.append(f'[0x{bank.entry:08X}u] =')
        if bank.name == 'hyper_bank_shared':
            required.extend(('[0x8009859Cu] =', '[0x80098810u] ='))
        if not all(line in source for line in required):
            raise ValueError(f'{label}: missing or incorrect dispatcher mapping')
        suspect = re.search(r'/\* UNKOWN OP|Dispatcher\.Call\(c, m, 0u\);', source)
        if suspect:
            raise ValueError(f'{label}: unresolved code/data boundary: {suspect.group()}')
        pointer = None if bank.entry is None else f'0x{bank.entry:08X}'
        rows.append({'game': bank.game, 'slot': bank.slot, 'name': bank.name,
                     'pointer': pointer, 'entry': pointer,
                     'relativeSector': bank.relative_sector, 'lba': bank.lba,
                     'declaredSize': bank.size, 'size': bank.size,
                     'paddedSize': ((bank.size + 2047) // 2048) * 2048,
                     'base': bank.base, 'generatedEntry': bank.entry is not None,
                     'activationTest': 'pending' if bank.entry is not None else 'not-applicable'})
    if sorted(registered) != sorted(names):
        raise ValueError('unexpected extra generated bank registration')
    return rows


def main(path: Path) -> None:
    rows = json.loads(path.read_text())
    if (len(rows) != 96 or
        [(row['game'], row['slot']) for row in rows] !=
            [(game, slot) for game, count in (('super', 46), ('hyper', 48))
             for slot in range(-1, count)] or
        any(row['activationTest'] != ('passed' if row['slot'] >= 0 else 'not-applicable') or
            row['generatedEntry'] != (row['slot'] >= 0) for row in rows)):
        raise ValueError('incomplete bank audit: require 46 Super + 48 Hyper activation passes')
    print('Bank audit: 46 Super + 48 Hyper entries generated and activated; '
          '2 shared banks checked; gameplay not verified')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: verify_banks.py .local/probe/bank-audit.json')
    main(Path(sys.argv[1]))
