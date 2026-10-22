# Experimental Linux boot

Requires your own `Bishi Bashi Special.bin` and its validated CUE, a .NET 10 SDK at `.local/dotnet/`, pinned RecompOne at `.local/RecompOne/` (`4259b76fa923d1e607a6b3379ef908cb5d5b9354`), and the local disc-probe config/maps under `.local/probe/config/` (see `docs/research/disc-probe.md`). None of these generated/game files are committed.

From the repository root:

```sh
python3 port/tools/recompile.py
.local/dotnet/dotnet build port/BishiBashi.csproj -c Release
port/run-linux.sh 'Bishi Bashi Special.cue'
```

The recompile step validates the owned disc **and requires the configured CUE to be the canonical CUE for that same BIN**, extracts both EXEs' bank tables, generates 47 Super + 49 Hyper sector-sourced code overlays without global linear sweep, preserves the original pad initializer and CD-poll hook, and idempotently applies both tracked runtime patches to the **pinned** RecompOne checkout. Do not skip it after cloning RecompOne. It fails if a requested game-entry mapping is missing. The launcher exposes bundled Linux native libraries without system installation. A clean checkout still needs the ignored disc-probe config/maps under `.local/probe/config/` (see the research report).

To check translated entries and bank-switch activation after the build (the final Python command reports **stored activation status**; source/LBA checks run during `recompile.py` and activation is performed by the preceding C# command):

```sh
.local/dotnet/dotnet run --project tests/BankSwitchCheck.csproj -c Release -- .local/probe/bank-audit.json
python3 port/tools/verify_banks.py .local/probe/bank-audit.json
```

The ignored audit records 46 Super and 48 Hyper **mapped/activation-tested slots**, not playable rounds. Bounded Linux runs passed the old Super racing `0x800C13F0` and Hyper startup `0x80098810` crashes, and displayed partial racing, Pins, Roach, and Hyper Piano screens. After removing sweep, a bounded Hyper route also required the observed shared-bank `0x8009859C` callback; both shared callbacks are explicit disc-backed entries, not stubs. A post-fix Hyper stage-selection run loaded bank 34 without a reported crash but did not verify its gameplay or repeat the earlier Piano intro. Hyper's early `0x80098810` call uses the **shared** bank, not game slot 6. Burst the Balloon gameplay, gamepad, audio, and Windows execution are unverified. For Xvfb visual tests in a Wayland session, unset `WAYLAND_DISPLAY` and set `XDG_SESSION_TYPE=x11`; otherwise GLFW can open on the real display instead.
