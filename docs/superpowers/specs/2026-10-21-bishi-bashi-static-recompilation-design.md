# Bishi Bashi Special: Windows/Linux static-recompilation design

## Goal and boundary

Produce native Windows and Linux programs that run game code translated ahead of time from the user's European PlayStation disc, **without launching a PS1 emulator or requiring a BIOS**. The first playable acceptance target is **Burst the Balloon**; the required boot, menu, and shared code paths are in scope only insofar as they are needed to reach and finish that game. A whole-game release, HD assets, networking, and a from-scratch SDL2 gameplay remake are out of scope. This is static recompilation, **not** a hardware-free rewrite: RecompOne's runtime supplies the PlayStation memory, GPU, audio, controller, and disc interfaces used by translated code.

The shipped binaries must not embed or redistribute the disc or generated copyrighted game code. A user supplies their own matching disc image. Any source project should exclude disc images, extracted assets, and generated translations from version control.

## Observed inputs and unknowns

- Local `Bishi Bashi Special.bin` is a 2352-byte-sector disc image with an ISO9660 volume named `BISHI_BASHI_SPECIAL`. `SYSTEM.CNF` names `SLES_025.37` as the boot executable. The disc also contains `BISHI1.EXE`, `BISHI2.EXE`, `CD_DATA1.BIN`, `CD_DATA2.BIN`, `MENU.BIN`, and STR video files. All three named executables start with `PS-X EXE` and their recorded load address is `0x80010000`. These observations came from reading the disc's raw sectors, **not from REA**.
- Which executable and data ranges implement Burst the Balloon, how the game transitions between them, and whether additional code is embedded in the large BIN files are **unknown**. Treat unrecognized code loads as investigation gates, not as ordinary assets.
- The archive had no CUE file. RecompOne's disc reader accepts CUE/BIN or CHD, not a bare `.bin`; reconstructing a CUE requires checking the actual track layout. A single guessed MODE2 track is not evidence that audio and every sector work.
- REA 6.4.0's `inspect-artifact` rejected both the `.7z` and the extracted PS-X EXE as unsupported formats; native decompilation providers are not available in the current setup. No REA function-level Evidence has been obtained. Do not label manual parsing or RecompOne output as REA findings. If a compatible REA provider/loader becomes available, use it to corroborate code and overlay boundaries; otherwise record the limitation.
- RecompOne requires .NET 10. The host's `dotnet` currently fails to find `libhostfxr.so`, so building cannot yet be verified. Windows and Linux publication are targets, not demonstrated results.

## Approach

Use [RecompOne](https://github.com/BlackLabelHQ/RecompOne) pinned to a tested revision. Its [porting guide](https://github.com/BlackLabelHQ/RecompOne/wiki/How-to-recompile-a-game%3F) describes a config, function maps, generated C#, optional game-specific patches, and a runtime reference. The [X-Men: Mutant Academy 2 port](https://github.com/GTTeancum/xmen-mutant-academy-2-pc/blob/main/port/README.md) is a process reference, **not** reusable Bishi Bashi mappings or patches.

1. **Establish a reproducible input.** Validate the BIN's sector size, ISO filesystem, executable hashes, boot record, and track structure. Create a local CUE only if the layout is substantiated; keep both files untracked. Pin the RecompOne revision and restore a working .NET 10 SDK through a separately approved setup step.
2. **Probe and map.** Use RecompOne's disc probe/autoconfiguration for the boot EXE and discovered PS-X EXEs; review its guesses. Determine whether `BISHI1.EXE` and `BISHI2.EXE` should be treated as loadable modules and whether code within `CD_DATA*.BIN` or `MENU.BIN` needs separately specified load addresses. Generate and curate function maps; identify PSYQ SDK functions to route to runtime implementations. Use REA only where its connected tools actually support the artifact. Keep a small evidence ledger for guesses, confirmed mappings, and unknowns.
3. **Reach the selected minigame.** Generate C# from the necessary modules. Start the translated boot entry against the runtime and use bounded logs and reproducible input to locate the menu → Burst the Balloon path. Patch only demonstrated integration gaps (for example, an unsupported SDK call or module loader); avoid gameplay rewrites unless an observed incompatibility requires one. The milestone cannot be called playable merely because C# was generated or a title screen rendered.
4. **Publish and verify.** Build `win-x64` and `linux-x64` from the same translated sources, each using the user's disc image at runtime. Validate launch, input, game entry, timer, button presses, win/loss, and return to menu on both platforms. If Windows cannot be run in this environment, mark its runtime test pending rather than claiming success from a cross-build.

## Data flow and failure handling

User-owned BIN + validated CUE/CHD → RecompOne disc probe and curated config/maps → generated C# (ignored) → platform-specific .NET application + RecompOne runtime → user-supplied disc at launch. Missing/mismatched disc, missing tracks, unresolved control transfers, unknown module bases, and unsupported runtime calls should produce explicit diagnostics. No silent fallback to an emulator or invented gameplay rules.

## Verification gates

- Disc identity and track layout are documented; the same known inputs reproducibly generate the same maps/build.
- Every executed function on the chosen path resolves to translated code or a reviewed SDK/patch implementation; unresolved calls are reported, not hidden.
- A repeatable input sequence reaches Burst the Balloon and completes one winning and one losing round with sensible visual/audio feedback; compare rules/timing to reference behavior where obtainable.
- Linux binary builds and is exercised locally; Windows binary builds and is exercised on Windows before either is described as fully verified.

## Decision points

If CUE reconstruction or unknown embedded modules prevent a trustworthy boot, stop and report the specific gap before expanding scope. If RecompOne's hardware/runtime behavior needs extensive game-specific reimplementation, reassess this approach against the smaller, from-scratch minigame rewrite. A first minigame is a validation target, not a claim that static recompilation can exclude the rest of the boot chain.
