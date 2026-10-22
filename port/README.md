# Experimental Linux boot

Requires your own `Bishi Bashi Special.bin` and its validated CUE, a .NET 10 SDK at `.local/dotnet/`, pinned RecompOne at `.local/RecompOne/` (`4259b76fa923d1e607a6b3379ef908cb5d5b9354`), and the local disc-probe config/maps under `.local/probe/config/` (see `docs/research/disc-probe.md`). None of these generated/game files are committed.

From the repository root:

```sh
python3 port/tools/recompile.py
.local/dotnet/dotnet build port/BishiBashi.csproj -c Release
port/run-linux.sh 'Bishi Bashi Special.cue'
```

The recompile step preserves the disc's original pad initializer, attaches the controller and CD-poll hooks, and idempotently applies `port/patches/runtime-cd.patch` to the **pinned** local RecompOne checkout before building. Do not skip it when rebuilding from a clean RecompOne clone. The launcher exposes bundled Linux native libraries without installing them system-wide. **This is not yet playable:** Super loads The Pins and Roach code banks; a bounded Roach selection passed `0x800C0CC0` and showed a countdown, not verified gameplay. Hyper still crashes on `0x80098810`. Gamepad and minigames have not been verified. A clean checkout still needs the disc-probe maps generated first.
