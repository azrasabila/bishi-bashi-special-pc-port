# Bishi Bashi Disc Code-Bank Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give all 46 Super and 48 Hyper game-call slots validated static-recompilation bank sources and active dispatcher entries, and clear the observed Super racing/representative Hyper calls without claiming gameplay.

**Architecture:** Parse the two on-disc EXEs' paired bank directories and call tables into a small immutable catalog. Produce LBA-sourced RecompOne overlays from it, verify every emitted entry, and test exclusive activation of same-base banks. Fail on mismatches rather than substituting code from a different stage.

**Tech Stack:** Python 3 standard library (`struct`, `json`, `unittest`), pinned RecompOne/.NET 10/C#, the ignored MODE2/2352 disc and ignored generated config.

**Spec:** `docs/superpowers/specs/2026-10-22-bishi-bashi-disc-code-bank-mapping-design.md`

## Global Constraints

- The disc is the validated European `SLES_025.37` MODE2/2352 user image; use `tools/disc_preflight.py`'s existing SHA-256 validation and `.local/probe/disc.json` for ISO extents.
- Keep disc bytes, extracted assets, generated metadata, C#, and visual artifacts ignored; no emulator, BIOS, stub, or guessed callback body.
- RecompOne must be at `4259b76fa923d1e607a6b3379ef908cb5d5b9354`; add port-local patches idempotently, never modify upstream checkout version without validation.
- Success is mapping-level coverage plus bounded Linux checks, not 94 gameplay wins, audio/gamepad/Windows runtime verification, or a Burst the Balloon playability claim.
- Work in an ignored isolated worktree; symlink the ignored BIN/CUE, disc inventory, and local `.local/dotnet` SDK from the parent repo, copy the mutable ignored `.local/probe/config` into the worktree, and use an **independent copy/clone** of pinned `.local/RecompOne` because patching mutates it. Merge reviewed commits locally to `main`, do not push. Preserve the preexisting untracked `interface.ini`.

## Review Focus

1. Last Super record extends 1,692 bytes beyond the ISO byte length but fits padded sectors: parser and RecompOne must not truncate it (Task 1 and 2 tests).
2. Slot aliases (45 distinct Super pointers among 46 slots; 46 distinct Hyper among 48) must remain separate bank records (Task 1 test).
3. A smaller same-base incoming bank must evict a larger bank's stale dispatcher entries (Task 3 executable test).
4. One failed function extraction or wrong LBA must fail the gate with game/slot, not silently count a bank as mapped (Task 4 test).
5. Hyper's `0x80098000` base and slot-to-bank alignment have only static evidence: require a live RAM/disc match and bounded check before claiming runtime confirmation (Task 5).

---

### Task 1: Extract and validate both disc bank catalogs

**Files:**
- Create: `port/tools/code_banks.py` — immutable bank records and raw-sector/EXE parsing.
- Create: `tests/test_code_banks.py` — synthetic table fixtures and validation.

**Interfaces:**
- Consumes: `tools.disc_preflight.validate(image: Path)`, the ignored BIN, `.local/probe/disc.json` entries `path/lba/size`.
- Produces: `Bank(game: str, slot: int, entry: int | None, relative_sector: int, lba: int, size: int, base: int)` with `name` property (`super_bank_shared`, `super_bank_00`, …, `hyper_bank_47`); `parse_bank_table(exe: bytes, *, game: str, cd_lba: int, cd_sectors: int, disc_sectors: int) -> list[Bank]`; `load_catalog(image: Path, inventory: Path) -> list[Bank]`. `slot=-1`/`entry=None` is the shared bank. Return exactly 47 Super + 49 Hyper records, retaining duplicate entry addresses as separate slots.

- [ ] **Step 1: Write failing pure-parser tests.** Construct a PS-X EXE bytearray with the destination at header offset `0x18`, `count+1` `<II` records at the selected directory offset, and `count` `<I` addresses at `(table_ram - destination + 0x800)`. Test both `super` (directory `0x4A4E0`, table `0x80057470`, 46 calls, base `0x800C0000`) and `hyper` (`0x3D330`, `0x8004BFE0`, 48 calls, `0x80098000`). Assert bank `i+1` holds slot `i`, absolute LBA adds the CD_DATA start, an aliased pointer creates two slots, and a padded last sector passes when its end fits `cd_sectors` despite an unpadded ISO length. Mutate one header, pointer, sector offset, and size to assert `ValueError` includes game/slot.

```python
# tests/test_code_banks.py — complete synthetic directory + pointer fixture.
def fake_exe(game, entry=None):
    directory, table, count, base, first = {
        'super': (0x4A4E0, 0x80057470, 46, 0x800C0000, 511),
        'hyper': (0x3D330, 0x8004BFE0, 48, 0x80098000, 671),
    }[game]
    pointer_offset = table - 0x80010000 + 0x800
    exe = bytearray(max(directory + (count + 1) * 8, pointer_offset + count * 4))
    exe[:8] = b'PS-X EXE'
    struct.pack_into('<I', exe, 0x18, 0x80010000)
    for i in range(count + 1):
        struct.pack_into('<II', exe, directory + i * 8, first + 16 * i, 0x4000)
    for i in range(count):
        struct.pack_into('<I', exe, pointer_offset + i * 4,
                         (base + 0x100) if i or entry is None else entry)
    return bytes(exe)

banks = parse_bank_table(fake_exe('super'), game='super', cd_lba=189,
                         cd_sectors=4619, disc_sectors=88290)
assert len(banks) == 47
assert banks[0].slot == -1 and banks[1].slot == 0
assert banks[1].lba == 189 + 511 + 16  # fixture: second relative sector 527
assert banks[1].entry == 0x800C0100
with self.assertRaisesRegex(ValueError, 'super slot 0'):
    parse_bank_table(fake_exe('super', entry=0), game='super', cd_lba=189,
                     cd_sectors=4619, disc_sectors=88290)
```

- [ ] **Step 2: Confirm RED.** Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_code_banks.py' -v`; expect import/function failure, not a fixture error.
- [ ] **Step 3: Implement the minimum parser.** Use fixed, reviewed table layouts, not a heuristic that might select another pointer run. Check `b'PS-X EXE'`, destination `0x80010000`, record and pointer bounds, 2048-byte-aligned nonzero sizes, strictly increasing and unique relative sector starts, `relative + size//2048 <= cd_sectors`, `absolute_lba + size//2048 <= disc_sectors`, aligned entries inside `[base, base+size)`. `load_catalog` first calls `validate(image)`, reads each ISO file as consecutive `image.seek((lba+i)*2352+24); image.read(2048)` payloads (including the padded last sector), then calls the pure parser. Require exactly one inventory entry for each of `BISHI1.EXE`, `BISHI2.EXE`, `CD_DATA1.BIN`, `CD_DATA2.BIN`. In `load_catalog`, also call `validate_anchors(banks)` to require real-disc record `(relative sector, size)` pairs: Super directory indices 0 `(0x1FF,0x4000)`, 2 `(0x2BD,0xC000)`, 5 `(0x408,0x4800)`, 7 `(0x4EA,0x5800)`, 46 `(0x1201,0x5000)`; Hyper indices 0 `(0x29F,0x4000)`, 7 `(0x52B,0x4000)`, 48 `(0x1391,0x5800)`. `validate_anchors` raises on a mismatch with game and slot; test a mutated racing anchor as a failing gate.

```python
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
        return f'{self.game}_bank_shared' if self.slot < 0 else f'{self.game}_bank_{self.slot:02d}'

# Inside parse_bank_table, read the exact fields before constructing Bank:
relative, size = struct.unpack_from('<II', exe, directory_offset + 8 * (slot + 1))
entry, = struct.unpack_from('<I', exe, pointer_offset + 4 * slot)
if entry & 3 or not base <= entry < base + size:
    raise ValueError(f'{game} slot {slot}: entry outside bank')
```

- [ ] **Step 4: GREEN and real-disc anchors.** Run the focused suite and a read-only `load_catalog(...)` invocation with the ignored disc. Assert 96 records (47 + 49), Super shared LBA 700, Pins slot 1 LBA 890, Roach slot 6 LBA 1447, racing slot 4 LBA 1221, and Hyper slot 6 LBA 6265. Confirm the padded last Super record is accepted, not truncated. Do not write disc bytes.
- [ ] **Step 5: Commit** `port/tools/code_banks.py` and `tests/test_code_banks.py` with a single descriptive message. Run the entire Python suite after the focused gate.

### Task 2: Generate RecompOne overlays from the catalog

**Files:**
- Modify: `port/tools/recompile.py` — replace the three manual bank constants with catalog-backed LBA records.
- Modify: `tests/test_recompile.py` — idempotence, migration, and rejection fixtures.

**Interfaces:**
- Consumes: `list[Bank]` from Task 1, existing `prepare(path)` callback splits and runtime CD patch.
- Produces: `prepare(path: Path, banks: list[Bank]) -> None`. `__main__` uses `load_catalog(ROOT / 'Bishi Bashi Special.bin', ROOT / '.local/probe/disc.json')`. One overlay per Bank: `{'name': bank.name, 'lba': bank.lba, 'size': bank.size, 'base': f'0x{bank.base:08X}', 'functions': [] if bank.entry is None else [{'address': f'{bank.entry:08X}'}]}`. Keep known shared Super seeds `0x800C00B4`, `0x800C0A44`, `0x800C0FB0`, and Pins slot 1 `0x800C4530` only if needed for the already observed nested call; do not create duplicate bank registrations.

- [ ] **Step 1: Write failing config tests.** Adapt the existing temp config fixture to pass 96 synthetic `Bank` objects to `prepare`; assert 96 uniquely named bank overlays after two calls, correct base/LBA/size/seeds for both variants, and the unchanged pad/CD hooks and callback splits. Put the three current hand-written bank descriptors into the fixture: they must migrate, not coexist with catalog entries. Change a legacy descriptor or add a duplicate generated bank name; expect `ValueError` **before any file write**.

```python
# tests/test_recompile.py — compact coverage check, alongside existing hook assertions.
prepare(config, banks)
prepare(config, banks)
rows = [o for o in json.loads(config.read_text())['overlays']
        if o['name'].startswith(('super_bank_', 'hyper_bank_'))]
self.assertEqual((len(rows), len({o['name'] for o in rows})), (96, 96))
self.assertEqual(next(o for o in rows if o['name'] == 'super_bank_04')['lba'], 1221)
self.assertEqual(next(o for o in rows if o['name'] == 'hyper_bank_06')['lba'], 6265)
```

- [ ] **Step 2: RED:** `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_recompile.py' -v` must fail on the absent bank-aware `prepare` behavior.
- [ ] **Step 3: Implement validated migration and generation.** Compare any legacy `RAW_CODE/PINS_CODE/ROACH_CODE` entry against its original exact dictionary, then remove it. Reject unknown bank-name collisions or mismatching existing generated entries. Validate the full catalog before writing `BishiBashi.json` or funcmaps; append deterministic catalog overlays in game/slot order. Keep `prepare` idempotent and leave existing PadInitDirect/VSync/IRQ split logic unchanged. Use `lba` rather than `file` to allow the padded final bank.

```python
for bank in banks:
    overlay = {'name': bank.name, 'lba': bank.lba, 'size': bank.size,
               'base': f'0x{bank.base:08X}',
               'functions': [] if bank.entry is None else
                            [{'address': f'{bank.entry:08X}'}]}
    old = [row for row in config['overlays'] if row['name'] == bank.name]
    if old and old != [overlay]:
        raise ValueError(f'{bank.game} slot {bank.slot}: unexpected existing overlay')
    if not old:
        config['overlays'].append(overlay)
```

- [ ] **Step 4: GREEN** focused and whole Python suite. With the owned disc, regenerate in the ignored `.local/probe/` path and confirm RecompOne emits all 96 bank overlay classes; record actual recompiler warnings/failures per bank. If the generator cannot emit a seeded slot or code/data ambiguity prevents sound output, **stop** with that slot and revise the extraction boundary instead of calling the build mapped.
- [ ] **Step 5: Commit** only tracked Python/tests; do not stage generated config, C#, or disc content.

### Task 3: Exclusively activate overlapping code banks

**Files:**
- Create: `port/patches/runtime-bank-switch.patch` — pinned-runtime same-base overlap correction.
- Modify: `port/tools/recompile.py` — idempotent application alongside `runtime-cd.patch`.
- Modify: `tests/test_runtime_patch.py` — patch/revision checks.
- Create: `tests/BankSwitchCheck.csproj`, `tests/BankSwitchCheck.cs` — small runnable bank-switch regression using real `Dispatcher`, first with fake overlays.

**Interfaces:**
- Consumes: Task 2's overlay names/bases, pinned RecompOne `IOverlay` and `Dispatcher`.
- Produces: `.local/dotnet/dotnet run --project tests/BankSwitchCheck.csproj -c Release -- fake` returns 0 only when a smaller new bank evicts an old same-base bank, its exclusive old function is absent, and partial overlaps with different bases retain existing behavior. `apply_runtime_patch(repo)` remains revision-checked and idempotent for both tracked patches.

- [ ] **Step 1: Write RED executable test.** Create a .NET 10 console project referencing `../.local/RecompOne/RecompOne.Runtime/RecompOne.Runtime.csproj`. Implement `IOverlay` as below; register `big` (`Base=0x800C0000`, `Size=0x5000`, exclusive entry `0x800C4000`) and `small` (same base, `Size=0x3000`, entry `0x800C0100`). Call `Dispatcher.Load("big")`, `Dispatcher.LoadByLba(small.LbaStart)`, `Dispatcher.NotifyWrite(0x000C0000)`. Assert `Dispatcher.ActiveNames` contains only `small` and `!Dispatcher.CanCall(0x800C4000)`. Also test two different-base partially overlapping overlays remain active. A separate Python test clones the pinned runtime, applies both patches twice, checks changed paths, and rejects a wrong revision.

```xml
<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType>
<TargetFramework>net10.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings>
<Nullable>enable</Nullable></PropertyGroup><ItemGroup><ProjectReference
Include="../.local/RecompOne/RecompOne.Runtime/RecompOne.Runtime.csproj" />
</ItemGroup></Project>
```

```csharp
using RecompOne.Runtime.Context;
using RecompOne.Runtime.Dispatch;
using RecompOne.Runtime.Memory;

var big = new Fake("big", 200, 0x800C0000u, 0x5000u, 0x800C4000u);
var small = new Fake("small", 201, 0x800C0000u, 0x3000u, 0x800C0100u);
Dispatcher.Reset();
Dispatcher.Register("big", big);
Dispatcher.Register("small", small);
Dispatcher.Load("big");
Dispatcher.LoadByLba(small.LbaStart);
Dispatcher.NotifyWrite(0x000C0000);
if (Dispatcher.ActiveNames.Contains("big") || !Dispatcher.CanCall(0x800C0100)
    || Dispatcher.CanCall(0x800C4000)) throw new Exception("stale code bank");

sealed class Fake(string name, int lba, uint @base, uint size, uint entry) : IOverlay {
    public string Name => name;
    public int LbaStart => lba;
    public uint Base => @base;
    public uint Size => size;
    public IReadOnlyDictionary<uint, Action<CpuContext, IMemory>> Functions { get; } =
        new Dictionary<uint, Action<CpuContext, IMemory>> { [entry] = (_, _) => { } };
}
```

- [ ] **Step 2: Confirm RED** on the unpatched clone via `.local/dotnet/dotnet run --project tests/BankSwitchCheck.csproj -c Release -- fake` (fails with `stale code bank`). Run the new `test_runtime_patch.py` assertion (fails because the second patch is absent).
- [ ] **Step 3: Minimal patch.** In `Dispatcher.HandleRegionOverwrites`, where a region overlap currently evicts only when `s >= newStart && e <= newEnd`, evict also when `s == newStart`. Do not alter other overlapping-region logic. Save the diff as `port/patches/runtime-bank-switch.patch`. In `apply_runtime_patch`, iterate `('runtime-cd.patch', 'runtime-bank-switch.patch')`, with the existing reverse-check → check → apply sequence and the single pinned-revision guard.

```csharp
// In the existing overlapping-regions branch, before continue:
if (s == newStart || (s >= newStart && e <= newEnd))
{
    overwritten ??= [];
    overwritten.Add(activeName);
}
```

- [ ] **Step 4: GREEN** C# fake-bank check and full Python suite; test `apply_runtime_patch` twice in a fresh clone and confirm it changes only `sdk/LibCd.cs` and `Dispatch/Dispatcher.cs`. Rebuild the port. Stop if the patch breaks `main` → BISHI1/BISHI2 activation.
- [ ] **Step 5: Commit** patch, integration, and tests together; do not commit `.local/RecompOne` changes.

### Task 4: Prove all generated entries and activation rules

**Files:**
- Create: `port/tools/verify_banks.py` — generated-entry/LBA audit and fail-closed report.
- Create: `tests/test_verify_banks.py` — missing/wrong-entry fixture.
- Modify: `tests/BankSwitchCheck.csproj`, `tests/BankSwitchCheck.cs` — run against generated port assembly and all 96 banks.

**Interfaces:**
- Consumes: `list[Bank]`, `.local/probe/generated/Entry.cs`, individual emitted bank files, built `port/BishiBashi.csproj`.
- Produces: `verify_generated(banks: list[Bank], generated_dir: Path) -> list[dict]`, raising `ValueError` with game/slot for missing register, wrong `LbaStart`/`Base`/`Size`, or absent `[0xENTRYu]` dispatcher key. Write ignored `.local/probe/bank-audit.json` only after static checks; the executable bank switch check adds activation results or fails (no mapped status for failed slots).

- [ ] **Step 1: Write RED verifier tests.** Feed tiny synthetic `Entry.cs`/bank `.cs` text: one correct slot, one missing register, one wrong LBA, and one missing entry. Assert every invalid input raises with its `game slot N`, and two alias slots retain distinct audit rows.

```python
rows = verify_generated([bank], generated_dir)
self.assertEqual(rows[0]['entry'], '0x800C13F0')
(generated_dir / 'super_bank_04.cs').write_text('public int LbaStart => 999;')
with self.assertRaisesRegex(ValueError, 'super slot 4'):
    verify_generated([bank], generated_dir)
```

- [ ] **Step 2: Confirm RED** with `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_verify_banks.py' -v`.
- [ ] **Step 3: Implement bounded static audit.** Inspect exact bank class/register declarations in generated C# (no fuzzy address-only grep over other overlays). Require 96 unique LBA registrations, 94 seeded game entry keys, and the shared pair. Do not coalesce duplicate pointer values from distinct files. Serialize audited fields `game,slot,name,pointer,entry,relativeSector,lba,declaredSize,size,paddedSize,base,generatedEntry,activationTest` under `.local/probe/`; set `activationTest` to `pending` until the runtime check succeeds.

```python
# For a single emitted bank file, require exact metadata/key text.
if f'public int LbaStart => {bank.lba};' not in source or \
   f'public uint Base => 0x{bank.base:08X}u;' not in source or \
   f'public uint Size => 0x{bank.size:X}u;' not in source or \
   (bank.entry is not None and f'[0x{bank.entry:08X}u] =' not in source):
    raise ValueError(f'{bank.game} slot {bank.slot}: missing dispatcher mapping')
```

- [ ] **Step 4: Extend the C# check for real generated overlays.** Reference `../port/BishiBashi.csproj`; deserialize the ignored audit JSON into `BankRow` (defined below) and instantiate `IOverlay` types from `typeof(Recompiled.Entry).Assembly` by catalog name. Register them, then for **each of 94 slots** call `LoadByLba(lba)` and `NotifyWrite(base & 0x1FFFFFFF)`. Assert one active bank per base, correct LBA/base/size, the entry key in the active bank, and that the private dispatcher `_funcMap[entry]` delegate is the active overlay's delegate (reflection is test-only; no product debug API). Switch from largest to smaller, across aliases, and from Super to Hyper. Exit nonzero with game/slot on first failure; only after all pass, rewrite the audit rows with `ActivationTest="passed"`, preserving all other fields.

```csharp
using System.Reflection;
using System.Text.Json;
using RecompOne.Runtime.Context;
using RecompOne.Runtime.Dispatch;
using RecompOne.Runtime.Memory;

var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true, WriteIndented = true };
var catalog = JsonSerializer.Deserialize<List<BankRow>>(File.ReadAllText(args[0]), options)!;
var byName = typeof(Recompiled.Entry).Assembly.GetTypes()
    .Where(t => typeof(IOverlay).IsAssignableFrom(t) && !t.IsAbstract)
    .Select(t => (IOverlay)Activator.CreateInstance(t)!)
    .ToDictionary(o => o.Name);
foreach (var active in byName.Values) Dispatcher.Register(active.Name, active);
var map = (Dictionary<uint, Action<CpuContext, IMemory>>)typeof(Dispatcher)
    .GetField("_funcMap", BindingFlags.NonPublic | BindingFlags.Static)!.GetValue(null)!;
foreach (var bank in catalog.Where(b => b.Slot >= 0)) {
    var active = byName[bank.Name];
    var entry = Convert.ToUInt32(bank.Entry![2..], 16);
    Dispatcher.LoadByLba(bank.Lba);
    Dispatcher.NotifyWrite(bank.Base & 0x1FFFFFFFu);
    if (!Dispatcher.ActiveNames.Contains(bank.Name) ||
        active.LbaStart != bank.Lba || active.Base != bank.Base ||
        active.Size != bank.Size ||
        Dispatcher.ActiveNames.Count(n => byName.TryGetValue(n, out var o) &&
                                          o.Base == bank.Base) != 1 ||
        !active.Functions.TryGetValue(entry, out var expected) ||
        !map.TryGetValue(entry, out var actual) || actual != expected)
        throw new Exception($"{bank.Game} slot {bank.Slot}: activation failed");
}
File.WriteAllText(args[0], JsonSerializer.Serialize(
    catalog.Select(b => b with { ActivationTest = "passed" }), options));

record BankRow(string Game, int Slot, string Name, string? Pointer, string? Entry,
               int RelativeSector, int Lba, int DeclaredSize, int Size,
               int PaddedSize, uint Base, bool GeneratedEntry,
               string ActivationTest);
```

- [ ] **Step 5: GREEN** focused/whole Python suite, `python3 port/tools/recompile.py`, `.local/dotnet/dotnet build port/BishiBashi.csproj -c Release`, `.local/dotnet/dotnet run --project tests/BankSwitchCheck.csproj -c Release -- .local/probe/bank-audit.json`, and `python3 port/tools/verify_banks.py .local/probe/bank-audit.json`; check report counts (46 Super, 48 Hyper, 94 `activationTest: passed`). A failure is a blocker, not a warning that can be ignored.
- [ ] **Step 6: Commit** verifier and tests, not generated translations or audit JSON.

### Task 5: Bounded route checks and user-facing coverage

**Files:**
- Modify: `docs/research/disc-probe.md` — mapping evidence, per-variant coverage totals, next blockers.
- Modify: `port/README.md` — regeneration/audit commands and honest playability status.

**Interfaces:**
- Consumes: Task 4's generated audit and built Linux host.
- Produces: reproducible bounded logs/screenshots under ignored `.local/probe/bank-visual/`, and a concise tracked report; no new gameplay code.

- [ ] **Step 1: Check the known racing route.** With an isolated Xvfb screen, `port/run-linux.sh 'Bishi Bashi Special.cue'`; Super → BishiBashi Alone → Stage Select → slot 4 (four Right inputs from the initial selection, confirm the racing thumbnail). Confirm load of `super_bank_04` at predicted LBA 1221 and absence of the original `0x800C13F0` crash; capture a timestamped screenshot and next failure if any. Compare at least 32 live bytes at the call address against LBA 1221 + address offset before claiming that specific bank's runtime source.

```bash
# Bounded host launch; send the route's keys on the same X display while it runs,
# save the screen and input sequence in .local/probe/bank-visual/, then terminate.
mkdir -p .local/probe/bank-visual
timeout 180s xvfb-run -a -s '-screen 0 640x480x24' \
  port/run-linux.sh 'Bishi Bashi Special.cue' > .local/probe/bank-visual/racing.log 2>&1
```

- [ ] **Step 2: Check Hyper and selected Super paths.** Select Hyper via the keyboard menu; confirm an actual `hyper_bank_06` load near predicted LBA 6265, live RAM/disc identity at `0x80098810`, and no original unmapped call. Repeat a bounded check for previously observed Pins and Roach transitions; record distinct next crashes rather than claiming all 94 games are playable. Identify Burst the Balloon's labeled stage only if screen evidence permits; do not infer from pointer index alone.
- [ ] **Step 3: Publish an accurate report.** Write `docs/research/disc-probe.md` with 94 static/activation counts **only if live source matches**; if Hyper pairing/base or racing source disagrees, stop and mark affected slots blocked rather than mapped. Record tested routes, actual screenshots/log paths, unresolved code/data or runtime defects, and explicit unverified gameplay/audio/gamepad/Windows status. Update `port/README.md` with `python3 port/tools/recompile.py`, `.local/dotnet/dotnet build port/BishiBashi.csproj -c Release`, `.local/dotnet/dotnet run --project tests/BankSwitchCheck.csproj -c Release -- .local/probe/bank-audit.json`, and `python3 port/tools/verify_banks.py .local/probe/bank-audit.json`.
- [ ] **Step 4: Final gate and commit.** Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -q`, the bank-switch executable, Release build, `git diff --check`, and inspect `git status --short` so only tracked source/docs/tests are committed. Commit docs, merge the isolated branch locally into `main` after review, keep `interface.ini` intact, and do not push.
