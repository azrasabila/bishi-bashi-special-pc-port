"""Extract stage code-bank sources from the validated SLES_025.37 disc."""
import json
import struct
from dataclasses import dataclass
from pathlib import Path

from tools.disc_preflight import validate


@dataclass(frozen=True)
class Bank:
    game: str
    slot: int
    entry: int | None
    relative_sector: int
    lba: int
    size: int
    base: int

    @property
    def name(self) -> str:
        return (f'{self.game}_bank_shared' if self.slot < 0 else
                f'{self.game}_bank_{self.slot:02d}')


# Directory offset, call-table RAM address, call count, stage load base.
LAYOUTS = {
    'super': (0x4A4E0, 0x80057470, 46, 0x800C0000),
    'hyper': (0x3D330, 0x8004BFE0, 48, 0x80098000),
}
# File extents are fixed for the SHA-256-validated European disc.
FILES = {
    'BISHI1.EXE': (23, 339968), 'CD_DATA1.BIN': (189, 9458020),
    'BISHI2.EXE': (4808, 274432), 'CD_DATA2.BIN': (4942, 10865120),
}
ANCHORS = {
    'super': {0: (0x1FF, 0x4000), 2: (0x2BD, 0xC000),
              5: (0x408, 0x4800), 7: (0x4EA, 0x5800), 46: (0x1201, 0x5000)},
    'hyper': {0: (0x29F, 0x4000), 7: (0x52B, 0x4000), 48: (0x1391, 0x5800)},
}


def parse_bank_table(exe: bytes, *, game: str, cd_lba: int,
                     cd_sectors: int, disc_sectors: int) -> list[Bank]:
    directory, table, count, base = LAYOUTS[game]
    if exe[:8] != b'PS-X EXE' or len(exe) < 0x1C or struct.unpack_from('<I', exe, 0x18)[0] != 0x80010000:
        raise ValueError(f'{game} slot -1: unexpected PS-X EXE header/load address')
    pointer_offset = table - 0x80010000 + 0x800
    if len(exe) < max(directory + (count + 1) * 8, pointer_offset + count * 4):
        raise ValueError(f'{game} slot -1: truncated bank directory or pointer table')
    banks = []
    previous_end = -1
    for i in range(count + 1):
        slot = i - 1
        relative, size = struct.unpack_from('<II', exe, directory + i * 8)
        if not size or size % 2048 or relative < previous_end:
            raise ValueError(f'{game} slot {slot}: invalid bank sector/size')
        end = relative + size // 2048
        lba = cd_lba + relative
        if end > cd_sectors or lba + size // 2048 > disc_sectors:
            raise ValueError(f'{game} slot {slot}: bank exceeds disc sectors')
        previous_end = end
        entry = None
        if slot >= 0:
            entry, = struct.unpack_from('<I', exe, pointer_offset + 4 * slot)
            if entry & 3 or not base <= entry < base + size:
                raise ValueError(f'{game} slot {slot}: entry outside bank')
        banks.append(Bank(game, slot, entry, relative, lba, size, base))
    return banks


def validate_anchors(banks: list[Bank]) -> None:
    for game, checks in ANCHORS.items():
        group = [b for b in banks if b.game == game]
        if len(group) != LAYOUTS[game][2] + 1:
            raise ValueError(f'{game} slot -1: unexpected bank count')
        for index, pair in checks.items():
            bank = group[index]
            if (bank.slot, bank.relative_sector, bank.size) != (index - 1, *pair):
                raise ValueError(f'{game} slot {index - 1}: unexpected known bank record')


def load_catalog(image: Path, inventory: Path) -> list[Bank]:
    validate(image)
    files = json.loads(inventory.read_text())['files']
    extents = {}
    for name, expected in FILES.items():
        matches = [f for f in files if f['path'] == name]
        if len(matches) != 1 or (matches[0]['lba'], matches[0]['size']) != expected:
            raise ValueError(f'{name}: missing or unexpected ISO extent')
        extents[name] = expected

    banks = []
    disc_sectors = image.stat().st_size // 2352
    with image.open('rb') as stream:
        def read_sectors(lba: int, size: int) -> bytes:
            result = bytearray()
            for sector in range((size + 2047) // 2048):
                stream.seek((lba + sector) * 2352 + 24)
                payload = stream.read(2048)
                if len(payload) != 2048:
                    raise ValueError(f'sector {lba + sector}: truncated disc')
                result.extend(payload)
            return bytes(result)

        for game, exe_name, data_name in (
            ('super', 'BISHI1.EXE', 'CD_DATA1.BIN'),
            ('hyper', 'BISHI2.EXE', 'CD_DATA2.BIN'),
        ):
            exe_lba, exe_size = extents[exe_name]
            cd_lba, cd_size = extents[data_name]
            banks += parse_bank_table(read_sectors(exe_lba, exe_size), game=game,
                                      cd_lba=cd_lba, cd_sectors=(cd_size + 2047) // 2048,
                                      disc_sectors=disc_sectors)
    validate_anchors(banks)
    return banks
