import hashlib
import os
import sys
import tempfile
from pathlib import Path

EXPECTED_SHA256 = '76c717d7ca2a99b4a66e692889f277fef8db80761849c11c15c85d7f30436872'
SYNC = bytes.fromhex('00ffffffffffffffffffff00')


def validate(path: Path, *, expected_hash: str = EXPECTED_SHA256) -> None:
    try:
        size = path.stat().st_size
        if not size or size % 2352 or (expected_hash == EXPECTED_SHA256 and size != 88290 * 2352):
            raise ValueError('not the expected MODE2/2352 image')
        with path.open('rb') as f:
            digest = hashlib.sha256()
            for block in iter(lambda: f.read(1024 * 1024), b''):
                digest.update(block)
            if digest.hexdigest() != expected_hash:
                raise ValueError('disc SHA-256 does not match SLES_025.37 input')
            f.seek(0)
            for lba in range(size // 2352):
                h = f.read(2352)[:16]
                if h[:12] != SYNC or h[15] != 2:
                    raise ValueError(f'sector {lba}: not MODE2 data')
                if any((b >> 4) > 9 or (b & 15) > 9 for b in h[12:15]):
                    raise ValueError(f'sector {lba}: invalid BCD time')
                m, s, frame = ((b >> 4) * 10 + (b & 15) for b in h[12:15])
                if s >= 60 or frame >= 75 or (m * 60 + s) * 75 + frame != lba + 150:
                    raise ValueError(f'sector {lba}: discontinuous MSF')
    except OSError as exc:
        raise ValueError(f'cannot read disc: {exc}') from exc


def cue_text(name: str) -> str:
    if not name or any(c in name for c in ('"', '\r', '\n', '/', '\\')):
        raise ValueError('unsafe CUE filename')
    return f'FILE "{name}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n'


def main() -> int:
    try:
        path = Path(sys.argv[1]) if len(sys.argv) == 2 else None
        if path is None:
            raise ValueError('usage: disc_preflight.py path/to/disc.bin')
        text = cue_text(path.name)
        validate(path)
        cue = path.with_suffix('.cue')
        tmp = None
        try:
            with tempfile.NamedTemporaryFile('w', dir=path.parent, prefix='.cue-', delete=False) as f:
                tmp = f.name
                f.write(text)
            os.replace(tmp, cue)
        finally:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)
        print(cue)
        return 0
    except (ValueError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
