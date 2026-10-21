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

## Bounded Linux boot attempt — 2026-10-21

A minimal host in `port/` compiled the generated C# with RecompOne's runtime and accepted an explicit user-owned CUE. Build: `DOTNET_ROOT="$PWD/.local/dotnet" PATH="$PWD/.local/dotnet:$PATH" dotnet build port/BishiBashi.csproj -c Release --nologo` (zero errors; warnings in RecompOne and generated code). The host's three invalid-input scenarios return exit code 2 without initializing the runtime; five Python tests pass. Only Linux compilation has been exercised; there is no Windows build verification.

From the isolated worktree, `timeout 15s xvfb-run -a .local/dotnet/dotnet port/bin/Release/net10.0/BishiBashi.dll "$PWD/Bishi Bashi Special.cue"` exited **134**, not 124: the process aborted with an exception before the timeout. Retained log: ignored `.local/probe/boot.log`. No screenshot/window capture was taken; **no menu, minigame, graphics, or audio is verified**. The runtime wrote two new 131,072-byte `card?.sav` memory-card files into the worktree; these are ignored to prevent accidental staging.

Observed log order:

1. Silk.NET reported no suitable GLFW window platform for GL 4.5, 3.3, or 2.1, then `no usable gl context were found`. The runtime continued; this alone did not terminate the process.
2. Runtime reported loading the `main` overlay, then threw `InvalidOperationException: unmapped call: 0x00000000`. Generated `main.cs` at line 25183 (`func_8002429C`, caller chain `func_800137C8` → `func_800110D8` → `func_80010D48` → boot `func_80016030`) loads a call target from memory address `0x8003186C` and calls the value, which was zero. The immediately preceding generated call is to `0x8001E9BC`. This is an observed null indirect call, **not proof** whether the cause is a bad function map, uninitialized data, incorrect SDK routing, or missing hardware behavior.

After an independent review, `port/Program.cs` now seeds RecompOne's persisted `Settings.System.DiscPath` from the explicit CLI path before `Entry.Run`, and runs translated code through `Runtime.Run` so presentation/events have a host loop. Each wiring change was covered by a failing-then-passing CLI test. A second bounded Xvfb run was launched from ignored `.local/probe/boot-run/`, keeping settings, memory cards, and crash logs out of the tracked tree. It exited **3** (host-reported runtime exception) with the same no-GL warnings and same `0x00000000` indirect call; the new retained log is `.local/probe/boot-after-review.log`. No screen capture was made; neither a working GL window nor minigame behavior has been established.

Next investigate the Linux window-platform native library/setup *and* trace which original initializer should populate `0x8003186C`, checking the mapped function at `0x8001E9BC` and its preceding calls before changing code. The `CD_DATA*.BIN` code candidates were not reached in this bounded attempt; their bases remain unknown. Do not substitute a guessed callback or claim a playable port.

## Next gate before a playable-build plan

Trace boot → menus → Burst the Balloon, identify which EXE runs that minigame and how the other executables and `CD_DATA*.BIN` are loaded. Resolve any embedded code load addresses and ambiguous SDK functions on the selected path with static or bounded runtime evidence; add only demonstrated compatibility patches. Then plan generated-code compilation and verification on Linux and Windows. If these code/data boundaries cannot be established, stop and reassess rather than inventing gameplay or claiming a port.
