# Bishi Bashi Special — experimental native port

An in-progress Windows/Linux port of *Bishi Bashi Special* using [RecompOne](https://github.com/BlackLabelHQ/RecompOne) static recompilation of the original PlayStation code. This is **not an emulator** and does not include the game or its assets.

**Status:** The Linux host boots and reaches some menus and game screens. All 46 Super and 48 Hyper game slots have translated code and pass dispatcher-activation checks; that does **not** mean all games are playable. Some routes show blank or incomplete screens. Burst the Balloon gameplay, full rounds, gamepad, audio, and a native Windows build have not been verified.

## Build and run on Linux

You need your own European `Bishi Bashi Special.bin` (SHA-256 `76c717d7ca2a99b4a66e692889f277fef8db80761849c11c15c85d7f30436872`), Python 3, a .NET 10 SDK installed at `.local/dotnet/`, and the pinned RecompOne source. From the repository root:

```sh
mkdir -p .local/probe
git clone https://github.com/BlackLabelHQ/RecompOne.git .local/RecompOne
git -C .local/RecompOne checkout 4259b76fa923d1e607a6b3379ef908cb5d5b9354
python3 tools/disc_preflight.py 'Bishi Bashi Special.bin'
.local/dotnet/dotnet build .local/RecompOne/RecompOne.Recompiler -c Release
.local/dotnet/dotnet run --project .local/RecompOne/RecompOne.Recompiler -c Release --no-build -- --probe-disc 'Bishi Bashi Special.cue' -json .local/probe/disc.json -all
.local/dotnet/dotnet run --project .local/RecompOne/RecompOne.Recompiler -c Release --no-build -- --autoconfigure 'Bishi Bashi Special.cue' -out .local/probe/config -name BishiBashi -sweep-all
python3 port/tools/recompile.py
.local/dotnet/dotnet build port/BishiBashi.csproj -c Release
port/run-linux.sh 'Bishi Bashi Special.cue'
```

The BIN, generated CUE, local SDK, RecompOne checkout, generated code, and configuration are ignored by Git. The recompile step validates the disc and CUE, then applies patches only to the pinned RecompOne revision. Run commands from the repository root; these are source-build instructions, not a prebuilt release.

For a normal-run log, append `2>&1 | tee .local/probe/game.log` to the launch command. A timestamped `.log` file is otherwise created only on a crash.

See [port/README.md](port/README.md) for build checks and limitations, and [disc research](docs/research/disc-probe.md) for the mapping evidence.
