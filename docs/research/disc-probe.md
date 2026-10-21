# Bishi Bashi Special disc probe — 2026-10-21

## Input and method

- User-supplied `Bishi Bashi Special.bin`, SHA-256 `76c717d7ca2a99b4a66e692889f277fef8db80761849c11c15c85d7f30436872`, 207,658,080 bytes (88,290 sectors of 2352 bytes).
- `python3 tools/disc_preflight.py 'Bishi Bashi Special.bin'` verified the full SHA-256 and every sector's sync, MODE2 byte, and sequential MSF from `00:02:00`. It wrote a one-track `Bishi Bashi Special.cue` beside the BIN. This establishes a defensible *data* track layout, not perfect XA audio playback or exhaustively verified subchannels.
- `SYSTEM.CNF` points to `SLES_025.37`; the disc volume is `BISHI_BASHI_SPECIAL` (direct raw-sector observations). The CUE and all game bytes stay out of source control.
- REA 6.4.0 `inspect-artifact` rejected both the `.7z` and PS-X executable with `target_unavailable`/unsupported binary format. REA's native analysis providers are unavailable; **there is no REA Evidence ID**. All findings below come from raw-sector inspection or RecompOne, not REA.

## RecompOne results

Pinned upstream revision: [`4259b76fa923d1e607a6b3379ef908cb5d5b9354`](https://github.com/BlackLabelHQ/RecompOne/commit/4259b76fa923d1e607a6b3379ef908cb5d5b9354). Local .NET SDK 10.0.402 at `.local/dotnet/` (system `/usr/bin/dotnet` remains broken). Build succeeded with five upstream warnings, no errors.

Executed with `DOTNET_ROOT="$PWD/.local/dotnet" PATH="$PWD/.local/dotnet:$PATH"`:

```sh
dotnet build .local/RecompOne/RecompOne.Recompiler -c Release
dotnet run --project .local/RecompOne/RecompOne.Recompiler -c Release --no-build -- --probe-disc 'Bishi Bashi Special.cue' -json .local/probe/disc.json -all
dotnet run --project .local/RecompOne/RecompOne.Recompiler -c Release --no-build -- --autoconfigure 'Bishi Bashi Special.cue' -out .local/probe/config -name BishiBashi -sweep-all
```

Probe identified three PS-X executables, all declaring load base `0x80010000`:

| Disc path | Bytes | Probe result |
| --- | ---: | --- |
| `SLES_025.37` | 141,312 | Boot executable (`SYSTEM.CNF`); 463 tentative functions, 190 named |
| `BISHI1.EXE` | 339,968 | Separate EXE at entry `0x800337DC`; 966 tentative functions, 325 named |
| `BISHI2.EXE` | 274,432 | Separate EXE at entry `0x80034BB8`; 963 tentative functions, 241 named |
| `CD_DATA1.BIN` | 9,458,020 | MIPS-like raw code candidate; **no load base resolved** |
| `CD_DATA2.BIN` | 10,865,120 | MIPS-like raw code candidate; **no load base resolved** |

Other inventory: `MENU.BIN` was classified as data, `DMY.` as data, six `.STR` files as media. Classification is heuristic, not proof that those files contain no executable material. SDK-signature matches include ambiguities (16 for boot, 45 for bishi1, 38 for bishi2). Function counts and names are **autoconfiguration guesses**, not established call graph or recovered source.

RecompOne produced `.local/probe/config/BishiBashi.json` and three `funcmaps/*.json`. The config selects `SLES_025.37` as main and `BISHI1.EXE` / `BISHI2.EXE` as modules with 2048-byte PS-X header skips. The CUE path in generated JSON is absolute to this machine and must be made portable before a reusable build. The two `CD_DATA*.BIN` code candidates were **excluded** because RecompOne cannot determine their load addresses. Do not treat the config as runnable or call a generated program playable.

A subsequent `dotnet run --project .local/RecompOne/RecompOne.Recompiler -c Release --no-build -- .local/probe/config/BishiBashi.json` succeeded and wrote generated `Entry.cs`, `main.cs`, `bishi1.cs`, `bishi2.cs`, and `Stubs.cs` under ignored `.local/probe/generated/` (2,399 tentative functions, 147 SDK reimplementations). This establishes **translation only**: the generated code has not been compiled into a host program or executed. Text in the boot executable includes `Bishi Bashi Special` next to `\\BISHI1.EXE;1`, `Bishi Bashi Special2` next to `\\BISHI2.EXE;1`, and the other EXEs refer to `\\CD_DATA1.BIN;1` / `\\CD_DATA2.BIN;1` respectively. Those strings suggest routes, but do not establish control flow, game location, or load addresses.

## Next gate before a playable-build plan

Trace boot → menus → Burst the Balloon, identify which EXE runs that minigame and how the other executables and `CD_DATA*.BIN` are loaded. Resolve any embedded code load addresses and ambiguous SDK functions on the selected path with static or bounded runtime evidence; add only demonstrated compatibility patches. Then plan generated-code compilation and verification on Linux and Windows. If these code/data boundaries cannot be established, stop and reassess rather than inventing gameplay or claiming a port.
