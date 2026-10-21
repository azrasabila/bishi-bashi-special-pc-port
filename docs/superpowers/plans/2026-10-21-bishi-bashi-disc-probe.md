# Bishi Bashi Disc Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a verified local CUE and a reproducible RecompOne probe/configuration report for the supplied disc, establishing the actual boot/module inputs before planning a playable build.

**Architecture:** A small Python standard-library preflight validates the exact disc and generates an untracked CUE beside it; RecompOne at a pinned revision probes and autoconfigures the PS-X executables. A human-readable report distinguishes raw-disc observations, RecompOne guesses, and REA's unavailable PS-X analysis. This is a **discovery milestone**, not the playable-port plan: unknown code-loading and patch behavior cannot responsibly be specified before this probe.

**Tech Stack:** Python 3 standard library; RecompOne revision `4259b76fa923d1e607a6b3379ef908cb5d5b9354`; .NET 10 SDK. No new product dependency besides the chosen recompiler.

**Spec:** `docs/superpowers/specs/2026-10-21-bishi-bashi-static-recompilation-design.md`

## Global Constraints

- Target eventual native `win-x64` and `linux-x64` programs; no emulator launcher or PS1 BIOS. First playable acceptance target: Burst the Balloon, but that is **not** claimed by this plan.
- The disc, generated C#, extracted assets, and `.cue` remain untracked. Do not commit copyrighted game bytes.
- Input is the user's `Bishi Bashi Special.bin`, SHA-256 `76c717d7ca2a99b4a66e692889f277fef8db80761849c11c15c85d7f30436872`; do not silently accept another region/revision.
- If .NET 10 SDK setup requires system modifications, present the exact setup action to the user for approval before doing it; do not silently replace their existing `dotnet` launcher.
- Only claim REA Evidence if a supported REA operation returns it. `inspect-artifact` currently rejects PS-X EXE, and no native provider is available here.
- This directory currently has no Git repository. Do not initialize one without the user's approval; commit steps apply only if the user later provides a repository.

## Review Focus

- Missing/renamed BIN: reject without writing a misleading CUE (Task 1).
- Truncated or wrong-region BIN: reject before sector processing or CUE creation (Task 1).
- Data image containing CD-DA/non-MODE2 sectors or discontinuous MSF: reject the proposed one-track CUE rather than guessing (Task 1).
- Missing/broken .NET 10 SDK: stop with setup guidance instead of reporting a RecompOne probe result (Task 2).
- Autoconfig guesses that omit an executable or misidentify boot: fail the report gate; do not treat sweep output as validated game code (Task 2).

---

## Files and responsibilities

- Create `tools/disc_preflight.py`: validate exactly the supplied disc and atomically create an adjacent one-track CUE from measured sector evidence.
- Create `tests/test_disc_preflight.py`: tiny standard-library `unittest` tests of errors and cue syntax; no real disc copied into tests.
- Create `docs/research/disc-probe.md`: dated probe commands, measured outputs, remaining unknowns, and the next planning gate.
- Local untracked artifacts: `Bishi Bashi Special.cue`, `.local/RecompOne/`, `.local/probe/`. Add `.gitignore` **only if** this directory becomes a Git repository; never `git add` the disc or generated outputs.

### Task 1: Validate the disc and produce a CUE safely

**Files:** Create `tools/disc_preflight.py`; create `tests/test_disc_preflight.py`.

**Interfaces:** CLI: `python3 tools/disc_preflight.py 'Bishi Bashi Special.bin'`; success prints path to adjacent CUE. `validate(path: pathlib.Path, *, expected_hash: str = EXPECTED_SHA256) -> None` raises `ValueError` for incorrect input; `cue_text(name: str) -> str` returns `FILE "<name>" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n`. CLI reports errors and exits nonzero, with no CUE left on failure.

- [ ] **Step 1: Write failing tests.** Create `tests/test_disc_preflight.py`:

```python
import hashlib
import tempfile
import unittest
from pathlib import Path
from tools.disc_preflight import validate, cue_text


class DiscTest(unittest.TestCase):
    def test_rejects_missing_and_wrong_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'game.bin'
            with self.assertRaises(ValueError): validate(path)
            path.write_bytes(b'bad')
            with self.assertRaises(ValueError): validate(path)
            path.write_bytes(b'\0' * 2352)
            with self.assertRaises(ValueError): validate(path)

    def test_checks_sector_mode_and_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'game.bin'
            sector = bytearray(2352)
            sector[:12] = bytes.fromhex('00ffffffffffffffffffff00')
            sector[12:16] = bytes([0, 2, 0, 2])
            path.write_bytes(sector)
            validate(path, expected_hash=hashlib.sha256(sector).hexdigest())
            for index, value in ((15, 1), (14, 1)):
                broken = sector.copy(); broken[index] = value
                path.write_bytes(broken)
                with self.assertRaises(ValueError):
                    validate(path, expected_hash=hashlib.sha256(broken).hexdigest())

    def test_cue_syntax_and_name(self):
        self.assertEqual(cue_text('game.bin'), 'FILE "game.bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n')
        for name in ('bad".bin', 'bad\n.bin', '../bad.bin'):
            with self.assertRaises(ValueError): cue_text(name)
```
- [ ] **Step 2: Run `python3 -m unittest discover -s tests -v`; expect import or assertion failure.**
- [ ] **Step 3: Implement the minimum.** Create `tools/disc_preflight.py`:

```python
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
```

The CUE assumption is deliberately limited to the hashed image after checking every sector's sync, mode, and sequential MSF; it does not prove perfect XA audio playback.
- [ ] **Step 4: Re-run the unittest command; expect PASS.** Run `python3 tools/disc_preflight.py 'Bishi Bashi Special.bin'`; expect the exact input SHA-256 to pass and one CUE beside the BIN. Check `git status --short` only if inside a Git repository; exclude the CUE and BIN from any commit.
- [ ] **Step 5: If and only if a repository exists, commit the script/tests without game data.** Otherwise leave files uncommitted and report that no Git repository exists.

### Task 2: Establish RecompOne's actual view of boot and modules

**Files:** Create `docs/research/disc-probe.md`. No modification to RecompOne source in this task.

**Interfaces:** Input: Task 1 CUE. Output: `.local/probe/disc.json` and an evidence report listing executable entries, load addresses, configured module mapping, unresolved embedded-code questions, and the route to the next implementation plan.

- [ ] **Step 1: Verify `dotnet --list-sdks` shows major version 10.** If it fails (currently `libhostfxr.so` is missing), stop and request approval for a scoped .NET 10 installation; do not run or claim the remainder until repaired.
- [ ] **Step 2: Obtain the pinned RecompOne revision outside version control.** Run `git clone https://github.com/BlackLabelHQ/RecompOne .local/RecompOne && git -C .local/RecompOne checkout 4259b76fa923d1e607a6b3379ef908cb5d5b9354`. If it already exists, confirm the hash and reuse it. Run `dotnet build .local/RecompOne/RecompOne.Recompiler -c Release`; expect zero exit status.
- [ ] **Step 3: Probe, capturing outputs rather than inferring success.** Run `mkdir -p .local/probe && dotnet run --project .local/RecompOne/RecompOne.Recompiler -c Release --no-build -- --probe-disc 'Bishi Bashi Special.cue' -json .local/probe/disc.json -all > .local/probe/probe.log`. Use `python3 -c "import json; d=json.load(open('.local/probe/disc.json')); assert d['boot']=='SLES_025.37'; assert {'BISHI1.EXE','BISHI2.EXE','SLES_025.37'} <= {f['path'] for f in d['files'] if f['kind']=='executable'}"`; expect zero exit status. Inspect all non-media records, not only these three.
- [ ] **Step 4: Generate tentative config/maps.** Run `dotnet run --project .local/RecompOne/RecompOne.Recompiler -c Release --no-build -- --autoconfigure 'Bishi Bashi Special.cue' -out .local/probe/config -name BishiBashi -sweep-all > .local/probe/autoconfigure.log`. Check exit status, generated config's `cue`/`overlays`, and map files. If this command fails, record its exact error; do not manually invent module bases to make it pass.
- [ ] **Step 5: Write `docs/research/disc-probe.md` from observed results.** Record disc SHA and CUE rationale, pinned tool revision, boot and all identified executable/module candidates with confidence, exact probe commands and pass/fail, toolchain status, REA limitation (no Evidence ID), which code/data loads remain unknown, and the next gated experiment (trace boot → menu → Burst the Balloon; locate embedded code before generating playable-build tasks). Do not copy copyrighted binary or generated C# into the report.
- [ ] **Step 6: If and only if a repository exists, commit the report/configuration text after excluding the disc and `.local/`.** Otherwise report that no commit was possible. Stop here; design the runnable-port plan using the actual probe findings.

## Self-review checks

Compare the report against the spec's input, module, REA, toolchain, platform, and copyright constraints. Confirm all five Review Focus conditions are tested or gated as indicated. A generated config alone does not establish playable gameplay; publish no `win-x64` or `linux-x64` success claim in this phase.
